from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List


@dataclass
class AuditEvent:
    trace_id: str
    actor_type: str
    actor_id: str
    event_type: str
    decision: str
    reason: str
    payload: Dict[str, Any]
    created_at: str


class MemoryAuditSink:
    def __init__(self) -> None:
        self.events: List[AuditEvent] = []

    def write(self, *, trace_id: str, actor_type: str, actor_id: str, event_type: str, decision: str, reason: str, payload: Dict[str, Any]) -> AuditEvent:
        event = AuditEvent(
            trace_id=trace_id,
            actor_type=actor_type,
            actor_id=actor_id,
            event_type=event_type,
            decision=decision,
            reason=reason,
            payload=payload,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self.events.append(event)
        return event

    def as_dicts(self) -> list[dict]:
        return [asdict(e) for e in self.events]
