import os
import time

import board
import busio
import displayio
import terminalio
import vectorio
import wifi
import dotclockframebuffer
from framebufferio import FramebufferDisplay
from adafruit_display_text import label

import bambulabs as bl

# ---- Display hardware init -------------------------------------------------

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

# ---- Colors ----------------------------------------------------------------

COLOR_BG      = 0x000000
COLOR_WHITE   = 0xFFFFFF
COLOR_GRAY    = 0x444444
COLOR_DIVIDER = 0x333333
COLOR_GREEN   = 0x00FF00
COLOR_CYAN    = 0x00FFFF    # progress
COLOR_ORANGE  = 0xFF6600    # nozzle
COLOR_RED     = 0xFF2200    # bed
COLOR_BLUE    = 0x0088FF    # fan

# ---- Screen layout ---------------------------------------------------------
#
#  480 x 480 px total:
#
#   ┌────────────────────────────────────┐  y=0
#   │  Status: Printing    ETA: 1h 23m  │  HEADER (48px)
#   ├──────────────────┬─────────────────┤  y=48
#   │   PROGRESS       │   NOZZLE        │
#   │                  │                 │  each quadrant 200px tall
#   ├──────────────────┼─────────────────┤  y=248
#   │   BED            │   FAN           │
#   │                  │                 │
#   ├────────────────────────────────────┤  y=448
#   │  Layer: 112 / 177                  │  FOOTER (32px)
#   └────────────────────────────────────┘  y=480

HEADER_H = 48
FOOTER_H = 32
QW, QH   = 240, 200
BAR_W, BAR_H   = 200, 24
BAR_INNER_W    = BAR_W - 4
BAR_INNER_H    = BAR_H - 4

QUAD_ROW1_Y = HEADER_H               # 48
QUAD_ROW2_Y = HEADER_H + QH          # 248
FOOTER_Y    = HEADER_H + QH * 2      # 448

ORIGINS = {
    "progress": (0,   QUAD_ROW1_Y),
    "nozzle":   (240, QUAD_ROW1_Y),
    "bed":      (0,   QUAD_ROW2_Y),
    "fan":      (240, QUAD_ROW2_Y),
}

STATE_MAP = {
    "IDLE":    "Idle",
    "RUNNING": "Printing",
    "PAUSE":   "Paused",
    "FINISH":  "Finished",
    "PREPARE": "Preparing",
    "FAILED":  "Failed",
    "SLICING": "Slicing",
}

# ---- Build display group ---------------------------------------------------

main_group = displayio.Group()

# Background
bg_bitmap = displayio.Bitmap(480, 480, 1)
bg_palette = displayio.Palette(1)
bg_palette[0] = COLOR_BG
main_group.append(displayio.TileGrid(bg_bitmap, pixel_shader=bg_palette))

# Divider palette (reused for all lines)
div_palette = displayio.Palette(1)
div_palette[0] = COLOR_DIVIDER

# Horizontal divider: header / quadrants
main_group.append(displayio.TileGrid(
    displayio.Bitmap(480, 2, 1), pixel_shader=div_palette, x=0, y=HEADER_H - 2,
))
# Horizontal divider: quadrant rows
main_group.append(displayio.TileGrid(
    displayio.Bitmap(480, 2, 1), pixel_shader=div_palette, x=0, y=QUAD_ROW2_Y - 1,
))
# Horizontal divider: quadrants / footer
main_group.append(displayio.TileGrid(
    displayio.Bitmap(480, 2, 1), pixel_shader=div_palette, x=0, y=FOOTER_Y - 1,
))
# Vertical divider between columns
main_group.append(displayio.TileGrid(
    displayio.Bitmap(2, QH * 2, 1), pixel_shader=div_palette, x=239, y=HEADER_H,
))

# ---- Header labels ---------------------------------------------------------

