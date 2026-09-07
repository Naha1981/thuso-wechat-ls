from datetime import datetime
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict

class ProviderCreateV2(BaseModel):
    owner_user_id: UUID | None = None
    category: str = Field(min_length=2, max_length=40)
    business_name: str = Field(min_length=2, max_length=160)
    phone_e164: str | None = Field(default=None, max_length=20)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    metadata: dict = Field(default_factory=dict)

class ServiceRequestCreateV2(BaseModel):
    user_id: UUID | None = None
    category: str = Field(min_length=2, max_length=40)
    description: str | None = Field(default=None, max_length=4000)
    pickup_lat: float | None = Field(default=None, ge=-90, le=90)
    pickup_lng: float | None = Field(default=None, ge=-180, le=180)
    destination_lat: float | None = Field(default=None, ge=-90, le=90)
    destination_lng: float | None = Field(default=None, ge=-180, le=180)
    payload: dict = Field(default_factory=dict)

class ServiceRequestOutV2(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    user_id: UUID
    category: str
    status: str
    created_at: datetime

class DispatchMatch(BaseModel):
    provider_id: UUID
    distance_m: float
    score: float

class POSProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    sku: str = Field(min_length=1, max_length=80)
    price: Decimal = Field(ge=0, decimal_places=2)
    stock_quantity: Decimal = Field(default=0, ge=0)

class POSOrderItem(BaseModel):
    product_id: UUID
    quantity: Decimal = Field(gt=0)

class POSOrderCreate(BaseModel):
    merchant_id: UUID
    items: list[POSOrderItem] = Field(min_length=1)

class CVRequest(BaseModel):
    user_id: UUID | None = None
    target_role: str = Field(min_length=2, max_length=160)
    profile: dict = Field(default_factory=dict)

class TutorRequest(BaseModel):
    user_id: UUID | None = None
    grade: str = Field(min_length=1, max_length=30)
    subject: str = Field(min_length=1, max_length=80)
    topic: str = Field(min_length=1, max_length=200)
