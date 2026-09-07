from decimal import Decimal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db
from app.core.auth import require_session
from app.core.principal import require_merchant_access, require_user_access
from app.services.commerce import *

router=APIRouter(prefix='/commerce',tags=['commerce'])
class AddItemIn(BaseModel):
 merchant_id: UUID; product_id: UUID; quantity: Decimal=Field(gt=0)
class CheckoutIn(BaseModel):
 cart_id: UUID; delivery_lat: float|None=None; delivery_lng: float|None=None; delivery_fee: Decimal=Field(default=Decimal('0'),ge=0)

@router.get('/food')
async def food(lat:float|None=None,lng:float|None=None,db:AsyncSession=Depends(get_db)):
 return await discover_food(db,lat,lng)
@router.get('/merchants/{merchant_id}/menu')
async def merchant_menu(merchant_id:UUID,db:AsyncSession=Depends(get_db)):
 return await menu(db,merchant_id)
@router.post('/cart/items')
async def cart_add(body:AddItemIn,db:AsyncSession=Depends(get_db),session=Depends(require_session)):
 try:
  result=await add_to_cart(db,UUID(str(session['user_id'])),body.merchant_id,body.product_id,body.quantity); await db.commit(); return result
 except CommerceError as e: await db.rollback(); raise HTTPException(400,str(e))
@router.get('/carts/{cart_id}')
async def cart(cart_id:UUID,db:AsyncSession=Depends(get_db),session=Depends(require_session)):
 try:
  result=await get_cart(db,cart_id)
  if UUID(str(result['cart']['user_id'])) != UUID(str(session['user_id'])): raise HTTPException(403,'cart access denied')
  return result
 except CommerceError as e: raise HTTPException(404,str(e))
@router.post('/checkout')
async def order_checkout(body:CheckoutIn,db:AsyncSession=Depends(get_db),session=Depends(require_session)):
 try:
  result=await checkout(db,UUID(str(session['user_id'])),body.cart_id,body.delivery_lat,body.delivery_lng,body.delivery_fee); await db.commit(); return result
 except CommerceError as e: await db.rollback(); raise HTTPException(400,str(e))
@router.get('/orders/{order_id}')
async def order(order_id:UUID,db:AsyncSession=Depends(get_db),session=Depends(require_session)):
 try:return await get_order(db,UUID(str(session['user_id'])),order_id)
 except CommerceError as e: raise HTTPException(404,str(e))
