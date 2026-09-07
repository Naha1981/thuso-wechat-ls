# THUSO v2.15 — Food + Delivery Customer Experience

v2.15 turns the existing commerce, payments, merchant, dispatch, delivery and WhatsApp primitives into a complete first consumer vertical: **Food + Delivery**.

## Customer journey

1. `FOOD` — discover food merchants.
2. `MENU <merchant_id>` — browse an available menu.
3. `ADD <product_id> <quantity>` — build a cart.
4. `CART` — review the cart.
5. Share a WhatsApp location — THUSO saves it as the customer's default delivery location.
6. `CHECKOUT` — create the order and start routed payment.
7. `ORDERS` — see order history.
8. `TRACK <order_id>` — inspect current delivery state and ETA when available.
9. Merchant accepts/prepares/marks the order ready.
10. The platform creates a delivery job and dispatches a courier.
11. Courier sends location/status/proof through the existing Delivery OS.
12. Customer receives WhatsApp lifecycle notifications.
13. `CONFIRM DELIVERY <job_id>` can record recipient confirmation while the delivery is in transit.

## HTTP customer surface

- `GET /api/v1/food/feed`
- `GET /api/v1/food/merchants/{merchant_id}/menu`
- `GET /api/v1/food/location`
- `PUT /api/v1/food/location`
- `PATCH /api/v1/food/cart/items`
- `GET /api/v1/food/orders`
- `GET /api/v1/food/orders/{order_id}/timeline`
- `POST /api/v1/food/orders/{order_id}/cancel`

The existing commerce checkout remains the transactional order/payment boundary; the new Food API is the consumer-facing experience layer around it.

## Release boundary

This release focuses on the customer experience layer. Existing v2.14 production hardening remains the foundation; v2.15 does not replace the established identity, payment, dispatch, delivery or WhatsApp transport boundaries.

## Verification

- Python compile checks passed.
- **67 automated tests passed.**
- No secrets are added by this release.

## Database

Apply `supabase/migrations/034_food_delivery_experience.sql` after the previous migrations.
