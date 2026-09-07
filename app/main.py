from fastapi import FastAPI
from app.core.config import get_settings
from app.api.routes import router as api_router
from app.api.webhooks import router as webhook_router
from app.api.execution import router as execution_router
from app.api.v2 import router as platform_router
from app.api.agent import router as agent_router
from app.api.provider import router as provider_router
from app.api.dispatch import router as dispatch_router
from app.api.realtime import router as realtime_router
from app.api.financial import router as financial_router
from app.api.payment_providers import router as payment_provider_router
from app.api.payment_provider_webhooks import router as payment_webhook_router
from app.api.payment_routing import router as payment_routing_router
from app.api.payment_orchestration import router as payment_orchestration_router
from app.api.settlement import router as settlement_router
from app.api.reconciliation import router as reconciliation_router
from app.api.risk import router as risk_router
from app.api.kyc import router as kyc_router
from app.api.commerce import router as commerce_router
from app.api.merchant import router as merchant_router
from app.api.delivery import router as delivery_router
from app.api.identity import router as identity_router
from app.api.media import router as media_router
from app.api.intelligence import router as intelligence_router
from app.api.whatsapp_identity import router as whatsapp_identity_router
from app.api.whatsapp_ops import router as whatsapp_ops_router
from app.core.startup import validate_startup_configuration

settings=get_settings()
app=FastAPI(title="Naha SuperApp Platform API", version="2.14.0")

@app.on_event("startup")
async def startup_validation():
    validate_startup_configuration()
app.include_router(api_router, prefix=settings.api_prefix)
app.include_router(platform_router, prefix=settings.api_prefix)
app.include_router(execution_router, prefix=settings.api_prefix)
app.include_router(webhook_router, prefix="/webhooks", tags=["webhooks"])
app.include_router(agent_router, prefix=settings.api_prefix)
app.include_router(provider_router, prefix=settings.api_prefix)
app.include_router(dispatch_router, prefix=settings.api_prefix)
app.include_router(realtime_router, prefix=settings.api_prefix)
app.include_router(payment_provider_router)
app.include_router(payment_webhook_router)
app.include_router(payment_routing_router, prefix=settings.api_prefix)
app.include_router(financial_router, prefix=settings.api_prefix)
app.include_router(payment_orchestration_router, prefix=settings.api_prefix)
app.include_router(settlement_router, prefix=settings.api_prefix)
app.include_router(reconciliation_router, prefix=settings.api_prefix)
app.include_router(risk_router, prefix=settings.api_prefix)
app.include_router(kyc_router, prefix=settings.api_prefix)
app.include_router(commerce_router, prefix=settings.api_prefix)
app.include_router(merchant_router, prefix=settings.api_prefix)
app.include_router(delivery_router, prefix=settings.api_prefix)
app.include_router(identity_router, prefix=settings.api_prefix)
app.include_router(media_router, prefix=settings.api_prefix)
app.include_router(intelligence_router, prefix=settings.api_prefix)
app.include_router(whatsapp_identity_router, prefix=settings.api_prefix)
app.include_router(whatsapp_ops_router, prefix=settings.api_prefix)

@app.get("/healthz")
async def healthz(): return {"status":"ok","service":settings.app_name,"version":"2.14.0"}
