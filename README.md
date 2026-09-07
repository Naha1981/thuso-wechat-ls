# THUSO Platform

> **Ask THUSO. Get it done.**

**Current release: v2.15 — Food + Delivery Customer Experience**

THUSO is a WhatsApp-first consumer platform. WhatsApp is the interface; the Naha backend provides identity, commerce, payments, merchants, dispatch, delivery, media, memory and agent orchestration.

## First production vertical: Food + Delivery

The customer journey is:

`FOOD` → discover merchants → `MENU <merchant_id>` → `ADD <product_id> <quantity>` → `CART` → share location → `CHECKOUT` → payment → merchant preparation → courier dispatch → live delivery state → proof/confirmation.

The existing v2.14 commerce, merchant, dispatch, delivery and payment primitives remain the transactional foundation. v2.15 adds the customer-facing Food API and persistent delivery location/timeline primitives.

## Customer API

```text
GET   /api/v1/food/feed
GET   /api/v1/food/merchants/{merchant_id}/menu
GET   /api/v1/food/location
PUT   /api/v1/food/location
PATCH /api/v1/food/cart/items
GET   /api/v1/food/orders
GET   /api/v1/food/orders/{order_id}/timeline
POST  /api/v1/food/orders/{order_id}/cancel
```

## Database

Apply:

```text
supabase/migrations/034_food_delivery_experience.sql
```

This adds customer delivery locations and indexes the commerce/delivery event streams for chronological order tracking.

## WhatsApp

The existing WhatsApp commerce flow remains available:

```text
FOOD / MENU
MENU <merchant_id>
ADD <product_id> <quantity>
CART
CHECKOUT
```

Location messages are already parsed by WhatsApp ingress and can be used by the Food experience layer. Payment and delivery notifications continue through the durable outbox.

## Verification

```text
67 passed
```

Python compilation checks pass for the new Food API/service and application entrypoint. Live Supabase, Redis, WhatsApp and payment-provider integration tests still require production-like infrastructure and credentials.
