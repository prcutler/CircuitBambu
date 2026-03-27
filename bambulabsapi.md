# BambuLabs MQTT API Reference

The BambuLabs API uses a simple **two-topic** MQTT architecture. All communication is multiplexed over just these two topics using JSON payloads.

## MQTT Topics

### `device/{serial}/report` — Subscribe (incoming data)

The **only** topic the client subscribes to. All printer state data arrives here. The JSON payload contains different top-level keys:

| Payload Key | Data Received |
|-------------|---------------|
| `print` | Temperatures, fan speeds, print progress, layers, AMS info, speed, errors, etc. |
| `info` | Hardware/firmware version details |
| `upgrade` | Firmware version history, update availability |
| `system` | Light state, wifi signal, access code, accessories |

### `device/{serial}/request` — Publish (outgoing commands)

The **only** topic the client publishes to. All commands are sent here, differentiated by JSON payload structure:

| Payload Key | Command | Purpose |
|-------------|---------|---------|
| `pushing` | `pushall` | Force full state update |
| `info` | `get_version` | Request hardware/firmware info |
| `upgrade` | `get_history` | Get firmware version history |
| `upgrade` | `upgrade_confirm` | Upgrade firmware |
| `upgrade` | `upgrade_history` | Downgrade to specific firmware |
| `print` | `project_file` | Start printing a 3MF file |
| `print` | `stop` | Stop current print |
| `print` | `pause` | Pause current print |
| `print` | `resume` | Resume paused print |
| `print` | `gcode_line` | Send raw G-code commands |
| `print` | `print_speed` | Set speed level (0-3) |
| `print` | `ams_filament_setting` | Set filament type/color for a tray |
| `print` | `ams_change_filament` | Load/unload filament |
| `print` | `ams_control` (`resume`) | Retry filament action |
| `print` | `calibration` | Run calibration routines |
| `print` | `skip_objects` | Skip objects during print |
| `system` | `led_mode: on/off` | Toggle chamber light |
| `system` | `get_access_code` | Request access code |
| `system` | `set_accessories` | Set nozzle type/diameter |
| `system` | `reboot` | Reboot the printer |
| `camera` | `ipcam_record_set` | Enable/disable timelapse |

On initial connection, the client automatically publishes three commands together: `pushall`, `get_version`, and `get_history` to bootstrap the full printer state.

## MQTT Commands (Python API)

### Connection & System

| Command | Description | Parameters |
|---------|-------------|------------|
| `connect()` | Establish MQTT connection | — |
| `start()` | Start the MQTT client | — |
| `stop()` | Stop the MQTT client | — |
| `loop_forever()` | Block and loop indefinitely | — |
| `is_connected()` | Check connection status | — |

### Status & Info

| Command | Description | Parameters |
|---------|-------------|------------|
| `dump()` | Get full printer state as dict | — |
| `get_current_state()` | Get state from `stg_cur` | Returns `PrintStatus` |
| `get_printer_state()` | Get operational state | Returns `GcodeState` |
| `info_get_version()` | Get hardware/firmware info | — |
| `request_firmware_history()` | Query firmware versions | — |
| `pushall()` | Force full state update (use sparingly) | — |

### Temperature Control

| Command | Description | Parameters |
|---------|-------------|------------|
| `set_bed_temperature()` | Set bed temp | `temperature` (int), `override` (bool) |
| `get_bed_temperature()` | Read bed temp | — |
| `get_bed_temperature_target()` | Get target bed temp | — |
| `set_nozzle_temperature()` | Set nozzle temp | `temperature` (int), `override` (bool) |
| `get_nozzle_temperature()` | Read nozzle temp | — |
| `get_nozzle_temperature_target()` | Get target nozzle temp | — |
| `get_chamber_temperature()` | Read chamber temp | — |

### Fan Control

| Command | Description | Parameters |
|---------|-------------|------------|
| `set_part_fan_speed()` | Set part cooling fan | `speed` (int/float) |
| `get_part_fan_speed()` | Read part fan (0-255) | — |
| `set_aux_fan_speed()` | Set auxiliary fan | `speed` (int/float) |
| `get_aux_fan_speed()` | Read aux fan (0-255) | — |
| `set_chamber_fan_speed()` | Set chamber fan | `speed` (int/float) |
| `get_chamber_fan_speed()` | Read chamber fan (0-255) | — |
| `get_fan_gear()` | Get consolidated fan status | — |

