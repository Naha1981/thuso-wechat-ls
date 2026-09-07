from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_env: str = "development"
    app_name: str = "naha-superapp"
    api_prefix: str = "/api/v1"
    log_level: str = "INFO"
    database_url: str
    redis_url: str = "redis://localhost:6379/0"
    supabase_url: str
    supabase_service_role_key: str
    whatsapp_verify_token: str
    whatsapp_app_secret: str
    whatsapp_access_token: str
    whatsapp_phone_number_id: str
    whatsapp_graph_version: str = "v23.0"
    internal_webhook_secret: str = ""
    webhook_max_body_bytes: int = 1_048_576
    rate_limit_per_minute: int = 60
    payment_webhook_secret: str = ""
    whatsapp_transport: str = "baileys"
    operator_url: str = "http://localhost:3001"
    operator_api_key: str = ""
    whatsapp_operator_account_key: str = ""
    webhook_secret: str = ""
    main_app_webhook_url: str = "http://localhost:8000/webhooks/whatsapp/baileys"
    identity_pepper: str = "change-me"
    identity_session_ttl_minutes: int = 60
    otp_ttl_seconds: int = 300
    otp_max_attempts: int = 5
    media_storage_backend: str = "supabase"
    media_bucket: str = "whatsapp-media"
    media_signed_url_ttl_seconds: int = 300
    media_local_root: str = "/tmp/naha-media"
    media_antivirus_backend: str = "clamav"
    media_antivirus_fail_closed: bool = True
    clamav_host: str = "127.0.0.1"
    clamav_port: int = 3310
    intelligence_provider: str = "kie"
    kie_api_key: str = ""
    kie_base_url: str = "https://api.kie.ai"
    kie_multimodal_model: str = "gemini-3-7-flash-openai"
    kie_timeout_seconds: int = 90
    intelligence_max_output_chars: int = 12000
    intelligence_auto_reply: bool = False

@lru_cache
def get_settings() -> Settings:
    return Settings()
