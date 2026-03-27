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

# Colors (inspired by BambuHelper)
COLOR_WHITE = 0xFFFFFF
COLOR_DIM = 0xAAAAAA
COLOR_DARK = 0x666666
COLOR_GREEN = 0x00FF00
COLOR_YELLOW = 0xFFFF00
COLOR_CYAN = 0x00FFFF
COLOR_NOZZLE_ORANGE = 0xFFAA00
COLOR_BED_CYAN = 0x00DDFF
COLOR_RED = 0xFF0000
COLOR_GOLD = 0xFFCC00
COLOR_FAN_BLUE = 0x4488FF
COLOR_TRACK = 0x333333
COLOR_BG = 0x000000

# Friendly state names and colors
STATE_MAP = {
    "IDLE": ("Idle", COLOR_GREEN),
    "RUNNING": ("Printing", COLOR_GREEN),
    "PAUSE": ("Paused", COLOR_YELLOW),
    "FINISH": ("Finished", COLOR_GREEN),
    "PREPARE": ("Preparing", COLOR_CYAN),
    "FAILED": ("ERROR!", COLOR_RED),
    "SLICING": ("Slicing", COLOR_CYAN),
}

# Speed level names
SPEED_MAP = {
    1: "Silent",
    2: "Standard",
    3: "Sport",
    4: "Ludicrous",
}

# Build display layout
main_group = displayio.Group()

# Background
bg_bitmap = displayio.Bitmap(480, 480, 1)
bg_palette = displayio.Palette(1)
bg_palette[0] = COLOR_BG
bg_sprite = displayio.TileGrid(bg_bitmap, pixel_shader=bg_palette)
main_group.append(bg_sprite)


def make_bar(x, y, w, h, fill_color, track_color=COLOR_TRACK):
    group = displayio.Group()
    # Track (background)
    track_bmp = displayio.Bitmap(w, h, 1)
    track_pal = displayio.Palette(1)
    track_pal[0] = track_color
    track_tg = displayio.TileGrid(track_bmp, pixel_shader=track_pal, x=x, y=y)
    group.append(track_tg)
    # Fill (foreground)
    fill_bmp = displayio.Bitmap(1, h, 1)
    fill_pal = displayio.Palette(1)
    fill_pal[0] = fill_color
    fill_tg = displayio.TileGrid(fill_bmp, pixel_shader=fill_pal, x=x, y=y)
    group.append(fill_tg)
    return group, fill_tg, w, h


def update_bar(fill_tg, percent, bar_w, bar_h):
    fill_w = max(1, int(bar_w * percent / 100))
    fill_tg.bitmap = displayio.Bitmap(fill_w, bar_h, 1)
    fill_tg.bitmap.fill(0)


# --- Top progress bar (thin, full width) ---
top_bar_group, top_bar_fill, TOP_BAR_W, TOP_BAR_H = make_bar(
    10, 4, 460, 6, COLOR_GOLD
)
main_group.append(top_bar_group)

# --- Header row: title + state ---
title_label = label.Label(
    terminalio.FONT, text="Bambu Printer", color=COLOR_GREEN,
    anchor_point=(0, 0), anchored_position=(20, 20), scale=3
)
main_group.append(title_label)

labels = {}

labels["state"] = label.Label(
    terminalio.FONT, text="Connecting...", color=COLOR_DIM,
    anchor_point=(1.0, 0), anchored_position=(460, 24), scale=2
)
main_group.append(labels["state"])

# --- File name ---
labels["file"] = label.Label(
    terminalio.FONT, text="", color=COLOR_DARK,
    anchor_point=(0, 0), anchored_position=(20, 60), scale=2
)
main_group.append(labels["file"])

# --- Progress section ---
labels["progress_pct"] = label.Label(
    terminalio.FONT, text="--%", color=COLOR_WHITE,
    anchor_point=(0, 0), anchored_position=(20, 95), scale=4
)
main_group.append(labels["progress_pct"])

labels["eta"] = label.Label(
    terminalio.FONT, text="ETA: --", color=COLOR_DIM,
    anchor_point=(1.0, 0), anchored_position=(460, 100), scale=2
)
main_group.append(labels["eta"])

# Main progress bar
main_bar_group, main_bar_fill, MAIN_BAR_W, MAIN_BAR_H = make_bar(
    20, 140, 440, 14, COLOR_GOLD
)
main_group.append(main_bar_group)

# --- Separator ---
sep1_bmp = displayio.Bitmap(440, 1, 1)
sep1_pal = displayio.Palette(1)
sep1_pal[0] = COLOR_TRACK
sep1_tg = displayio.TileGrid(sep1_bmp, pixel_shader=sep1_pal, x=20, y=168)
main_group.append(sep1_tg)

