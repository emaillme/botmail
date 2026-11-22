"""Build boto3 sessions with optional profile, env-file keys, and assumed roles."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import boto3
from botocore.credentials import RefreshableCredentials
from botocore.session import Session as BotocoreSession


def _expiry_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S%z")


def _assume_role_metadata(
    sts_client: Any,
    *,
    role_arn: str,
    role_session_name: str,
    external_id: str | None,
) -> dict[str, str]:
    kwargs: dict[str, Any] = {
        "RoleArn": role_arn,
        "RoleSessionName": role_session_name,
    }
    if external_id:
        kwargs["ExternalId"] = external_id
    resp = sts_client.assume_role(**kwargs)
    creds = resp["Credentials"]
    return {
        "access_key": creds["AccessKeyId"],
        "secret_key": creds["SecretAccessKey"],
        "token": creds["SessionToken"],
        "expiry_time": _expiry_iso(creds["Expiration"]),
    }


def _refreshable_assume_role(
    base_session: boto3.Session,
    *,
    role_arn: str,
    role_session_name: str,
    external_id: str | None,
    region: str,
) -> boto3.Session:
    def refresh() -> dict[str, str]:
        sts = base_session.client("sts", region_name=region)
        return _assume_role_metadata(
            sts,
            role_arn=role_arn,
            role_session_name=role_session_name,
            external_id=external_id,
        )

    metadata = refresh()
    refreshable = RefreshableCredentials.create_from_metadata(
        metadata=metadata,
        refresh_using=refresh,
        method="sts-assume-role",
    )
    bc = BotocoreSession()
    bc._credentials = refreshable  # noqa: SLF001
    bc.set_config_variable("region", region)
    return boto3.Session(botocore_session=bc)


def build_boto3_session(
    *,
    region: str,
    profile: str | None = None,
    access_key_id: str | None = None,
    secret_access_key: str | None = None,
    session_token: str | None = None,
    role_arn: str | None = None,
    role_session_name: str | None = None,
    external_id: str | None = None,
) -> boto3.Session:
    """Return a boto3 Session. Never logs credentials."""
    session_kwargs: dict[str, str] = {}
    if access_key_id and secret_access_key:
        session_kwargs["aws_access_key_id"] = access_key_id
        session_kwargs["aws_secret_access_key"] = secret_access_key
        if session_token:
            session_kwargs["aws_session_token"] = session_token
    elif profile:
        session_kwargs["profile_name"] = profile

    base = boto3.Session(region_name=region, **session_kwargs)

    if role_arn:
        name = role_session_name or "botmail"
        return _refreshable_assume_role(
            base,
            role_arn=role_arn,
            role_session_name=name,
            external_id=external_id,
            region=region,
        )
    return base