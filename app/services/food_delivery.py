from __future__ import annotations
from decimal import Decimal
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class FoodDeliveryError(Exception):
    pass


async def save_customer_location(db: AsyncSession, user_id: UUID, lat: float, lng: float, label: str = 'WhatsApp location'):
    await db.execute(text("update customer_addresses set is_default=false,updated_at=now() where user_id=:uid and is_default=true"), {'uid': user_id})
    row = (await db.execute(text("""
        insert into customer_addresses(user_id,label,latitude,longitude,is_default)
        values(:uid,:label,:lat,:lng,true)
        returning *
    """), {'uid': user_id, 'label': label[:120], 'lat': lat, 'lng': lng})).mappings().one()
    return dict(row)


async def get_default_location(db: AsyncSession, user_id: UUID):
    row = (await db.execute(text("""
        select id,label,latitude,longitude,is_default,created_at,updated_at
        from customer_addresses where user_id=:uid and is_default=true limit 1
    """), {'uid': user_id})).mappings().first()
    return dict(row) if row else None


async def update_cart_item(db: AsyncSession, user_id: UUID, product_id: UUID, quantity: Decimal):
    item = (await db.execute(text("""
        select ci.cart_id,ci.product_id,ci.quantity,p.merchant_id,p.stock_quantity,p.price
        from commerce_cart_items ci join commerce_carts c on c.id=ci.cart_id
        join pos_products p on p.id=ci.product_id
        where c.user_id=:uid and c.status='active' and ci.product_id=:pid
        order by c.updated_at desc limit 1 for update
    """), {'uid': user_id, 'pid': product_id})).mappings().first()
    if not item:
        raise FoodDeliveryError('cart item not found')
    if quantity < 0:
        raise FoodDeliveryError('quantity cannot be negative')
    if quantity == 0:
        await db.execute(text('delete from commerce_cart_items where cart_id=:cid and product_id=:pid'), {'cid': item['cart_id'], 'pid': product_id})
    else:
        if quantity > Decimal(str(item['stock_quantity'])):
            raise FoodDeliveryError('insufficient stock')
        await db.execute(text('update commerce_cart_items set quantity=:qty,unit_price=:price,updated_at=now() where cart_id=:cid and product_id=:pid'), {'qty': quantity, 'price': item['price'], 'cid': item['cart_id'], 'pid': product_id})
    from app.services.commerce import get_cart
    return await get_cart(db, item['cart_id'])


async def customer_orders(db: AsyncSession, user_id: UUID, limit: int = 20):
    rows = (await db.execute(text("""
        select o.id,o.merchant_id,p.business_name merchant_name,o.status,o.currency,o.subtotal,o.delivery_fee,o.total,
               o.delivery_request_id,o.created_at,o.updated_at
        from commerce_orders o join providers p on p.id=o.merchant_id
        where o.user_id=:uid order by o.created_at desc limit :limit
    """), {'uid': user_id, 'limit': limit})).mappings().all()
    return [dict(r) for r in rows]


async def order_timeline(db: AsyncSession, user_id: UUID, order_id: UUID):
    owner = (await db.execute(text('select id from commerce_orders where id=:oid and user_id=:uid'), {'oid': order_id, 'uid': user_id})).first()
    if not owner:
        raise FoodDeliveryError('order not found')
    events = (await db.execute(text("""
        select event_type,actor_type,payload,created_at from commerce_events
        where order_id=:oid order by created_at asc
    """), {'oid': order_id})).mappings().all()
    delivery = (await db.execute(text("""
        select id,status,eta_seconds,distance_m,assigned_at,picked_up_at,delivered_at,updated_at
        from delivery_jobs where order_id=:oid
    """), {'oid': order_id})).mappings().first()
    delivery_events = []
    if delivery:
        delivery_events = (await db.execute(text("""
            select event_type,actor_type,payload,created_at from delivery_events
            where delivery_job_id=:jid order by created_at asc
        """), {'jid': delivery['id']})).mappings().all()
    return {
        'order_id': str(order_id),
        'events': [dict(e) for e in events],
        'delivery': dict(delivery) if delivery else None,
        'delivery_events': [dict(e) for e in delivery_events],
    }


async def cancel_customer_order(db: AsyncSession, user_id: UUID, order_id: UUID, reason: str = 'Cancelled by customer'):
    row = (await db.execute(text("""
        update commerce_orders set status='cancelled',rejection_reason=:reason,updated_at=now()
        where id=:oid and user_id=:uid and status='pending_payment' returning *
    """), {'oid': order_id, 'uid': user_id, 'reason': reason[:500]})).mappings().first()
    if not row:
        raise FoodDeliveryError('order cannot be cancelled at its current status')
    await db.execute(text("""
        insert into commerce_events(order_id,event_type,actor_type,actor_id,payload)
        values(:oid,'order.cancelled','customer',:uid,cast(:payload as jsonb))
    """), {'oid': order_id, 'uid': user_id, 'payload': '{"reason":"' + reason.replace('"','\\"') + '"}'})
    return dict(row)
