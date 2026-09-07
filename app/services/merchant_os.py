from __future__ import annotations
import json
import re
from decimal import Decimal
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.outbox import enqueue, enqueue_channel
from app.services.delivery import create_delivery_job

ORDER_STATES = {
    'paid': {'preparing', 'cancelled'},
    'preparing': {'ready', 'cancelled'},
    'ready': {'out_for_delivery', 'completed', 'cancelled'},
    'out_for_delivery': {'completed', 'cancelled'},
}


def parse_merchant_command(text_in: str) -> tuple[str, dict] | None:
    s=(text_in or '').strip()
    u=s.upper()
    if u in {'ORDERS','NEW ORDERS','MY ORDERS'}: return 'orders', {}
    m=re.match(r'^(?:ORDER|VIEW)\s+([0-9a-fA-F-]{36})$',s,re.I)
    if m: return 'order', {'order_id': m.group(1)}
    for command, words in {
        'accept': ('ACCEPT','ACCEPT ORDER'),
        'reject': ('REJECT','REJECT ORDER','DECLINE','DECLINE ORDER'),
        'preparing': ('PREPARING','START ORDER','START'),
        'ready': ('READY','READY ORDER'),
        'complete': ('COMPLETE','COMPLETE ORDER','DONE'),
        'cancel': ('CANCEL','CANCEL ORDER'),
    }.items():
        for word in words:
            m=re.match(r'^'+re.escape(word)+r'\s+([0-9a-fA-F-]{36})(?:\s+(.+))?$',s,re.I)
            if m:
                return command, {'order_id':m.group(1), 'reason':m.group(2)}
    if u in {'MENU','MANAGE MENU'}: return 'menu', {}
    m=re.match(r'^(?:ADD ITEM|ADD PRODUCT)\s+(.+?)\s+([0-9]+(?:\.[0-9]{1,2})?)$',s,re.I)
    if m: return 'add_item', {'name':m.group(1).strip(), 'price':m.group(2)}
    m=re.match(r'^STOCK\s+([0-9a-fA-F-]{36})\s+([0-9]+(?:\.[0-9]{1,3})?)$',s,re.I)
    if m: return 'stock', {'product_id':m.group(1), 'quantity':m.group(2)}
    if u in {'EARNINGS','SALES','MERCHANT BALANCE'}: return 'earnings', {}
    return None


async def merchant_by_phone(db: AsyncSession, phone: str):
    return (await db.execute(text("""select * from providers where phone_e164=:phone and category='food' limit 1"""), {'phone':phone})).mappings().first()

async def merchant_orders(db: AsyncSession, merchant_id: UUID, limit: int=20):
    rows=(await db.execute(text("""select o.id,o.user_id,o.status,o.currency,o.subtotal,o.delivery_fee,o.total,
        o.delivery_lat,o.delivery_lng,o.created_at,o.accepted_at,o.preparing_at,o.ready_at,
        o.completed_at,o.rejection_reason,p.phone_e164 customer_phone
      from commerce_orders o join users p on p.id=o.user_id
      where o.merchant_id=:mid and o.status not in ('completed','cancelled','refunded')
      order by o.created_at desc limit :limit"""), {'mid':merchant_id,'limit':limit})).mappings().all()
    return [dict(r) for r in rows]

async def merchant_order(db: AsyncSession, merchant_id: UUID, order_id: UUID):
    row=(await db.execute(text("""select o.*,u.phone_e164 customer_phone,u.display_name customer_name
      from commerce_orders o join users u on u.id=o.user_id
      where o.id=:oid and o.merchant_id=:mid for update"""), {'oid':order_id,'mid':merchant_id})).mappings().first()
    if not row: raise ValueError('order not found')
    items=(await db.execute(text("""select product_id,product_name,quantity,unit_price,line_total
      from commerce_order_items where order_id=:oid order by product_name"""), {'oid':order_id})).mappings().all()
    return {'order':dict(row),'items':[dict(x) for x in items]}

async def _notify_customer(db: AsyncSession, order: dict, body: str):
    phone=order.get('customer_phone')
    if phone:
        await enqueue_channel(db,'whatsapp',phone.lstrip('+'),'text',{'body':body})

async def _event(db: AsyncSession, merchant_id: UUID, order_id: UUID, event_type: str, payload: dict):
    await db.execute(text("""insert into merchant_events(merchant_id,order_id,event_type,actor_type,actor_id,payload)
      values(:mid,:oid,:type,'merchant',:mid,cast(:payload as jsonb))"""),
      {'mid':merchant_id,'oid':order_id,'type':event_type,'payload':json.dumps(payload)})
    await enqueue(db,'commerce_order',order_id,f'commerce.merchant_{event_type}',payload)

