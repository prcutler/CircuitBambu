import os
import time

import adafruit_connection_manager
import board
import busio
import displayio
import terminalio
import wifi
import dotclockframebuffer
from framebufferio import FramebufferDisplay
from adafruit_display_text import label
from digitalio import DigitalInOut

import bambulabs

displayio.release_displays()

tft_pins = dict(board.TFT_PINS)

tft_timings = {
    "frequency": 16000000,
    "width": 480,
    "height": 480,
    "hsync_pulse_width": 20,
    "hsync_front_porch": 40,
    "hsync_back_porch": 40,
    "vsync_pulse_width": 10,
    "vsync_front_porch": 40,
    "vsync_back_porch": 40,
    "hsync_idle_low": False,
    "vsync_idle_low": False,
    "de_idle_high": False,
    "pclk_active_high": False,
    "pclk_idle_high": False,
}

init_sequence_tl034wvs05 = bytes((
    b'\xff\x05w\x01\x00\x00\x13'
    b'\xef\x01\x08'
    b'\xff\x05w\x01\x00\x00\x10'
    b'\xc0\x02;\x00'
    b'\xc1\x02\x12\n'
    b'\xc2\x02\x07\x03'
    b'\xc3\x01\x02'
    b'\xcc\x01\x10'
    b'\xcd\x01\x08'
    b'\xb0\x10\x0f\x11\x17\x15\x15\t\x0c\x08\x08&\x04Y\x16f-\x1f'
    b'\xb1\x10\x0f\x11\x17\x15\x15\t\x0c\x08\x08&\x04Y\x16f-\x1f'
    b'\xff\x05w\x01\x00\x00\x11'
    b'\xb0\x01m'
    b'\xb1\x01:'
    b'\xb2\x01\x01'
    b'\xb3\x01\x80'
    b'\xb5\x01I'
    b'\xb7\x01\x85'
    b'\xb8\x01 '
    b'\xc1\x01x'
    b'\xc2\x01x'
    b'\xd0\x01\x88'
    b'\xe0\x03\x00\x00\x02'
    b'\xe1\x0b\x07\x00\t\x00\x06\x00\x08\x00\x0033'
    b'\xe2\r\x11\x1133\xf6\x00\xf6\x00\xf6\x00\xf6\x00\x00'
    b'\xe3\x04\x00\x00\x11\x11'
    b'\xe4\x02DD'
    b'\xe5\x10\x0f\xf3=\xff\x11\xf5=\xff\x0b\xef=\xff\r\xf1=\xff'
    b'\xe6\x04\x00\x00\x11\x11'
    b'\xe7\x02DD'
    b'\xe8\x10\x0e\xf2=\xff\x10\xf4=\xff\n\xee=\xff\x0c\xf0=\xff'
    b'\xe9\x026\x00'
    b'\xeb\x07\x00\x01\xe4\xe4D\xaa\x10'
    b'\xec\x02<\x00'
    b'\xed\x10\xffEg\xfa\x01+\xcf\xff\xff\xfc\xb2\x10\xafvT\xff'
    b'\xef\x06\x10\r\x04\x08?\x1f'
    b'\xff\x05w\x01\x00\x00\x00'
    b'5\x01\x00'
    b':\x01f'
    b'\x11\x80x'
    b')\x802'
))

board.I2C().deinit()
i2c = busio.I2C(board.SCL, board.SDA)
tft_io_expander = dict(board.TFT_IO_EXPANDER)
dotclockframebuffer.ioexpander_send_init_sequence(i2c, init_sequence_tl034wvs05, **tft_io_expander)
i2c.deinit()

fb = dotclockframebuffer.DotClockFramebuffer(**tft_pins, **tft_timings)
display = FramebufferDisplay(fb, auto_refresh=True)

COLOR_WHITE = 0xFFFFFF
COLOR_GREEN = 0x00FF00
COLOR_YELLOW = 0xFFFF00
COLOR_CYAN = 0x00FFFF
COLOR_ORANGE = 0xFF8800
COLOR_GRAY = 0x888888
COLOR_BG = 0x000000

main_group = displayio.Group()

bg_bitmap = displayio.Bitmap(480, 480, 1)
bg_palette = displayio.Palette(1)
bg_palette[0] = COLOR_BG
bg_sprite = displayio.TileGrid(bg_bitmap, pixel_shader=bg_palette)
main_group.append(bg_sprite)

title_label = label.Label(
    terminalio.FONT, text="Bambu Printer", color=COLOR_GREEN,
    anchor_point=(0.5, 0), anchored_position=(240, 30), scale=3
)
main_group.append(title_label)

LABEL_DEFS = [
    ("state", "State: Connecting...", COLOR_WHITE, 100),
    ("progress", "Progress: --", COLOR_CYAN, 150),
    ("remaining", "Remaining: --", COLOR_YELLOW, 200),
    ("nozzle", "Nozzle: --", COLOR_ORANGE, 250),
    ("bed", "Bed: --", COLOR_ORANGE, 300),
    ("layer", "Layer: --", COLOR_GRAY, 350),
    ("file", "", COLOR_GRAY, 400),
]