status_lbl = label.Label(
    terminalio.FONT, text="Status: --", color=COLOR_GREEN,
    anchor_point=(0, 0.5), anchored_position=(12, HEADER_H // 2), scale=2,
)
main_group.append(status_lbl)

eta_lbl = label.Label(
    terminalio.FONT, text="ETA: --", color=COLOR_WHITE,
    anchor_point=(1, 0.5), anchored_position=(468, HEADER_H // 2), scale=2,
)
main_group.append(eta_lbl)

# ---- Footer label ----------------------------------------------------------

layer_lbl = label.Label(
    terminalio.FONT, text="Layer: --", color=COLOR_WHITE,
    anchor_point=(0.5, 0.5), anchored_position=(240, FOOTER_Y + FOOTER_H // 2), scale=2,
)
main_group.append(layer_lbl)

# ---- Quadrant builder ------------------------------------------------------

def make_quadrant(title, color, ox, oy):
    """Add a titled quadrant with value, sub-label, and progress bar to main_group.
    Returns (value_lbl, sub_lbl, bar_rect).
    """
    main_group.append(label.Label(
        terminalio.FONT, text=title, color=color,
        anchor_point=(0.5, 0), anchored_position=(ox + QW // 2, oy + 8), scale=2,
    ))
    value_lbl = label.Label(
        terminalio.FONT, text="--", color=COLOR_WHITE,
        anchor_point=(0.5, 0), anchored_position=(ox + QW // 2, oy + 48), scale=3,
    )
    main_group.append(value_lbl)

    sub_lbl = label.Label(
        terminalio.FONT, text="", color=COLOR_GRAY,
        anchor_point=(0.5, 0), anchored_position=(ox + QW // 2, oy + 112), scale=2,
    )
    main_group.append(sub_lbl)

    bar_ox = ox + (QW - BAR_W) // 2
    bar_oy = oy + 148

    outline_pal = displayio.Palette(1)
    outline_pal[0] = COLOR_GRAY
    main_group.append(displayio.TileGrid(
        displayio.Bitmap(BAR_W, BAR_H, 1), pixel_shader=outline_pal, x=bar_ox, y=bar_oy,
    ))

    fill_pal = displayio.Palette(1)
    fill_pal[0] = color
    bar_rect = vectorio.Rectangle(
        pixel_shader=fill_pal, width=1, height=BAR_INNER_H,
        x=bar_ox + 2, y=bar_oy + 2,
    )
    main_group.append(bar_rect)

    return value_lbl, sub_lbl, bar_rect


progress_value, progress_sub, progress_bar = make_quadrant(
    "Progress", COLOR_CYAN, *ORIGINS["progress"]
)
nozzle_value, nozzle_sub, nozzle_bar = make_quadrant(
    "Nozzle", COLOR_ORANGE, *ORIGINS["nozzle"]
)
bed_value, bed_sub, bed_bar = make_quadrant(
    "Bed", COLOR_RED, *ORIGINS["bed"]
)
fan_value, fan_sub, fan_bar = make_quadrant(
    "Fan", COLOR_BLUE, *ORIGINS["fan"]
)

display.root_group = main_group

# ---- Update helpers --------------------------------------------------------

NOZZLE_MAX = 250
BED_MAX    = 65


def _bar_width(pct):
    return max(1, int(BAR_INNER_W * min(pct, 100) / 100))


def _fmt_eta(mins):
    if mins is None:
        return "ETA: --"
    hours, remainder = divmod(mins, 60)
    if hours > 0:
        return f"ETA: {hours}h {remainder}m"
    return f"ETA: {remainder}m"


def update_display(status):
    # Header: status + ETA
    raw_state = status.gcode_state
    if raw_state:
        status_lbl.text = f"Status: {STATE_MAP.get(raw_state, raw_state)}"
    eta_lbl.text = _fmt_eta(status.remaining_time)

    # Footer: layers
    layer = status.current_layer
    total = status.total_layers
    if layer is not None and total is not None:
        layer_lbl.text = f"Layer: {layer} / {total}"

    # Progress quadrant
    pct = status.print_percentage
    if pct is not None:
        progress_value.text = f"{pct}%"
        progress_sub.text = ""
        progress_bar.width = _bar_width(pct)

    # Nozzle quadrant
    nozzle = status.nozzle_temperature
    if nozzle is not None:
        target = status.nozzle_temperature_target or 0
        nozzle_value.text = f"{nozzle}C"
        nozzle_sub.text = f"target {target}C" if target else ""
        nozzle_bar.width = _bar_width(nozzle / NOZZLE_MAX * 100)

    # Bed quadrant
    bed = status.bed_temperature
    if bed is not None:
        target = status.bed_temperature_target or 0
        bed_value.text = f"{bed}C"
        bed_sub.text = f"target {target}C" if target else ""
        bed_bar.width = _bar_width(bed / BED_MAX * 100)

    # Fan quadrant
    fan = status.part_fan_speed
    if fan is not None:
        fan = int(fan)
        fan_pct = int(fan / 255 * 100)
        fan_value.text = f"{fan_pct}%"
        fan_sub.text = f"speed {fan}/255"
        fan_bar.width = _bar_width(fan_pct)


# ---- WiFi + printer connection ---------------------------------------------

print("Connecting to WiFi...")
wifi.radio.connect(os.getenv("CIRCUITPY_WIFI_SSID"), os.getenv("CIRCUITPY_WIFI_PASSWORD"))
print(f"Connected — IP: {wifi.radio.ipv4_address}")

device_id = os.getenv("DEVICE_ID")
printer = bl.BambuPrinter(device_id)
printer.connect()
status_lbl.text = "Status: Connected"

status = printer.pushall()
if status is None:
    print("Timed out waiting for pushall response.")
    status_lbl.text = "Status: No response"
else:
    update_display(status)

# ---- Main loop -------------------------------------------------------------

STATUS_INTERVAL = 30
last_poll = time.monotonic()

while True:
    try:
        printer.loop()
    except Exception as e:
        print(f"MQTT error: {e}")
        status_lbl.text = "Status: Reconnecting"
        try:
            printer.connect()
            status_lbl.text = "Status: Connected"
        except Exception as re:
            print(f"Reconnect failed: {re}")
            status_lbl.text = "Status: Lost"
            time.sleep(5)

    now = time.monotonic()
    if now - last_poll >= STATUS_INTERVAL:
        status = printer.pushall()
        if status is not None:
            update_display(status)
        else:
            print("Timed out waiting for pushall response.")
        last_poll = now

    time.sleep(0.1)
