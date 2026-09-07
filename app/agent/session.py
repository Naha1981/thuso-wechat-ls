from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any

@dataclass
class SessionState:
    user_id: str
    intent: str = 'help'
    pending_action: str | None = None
    pending_payload: dict[str, Any] = field(default_factory=dict)
    expires_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc)+timedelta(minutes=20))

    def active(self) -> bool:
        return datetime.now(timezone.utc) < self.expires_at