labels = {}
for name, default_text, color, y_pos in LABEL_DEFS:
    lbl = label.Label(
        terminalio.FONT, text=default_text, color=color,
        anchor_point=(0, 0), anchored_position=(40, y_pos), scale=2
    )
    main_group.append(lbl)
    labels[name] = lbl

display.root_group = main_group

BAR_X = 40
BAR_Y = 440
BAR_W = 400
BAR_H = 20

bar_outline = displayio.Bitmap(BAR_W, BAR_H, 1)
bar_outline_palette = displayio.Palette(1)
bar_outline_palette[0] = COLOR_GRAY
bar_outline_tg = displayio.TileGrid(bar_outline, pixel_shader=bar_outline_palette, x=BAR_X, y=BAR_Y)
main_group.append(bar_outline_tg)

bar_fill = displayio.Bitmap(1, BAR_H - 4, 1)
bar_fill_palette = displayio.Palette(1)
bar_fill_palette[0] = COLOR_GREEN
bar_fill_tg = displayio.TileGrid(bar_fill, pixel_shader=bar_fill_palette, x=BAR_X + 2, y=BAR_Y + 2)
main_group.append(bar_fill_tg)


def update_progress_bar(percent):
    fill_w = max(1, int((BAR_W - 4) * percent / 100))
    bar_fill_tg.bitmap = displayio.Bitmap(fill_w, BAR_H - 4, 1)
    bar_fill_tg.bitmap.fill(0)


STATE_MAP = {
    "IDLE": "Idle",
    "RUNNING": "Printing",
    "PAUSE": "Paused",
    "FINISH": "Finished",
    "PREPARE": "Preparing",
    "FAILED": "Failed",
    "SLICING": "Slicing",
}

print("Connecting to AP...")
wifi.radio.connect(
    os.getenv("CIRCUITPY_WIFI_SSID"), os.getenv("CIRCUITPY_WIFI_PASSWORD")
)
print(f"Connected to {os.getenv('CIRCUITPY_WIFI_SSID')}")
print(f"My IP address: {wifi.radio.ipv4_address}")

serial_number = os.getenv("BAMBU_SERIAL")
printer = bambulabs.BambuPrinter(bambulabs.mqtt_client, serial_number)


def on_connect(client, userdata, flags, rc):
    print("Connected to Bambu printer MQTT broker")
    labels["state"].text = "State: Connected"
    request_pushall()


def on_disconnect(client, userdata, rc):
    print("Disconnected from MQTT broker")
    labels["state"].text = "State: Disconnected"


def request_pushall():
    status = printer.pushall()
    if status:
        update_display(status)


def update_display(status):
    raw_state = status.gcode_state
    if raw_state:
        friendly = STATE_MAP.get(raw_state, raw_state)
        labels["state"].text = f"State: {friendly}"
        print(f"  State: {friendly}")

    pct = status.print_percentage
    if pct is not None:
        labels["progress"].text = f"Progress: {pct}%"
        update_progress_bar(pct)
        print(f"  Progress: {pct}%")

    mins = status.remaining_time
    if mins is not None:
        hours = mins // 60
        remainder = mins % 60
        if hours > 0:
            labels["remaining"].text = f"Remaining: {hours}h {remainder}m"
        else:
            labels["remaining"].text = f"Remaining: {remainder}m"
        print(f"  Remaining: {mins} min")

    nozzle_temp = status.nozzle_temperature
    if nozzle_temp is not None:
        target = status.nozzle_temperature_target
        if target:
            labels["nozzle"].text = f"Nozzle: {nozzle_temp}/{target}C"
        else:
            labels["nozzle"].text = f"Nozzle: {nozzle_temp}C"
        print(f"  Nozzle: {nozzle_temp}C")

    bed_temp = status.bed_temperature
    if bed_temp is not None:
        target = status.bed_temperature_target
        if target:
            labels["bed"].text = f"Bed: {bed_temp}/{target}C"
        else:
            labels["bed"].text = f"Bed: {bed_temp}C"
        print(f"  Bed: {bed_temp}C")

    current_layer = status.current_layer
    if current_layer is not None:
        total = status.total_layers
        labels["layer"].text = f"Layer: {current_layer}/{total}"
        print(f"  Layer: {current_layer}/{total}")

    filename = status.gcode_file
    if filename:
        if len(filename) > 30:
            filename = filename[:27] + "..."
        labels["file"].text = filename


bambulabs.mqtt_client.on_connect = on_connect
bambulabs.mqtt_client.on_disconnect = on_disconnect

print(f"Connecting to Bambu printer...")
printer.connect()

last_status_request = time.monotonic()
STATUS_INTERVAL = 30

while True:
    try:
        printer.loop()
    except Exception as e:
        print(f"MQTT loop error: {e}")
        labels["state"].text = "State: Reconnecting..."
        try:
            bambulabs.mqtt_client.reconnect()
        except Exception as re:
            print(f"Reconnect failed: {re}")
            labels["state"].text = "State: Connection lost"
            time.sleep(5)

    now = time.monotonic()
    if now - last_status_request >= STATUS_INTERVAL:
        try:
            request_pushall()
        except Exception as e:
            print(f"Status request error: {e}")
        last_status_request = now

    time.sleep(0.1)
