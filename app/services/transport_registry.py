from __future__ import annotations
from functools import lru_cache
from app.core.config import get_settings
from app.services.whatsapp import WhatsAppClient
from app.services.whatsapp_transport import BaileysTransport, MetaCloudTransport, WhatsAppTransport, TransportError


@lru_cache
def get_whatsapp_transport() -> WhatsAppTransport:
    settings = get_settings()
    name = settings.whatsapp_transport.lower()
    if name == "baileys":
        return BaileysTransport(WhatsAppClient())
    if name == "meta_cloud":
        return MetaCloudTransport(settings)
    raise TransportError(f"unsupported WHATSAPP_TRANSPORT={settings.whatsapp_transport!r}")
