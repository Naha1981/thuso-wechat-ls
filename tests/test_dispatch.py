from datetime import datetime, timezone, timedelta
from uuid import uuid4
from app.services.dispatch import Candidate, score_candidate

def test_nearer_provider_scores_higher_when_other_factors_equal():
    now=datetime.now(timezone.utc)
    near=Candidate(uuid4(),500,5,10,now,1.0)
    far=Candidate(uuid4(),10000,5,10,now,1.0)
    assert score_candidate(near,now) > score_candidate(far,now)

def test_response_rate_and_rating_influence_score():
    now=datetime.now(timezone.utc)
    strong=Candidate(uuid4(),2000,5,20,now,1.0)
    weak=Candidate(uuid4(),2000,2,20,now,0.1)
    assert score_candidate(strong,now) > score_candidate(weak,now)

def test_stale_provider_is_penalized():
    now=datetime.now(timezone.utc)
    fresh=Candidate(uuid4(),2000,4,10,now,0.5)
    stale=Candidate(uuid4(),2000,4,10,now-timedelta(hours=3),0.5)
    assert score_candidate(fresh,now) > score_candidate(stale,now)
