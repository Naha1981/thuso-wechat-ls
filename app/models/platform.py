import uuid
from decimal import Decimal
from datetime import datetime
from sqlalchemy import ForeignKey, Numeric, String, DateTime, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.models.domain import Base

class POSProduct(Base):
    __tablename__='pos_products'
    id: Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),primary_key=True,default=uuid.uuid4)
    merchant_id: Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),ForeignKey('providers.id'),index=True)
    name: Mapped[str]=mapped_column(String(160))
    sku: Mapped[str]=mapped_column(String(80))
    price: Mapped[Decimal]=mapped_column(Numeric(14,2))
    stock_quantity: Mapped[Decimal]=mapped_column(Numeric(14,3),default=0)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
    __table_args__=(UniqueConstraint('merchant_id','sku',name='uq_pos_product_merchant_sku'),)

class POSOrder(Base):
    __tablename__='pos_orders'
    id: Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),primary_key=True,default=uuid.uuid4)
    merchant_id: Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),ForeignKey('providers.id'),index=True)
    status: Mapped[str]=mapped_column(String(20),default='pending',index=True)
    total: Mapped[Decimal]=mapped_column(Numeric(14,2))
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())

class POSOrderItem(Base):
    __tablename__='pos_order_items'
    id: Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),primary_key=True,default=uuid.uuid4)
    order_id: Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),ForeignKey('pos_orders.id',ondelete='cascade'),index=True)
    product_id: Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),ForeignKey('pos_products.id'))
    quantity: Mapped[Decimal]=mapped_column(Numeric(14,3))
    unit_price: Mapped[Decimal]=mapped_column(Numeric(14,2))
    line_total: Mapped[Decimal]=mapped_column(Numeric(14,2))
