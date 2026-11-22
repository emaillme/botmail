# botmail

**botmail** is a small Python CLI that gives AI agents real email addresses backed by AWS: inbound mail is received by [Amazon SES](https://aws.amazon.com/ses/) and stored in [S3](https://aws.amazon.com/s3/) as raw MIME; outbound mail is sent through SES. It uses **boto3** only (no AWS CLI).

Agents need a real inbox for sign-ups, verification codes, magic links, password resets, and human replies. botmail exposes that inbox as stable commands with **`--json`** output for automation.

The installable package on PyPI is published as **`botmail-cli`** (the `botmail` name is taken); the command on your PATH is still `botmail`.

## How it works

```mermaid
flowchart LR
  subgraph inbound["Inbound"]
    Sender[Sender] --> MX[MX record]
    MX --> SESin[SES receiving]
    SESin --> S3[(S3 bucket)]
    S3 --> CLI[botmail list / read / wait]
  end
  subgraph outbound["Outbound"]
    CLI2[botmail send / reply] --> SESout[SES sending]
    SESout --> Recipient[Recipient]
  end
```

ASCII overview:

```
Sender -> MX -> SES (inbound) -> S3 -> botmail
botmail -> SES (outbound) -> recipient
```

## Install

From Git (recommended until PyPI publish):

```bash
pipx install git+https://github.com/emaillme/botmail.git
# or
pip install --user git+https://github.com/emaillme/botmail.git
```

Development install:

```bash
git clone https://github.com/emaillme/botmail.git
cd botmail
pip install -e ".[dev]"
```

## Quickstart

1. Deploy AWS resources (see [AWS setup](#aws-setup)) and note bucket, prefix, and domain.
2. Configure credentials (role recommended, or optional keys in an env file).
3. List mail:

```bash
export BOTMAIL_DOMAIN=example.com
export BOTMAIL_PREFIX=example.com/
export BOTMAIL_BUCKET=my-botmail-bucket
export AWS_REGION=us-east-1

botmail --json list --limit 10
```

Or use `~/.config/botmail/agent.env`:

```bash
# Optional static keys; omit to use IAM role / instance profile / AWS_PROFILE
# AWS_ACCESS_KEY_ID=...
# AWS_SECRET_ACCESS_KEY=...
# AWS_SESSION_TOKEN=...
BOTMAIL_DOMAIN=example.com
BOTMAIL_PREFIX=example.com/
BOTMAIL_BUCKET=my-botmail-bucket
BOTMAIL_REGION=us-east-1
# BOTMAIL_ROLE_ARN=arn:aws:iam::123456789012:role/botmail-agent
```

If exactly one file exists in `~/.config/botmail/*.env`, it is picked automatically; otherwise set `BOTMAIL_ENV` or pass `--env`.

Global flags: `--domain`, `--prefix`, `--bucket`, `--region`, `--profile`, `--role-arn`, `--external-id`, `--role-session-name`, `--json`.

## Commands

### `list`

```bash
botmail list
botmail list --to agent@example.com --since 2h --limit 20 --unread
botmail --json list --limit 3
```

`--json` example:

```json
[
  {
    "id": "msg-1",
    "date": "2024-06-01T12:00:00+00:00",
    "from": "noreply@example.com",
    "to": "agent@example.com",
    "subject": "Your code",
    "unread": true
  }
]
```

### `read`

```bash
botmail read MESSAGE_ID
botmail read MESSAGE_ID --raw
botmail --json read MESSAGE_ID
```

`--json` example (truncated):

```json
{
  "id": "msg-1",
  "headers": {
    "from": "noreply@example.com",
    "to": "agent@example.com",
    "subject": "Your code",
    "date": "2024-06-01T12:00:00+00:00",
    "message_id": "<id@example.com>"
  },
  "body": "Your verification code is 123456",
  "attachments": [],
  "authentication_results": ""
}
```

### `wait`

Polls S3 until a message matches `--to` (and optional `--subject-contains`).

```bash
botmail wait --to agent@example.com --subject-contains Verify --timeout 300
botmail --json wait --to agent@example.com --timeout 60
```

`--json` example:

```json
{
  "id": "inbound-abc123"
}
```

### `links`

```bash
botmail links MESSAGE_ID
botmail --json links MESSAGE_ID
```

`--json` example:

```json
{
  "links": [
    "https://example.com/verify?token=abc"
  ]
}
```

### `save-attachments`

```bash
botmail save-attachments MESSAGE_ID ./downloads
botmail --json save-attachments MESSAGE_ID ./downloads
```

`--json` example:

```json
{
  "paths": [
    "/path/downloads/report.pdf"
  ]
}
```

### `send`

`--from` must be `*@BOTMAIL_DOMAIN`.

```bash
botmail send --from agent@example.com --to user@example.org \
  --subject "Hello" --body "Plain text"

botmail send --from agent@example.com --to user@example.org \
  --subject "Hello" --body-file ./msg.txt --html-file ./msg.html --attach ./file.pdf

botmail --json send --from agent@example.com --to user@example.org \
  --subject "Hello" --body "Hi"
```

`--json` example:

```json
{
  "message_id": "0100018a00000000-00000000-0000-0000-0000-000000000000-000000"
}
```

### `reply`

```bash
botmail reply MESSAGE_ID --body "Thanks"
botmail --json reply MESSAGE_ID --body "Thanks"
```

`--json` example:

```json
{
  "message_id": "0100018a00000000-...",
  "in_reply_to": "msg-1"
}
```

## AWS setup

### 1. Pick a region

Use an SES region that supports **email receiving** (for example `us-east-1`, `eu-west-1`). The bucket and receipt rule must be in the **same region** as SES receiving.

See [Amazon SES endpoints](https://docs.aws.amazon.com/general/latest/gr/ses.html).

### 2. Verify your domain (outbound + identity)

In SES, verify the domain you will send from and receive on. Enable **DKIM** (Easy DKIM). This is **not** created by the included CloudFormation template.

Console: SES -> Verified identities -> Create identity (domain).

CLI:

```bash
aws sesv2 create-email-identity --email-identity example.com
```

Add the DKIM CNAME records SES provides to your DNS.

### 3. MX record for inbound mail

Publish an MX record pointing at the SES inbound endpoint for your region. Example for `example.com` in `us-east-1`:

```
10 inbound-smtp.us-east-1.amazonaws.com
```

See [Receiving email with Amazon SES](https://docs.aws.amazon.com/ses/latest/dg/receiving-email.html).

### 4. Deploy infrastructure

Template: [`infra/botmail.yaml`](infra/botmail.yaml).

Example (account `123456789012`):

```bash
aws cloudformation deploy \
  --stack-name botmail-inbox \
  --template-file infra/botmail.yaml \
  --parameter-overrides \
    DomainName=example.com \
    BucketName=my-botmail-bucket-unique \
    MailboxPrefix=example.com/ \
    CreateReceiptRuleSet=true \
    RuleSetName=botmail-inbound
```

### 5. Activate the receipt rule set

Only **one** receipt rule set is active per region. If you created a new set, activate it:

```bash
aws ses set-active-receipt-rule-set --rule-set-name botmail-inbound
```

Check the active set:

```bash
aws ses describe-active-receipt-rule-set
```

If `CreateReceiptRuleSet=false`, the rule is added to an **existing** `RuleSetName` you already manage.

### 6. IAM for agents

**Recommended:** attach the stack output `BotmailPolicyArn` to a role your agent runs as, or use the optional `BotmailRoleArn` from the template. Pass the role to botmail:

```bash
export BOTMAIL_ROLE_ARN=arn:aws:iam::123456789012:role/botmail-agent
```

**Fallback:** IAM user access keys in the env file (discouraged for production).

botmail never prints credentials.

### 7. Leave the SES sandbox

New SES accounts are in sandbox mode (limited recipients). Request production access in the SES console when you are ready to send to arbitrary addresses.

### Costs (rough)

- **SES**: per-message pricing for send and receive; see [SES pricing](https://aws.amazon.com/ses/pricing/).
- **S3**: storage and requests for stored MIME; see [S3 pricing](https://aws.amazon.com/s3/pricing/).
- **Data transfer**: standard AWS data transfer charges may apply.

### Security notes

- Block public access on the inbox bucket (the template does this).
- Scope IAM to the inbox prefix and `ses:FromAddress` for your domain.
- Treat inbound MIME as untrusted (phishing, malware). Scan attachments before opening.
- Rotate keys if used; prefer instance/task roles and `AssumeRole`.

## Development

```bash
pip install -e ".[dev]"
pytest -q
ruff check src tests
cfn-lint infra/botmail.yaml
```

See [`docs/developer.md`](docs/developer.md) and [`AGENTS.md`](AGENTS.md).

## License

MIT. See [`LICENSE`](LICENSE).

Don't want to run AWS yourself? [emaillme](https://emaillme.com) gives your agents email without the setup.