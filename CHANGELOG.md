# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.1.0] - 2025-11-22

### Added

- `botmail` CLI: `list`, `read`, `wait`, `links`, `save-attachments`, `send`, `reply` with `--json`
- Inbound mail from S3 (SES receipt rules) and outbound via SES (boto3)
- Optional env-file credentials; default AWS credential chain; profile and STS role assumption
- Reference CloudFormation template `infra/botmail.yaml`
- Documentation: `README.md`, `AGENTS.md`, `docs/developer.md`

[0.1.0]: https://github.com/emaillme/botmail/releases/tag/v0.1.0