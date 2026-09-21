from pydantic import BaseModel, Field
from datetime import datetime, timezone
from typing import Optional, Any


class RelayMessage(BaseModel):
    type: str
    from_: Optional[str] = Field(default=None, alias="from")
    to: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    payload: dict[str, Any] = {}

    class Config:
        populate_by_name = True