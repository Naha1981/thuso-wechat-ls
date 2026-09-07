from __future__ import annotations
import json
import re
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.payments import create_payment
from app.services.outbox import enqueue, enqueue_channel

class CommerceError(Exception): pass

TWOPLACES = Decimal('0.01')
def money(v) -> Decimal: return Decimal(str(v)).quantize(TWOPLACES, rounding=ROUND_HALF_UP)

def parse_commerce_command(text_in: str) -> tuple[str, dict] | None:
    s=(text_in or '').strip()
    u=s.upper()
    if u in ('MENU','FOOD','RESTAURANTS'): return ('menu',{})
    m=re.match(r'^(?:MENU|CATALOG)\s+([0-9a-fA-F-]{36})$',s,re.I)
    if m: return ('merchant_menu',{'merchant_id':m.group(1)})
    if u in ('CART','MY CART'): return ('cart',{})
    if u in ('CHECKOUT','PAY'): return ('checkout',{})
    m=re.match(r'^(?:ADD|BUY)\s+([0-9a-fA-F-]{36})\s+(\d+(?:\.\d+)?)$',s,re.I)
    if m: return ('add',{'product_id':m.group(1),'quantity':Decimal(m.group(2))})
    m=re.match(r'^ADD\s+(\d+)\s+(\d+(?:\.\d+)?)$',s,re.I)
    if m: return ('add_index',{'index':int(m.group(1)),'quantity':Decimal(m.group(2))})
    return None

async def discover_food(db: AsyncSession, lat: float|None=None, lng: float|None=None, limit: int=10):
    if lat is not None and lng is not None:
        q='''select p.id,p.business_name,p.category,st_distance(pl.location,st_setsrid(st_makepoint(:lng,:lat),4326)::geography) distance_m
             from providers p join provider_locations pl on pl.provider_id=p.id
             where p.category='food' and p.status='active' and pl.is_active=true
             order by distance_m asc limit :limit'''
        rows=(await db.execute(text(q),{'lat':lat,'lng':lng,'limit':limit})).mappings().all()
    else:
        rows=(await db.execute(text('''select id,business_name,category,null::numeric distance_m from providers where category='food' and status='active' order by business_name limit :limit'''),{'limit':limit})).mappings().all()
    return [dict(r) for r in rows]

async def menu(db: AsyncSession, merchant_id: UUID):
    rows=(await db.execute(text('''select id,name,sku,price,stock_quantity from pos_products where merchant_id=:mid and stock_quantity>0 order by name'''),{'mid':merchant_id})).mappings().all()
    return [dict(r) for r in rows]

async def get_or_create_cart(db: AsyncSession, user_id: UUID, merchant_id: UUID, currency='LSL'):
    row=(await db.execute(text('''select * from commerce_carts where user_id=:uid and merchant_id=:mid and status='active' for update'''),{'uid':user_id,'mid':merchant_id})).mappings().first()
    if row: return dict(row)
    row=(await db.execute(text('''insert into commerce_carts(user_id,merchant_id,currency) values(:uid,:mid,:currency) returning *'''),{'uid':user_id,'mid':merchant_id,'currency':currency})).mappings().one()
    return dict(row)

async def add_to_cart(db: AsyncSession, user_id: UUID, merchant_id: UUID, product_id: UUID, quantity: Decimal):
    if quantity <= 0: raise CommerceError('quantity must be positive')
    cart=await get_or_create_cart(db,user_id,merchant_id)
    product=(await db.execute(text('select id,merchant_id,name,price,stock_quantity from pos_products where id=:id and merchant_id=:mid for update'),{'id':product_id,'mid':merchant_id})).mappings().first()
    if not product: raise CommerceError('product not found')
    existing=(await db.execute(text('select quantity from commerce_cart_items where cart_id=:cid and product_id=:pid for update'),{'cid':cart['id'],'pid':product_id})).scalar_one_or_none()
    new_qty=Decimal(str(existing or 0))+quantity
    if new_qty > Decimal(str(product['stock_quantity'])): raise CommerceError('insufficient stock')
    await db.execute(text('''insert into commerce_cart_items(cart_id,product_id,quantity,unit_price) values(:cid,:pid,:qty,:price)
      on conflict(cart_id,product_id) do update set quantity=:qty,unit_price=:price,updated_at=now()'''),{'cid':cart['id'],'pid':product_id,'qty':new_qty,'price':product['price']})
    return await get_cart(db,cart['id'])

async def get_cart(db: AsyncSession, cart_id: UUID):
    cart=(await db.execute(text('select * from commerce_carts where id=:id'),{'id':cart_id})).mappings().first()
    if not cart: raise CommerceError('cart not found')
    items=(await db.execute(text('''select ci.product_id,p.name,ci.quantity,ci.unit_price,(ci.quantity*ci.unit_price) line_total
      from commerce_cart_items ci join pos_products p on p.id=ci.product_id where ci.cart_id=:cid order by p.name'''),{'cid':cart_id})).mappings().all()
    subtotal=sum((money(r['line_total']) for r in items),Decimal('0'))
    return {'cart':dict(cart),'items':[dict(r) for r in items],'subtotal':money(subtotal)}

