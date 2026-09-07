from fastapi import APIRouter

from app.services.lesotho_payment_methods import list_lesotho_payment_methods

router = APIRouter(prefix="/payment-methods", tags=["payment-methods"])


@router.get("/LSL")
async def lesotho_payment_methods():
    methods = list_lesotho_payment_methods()
    return {
        "country": "LS",
        "currency": "LSL",
        "mobile_money_first": True,
        "methods": methods,
    }
