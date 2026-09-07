from decimal import Decimal
from fastapi import APIRouter
from pydantic import BaseModel, Field
from app.services.risk import RiskInput, score_transaction

router=APIRouter(prefix='/risk',tags=['risk'])
class RiskIn(BaseModel):
    amount: Decimal=Field(gt=0); daily_amount: Decimal=Field(default=Decimal('0'),ge=0); daily_count:int=Field(default=0,ge=0)
    failed_count:int=Field(default=0,ge=0); account_age_days:int=Field(default=0,ge=0); kyc_level:str='unverified'
    payout:bool=False; new_destination:bool=False; velocity_window_count:int=Field(default=0,ge=0)
@router.post('/score')
async def score(body:RiskIn):
    r=score_transaction(RiskInput(**body.model_dump()))
    return {'score':r.score,'decision':r.decision,'reasons':list(r.reasons)}
