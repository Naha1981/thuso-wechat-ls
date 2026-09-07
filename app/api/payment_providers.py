from fastapi import APIRouter, HTTPException
from app.payments.registry import get_payment_registry
router=APIRouter(prefix='/payment-providers',tags=['payment-providers'])
@router.get('/LS')
async def lesotho_payment_providers(): return {'country':'LS','currency':'LSL','providers':get_payment_registry().list()}
