"""Recorded-shape sensor payloads (values sanitized — real topic/device ids are unlisted).

Shapes match production reality documented in docs/current-state.md §6:
the 2024-era payload lacks pulse_ton/pulse_toff; time fields carry São Paulo
local time mislabeled with a Z suffix.
"""

import json

PAYLOAD_2026 = json.dumps(
    {
        "device_id": "unit-sensor",
        "time_system": "2026-07-31T16:44:10Z",
        "time_poweron": "2026-07-29T19:53:27Z",
        "time_detected": "2026-07-31T16:44:10Z",
        "access_count": 14007,
        "people_count": 7003,
        "status_sensor": "free",
        "ip_address": "10.0.0.42",
        "RSSI": "-76",
        "pulse_ton": 101,
        "pulse_toff": 302,
    }
)

PAYLOAD_2024 = json.dumps(  # early firmware: no pulse fields
    {
        "device_id": "unit-sensor",
        "time_system": "2024-09-23T12:41:52Z",
        "time_poweron": "2024-09-12T17:15:21Z",
        "time_detected": "2024-09-23T12:41:52Z",
        "access_count": 4200,
        "people_count": 2100,
        "status_sensor": "free",
        "ip_address": "10.0.0.42",
        "RSSI": "-82",
    }
)

PAYLOAD_MULTILINE = '{\n"device_id": "unit-sensor",\n"access_count": 7\n}'

GARBAGE_TEXT = "!!not-json-garbage!!"
GARBAGE_BYTES = b"\xff\xfe\xfa"
OVERSIZE_TEXT = "x" * 1500  # exceeds data_tracker.payload VARCHAR(1000)
