"""Sensor simulator: publishes JSON passage messages like the real device.

Faithful to production behavior (docs/current-state.md §6), including the device's
timezone quirk: time_detected is São Paulo local time with a fake "Z" suffix.
Supports injecting the anomalies observed in prod: duplicate deliveries, gaps
(lost messages), counter resets, and garbage payloads.

Examples:
    python scripts/simulate_sensor.py                     # 10 passages, 1s apart
    python scripts/simulate_sensor.py --count 50 --interval 0.2
    python scripts/simulate_sensor.py --duplicate-every 7 --gap-every 11 --reset-at 30
    python scripts/simulate_sensor.py --garbage-every 9
"""

import argparse
import json
import os
import random
import sys
import time
from datetime import UTC, datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import paho.mqtt.client as mqtt  # noqa: E402

from scripts.env_loader import load_dotenv  # noqa: E402


# Real topic names are unlisted (public repo); set MQTT_TOPIC_JSON in .env.
# The placeholder default matches .env.example for a self-contained demo.
def json_topic() -> str:
    return os.environ.get("MQTT_TOPIC_JSON", "demo-sensor-json")


# Brazil has no DST since 2019; a fixed offset avoids the tzdata dependency on Windows.
SAO_PAULO = timezone(timedelta(hours=-3))


def device_timestamp(dt_utc: datetime) -> str:
    """Format like the real firmware: local São Paulo time, mislabeled with Z."""
    return dt_utc.astimezone(SAO_PAULO).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_payload(device_id: str, access_count: int, poweron: datetime) -> str:
    now = datetime.now(UTC)
    return json.dumps(
        {
            "device_id": device_id,
            "time_system": device_timestamp(now),
            "time_poweron": device_timestamp(poweron),
            "time_detected": device_timestamp(now),
            "access_count": access_count,
            "people_count": access_count // 2,
            "status_sensor": "free",
            "ip_address": "10.0.0.42",
            "RSSI": str(random.randint(-85, -70)),
            "pulse_ton": random.randint(95, 110),
            "pulse_toff": 302,
        }
    )


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=10, help="messages to publish")
    parser.add_argument("--interval", type=float, default=1.0, help="seconds between messages")
    parser.add_argument("--device", default="sensor-1")
    parser.add_argument("--start-count", type=int, default=14100, help="initial access_count")
    parser.add_argument(
        "--duplicate-every", type=int, default=0, help="re-publish every Nth message (delivery dup)"
    )
    parser.add_argument(
        "--gap-every", type=int, default=0, help="skip counter values every Nth message (lost msg)"
    )
    parser.add_argument(
        "--reset-at",
        type=int,
        default=0,
        help="reset access_count to 1 at message N (device reboot)",
    )
    parser.add_argument(
        "--garbage-every", type=int, default=0, help="publish a non-JSON payload every Nth message"
    )
    args = parser.parse_args()

    host = os.environ.get("MQTT_BROKER_HOST", "localhost")
    port = int(os.environ.get("MQTT_BROKER_PORT", "1883"))
    topic = json_topic()

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="sensor-simulator")
    client.connect(host, port, 60)
    client.loop_start()

    poweron = datetime.now(UTC) - timedelta(days=2)
    access = args.start_count
    published = 0

    for i in range(1, args.count + 1):
        if args.reset_at and i == args.reset_at:
            access = 0
            poweron = datetime.now(UTC)
            print(f"[{i}] -- simulating device reset (counter back to 1) --")

        if args.gap_every and i % args.gap_every == 0:
            access += random.randint(2, 4)  # counter advances, messages never sent
            print(f"[{i}] -- simulating gap (counter jumped to {access}) --")

        access += 1
        if args.garbage_every and i % args.garbage_every == 0:
            payload = "!!not-json-garbage!!"
        else:
            payload = build_payload(args.device, access, poweron)

        client.publish(topic, payload, qos=0)
        published += 1
        print(f"[{i}] published access_count={access}")

        if args.duplicate_every and i % args.duplicate_every == 0:
            client.publish(topic, payload, qos=0)
            published += 1
            print(f"[{i}] -- simulating duplicate delivery --")

        time.sleep(args.interval)

    time.sleep(1)  # let the last publishes flush
    client.loop_stop()
    client.disconnect()
    print(f"done: {published} messages published to {host}:{port} topic {topic}")


if __name__ == "__main__":
    main()
