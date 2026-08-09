"""Room-level authorization (spec-003). Runs AFTER require_auth (needs g.user)."""

from functools import wraps

from flask import g
from flask_restx import abort

from app.extensions import db
from app.models.room import Room
from app.models.user_room import UserRoom


def is_admin() -> bool:
    return g.user.get("app_role") == "admin"


def has_room_access(user_id: str, room_id: int) -> bool:
    return db.session.get(UserRoom, (user_id, room_id)) is not None


def require_room_access(f):
    """404 (not 403) when the room doesn't exist OR the caller lacks a grant —
    room existence is not leaked to users without access."""

    @wraps(f)
    def wrapper(*args, room_id: int, **kwargs):
        room = db.session.get(Room, room_id)
        if room is None or (not is_admin() and not has_room_access(g.user["id"], room_id)):
            abort(404, "Room not found")
        g.room = room
        return f(*args, room_id=room_id, **kwargs)

    return wrapper


def require_admin(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not is_admin():
            abort(403, "Admin role required")
        return f(*args, **kwargs)

    return wrapper