async def checkout(db: AsyncSession, user_id: UUID, cart_id: UUID, delivery_lat: float|None=None, delivery_lng: float|None=None, delivery_fee: Decimal=Decimal('0')):
    cart=(await db.execute(text('select * from commerce_carts where id=:id and user_id=:uid and status=\'active\' for update'),{'id':cart_id,'uid':user_id})).mappings().first()
    if not cart: raise CommerceError('active cart not found')
    items=(await db.execute(text('''select ci.product_id,p.name,p.stock_quantity,ci.quantity,p.price
      from commerce_cart_items ci join pos_products p on p.id=ci.product_id where ci.cart_id=:cid for update'''),{'cid':cart_id})).mappings().all()
    if not items: raise CommerceError('cart is empty')
    subtotal=Decimal('0')
    for item in items:
        if Decimal(str(item['quantity'])) > Decimal(str(item['stock_quantity'])): raise CommerceError(f'insufficient stock for {item["name"]}')
        subtotal += money(Decimal(str(item['quantity']))*Decimal(str(item['price'])))
    delivery_fee=money(delivery_fee); total=money(subtotal+delivery_fee)
    for item in items:
        await db.execute(text('update pos_products set stock_quantity=stock_quantity-:qty where id=:id'),{'qty':item['quantity'],'id':item['product_id']})
    ref=f'NHAFOOD{str(UUID(int=UUID(str(cart["id"])).int)).replace("-","")[:24].upper()}'
    payment=await create_payment(db,user_id,total,ref,currency='LSL')
    order=(await db.execute(text('''insert into commerce_orders(user_id,merchant_id,cart_id,payment_id,status,currency,subtotal,delivery_fee,total,delivery_lat,delivery_lng,metadata)
      values(:uid,:mid,:cid,:pid,'pending_payment','LSL',:sub,:fee,:total,:lat,:lng,cast(:meta as jsonb)) returning *'''),{'uid':user_id,'mid':cart['merchant_id'],'cid':cart_id,'pid':payment['id'],'sub':subtotal,'fee':delivery_fee,'total':total,'lat':delivery_lat,'lng':delivery_lng,'meta':json.dumps({'payment_reference':payment['reference']})})).mappings().one()
    for item in items:
        await db.execute(text('''insert into commerce_order_items(order_id,product_id,product_name,quantity,unit_price,line_total)
          values(:oid,:pid,:name,:qty,:price,:line)'''),{'oid':order['id'],'pid':item['product_id'],'name':item['name'],'qty':item['quantity'],'price':item['price'],'line':money(Decimal(str(item['quantity']))*Decimal(str(item['price'])))})
    await db.execute(text("update commerce_carts set status='checked_out',updated_at=now() where id=:id"),{'id':cart_id})
    await db.execute(text("insert into commerce_events(order_id,event_type,actor_type,actor_id,payload) values(:oid,'order.created','customer',:uid,cast(:payload as jsonb))"),{'oid':order['id'],'uid':user_id,'payload':json.dumps({'total':str(total),'payment_id':str(payment['id'])})})
    await enqueue(db,'commerce_order',order['id'],'commerce.order_created',{'user_id':str(user_id),'merchant_id':str(cart['merchant_id']),'payment_id':str(payment['id']),'total':str(total)})
    return {'order':dict(order),'payment':payment}

async def mark_order_paid(db: AsyncSession, payment_id: UUID):
    row=(await db.execute(text('''update commerce_orders set status='paid',updated_at=now() where payment_id=:pid and status='pending_payment' returning *'''),{'pid':payment_id})).mappings().first()
    if not row: return None
    recipient=(await db.execute(text('select phone_e164 from users where id=:uid'),{'uid':row['user_id']})).scalar_one_or_none()
    await db.execute(text("insert into commerce_events(order_id,event_type,actor_type,payload) values(:oid,'payment.confirmed','system',cast(:payload as jsonb))"),{'oid':row['id'],'payload':json.dumps({'payment_id':str(payment_id)})})
    await enqueue(db,'commerce_order',row['id'],'commerce.payment_confirmed',{'payment_id':str(payment_id),'merchant_id':str(row['merchant_id']),'user_id':str(row['user_id'])})
    if recipient:
        await enqueue_channel(db,'whatsapp',recipient.lstrip('+'),'text',{'body':f'Payment confirmed for order {row["id"]}. Your order is now with the merchant.'})
    return dict(row)

async def get_order(db: AsyncSession, user_id: UUID, order_id: UUID):
    row=(await db.execute(text('''select o.*,p.business_name merchant_name from commerce_orders o join providers p on p.id=o.merchant_id where o.id=:oid and o.user_id=:uid'''),{'oid':order_id,'uid':user_id})).mappings().first()
    if not row: raise CommerceError('order not found')
    items=(await db.execute(text('select product_name,quantity,unit_price,line_total from commerce_order_items where order_id=:oid order by product_name'),{'oid':order_id})).mappings().all()
    return {'order':dict(row),'items':[dict(i) for i in items]}
