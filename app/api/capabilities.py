from fastapi import APIRouter

from app.nahaos.modules import list_modules

router = APIRouter(prefix="/capabilities", tags=["capabilities"])

@router.get("")
async def capabilities():
    """Public machine-readable NahaOS capability catalogue."""
    return {
        "platform": "NahaOS",
        "market": "Lesotho",
        "interface_principle": "WhatsApp-first, with Web/USSD/Voice channels",
        "modules": list_modules(),
    }