### Print Operations

| Command | Description | Parameters |
|---------|-------------|------------|
| `start_print_3mf()` | Start printing a 3MF file | `filename`, `plate_number`, `use_ams`, `ams_mapping`, `skip_objects`, `flow_calibration` |
| `pause_print()` | Pause active print | — |
| `resume_print()` | Resume paused print | — |
| `stop_print()` | Stop current print | — |
| `get_file_name()` | Get current print filename | — |
| `gcode_file()` | Get active gcode file | — |
| `get_last_print_percentage()` | Get completion % | — |
| `get_remaining_time()` | Get time remaining | — |

### Layer & Progress

| Command | Description | Parameters |
|---------|-------------|------------|
| `current_layer_num()` | Current layer number | — |
| `total_layer_num()` | Total layers | — |
| `gcode_file_prepare_percentage()` | File prep progress | — |
| `subtask_name()` | Current task ID | — |

### Speed & Object Control

| Command | Description | Parameters |
|---------|-------------|------------|
| `set_print_speed_lvl()` | Set speed level | `speed_lvl` (int, default 1) |
| `get_print_speed()` | Read print speed | — |
| `skip_objects()` | Skip objects during print | `obj_list` (list of ints) |
| `get_skipped_objects()` | Get skipped objects | — |

### Filament / AMS

| Command | Description | Parameters |
|---------|-------------|------------|
| `load_filament_spool()` | Load filament | — |
| `unload_filament_spool()` | Unload filament | — |
| `resume_filament_action()` | Resume filament operation | — |
| `set_printer_filament()` | Set manual filament properties | `filament_material`, `colour`, `ams_id`, `tray_id` |
| `process_ams()` | Get AMS filament data | — |
| `vt_tray()` | Get external spool properties | — |

### Nozzle Config

| Command | Description | Parameters |
|---------|-------------|------------|
| `set_nozzle_info()` | Configure nozzle specs | `nozzle_type`, `nozzle_diameter` (default 0.4) |
| `nozzle_type()` | Get installed nozzle type | — |
| `nozzle_diameter()` | Get nozzle size | — |

### Lighting

| Command | Description | Parameters |
|---------|-------------|------------|
| `turn_light_on()` | Turn on chamber light | — |
| `turn_light_off()` | Turn off chamber light | — |
| `get_light_state()` | Get light mode | — |

### Calibration & Maintenance

| Command | Description | Parameters |
|---------|-------------|------------|
| `auto_home()` | Home all axes | — |
| `calibration()` | Run calibration | `bed_levelling`, `motor_noise_cancellation`, `vibration_compensation` (all bool) |
| `set_bed_height()` | Set Z-axis bed position | `height` (int, 0-256) |
| `set_auto_step_recovery()` | Enable/disable step recovery | `auto_step_recovery` (bool) |

### Firmware

| Command | Description | Parameters |
|---------|-------------|------------|
| `firmware_version()` | Get current firmware | — |
| `new_printer_firmware()` | Check for updates | — |
| `upgrade_firmware()` | Update firmware | `override` (bool) |
| `downgrade_firmware()` | Revert firmware | `firmware_version` (str) |
| `get_firmware_history()` | Get version history | — |

### GCode & Advanced

| Command | Description | Parameters |
|---------|-------------|------------|
| `send_gcode()` | Send raw G-code | `gcode_command` (str/list), `gcode_check` (bool) |
| `print_type()` | Get print source (cloud/local) | — |
| `print_error_code()` | Get error code | — |

### System

| Command | Description | Parameters |
|---------|-------------|------------|
| `get_access_code()` | Get local access code | — |
| `request_access_code()` | Request access code from device | — |
| `set_onboard_printer_timelapse()` | Enable/disable timelapse | `enable` (bool) |
| `get_sequence_id()` | Get message sequence ID | — |
| `wifi_signal()` | Get WiFi signal (dBm) | — |
| `reboot()` | Restart the printer | — |
