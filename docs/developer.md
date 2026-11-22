# Developer guide

## Layout

| Path | Purpose |
| --- | --- |
| `src/botmail/cli.py` | Argument parser and subcommands |
| `src/botmail/config.py` | Env file discovery, mailbox settings, `BotConfig` |
| `src/botmail/session.py` | boto3 session (profile, static keys, STS assume role) |
| `src/botmail/store.py` | S3 inbox + SES send |
| `src/botmail/mimeutil.py` | MIME parsing, links, reply headers |
| `infra/botmail.yaml` | Reference CloudFormation for bucket, receipt rule, IAM |
| `tests/` | pytest + moto |

## PyPI package name

The console script is always `botmail`. The PyPI distribution name is **`botmail-cli`** because `botmail` is already taken on PyPI.

## Credentials behavior

1. **Env file** (`~/.config/botmail/*.env`, `BOTMAIL_ENV`, or `--env`): optional `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_SESSION_TOKEN`.
2. **No static keys in the env file**: `build_boto3_session` uses the default credential chain (process env, shared config/`AWS_PROFILE`, SSO, instance/task role).
3. **`BOTMAIL_PROFILE` / `--profile`**: passed to `boto3.Session(profile_name=...)`.
4. **`BOTMAIL_ROLE_ARN` / `--role-arn`**: STS `AssumeRole` with `RefreshableCredentials` (optional `BOTMAIL_EXTERNAL_ID`, session name).

Static keys are never logged. Region defaults to `us-east-1`; bucket default placeholder is `my-botmail-bucket`.

## Local development

```bash
pip install -e ".[dev]"
ruff check src tests
pytest -q
cfn-lint infra/botmail.yaml
```

## Version

Set `__version__` in `src/botmail/__init__.py` only. `pyproject.toml` reads it via `[tool.setuptools.dynamic]`.

## CI

`.github/workflows/ci.yml` runs:

- **package**: `python -m build`, `twine check`, install wheel, `botmail --help`
- **test**: ruff, pytest on Python 3.9 through 3.13, cfn-lint

## Releases

See [`docs/RELEASING.md`](RELEASING.md) for PyPI Trusted Publishing and GitHub release steps.