import asyncio
import json
import os

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

# Set up networking
ssid = os.getenv("CIRCUITPY_WIFI_SSID")
password = os.getenv("CIRCUITPY_WIFI_PASSWORD")

radio = wifi.radio

# code to make sure your radio is connected

pool = adafruit_connection_manager.get_radio_socketpool(radio)
ssl_context = adafruit_connection_manager.get_radio_ssl_context(radio)

print("Connecting to AP...")
wifi.radio.connect(
    os.getenv("CIRCUITPY_WIFI_SSID"), os.getenv("CIRCUITPY_WIFI_PASSWORD")
)
print(f"Connected to {os.getenv('CIRCUITPY_WIFI_SSID')}")
print(f"My IP address: {wifi.radio.ipv4_address}")

# Bambu MQTT settings
bambu_ip = "192.168.1.26"
device_id = os.getenv("DEVICE_ID")
lan_access_code = os.getenv("LAN_ACCESS_CODE")
user_id = os.getenv("USER_ID")
bambu_access_token = os.getenv("BAMBU_ACCESS_TOKEN")
bambu_broker = os.getenv("BAMBU_BROKER")

report_topic = "device/01S09A2B1100104/report"
request_topic = f"device/{device_id}/request"

sequence_id = 0


def on_connect(client, userdata, flags, rc):
    print(f"Connected to Bambu printer MQTT broker")
    client.subscribe(report_topic)
    print(f"Subscribed to {report_topic}")



def on_disconnect(client, userdata, rc):
    print(f"Disconnected from MQTT broker")


def on_message(client, topic, message):
    print(f"Message on {topic}")
    try:
        data = json.loads(message)
        if "print" in data:
            print_data = data["print"]
            if "gcode_state" in print_data:
                print(f"  State: {print_data['gcode_state']}")
            if "mc_percent" in print_data:
                print(f"  Progress: {print_data['mc_percent']}%")
            if "mc_remaining_time" in print_data:
                print(f"  Remaining: {print_data['mc_remaining_time']} min")
            if "nozzle_temper" in print_data:
                print(f"  Nozzle temp: {print_data['nozzle_temper']}C")
            if "bed_temper" in print_data:
                print(f"  Bed temp: {print_data['bed_temper']}C")
    except (ValueError, KeyError) as e:
        print(f"  Error parsing message: {e}")



# Set up MQTT client
mqtt_client = MQTT.MQTT(
    broker="192.168.1.26",
    port=8883,
    username=os.getenv("USER_NAME"),
    password=lan_access_code,
    socket_pool=pool,
    ssl_context=ssl_context,
    is_ssl=True,
    socket_timeout=0.01  # apparently socket recvs even block asyncio
)

mqtt_client.on_connect = on_connect
mqtt_client.on_disconnect = on_disconnect
mqtt_client.on_message = on_message

print(f"Connecting to Bambu printer at {bambu_ip}...")
mqtt_client.connect()


async def mqtt_loop():
    while True:
        try:
            mqtt_client.loop(timeout=1)
        except Exception as e:
            print(f"MQTT loop error: {e}")
            try:
                mqtt_client.reconnect()
            except Exception as re:
                print(f"Reconnect failed: {re}")
                await asyncio.sleep(5)
        await asyncio.sleep(0.1)


async def request_status():
    while True:
        await asyncio.sleep(60)
        try:
            request_pushall(mqtt_client)
        except Exception as e:
            print(f"Status request error: {e}")


async def main():
    mqtt_task = asyncio.create_task(mqtt_loop())
    status_task = asyncio.create_task(request_status())
    await asyncio.gather(mqtt_task, status_task)


asyncio.run(main())

