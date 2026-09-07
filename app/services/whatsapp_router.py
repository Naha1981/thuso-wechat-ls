from __future__ import annotations
import uuid
from decimal import Decimal
from types import SimpleNamespace
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.agent import AgentMessageIn, process_message, ConfirmIn, confirm
from app.services.outbox import enqueue_channel
from app.services.provider_os import (
    parse_provider_command, get_provider_by_phone, start_onboarding,
    provider_offers, provider_accept, provider_reject, provider_transition,
    provider_earnings_summary, set_online,
)
from app.services.commerce import (
    parse_commerce_command, discover_food, menu, get_cart, add_to_cart,
    checkout, CommerceError,
)
from app.services.merchant_os import (
    parse_merchant_command, merchant_by_phone, merchant_orders, merchant_order,
    merchant_transition, merchant_menu, add_menu_item, update_stock,
    merchant_sales_summary,
)
from app.services.payment_orchestration import initiate_routed_payment, PaymentOrchestrationError
from app.services.delivery import get_delivery, transition_delivery, add_proof, confirm_delivery_receipt


async def handle_whatsapp_message(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    phone_e164: str,
    message: dict,
) -> SimpleNamespace:
    """Single channel-neutral WhatsApp command surface.

    Both Meta-shaped and Baileys-shaped ingress adapters must call this function.
    It is deliberately independent of transport so command behavior cannot drift
    between WhatsApp transports.
    """
    body = str(message.get('body') or '')
    message_type = str(message.get('type') or 'text')
    media_id = message.get('media_id')
    button_action = _confirmation_from_message(body)

    provider = await get_provider_by_phone(db, phone_e164)
    merchant = await merchant_by_phone(db, phone_e164)
    command_text = body
    provider_cmd = parse_provider_command(command_text) if command_text else None
    delivery_cmd = _parse_delivery_command(command_text) if command_text else None
    merchant_cmd = parse_merchant_command(command_text) if command_text else None
    commerce_cmd = parse_commerce_command(command_text) if command_text else None

    if button_action:
        approved, action_id = button_action
        result = await confirm(
            ConfirmIn(user_id=user_id, action_id=action_id, approved=approved), db
        )
        body_text = result.get('status', 'processed') if isinstance(result, dict) else 'Processed.'
        return _out(body_text)

    if merchant and merchant_cmd:
        return await _merchant(db, merchant, merchant_cmd)

    if commerce_cmd:
        return await _commerce(db, user_id, phone_e164, commerce_cmd)

    if delivery_cmd and provider and provider.get('category') == 'delivery':
        return await _delivery(db, provider, user_id, delivery_cmd, phone_e164, media_id)

    if body.upper().startswith('CONFIRM DELIVERY '):
        return await _customer_confirm_delivery(db, user_id, body)

    if provider_cmd and (provider or provider_cmd[0] == 'onboard'):
        return await _provider(db, provider, user_id, provider_cmd, phone_e164)

    if message_type in {'image','video','audio','document','sticker'} and not body:
        labels={'image':'Image','video':'Video','audio':'Voice note','document':'Document','sticker':'Sticker'}
        return _out(f"{labels.get(message_type, 'Media')} received.")

    out = await process_message(
        AgentMessageIn(
            user_id=user_id,
            text=body or 'help',
            channel='whatsapp',
            external_message_id=message.get('id'),
            latitude=message.get('latitude'),
            longitude=message.get('longitude'),
        ),
        db,
    )
    return out


