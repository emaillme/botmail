"""MIME parsing, HTML-to-text, link extraction, reply headers."""

from __future__ import annotations

import re
from email import policy
from email.header import decode_header, make_header
from email.message import EmailMessage, Message
from email.parser import BytesParser
from html.parser import HTMLParser

_URL_RE = re.compile(r"https?://[^\s<>\"')}\]]+", re.IGNORECASE)


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []

    def handle_data(self, data: str) -> None:
        self._chunks.append(data)

    def get_text(self) -> str:
        return " ".join(self._chunks)


def parse_raw_mime(data: bytes) -> Message:
    return BytesParser(policy=policy.default).parsebytes(data)


def decode_mime_header(value: str | None) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value


def address_list(msg: Message, header: str) -> list[str]:
    raw = msg.get(header)
    if not raw:
        return []
    from email.utils import getaddresses

    return [addr for _, addr in getaddresses([raw]) if addr]


def message_date(msg: Message) -> str:
    from email.utils import parsedate_to_datetime

    raw = msg.get("Date")
    if not raw:
        return ""
    try:
        dt = parsedate_to_datetime(raw)
        return dt.isoformat()
    except Exception:
        return raw


def html_to_text(html: str) -> str:
    parser = _TextExtractor()
    try:
        parser.feed(html)
        parser.close()
    except Exception:
        return re.sub(r"<[^>]+>", " ", html)
    text = parser.get_text()
    return re.sub(r"\s+", " ", text).strip()


def extract_body_parts(msg: Message) -> tuple[str | None, str | None]:
    """Return (text/plain, text/html) bodies, preferring leaf parts."""
    text: str | None = None
    html: str | None = None

    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_maintype() == "multipart":
                continue
            if part.get_content_disposition() == "attachment":
                continue
            ctype = part.get_content_type()
            try:
                payload = part.get_content()
            except Exception:
                payload = part.get_payload(decode=True)
                if isinstance(payload, bytes):
                    charset = part.get_content_charset() or "utf-8"
                    payload = payload.decode(charset, errors="replace")
            if not isinstance(payload, str):
                continue
            if ctype == "text/plain" and text is None:
                text = payload
            elif ctype == "text/html" and html is None:
                html = payload
    else:
        ctype = msg.get_content_type()
        try:
            payload = msg.get_content()
        except Exception:
            raw = msg.get_payload(decode=True)
            if raw is None:
                payload = ""
            elif isinstance(raw, bytes):
                charset = msg.get_content_charset() or "utf-8"
                payload = raw.decode(charset, errors="replace")
            else:
                payload = str(raw)
        if ctype == "text/html":
            html = payload if isinstance(payload, str) else str(payload)
        else:
            text = payload if isinstance(payload, str) else str(payload)

    return text, html


def best_text_body(msg: Message, *, prefer_html: bool = False) -> str:
    text, html = extract_body_parts(msg)
    if prefer_html and html:
        return html_to_text(html) if not text else text
    if text:
        return text.strip()
    if html:
        return html_to_text(html)
    return ""


def list_attachments(msg: Message) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for part in msg.walk():
        disp = part.get_content_disposition()
        if disp not in ("attachment", "inline"):
            continue
        filename = part.get_filename()
        if not filename:
            continue
        out.append(
            {
                "filename": decode_mime_header(filename),
                "content_type": part.get_content_type(),
            }
        )
    return out


def extract_links(text: str) -> list[str]:
    seen: set[str] = set()
    links: list[str] = []
    for url in _URL_RE.findall(text):
        url = url.rstrip(".,;")
        if url not in seen:
            seen.add(url)
            links.append(url)
    return links


def authentication_results(msg: Message) -> str:
    for key in msg.keys():
        if key.lower() == "authentication-results":
            return msg[key] or ""
    return ""


def summary_from_bytes(data: bytes) -> dict[str, str]:
    msg = parse_raw_mime(data)
    return {
        "date": message_date(msg),
        "from": ", ".join(address_list(msg, "From")) or decode_mime_header(msg.get("From")),
        "to": ", ".join(address_list(msg, "To")) or decode_mime_header(msg.get("To")),
        "subject": decode_mime_header(msg.get("Subject")),
    }


def build_reply_headers(original: Message, reply_from: str) -> EmailMessage:
    """Prepare a reply shell with threading headers and Re: subject."""
    reply = EmailMessage()
    reply["From"] = reply_from
    orig_msg_id = original.get("Message-ID") or original.get("Message-Id")
    refs = original.get("References", "")
    if orig_msg_id:
        reply["In-Reply-To"] = orig_msg_id
        combined = f"{refs} {orig_msg_id}".strip() if refs else orig_msg_id
        reply["References"] = combined
    subj = decode_mime_header(original.get("Subject"))
    if subj.lower().startswith("re:"):
        reply["Subject"] = subj
    else:
        reply["Subject"] = f"Re: {subj}" if subj else "Re:"
    return reply


def recipient_for_reply(original: Message) -> str:
    """Address this bot received mail at (first To/Cc/Delivered-To)."""
    for header in ("Delivered-To", "X-Original-To", "To", "Cc"):
        addrs = address_list(original, header)
        if addrs:
            return addrs[0]
    return ""


def addresses_match(haystack: str, needle: str) -> bool:
    needle_l = needle.lower()
    return needle_l in haystack.lower()


def subject_contains(subject: str, fragment: str) -> bool:
    return fragment.lower() in (subject or "").lower()


def iter_header_bytes(data: bytes, max_bytes: int = 262144) -> Message:
    """Parse headers from a prefix of raw MIME (for list)."""
    chunk = data[:max_bytes]
    return BytesParser(policy=policy.default).parsebytes(chunk)