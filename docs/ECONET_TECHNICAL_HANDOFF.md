# Econet Technical Handoff

## Production goal

NahaOS is delivered as a complete production integration target. Econet does not need NahaLabs engineers to edit source code to connect the approved AI APIs.

Production flow: Econet credentials + API contract → NahaOS Integration Control Plane → encrypted provider configuration → EconetAIProvider → AIProvider → NahaOS.

## What Econet needs to provide

- API base URL
- authentication method and credential issuance process
- API/model/service identifier
- chat request/response schema
- health/capability endpoint, when available
- rate limits
- timeout/retry rules
- error semantics
- data residency/privacy requirements
- approved AI capabilities and usage limits
- sandbox credentials when available

No production source-code modification is required when the API can be represented by the control-plane contract mapping.

## How Econet connects itself

1. Deploy NahaOS and run database migrations, including 036_econet_integration_control_plane.sql.
2. Configure the server-side SECRETS_ENCRYPTION_KEY.
3. Configure the one-time ADMIN_BOOTSTRAP_TOKEN.
4. Open /admin.
5. Complete first-time administrator setup.
6. Enter the Econet production API configuration.
7. Enter credentials. Credentials are encrypted before database persistence and are never returned to the browser.
8. Save the configuration.
9. Run Test health or Test AI request.
10. Activate production only after the test passes.

Activation is reversible. Deactivation returns runtime selection to the NahaOS fallback provider.

## Provider contract

AIProvider exposes chat(request), health(), and capabilities().

Econet-specific mapping is isolated in EconetAIProvider.

The control plane supports configurable request templates and response-path mappings so Econet can map a non-identical JSON contract without changing citizen-facing flows.

## Security boundary

- API secrets are encrypted with AES-GCM using SECRETS_ENCRYPTION_KEY.
- Secrets are never returned in API responses.
- Admin authentication uses server-side sessions with HttpOnly cookies.
- Mutating admin requests require a session-bound CSRF token.
- Failed admin logins trigger a temporary account lock after repeated failures.
- Integration changes, tests, activations and deactivations are audited.
- Production endpoints require HTTPS.
- Public endpoint addresses are checked against private/reserved networks unless the administrator explicitly enables private-network mode.
- Provider errors exposed to callers do not include upstream response bodies or credentials.
- NahaOS retains deterministic policy/action execution; AI does not directly authorize payments or consequential actions.

## Sandbox

The NahaOS Sandbox is a separate deterministic provider. It exists for demonstrations, QA and development.

It does not use Econet credentials and does not block production integration. Production activation happens only through the control plane.

## Commercial traceability

Every AI request can receive a trace ID. AI usage is persisted alongside business outcome events so Econet can measure observed and attributable commercial value without treating estimates as booked revenue.

## Acceptance tests

Before production launch, Econet should execute authentication, health/capability, AI request, timeout/retry, rate-limit, malformed-response, trace/audit, data/privacy, load, and rollback/deactivation checks.

The portal controls Test health, Test AI request, Activate production, and Deactivate production are the operational entry points for these checks.