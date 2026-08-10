"""API v2 (spec-002/003): passage aggregates from passage_event, room-scoped."""

from datetime import datetime

from flask import g, request
from flask_restx import Namespace, Resource, abort
from sqlalchemy import func, select

from app.extensions import db
from app.models.device import Device
from app.models.room import Room
from app.models.user_room import UserRoom
from app.services import passages_v2
from app.utils.auth import require_auth
from app.utils.authz import require_admin, require_room_access

me_ns = Namespace("me", path="/api/v2/me", description="Caller-scoped resources")
rooms_ns = Namespace("rooms", path="/api/v2/rooms", description="Room-scoped passages + admin")

MAX_RANGE_DAYS = 400


def _room_payload(room, last_seen=None):
    return {
        "id": room.id,
        "name": room.name,
        "slug": room.slug,
        "timezone": room.timezone,
        "device_last_seen": last_seen.isoformat() if last_seen else None,
    }


@me_ns.route("/rooms")
class MyRooms(Resource):
    @require_auth()
    def get(self):
        from app.utils.authz import is_admin

        last_seen = (
            select(Device.room_id, func.max(Device.last_seen).label("last_seen"))
            .group_by(Device.room_id)
            .subquery()
        )
        query = (
            select(Room, last_seen.c.last_seen)
            .outerjoin(last_seen, last_seen.c.room_id == Room.id)
            .order_by(Room.name)
        )
        if not is_admin():
            query = query.join(
                UserRoom,
                (UserRoom.room_id == Room.id) & (UserRoom.user_id == g.user["id"]),
            )
        rows = db.session.execute(query).all()
        return [_room_payload(room, seen) for room, seen in rows]


def _parse_date(value: str, fmt: str, label: str):
    try:
        return datetime.strptime(value or "", fmt)
    except ValueError:
        abort(400, f"Invalid or missing {label}")


@rooms_ns.route("/<int:room_id>/passages/daily")
class DailyPassages(Resource):
    @require_auth()
    @require_room_access
    def get(self, room_id):
        day = _parse_date(request.args.get("date"), "%Y-%m-%d", "date (YYYY-MM-DD)").date()
        return passages_v2.daily(g.room, day)


@rooms_ns.route("/<int:room_id>/passages/monthly")
class MonthlyPassages(Resource):
    @require_auth()
    @require_room_access
    def get(self, room_id):
        month = _parse_date(request.args.get("month"), "%Y-%m", "month (YYYY-MM)")
        return passages_v2.monthly(g.room, month.year, month.month)


@rooms_ns.route("/<int:room_id>/passages/range")
class RangePassages(Resource):
    @require_auth()
    @require_room_access
    def get(self, room_id):
        start = _parse_date(request.args.get("start"), "%Y-%m-%d", "start (YYYY-MM-DD)").date()
        end = _parse_date(request.args.get("end"), "%Y-%m-%d", "end (YYYY-MM-DD)").date()
        if start > end:
            abort(400, "start must be <= end")
        if (end - start).days > MAX_RANGE_DAYS:
            abort(400, f"Range too large (max {MAX_RANGE_DAYS} days)")
        return passages_v2.date_range(g.room, start, end)


@rooms_ns.route("/<int:room_id>/passages/yearly")
class YearlyPassages(Resource):
    @require_auth()
    @require_room_access
    def get(self, room_id):
        year = _parse_date(request.args.get("year"), "%Y", "year (YYYY)").year
        resolution = request.args.get("resolution", "monthly")
        if resolution not in ("monthly", "daily"):
            abort(400, "resolution must be 'monthly' or 'daily'")
        return passages_v2.yearly(g.room, year, resolution)


@rooms_ns.route("/<int:room_id>/reports/passages.pdf")
class PassagesReportPdf(Resource):
    @require_auth()
    @require_room_access
    def get(self, room_id):
        from flask import Response

        from app.services import pdf_report, reports

        start = _parse_date(request.args.get("start"), "%Y-%m-%d", "start (YYYY-MM-DD)").date()
        end = _parse_date(request.args.get("end"), "%Y-%m-%d", "end (YYYY-MM-DD)").date()
        if start > end:
            abort(400, "start must be <= end")
        if (end - start).days > MAX_RANGE_DAYS:
            abort(400, f"Range too large (max {MAX_RANGE_DAYS} days)")

        report = reports.range_report(g.room, start, end)
        pdf_bytes = pdf_report.build_pdf(report)
        filename = f"relatorio-{g.room.slug}-{report['start']}-{report['end']}.pdf"
        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )


@rooms_ns.route("")
class RoomCollection(Resource):
    @require_auth()
    @require_admin
    def post(self):
        body = request.get_json(silent=True) or {}
        name, slug = body.get("name"), body.get("slug")
        if not name or not slug:
            abort(400, "name and slug are required")
        if db.session.execute(select(Room).filter_by(slug=slug)).scalar_one_or_none():
            abort(409, "slug already exists")
        room = Room(name=name, slug=slug, timezone=body.get("timezone", "America/Sao_Paulo"))
        db.session.add(room)
        db.session.commit()
        return _room_payload(room), 201


@rooms_ns.route("/<int:room_id>/devices")
class RoomDevices(Resource):
    @require_auth()
    @require_admin
    def post(self, room_id):
        room = db.session.get(Room, room_id)
        if room is None:
            abort(404, "Room not found")
        body = request.get_json(silent=True) or {}
        device_id = body.get("device_id")
        if not device_id:
            abort(400, "device_id is required")
        device = db.session.get(Device, device_id)
        if device is None:
            device = Device(id=device_id, room_id=room.id, description=body.get("description"))
            db.session.add(device)
        else:
            device.room_id = room.id
            device.description = body.get("description", device.description)
        db.session.commit()
        return {"device_id": device_id, "room_id": room.id}, 201


@rooms_ns.route("/<int:room_id>/users")
class RoomUsers(Resource):
    @require_auth()
    @require_admin
    def get(self, room_id):
        if db.session.get(Room, room_id) is None:
            abort(404, "Room not found")
        grants = db.session.execute(select(UserRoom).filter_by(room_id=room_id)).scalars()
        return [
            {"user_id": str(grant.user_id), "granted_at": grant.granted_at.isoformat()}
            for grant in grants
        ]


@rooms_ns.route("/<int:room_id>/users/<string:user_id>")
class RoomUserGrant(Resource):
    @require_auth()
    @require_admin
    def put(self, room_id, user_id):
        if db.session.get(Room, room_id) is None:
            abort(404, "Room not found")
        if db.session.get(UserRoom, (user_id, room_id)) is None:
            db.session.add(UserRoom(user_id=user_id, room_id=room_id, granted_by=g.user["id"]))
            db.session.commit()
        return {"user_id": user_id, "room_id": room_id}, 201

    @require_auth()
    @require_admin
    def delete(self, room_id, user_id):
        grant = db.session.get(UserRoom, (user_id, room_id))
        if grant is None:
            abort(404, "Grant not found")
        db.session.delete(grant)
        db.session.commit()
        return "", 204
