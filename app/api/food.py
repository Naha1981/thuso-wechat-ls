from decimal import Decimal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.auth import require_session
from app.core.db import get_db
from app.services.commerce import discover_food, menu, get_cart, checkout, CommerceError
from app.services.payment_orchestration import initiate_routed_payment, PaymentOrchestrationError
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


class CheckoutIn(BaseModel):
    cart_id: UUID
    delivery_fee: Decimal = Field(default=Decimal('0'), ge=0)


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


@router.post('/checkout')
async def food_checkout(body: CheckoutIn, db: AsyncSession = Depends(get_db), session=Depends(require_session)):
    user_id = UUID(str(session['user_id']))
    try:
        location_row = await get_default_location(db, user_id)
        if not location_row:
            raise FoodDeliveryError('delivery location required')
        result = await checkout(
            db, user_id, body.cart_id,
            float(location_row['latitude']), float(location_row['longitude']), body.delivery_fee
        )
        from sqlalchemy import text
        phone = (await db.execute(text('select phone_e164 from users where id=:uid'), {'uid': user_id})).scalar_one_or_none()
        if not phone:
            raise FoodDeliveryError('verified phone number required for payment')
        try:
            result['payment'] = await initiate_routed_payment(db, result['payment']['id'], phone)
        except PaymentOrchestrationError as exc:
            raise FoodDeliveryError(f'payment could not be started: {exc}')
        await db.commit()
        return result
    except (FoodDeliveryError, CommerceError) as exc:
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
