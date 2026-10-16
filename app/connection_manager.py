import json
import logging
from pathlib import Path
from fastapi import WebSocket

logger = logging.getLogger("relay")

# Stored next to the other data files (outbox.jsonl lives in the same dir)
_TOKEN_FILE = Path(__file__).parent / "device_token.json"


class ConnectionManager:
    """In-memory registry: device_id -> live WebSocket connection.
    Offline-delivery persistence is handled by outbox.py (file-based), not here.

    device_token is now persisted to disk so it survives server restarts —
    the child app won't need to re-pair every time the Pi reboots."""

    def __init__(self):
        self.child_connection: WebSocket | None = None
        self.parent_connection: WebSocket | None = None
        self._device_token: str | None = self._load_token()
        self._child_fcm_token: str | None = self._load_fcm_token()

    # --- device_token as a property: auto-persists on write ---

    @property
    def device_token(self) -> str | None:
        return self._device_token

    @device_token.setter
    def device_token(self, value: str | None):
        self._device_token = value
        self._save_token(value)

    # --- child_fcm_token: auto-persists so FCM wake survives server reboots ---

    @property
    def child_fcm_token(self) -> str | None:
        return self._child_fcm_token

    @child_fcm_token.setter
    def child_fcm_token(self, value: str | None):
        self._child_fcm_token = value
        self._save_fcm_token(value)

    # --- persistence helpers ---

    @staticmethod
    def _load_token() -> str | None:
        """Load the device token from disk at startup."""
        try:
            if _TOKEN_FILE.exists():
                data = json.loads(_TOKEN_FILE.read_text())
                token = data.get("device_token")
                if token:
                    logger.info("Loaded persisted device token from %s", _TOKEN_FILE.name)
                    return token
        except Exception as e:
            logger.warning("Could not load device token: %s", e)
        return None

    @staticmethod
    def _save_token(token: str | None):
        """Write the device token to disk so it survives restarts."""
        try:
            _TOKEN_FILE.write_text(json.dumps({"device_token": token}))
            logger.info("Device token persisted to %s", _TOKEN_FILE.name)
        except Exception as e:
            logger.warning("Could not save device token: %s", e)

    @staticmethod
    def _load_fcm_token() -> str | None:
        fcm_file = Path(__file__).parent / "child_fcm_token.json"
        try:
            if fcm_file.exists():
                data = json.loads(fcm_file.read_text())
                token = data.get("fcm_token")
                if token:
                    logger.info("Loaded persisted Child FCM token from %s", fcm_file.name)
                    return token
        except Exception as e:
            logger.warning("Could not load child FCM token: %s", e)
        return None

    @staticmethod
    def _save_fcm_token(token: str | None):
        fcm_file = Path(__file__).parent / "child_fcm_token.json"
        try:
            fcm_file.write_text(json.dumps({"fcm_token": token}))
            logger.info("Child FCM token persisted to %s", fcm_file.name)
        except Exception as e:
            logger.warning("Could not save child FCM token: %s", e)

    # --- connection helpers ---

    def is_child_connected(self) -> bool:
        return self.child_connection is not None

    def is_parent_connected(self) -> bool:
        return self.parent_connection is not None


manager = ConnectionManager()