async def merchant_transition(db: AsyncSession, merchant_id: UUID, order_id: UUID, action: str, reason: str|None=None):
    row=(await db.execute(text("""select o.*,u.phone_e164 customer_phone,p.business_name merchant_name,
        p.location as merchant_location
      from commerce_orders o join users u on u.id=o.user_id join providers p on p.id=o.merchant_id
      where o.id=:oid and o.merchant_id=:mid for update"""), {'oid':order_id,'mid':merchant_id})).mappings().first()
    if not row: raise ValueError('order not found')
    current=row['status']
    if action == 'accept': new='preparing'
    elif action == 'reject': new='cancelled'
    elif action == 'preparing': new='preparing'
    elif action == 'ready': new='ready'
    elif action == 'complete': new='completed'
    elif action == 'cancel': new='cancelled'
    else: raise ValueError('unsupported merchant action')
    if new not in ORDER_STATES.get(current,set()):
        raise ValueError(f'cannot transition {current} to {new}')
    if new == 'cancelled' and not reason:
        reason='Merchant cancelled the order.'
    timestamp_column={'preparing':'preparing_at','ready':'ready_at','completed':'completed_at','cancelled':None}.get(new)
    if new == 'cancelled':
        await db.execute(text("update commerce_orders set status='cancelled',rejection_reason=:reason,updated_at=now() where id=:oid"), {'oid':order_id,'reason':reason})
    elif new == 'preparing' and current == 'paid':
        await db.execute(text("update commerce_orders set status='preparing',accepted_at=coalesce(accepted_at,now()),preparing_at=now(),updated_at=now() where id=:oid"), {'oid':order_id})
    elif new == 'ready':
        await db.execute(text("update commerce_orders set status='ready',ready_at=now(),updated_at=now() where id=:oid"), {'oid':order_id})
    elif new == 'completed':
        await db.execute(text("update commerce_orders set status='completed',completed_at=now(),updated_at=now() where id=:oid"), {'oid':order_id})
    else:
        await db.execute(text("update commerce_orders set status=:status,updated_at=now() where id=:oid"), {'status':new,'oid':order_id})
    payload={'order_id':str(order_id),'from':current,'to':new}
    if reason: payload['reason']=reason
    await _event(db,merchant_id,order_id,f'order_{new}',payload)
    fresh=(await db.execute(text("select * from commerce_orders where id=:oid"),{'oid':order_id})).mappings().one()
    fresh=dict(fresh); fresh['customer_phone']=row['customer_phone']
    messages={
      'preparing':f"Order {order_id} accepted and is being prepared.",
      'ready':f"Order {order_id} is ready.",
      'completed':f"Order {order_id} has been completed. Thank you.",
      'cancelled':f"Order {order_id} was cancelled by the merchant. {reason or ''}".strip(),
    }
    await _notify_customer(db,fresh,messages[new])
    if new == 'ready' and row['delivery_lat'] is not None and row['delivery_lng'] is not None:
        coords=(await db.execute(text("""select st_y(location::geometry) lat, st_x(location::geometry) lng
          from providers where id=:mid"""), {'mid':merchant_id})).mappings().first()
        if coords and coords['lat'] is not None:
            job=await create_delivery_job(db,row['user_id'],order_id,merchant_id,float(coords['lat']),float(coords['lng']),float(row['delivery_lat']),float(row['delivery_lng']),Decimal(str(row['delivery_fee'] or 0)))
            await db.execute(text("update commerce_orders set delivery_request_id=(select service_request_id from delivery_jobs where id=:jid),status='out_for_delivery',updated_at=now() where id=:oid"),{'jid':job['id'],'oid':order_id})
            fresh['status']='out_for_delivery'; fresh['delivery_request_id']=job['service_request_id']
    return {'order':fresh,'status':fresh['status']}

async def merchant_menu(db: AsyncSession, merchant_id: UUID):
    rows=(await db.execute(text("""select id,name,sku,price,stock_quantity,created_at
      from pos_products where merchant_id=:mid order by name"""),{'mid':merchant_id})).mappings().all()
    return [dict(x) for x in rows]

async def add_menu_item(db: AsyncSession, merchant_id: UUID, name: str, price: Decimal, sku: str|None=None):
    if not name.strip() or price < 0: raise ValueError('invalid item')
    sku=(sku or re.sub(r'[^A-Z0-9]+','-',name.upper()).strip('-'))[:80] or 'ITEM'
    row=(await db.execute(text("""insert into pos_products(merchant_id,name,sku,price,stock_quantity)
      values(:mid,:name,:sku,:price,0) returning *"""),{'mid':merchant_id,'name':name.strip()[:160],'sku':sku,'price':price})).mappings().one()
    return dict(row)

async def update_stock(db: AsyncSession, merchant_id: UUID, product_id: UUID, quantity: Decimal):
    row=(await db.execute(text("""update pos_products set stock_quantity=:qty where id=:pid and merchant_id=:mid returning *"""),{'qty':quantity,'pid':product_id,'mid':merchant_id})).mappings().first()
    if not row: raise ValueError('product not found')
    return dict(row)

async def merchant_sales_summary(db: AsyncSession, merchant_id: UUID):
    row=(await db.execute(text("""select count(*) filter(where status not in ('cancelled','refunded'))::int orders,
      count(*) filter(where status='completed')::int completed_orders,
      coalesce(sum(total) filter(where status not in ('cancelled','refunded')),0) gross_sales,
      coalesce(sum(total) filter(where status='completed'),0) completed_sales
      from commerce_orders where merchant_id=:mid"""),{'mid':merchant_id})).mappings().one()
    return dict(row)
