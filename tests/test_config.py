from pathlib import Path

import pytest

from botmail.config import DEFAULT_BUCKET, load_config


def test_load_env_file_with_keys(tmp_path, monkeypatch):
    env = tmp_path / "agent.env"
    env.write_text(
        "AWS_ACCESS_KEY_ID=AKIA_TEST\n"
        "AWS_SECRET_ACCESS_KEY=secret\n"
        "BOTMAIL_DOMAIN=example.com\n"
        "BOTMAIL_PREFIX=example.com/\n"
        "BOTMAIL_BUCKET=my-botmail-bucket\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    (tmp_path / ".local" / "state" / "botmail" / "agent").mkdir(parents=True)
    cfg = load_config(env_path=env)
    assert cfg.bot_name == "agent"
    assert cfg.domain == "example.com"
    assert cfg.prefix == "example.com/"
    assert cfg.bucket == "my-botmail-bucket"
    assert cfg.access_key_id == "AKIA_TEST"
    assert cfg.secret_access_key == "secret"


def test_load_env_file_without_keys(tmp_path, monkeypatch):
    env = tmp_path / "agent.env"
    env.write_text(
        "BOTMAIL_DOMAIN=example.com\n"
        "BOTMAIL_PREFIX=example.com/\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    cfg = load_config(env_path=env)
    assert cfg.access_key_id is None
    assert cfg.secret_access_key is None
    assert cfg.domain == "example.com"


def test_domain_from_filename_and_env_vars(tmp_path, monkeypatch):
    env = tmp_path / "custom.env"
    env.write_text(
        "AWS_ACCESS_KEY_ID=AKIA_TEST\n"
        "AWS_SECRET_ACCESS_KEY=secret\n"
        "BOTMAIL_DOMAIN=example.com\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    cfg = load_config(env_path=env)
    assert cfg.domain == "example.com"
    assert cfg.prefix == "example.com/"


def test_flags_without_env_file(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    cfg = load_config(
        env_path=None,
        domain_override="example.com",
        prefix_override="example.com/",
        bucket_override="my-botmail-bucket",
        region_override="us-east-1",
    )
    assert cfg.env_path is None
    assert cfg.domain == "example.com"
    assert cfg.bucket == "my-botmail-bucket"


def test_session_token_in_env_file(tmp_path, monkeypatch):
    env = tmp_path / "agent.env"
    env.write_text(
        "AWS_ACCESS_KEY_ID=AKIA_TEST\n"
        "AWS_SECRET_ACCESS_KEY=secret\n"
        "AWS_SESSION_TOKEN=token123\n"
        "BOTMAIL_DOMAIN=example.com\n"
        "BOTMAIL_PREFIX=example.com/\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    cfg = load_config(env_path=env)
    assert cfg.session_token == "token123"


def test_missing_mailbox_settings_exits(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    with pytest.raises(SystemExit):
        load_config(env_path=None)


def test_profile_override(tmp_path, monkeypatch):
    env = tmp_path / "agent.env"
    env.write_text(
        "BOTMAIL_DOMAIN=example.com\n"
        "BOTMAIL_PREFIX=example.com/\n"
        "BOTMAIL_PROFILE=deploy\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    cfg = load_config(env_path=env)
    assert cfg.profile == "deploy"


def test_default_bucket_placeholder(tmp_path, monkeypatch):
    env = tmp_path / "a.env"
    env.write_text(
        "BOTMAIL_DOMAIN=example.com\n"
        "BOTMAIL_PREFIX=example.com/\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    cfg = load_config(env_path=env)
    assert cfg.bucket == DEFAULT_BUCKET