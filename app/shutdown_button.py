
import asyncio
import logging
import subprocess

from app.config import SHUTDOWN_BUTTON_PIN, SHUTDOWN_HOLD_SECONDS
from app.led_controller import led

logger = logging.getLogger("shutdown")

try:
    from gpiozero import Button
    _HARDWARE_AVAILABLE = True
except Exception:
    _HARDWARE_AVAILABLE = False

SHUTDOWN_INDICATION_SECONDS = 1.5  # how long the red LED shows before the Pi actually powers off


class ShutdownButton:
    def __init__(self):
        self._button = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._shutting_down = False

    def start(self, loop: asyncio.AbstractEventLoop):
        """Call once at app startup, from inside the running event loop."""
        self._loop = loop

        if not _HARDWARE_AVAILABLE:
            logger.info("gpiozero not available, shutdown button running in no-op mode")
            return

        try:
            self._button = Button(
                SHUTDOWN_BUTTON_PIN,
                pull_up=True,
                bounce_time=SHUTDOWN_HOLD_SECONDS,
            )
            self._button.when_pressed = self._on_press
        except Exception:
            logger.warning("Shutdown button hardware init failed, running in no-op mode", exc_info=True)
            self._button = None

    def _on_press(self):
        # runs on gpiozero's own thread — hop over to the event loop
        if self._shutting_down or self._loop is None:
            return
        self._shutting_down = True
        asyncio.run_coroutine_threadsafe(self._shutdown_sequence(), self._loop)

    async def _shutdown_sequence(self):
        logger.warning("Shutdown button pressed — powering off")
        led.set_shutdown()
        await asyncio.sleep(SHUTDOWN_INDICATION_SECONDS)
        try:
            subprocess.run(["sudo", "shutdown", "-h", "now"], check=True)
        except Exception:
            logger.error("System shutdown command failed", exc_info=True)


shutdown_button = ShutdownButton()