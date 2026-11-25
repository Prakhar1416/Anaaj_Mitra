from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator


def _strict_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    raise ValueError("nutrition_priority must be a JSON boolean")


NutritionPriority = Annotated[bool, BeforeValidator(_strict_bool)]
IDENTIFIER = r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$"


class HealthReportIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hamlet_id: str = Field(pattern=IDENTIFIER)
    nutrition_priority: NutritionPriority
    reason: str | None = Field(default=None, max_length=500)
    reported_by: str | None = Field(default=None, pattern=IDENTIFIER)
    reported_at: datetime | None = None
    idempotency_key: str | None = Field(default=None, pattern=IDENTIFIER)


class LogisticsDecisionOut(BaseModel):
    decision_id: str
    event_id: str | None = None
    hamlet_id: str
    warehouse_id: str | None = None
    decision: str
    recommendation: str
    stock_available: bool
    feasible: bool
    nutrition_priority: bool
    spoilage_risk: str | None = None
    delivery_completed: bool
    details: dict[str, Any]
    created_at: str


class HealthReportResult(BaseModel):
    accepted: bool
    duplicate: bool
    status: str
    reassessment_triggered: bool
    hamlet_id: str
    nutrition_priority: bool
    reason: str | None = None
    reported_by: str | None = None
    event_id: str | None = None
    event_type: str | None = None
    report_id: str | None = None
    message: str
    logistics_decision: LogisticsDecisionOut | None = None


class HealthStatusOut(BaseModel):
    hamlet_id: str
    name: str
    nutrition_priority: bool
    reason: str | None = None
    reported_by: str | None = None
    reported_at: str | None = None
    updated_at: str | None = None
    last_event_id: str | None = None


class HealthStatusList(BaseModel):
    hamlets: list[HealthStatusOut]


class HealthEventOut(BaseModel):
    event_id: str
    event_type: str
    hamlet_id: str
    nutrition_priority: bool
    source: str
    reason: str | None = None
    reported_by: str | None = None
    report_id: str | None = None
    timestamp: str


class HealthEventList(BaseModel):
    events: list[HealthEventOut]


class HealthReportOut(BaseModel):
    report_id: str
    hamlet_id: str
    nutrition_priority: bool
    reason: str | None = None
    reported_by: str | None = None
    reported_at: str
    idempotency_key: str | None = None
    event_id: str | None = None
    created_at: str


class HealthReportList(BaseModel):
    reports: list[HealthReportOut]


class AgentLogOut(BaseModel):
    log_id: int
    agent_name: str
    event_type: str
    event_id: str | None = None
    hamlet_id: str | None = None
    warehouse_id: str | None = None
    input_summary: str
    result: str
    status: str
    error_detail: str | None = None
    timestamp: str


class AgentLogList(BaseModel):
    logs: list[AgentLogOut]


class LogisticsDecisionList(BaseModel):
    decisions: list[LogisticsDecisionOut]


class LogisticsStatusOut(BaseModel):
    hamlet_id: str
    decision: LogisticsDecisionOut | None = None


class HamletOut(BaseModel):
    hamlet_id: str
    name: str
    health: HealthStatusOut
    logistics: LogisticsDecisionOut | None = None


class StateSnapshot(BaseModel):
    hamlets: dict[str, Any]
    warehouses: dict[str, Any]
    health: dict[str, Any]
    environment: dict[str, Any]
    storage: dict[str, Any]
    logistics: dict[str, Any]
    finance: dict[str, Any]
    verification: dict[str, Any]
    agent_logs: list[dict[str, Any]]


class ReassessIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hamlet_id: str = Field(pattern=IDENTIFIER)


class WarehouseStockIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    available_stock_kg: float | None = Field(default=None, ge=0)
    fill_percent: int | None = Field(default=None, ge=0, le=100)
    capacity_kg: float | None = Field(default=None, ge=0)
    grain_type: str | None = Field(default=None, min_length=1, max_length=32)
    stock_source: str | None = Field(default=None, min_length=1, max_length=32)

    @model_validator(mode="after")
    def at_least_one_field(self) -> "WarehouseStockIn":
        if all(
            value is None
            for value in (
                self.available_stock_kg,
                self.fill_percent,
                self.capacity_kg,
                self.grain_type,
                self.stock_source,
            )
        ):
            raise ValueError("At least one warehouse field is required")
        return self


class WarehouseOut(BaseModel):
    warehouse_id: str
    name: str
    fill_percent: int
    capacity_kg: float
    available_stock_kg: float
    grain_type: str
    stock_source: str
    updated_at: str | None = None


class StreamStateOut(BaseModel):
    stream: str
    entity_id: str
    payload: dict[str, Any]
    updated_at: str
