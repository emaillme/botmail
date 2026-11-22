"""botmail command-line interface."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from botmail import compose, mimeutil
from botmail.config import load_config
from botmail.state import ReadState
from botmail.store import MailStore
from botmail.timeparse import parse_since
from botmail.wait import wait_for_message


def _add_global_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--env",
        type=Path,
        help="Path to bot env file (default: single file in ~/.config/botmail/)",
    )
    parser.add_argument("--domain", help="Override SES domain / bot domain")
    parser.add_argument("--prefix", help="Override S3 key prefix")
    parser.add_argument("--bucket", help="Override S3 bucket")
    parser.add_argument("--region", help="Override AWS region")
    parser.add_argument("--profile", help="AWS profile name (or BOTMAIL_PROFILE)")
    parser.add_argument(
        "--role-arn",
        dest="role_arn",
        help="IAM role to assume (or BOTMAIL_ROLE_ARN)",
    )
    parser.add_argument(
        "--role-session-name",
        dest="role_session_name",
        help="STS session name when assuming a role",
    )
    parser.add_argument(
        "--external-id",
        dest="external_id",
        help="External ID for role assumption (or BOTMAIL_EXTERNAL_ID)",
    )
    parser.add_argument("--json", action="store_true", dest="as_json", help="JSON output")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="botmail", description="CLI email for AI agents")
    _add_global_flags(parser)
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="List inbound messages")
    p_list.add_argument("--to", dest="to_addr", help="Filter by recipient address")
    p_list.add_argument("--since", help="Only messages after duration (1h, 2d) or ISO time")
    p_list.add_argument("--limit", type=int, default=50)
    p_list.add_argument("--unread", action="store_true", help="Only unread messages")

    p_read = sub.add_parser("read", help="Read a message by id")
    p_read.add_argument("message_id")
    p_read.add_argument("--raw", action="store_true", help="Print raw MIME")
    p_read.add_argument("--html", action="store_true", help="Prefer HTML body as text source")

    p_save = sub.add_parser("save-attachments", help="Save attachments to a directory")
    p_save.add_argument("message_id")
    p_save.add_argument("directory", type=Path)

    p_wait = sub.add_parser("wait", help="Wait for a matching inbound message")
    p_wait.add_argument("--to", dest="to_addr", required=True)
    p_wait.add_argument("--subject-contains", dest="subject_contains")
    p_wait.add_argument("--timeout", type=int, default=300)

    p_links = sub.add_parser("links", help="Print URLs from message body")
    p_links.add_argument("message_id")

    p_send = sub.add_parser("send", help="Send outbound mail via SES")
    p_send.add_argument("--from", dest="from_addr", required=True)
    p_send.add_argument("--to", dest="to_addr", required=True)
    p_send.add_argument("--cc", action="append", default=[])
    p_send.add_argument("--subject", required=True)
    body = p_send.add_mutually_exclusive_group(required=True)
    body.add_argument("--body")
    body.add_argument("--body-file", type=Path)
    p_send.add_argument("--html-file", type=Path)
    p_send.add_argument("--attach", action="append", default=[])

    p_reply = sub.add_parser("reply", help="Reply to an inbound message")
    p_reply.add_argument("message_id")
    body_r = p_reply.add_mutually_exclusive_group(required=True)
    body_r.add_argument("--body")
    body_r.add_argument("--body-file", type=Path)
    p_reply.add_argument("--html-file", type=Path)
    p_reply.add_argument("--attach", action="append", default=[])

    return parser


def _print_table(rows: list[dict[str, str]]) -> None:
    if not rows:
        print("(no messages)")
        return
    cols = ["id", "date", "from", "to", "subject"]
    widths = {c: len(c) for c in cols}
    for row in rows:
        for c in cols:
            widths[c] = max(widths[c], len(str(row.get(c, ""))[:80]))
    fmt = "  ".join(f"{{:{widths[c]}}}" for c in cols)
    print(fmt.format(*cols))
    print(fmt.format(*["-" * widths[c] for c in cols]))
    for row in rows:
        print(fmt.format(*[str(row.get(c, ""))[:80] for c in cols]))


def _read_body_arg(body: str | None, body_file: Path | None) -> str:
    if body is not None:
        return body
    assert body_file is not None
    return body_file.read_text(encoding="utf-8")


def cmd_list(args: argparse.Namespace, store: MailStore, state: ReadState) -> int:
    since = parse_since(args.since) if args.since else None

    def is_read(mid: str) -> bool:
        return state.is_read(mid)

    summaries = store.filter_summaries(
        to_addr=args.to_addr,
        since=since,
        limit=args.limit,
        unread_only=args.unread,
        is_read=is_read if args.unread else None,
    )
    rows = [
        {
            "id": s.id,
            "date": s.date,
            "from": s.from_addr,
            "to": s.to_addr,
            "subject": s.subject,
            "unread": not state.is_read(s.id),
        }
        for s in summaries
    ]
    if args.as_json:
        print(json.dumps(rows, indent=2))
    else:
        _print_table(rows)
    return 0


def cmd_read(args: argparse.Namespace, store: MailStore, state: ReadState) -> int:
    raw = store.fetch_bytes(args.message_id)
    if args.raw:
        sys.stdout.buffer.write(raw)
        state.mark_read(args.message_id)
        return 0
    msg = mimeutil.parse_raw_mime(raw)
    state.mark_read(args.message_id)
    body = mimeutil.best_text_body(msg, prefer_html=args.html)
    attachments = mimeutil.list_attachments(msg)
    auth = mimeutil.authentication_results(msg)
    payload = {
        "id": args.message_id,
        "headers": {
            "from": mimeutil.decode_mime_header(msg.get("From")),
            "to": mimeutil.decode_mime_header(msg.get("To")),
            "subject": mimeutil.decode_mime_header(msg.get("Subject")),
            "date": mimeutil.message_date(msg),
            "message_id": msg.get("Message-ID") or msg.get("Message-Id"),
        },
        "body": body,
        "attachments": attachments,
        "authentication_results": auth,
    }
    if args.as_json:
        print(json.dumps(payload, indent=2))
        return 0
    print(f"From: {payload['headers']['from']}")
    print(f"To: {payload['headers']['to']}")
    print(f"Date: {payload['headers']['date']}")
    print(f"Subject: {payload['headers']['subject']}")
    if auth:
        print(f"Authentication-Results: {auth}")
    print()
    print(body)
    if attachments:
        print()
        print("Attachments:")
        for att in attachments:
            print(f"  - {att['filename']} ({att['content_type']})")
    return 0


def cmd_save_attachments(args: argparse.Namespace, store: MailStore, state: ReadState) -> int:
    saved = store.save_attachments(args.message_id, str(args.directory))
    state.mark_read(args.message_id)
    if args.as_json:
        print(json.dumps({"paths": saved}))
    else:
        for path in saved:
            print(path)
    return 0


def cmd_wait(args: argparse.Namespace, store: MailStore, state: ReadState) -> int:
    mid = wait_for_message(
        store,
        to_addr=args.to_addr,
        subject_contains=args.subject_contains,
        timeout_sec=float(args.timeout),
    )
    if args.as_json:
        print(json.dumps({"id": mid}))
    else:
        print(mid)
    return 0


def cmd_links(args: argparse.Namespace, store: MailStore, state: ReadState) -> int:
    msg = store.fetch_message(args.message_id)
    text = mimeutil.best_text_body(msg)
    _, html = mimeutil.extract_body_parts(msg)
    if html:
        text = f"{text}\n{html}"
    links = mimeutil.extract_links(text)
    state.mark_read(args.message_id)
    if args.as_json:
        print(json.dumps({"links": links}))
    else:
        for url in links:
            print(url)
    return 0


def cmd_send(args: argparse.Namespace, store: MailStore, config) -> int:
    body_text = _read_body_arg(args.body, args.body_file)
    body_html = args.html_file.read_text(encoding="utf-8") if args.html_file else None
    to_list = [a.strip() for a in args.to_addr.split(",") if a.strip()]
    cc_list = [a.strip() for a in args.cc if a.strip()]
    if not args.from_addr.endswith(f"@{config.domain}"):
        raise SystemExit(f"--from must be an address at {config.domain}")
    msg = compose.build_message(
        from_addr=args.from_addr,
        to_addrs=to_list,
        cc_addrs=cc_list,
        subject=args.subject,
        body_text=body_text,
        body_html=body_html,
        attach_paths=args.attach,
    )
    dest = compose.all_destinations(to_list, cc_list)
    mid = store.send_raw(compose.message_as_bytes(msg), source=args.from_addr, destinations=dest)
    if args.as_json:
        print(json.dumps({"message_id": mid}))
    else:
        print(mid)
    return 0


def cmd_reply(args: argparse.Namespace, store: MailStore, config, state: ReadState) -> int:
    original = store.fetch_message(args.message_id)
    reply_from = mimeutil.recipient_for_reply(original)
    if not reply_from:
        raise SystemExit("Could not determine which address received this message.")
    if not reply_from.endswith(f"@{config.domain}"):
        raise SystemExit(f"Reply From must be at {config.domain}; got {reply_from}")
    body_text = _read_body_arg(args.body, args.body_file)
    body_html = args.html_file.read_text(encoding="utf-8") if args.html_file else None
    shell = mimeutil.build_reply_headers(original, reply_from)
    to_addrs = mimeutil.address_list(original, "From")
    if not to_addrs:
        raise SystemExit("Original message has no From address.")
    msg = compose.build_message(
        from_addr=reply_from,
        to_addrs=to_addrs,
        subject=shell["Subject"],
        body_text=body_text,
        body_html=body_html,
        attach_paths=args.attach,
        extra_headers={k: shell[k] for k in ("In-Reply-To", "References") if k in shell},
    )
    dest = compose.all_destinations(to_addrs)
    mid = store.send_raw(compose.message_as_bytes(msg), source=reply_from, destinations=dest)
    state.mark_read(args.message_id)
    if args.as_json:
        print(json.dumps({"message_id": mid, "in_reply_to": args.message_id}))
    else:
        print(mid)
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    parser = _build_parser()
    args = parser.parse_args(argv)
    config = load_config(
        env_path=args.env,
        domain_override=args.domain,
        prefix_override=args.prefix,
        bucket_override=args.bucket,
        region_override=args.region,
        profile_override=args.profile,
        role_arn_override=args.role_arn,
        role_session_name_override=args.role_session_name,
        external_id_override=args.external_id,
    )
    state = ReadState(config.state_dir / "read.json")
    store = MailStore(config)

    handlers = {
        "list": lambda: cmd_list(args, store, state),
        "read": lambda: cmd_read(args, store, state),
        "save-attachments": lambda: cmd_save_attachments(args, store, state),
        "wait": lambda: cmd_wait(args, store, state),
        "links": lambda: cmd_links(args, store, state),
        "send": lambda: cmd_send(args, store, config),
        "reply": lambda: cmd_reply(args, store, config, state),
    }
    return handlers[args.command]()


if __name__ == "__main__":
    raise SystemExit(main())