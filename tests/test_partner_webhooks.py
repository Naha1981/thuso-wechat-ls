import pytest

from app.integrations.universal_adapter import AdapterContext
from app.services.partner_integrations import PartnerIntegration
from app.services.partner_webhooks import parse_webhook_payload, verify_webhook


def webhook_config(auth_scheme="hmac_sha256"):
    return PartnerIntegration(
        id="1",
        stakeholder_name="Test",
        stakeholder_type="bank",
        service_domain="payments",
        provider_key="test-bank",
        environment="production",
        enabled=True,
        allow_private_network=False,
        adapter_type="rest_json",
        base_url="https://partner.example",
        api_spec_url=None,
        health_endpoint_path=None,
        auth_scheme="none",
        auth_header_name="Authorization",
        timeout_seconds=10,
        request_defaults={},
        operation_configs={},
        response_mappings={},
        auth_config={},
        webhook_config={
            "auth_scheme": auth_scheme,
            "signature_header": "X-Signature",
            "timestamp_header": "X-Timestamp",
        },
        workflow_configs={},
        secrets={"hmac_secret": "secret", "api_key": "key"},
        last_test_status="passed",
        last_test_operation="payment_status",
    )


def test_webhook_json_parsing():
    config = webhook_config()
    payload = parse_webhook_payload(config, b'{"event":"paid","id":"1"}', "application/json")
    assert payload["event"] == "paid"


def test_webhook_hmac_verification():
    import hashlib
    import hmac
    import time

    config = webhook_config()
    body = b'{"event":"paid"}'
    timestamp = str(int(time.time()))
    canonical = "\n".join((timestamp, body.decode()))
    signature = hmac.new(b"secret", canonical.encode(), hashlib.sha256).hexdigest()
    verify_webhook(config, headers={
        "x-signature": signature,
        "x-timestamp": timestamp,
    }, body=body)


def test_webhook_rejects_bad_signature():
    import time
    config = webhook_config()
    with pytest.raises(PermissionError):
        verify_webhook(config, headers={
            "x-signature": "bad",
            "x-timestamp": str(int(time.time())),
        }, body=b'{"event":"paid"}')
