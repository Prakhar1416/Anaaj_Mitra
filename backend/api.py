import json
import logging
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Query, Request, Response
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from backend.common import ID_PATTERN
from backend.config import PROJECT_ROOT, Settings, load_settings
from backend.coordinator import Coordinator
from backend.database import initialize_database
from backend.errors import AppError
from backend.health_agent import HealthAgent
from backend.logistics_agent import LogisticsAgent
from backend.schemas import (
    AgentLogList,
    HamletOut,
    HealthEventList,
    HealthReportIn,
    HealthReportList,
    HealthReportResult,
    HealthStatusList,
    HealthStatusOut,
    LogisticsDecisionList,
    LogisticsDecisionOut,
    LogisticsStatusOut,
    ReassessIn,
    StateSnapshot,
    StreamStateOut,
    WarehouseOut,
    WarehouseStockIn,
)
from backend.pipeline import run_coordination
from backend.shared_state import STREAMS, SharedState

logger = logging.getLogger("anaaj_mitra")


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or load_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        initialize_database(resolved)
        shared_state = SharedState(resolved.database_path)
        logistics_agent = LogisticsAgent(shared_state, resolved.min_delivery_kg)
        coordinator = Coordinator(shared_state, logistics_agent)
        app.state.settings = resolved
        app.state.shared_state = shared_state
        app.state.logistics_agent = logistics_agent
        app.state.coordinator = coordinator
        app.state.health_agent = HealthAgent(shared_state, coordinator)
        yield

    app = FastAPI(
        title="Anaaj Mitra API",
        version="0.2.0",
        summary="Shared state, health-priority reports, and logistics reassessment.",
        lifespan=lifespan,
        openapi_tags=[
            {"name": "System", "description": "Process health and public configuration."},
            {"name": "Health", "description": "Community health-worker nutrition priority."},
            {"name": "State", "description": "Shared hamlet, warehouse, stream, and log state."},
            {"name": "Logistics", "description": "Priority reassessment recommendations."},
            {"name": "Storage", "description": "Warehouse stock written by the storage stream."},
            {
                "name": "Coordination",
                "description": "Water, crop, storage, spoilage, logistics, trust, and loan in dependency order.",
            },
        ],
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:8000",
            "http://localhost:8000",
            "http://127.0.0.1:8001",
            "http://localhost:8001",
        ],
        allow_methods=["GET", "POST", "PUT", "PATCH"],
        allow_headers=["Content-Type"],
    )

    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": {"message": exc.message, "code": exc.code}},
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation(request: Request, exc: RequestValidationError):
        shared = getattr(request.app.state, "shared_state", None)
        if shared is not None and request.url.path.startswith("/api/health"):
            shared.append_log(
                {
                    "agent_name": "health_agent",
                    "event_type": "HEALTH_REPORT_REJECTED",
                    "event_id": None,
                    "hamlet_id": None,
                    "warehouse_id": None,
                    "input_summary": "Request body failed validation.",
                    "result": "rejected",
                    "status": "failure",
                    "error_detail": "The health report was malformed.",
                }
            )
        return await request_validation_exception_handler(request, exc)

    @app.exception_handler(sqlite3.Error)
    async def handle_database(_: Request, exc: sqlite3.Error) -> JSONResponse:
        logger.exception("Database error: %s", exc)
        return JSONResponse(
            status_code=500,
            content={
                "detail": {
                    "message": "The request could not be saved.",
                    "code": "database_error",
                }
            },
        )

    @app.get("/health", tags=["System"])
    def health_check() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/config", tags=["System"])
    def get_config(request: Request) -> dict[str, object]:
        return request.app.state.settings.public_dict()

    @app.get("/", include_in_schema=False)
    def dashboard() -> FileResponse:
        return _static_file("index.html", "text/html")

    @app.get("/style.css", include_in_schema=False)
    def styles() -> FileResponse:
        return _static_file("style.css", "text/css")

    @app.get("/script.js", include_in_schema=False)
    def browser_script() -> FileResponse:
        return _static_file("script.js", "text/javascript")

    @app.post(
        "/api/health/reports",
        response_model=HealthReportResult,
        status_code=201,
        tags=["Health"],
        summary="Submit a nutrition-priority report",
    )
    def submit_health_report(
        body: HealthReportIn, request: Request, response: Response
    ) -> dict[str, Any]:
        """Accept a health-worker report.

        An identical resubmission returns HTTP 200 with duplicate=true and does
        not create another logistics decision. A changed priority, reason, or
        reporter returns HTTP 201 and asks the coordinator to reassess.
        """
        result = request.app.state.health_agent.process_health_report(
            _report_payload(body)
        )
        response.status_code = 200 if result["duplicate"] else 201
        return result

    @app.put(
        "/api/health/hamlets/{hamlet_id}",
        response_model=HealthReportResult,
        tags=["Health"],
        summary="Correct a hamlet nutrition-priority report",
    )
    def correct_health_report(
        hamlet_id: str, body: HealthReportIn, request: Request
    ) -> dict[str, Any]:
        if body.hamlet_id != hamlet_id:
            raise AppError(
                "hamlet_mismatch",
                "The hamlet_id in the body must match the path.",
            )
        return request.app.state.health_agent.process_health_report(_report_payload(body))

    @app.get(
        "/api/health/hamlets/{hamlet_id}",
        response_model=HealthStatusOut,
        tags=["Health"],
    )
    def get_health_status(hamlet_id: str, request: Request) -> dict[str, Any]:
        hamlet = _require_hamlet(request, hamlet_id)
        return hamlet["health"]

    @app.get(
        "/api/health/priorities",
        response_model=HealthStatusList,
        tags=["Health"],
    )
    def list_priority_hamlets(request: Request) -> dict[str, Any]:
        return {"hamlets": request.app.state.shared_state.list_priority_hamlets()}

    @app.get("/api/health/events", response_model=HealthEventList, tags=["Health"])
    def list_health_events(
        request: Request,
        hamlet_id: str | None = None,
        limit: int = Query(default=50, ge=1, le=200),
    ) -> dict[str, Any]:
        return {
            "events": request.app.state.shared_state.list_events(hamlet_id, limit)
        }

    @app.get("/api/health/reports", response_model=HealthReportList, tags=["Health"])
    def list_health_reports(
        request: Request,
        hamlet_id: str | None = None,
        limit: int = Query(default=50, ge=1, le=200),
    ) -> dict[str, Any]:
        return {
            "reports": request.app.state.shared_state.list_reports(hamlet_id, limit)
        }

    @app.get("/api/state", response_model=StateSnapshot, tags=["State"])
    def get_state(request: Request) -> dict[str, Any]:
        return request.app.state.shared_state.snapshot()

    @app.get("/api/hamlets/{hamlet_id}", response_model=HamletOut, tags=["State"])
    def get_hamlet(hamlet_id: str, request: Request) -> dict[str, Any]:
        return _require_hamlet(request, hamlet_id)

    @app.get("/api/logs", response_model=AgentLogList, tags=["State"])
    def list_logs(
        request: Request,
        agent: str | None = None,
        hamlet_id: str | None = None,
        event_id: str | None = None,
        status: str | None = None,
        limit: int = Query(default=50, ge=1, le=200),
    ) -> dict[str, Any]:
        return {
            "logs": request.app.state.shared_state.list_logs(
                agent_name=agent,
                hamlet_id=hamlet_id,
                event_id=event_id,
                status=status,
                limit=limit,
            )
        }

    @app.put(
        "/api/streams/{stream}/{entity_id}",
        response_model=StreamStateOut,
        tags=["State"],
        summary="Merge a partial update into another stream's state",
    )
    def update_stream(
        stream: str, entity_id: str, payload: dict[str, Any], request: Request
    ) -> dict[str, Any]:
        _check_stream_target(stream, entity_id, payload)
        return request.app.state.shared_state.merge_stream(stream, entity_id, payload)

    @app.get(
        "/api/streams/{stream}/{entity_id}",
        response_model=StreamStateOut,
        tags=["State"],
    )
    def get_stream(stream: str, entity_id: str, request: Request) -> dict[str, Any]:
        if stream not in STREAMS:
            raise AppError("unknown_stream", f"Unknown stream '{stream}'.", 404)
        record = request.app.state.shared_state.get_stream(stream, entity_id)
        if record is None:
            raise AppError(
                "stream_not_found",
                f"No state is stored for {stream}/{entity_id}.",
                404,
            )
        return record

    @app.get(
        "/api/logistics/decisions",
        response_model=LogisticsDecisionList,
        tags=["Logistics"],
    )
    def list_logistics_decisions(
        request: Request,
        hamlet_id: str | None = None,
        limit: int = Query(default=50, ge=1, le=200),
    ) -> dict[str, Any]:
        return {
            "decisions": request.app.state.shared_state.list_decisions(
                hamlet_id, limit
            )
        }

    @app.get(
        "/api/logistics/hamlets/{hamlet_id}",
        response_model=LogisticsStatusOut,
        tags=["Logistics"],
    )
    def get_logistics_status(hamlet_id: str, request: Request) -> dict[str, Any]:
        hamlet = _require_hamlet(request, hamlet_id)
        return {"hamlet_id": hamlet_id, "decision": hamlet["logistics"]}

    @app.post(
        "/api/logistics/reassess",
        response_model=LogisticsDecisionOut,
        tags=["Logistics"],
        summary="Ask the coordinator to reassess the hamlet's current priority",
    )
    def reassess_logistics(body: ReassessIn, request: Request) -> dict[str, Any]:
        return request.app.state.coordinator.request_reassessment(body.hamlet_id)

    @app.patch(
        "/api/storage/warehouses/{warehouse_id}",
        response_model=WarehouseOut,
        tags=["Storage"],
        summary="Update warehouse stock without changing hamlet health",
    )
    def update_warehouse_stock(
        warehouse_id: str, body: WarehouseStockIn, request: Request
    ) -> dict[str, Any]:
        updated = request.app.state.shared_state.update_warehouse(
            warehouse_id,
            body.model_dump(exclude_unset=True),
        )
        if updated is None:
            raise AppError(
                "unknown_warehouse",
                f"Unknown warehouse_id '{warehouse_id}'.",
                404,
            )
        return updated

    @app.post("/api/pipeline/run", tags=["Coordination"])
    def run_pipeline(payload: dict[str, Any], request: Request) -> dict[str, Any]:
        """Run the merged agents and publish stock, spoilage, finance, and verification."""
        result = run_coordination(
            request.app.state.shared_state,
            request.app.state.settings,
            payload,
        )
        request.app.state.pipeline_result = result
        return result

    @app.get("/api/pipeline/latest", tags=["Coordination"])
    def latest_pipeline(request: Request) -> dict[str, Any]:
        result = getattr(request.app.state, "pipeline_result", None)
        if result is None:
            raise AppError(
                "pipeline_not_run",
                "Run the coordination pipeline before reading its latest result.",
                404,
            )
        return result

    return app


