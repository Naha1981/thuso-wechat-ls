from dataclasses import dataclass
import re

@dataclass(frozen=True)
class ParsedCommand:
    command: str
    args: dict

def parse(text: str) -> ParsedCommand | None:
    t=text.strip()
    if re.fullmatch(r'(help|menu)', t, re.I): return ParsedCommand('help',{})
    if re.fullmatch(r'(cancel|stop)', t, re.I): return ParsedCommand('cancel',{})
    if re.fullmatch(r'(status|track)', t, re.I): return ParsedCommand('status',{})
    for pattern, command in [
        (r'^ride(?:\s+(.+))?$', 'ride'),
        (r'^(food|meal)(?:\s+(.+))?$', 'food'),
        (r'^(groceries|grocery)(?:\s+(.+))?$', 'groceries'),
        (r'^(shop|shopping)(?:\s+(.+))?$', 'shopping'),
        (r'^(send|diaspora)(?:\s+(.+))?$', 'diaspora'),
        (r'^(airtime|bundle)(?:\s+(.+))?$', 'telecom'),
        (r'^(loan|credit)(?:\s+(.+))?$', 'credit'),
        (r'^(tax|vat|customs)(?:\s+(.+))?$', 'tax'),
        (r'^(farm|farmer|agriculture)(?:\s+(.+))?$', 'agriculture'),
        (r'^(pay|payment)(?:\s+(.+))?$', 'payment'),
        (r'^(travel|hotel|flight)(?:\s+(.+))?$', 'travel'),
        (r'^(business|sme|spaza)(?:\s+(.+))?$', 'business'),
    ]:
        if m:=re.match(pattern,t,re.I):
            return ParsedCommand(command,{'details':m.group(1) or ''})
    if m:=re.match(r'^(mechanic|handyman)(?:\s+(.+))?$',t,re.I): return ParsedCommand(m.group(1).lower(),{'details':m.group(2) or ''})
    if m:=re.match(r'^(cv|resume)(?:\s+(.+))?$',t,re.I): return ParsedCommand('cv',{'details':m.group(2) or ''})
    return None
