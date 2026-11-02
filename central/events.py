import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List


@dataclass
class SystemEvent:
    event_type: str
    description: str
    state: str
    details: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]):
        state = str(payload.get("state", "NORMAL")).upper()
        details = dict(payload)
        vision = payload.get("vision")
        safety_result = None
        access_result = None
        if isinstance(vision, dict):
            safety_result = vision.get("safety", vision.get("lab"))
            access_result = vision.get("access", vision.get("entry"))

        if payload.get("emergency_button_pressed") is True:
            event_type = "SAFETY"
            description = "Botão de emergência pressionado"
        elif payload.get("smoke_detected") is True:
            event_type = "SENSOR"
            description = "Fumaça detectada"
        elif payload.get("gas_detected") is True:
            event_type = "SENSOR"
            description = "Gás acima do limiar configurado"
        elif float(payload.get("gas_ppm", 0.0) or 0.0) >= 0.7:
            event_type = "SENSOR"
            description = "Gás em nível crítico"
        elif isinstance(safety_result, dict) and safety_result.get("risk") == "EMERGENCY":
            event_type = "VISION"
            description = "Fumaça ou incêndio detectado pela câmera"
        elif isinstance(access_result, dict) and access_result.get("status") == "ALERTA":
            event_type = "EPI"
            description = "EPI inadequado detectado na entrada"
        elif state in {"ALERT", "WARNING", "EMERGENCY"}:
            event_type = "SENSOR"
            description = "Leitura ambiental fora do normal"
        else:
            event_type = "SYSTEM"
            description = "Estado do sistema normal"

        return cls(
            event_type=event_type,
            description=description,
            state=state,
            details=details,
        )


class EventStore:
    """Persistência simples de eventos em SQLite para o sistema central."""

    def __init__(self, db_path: str = "ctrlab_events.db"):
        self.db_path = db_path
        self._ensure_schema()

    def _ensure_schema(self):
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    description TEXT NOT NULL,
                    state TEXT NOT NULL,
                    details TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def log_event(
        self,
        event_type: str,
        description: str,
        state: str,
        details: Dict[str, Any] | None = None,
    ) -> int:
        payload = details or {}
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")

        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.execute(
                """
                INSERT INTO events (created_at, event_type, description, state, details)
                VALUES (?, ?, ?, ?, ?)
                """,
                (now, event_type, description, str(state).upper(), json.dumps(payload, ensure_ascii=False)),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def get_recent_events(self, limit: int = 20) -> List[Dict[str, Any]]:
        with closing(sqlite3.connect(self.db_path)) as conn:
            rows = conn.execute(
                """
                SELECT id, created_at, event_type, description, state, details
                FROM events
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        result = []
        for row in rows:
            event_id, created_at, event_type, description, state, details_raw = row
            result.append(
                {
                    "id": event_id,
                    "created_at": created_at,
                    "event_type": event_type,
                    "description": description,
                    "state": state,
                    "details": json.loads(details_raw or "{}"),
                }
            )

        return result

    def save_payload(self, payload: Dict[str, Any]) -> SystemEvent:
        event = SystemEvent.from_payload(payload)
        self.log_event(
            event_type=event.event_type,
            description=event.description,
            state=event.state,
            details=event.details,
        )
        return event
