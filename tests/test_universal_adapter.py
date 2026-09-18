from uuid import uuid4

import httpx
import pytest
import respx

from app.integrations.universal_adapter import AdapterContext, GraphQLAdapter, FormUrlEncodedAdapter, RestJsonAdapter, SoapXmlAdapter


def ctx(adapter_type="rest_json", auth_scheme="none", auth_config=None, secrets=None, operation_config=None):
    return AdapterContext(
        base_url="https://partner.example",
        operation="demo",
        trace_id=str(uuid4()),
        timeout_seconds=10,
        request_defaults={},
        operation_config=operation_config or {"path": "/demo", "method": "POST", "request_template": {"payload": "{{payload}}"}},
        auth_scheme=auth_scheme,
        auth_config=auth_config or {},
        secrets=secrets or {},
        allow_private_network=False,
    )


@pytest.mark.asyncio
@respx.mock
async def test_rest_json_adapter():
    route = respx.post("https://partner.example/demo").mock(
        return_value=httpx.Response(200, json={"id": "123", "status": "ok"})
    )
    result = await RestJsonAdapter().execute(ctx(), {"name": "Thuso"})
    assert route.called
    assert result.data["id"] == "123"


@pytest.mark.asyncio
@respx.mock
async def test_rest_json_hmac_headers():
    route = respx.post("https://partner.example/demo").mock(return_value=httpx.Response(200, json={"ok": True}))
    context = ctx(auth_scheme="hmac_sha256", auth_config={"signature_header": "X-Signature", "timestamp_header": "X-Timestamp"}, secrets={"hmac_secret": "secret"})
    await RestJsonAdapter().execute(context, {"amount": 100})
    assert route.called
    request = route.calls[0].request
    assert request.headers.get("X-Signature")
    assert request.headers.get("X-Timestamp")
    assert request.headers.get("X-NahaOS-Idempotency-Key") == context.trace_id


@pytest.mark.asyncio
@respx.mock
async def test_graphql_adapter():
    route = respx.post("https://partner.example/demo").mock(
        return_value=httpx.Response(200, json={"data": {"customer": {"id": "c1"}}})
    )
    context = ctx(operation_config={"path": "/demo", "query": "query Customer($id: ID!){ customer(id:$id){ id } }", "variables": {"id": "{{payload.customer_id}}"})
    result = await GraphQLAdapter().execute(context, {"customer_id": "c1"})
    assert route.called
    assert result.data["data"]["customer"]["id"] == "c1"


@pytest.mark.asyncio
@respx.mock
async def test_form_urlencoded_adapter():
    route = respx.post("https://partner.example/demo").mock(return_value=httpx.Response(200, json={"accepted": True}))
    result = await FormUrlEncodedAdapter().execute(ctx(operation_config={"path": "/demo", "request_template": {"name": "{{payload.name}}", "amount": "{{payload.amount}}"}},), {"name": "A", "amount": 50})
    assert route.called
    assert b"name=A" in route.calls[0].request.content
    assert result.data["accepted"] is True


@pytest.mark.asyncio
@respx.mock
async def test_soap_xml_adapter():
    route = respx.post("https://partner.example/demo").mock(
        return_value=httpx.Response(200, text="<Envelope><Body><Result><Status>OK</Status></Result></Body></Envelope>")
    )
    result = await SoapXmlAdapter().execute(
        ctx(operation_config={
            "path": "/demo",
            "xml_template": "<Envelope><Body><Submit><Name>{{payload.name}}</Name></Submit></Body></Envelope>",
            "soap_action": "Submit",
        }),
        {"name": "A"},
    )
    assert route.called
    assert result.data["xml_root"]["Body"]["Result"]["Status"] == "OK"


@pytest.mark.asyncio
@respx.mock
async def test_oauth2_client_credentials_adapter():
    token_route = respx.post("https://auth.example/token").mock(
        return_value=httpx.Response(200, json={"access_token": "access-123", "expires_in": 300})
    )
    api_route = respx.post("https://partner.example/demo").mock(
        return_value=httpx.Response(200, json={"accepted": True})
    )
    context = ctx(
        auth_scheme="oauth2_client_credentials",
        auth_config={"token_url": "https://auth.example/token", "client_id": "client-1", "scope": "payments"},
        secrets={"client_secret": "secret"},
    )
    result = await RestJsonAdapter().execute(context, {"amount": 5})
    assert token_route.called
    assert api_route.called
    assert api_route.calls[0].request.headers["Authorization"] == "Bearer access-123"
    assert result.data["accepted"] is True


@pytest.mark.asyncio
async def test_template_nested_values():
    from app.services.template_engine import render
    value = render({"id": "{{payload.customer_id}}", "quote": "{{steps.quote.id}}"}, {
        "payload": {"customer_id": "c1"},
        "steps": {"quote": {"id": "q1"}},
    })
    assert value == {"id": "c1", "quote": "q1"}
