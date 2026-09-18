from app.agent.core import IntentName, classify

def test_diaspora_request_routes_to_ramalaisha():
    assert classify("send groceries to my family in Lesotho").name == IntentName.DIASPORA

def test_grocery_request_routes_to_groceries():
    assert classify("buy groceries").name == IntentName.GROCERIES

def test_ride_request_routes_to_transport():
    assert classify("I need a ride to town").name == IntentName.RIDE

def test_loan_request_routes_to_credit():
    assert classify("am I eligible for a small business loan").name == IntentName.CREDIT

def test_airtime_request_routes_to_telecom():
    assert classify("buy airtime").name == IntentName.TELECOM
