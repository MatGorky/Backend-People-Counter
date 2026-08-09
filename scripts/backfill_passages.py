"""Backfill passage_event from the raw data_tracker log (spec-002).

Idempotent: rows whose id already appears as passage_event.raw_id are skipped
(their counters still feed the dedupe/era tracking so re-runs and the
live-ingest boundary stay consistent). Produces a data-quality report.

    python scripts/backfill_passages.py            # local rehearsal
    python scripts/backfill_passages.py --allow-remote   # prod gate use
"""

import argparse
import os
import sys
from datetime import UTC

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.env_loader import load_dotenv  # noqa: E402

BATCH = 1000


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-remote", action="store_true")
    args = parser.parse_args()

    uri = os.environ.get("SQLALCHEMY_DATABASE_URI", "")
    if not args.allow_remote and "localhost" not in uri and "127.0.0.1" not in uri:
        sys.exit(f"REFUSING non-local database without --allow-remote: {uri!r}")

    from sqlalchemy import select

    from app import create_app, db
    from app.models.data_tracker import DataTracker
    from app.models.device import Device
    from app.models.passage_event import PassageEvent
    from app.services.ingestion import is_duplicate, parse_passage

    app = create_app()
    with app.app_context():
        json_topic = app.config["MQTT_TOPIC_JSON"]
        if not json_topic:
            sys.exit("MQTT_TOPIC_JSON not configured")

        device_rooms = {d.id: d.room_id for d in db.session.execute(select(Device)).scalars()}
        existing = {
            raw_id: (dev, ac)
            for raw_id, dev, ac in db.session.execute(
                select(PassageEvent.raw_id, PassageEvent.device_id, PassageEvent.access_count)
                .filter(PassageEvent.raw_id.is_not(None))
                .order_by(PassageEvent.raw_id)
            )
        }

        stats = {
            "raw_rows": 0,
            "already_migrated": 0,
            "events_created": 0,
            "duplicates_dropped": 0,
            "parse_failures": 0,
            "unknown_device": 0,
            "counter_resets": 0,
            "gap_jumps": 0,
            "estimated_missed_passages": 0,
            "clock_skew_fallbacks": 0,
        }
        last_access: dict[str, int | None] = {}

        def next_batch(after_id: int):
            return (
                db.session.execute(
                    select(DataTracker)
                    .filter(DataTracker.topic == json_topic, DataTracker.id > after_id)
                    .order_by(DataTracker.id)
                    .limit(BATCH)
                )
                .scalars()
                .all()
            )

        last_id = 0
        while batch_rows := next_batch(last_id):
            for raw in batch_rows:
                stats["raw_rows"] += 1

                if raw.id in existing:
                    dev, ac = existing[raw.id]
                    if ac is not None:
                        last_access[dev] = ac
                    stats["already_migrated"] += 1
                    continue

                received_at = raw.register_time.replace(tzinfo=UTC)
                parsed = parse_passage(raw.payload, received_at)
                if parsed is None:
                    stats["parse_failures"] += 1
                    continue
                if parsed.device_id not in device_rooms:
                    stats["unknown_device"] += 1
                    continue
                if parsed.clock_skew_flagged:
                    stats["clock_skew_fallbacks"] += 1

                prev = last_access.get(parsed.device_id)
                if is_duplicate(parsed.access_count, prev):
                    stats["duplicates_dropped"] += 1
                    continue
                if parsed.access_count is not None and prev is not None:
                    if parsed.access_count < prev:
                        stats["counter_resets"] += 1
                    elif parsed.access_count > prev + 1:
                        stats["gap_jumps"] += 1
                        stats["estimated_missed_passages"] += parsed.access_count - prev - 1
                if parsed.access_count is not None:
                    last_access[parsed.device_id] = parsed.access_count

                db.session.add(
                    PassageEvent(
                        device_id=parsed.device_id,
                        room_id=device_rooms[parsed.device_id],
                        occurred_at=parsed.occurred_at,
                        received_at=received_at,
                        access_count=parsed.access_count,
                        people_count=parsed.people_count,
                        status_sensor=parsed.status_sensor,
                        rssi=parsed.rssi,
                        ip_address=parsed.ip_address,
                        pulse_ton=parsed.pulse_ton,
                        pulse_toff=parsed.pulse_toff,
                        raw_id=raw.id,
                    )
                )
                stats["events_created"] += 1

            last_id = batch_rows[-1].id
            db.session.commit()

    print("== backfill report ==")
    for key, value in stats.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
