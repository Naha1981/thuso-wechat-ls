# NahaOS Partner Integration Hub

## Goal

A stakeholder should be able to connect an existing API to NahaOS without asking NahaLabs to modify source code, build a custom SDK, or redeploy the platform.

## Onboarding flow

Invite → Connect → Discover → Map → Test → Activate

1. A NahaOS administrator creates a short-lived onboarding link for the stakeholder and selects its service domain.
2. The stakeholder opens the link. The token is kept in the browser fragment so it is not sent as a normal URL path/query value.
3. The stakeholder enters:
   - API base URL
   - authentication method and secret
   - optional health endpoint
   - optional OpenAPI JSON URL
4. NahaOS can import the OpenAPI document and create an initial operation catalogue.
5. The stakeholder confirms request templates and response mappings.
6. NahaOS executes a live test against at least one real service operation. A health check can be used for diagnostics but is not enough for production activation.
7. Only a configuration with a passed service-operation test can be activated.
8. Activation routes future requests for that service domain through the configured provider.
9. Editing an active configuration automatically disables it until the new configuration passes a fresh test.

## Provider contract

Citizen request
  ↓
NahaOS Agent + Policy
  ↓
ServiceGateway
  ↓
DatabaseHTTPServiceProvider
  ↓
PartnerIntegration contract
  ↓
Stakeholder API

The contract carries:
- trace ID
- operation name
- user/service payload
- optional explicit provider key

The adapter sends:
- authentication
- trace ID
- idempotency key
- configured request body
- configured endpoint

The adapter returns a normalised NahaOS ServiceResult.

## Security

- Secrets are encrypted server-side.
- Secrets are never returned to the onboarding browser after save.
- Production HTTP endpoints require HTTPS unless the platform explicitly allows a private-network endpoint.
- Endpoint hostname resolution rejects private/reserved addresses by default to reduce SSRF risk.
- Endpoint paths cannot contain `..`.
- Integrations are disabled until a test passes.
- Activation is auditable.
- Trace IDs connect user action, partner API call and downstream business outcome.

## Rural / low-connectivity behavior

NahaOS treats weak connectivity as a normal operating condition.

### What can work offline

- Load the lightweight PWA shell.
- Re-open previously cached safe public content.
- Draft/store approved idempotent requests in the local outbox.
- Show the user exactly what is pending.
- Automatically retry queued work when the connection returns.

### What cannot be falsely claimed offline

Payments, identity changes, government submissions, loan disbursement, purchases and other consequential actions are not marked completed until NahaOS receives a server-side confirmation.

### Channel strategy

- Smartphone users: PWA/Web + WhatsApp.
- Feature-phone users: USSD and supported messaging workflows.
- Weak-data users: cached pages, compressed payloads and store-and-forward requests.
- No-data moments: local queue and clear pending state until connectivity returns.

Offline mode means resilient operation, not pretending that an external transaction happened when no server could confirm it.


## Activation gate
A partner is never switched live merely because its hostname responds. At least one real business/service operation must pass through the configured contract before activation.


## Built-in adapter families

Stakeholders do not need to reshape their systems to look like a NahaOS REST API. The onboarding contract can select:

- REST / JSON
- GraphQL
- form-encoded HTTP
- SOAP / XML
- SFTP / file exchange

Authentication/signing options include bearer tokens, API keys, Basic auth, OAuth2 client credentials, HMAC-SHA256 signing and mTLS. Inbound webhook verification is supported separately.

For workflows that span multiple partner operations, NahaOS can execute configured steps with trace propagation and optional compensation operations. A partner can therefore keep its existing backend semantics while NahaOS presents one consistent citizen experience.
