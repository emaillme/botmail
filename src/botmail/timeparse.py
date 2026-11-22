"""Parse --since durations and ISO timestamps."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

_DURATION = re.compile(r"^(\d+)([hdm])$", re.IGNORECASE)


def parse_since(value: str) -> datetime:
    """Return UTC cutoff: messages at or after this time match --since."""
    value = value.strip()
    m = _DURATION.match(value)
    if m:
        n = int(m.group(1))
        unit = m.group(2).lower()
        if unit == "h":
            delta = timedelta(hours=n)
        elif unit == "d":
            delta = timedelta(days=n)
        elif unit == "m":
            delta = timedelta(minutes=n)
        else:
            raise ValueError(unit)
        return datetime.now(timezone.utc) - delta

    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(value)
    except ValueError as exc:
        raise SystemExit(
            f"Invalid --since {value!r}; use 1h, 2d, 30m, or ISO-8601."
        ) from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)