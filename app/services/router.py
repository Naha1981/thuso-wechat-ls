from dataclasses import dataclass

@dataclass(frozen=True)
class Intent:
    name: str
    confidence: float
    args: dict

KEYWORDS = {
    "ride": {"ride", "taxi", "uber", "lift", "car"},
    "mechanic": {"mechanic", "car broken", "repair", "puncture", "battery"},
    "handyman": {"plumber", "electrician", "handyman", "fix", "repair house"},
    "food": {"food", "restaurant", "hungry", "order food", "delivery"},
    "tutor": {"tutor", "homework", "maths", "math", "study", "teacher"},
    "career": {"cv", "resume", "job", "jobs", "career"},
    "mental_health": {"anxious", "anxiety", "depressed", "depression", "stress", "mental health"},
}

def classify(text: str) -> Intent:
    normalized = text.lower().strip()
    for name, terms in KEYWORDS.items():
        if any(term in normalized for term in terms):
            return Intent(name, 0.92, {})
    return Intent("help", 0.35, {})
