from email.message import EmailMessage
from pathlib import Path

import boto3
import pytest
from moto import mock_aws

from botmail.config import BotConfig, load_config
from botmail.state import ReadState
from botmail.store import MailStore
from botmail.wait import message_matches, wait_for_message


def _sample_raw(from_addr: str, to_addr: str, subject: str, body: str) -> bytes:
    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg["Delivered-To"] = to_addr
    msg.set_content(body)
    return msg.as_bytes()


@pytest.fixture
def bot_config(tmp_path, monkeypatch):
    env = tmp_path / "agent.env"
    env.write_text(
        "AWS_ACCESS_KEY_ID=testing\n"
        "AWS_SECRET_ACCESS_KEY=testing\n"
        "BOTMAIL_BUCKET=test-botmail\n"
        "BOTMAIL_PREFIX=example.com/\n"
        "BOTMAIL_DOMAIN=example.com\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    (tmp_path / ".local" / "state" / "botmail" / "agent").mkdir(parents=True)
    return load_config(env_path=env)


@mock_aws
def test_list_and_filter(bot_config: BotConfig):
    s3 = boto3.client("s3", region_name=bot_config.region)
    s3.create_bucket(Bucket=bot_config.bucket)
    key = f"{bot_config.prefix}msg-1"
    raw = _sample_raw("ext@example.com", "agent@example.com", "Hello", "body")
    s3.put_object(Bucket=bot_config.bucket, Key=key, Body=raw)

    store = MailStore(bot_config)
    rows = store.filter_summaries(to_addr="agent@example.com", limit=10)
    assert len(rows) == 1
    assert rows[0].subject == "Hello"
    assert rows[0].id == "msg-1"

    empty = store.filter_summaries(to_addr="other@example.com", limit=10)
    assert empty == []


@mock_aws
def test_wait_for_message(bot_config: BotConfig):
    s3 = boto3.client("s3", region_name=bot_config.region)
    s3.create_bucket(Bucket=bot_config.bucket)
    key = f"{bot_config.prefix}wait-1"
    raw = _sample_raw("n@example.com", "signup@example.com", "Confirm email", "https://example.com/y")
    s3.put_object(Bucket=bot_config.bucket, Key=key, Body=raw)
    store = MailStore(bot_config)
    mid = wait_for_message(
        store,
        to_addr="signup@example.com",
        subject_contains="Confirm",
        timeout_sec=5,
        poll_interval=0.2,
    )
    assert mid == "wait-1"


def test_message_matches_helpers():
    raw = _sample_raw("a@b.com", "z@example.com", "Hello world", "x")
    from botmail import mimeutil

    msg = mimeutil.parse_raw_mime(raw)
    assert message_matches(msg, to_addr="z@example.com", subject_contains="world")
    assert not message_matches(msg, to_addr="other@example.com", subject_contains=None)


def test_read_state(tmp_path):
    path = tmp_path / "read.json"
    st = ReadState(path)
    assert st.unread_only("m1")
    st.mark_read("m1")
    assert st.is_read("m1")
    st2 = ReadState(path)
    assert st2.is_read("m1")