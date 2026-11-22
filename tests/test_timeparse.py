from datetime import datetime, timedelta, timezone

from botmail.timeparse import parse_since


def test_parse_duration_hours():
    before = datetime.now(timezone.utc)
    cutoff = parse_since("2h")
    after = datetime.now(timezone.utc)
    assert before - timedelta(hours=2, minutes=1) < cutoff < after - timedelta(hours=1, minutes=59)


def test_parse_iso():
    dt = parse_since("2024-01-15T12:00:00+00:00")
    assert dt.year == 2024
    assert dt.month == 1