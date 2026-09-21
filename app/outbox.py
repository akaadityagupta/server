import json
import asyncio
from pathlib import Path

OUTBOX_FILE = Path(__file__).parent / "outbox.jsonl"
MAX_LINES = 2000  # same cap as before — keeps the file from growing unbounded

_lock = asyncio.Lock()  # guards concurrent read/write since child + parent handlers run concurrently


async def enqueue(message: dict):
    async with _lock:
        with OUTBOX_FILE.open("a") as f:
            f.write(json.dumps(message) + "\n")
        _trim_if_needed()


def _trim_if_needed():
    if not OUTBOX_FILE.exists():
        return
    lines = OUTBOX_FILE.read_text().splitlines()
    if len(lines) > MAX_LINES:
        trimmed = lines[-MAX_LINES:]  # drop oldest first, same policy as before
        OUTBOX_FILE.write_text("\n".join(trimmed) + "\n")


async def drain_all() -> list[dict]:
    async with _lock:
        if not OUTBOX_FILE.exists():
            return []
        lines = OUTBOX_FILE.read_text().splitlines()
        OUTBOX_FILE.write_text("")  # clear after reading
        return [json.loads(line) for line in lines if line.strip()]