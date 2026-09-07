from fastapi import APIRouter, Request, HTTPException
from app.payments.registry import get_payment_registry
from app.services.payment_provider_service import process_provider_webhook, ProviderPaymentError
from app.core.db import get_db
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
router=APIRouter(prefix='/webhooks/payments',tags=['payment-webhooks'])
@router.post('/{provider}')
async def provider_webhook(provider:str, request:Request, db:AsyncSession=Depends(get_db)):
    body=await request.body(); signature=request.headers.get('x-signature') or request.headers.get('x-webhook-signature')
    try: adapter=get_payment_registry().get(provider)
    except KeyError: raise HTTPException(404,'unknown payment provider')
    if not adapter.verify_webhook(body,signature): raise HTTPException(401,'invalid webhook signature')
    try:
        result=await process_provider_webhook(db,provider,adapter.parse_webhook(body)); await db.commit(); return result
    except ProviderPaymentError as e: await db.rollback(); raise HTTPException(422,str(e))
