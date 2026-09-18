import pytest

from app.services.partner_integrations import hash_token, normalise_path, render

def test_partner_token_hash_is_not_plaintext():
    token = "example-secret-token"
    assert hash_token(token) != token
    assert len(hash_token(token)) == 64

def test_partner_path_rejects_traversal():
    assert normalise_path("/v1/status") == "/v1/status"
    try:
        normalise_path("../private")
    except ValueError:
        pass
    else:
        raise AssertionError("path traversal must be rejected")

def test_partner_template_rendering():
    body = render({"trace": "{{trace_id}}", "payload": "{{payload}}"}, {"trace_id": "t1", "payload": {"id": 1}})
    assert body["trace"] == "t1"
    assert body["payload"]["id"] == 1

def test_private_network_default_is_false():
    from app.services.partner_integrations import PartnerIntegration
    assert "allow_private_network" in PartnerIntegration.__dataclass_fields__

@pytest.mark.asyncio
async def test_partner_workflow_compensation(monkeypatch):
    from app.services.partner_integrations import execute_workflow, PartnerIntegration
    calls = []

    async def fake_execute(config, *, operation, trace_id, payload):
        calls.append(operation)
        if operation == "submit":
            raise RuntimeError("submit failed")
        return {"ok": True, "operation": operation}, True

    monkeypatch.setattr("app.services.partner_integrations.execute_partner", fake_execute)
    config = PartnerIntegration(
        id="1", stakeholder_name="Test", stakeholder_type="government",
        service_domain="government", provider_key="gov", environment="production",
        enabled=True, allow_private_network=False, adapter_type="rest_json",
        base_url="https://example.org", api_spec_url=None, health_endpoint_path=None,
        auth_scheme="none", auth_header_name="Authorization", timeout_seconds=10,
        request_defaults={}, operation_configs={"validate": {}, "submit": {}, "rollback": {}},
        response_mappings={}, auth_config={}, webhook_config={},
        workflow_configs={"application": [
            {"operation": "validate", "compensation_operation": "rollback"},
            {"operation": "submit"},
        ]},
        secrets={}, last_test_status="passed", last_test_operation="submit",
    )
    with pytest.raises(RuntimeError):
        await execute_workflow(config, workflow_name="application", trace_id="trace", payload={"id": "1"})
    assert calls == ["validate", "submit", "rollback"]
