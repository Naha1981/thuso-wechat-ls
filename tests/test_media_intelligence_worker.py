from uuid import uuid4

from app.services.media_intelligence_worker import _reply_text, STREAM, GROUP


def test_worker_stream_contract():
    assert STREAM == "naha:media:intelligence"
    assert GROUP == "media-intelligence-workers"


def test_transcription_reply_is_bounded():
    result = {"task_type": "transcription", "text": "hello " * 3000, "structured": {}}
    body = _reply_text(result)
    assert body.startswith("I received your voice note.")
    assert len(body) <= 6050


def test_receipt_reply_uses_structured_total():
    body = _reply_text({
        "task_type": "receipt",
        "text": "",
        "structured": {"receipt": {"total": "125.50", "currency": "LSL"}},
    })
    assert body == "Receipt processed. Total: LSL 125.50."


def test_generic_media_reply():
    assert _reply_text({"task_type": "vision", "text": "x", "structured": {}}) == "I received and processed your media."
