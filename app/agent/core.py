from dataclasses import dataclass
from enum import Enum
import re

class IntentName(str, Enum):
    HELP='help'; RIDE='ride'; MECHANIC='mechanic'; HANDYMAN='handyman'; FOOD='food'; TUTOR='tutor'; CAREER='career'; MENTAL_HEALTH='mental_health'; POS='pos'; FINANCE='finance'; CANCEL='cancel'; STATUS='status'

@dataclass(frozen=True)
class Intent:
    name: IntentName
    confidence: float
    args: dict

PATTERNS = {
    IntentName.RIDE: r'\b(ride|taxi|uber|lift|driver|transport)\b',
    IntentName.MECHANIC: r'\b(mechanic|car.*(broken|repair)|puncture|flat tyre|battery|tow)\b',
    IntentName.HANDYMAN: r'\b(handyman|plumber|electrician|carpenter|repair.*house|fix.*house)\b',
    IntentName.FOOD: r'\b(food|restaurant|hungry|order.*food|delivery|takeaway)\b',
    IntentName.TUTOR: r'\b(tutor|homework|maths|math|study|teacher|exam|caps)\b',
    IntentName.CAREER: r'\b(cv|resume|job|jobs|career|work)\b',
    IntentName.MENTAL_HEALTH: r'\b(anxious|anxiety|depress|depression|stress|panic|mental health|suicid|kill myself|hurt myself)\b',
    IntentName.POS: r'\b(pos|point of sale|stock|inventory|till|sales)\b',
    IntentName.FINANCE: r'\b(finance|financial|money|budget|saving|savings|debt|credit|learn.*money)\b',
    IntentName.CANCEL: r'^\s*(cancel|stop|nevermind|never mind)\s*$',
    IntentName.STATUS: r'\b(status|where.*(driver|provider)|my request)\b',
}

def classify(text: str) -> Intent:
    t = text.strip().lower()
    for name, pattern in PATTERNS.items():
        if re.search(pattern, t):
            args = {}
            if name == IntentName.MENTAL_HEALTH and re.search(r'\b(suicid|kill myself|hurt myself)\b', t):
                args['crisis_signal'] = True
            return Intent(name, 0.96, args)
    return Intent(IntentName.HELP, 0.25, {})
