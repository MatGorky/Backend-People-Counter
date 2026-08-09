"""Parse and store passage events from the device's JSON topic (spec-002).

Every message is raw-logged to data_tracker (audit trail). A passage_event row is
added only when the payload parses, the device is registered, and the message is
not a duplicate delivery. Raw row and event commit atomically.
"""

import ipaddress
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone

from sqlalchemy import select

from app.extensions import db
from app.models.data_tracker import DataTracker
from app.models.device import Device
from app.models.passage_event import PassageEvent

logger = logging.getLogger(__name__)

# The device clock is São Paulo local time mislabeled with a Z suffix
# (docs/current-state.md §6). Brazil has no DST since 2019 — fixed offset.
DEVICE_TZ = timezone(timedelta(hours=-3))
# Beyond this device-vs-server divergence, trust the server clock instead.
MAX_CLOCK_SKEW = timedelta(minutes=30)


@dataclass
class ParsedPassage:
    device_id: str
    occurred_at: datetime  # true UTC
    access_count: int | None
    people_count: int | None
    status_sensor: str | None
    rssi: int | None
    ip_address: str | None
    pulse_ton: int | None
    pulse_toff: int | None
    clock_skew_flagged: bool = False


def _parse_device_time(value) -> datetime | None:
    """'2026-08-7T08:48:17Z' → aware UTC. The Z is a lie; the value is SP wall time.

    strptime is deliberately used for its leniency: the firmware emits non-zero-padded
    day/month (observed in prod), which %d/%m accept.
    """
    if not isinstance(value, str):
        return None
    try:
        naive = datetime.strptime(value.strip(), "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None
    return naive.replace(tzinfo=DEVICE_TZ).astimezone(UTC)


def _to_int(value) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _to_ip(value) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        ipaddress.ip_address(value.strip())
    except ValueError:
        return None
    return value.strip()


def _to_str(value) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def parse_passage(payload: str, received_at: datetime) -> ParsedPassage | None:
    """Returns None when the payload is not a parsable passage message."""
    try:
        data = json.loads(payload)
    except (TypeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None

    device_id = _to_str(data.get("device_id"))
    if device_id is None:
        return None

    occurred_at = _parse_device_time(data.get("time_detected"))
    skewed = False
    if occurred_at is None:
        occurred_at = received_at  # firmware variants without a usable timestamp
    elif abs(occurred_at - received_at) > MAX_CLOCK_SKEW:
        logger.warning(
            "Device %s clock skew (%s vs server %s); using server time",
            device_id,
            occurred_at,
            received_at,
        )
        occurred_at = received_at
        skewed = True

    return ParsedPassage(
        device_id=device_id.strip(),
        occurred_at=occurred_at,
        access_count=_to_int(data.get("access_count")),
        people_count=_to_int(data.get("people_count")),
        status_sensor=_to_str(data.get("status_sensor")),
        rssi=_to_int(data.get("RSSI")),
        ip_address=_to_ip(data.get("ip_address")),
        pulse_ton=_to_int(data.get("pulse_ton")),
        pulse_toff=_to_int(data.get("pulse_toff")),
        clock_skew_flagged=skewed,
    )


def last_accepted_access(device_id: str) -> int | None:
    return db.session.execute(
        select(PassageEvent.access_count)
        .filter(
            PassageEvent.device_id == device_id,
            PassageEvent.access_count.is_not(None),
        )
        .order_by(PassageEvent.id.desc())
        .limit(1)
    ).scalar()


def is_duplicate(access_count: int | None, last_access: int | None) -> bool:
    """Same counter value as the last accepted event = same physical passage
    delivered again. A LOWER value is a device reset (new era) — not a duplicate."""
    if access_count is None or last_access is None:
        return False
    return access_count == last_access


def ingest_json_message(topic: str, payload: str) -> PassageEvent | None:
    """Runs inside an app context. Returns the stored event, or None if raw-only."""
    received_at = datetime.now(UTC)
    raw = DataTracker(topic=topic, payload=payload.replace("\n", "").replace("\r", ""))
    db.session.add(raw)
    db.session.flush()

    parsed = parse_passage(payload, received_at)
    if parsed is None:
        logger.warning("Unparsable payload on JSON topic; raw-logged only (raw_id=%s)", raw.id)
        db.session.commit()
        return None

    device = db.session.get(Device, parsed.device_id)
    if device is None:
        logger.warning(
            "Unregistered device %r; raw-logged only (raw_id=%s)", parsed.device_id, raw.id
        )
        db.session.commit()
        return None

    device.last_seen = received_at
    if device.first_seen is None:
        device.first_seen = received_at

    if is_duplicate(parsed.access_count, last_accepted_access(parsed.device_id)):
        logger.info(
            "Duplicate delivery (device=%s, access_count=%s); raw-logged only",
            parsed.device_id,
            parsed.access_count,
        )
        db.session.commit()
        return None

    event = PassageEvent(
        device_id=parsed.device_id,
        room_id=device.room_id,
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
    db.session.add(event)
    db.session.commit()
    return event
