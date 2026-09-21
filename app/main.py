import logging
import secrets
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from app.config import EXPECTED_PAIRING_CODE, PARENT_AUTH_KEY
from app.connection_manager import manager
from app.models import RelayMessage
from app import outbox

FORWARD_TO_PARENT_TYPES = {"USAGE_REPORT", "CALL_LOG_REPORT", "NOTIFICATION_REPORT", "STUDY_SESSION_STARTED", "STUDY_SESSION_STOPPED"}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("relay")

app = FastAPI()


@app.get("/health")
def health():
    return {"status": "ok"}


async def deliver_to_parent_or_queue(message: dict):
    if manager.parent_connection is not None:
        try:
            await manager.parent_connection.send_json(message)
            return
        except Exception:
            logger.warning("Send to parent failed, will queue instead")
            manager.parent_connection = None

    await outbox.enqueue(message)
    logger.info("Queued %s for parent (persisted to disk)", message.get("type"))


async def notify_parent_of_device_status(status: str):
    if manager.parent_connection is not None:
        try:
            await manager.parent_connection.send_json({
                "type": "DEVICE_STATUS",
                "payload": {"status": status},
            })
        except Exception:
            logger.warning("Failed to notify parent of device status")
            manager.parent_connection = None


@app.websocket("/ws/child")
async def child_socket(websocket: WebSocket):
    await websocket.accept()

    try:
        first_raw = await websocket.receive_json()
        first_message = RelayMessage(**first_raw)
    except WebSocketDisconnect:
        logger.info("Child disconnected before completing handshake")
        return
    except Exception:
        await websocket.close(code=4001, reason="Invalid first message")
        return

    authenticated = False

    if first_message.type == "PAIR_REQUEST":
        code = first_message.payload.get("pairing_code")
        if code == EXPECTED_PAIRING_CODE:
            manager.device_token = secrets.token_hex(16)
            await websocket.send_json({
                "type": "PAIR_CONFIRM",
                "payload": {"device_token": manager.device_token},
            })
            authenticated = True
            logger.info("Child paired successfully (new token issued)")
        else:
            await websocket.send_json({"type": "PAIR_REJECTED", "payload": {}})
            logger.warning("Child sent wrong pairing code: %s", code)

    elif first_message.type == "AUTH":
        token = first_message.payload.get("device_token")
        if manager.device_token is not None and token == manager.device_token:
            authenticated = True
            await websocket.send_json({"type": "AUTH_OK", "payload": {}})
            logger.info("Child re-authenticated with existing token")
        else:
            await websocket.send_json({"type": "AUTH_FAILED", "payload": {}})
            logger.warning("Child sent invalid/unknown token")

    if not authenticated:
        await websocket.close(code=4003, reason="Unauthorized")
        return

    manager.child_connection = websocket
    await notify_parent_of_device_status("online")

    try:
        while True:
            raw = await websocket.receive_json()
            message = RelayMessage(**raw)

            if message.type in FORWARD_TO_PARENT_TYPES:
                await deliver_to_parent_or_queue({
                    "type": message.type,
                    "payload": message.payload,
                })
            else:
                logger.info("Received %s from child (no handler yet)", message.type)

    except WebSocketDisconnect:
        manager.child_connection = None
        logger.info("Child device disconnected")
        await notify_parent_of_device_status("offline")


@app.websocket("/ws/parent")
async def parent_socket(websocket: WebSocket):
    await websocket.accept()

    try:
        first_raw = await websocket.receive_json()
        first_message = RelayMessage(**first_raw)
    except WebSocketDisconnect:
        logger.info("Parent disconnected before completing handshake")
        return
    except Exception:
        await websocket.close(code=4001, reason="Invalid first message")
        return

    await websocket.send_json({"type": "AUTH_OK", "payload": {}})
    manager.parent_connection = websocket
    logger.info("Parent app connected and authenticated")

    current_status = "online" if manager.is_child_connected() else "offline"
    await websocket.send_json({"type": "DEVICE_STATUS", "payload": {"status": current_status}})

    queued_messages = await outbox.drain_all()
    if queued_messages:
        logger.info("Flushing %d queued message(s) to parent", len(queued_messages))
        for queued_message in queued_messages:
            await websocket.send_json(queued_message)

    try:
        while True:
            raw = await websocket.receive_json()
            logger.info("Received from parent: %s", raw)
    except WebSocketDisconnect:
        manager.parent_connection = None
        logger.info("Parent app disconnected")