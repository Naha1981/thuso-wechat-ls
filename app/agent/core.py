from dataclasses import dataclass
from enum import Enum
import re

class IntentName(str, Enum):
    HELP='help'
    RIDE='ride'
    MECHANIC='mechanic'
    HANDYMAN='handyman'
    FOOD='food'
    GROCERIES='groceries'
    SHOPPING='shopping'
    DIASPORA='diaspora'
    TUTOR='tutor'
    CAREER='career'
    MENTAL_HEALTH='mental_health'
    POS='pos'
    FINANCE='finance'
    CREDIT='credit'
    TAX='tax'
    AGRICULTURE='agriculture'
    TELECOM='telecom'
    TRAVEL='travel'
    PAYMENT='payment'
    BUSINESS='business'
    CANCEL='cancel'
    STATUS='status'

@dataclass(frozen=True)
class Intent:
    name: IntentName
    confidence: float
    args: dict

PATTERNS = {
    IntentName.MENTAL_HEALTH: r'\b(anxious|anxiety|depress|depression|stress|panic|mental health|suicid|kill myself|hurt myself)\b',
    IntentName.DIASPORA: r'\b(send.*(groceries|food|shopping)|feed.*family|family.*back home|diaspora|send.*home)\b',
    IntentName.CREDIT: r'\b(loan|credit|borrow|financ(e|ing)|credit score|eligible.*loan)\b',
    IntentName.TELECOM: r'\b(airtime|data bundle|bundle|mobile data|sim|telecom)\b',
    IntentName.TAX: r'\b(tax|vat|customs|duty|import|export|trade|rsl|sars)\b',
    IntentName.AGRICULTURE: r'\b(farmer|farm|farming|fertilizer|seed|crop|harvest|yield|agriculture)\b',
    IntentName.PAYMENT: r'\b(pay|payment|ecocash|m-pesa|mpesa|bank transfer|wallet)\b',
    IntentName.GROCERIES: r'\b(grocer(y|ies)|grocery|groceries|shoprite|checkers|pick n pay|vegetables|weekly shop)\b',
    IntentName.FOOD: r'\b(food|restaurant|hungry|order.*food|takeaway)\b',
    IntentName.RIDE: r'\b(ride|taxi|uber|lift|driver|transport|pick me up)\b',
    IntentName.MECHANIC: r'\b(mechanic|car.*(broken|repair)|puncture|flat tyre|battery|tow)\b',
    IntentName.HANDYMAN: r'\b(handyman|plumber|electrician|carpenter|repair.*house|fix.*house)\b',
    IntentName.TRAVEL: r'\b(travel|hotel|accommodation|flight|bus ticket|trip|itinerary)\b',
    IntentName.SHOPPING: r'\b(shopping|buy|purchase|order.*(product|item|goods))\b',
    IntentName.BUSINESS: r'\b(business|sme|merchant|spaza|shop owner|store owner|company)\b',
    IntentName.POS: r'\b(pos|point of sale|stock|inventory|till|sales)\b',
    IntentName.FINANCE: r'\b(finance|financial|money|budget|saving|savings|debt|learn.*money|profit)\b',
    IntentName.TUTOR: r'\b(tutor|homework|maths|math|study|teacher|exam|caps)\b',
    IntentName.CAREER: r'\b(cv|resume|job|jobs|career|work|employment)\b',
    IntentName.CANCEL: r'^\s*(cancel|stop|nevermind|never mind)\s*$',
    IntentName.STATUS: r'\b(status|where.*(driver|provider|order)|track|my request|my order)\b',
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