# --- Temperature section ---
temp_section_label = label.Label(
    terminalio.FONT, text="TEMPERATURES", color=COLOR_DARK,
    anchor_point=(0, 0), anchored_position=(20, 180), scale=1
)
main_group.append(temp_section_label)

# Nozzle
labels["nozzle_label"] = label.Label(
    terminalio.FONT, text="Nozzle", color=COLOR_DIM,
    anchor_point=(0, 0), anchored_position=(20, 200), scale=2
)
main_group.append(labels["nozzle_label"])

labels["nozzle_temp"] = label.Label(
    terminalio.FONT, text="--/--C", color=COLOR_NOZZLE_ORANGE,
    anchor_point=(1.0, 0), anchored_position=(460, 200), scale=2
)
main_group.append(labels["nozzle_temp"])

nozzle_bar_group, nozzle_bar_fill, NOZZLE_BAR_W, NOZZLE_BAR_H = make_bar(
    20, 225, 440, 10, COLOR_NOZZLE_ORANGE
)
main_group.append(nozzle_bar_group)

# Bed
labels["bed_label"] = label.Label(
    terminalio.FONT, text="Bed", color=COLOR_DIM,
    anchor_point=(0, 0), anchored_position=(20, 248), scale=2
)
main_group.append(labels["bed_label"])

labels["bed_temp"] = label.Label(
    terminalio.FONT, text="--/--C", color=COLOR_BED_CYAN,
    anchor_point=(1.0, 0), anchored_position=(460, 248), scale=2
)
main_group.append(labels["bed_temp"])

bed_bar_group, bed_bar_fill, BED_BAR_W, BED_BAR_H = make_bar(
    20, 273, 440, 10, COLOR_BED_CYAN
)
main_group.append(bed_bar_group)

# --- Separator ---
sep2_bmp = displayio.Bitmap(440, 1, 1)
sep2_pal = displayio.Palette(1)
sep2_pal[0] = COLOR_TRACK
sep2_tg = displayio.TileGrid(sep2_bmp, pixel_shader=sep2_pal, x=20, y=296)
main_group.append(sep2_tg)

# --- Fans section ---
fan_section_label = label.Label(
    terminalio.FONT, text="FANS", color=COLOR_DARK,
    anchor_point=(0, 0), anchored_position=(20, 308), scale=1
)
main_group.append(fan_section_label)

# Part fan
labels["part_fan_label"] = label.Label(
    terminalio.FONT, text="Part Fan", color=COLOR_DIM,
    anchor_point=(0, 0), anchored_position=(20, 328), scale=2
)
main_group.append(labels["part_fan_label"])

labels["part_fan_pct"] = label.Label(
    terminalio.FONT, text="--%", color=COLOR_FAN_BLUE,
    anchor_point=(1.0, 0), anchored_position=(460, 328), scale=2
)
main_group.append(labels["part_fan_pct"])

part_fan_bar_group, part_fan_bar_fill, PFAN_BAR_W, PFAN_BAR_H = make_bar(
    20, 353, 440, 10, COLOR_FAN_BLUE
)
main_group.append(part_fan_bar_group)

# Aux fan
labels["aux_fan_label"] = label.Label(
    terminalio.FONT, text="Aux Fan", color=COLOR_DIM,
    anchor_point=(0, 0), anchored_position=(20, 375), scale=2
)
main_group.append(labels["aux_fan_label"])

labels["aux_fan_pct"] = label.Label(
    terminalio.FONT, text="--%", color=COLOR_FAN_BLUE,
    anchor_point=(1.0, 0), anchored_position=(460, 375), scale=2
)
main_group.append(labels["aux_fan_pct"])

aux_fan_bar_group, aux_fan_bar_fill, AFAN_BAR_W, AFAN_BAR_H = make_bar(
    20, 400, 440, 10, COLOR_FAN_BLUE
)
main_group.append(aux_fan_bar_group)

# Chamber fan
labels["cham_fan_label"] = label.Label(
    terminalio.FONT, text="Chamber", color=COLOR_DIM,
    anchor_point=(0, 0), anchored_position=(20, 422), scale=2
)
main_group.append(labels["cham_fan_label"])

labels["cham_fan_pct"] = label.Label(
    terminalio.FONT, text="--%", color=COLOR_FAN_BLUE,
    anchor_point=(1.0, 0), anchored_position=(460, 422), scale=2
)
main_group.append(labels["cham_fan_pct"])

cham_fan_bar_group, cham_fan_bar_fill, CFAN_BAR_W, CFAN_BAR_H = make_bar(
    20, 447, 440, 10, COLOR_FAN_BLUE
)
main_group.append(cham_fan_bar_group)

