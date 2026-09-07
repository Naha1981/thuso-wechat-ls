from app.services.router import classify

def test_classifies_ride():
    assert classify("I need a ride to Sandton").name == "ride"

def test_classifies_cv():
    assert classify("help me write my CV").name == "career"
