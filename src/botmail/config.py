"""Load bot credentials and defaults from env files and environment."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

import boto3

from botmail.session import build_boto3_session

DEFAULT_BUCKET = "my-botmail-bucket"
DEFAULT_REGION = "us-east-1"

_ENV_VAR = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class BotConfig:
    env_path: Path | None
    bot_name: str
    access_key_id: str | None
    secret_access_key: str | None
    session_token: str | None
    profile: str | None
    role_arn: str | None
    role_session_name: str | None
    external_id: str | None
    region: str
    bucket: str
    prefix: str
    domain: str
    state_dir: Path

    def boto_session(self) -> boto3.Session:
        return build_boto3_session(
            region=self.region,
            profile=self.profile,
            access_key_id=self.access_key_id,
            secret_access_key=self.secret_access_key,
            session_token=self.session_token,
            role_arn=self.role_arn,
            role_session_name=self.role_session_name,
            external_id=self.external_id,
        )


def _config_dir() -> Path:
    return Path.home() / ".config" / "botmail"


def _parse_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'\"")
        if _ENV_VAR.match(key):
            out[key] = value
    return out


def _bot_name_from_path(path: Path) -> str:
    return path.stem.lower() or "default"


def _derive_domain_prefix(
    bot_name: str,
    data: dict[str, str],
    *,
    domain_override: str | None,
    prefix_override: str | None,
) -> tuple[str, str]:
    domain = (
        domain_override
        or data.get("BOTMAIL_DOMAIN")
        or data.get("DOMAIN")
        or data.get("BOT_DOMAIN")
        or os.environ.get("BOTMAIL_DOMAIN")
    )
    prefix = (
        prefix_override
        or data.get("BOTMAIL_PREFIX")
        or data.get("S3_PREFIX")
        or data.get("PREFIX")
        or os.environ.get("BOTMAIL_PREFIX")
    )
    if domain and not prefix:
        prefix = domain if domain.endswith("/") else f"{domain}/"
    if prefix and not prefix.endswith("/"):
        prefix = f"{prefix}/"
    if not domain and prefix:
        domain = prefix.rstrip("/")
    if not domain or not prefix:
        raise SystemExit(
            "Could not derive domain/prefix; set BOTMAIL_DOMAIN and BOTMAIL_PREFIX "
            "(env vars, env file, or pass --domain / --prefix)."
        )
    _ = bot_name
    return domain, prefix


def discover_env_file() -> Path | None:
    cfg = _config_dir()
    if not cfg.is_dir():
        return None
    env_files = sorted(cfg.glob("*.env"))
    if len(env_files) == 0:
        return None
    if len(env_files) > 1:
        names = ", ".join(p.name for p in env_files)
        raise SystemExit(
            f"Multiple env files in {cfg} ({names}); pass --env FILE or set BOTMAIL_ENV."
        )
    return env_files[0]


def _has_mailbox_settings_from_env_or_flags(
    *,
    domain_override: str | None,
    prefix_override: str | None,
    bucket_override: str | None,
    region_override: str | None,
) -> bool:
    if any((domain_override, prefix_override, bucket_override, region_override)):
        return True
    keys = (
        "BOTMAIL_DOMAIN",
        "BOTMAIL_PREFIX",
        "BOTMAIL_BUCKET",
        "BOTMAIL_REGION",
        "AWS_REGION",
        "AWS_DEFAULT_REGION",
    )
    return any(os.environ.get(k) for k in keys)


def load_config(
    *,
    env_path: Path | None = None,
    domain_override: str | None = None,
    prefix_override: str | None = None,
    bucket_override: str | None = None,
    region_override: str | None = None,
    profile_override: str | None = None,
    role_arn_override: str | None = None,
    role_session_name_override: str | None = None,
    external_id_override: str | None = None,
) -> BotConfig:
    data: dict[str, str] = {}
    resolved_env: Path | None = None

    if env_path is None:
        env_from_os = os.environ.get("BOTMAIL_ENV")
        if env_from_os:
            resolved_env = Path(env_from_os).expanduser()
        else:
            resolved_env = discover_env_file()
    else:
        resolved_env = env_path.expanduser()

    if resolved_env is not None:
        if not resolved_env.is_file():
            raise SystemExit(f"Env file not found: {resolved_env}")
        data = _parse_env_file(resolved_env)

    for key in (
        "AWS_DEFAULT_REGION",
        "AWS_REGION",
        "BOTMAIL_PROFILE",
        "BOTMAIL_ROLE_ARN",
        "BOTMAIL_ROLE_SESSION_NAME",
        "BOTMAIL_EXTERNAL_ID",
        "BOTMAIL_BUCKET",
        "BOTMAIL_PREFIX",
        "BOTMAIL_DOMAIN",
        "BOTMAIL_REGION",
    ):
        if key not in data and key in os.environ:
            data[key] = os.environ[key]

    if resolved_env is None and not _has_mailbox_settings_from_env_or_flags(
        domain_override=domain_override,
        prefix_override=prefix_override,
        bucket_override=bucket_override,
        region_override=region_override,
    ):
        cfg = _config_dir()
        raise SystemExit(
            f"No env file and missing mailbox settings. Pass --domain, --prefix, "
            f"--bucket, and --region (or set BOTMAIL_* env vars), or create "
            f"{cfg}/*.env or pass --env FILE."
        )

    access = data.get("AWS_ACCESS_KEY_ID")
    secret = data.get("AWS_SECRET_ACCESS_KEY")
    token = data.get("AWS_SESSION_TOKEN")
    if access and not secret:
        raise SystemExit("AWS_ACCESS_KEY_ID is set without AWS_SECRET_ACCESS_KEY.")
    if secret and not access:
        raise SystemExit("AWS_SECRET_ACCESS_KEY is set without AWS_ACCESS_KEY_ID.")

    profile = profile_override or data.get("BOTMAIL_PROFILE") or data.get("AWS_PROFILE")
    role_arn = role_arn_override or data.get("BOTMAIL_ROLE_ARN")
    role_session_name = (
        role_session_name_override or data.get("BOTMAIL_ROLE_SESSION_NAME") or "botmail"
    )
    external_id = external_id_override or data.get("BOTMAIL_EXTERNAL_ID")

    region = (
        region_override
        or data.get("BOTMAIL_REGION")
        or data.get("AWS_DEFAULT_REGION")
        or data.get("AWS_REGION")
        or DEFAULT_REGION
    )
    bucket = (
        bucket_override
        or data.get("BOTMAIL_BUCKET")
        or data.get("S3_BUCKET")
        or data.get("BUCKET")
        or DEFAULT_BUCKET
    )

    bot_name = _bot_name_from_path(resolved_env) if resolved_env else "default"
    domain, prefix = _derive_domain_prefix(
        bot_name, data, domain_override=domain_override, prefix_override=prefix_override
    )

    state_dir = Path.home() / ".local" / "state" / "botmail" / bot_name
    state_dir.mkdir(parents=True, exist_ok=True)

    return BotConfig(
        env_path=resolved_env,
        bot_name=bot_name,
        access_key_id=access,
        secret_access_key=secret,
        session_token=token,
        profile=profile,
        role_arn=role_arn,
        role_session_name=role_session_name,
        external_id=external_id,
        region=region,
        bucket=bucket,
        prefix=prefix,
        domain=domain,
        state_dir=state_dir,
    )