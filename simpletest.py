import json
import os
import wifi
import bambulabs as bl

# Set up networking
print("Connecting to AP...")
wifi.radio.connect(
    os.getenv("CIRCUITPY_WIFI_SSID"), os.getenv("CIRCUITPY_WIFI_PASSWORD")
)
print(f"Connected to {os.getenv('CIRCUITPY_WIFI_SSID')}")
print(f"My IP address: {wifi.radio.ipv4_address}")

device_id = os.getenv("DEVICE_ID")

printer = bl.BambuPrinter(device_id)
printer.connect()

status = printer.pushall()

if status is None:
    print("Timed out waiting for pushall response.")
else:
    print("--- Printer Status ---")
    print(f"State:             {status.gcode_state}")
    print(f"File:              {status.gcode_file}")
    print(f"Job:               {status.subtask_name}")
    print(f"Progress:          {status.print_percentage}%")
    print(f"Remaining:         {status.remaining_time} min")
    print(f"Layer:             {status.current_layer} / {status.total_layers}")
    print(f"Print speed:       {status.print_speed}")
    print(f"Print error:       {status.print_error_code}")
    print(f"Nozzle temp:       {status.nozzle_temperature} / {status.nozzle_temperature_target} C")
    print(f"Bed temp:          {status.bed_temperature} / {status.bed_temperature_target} C")
    print(f"Chamber temp:      {status.chamber_temperature} C")
    print(f"Part fan:          {status.part_fan_speed}")
    print(f"Aux fan:           {status.aux_fan_speed}")
    print(f"Chamber fan:       {status.chamber_fan_speed}")
    print(f"Nozzle type:       {status.nozzle_type}")
    print(f"Nozzle diameter:   {status.nozzle_diameter} mm")
    print(f"WiFi signal:       {status.wifi_signal}")
    print(f"Light state:       {status.light_state}")
    print(f"Firmware version:  {status.firmware_version}")
    print()
    print("--- Raw JSON ---")
    print(json.dumps(status.raw))
