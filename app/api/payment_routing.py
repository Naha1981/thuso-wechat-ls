from decimal import Decimal
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.services.payment_routing import RouteCandidate, choose_route
from app.payments.registry import get_payment_registry

router=APIRouter(prefix='/payment-routing',tags=['payment-routing'])

class RouteIn(BaseModel):
    amount: Decimal = Field(gt=0)
    currency: str = Field(default='LSL', min_length=3, max_length=3)
    channel: str | None = None
    provider: str | None = None

@router.post('/LS/quote')
async def route_quote(body: RouteIn):
    if body.currency != 'LSL':
        raise HTTPException(422,'Lesotho routing endpoint requires LSL')
    candidates=[]
    for item in get_payment_registry().list():
        if body.provider and item['name'] != body.provider: continue
        for ch in item['channels']:
            if body.channel and ch != body.channel: continue
            # Production fee/health values are loaded from the routing policy table.
            # This endpoint intentionally returns a deterministic default policy until
            # merchant-specific pricing/health data is configured.
            candidates.append(RouteCandidate(provider=item['name'],channel=ch,priority=10 if item['name'] in ('mopay_ls','paylesotho') else 20))
    try:
        d=choose_route(body.amount,candidates)
    except ValueError as e:
        raise HTTPException(409,str(e))
    return {'currency':'LSL','amount':str(body.amount),'provider':d.provider,'channel':d.channel,
            'estimated_fee':str(d.estimated_fee),'score':str(d.score),
            'fallback_providers':list(d.fallback_providers),'reason':d.reason}
