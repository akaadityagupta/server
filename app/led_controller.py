import asyncio
import logging
from enum import Enum, auto

from app.config import (
    LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA,
    LED_BRIGHTNESS, LED_INVERT, LED_CHANNEL,
)

logger = logging.getLogger("led")

try:
    from rpi_ws281x import PixelStrip, Color
    _HARDWARE_AVAILABLE = True
except Exception:
    _HARDWARE_AVAILABLE = False


class LedState(Enum):
    STARTING = auto()          # blue breathing
    WAITING_CHILD = auto()     # yellow blink
    CHILD_CONNECTED = auto()   # green blink
    PARENT_CONNECT_PULSE = auto()    # pink blink x2, then falls back
    PARENT_DISCONNECT_PULSE = auto()  # pink blink x5, then falls back
    SHUTDOWN = auto()          # solid/fast red
    OFF = auto()

# (R, G, B)
COLOR_BLUE = (0, 0, 255)
COLOR_YELLOW = (255, 100, 0)
COLOR_GREEN = (0, 255, 0)
COLOR_PINK = (255, 20, 100)
COLOR_RED = (255, 0, 0)

TICK_SECONDS = 0.05  # 20 fps render loop


class LedController:
    def __init__(self):
        self._state = LedState.OFF
        self._child_connected = False  # remembered so pink pulses know what to fall back to
        self._pulse_generation = 0  # bumped whenever a new pulse starts, to cancel stale ones
        self._task: asyncio.Task | None = None
        self._strip = None

        if _HARDWARE_AVAILABLE:
            try:
                self._strip = PixelStrip(
                    LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA,
                    LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL,
                )
                self._strip.begin()
            except Exception:
                logger.warning("LED hardware init failed, running in no-op mode")
                self._strip = None
        else:
            logger.info("rpi_ws281x not available, LED running in no-op mode")

    # ---------- public API ----------

    def start(self):
        """Call once at app startup to launch the render loop."""
        if self._task is None:
            self._task = asyncio.create_task(self._render_loop())

    async def stop(self):
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        self._set_pixel((0, 0, 0))

    def set_starting(self):
        self._state = LedState.STARTING

    def set_waiting_child(self):
        self._child_connected = False
        self._state = LedState.WAITING_CHILD

    def set_child_connected(self):
        self._child_connected = True
        self._state = LedState.CHILD_CONNECTED

    def pulse_parent_connected(self):
        """Pink blinks 2x, then falls back to current child status."""
        self._trigger_pulse(LedState.PARENT_CONNECT_PULSE)

    def pulse_parent_disconnected(self):
        """Pink blinks 5x, then falls back to current child status."""
        self._trigger_pulse(LedState.PARENT_DISCONNECT_PULSE)

    def set_shutdown(self):
        self._state = LedState.SHUTDOWN

    # ---------- internals ----------

    def _trigger_pulse(self, pulse_state: LedState):
        self._pulse_generation += 1
        self._state = pulse_state

    def _child_status_state(self) -> LedState:
        return LedState.CHILD_CONNECTED if self._child_connected else LedState.WAITING_CHILD

    def _set_pixel(self, rgb: tuple[int, int, int]):
        if self._strip is not None:
            r, g, b = rgb
            # This strip's hardware wiring is GRB, not RGB — swap so the
            # colors we define (COLOR_BLUE, COLOR_YELLOW, etc.) render correctly.
            pixel_color = Color(g, r, b)
            self._strip.setPixelColor(0, pixel_color)
            for i in range(1, LED_COUNT):
                self._strip.setPixelColor(i, pixel_color)
            self._strip.show()
        # in no-op mode we simply don't render anything (avoids log spam every tick)

    async def _render_loop(self):
        t = 0.0
        while True:
            state = self._state

            if state == LedState.STARTING:
                brightness = _breathe(t, period=2.5)
                self._set_pixel(_scale(COLOR_BLUE, brightness))

            elif state == LedState.WAITING_CHILD:
                self._set_pixel(COLOR_YELLOW if _blink(t, period=1.0) else (0, 0, 0))

            elif state == LedState.CHILD_CONNECTED:
                 self._set_pixel(COLOR_GREEN if _blink_asymmetric(t, on_time=0.1, off_time=1.0) else (0, 0, 0))

            elif state in (LedState.PARENT_CONNECT_PULSE, LedState.PARENT_DISCONNECT_PULSE):
                count = 2 if state == LedState.PARENT_CONNECT_PULSE else 5
                await self._run_pulse(COLOR_PINK, count, self._pulse_generation)
                if self._state in (LedState.PARENT_CONNECT_PULSE, LedState.PARENT_DISCONNECT_PULSE):
                    self._state = self._child_status_state()
                continue

            elif state == LedState.SHUTDOWN:
                self._set_pixel(COLOR_RED if _blink(t, period=0.3) else (0, 0, 0))

            elif state == LedState.OFF:
                self._set_pixel((0, 0, 0))

            await asyncio.sleep(TICK_SECONDS)
            t += TICK_SECONDS

    async def _run_pulse(self, color, count: int, generation: int):
        """Blink `color` on/off `count` times, then return.
        Bails early if a newer pulse/state change supersedes it."""
        on_time = 0.15
        off_time = 0.15
        for _ in range(count):
            if self._pulse_generation != generation:
                return
            self._set_pixel(color)
            await asyncio.sleep(on_time)
            if self._pulse_generation != generation:
                return
            self._set_pixel((0, 0, 0))
            await asyncio.sleep(off_time)


def _blink(t: float, period: float) -> bool:
    return (t % period) < (period / 2)

def _blink_asymmetric(t: float, on_time: float, off_time: float) -> bool:
    """Like _blink, but on/off durations don't have to be equal.
    e.g. on_time=0.2, off_time=1.0 -> LED on for 0.2s, off for 1.0s, repeat."""
    period = on_time + off_time
    return (t % period) < on_time


def _breathe(t: float, period: float) -> float:
    import math
    phase = (t % period) / period
    return (math.sin(phase * 2 * math.pi - math.pi / 2) + 1) / 2


def _scale(rgb: tuple[int, int, int], factor: float) -> tuple[int, int, int]:
    return tuple(int(c * factor) for c in rgb)


led = LedController()