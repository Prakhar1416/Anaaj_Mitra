import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from backend.common import utcnow_iso
from backend.database import connect

STREAMS = ("environment", "storage", "finance", "verification")


def _bool(value: object) -> bool:
    return bool(value)


def _loads(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    loaded = json.loads(value)
    if isinstance(loaded, dict):
        return loaded
    return {}


class SharedState:
    """SQLite-backed shared state.

    Each write method updates only the columns or stream it is given.
    A hamlet health update does not rewrite warehouse stock, and a stock
    update does not rewrite nutrition priority.
    """

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        connection = connect(self.database_path)
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def hamlet_exists(
        self, hamlet_id: str, connection: sqlite3.Connection | None = None
    ) -> bool:
        def read(current: sqlite3.Connection) -> bool:
            row = current.execute(
                "SELECT 1 FROM hamlets WHERE hamlet_id = ?",
                (hamlet_id,),
            ).fetchone()
            return row is not None

        return self._read(connection, read)

    def get_hamlet(self, hamlet_id: str) -> dict[str, Any] | None:
        row = self._hamlet_row(hamlet_id)
        if row is None:
            return None
        return self._hamlet_view(row)

    def list_priority_hamlets(self) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            rows = connection.execute(
                """
                SELECT * FROM hamlets
                WHERE nutrition_priority = 1
                ORDER BY hamlet_id
                """
            ).fetchall()
        return [self._health_from_row(row) for row in rows]

    def list_warehouses(self) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            rows = connection.execute(
                "SELECT * FROM warehouses ORDER BY warehouse_id"
            ).fetchall()
        return [self._warehouse_from_row(row) for row in rows]

    def get_warehouse(self, warehouse_id: str) -> dict[str, Any] | None:
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM warehouses WHERE warehouse_id = ?",
                (warehouse_id,),
            ).fetchone()
        if row is None:
            return None
        return self._warehouse_from_row(row)

    def update_warehouse(
        self, warehouse_id: str, fields: dict[str, Any]
    ) -> dict[str, Any] | None:
        allowed = {
            "fill_percent": "fill_percent",
            "capacity_kg": "capacity_kg",
            "available_stock_kg": "available_stock_kg",
            "grain_type": "grain_type",
            "stock_source": "stock_source",
        }
        assignments = []
        values: list[Any] = []
        for key, column in allowed.items():
            if key in fields and fields[key] is not None:
                assignments.append(f"{column} = ?")
                values.append(fields[key])
        if not assignments:
            return self.get_warehouse(warehouse_id)
        assignments.append("updated_at = ?")
        values.append(utcnow_iso())
        values.append(warehouse_id)
        with self.transaction() as connection:
            cursor = connection.execute(
                f"UPDATE warehouses SET {', '.join(assignments)} WHERE warehouse_id = ?",
                values,
            )
            if cursor.rowcount == 0:
                return None
            row = connection.execute(
                "SELECT * FROM warehouses WHERE warehouse_id = ?",
                (warehouse_id,),
            ).fetchone()
        return self._warehouse_from_row(row)

    def get_report_by_key(
        self, idempotency_key: str, connection: sqlite3.Connection
    ) -> dict[str, Any] | None:
        row = connection.execute(
            "SELECT * FROM health_reports WHERE idempotency_key = ?",
            (idempotency_key,),
        ).fetchone()
        return dict(row) if row else None

    def latest_report(
        self, hamlet_id: str, connection: sqlite3.Connection
    ) -> dict[str, Any] | None:
        row = connection.execute(
            """
            SELECT * FROM health_reports
            WHERE hamlet_id = ?
            ORDER BY created_at DESC, report_id DESC
            LIMIT 1
            """,
            (hamlet_id,),
        ).fetchone()
        return dict(row) if row else None

    def insert_health_report(
        self, report: dict[str, Any], connection: sqlite3.Connection
    ) -> None:
        connection.execute(
            """
            INSERT INTO health_reports (
                report_id, hamlet_id, nutrition_priority, reason, reported_by,
                reported_at, idempotency_key, event_id, result_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)
            """,
            (
                report["report_id"],
                report["hamlet_id"],
                int(report["nutrition_priority"]),
                report["reason"],
                report["reported_by"],
                report["reported_at"],
                report["idempotency_key"],
                report["event_id"],
                report["created_at"],
            ),
        )

    def update_report_result(self, report_id: str, result: dict[str, Any]) -> None:
        with self.transaction() as connection:
            connection.execute(
                "UPDATE health_reports SET result_json = ? WHERE report_id = ?",
                (json.dumps(result), report_id),
            )

    def update_hamlet_health(
        self, health: dict[str, Any], connection: sqlite3.Connection
    ) -> None:
        connection.execute(
            """
            UPDATE hamlets
            SET nutrition_priority = ?,
                priority_reason = ?,
                priority_reported_by = ?,
                priority_reported_at = ?,
                priority_updated_at = ?,
                last_event_id = ?
            WHERE hamlet_id = ?
            """,
            (
                int(health["nutrition_priority"]),
                health["reason"],
                health["reported_by"],
                health["reported_at"],
                health["updated_at"],
                health["last_event_id"],
                health["hamlet_id"],
            ),
        )

    def insert_event(
        self, event: dict[str, Any], connection: sqlite3.Connection
    ) -> None:
        connection.execute(
            """
            INSERT INTO health_priority_events (
                event_id, event_type, hamlet_id, nutrition_priority, source,
                reason, reported_by, report_id, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event["event_id"],
                event["event_type"],
                event["hamlet_id"],
                int(event["nutrition_priority"]),
                event["source"],
                event.get("reason"),
                event.get("reported_by"),
                event.get("report_id"),
                event["timestamp"],
            ),
        )

    def list_events(
        self, hamlet_id: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        return self._filtered_rows(
            """
            SELECT * FROM health_priority_events
            {where}
            ORDER BY timestamp DESC, event_id DESC
            LIMIT ?
            """,
            hamlet_id=hamlet_id,
            limit=limit,
            transform=self._event_from_row,
        )

    def list_reports(
        self, hamlet_id: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        return self._filtered_rows(
            """
            SELECT report_id, hamlet_id, nutrition_priority, reason, reported_by,
                   reported_at, idempotency_key, event_id, created_at
            FROM health_reports
            {where}
            ORDER BY created_at DESC, report_id DESC
            LIMIT ?
            """,
            hamlet_id=hamlet_id,
            limit=limit,
            transform=self._report_from_row,
        )

    def insert_decision(self, decision: dict[str, Any]) -> dict[str, Any]:
        with self.transaction() as connection:
            connection.execute(
                """
                INSERT INTO logistics_decisions (
                    decision_id, event_id, hamlet_id, warehouse_id, decision,
                    recommendation, stock_available, feasible, nutrition_priority,
                    spoilage_risk, delivery_completed, details_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    decision["decision_id"],
                    decision.get("event_id"),
                    decision["hamlet_id"],
                    decision.get("warehouse_id"),
                    decision["decision"],
                    decision["recommendation"],
                    int(decision["stock_available"]),
                    int(decision["feasible"]),
                    int(decision["nutrition_priority"]),
                    decision.get("spoilage_risk"),
                    int(decision["delivery_completed"]),
                    json.dumps(decision.get("details") or {}),
                    decision["created_at"],
                ),
            )
        return decision

    def list_decisions(
        self, hamlet_id: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        return self._filtered_rows(
            """
            SELECT * FROM logistics_decisions
            {where}
            ORDER BY created_at DESC, decision_id DESC
            LIMIT ?
            """,
            hamlet_id=hamlet_id,
            limit=limit,
            transform=self._decision_from_row,
        )

    def latest_decision(self, hamlet_id: str) -> dict[str, Any] | None:
        decisions = self.list_decisions(hamlet_id=hamlet_id, limit=1)
        return decisions[0] if decisions else None

    def append_log(
        self,
        entry: dict[str, Any],
        connection: sqlite3.Connection | None = None,
    ) -> None:
        def write(current: sqlite3.Connection) -> None:
            current.execute(
                """
                INSERT INTO agent_logs (
                    agent_name, event_type, event_id, hamlet_id, warehouse_id,
                    input_summary, result, status, error_detail, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry["agent_name"],
                    entry["event_type"],
                    entry.get("event_id"),
                    entry.get("hamlet_id"),
                    entry.get("warehouse_id"),
                    str(entry.get("input_summary") or "")[:500],
                    str(entry.get("result") or "")[:500],
                    entry["status"],
                    None
                    if entry.get("error_detail") is None
                    else str(entry["error_detail"])[:500],
                    entry.get("timestamp") or utcnow_iso(),
                ),
            )

        if connection is not None:
            write(connection)
            return
        with self.transaction() as owned:
            write(owned)

    def list_logs(
        self,
        agent_name: str | None = None,
        hamlet_id: str | None = None,
        event_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        parameters: list[Any] = []
        if agent_name:
            clauses.append("agent_name = ?")
            parameters.append(agent_name)
        if hamlet_id:
            clauses.append("hamlet_id = ?")
            parameters.append(hamlet_id)
        if event_id:
            clauses.append("event_id = ?")
            parameters.append(event_id)
        if status:
            clauses.append("status = ?")
            parameters.append(status)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        parameters.append(limit)
        with self.transaction() as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM agent_logs
                {where}
                ORDER BY log_id DESC
                LIMIT ?
                """,
                parameters,
            ).fetchall()
        return [self._log_from_row(row) for row in rows]

    def get_stream(self, stream: str, entity_id: str) -> dict[str, Any] | None:
        with self.transaction() as connection:
            row = connection.execute(
                """
                SELECT payload_json, updated_at FROM stream_state
                WHERE stream = ? AND entity_id = ?
                """,
                (stream, entity_id),
            ).fetchone()
        if row is None:
            return None
        return {
            "stream": stream,
            "entity_id": entity_id,
            "payload": _loads(row["payload_json"]),
            "updated_at": row["updated_at"],
        }

    def merge_stream(
        self, stream: str, entity_id: str, patch: dict[str, Any]
    ) -> dict[str, Any]:
        timestamp = utcnow_iso()
        with self.transaction() as connection:
            row = connection.execute(
                """
                SELECT payload_json FROM stream_state
                WHERE stream = ? AND entity_id = ?
                """,
                (stream, entity_id),
            ).fetchone()
            payload = _loads(row["payload_json"]) if row else {}
            payload.update(patch)
            connection.execute(
                """
                INSERT INTO stream_state (stream, entity_id, payload_json, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(stream, entity_id) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (stream, entity_id, json.dumps(payload), timestamp),
            )
        return {
            "stream": stream,
            "entity_id": entity_id,
            "payload": payload,
            "updated_at": timestamp,
        }

    def environment_spoilage_risk(self) -> str | None:
        record = self.get_stream("environment", "village")
        if record is None:
            return None
        risk = record["payload"].get("spoilage_risk")
        if not isinstance(risk, str) or not risk.strip():
            return None
        return risk.strip().upper()

    def snapshot(self) -> dict[str, Any]:
        with self.transaction() as connection:
            hamlet_rows = [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM hamlets ORDER BY hamlet_id"
                ).fetchall()
            ]
            warehouse_rows = [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM warehouses ORDER BY warehouse_id"
                ).fetchall()
            ]
            decision_rows = [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT * FROM logistics_decisions
                    ORDER BY created_at DESC, decision_id DESC
                    LIMIT 50
                    """
                ).fetchall()
            ]
            log_rows = [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM agent_logs ORDER BY log_id DESC LIMIT 50"
                ).fetchall()
            ]
            stream_rows = [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM stream_state ORDER BY stream, entity_id"
                ).fetchall()
            ]

        latest: dict[str, dict[str, Any]] = {}
        for row in decision_rows:
            latest.setdefault(row["hamlet_id"], row)

        hamlets: dict[str, Any] = {}
        priority_ids: list[str] = []
        for row in hamlet_rows:
            decision_row = latest.get(row["hamlet_id"])
            view = {
                "hamlet_id": row["hamlet_id"],
                "name": row["name"],
                "health": self._health_from_mapping(row),
                "logistics": None
                if decision_row is None
                else self._decision_from_mapping(decision_row),
            }
            hamlets[row["hamlet_id"]] = view
            if view["health"]["nutrition_priority"]:
                priority_ids.append(row["hamlet_id"])

        streams: dict[str, dict[str, Any]] = {name: {} for name in STREAMS}
        for row in stream_rows:
            if row["stream"] in streams:
                streams[row["stream"]][row["entity_id"]] = {
                    "payload": _loads(row["payload_json"]),
                    "updated_at": row["updated_at"],
                }

        return {
            "hamlets": hamlets,
            "warehouses": {
                row["warehouse_id"]: self._warehouse_from_mapping(row)
                for row in warehouse_rows
            },
            "health": {"priority_hamlet_ids": priority_ids},
            "environment": streams["environment"],
            "storage": streams["storage"],
            "logistics": {
                "decisions": [
                    self._decision_from_mapping(row) for row in decision_rows
                ]
            },
            "finance": streams["finance"],
            "verification": streams["verification"],
            "agent_logs": [self._log_from_mapping(row) for row in log_rows],
        }

    def _hamlet_row(self, hamlet_id: str) -> sqlite3.Row | None:
        with self.transaction() as connection:
            return connection.execute(
                "SELECT * FROM hamlets WHERE hamlet_id = ?",
                (hamlet_id,),
            ).fetchone()

    def _hamlet_view(
        self, row: sqlite3.Row, logistics: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        if logistics is None:
            logistics = self.latest_decision(row["hamlet_id"])
        return {
            "hamlet_id": row["hamlet_id"],
            "name": row["name"],
            "health": self._health_from_row(row),
            "logistics": logistics,
        }

    def _health_from_row(self, row: sqlite3.Row) -> dict[str, Any]:
        return self._health_from_mapping(row)

    def _health_from_mapping(self, row: Any) -> dict[str, Any]:
        return {
            "hamlet_id": row["hamlet_id"],
            "name": row["name"],
            "nutrition_priority": _bool(row["nutrition_priority"]),
            "reason": row["priority_reason"],
            "reported_by": row["priority_reported_by"],
            "reported_at": row["priority_reported_at"],
            "updated_at": row["priority_updated_at"],
            "last_event_id": row["last_event_id"],
        }

    def _warehouse_from_row(self, row: sqlite3.Row) -> dict[str, Any]:
        return self._warehouse_from_mapping(row)

    def _warehouse_from_mapping(self, row: Any) -> dict[str, Any]:
        return {
            "warehouse_id": row["warehouse_id"],
            "name": row["name"],
            "fill_percent": row["fill_percent"],
            "capacity_kg": row["capacity_kg"],
            "available_stock_kg": row["available_stock_kg"],
            "grain_type": row["grain_type"],
            "stock_source": row["stock_source"],
            "updated_at": row["updated_at"],
        }

    def _event_from_row(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "event_id": row["event_id"],
            "event_type": row["event_type"],
            "hamlet_id": row["hamlet_id"],
            "nutrition_priority": _bool(row["nutrition_priority"]),
            "source": row["source"],
            "reason": row["reason"],
            "reported_by": row["reported_by"],
            "report_id": row["report_id"],
            "timestamp": row["timestamp"],
        }

    def _report_from_row(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "report_id": row["report_id"],
            "hamlet_id": row["hamlet_id"],
            "nutrition_priority": _bool(row["nutrition_priority"]),
            "reason": row["reason"],
            "reported_by": row["reported_by"],
            "reported_at": row["reported_at"],
            "idempotency_key": row["idempotency_key"],
            "event_id": row["event_id"],
            "created_at": row["created_at"],
        }

    def _decision_from_row(self, row: sqlite3.Row) -> dict[str, Any]:
        return self._decision_from_mapping(row)

    def _decision_from_mapping(self, row: Any) -> dict[str, Any]:
        return {
            "decision_id": row["decision_id"],
            "event_id": row["event_id"],
            "hamlet_id": row["hamlet_id"],
            "warehouse_id": row["warehouse_id"],
            "decision": row["decision"],
            "recommendation": row["recommendation"],
            "stock_available": _bool(row["stock_available"]),
            "feasible": _bool(row["feasible"]),
            "nutrition_priority": _bool(row["nutrition_priority"]),
            "spoilage_risk": row["spoilage_risk"],
            "delivery_completed": _bool(row["delivery_completed"]),
            "details": _loads(row["details_json"]),
            "created_at": row["created_at"],
        }

    def _log_from_row(self, row: sqlite3.Row) -> dict[str, Any]:
        return self._log_from_mapping(row)

    def _log_from_mapping(self, row: Any) -> dict[str, Any]:
        return {
            "log_id": row["log_id"],
            "agent_name": row["agent_name"],
            "event_type": row["event_type"],
            "event_id": row["event_id"],
            "hamlet_id": row["hamlet_id"],
            "warehouse_id": row["warehouse_id"],
            "input_summary": row["input_summary"],
            "result": row["result"],
            "status": row["status"],
            "error_detail": row["error_detail"],
            "timestamp": row["timestamp"],
        }

    def _filtered_rows(
        self,
        sql: str,
        transform: Any,
        hamlet_id: str | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        parameters: list[Any] = []
        where = ""
        if hamlet_id:
            where = "WHERE hamlet_id = ?"
            parameters.append(hamlet_id)
        parameters.append(limit)
        with self.transaction() as connection:
            rows = connection.execute(sql.format(where=where), parameters).fetchall()
        return [transform(row) for row in rows]

    def _read(self, connection: sqlite3.Connection | None, read: Any) -> Any:
        if connection is not None:
            return read(connection)
        with self.transaction() as owned:
            return read(owned)
