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
        IntentName.GROCERIES:'🛒 I can help with groceries. Tell me what you need, who it is for, and the delivery/pickup area.',
        IntentName.SHOPPING:'🛍️ I can help you find and order products. Tell me what you need and where it should be delivered or collected.',
        IntentName.DIASPORA:'❤️ I can help you send groceries or purchases to family in Lesotho. Tell me what you want to send and who it is for.',
        IntentName.TUTOR:'🎓 Tell me your grade, subject and topic, and I’ll help you learn it.',
        IntentName.CAREER:'💼 I can help with a CV or job search. Send your current CV or say CV/JOBS.',
        IntentName.MENTAL_HEALTH:'🧠 I can listen and help you find appropriate support. Tell me what’s going on.',
        IntentName.POS:'🏪 I can help set up your mobile POS, products, stock and sales.',
        IntentName.BUSINESS:'🏪 I can help run your business: sales, stock, expenses, customers and daily summaries.',
        IntentName.FINANCE:'💰 I can teach budgeting, saving, debt basics and small-business finance.',
        IntentName.CREDIT:'🏦 I can explain credit and check the information needed for a financing or loan eligibility workflow.',
        IntentName.TAX:'🧾 I can help with VAT, tax records, trade and customs-ready information.',
        IntentName.AGRICULTURE:'🌾 I can help with farming inputs, markets, crop information and agricultural services.',
        IntentName.TELECOM:'📱 I can help with airtime, data bundles and supported telecom services.',
        IntentName.TRAVEL:'✈️ I can help plan travel, transport and accommodation services.',
        IntentName.PAYMENT:'💳 I can help you make or track a supported payment.',
        IntentName.CANCEL:'Okay — I’ll stop the current pending action.',
        IntentName.STATUS:'📍 I can check your latest request or order status.',
        IntentName.HELP:'Hi! I can help with government services, food, groceries, shopping, rides, business, payments, jobs, education, agriculture, telecom and more. What do you need?'
    }[intent]
