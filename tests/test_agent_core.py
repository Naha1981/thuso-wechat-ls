from app.agent.core import classify, IntentName
from app.agent.commands import parse
from app.agent.permissions import requires_confirmation

def test_classification(): assert classify('I need a mechanic for my car').name == IntentName.MECHANIC
def test_crisis_signal(): assert classify('I want to kill myself').args['crisis_signal'] is True
def test_command(): assert parse('ride to Sandton').command == 'ride'
def test_high_stakes_confirmation(): assert requires_confirmation('charge_payment') is True