async def _merchant(db, merchant, parsed):
    command, args = parsed
    try:
        if merchant['status'] not in ('active', 'pending', 'paused'):
            raise ValueError('merchant account is not currently available')
        if command == 'orders':
            rows = await merchant_orders(db, merchant['id'])
            body = 'No open orders.' if not rows else '\n'.join(
                f"ORDER {r['id']} — {r['status']} — {r['total']} {r['currency']}\nVIEW {r['id']}" for r in rows
            )
        elif command == 'order':
            data = await merchant_order(db, merchant['id'], uuid.UUID(args['order_id']))
            o = data['order']
            lines = '\n'.join(f"{i['product_name']} x{i['quantity']} = {i['line_total']}" for i in data['items'])
            body = f"ORDER {o['id']}\nStatus: {o['status']}\nCustomer: {o.get('customer_name') or o.get('customer_phone')}\n{lines}\nTotal: {o['total']} {o['currency']}"
        elif command in ('accept', 'reject', 'preparing', 'ready', 'complete', 'cancel'):
            result = await merchant_transition(db, merchant['id'], uuid.UUID(args['order_id']), command, args.get('reason'))
            body = f"Order {args['order_id']} is now {result['status']}."
        elif command == 'menu':
            rows = await merchant_menu(db, merchant['id'])
            body = ('Your menu:\n' + '\n'.join(
                f"{r['id']} — {r['name']} — {r['price']} LSL — stock {r['stock_quantity']}" for r in rows
            )) if rows else 'Your menu is empty. Reply: ADD ITEM <name> <price>'
        elif command == 'add_item':
            row = await add_menu_item(db, merchant['id'], args['name'], Decimal(args['price']))
            body = f"Added {row['name']} to your menu at {row['price']} LSL. Stock is 0.\nReply: STOCK {row['id']} <quantity>"
        elif command == 'stock':
            row = await update_stock(db, merchant['id'], uuid.UUID(args['product_id']), Decimal(args['quantity']))
            body = f"Stock updated: {row['name']} = {row['stock_quantity']}."
        elif command == 'earnings':
            sales = await merchant_sales_summary(db, merchant['id'])
            body = f"Orders: {sales['orders']}\nCompleted: {sales['completed_orders']}\nGross sales: {sales['gross_sales']} LSL\nCompleted sales: {sales['completed_sales']} LSL"
        else:
            body = 'Unknown merchant command.'
    except (ValueError, KeyError) as exc:
        body = f'Unable to process that: {exc}'
    return _out(body)


async def _commerce(db, user_id, phone_e164, parsed):
    command, args = parsed
    try:
        if command == 'menu':
            merchants = await discover_food(db)
            body = 'Food merchants:\n' + '\n'.join(f"{m['business_name']} — MENU {m['id']}" for m in merchants) if merchants else 'No food merchants are currently online.'
        elif command == 'merchant_menu':
            rows = await menu(db, uuid.UUID(args['merchant_id']))
            body = 'Menu:\n' + '\n'.join(f"{r['name']} — {r['price']} LSL — ADD {r['id']} 1" for r in rows) if rows else 'This merchant has no items available.'
        elif command == 'add':
            pid = uuid.UUID(args['product_id'])
            product = (await db.execute(text('select merchant_id,name from pos_products where id=:id'), {'id': pid})).mappings().first()
            if not product:
                raise CommerceError('product not found')
            cart = await add_to_cart(db, user_id, product['merchant_id'], pid, args['quantity'])
            body = f"Added to cart. Subtotal: {cart['subtotal']} {cart['cart']['currency']}. Reply CART or CHECKOUT."
        elif command == 'add_index':
            raise CommerceError('Use ADD <product_id> <quantity> from the menu.')
        elif command == 'cart':
            cartrow = (await db.execute(text("select id from commerce_carts where user_id=:uid and status='active' order by updated_at desc limit 1"), {'uid': user_id})).scalar_one_or_none()
            if not cartrow:
                body = 'Your cart is empty.'
            else:
                c = await get_cart(db, cartrow)
                body = 'Cart:\n' + '\n'.join(f"{i['name']} x{i['quantity']} = {i['line_total']}" for i in c['items']) + f"\nSubtotal: {c['subtotal']} {c['cart']['currency']}\nReply CHECKOUT to pay."
        elif command == 'checkout':
            cartrow = (await db.execute(text("select id from commerce_carts where user_id=:uid and status='active' order by updated_at desc limit 1"), {'uid': user_id})).scalar_one_or_none()
            if not cartrow:
                raise CommerceError('your cart is empty')
            result = await checkout(db, user_id, cartrow)
            try:
                payment = await initiate_routed_payment(db, result['payment']['id'], phone_e164)
                body = f"Order {result['order']['id']} created. Pay here: {payment.get('checkout_url') or payment.get('paymentUrl') or 'payment link unavailable'}"
            except PaymentOrchestrationError as exc:
                body = f"Order {result['order']['id']} created, but payment could not be started yet: {exc}"
        else:
            body = 'Unknown commerce command.'
    except (ValueError, CommerceError, PaymentOrchestrationError) as exc:
        body = f'Unable to process that: {exc}'
    return _out(body)