# --- Bottom info bar ---
labels["layer"] = label.Label(
    terminalio.FONT, text="Layer: --", color=COLOR_DIM,
    anchor_point=(0, 0), anchored_position=(20, 466), scale=1
)
main_group.append(labels["layer"])

labels["speed"] = label.Label(
    terminalio.FONT, text="", color=COLOR_DIM,
    anchor_point=(1.0, 0), anchored_position=(460, 466), scale=1
)
main_group.append(labels["speed"])

display.root_group = main_group

# Max temps for bar scaling
NOZZLE_MAX_TEMP = 300
BED_MAX_TEMP = 120

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
        friendly, color = STATE_MAP.get(raw_state, (raw_state, COLOR_DIM))
        labels["state"].text = friendly
        labels["state"].color = color
        print(f"  State: {friendly}")

    if "mc_percent" in print_data:
        pct = print_data["mc_percent"]
        labels["progress_pct"].text = f"{pct}%"
        update_bar(top_bar_fill, pct, TOP_BAR_W, TOP_BAR_H)
        update_bar(main_bar_fill, pct, MAIN_BAR_W, MAIN_BAR_H)
        print(f"  Progress: {pct}%")

    if "mc_remaining_time" in print_data:
        mins = print_data["mc_remaining_time"]
        hours = mins // 60
        remainder = mins % 60
        if hours > 0:
            labels["eta"].text = f"ETA: {hours}h {remainder}m"
        else:
            labels["eta"].text = f"ETA: {remainder}m"
        print(f"  Remaining: {mins} min")

    if "nozzle_temper" in print_data:
        temp = print_data["nozzle_temper"]
        target = print_data.get("nozzle_target_temper", 0)
        if target:
            labels["nozzle_temp"].text = f"{temp}/{target}C"
            bar_pct = min(100, int(temp / target * 100)) if target > 0 else 0
        else:
            labels["nozzle_temp"].text = f"{temp}C"
            bar_pct = min(100, int(temp / NOZZLE_MAX_TEMP * 100))
        update_bar(nozzle_bar_fill, bar_pct, NOZZLE_BAR_W, NOZZLE_BAR_H)
        print(f"  Nozzle: {temp}C")

    if "bed_temper" in print_data:
        temp = print_data["bed_temper"]
        target = print_data.get("bed_target_temper", 0)
        if target:
            labels["bed_temp"].text = f"{temp}/{target}C"
            bar_pct = min(100, int(temp / target * 100)) if target > 0 else 0
        else:
            labels["bed_temp"].text = f"{temp}C"
            bar_pct = min(100, int(temp / BED_MAX_TEMP * 100))
        update_bar(bed_bar_fill, bar_pct, BED_BAR_W, BED_BAR_H)
        print(f"  Bed: {temp}C")

    # Fan speeds (Bambu sends cooling_fan_speed as 0-15, big fans as 0-100)
    if "cooling_fan_speed" in print_data:
        raw = print_data["cooling_fan_speed"]
        pct = int(raw * 100 / 15)
        labels["part_fan_pct"].text = f"{pct}%"
        update_bar(part_fan_bar_fill, pct, PFAN_BAR_W, PFAN_BAR_H)
        print(f"  Part fan: {pct}%")

    if "big_fan1_speed" in print_data:
        raw = print_data["big_fan1_speed"]
        pct = int(raw * 100 / 15)
        labels["aux_fan_pct"].text = f"{pct}%"
        update_bar(aux_fan_bar_fill, pct, AFAN_BAR_W, AFAN_BAR_H)
        print(f"  Aux fan: {pct}%")

    if "big_fan2_speed" in print_data:
        raw = print_data["big_fan2_speed"]
        pct = int(raw * 100 / 15)
        labels["cham_fan_pct"].text = f"{pct}%"
        update_bar(cham_fan_bar_fill, pct, CFAN_BAR_W, CFAN_BAR_H)
        print(f"  Chamber fan: {pct}%")

    if "layer_num" in print_data:
        current = print_data["layer_num"]
        total = print_data.get("total_layer_num", "?")
        labels["layer"].text = f"Layer: {current}/{total}"
        print(f"  Layer: {current}/{total}")

    if "spd_lvl" in print_data:
        spd = print_data["spd_lvl"]
        labels["speed"].text = SPEED_MAP.get(spd, f"Speed: {spd}")

    if "subtask_name" in print_data:
        filename = print_data["subtask_name"]
        if len(filename) > 35:
            filename = filename[:32] + "..."
        labels["file"].text = filename
    elif "gcode_file" in print_data:
        filename = print_data["gcode_file"]
        if len(filename) > 35:
            filename = filename[:32] + "..."
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