def _report_payload(body: HealthReportIn) -> dict[str, Any]:
    payload = body.model_dump()
    reported_at = payload.get("reported_at")
    if isinstance(reported_at, datetime):
        if reported_at.tzinfo is None:
            reported_at = reported_at.replace(tzinfo=timezone.utc)
        payload["reported_at"] = (
            reported_at.astimezone(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )
    return payload


def _require_hamlet(request: Request, hamlet_id: str) -> dict[str, Any]:
    hamlet = request.app.state.shared_state.get_hamlet(hamlet_id)
    if hamlet is None:
        raise AppError(
            "unknown_hamlet",
            f"Unknown hamlet_id '{hamlet_id}'.",
            404,
        )
    return hamlet


def _check_stream_target(stream: str, entity_id: str, payload: dict[str, Any]) -> None:
    if stream not in STREAMS:
        raise AppError("unknown_stream", f"Unknown stream '{stream}'.", 404)
    if not ID_PATTERN.fullmatch(entity_id):
        raise AppError(
            "invalid_entity_id",
            "entity_id must be 1-64 characters of letters, numbers, '_' or '-'.",
        )
    if len(json.dumps(payload)) > 20000:
        raise AppError("payload_too_large", "Stream payload exceeds 20000 bytes.")


def _static_file(name: str, media_type: str) -> FileResponse:
    path = PROJECT_ROOT / name
    if not path.is_file():
        raise AppError("not_found", f"{name} is not available.", 404)
    return FileResponse(path, media_type=media_type)


app = create_app()
