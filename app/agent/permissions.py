from enum import Enum
class ActionRisk(str, Enum): LOW='low'; MEDIUM='medium'; HIGH='high'

# Consequential actions require explicit approval unless a server-side policy says otherwise.
RISK = {'create_service_request': ActionRisk.MEDIUM, 'accept_offer': ActionRisk.HIGH, 'charge_payment': ActionRisk.HIGH, 'cancel_request': ActionRisk.MEDIUM}

def requires_confirmation(action: str) -> bool:
    return RISK.get(action, ActionRisk.LOW) != ActionRisk.LOW
