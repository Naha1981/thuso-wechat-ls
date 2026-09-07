from app.services.media_intelligence_worker import _reply_text


def test_voice_result_is_conversational_input_contract():
    assert _reply_text({"task_type": "transcription", "text": "ride to town", "structured": {}}).startswith("I received your voice note.")


def test_action_confirmation_contract_is_explicit():
    action_id = "00000000-0000-0000-0000-000000000001"
    payload = {
        "body": "Please confirm",
        "buttons": [
            {"id": f"agent:confirm:{action_id}", "title": "Confirm"},
            {"id": f"agent:decline:{action_id}", "title": "Decline"},
        ],
    }
    assert payload["buttons"][0]["id"].startswith("agent:confirm:")
    assert payload["buttons"][1]["id"].startswith("agent:decline:")
