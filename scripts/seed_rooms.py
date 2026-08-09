"""Register a room, its device, and optional user grants (spec-003).

    python scripts/seed_rooms.py --name "Biblioteca NCE" --slug biblioteca-nce \
        --device <device-id> [--grant <supabase-user-uuid> ...]

Idempotent: existing room slug / device id / grant are updated or skipped.
Refuses non-localhost databases unless --allow-remote is passed (prod gate use).
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.env_loader import load_dotenv  # noqa: E402


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--device", required=True, help="MQTT device_id for this room")
    parser.add_argument("--timezone", default="America/Sao_Paulo")
    parser.add_argument("--grant", action="append", default=[], help="Supabase user UUID")
    parser.add_argument("--allow-remote", action="store_true")
    args = parser.parse_args()

    uri = os.environ.get("SQLALCHEMY_DATABASE_URI", "")
    if not args.allow_remote and "localhost" not in uri and "127.0.0.1" not in uri:
        sys.exit(f"REFUSING non-local database without --allow-remote: {uri!r}")

    from sqlalchemy import select

    from app import create_app, db
    from app.models.device import Device
    from app.models.room import Room
    from app.models.user_room import UserRoom

    app = create_app()
    with app.app_context():
        room = db.session.execute(select(Room).filter_by(slug=args.slug)).scalar_one_or_none()
        if room is None:
            room = Room(name=args.name, slug=args.slug, timezone=args.timezone)
            db.session.add(room)
            db.session.flush()
            print(f"created room {room.slug!r} (id={room.id})")
        else:
            room.name, room.timezone = args.name, args.timezone
            print(f"room {room.slug!r} already exists (id={room.id}) — updated")

        device = db.session.get(Device, args.device)
        if device is None:
            db.session.add(Device(id=args.device, room_id=room.id))
            print(f"registered device {args.device!r} -> room {room.id}")
        else:
            device.room_id = room.id
            print(f"device {args.device!r} already registered — pointed at room {room.id}")

        for user_id in args.grant:
            existing = db.session.get(UserRoom, (user_id, room.id))
            if existing is None:
                db.session.add(UserRoom(user_id=user_id, room_id=room.id))
                print(f"granted {user_id} access to room {room.id}")
            else:
                print(f"{user_id} already has access to room {room.id}")

        db.session.commit()
    print("done")


if __name__ == "__main__":
    main()
