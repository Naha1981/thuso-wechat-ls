from .core import IntentName

def response_for(intent: IntentName, *, crisis=False) -> str:
    if crisis:
        return ('I’m really sorry you’re dealing with this. I can stay with you and help you find support, '
                'but I’m not an emergency service. If you may hurt yourself or someone else, contact local emergency services '
                'or a trusted person now, and move somewhere you are not alone. If you can, tell me: are you in immediate danger right now?')
    return {
        IntentName.RIDE:'🚗 I can arrange a ride. Send your pickup location and destination.',
        IntentName.MECHANIC:'🔧 I can find a mechanic. Send your location and briefly describe the problem.',
        IntentName.HANDYMAN:'🛠️ What needs fixing? Send the job and your location.',
        IntentName.FOOD:'🍔 I can help you order food. Tell me what you want and your area.',
        IntentName.TUTOR:'🎓 Tell me your grade, subject and topic, and I’ll help you learn it.',
        IntentName.CAREER:'💼 I can help with a CV or job search. Send your current CV or say CV/JOBS.',
        IntentName.MENTAL_HEALTH:'🧠 I can listen and help you find appropriate support. Tell me what’s going on.',
        IntentName.POS:'🏪 I can help set up your mobile POS, products, stock and sales.',
        IntentName.FINANCE:'💰 I can teach budgeting, saving, debt basics and small-business finance.',
        IntentName.CANCEL:'Okay — I’ll stop the current pending action.',
        IntentName.STATUS:'📍 I can check your latest request status.',
        IntentName.HELP:'Hi! I can help with rides, mechanics, handymen, food, tutoring, CVs/jobs, POS and money education. What do you need?'
    }[intent]
