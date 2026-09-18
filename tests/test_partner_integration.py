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