async def _provider(db, provider, user_id, parsed, phone_e164):
    command, args = parsed
    try:
        if command == 'onboard':
            result = await start_onboarding(db, user_id, args.get('category'), args.get('business_name'))
            body = result['prompt']
        elif command == 'business':
            result = await start_onboarding(db, user_id, None, args.get('business_name'))
            body = result['prompt']
        elif not provider:
            body = 'No provider account found. Reply: PROVIDER <category> <business name>'
        elif provider['status'] not in ('active', 'pending', 'paused'):
            body = 'Your provider account is not currently available.'
        elif command == 'offers':
            rows = await provider_offers(db, provider['id'])
            body = 'No open jobs.' if not rows else '\n'.join(
                f"JOB {r['id']} — {r['category']} — {r['pickup_lat']},{r['pickup_lng']}\nACCEPT {r['id']}" for r in rows
            )
        elif command == 'accept':
            if provider['status'] != 'active':
                raise ValueError('go ONLINE before accepting jobs')
            rid = await provider_accept(db, provider['id'], uuid.UUID(args['offer_id']))
            req = (await db.execute(text("select u.phone_e164 from service_requests r join users u on u.id=r.user_id where r.id=:id"), {'id': rid})).scalar_one_or_none()
            if req:
                await enqueue_channel(db, 'whatsapp', req.lstrip('+'), 'text', {'body': f'Provider accepted your request. Request ID: {rid}'})
            body = f'Job accepted. Request ID: {rid}'
        elif command == 'reject':
            await provider_reject(db, provider['id'], uuid.UUID(args['offer_id']))
            body = 'Job declined.'
        elif command in ('start', 'complete'):
            await provider_transition(db, provider['id'], uuid.UUID(args['request_id']), 'in_progress' if command == 'start' else 'completed')
            body = 'Job started.' if command == 'start' else 'Job completed. Payment will be reflected after settlement.'
        elif command == 'earnings':
            e = await provider_earnings_summary(db, provider['id'])
            body = f"Jobs: {e['jobs']}\nTotal earnings: R{e['total']}\nAvailable: R{e['available']}\nPaid out: R{e['paid']}"
        elif command in ('online', 'pause'):
            await set_online(db, provider['id'], command == 'online')
            body = 'You are now online.' if command == 'online' else 'You are now offline.'
        else:
            body = 'Unknown provider command.'
    except ValueError as exc:
        body = f'Unable to process that: {exc}'
    return _out(body)


def _out(body: str):
    return SimpleNamespace(reply=body, actions=[], request_location=False, trace_id=uuid.uuid4())


def _confirmation_from_message(body: str):
    try:
        if body.startswith('agent:confirm:'):
            return True, uuid.UUID(body.rsplit(':', 1)[1])
        if body.startswith('agent:decline:'):
            return False, uuid.UUID(body.rsplit(':', 1)[1])
    except ValueError:
        return None
    return None


