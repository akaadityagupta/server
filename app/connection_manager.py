from fastapi import WebSocket


class ConnectionManager:
    """In-memory registry: device_id -> live WebSocket connection.
    Offline-delivery persistence is handled by outbox.py (file-based), not here."""

    def __init__(self):
        self.child_connection: WebSocket | None = None
        self.parent_connection: WebSocket | None = None
        self.device_token: str | None = None

    def is_child_connected(self) -> bool:
        return self.child_connection is not None

    def is_parent_connected(self) -> bool:
        return self.parent_connection is not None


manager = ConnectionManager()