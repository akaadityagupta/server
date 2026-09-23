import asyncio
import logging
import socket
import subprocess
import time
from app.connection_manager import manager
import psutil
from gpiozero import Button
from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306
from PIL import Image, ImageDraw, ImageFont
from app.config import OLED_BUTTON_PIN


logger = logging.getLogger("oled")


# =========================
# Configuration
# =========================

OLED_WIDTH = 128
OLED_HEIGHT = 64

OLED_I2C_ADDRESS = 0x3C

# BCM GPIO number for OLED push button


SCREEN_TIMEOUT = 10


class OLEDManager:
    def __init__(self):
        self.device = None
        self.button = None

        self.screen = 0
        self.last_activity = time.monotonic()

        self._task = None
        self._loop = None

        self.font = ImageFont.load_default()

    # =========================
    # START
    # =========================

    def start(self, loop):
        self._loop = loop

        try:
            serial = i2c(
                port=1,
                address=OLED_I2C_ADDRESS
            )

            self.device = ssd1306(
                serial,
                width=OLED_WIDTH,
                height=OLED_HEIGHT
            )

            self.button = Button(
                OLED_BUTTON_PIN,
                pull_up=True,
                bounce_time=0.05
            )

            self.button.when_pressed = self._button_pressed

            self.last_activity = time.monotonic()

            self._show_server_screen()

            self._task = asyncio.create_task(
                self._screen_loop()
            )

            logger.info("OLED initialized successfully")

        except Exception:
            logger.exception("OLED initialization failed")

    # =========================
    # BUTTON
    # =========================

    def _button_pressed(self):
        if self._loop is None:
            return

        asyncio.run_coroutine_threadsafe(
            self._handle_button(),
            self._loop
        )

    async def _handle_button(self):
        self.last_activity = time.monotonic()

        # OLED was OFF
        if self.screen == -1:
            self.device.show()  
            self.screen = 0

        else:
            self.screen += 1

            if self.screen > 2:
                self.screen = 0

        self._show_current_screen()
    # =========================
    # SCREEN LOOP
    # =========================

    async def _screen_loop(self):

        while True:

            try:
                # Turn OLED OFF after inactivity
                if (
                    self.device
                    and self.screen != -1
                    and time.monotonic() - self.last_activity
                    >= SCREEN_TIMEOUT
                ):
                    self.device.hide()
                    self.screen = -1

                # Refresh active screen
                elif self.device and self.screen != -1:

                    self._show_current_screen()

            except Exception:
                logger.exception("OLED update failed")

            await asyncio.sleep(1)

    # =========================
    # DRAWING
    # =========================

    def _new_image(self):
        image = Image.new(
            "1",
            (OLED_WIDTH, OLED_HEIGHT)
        )

        draw = ImageDraw.Draw(image)

        return image, draw

    def _show_current_screen(self):

        if not self.device:
            return

        if self.screen == 0:
            self._show_server_screen()

        elif self.screen == 1:
            self._show_system_screen()

        elif self.screen == 2:
            self._show_devices_screen()

    # =========================
    # SCREEN 0
    # =========================

    def _show_server_screen(self):

        image, draw = self._new_image()

        # draw.text(
        #     (22, 2),
        #     "MAX TRACKER",
        #     font=self.font,
        #     fill=255
        # )

        # draw.line(
        #     (0, 14, 127, 14),
        #     fill=255
        # )

        draw.text(
            (4, 18),
            "SERVER : ONLINE",
            font=self.font,
            fill=255
        )

        ip = self._get_ip()

        draw.text(
            (4, 35),
            f"IP: {ip}",
            font=self.font,
            fill=255
        )

        self.device.display(image)

    # =========================
    # SCREEN 1
    # =========================

    def _show_system_screen(self):

        image, draw = self._new_image()

        cpu = psutil.cpu_percent(interval=None)

        memory = psutil.virtual_memory()
        ram = memory.percent

        temperature = self._get_temperature()

        wifi_signal = self._get_wifi_signal()

        draw.text(
            (38, 2),
            "SYSTEM",
            font=self.font,
            fill=255
        )

        draw.line(
            (0, 14, 127, 14),
            fill=255
        )

        draw.text(
            (4, 19),
            f"CPU : {cpu:.0f}%",
            font=self.font,
            fill=255
        )

        draw.text(
            (4, 32),
            f"RAM : {ram:.0f}%",
            font=self.font,
            fill=255
        )

        draw.text(
            (4, 45),
            f"WIFI: {wifi_signal}",
            font=self.font,
            fill=255
        )

        draw.text(
            (75, 45),
            f"{temperature}C",
            font=self.font,
            fill=255
        )

        self.device.display(image)

    # =========================
    # SCREEN 2
    # =========================

    def _show_devices_screen(self):

        image, draw = self._new_image()

        draw.text(
            (32, 2),
            "DEVICES",
            font=self.font,
            fill=255
        )

        draw.line(
            (0, 14, 127, 14),
            fill=255
        )

        parent_status = self._get_parent_status()
        child_status = self._get_child_status()

        draw.text(
            (4, 25),
            f"Parent: {parent_status}",
            font=self.font,
            fill=255
        )

        draw.text(
            (4, 43),
            f"Child : {child_status}",
            font=self.font,
            fill=255
        )

        self.device.display(image)

    # =========================
    # NETWORK
    # =========================

    def _get_ip(self):

        try:
            s = socket.socket(
                socket.AF_INET,
                socket.SOCK_DGRAM
            )

            s.connect(("8.8.8.8", 80))

            ip = s.getsockname()[0]

            s.close()

            return ip

        except Exception:
            return "NO NETWORK"

    def _get_wifi_signal(self):

        try:

            result = subprocess.run(
                ["iwconfig", "wlan0"],
                capture_output=True,
                text=True
            )

            output = result.stdout

            for line in output.splitlines():

                if "Signal level=" in line:

                    value = line.split(
                        "Signal level="
                    )[1].split()[0]

                    return value

            return "N/A"

        except Exception:

            return "N/A"

    # =========================
    # TEMPERATURE
    # =========================

    def _get_temperature(self):

        try:

            with open(
                "/sys/class/thermal/thermal_zone0/temp",
                "r"
            ) as f:

                temp = int(f.read().strip()) / 1000

                return f"{temp:.0f}"

        except Exception:

            return "N/A"

    # =========================
    # DEVICE STATUS
    # =========================
    #
    # Replace these two methods
    # with your actual relay state.
    #

    def _get_parent_status(self):

        return "ONLINE" if manager.is_parent_connected() else "OFFLINE"

    def _get_child_status(self):

        return "ONLINE" if manager.is_child_connected() else "OFFLINE"

    # =========================
    # STOP
    # =========================

    def stop(self):

        try:

            if self._task:
                self._task.cancel()

            if self.button:
                self.button.close()

            if self.device:
                self.device.hide()

            logger.info("OLED stopped")

        except Exception:
            logger.exception("Error stopping OLED")


oled_manager = OLEDManager()