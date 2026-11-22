# Security

## Reporting vulnerabilities

Please report security issues privately through [GitHub Security Advisories](https://github.com/emaillme/botmail/security/advisories/new). Do not open a public issue for sensitive reports.

We will acknowledge receipt and work on a fix. Include steps to reproduce, impact, and any suggested mitigation.

## Safe use

- Never commit AWS credentials or env files.
- Treat inbound email as untrusted input.
- Restrict IAM permissions with the provided CloudFormation policy and prefer role-based access over long-lived access keys.