def _parse_delivery_command(text_in: str):
    import re
    s=(text_in or '').strip()
    u=s.upper()
    if u in {'DELIVERIES','DELIVERY JOBS','MY DELIVERIES'}: return ('list',{})
    m=re.match(r'^(DELIVERY|DELIVER)\s+([0-9a-fA-F-]{36})$',s,re.I)
    if m: return ('detail',{'job_id':m.group(2)})
    for label, command in [('AT PICKUP','at_pickup'),('PICKED UP','picked_up'),('IN TRANSIT','in_transit'),('DELIVERED','delivered')]:
        m=re.match(r'^'+label+r'\s+([0-9a-fA-F-]{36})$',s,re.I)
        if m: return (command,{'job_id':m.group(1)})
    m=re.match(r'^PROOF\s+([0-9a-fA-F-]{36})\s+(otp|photo|signature|recipient_confirmation)(?:\s+(\S+))?$',s,re.I)
    if m: return ('proof',{'job_id':m.group(1),'proof_type':m.group(2).lower(),'proof_hash':m.group(3)})
    return None

async def _delivery(db, provider, user_id, parsed, phone_e164, media_id=None):
    command,args=parsed
    try:
        if command=='list':
            rows=(await db.execute(text("""select id,order_id,status,pickup_lat,pickup_lng,dropoff_lat,dropoff_lng from delivery_jobs where courier_provider_id=:pid and status not in ('delivered','cancelled','failed') order by created_at desc limit 10"""),{'pid':provider['id']})).mappings().all()
            body='No active deliveries.' if not rows else '\n'.join(f"DELIVERY {r['id']} — {r['status']}\nAT PICKUP {r['id']} | PICKED UP {r['id']} | IN TRANSIT {r['id']}" for r in rows)
        elif command=='detail':
            data=await get_delivery(db, __import__('uuid').UUID(args['job_id']))
            j=data['job']
            if j.get('courier_provider_id') != provider['id']: raise ValueError('delivery is not assigned to you')
            body=f"DELIVERY {j['id']}\nStatus: {j['status']}\nPickup: {j['pickup_lat']},{j['pickup_lng']}\nDropoff: {j['dropoff_lat']},{j['dropoff_lng']}\nFee: {j['delivery_fee']}"
        elif command=='proof':
            jid=__import__('uuid').UUID(args['job_id'])
            proof_ref=args.get('proof_hash') or (str(media_id) if media_id and args['proof_type'] == 'photo' else None)
            metadata={'media_id':str(media_id)} if media_id else None
            await add_proof(db,jid,provider['id'],args['proof_type'],proof_ref,metadata)
            body=f"Proof recorded for delivery {jid}. You can now reply DELIVERED {jid}."
        else:
            jid=__import__('uuid').UUID(args['job_id'])
            await transition_delivery(db,jid,provider['id'],command)
            body=f"Delivery {jid} is now {command.replace('_',' ')}."
    except ValueError as exc:
        body=f'Unable to process delivery: {exc}'
    return _out(body)

async def _customer_confirm_delivery(db, user_id, body):
    import re
    m=re.match(r'^CONFIRM DELIVERY\s+([0-9a-fA-F-]{36})$',body.strip(),re.I)
    if not m: return _out('Use: CONFIRM DELIVERY <delivery_id>')
    jid=__import__('uuid').UUID(m.group(1))
    owner=(await db.execute(text("select 1 from delivery_jobs d join commerce_orders o on o.id=d.order_id where d.id=:jid and o.user_id=:uid"),{'jid':jid,'uid':user_id})).first()
    if not owner: return _out('Delivery not found for your account.')
    row=(await db.execute(text("select status from delivery_jobs where id=:jid"),{'jid':jid})).scalar_one_or_none()
    if row!='in_transit': return _out(f'Delivery is currently {row or "unknown"}.')
    await confirm_delivery_receipt(db,jid,user_id)
    return _out(f'Delivery {jid} confirmed. The courier can now mark it delivered.')
