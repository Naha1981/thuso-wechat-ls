from decimal import Decimal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.auth import require_session
from app.core.db import get_db
from app.services.commerce import discover_food, menu, get_cart
from app.services.food_delivery import (
    FoodDeliveryError, save_customer_location, get_default_location,
    update_cart_item, customer_orders, order_timeline, cancel_customer_order,
)

router = APIRouter(prefix='/food', tags=['food'])


class LocationIn(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    label: str = Field(default='Saved location', min_length=1, max_length=120)


class CartItemUpdateIn(BaseModel):
    product_id: UUID
    quantity: Decimal = Field(ge=0)


@router.get('/feed')
async def feed(lat: float | None = None, lng: float | None = None, db: AsyncSession = Depends(get_db)):
    merchants = await discover_food(db, lat, lng, limit=20)
    result = []
    for merchant in merchants:
        items = await menu(db, UUID(str(merchant['id'])))
        result.append({**merchant, 'menu_preview': items[:6]})
    return {'vertical': 'food', 'merchants': result}


@router.get('/merchants/{merchant_id}/menu')
async def merchant_food_menu(merchant_id: UUID, db: AsyncSession = Depends(get_db)):
    return {'merchant_id': str(merchant_id), 'items': await menu(db, merchant_id)}


@router.get('/location')
async def location(db: AsyncSession = Depends(get_db), session=Depends(require_session)):
    return {'location': await get_default_location(db, UUID(str(session['user_id'])))}


@router.put('/location')
async def save_location(body: LocationIn, db: AsyncSession = Depends(get_db), session=Depends(require_session)):
    row = await save_customer_location(db, UUID(str(session['user_id'])), body.latitude, body.longitude, body.label)
    await db.commit()
    return {'location': row}


@router.patch('/cart/items')
async def change_cart_item(body: CartItemUpdateIn, db: AsyncSession = Depends(get_db), session=Depends(require_session)):
    try:
        result = await update_cart_item(db, UUID(str(session['user_id'])), body.product_id, body.quantity)
        await db.commit()
        return result
    except FoodDeliveryError as exc:
        await db.rollback()
        raise HTTPException(409, str(exc))


@router.get('/orders')
async def orders(db: AsyncSession = Depends(get_db), session=Depends(require_session)):
    return {'orders': await customer_orders(db, UUID(str(session['user_id'])))}


@router.get('/orders/{order_id}/timeline')
async def timeline(order_id: UUID, db: AsyncSession = Depends(get_db), session=Depends(require_session)):
    try:
        return await order_timeline(db, UUID(str(session['user_id'])), order_id)
    except FoodDeliveryError as exc:
        raise HTTPException(404, str(exc))


@router.post('/orders/{order_id}/cancel')
async def cancel(order_id: UUID, db: AsyncSession = Depends(get_db), session=Depends(require_session)):
    try:
        row = await cancel_customer_order(db, UUID(str(session['user_id'])), order_id)
        await db.commit()
        return {'order': row}
    except FoodDeliveryError as exc:
        await db.rollback()
        raise HTTPException(409, str(exc))
