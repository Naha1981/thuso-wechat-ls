from datetime import datetime, timezone, timedelta
from uuid import uuid4
from app.services.dispatch import Candidate, score_candidate

def test_dispatch_score_prefers_nearby_fresh_provider():
    now = datetime.now(timezone.utc)
    near = Candidate(uuid4(), 500, 4.8, 50, now, .9, 180)
    far = Candidate(uuid4(), 12000, 4.9, 80, now-timedelta(minutes=30), .95, 1200)
    assert score_candidate(near, now) > score_candidate(far, now)

def test_dispatch_score_is_bounded():
    c = Candidate(uuid4(), 0, 5, 100, datetime.now(timezone.utc), 1, 0)
    assert 0 < score_candidate(c) <= 1
