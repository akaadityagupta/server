EXPECTED_PAIRING_CODE = "CHILD-DEVICE-0001"
PARENT_AUTH_KEY = "PARENT-APP-SECRET-KEY-0001" 

# --- WS2811 status LED ---
LED_COUNT = 1            # number of pixels on the strip (1 if it's a single indicator LED)
LED_PIN = 18              # GPIO18 (PWM0) — standard pin for ws281x data line
LED_FREQ_HZ = 800000      # WS2811 signal frequency
LED_DMA = 10              # DMA channel
LED_BRIGHTNESS = 120      # 0-255
LED_INVERT = False        # set True if using an NPN transistor level-shifter
LED_CHANNEL = 0           # PWM channel (0 for GPIO18)

# --- Shutdown push button ---
SHUTDOWN_BUTTON_PIN = 26  # GPIO17, button wired to GND with internal pull-up
SHUTDOWN_HOLD_SECONDS = 3  # debounce; bump up if you want a "press and hold" requiremen

OLED_BUTTON_PIN = 16