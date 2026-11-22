"""Poll S3 until a matching inbound message appears."""

from __future__ import annotations

import time
from typing import Callable

from botmail import mimeutil
from botmail.store import MailStore


def message_matches(
    msg,
    *,
    to_addr: str,
    subject_contains: str | None,
) -> bool:
    tos = mimeutil.address_list(msg, "To")
    ccs = mimeutil.address_list(msg, "Cc")
    delivered = mimeutil.address_list(msg, "Delivered-To")
    all_recipients = ", ".join(tos + ccs + delivered)
    if not mimeutil.addresses_match(all_recipients, to_addr):
        return False
    subj = mimeutil.decode_mime_header(msg.get("Subject"))
    if subject_contains and not mimeutil.subject_contains(subj, subject_contains):
        return False
    return True


def wait_for_message(
    store: MailStore,
    *,
    to_addr: str,
    subject_contains: str | None = None,
    timeout_sec: float = 300.0,
    poll_interval: float = 3.0,
    is_read: Callable[[str], bool] | None = None,
) -> str:
    """Return message id. Raises SystemExit on timeout."""
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        for ref in store.list_refs():
            try:
                msg = store.fetch_message(ref.id)
            except Exception:
                continue
            if not message_matches(msg, to_addr=to_addr, subject_contains=subject_contains):
                continue
            if is_read and is_read(ref.id):
                continue
            return ref.id
        time.sleep(poll_interval)
    raise SystemExit(f"Timeout after {int(timeout_sec)}s waiting for mail to {to_addr}.")