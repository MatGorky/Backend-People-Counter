"""Seed the LOCAL database with ~60 days of plausible library traffic.

Generates data_tracker rows shaped exactly like real JSON-topic ingestion
(JSON payload string + register_time in UTC), with a library-like daily profile:
weekdays 07-19h São Paulo time, lunchtime peak, quiet weekends.

SAFETY: refuses to run against anything that isn't localhost/127.0.0.1.

    python scripts/seed_local.py             # 60 days ending today
    python scripts/seed_local.py --days 90
"""
import argparse
import json
import os
import random
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.env_loader import load_dotenv  # noqa: E402

SAO_PAULO_OFFSET = timedelta(hours=-3)  # no DST in Brazil since 2019


def hourly_weight(hour_local: int, weekday: int) -> float:
    if weekday >= 5:  # weekend: library closed
        return 0.0
    if hour_local < 7 or hour_local > 19:
        return 0.0
    # ramp up in the morning, peak at lunch and mid-afternoon
    peaks = {7: 1, 8: 3, 9: 5, 10: 6, 11: 7, 12: 9, 13: 8, 14: 6, 15: 6, 16: 7, 17: 5, 18: 3, 19: 1}
    return peaks.get(hour_local, 0)


def main() -> None:
    load_dotenv()
    uri = os.environ.get("SQLALCHEMY_DATABASE_URI", "")
    if "localhost" not in uri and "127.0.0.1" not in uri:
        sys.exit(f"REFUSING to seed a non-local database: {uri!r}")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=60)
    parser.add_argument("--device", default="sensor-1")
    args = parser.parse_args()

    topic = os.environ.get("MQTT_TOPIC_JSON", "demo-sensor-json")

    from app import app, db  # noqa: E402  (import starts the app; broker guard handles no-MQTT)
    from app.models.data_tracker import DataTracker  # noqa: E402

    random.seed(438)
    # Work in NAIVE UTC throughout — matches how prod stores register_time.
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    poweron_utc = now_utc - timedelta(days=args.days + 3)
    access = 1000
    rows = []

    start = now_utc - timedelta(days=args.days)
    for day in range(args.days + 1):
        date_utc = start + timedelta(days=day)
        date_local = date_utc + SAO_PAULO_OFFSET
        for hour_local in range(6, 21):
            weight = hourly_weight(hour_local, date_local.weekday())
            passages = random.randint(0, 2) if weight == 0 else int(random.gauss(weight * 2, weight * 0.6))
            for _ in range(max(0, passages)):
                access += 1
                minute, second = random.randint(0, 59), random.randint(0, 59)
                local_naive = date_local.replace(hour=hour_local, minute=minute, second=second, microsecond=0)
                utc_naive = local_naive - SAO_PAULO_OFFSET  # register_time is naive UTC in prod
                if utc_naive > now_utc:
                    continue  # never seed the future
                device_ts = local_naive.strftime("%Y-%m-%dT%H:%M:%SZ")  # SP local mislabeled Z
                payload = json.dumps(
                    {
                        "device_id": args.device,
                        "time_system": device_ts,
                        "time_poweron": (poweron_utc + SAO_PAULO_OFFSET).strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "time_detected": device_ts,
                        "access_count": access,
                        "people_count": access // 2,
                        "status_sensor": "free",
                        "ip_address": "10.0.0.42",
                        "RSSI": str(random.randint(-85, -70)),
                        "pulse_ton": random.randint(95, 110),
                        "pulse_toff": 302,
                    }
                )
                rows.append(DataTracker(topic=topic, payload=payload, register_time=utc_naive))

    with app.app_context():
        db.session.add_all(rows)
        db.session.commit()
    print(f"seeded {len(rows)} passage rows over {args.days} days into {uri}")


if __name__ == "__main__":
    main()
