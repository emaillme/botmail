from email.message import EmailMessage

from botmail import mimeutil


def test_html_to_text_strips_tags():
    assert "Hello" in mimeutil.html_to_text("<p>Hello <b>world</b></p>")


def test_extract_links():
    body = "Confirm: https://example.com/ok?x=1 and http://example.org/a"
    links = mimeutil.extract_links(body)
    assert "https://example.com/ok?x=1" in links
    assert "http://example.org/a" in links


def test_reply_headers():
    orig = EmailMessage()
    orig["Subject"] = "Signup"
    orig["Message-ID"] = "<abc@example.com>"
    orig["References"] = "<older@example.com>"
    reply = mimeutil.build_reply_headers(orig, "agent@example.com")
    assert reply["From"] == "agent@example.com"
    assert reply["Subject"] == "Re: Signup"
    assert reply["In-Reply-To"] == "<abc@example.com>"
    assert "<older@example.com>" in reply["References"]


def test_best_text_body_prefers_plain():
    msg = EmailMessage()
    msg.set_content("plain body")
    msg.add_alternative("<p>html</p>", subtype="html")
    assert mimeutil.best_text_body(msg) == "plain body"


def test_summary_from_bytes():
    raw = (
        b"From: alice@example.com\r\n"
        b"To: bob@example.com\r\n"
        b"Subject: Test\r\n"
        b"\r\n"
        b"hi"
    )
    meta = mimeutil.summary_from_bytes(raw)
    assert meta["subject"] == "Test"
    assert "bob@example.com" in meta["to"]