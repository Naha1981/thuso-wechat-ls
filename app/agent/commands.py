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
    if m:=re.match(r'^ride(?:\s+(.+))?$',t,re.I): return ParsedCommand('ride',{'details':m.group(1) or ''})
    if m:=re.match(r'^(mechanic|handyman)(?:\s+(.+))?$',t,re.I): return ParsedCommand(m.group(1).lower(),{'details':m.group(2) or ''})
    if m:=re.match(r'^(cv|resume)(?:\s+(.+))?$',t,re.I): return ParsedCommand('cv',{'details':m.group(2) or ''})
    return None
