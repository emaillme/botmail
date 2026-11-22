import json
from pathlib import Path

import boto3
import pytest
from moto import mock_aws

from botmail.config import load_config
from botmail.store import MailStore


@mock_aws
def test_default_credential_chain_without_env_keys(tmp_path, monkeypatch):
    env = tmp_path / "agent.env"
    env.write_text(
        "BOTMAIL_DOMAIN=example.com\n"
        "BOTMAIL_PREFIX=example.com/\n"
        "BOTMAIL_BUCKET=chain-bucket\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")

    cfg = load_config(env_path=env)
    assert cfg.access_key_id is None
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket=cfg.bucket)
    store = MailStore(cfg)
    assert store.list_refs() == []


@mock_aws
def test_assume_role_credentials(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")

    iam = boto3.client("iam", region_name="us-east-1")
    sts = boto3.client("sts", region_name="us-east-1")
    account = sts.get_caller_identity()["Account"]
    trust = json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"AWS": f"arn:aws:iam::{account}:root"},
                    "Action": "sts:AssumeRole",
                }
            ],
        }
    )
    role_resp = iam.create_role(
        RoleName="botmail-test",
        AssumeRolePolicyDocument=trust,
    )
    role_arn = role_resp["Role"]["Arn"]

    env = tmp_path / "agent.env"
    env.write_text(
        f"BOTMAIL_DOMAIN=example.com\n"
        f"BOTMAIL_PREFIX=example.com/\n"
        f"BOTMAIL_BUCKET=role-bucket\n"
        f"BOTMAIL_ROLE_ARN={role_arn}\n",
        encoding="utf-8",
    )
    cfg = load_config(env_path=env)
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket=cfg.bucket)

    store = MailStore(cfg)
    assert store.list_refs() == []

    assumed = sts.assume_role(RoleArn=role_arn, RoleSessionName="botmail")
    assert assumed["Credentials"]["AccessKeyId"]


@mock_aws
def test_env_file_static_keys(tmp_path, monkeypatch):
    env = tmp_path / "agent.env"
    env.write_text(
        "AWS_ACCESS_KEY_ID=testing\n"
        "AWS_SECRET_ACCESS_KEY=testing\n"
        "BOTMAIL_DOMAIN=example.com\n"
        "BOTMAIL_PREFIX=example.com/\n"
        "BOTMAIL_BUCKET=key-bucket\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    cfg = load_config(env_path=env)
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket=cfg.bucket)
    store = MailStore(cfg)
    assert store.list_refs() == []


def test_mismatched_key_pair_exits(tmp_path, monkeypatch):
    env = tmp_path / "agent.env"
    env.write_text(
        "AWS_ACCESS_KEY_ID=AKIA_TEST\n"
        "BOTMAIL_DOMAIN=example.com\n"
        "BOTMAIL_PREFIX=example.com/\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    with pytest.raises(SystemExit):
        load_config(env_path=env)