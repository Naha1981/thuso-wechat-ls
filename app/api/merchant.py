from decimal import Decimal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db
from app.services.merchant_os import *

router=APIRouter(prefix='/merchants',tags=['merchant'])

async def require_internal(x_internal_secret: str|None=Header(default=None), db: AsyncSession=Depends(get_db)):
    from app.core.config import get_settings
    secret=get_settings().internal_webhook_secret
    if not secret or x_internal_secret != secret: raise HTTPException(401,'merchant API requires authenticated merchant session')
    return db

class MenuItemIn(BaseModel):
    name: str = Field(min_length=1,max_length=160)
    price: Decimal = Field(ge=0)
    sku: str|None = Field(default=None,max_length=80)
class StockIn(BaseModel):
    quantity: Decimal = Field(ge=0)
class ActionIn(BaseModel):
    reason: str|None = Field(default=None,max_length=500)

@router.get('/{merchant_id}/orders')
async def orders(merchant_id:UUID,db:AsyncSession=Depends(require_internal)):
    return {'orders':await merchant_orders(db,merchant_id)}

@router.get('/{merchant_id}/orders/{order_id}')
async def order(merchant_id:UUID,order_id:UUID,db:AsyncSession=Depends(require_internal)):
    try:return await merchant_order(db,merchant_id,order_id)
    except ValueError as e: raise HTTPException(404,str(e))

@router.post('/{merchant_id}/orders/{order_id}/{action}')
async def action(merchant_id:UUID,order_id:UUID,action:str,body:ActionIn=ActionIn(),db:AsyncSession=Depends(require_internal)):
    if action not in {'accept','reject','preparing','ready','complete','cancel'}: raise HTTPException(422,'invalid action')
    try:
        result=await merchant_transition(db,merchant_id,order_id,action,body.reason); await db.commit(); return result
    except ValueError as e: await db.rollback(); raise HTTPException(409,str(e))

@router.get('/{merchant_id}/menu')
async def menu(merchant_id:UUID,db:AsyncSession=Depends(require_internal)): return {'items':await merchant_menu(db,merchant_id)}

@router.post('/{merchant_id}/menu/items')
async def add_item(merchant_id:UUID,body:MenuItemIn,db:AsyncSession=Depends(require_internal)):
    try: row=await add_menu_item(db,merchant_id,body.name,body.price,body.sku); await db.commit(); return row
    except ValueError as e: await db.rollback(); raise HTTPException(400,str(e))

@router.patch('/{merchant_id}/menu/items/{product_id}/stock')
async def stock(merchant_id:UUID,product_id:UUID,body:StockIn,db:AsyncSession=Depends(require_internal)):
    try: row=await update_stock(db,merchant_id,product_id,body.quantity); await db.commit(); return row
    except ValueError as e: await db.rollback(); raise HTTPException(404,str(e))

@router.get('/{merchant_id}/sales')
async def sales(merchant_id:UUID,db:AsyncSession=Depends(require_internal)): return await merchant_sales_summary(db,merchant_id)
