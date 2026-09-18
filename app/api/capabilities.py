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
        "offline_mode": {
            "supported": True,
            "model": "store_and_forward",
            "cached_read_mode": True,
            "queued_mutations": True,
            "critical_actions_require_server_confirmation": True,
        },
        "stakeholder_onboarding": {
            "self_service": True,
            "secure_invite": True,
            "openapi_discovery": True,
            "test_then_activate": True,
            "encrypted_secrets": True,
            "code_changes_required_for_new_partner": False,
        },
        "modules": list_modules(),
    }
