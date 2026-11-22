"""S3-backed mailbox."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Callable

from botmail import mimeutil

if TYPE_CHECKING:
    from botmail.config import BotConfig


@dataclass
class MailRef:
    id: str
    key: str
    last_modified: datetime
    size: int


@dataclass
class MailSummary:
    id: str
    date: str
    from_addr: str
    to_addr: str
    subject: str
    last_modified: datetime


def _norm_dt(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class MailStore:
    def __init__(self, config: BotConfig) -> None:
        self._config = config
        session = config.boto_session()
        self._s3 = session.client("s3", region_name=config.region)
        self._ses = session.client("ses", region_name=config.region)

    @property
    def prefix(self) -> str:
        return self._config.prefix

    def list_refs(self) -> list[MailRef]:
        refs: list[MailRef] = []
        paginator = self._s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self._config.bucket, Prefix=self._config.prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if key.endswith("/"):
                    continue
                mid = self.id_from_key(key)
                refs.append(
                    MailRef(
                        id=mid,
                        key=key,
                        last_modified=_norm_dt(obj["LastModified"]),
                        size=int(obj["Size"]),
                    )
                )
        refs.sort(key=lambda r: r.last_modified, reverse=True)
        return refs

    def id_from_key(self, key: str) -> str:
        if key.startswith(self._config.prefix):
            return key[len(self._config.prefix) :]
        return key

    def key_from_id(self, message_id: str) -> str:
        if "/" in message_id or message_id.startswith(self._config.prefix):
            return message_id
        return f"{self._config.prefix}{message_id}"

    def fetch_bytes(self, message_id: str) -> bytes:
        key = self.key_from_id(message_id)
        resp = self._s3.get_object(Bucket=self._config.bucket, Key=key)
        return resp["Body"].read()

    def fetch_message(self, message_id: str):
        return mimeutil.parse_raw_mime(self.fetch_bytes(message_id))

    def summarize(
        self,
        ref: MailRef,
        *,
        fetch: Callable[[str], bytes] | None = None,
    ) -> MailSummary:
        getter = fetch or self.fetch_bytes
        try:
            data = getter(ref.id)
            if len(data) > 512 * 1024:
                msg = mimeutil.iter_header_bytes(data)
                date = mimeutil.message_date(msg)
                from_hdr = mimeutil.decode_mime_header(msg.get("From"))
                from_a = ", ".join(mimeutil.address_list(msg, "From")) or from_hdr
                to_a = ", ".join(mimeutil.address_list(msg, "To")) or mimeutil.decode_mime_header(
                    msg.get("To")
                )
                subj = mimeutil.decode_mime_header(msg.get("Subject"))
            else:
                meta = mimeutil.summary_from_bytes(data)
                date, from_a, to_a, subj = meta["date"], meta["from"], meta["to"], meta["subject"]
        except Exception:
            date, from_a, to_a, subj = "", "", "", "(parse error)"
        if not date:
            date = ref.last_modified.isoformat()
        return MailSummary(
            id=ref.id,
            date=date,
            from_addr=from_a,
            to_addr=to_a,
            subject=subj,
            last_modified=ref.last_modified,
        )

    def filter_summaries(
        self,
        *,
        to_addr: str | None = None,
        since: datetime | None = None,
        limit: int | None = None,
        unread_only: bool = False,
        is_read: Callable[[str], bool] | None = None,
    ) -> list[MailSummary]:
        out: list[MailSummary] = []
        for ref in self.list_refs():
            if since and ref.last_modified < since:
                continue
            summary = self.summarize(ref)
            if to_addr:
                if mimeutil.addresses_match(summary.to_addr, to_addr):
                    pass
                else:
                    msg = self.fetch_message(ref.id)
                    tos = mimeutil.address_list(msg, "To")
                    ccs = mimeutil.address_list(msg, "Cc")
                    delivered = mimeutil.address_list(msg, "Delivered-To")
                    all_to = ", ".join(tos + ccs + delivered)
                    if not mimeutil.addresses_match(all_to, to_addr):
                        continue
            if unread_only and is_read and is_read(ref.id):
                continue
            out.append(summary)
            if limit and len(out) >= limit:
                break
        return out

    def send_raw(self, raw: bytes, *, source: str, destinations: list[str]) -> str:
        resp = self._ses.send_raw_email(
            Source=source,
            Destinations=destinations,
            RawMessage={"Data": raw},
        )
        return resp.get("MessageId", "")

    def save_attachments(self, message_id: str, dest_dir: str) -> list[str]:
        from pathlib import Path

        msg = self.fetch_message(message_id)
        saved: list[str] = []
        dest = Path(dest_dir)
        dest.mkdir(parents=True, exist_ok=True)
        for part in msg.walk():
            if part.get_content_disposition() not in ("attachment", "inline"):
                continue
            filename = part.get_filename()
            if not filename:
                continue
            filename = mimeutil.decode_mime_header(filename)
            path = dest / filename
            payload = part.get_payload(decode=True)
            if payload is None:
                continue
            path.write_bytes(payload)
            saved.append(str(path))
        return saved