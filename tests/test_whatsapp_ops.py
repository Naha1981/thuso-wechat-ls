from datetime import datetime, timezone
from app.services.whatsapp_ops import normalize_health


def test_normalize_health_is_json_safe():
    row={
        'wa_account_id':'00000000-0000-0000-0000-000000000001',
        'transport':'baileys','state':'healthy','consecutive_failures':0,
        'last_success_at':datetime(2026,9,7,8,0,tzinfo=timezone.utc),
        'last_failure_at':None,'last_error':None,'circuit_open_until':None,
        'updated_at':datetime(2026,9,7,8,0,tzinfo=timezone.utc),
    }
    result=normalize_health(row)
    assert result['wa_account_id'].endswith('001')
    assert result['last_success_at'].endswith('+00:00')
    assert result['state']=='healthy'
