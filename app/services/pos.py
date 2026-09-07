from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import POSProduct, POSOrder, POSOrderItem

async def create_order(db: AsyncSession, merchant_id, items):
    product_ids = [i.product_id for i in items]
    products = (await db.scalars(select(POSProduct).where(POSProduct.id.in_(product_ids)).with_for_update())).all()
    by_id = {p.id:p for p in products}
    if len(by_id) != len(product_ids): raise ValueError("one or more products not found")
    order = POSOrder(merchant_id=merchant_id, status="pending", total=Decimal("0"))
    db.add(order); await db.flush()
    total = Decimal("0")
    for req in items:
        p = by_id[req.product_id]
        if p.stock_quantity < req.quantity: raise ValueError(f"insufficient stock for {p.sku}")
        line_total = p.price * req.quantity
        p.stock_quantity -= req.quantity
        db.add(POSOrderItem(order_id=order.id, product_id=p.id, quantity=req.quantity, unit_price=p.price, line_total=line_total))
        total += line_total
    order.total = total
    await db.flush()
    return order
