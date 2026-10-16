import os
import time
import datetime
import logging
from pathlib import Path

logger = logging.getLogger("relay.fcm")

try:
    import firebase_admin
    from firebase_admin import credentials, messaging
    _FIREBASE_AVAILABLE = True
except ImportError:
    _FIREBASE_AVAILABLE = False
    logger.warning("firebase-admin package not installed. FCM features disabled.")

# Path to the service account credentials JSON
_CRED_PATHS = [
    Path(__file__).parent.parent / "firebase-service-account.json",
    Path(__file__).parent / "firebase-service-account.json",
]


class FCMService:
    def __init__(self):
        self._initialized = False
        self._init_firebase()

    def _init_firebase(self):
        if not _FIREBASE_AVAILABLE:
            return

        # Check if already initialized by default app
        if firebase_admin._apps:
            self._initialized = True
            logger.info("Firebase Admin already initialized.")
            return

        cred_file = None
        for path in _CRED_PATHS:
            if path.exists():
                cred_file = path
                break

        env_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if env_path and Path(env_path).exists():
            cred_file = Path(env_path)

        if cred_file:
            try:
                cred = credentials.Certificate(str(cred_file))
                firebase_admin.initialize_app(cred)
                self._initialized = True
                logger.info("Firebase Admin initialized successfully using %s", cred_file.name)
            except Exception as e:
                logger.error("Failed to initialize Firebase Admin with %s: %s", cred_file, e)
        else:
            logger.warning(
                "FCM Service Account JSON not found at '%s'. "
                "FCM silent wake is running in standby mode until you place firebase-service-account.json in the server folder.",
                _CRED_PATHS[0]
            )

    @property
    def is_configured(self) -> bool:
        return self._initialized

    def send_silent_wake_push(self, fcm_token: str | None, reason: str = "PARENT_REQUEST") -> dict:
        """
        Sends an Android High-Priority Silent Data Message (no notification body).
        This wakes the child device's Google Play Services, spawns ChildFirebaseMessagingService,
        and reconnects the WebSocket relay.
        """
        if not self._initialized:
            # Re-attempt init in case file was placed after server started
            self._init_firebase()

        if not self._initialized:
            logger.warning("Cannot send FCM wake: firebase-service-account.json not found.")
            return {
                "success": False,
                "error": "firebase_credentials_missing",
                "message": "Please place firebase-service-account.json in the server folder."
            }

        if not fcm_token:
            logger.warning("Cannot send FCM wake: No child FCM token registered yet.")
            return {
                "success": False,
                "error": "no_child_token",
                "message": "Child app has not registered its FCM token with the server yet."
            }

        try:
            message = messaging.Message(
                token=fcm_token,
                data={
                    "action": "WAKE_UP",
                    "reason": reason,
                    "timestamp": str(int(time.time())),
                },
                android=messaging.AndroidConfig(
                    priority="high",
                    ttl=datetime.timedelta(seconds=120)
                )
            )
            response = messaging.send(message)
            logger.info("Successfully dispatched High-Priority FCM Wake Push (message_id=%s)", response)
            return {
                "success": True,
                "message_id": response
            }
        except Exception as e:
            logger.error("Failed to send FCM wake message: %s", e)
            return {
                "success": False,
                "error": "fcm_send_failed",
                "message": str(e)
            }


fcm_service = FCMService()
