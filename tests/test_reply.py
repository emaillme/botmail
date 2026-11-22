from email.message import EmailMessage

from botmail import compose, mimeutil


def test_reply_composition_threading():
    original = EmailMessage()
    original["From"] = "user@example.com"
    original["To"] = "inbox@example.com"
    original["Delivered-To"] = "inbox@example.com"
    original["Subject"] = "Question"
    original["Message-ID"] = "<orig123@example.com>"
    shell = mimeutil.build_reply_headers(original, "inbox@example.com")
    msg = compose.build_message(
        from_addr="inbox@example.com",
        to_addrs=["user@example.com"],
        subject=shell["Subject"],
        body_text="Thanks",
        extra_headers={k: shell[k] for k in ("In-Reply-To", "References") if k in shell},
    )
    assert msg["Subject"] == "Re: Question"
    assert msg["In-Reply-To"] == "<orig123@example.com>"
    assert msg["From"] == "inbox@example.com"
    assert mimeutil.recipient_for_reply(original) == "inbox@example.com"