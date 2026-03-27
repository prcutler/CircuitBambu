import json
import os
import time

import adafruit_connection_manager
import adafruit_minimqtt.adafruit_minimqtt as MQTT
import board
import busio
import displayio
import terminalio
import wifi
import dotclockframebuffer
from framebufferio import FramebufferDisplay
from adafruit_display_text import label
from digitalio import DigitalInOut

# Set up Qualia display

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
#tft_io_expander['i2c_address'] = 0x38 # uncomment for rev B
dotclockframebuffer.ioexpander_send_init_sequence(i2c, init_sequence_tl034wvs05, **tft_io_expander)
i2c.deinit()

fb = dotclockframebuffer.DotClockFramebuffer(**tft_pins, **tft_timings)
display = FramebufferDisplay(fb, auto_refresh=True)

# Colors
COLOR_WHITE = 0xFFFFFF
COLOR_GREEN = 0x00FF00
COLOR_YELLOW = 0xFFFF00
COLOR_CYAN = 0x00FFFF
COLOR_ORANGE = 0xFF8800
COLOR_GRAY = 0x888888
COLOR_BG = 0x000000

# Build display layout
main_group = displayio.Group()

# Background
bg_bitmap = displayio.Bitmap(480, 480, 1)
bg_palette = displayio.Palette(1)
bg_palette[0] = COLOR_BG
bg_sprite = displayio.TileGrid(bg_bitmap, pixel_shader=bg_palette)
main_group.append(bg_sprite)

# Title
title_label = label.Label(
    terminalio.FONT, text="Bambu Printer", color=COLOR_GREEN,
    anchor_point=(0.5, 0), anchored_position=(240, 30), scale=3
)
main_group.append(title_label)

# Status label definitions: (name, default_text, color, y_position)
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

# Progress bar
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
    """Update the progress bar width based on percentage."""
    fill_w = max(1, int((BAR_W - 4) * percent / 100))
    bar_fill_tg.bitmap = displayio.Bitmap(fill_w, BAR_H - 4, 1)
    bar_fill_tg.bitmap.fill(0)


# Friendly state names
STATE_MAP = {
    "IDLE": "Idle",
    "RUNNING": "Printing",
    "PAUSE": "Paused",
    "FINISH": "Finished",
    "PREPARE": "Preparing",
    "FAILED": "Failed",
    "SLICING": "Slicing",
}

# Set up networking
print("Connecting to AP...")
wifi.radio.connect(
    os.getenv("CIRCUITPY_WIFI_SSID"), os.getenv("CIRCUITPY_WIFI_PASSWORD")
)
print(f"Connected to {os.getenv('CIRCUITPY_WIFI_SSID')}")
print(f"My IP address: {wifi.radio.ipv4_address}")

pool = adafruit_connection_manager.get_radio_socketpool(wifi.radio)
ssl_context = adafruit_connection_manager.get_radio_ssl_context(wifi.radio)

# Bambu MQTT settings - Local Mode
bambu_ip = os.getenv("BAMBU_IP")
device_id = os.getenv("DEVICE_ID")
lan_access_code = os.getenv("LAN_ACCESS_CODE")

# BAMBU MQTT settings - Bambu Cloud
bambu_broker = os.getenv("BAMBU_BROKER")
access_token = os.getenv("BAMBU_ACCESS_TOKEN")
user_id = os.getenv("USER_ID")

report_topic = f"device/{device_id}/report"
request_topic = f"device/{device_id}/request"

sequence_id = 0


def update_display(print_data):
    if "gcode_state" in print_data:
        raw_state = print_data["gcode_state"]
        friendly = STATE_MAP.get(raw_state, raw_state)
        labels["state"].text = f"State: {friendly}"
        print(f"  State: {friendly}")

    if "mc_percent" in print_data:
        pct = print_data["mc_percent"]
        labels["progress"].text = f"Progress: {pct}%"
        update_progress_bar(pct)
        print(f"  Progress: {pct}%")

    if "mc_remaining_time" in print_data:
        mins = print_data["mc_remaining_time"]
        hours = mins // 60
        remainder = mins % 60
        if hours > 0:
            labels["remaining"].text = f"Remaining: {hours}h {remainder}m"
        else:
            labels["remaining"].text = f"Remaining: {remainder}m"
        print(f"  Remaining: {mins} min")

    if "nozzle_temper" in print_data:
        temp = print_data["nozzle_temper"]
        target = print_data.get("nozzle_target_temper", "")
        if target:
            labels["nozzle"].text = f"Nozzle: {temp}/{target}C"
        else:
            labels["nozzle"].text = f"Nozzle: {temp}C"
        print(f"  Nozzle: {temp}C")

    if "bed_temper" in print_data:
        temp = print_data["bed_temper"]
        target = print_data.get("bed_target_temper", "")
        if target:
            labels["bed"].text = f"Bed: {temp}/{target}C"
        else:
            labels["bed"].text = f"Bed: {temp}C"
        print(f"  Bed: {temp}C")

    if "layer_num" in print_data:
        current = print_data["layer_num"]
        total = print_data.get("total_layer_num", "?")
        labels["layer"].text = f"Layer: {current}/{total}"
        print(f"  Layer: {current}/{total}")

    if "gcode_file" in print_data:
        filename = print_data["gcode_file"]
        if len(filename) > 30:
            filename = filename[:27] + "..."
        labels["file"].text = filename


def on_connect(client, userdata, flags, rc):
    print("Connected to Bambu printer MQTT broker")
    client.subscribe(report_topic)
    print(f"Subscribed to {report_topic}")
    labels["state"].text = "State: Connected"
    request_pushall(client)


def on_disconnect(client, userdata, rc):
    print("Disconnected from MQTT broker")
    labels["state"].text = "State: Disconnected"


def on_message(client, topic, message):
    try:
        data = json.loads(message)
        if "print" not in data:
            return
        update_display(data["print"])
    except (ValueError, KeyError) as e:
        print(f"  Error parsing message: {e}")


def request_pushall(client):
    global sequence_id
    pushall = json.dumps({
        "pushing": {
            "sequence_id": str(sequence_id),
            "command": "pushall",
            "version": 1,
            "push_target": 1,
        }
    })
    client.publish(request_topic, pushall)
    sequence_id += 1
    print("Requested full status update")


# Set up MQTT client
mqtt_client = MQTT.MQTT(
    broker=bambu_broker,
    port=8883,
    username=user_id,
    password=access_token,
    socket_pool=pool,
    ssl_context=ssl_context,
    is_ssl=True,
)

mqtt_client.on_connect = on_connect
mqtt_client.on_disconnect = on_disconnect
mqtt_client.on_message = on_message

print(f"Connecting to Bambu printer at {bambu_ip}...")
mqtt_client.connect()

last_status_request = time.monotonic()
STATUS_INTERVAL = 60

while True:
    try:
        mqtt_client.loop(timeout=1)
    except Exception as e:
        print(f"MQTT loop error: {e}")
        labels["state"].text = "State: Reconnecting..."
        try:
            mqtt_client.reconnect()
        except Exception as re:
            print(f"Reconnect failed: {re}")
            labels["state"].text = "State: Connection lost"
            time.sleep(5)

    now = time.monotonic()
    if now - last_status_request >= STATUS_INTERVAL:
        try:
            request_pushall(mqtt_client)
        except Exception as e:
            print(f"Status request error: {e}")
        last_status_request = now

    time.sleep(0.1)
