from app.services.agent_execution import ACTION_TO_CATEGORY

def test_supported_service_categories():
    assert set(ACTION_TO_CATEGORY) == {'ride','mechanic','handyman','food'}
