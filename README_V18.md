# Naha SuperApp Backend v1.8 — Merchant Operating System

## Purpose

v1.8 completes the merchant side of the first WhatsApp commerce vertical slice: merchants can receive, inspect, accept, prepare, mark ready, complete/cancel orders, manage menu inventory, see sales, and trigger delivery dispatch for paid delivery orders.

## Merchant WhatsApp commands

```text
ORDERS
ORDER <order_id>
ACCEPT ORDER <order_id>
REJECT ORDER <order_id> <reason>
PREPARING <order_id>
READY ORDER <order_id>
COMPLETE ORDER <order_id>
CANCEL ORDER <order_id> <reason>
MENU
ADD ITEM <name> <price>
STOCK <product_id> <quantity>
EARNINGS
```

Merchant commands are evaluated before customer commerce commands for authenticated food merchants, preventing `MENU` from being interpreted as customer discovery when the sender is a merchant.

## Order state machine

```text
pending_payment -> paid -> preparing -> ready -> completed
                         |         |          |
                         +------> cancelled <+

ready -> out_for_delivery -> completed
```

A paid delivery order becomes `out_for_delivery` only after the merchant marks it `ready`, a merchant pickup location is available, and a delivery service request is created. Provider dispatch uses the existing deterministic dispatch engine.

## Security boundaries

- Merchant identity is resolved from the verified WhatsApp phone mapping, not from a user-supplied merchant ID in the WhatsApp flow.
- Merchant API routes remain behind the authenticated-session/internal boundary used by the current backend until a full provider JWT/session gateway is introduced.
- Order mutations are performed under row locks and validated against the merchant owner of the order.
- State transitions are explicit and fail closed.
- Customer notifications are delivered through the transactional channel outbox rather than synchronously from the request handler.
- Payment state is not changed by merchant commands.
- Financial settlement remains in the payment/ledger subsystem.

## APIs

```text
GET  /api/v1/merchants/{merchant_id}/orders
GET  /api/v1/merchants/{merchant_id}/orders/{order_id}
POST /api/v1/merchants/{merchant_id}/orders/{order_id}/{action}
GET  /api/v1/merchants/{merchant_id}/menu
POST /api/v1/merchants/{merchant_id}/menu/items
PATCH /api/v1/merchants/{merchant_id}/menu/items/{product_id}/stock
GET  /api/v1/merchants/{merchant_id}/sales
```

## Database

Migration:

```text
018_merchant_os.sql
```

Adds merchant order lifecycle timestamps, delivery request linkage, merchant action deduplication and merchant audit events.

## Delivery integration

When a paid delivery order reaches `ready`:

1. Naha reads the merchant pickup coordinates.
2. Creates a `delivery` service request linked to the commerce order.
3. Dispatches the request through Dispatch 2.0.
4. Stores the delivery request ID on the order.
5. Moves the order to `out_for_delivery`.
6. Notifies the customer through the WhatsApp outbox.

Provider acceptance and delivery completion continue through the existing provider operating system.

## Verification

```text
37 passed
```

This version is unit-tested in the local environment. Live Supabase, WhatsApp, payment-provider and production Redis integration tests still require real environment credentials/infrastructure.
