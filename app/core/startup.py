from __future__ import annotations
from app.core.config import get_settings

class ConfigurationError(RuntimeError):
    pass

def validate_startup_configuration() -> None:
    s=get_settings()
    required={
        'DATABASE_URL':s.database_url,
        'SUPABASE_URL':s.supabase_url,
        'SUPABASE_SERVICE_ROLE_KEY':s.supabase_service_role_key,
        'WHATSAPP_WEBHOOK_SECRET':s.webhook_secret,
        'OPERATOR_API_KEY':s.operator_api_key,
    }
    if s.app_env.lower() in {'production','prod'}:
        missing=[k for k,v in required.items() if not v or str(v).startswith('change-me')]
        if missing: raise ConfigurationError('missing production configuration: '+', '.join(missing))
        if s.whatsapp_transport == 'baileys' and 'localhost' in s.main_app_webhook_url.lower():
            raise ConfigurationError('MAIN_APP_WEBHOOK_URL cannot target localhost in production')
