"""Build outbound MIME messages."""

from __future__ import annotations

from email.message import EmailMessage
from pathlib import Path

from botmail import mimeutil


def build_message(
    *,
    from_addr: str,
    to_addrs: list[str],
    subject: str,
    body_text: str | None = None,
    body_html: str | None = None,
    cc_addrs: list[str] | None = None,
    attach_paths: list[str] | None = None,
    extra_headers: dict[str, str] | None = None,
) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = ", ".join(to_addrs)
    if cc_addrs:
        msg["Cc"] = ", ".join(cc_addrs)
    msg["Subject"] = subject
    if extra_headers:
        for k, v in extra_headers.items():
            msg[k] = v

    if body_html and body_text:
        msg.set_content(body_text)
        msg.add_alternative(body_html, subtype="html")
    elif body_html:
        msg.set_content(mimeutil.html_to_text(body_html), subtype="plain")
        msg.add_alternative(body_html, subtype="html")
    elif body_text:
        msg.set_content(body_text)
    else:
        msg.set_content("")

    for path in attach_paths or []:
        p = Path(path)
        data = p.read_bytes()
        msg.add_attachment(
            data,
            maintype="application",
            subtype="octet-stream",
            filename=p.name,
        )

    return msg


def message_as_bytes(msg: EmailMessage) -> bytes:
    return msg.as_bytes()


def all_destinations(
    to_addrs: list[str], cc_addrs: list[str] | None = None, bcc_addrs: list[str] | None = None
) -> list[str]:
    dest: list[str] = []
    for group in (to_addrs, cc_addrs or [], bcc_addrs or []):
        for a in group:
            if a and a not in dest:
                dest.append(a)
    return dest