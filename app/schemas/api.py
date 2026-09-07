from decimal import Decimal
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, Field

ServiceCategory = Literal["ride", "mechanic", "handyman", "food", "tutor", "career", "mental_health"]

class UserCreate(BaseModel):
    phone_e164: str = Field(pattern=r"^\+[1-9]\d{7,14}$")
    display_name: str | None = Field(default=None, max_length=120)

class UserOut(BaseModel):
    id: UUID
    phone_e164: str
    display_name: str | None
    locale: str
    model_config = {"from_attributes": True}

class ServiceRequestCreate(BaseModel):
    user_id: UUID
    category: ServiceCategory
    pickup_lat: Decimal | None = Field(default=None, ge=-90, le=90)
    pickup_lng: Decimal | None = Field(default=None, ge=-180, le=180)
    payload: dict = Field(default_factory=dict)

class ServiceRequestOut(BaseModel):
    id: UUID
    user_id: UUID
    category: str
    status: str
    payload: dict
    model_config = {"from_attributes": True}

class ProviderCreate(BaseModel):
    owner_user_id: UUID
    category: ServiceCategory
    business_name: str = Field(min_length=2, max_length=160)
    metadata: dict = Field(default_factory=dict)
