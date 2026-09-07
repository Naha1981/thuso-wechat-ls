from app.services.whatsapp_reliability import MAX_ATTEMPTS

def test_reliability_limits_are_bounded():
    assert MAX_ATTEMPTS == 8
