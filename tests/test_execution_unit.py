from app.services.execution import ACTIVE_REQUESTS

def test_active_request_states():
    assert {'searching','offered','accepted','in_progress'} == ACTIVE_REQUESTS
