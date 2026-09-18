# THUSO / NahaOS

> **Ask THUSO. Get it done.**

**Current release: v2.19.0 — NahaOS production integration control plane**

THUSO is evolving from a WhatsApp-first consumer platform into a Lesotho digital-services and AI orchestration platform. Existing identity, commerce, payment, merchant, dispatch, delivery, media and agent primitives remain the transactional foundation.

## Architecture

Citizen / Business → WhatsApp / Web / USSD / Voice → Identity + Consent → AI Gateway + Agent Orchestrator → Policy + Tools → Government / Enterprise / Commerce Services → Payment Gateway / Partner APIs.

Econet AI is a first-class provider through an adapter boundary. The demo works without Econet credentials. When Econet supplies an approved API contract, its credentials/endpoints are configured in the provider layer without rewriting citizen workflows.

## Existing foundation

- Identity and authenticated sessions
- Agent intent/routing and confirmation workflow
- WhatsApp orchestration
- Commerce, merchants and delivery
- Payment-provider abstraction and routing
- Media intelligence
- Audit/action receipts
- Lesotho-first currency and payment contracts

## AI gateway

GET `/api/v1/ai/provider`

POST `/api/v1/ai/chat`

Configuration defaults to the isolated NahaOS Sandbox.

For production, the NahaOS Integration Control Plane is the source of truth. Authorized Econet administrators can open /admin, sign in, enter their approved API contract, save encrypted secrets, test the connection, and activate production. No source-code change, rebuild, or NahaLabs-side API access is required after deployment.

The runtime boundary is:

Econet API
   ↓
EconetAIProvider
   ↓
AIProvider
   ↓
NahaOS Agent + Services + Policy + Tools

The sandbox and production paths are isolated. A sandbox response never writes to or uses Econet production credentials.

The runtime boundary is intentionally fixed:

```text
EconetAIProvider → AIProvider → NahaOS
```

NahaOS does not import or depend on Econet-specific SDKs. When Econet changes its API schema, only the adapter mapping changes.

AI chat is authenticated through the existing NahaOS session layer and successful calls are recorded in `ai_usage_events` with a trace ID.

## Monetization proof

THUSO is designed to prove Econet commercial value through traceable events rather than assumptions. See `docs/ECONET_MONETIZATION.md` and `docs/REVENUE_PROOF.md`.

The proof model distinguishes observed, attributed and estimated value.

## Food + delivery

The existing journey remains available: FOOD → merchant → menu → cart → location → checkout → payment → preparation → dispatch → delivery → proof/confirmation.

## Verification

Run pytest -q tests/test_ai_gateway.py tests/test_control_plane.py, ruff check app tests, python -m compileall app tests, npm run build in web/, and npm run typecheck in operator/.

External provider, WhatsApp, Supabase and payment integrations require their respective credentials/contracts and are intentionally not fabricated.

## NahaOS Economic OS modules

NahaOS now treats the former standalone product ideas as modules of one Lesotho platform:

- **SkyPay / SME Business:** merchant identity, POS, sales, inventory, expenses and financial visibility.
- **Ramalaisha:** diaspora-to-family grocery and retail fulfilment, retailer preparation, OTP pickup/delivery and backorders.
- **AegisGrid:** fraud, risk, anomaly and credit decision-support signals.
- **Credit & Lending:** eligibility, applications, stock finance and repayment workflows.
- **Tax + Cross-Border Trade:** VAT classification, reporting, customs-ready manifests and anomaly detection.
- **Agriculture:** farmer services, inputs, markets, yield intelligence and supply forecasting.
- **Financial Literacy:** WhatsApp-first money lessons and personalised business/household guidance.
- **Shopping + Transport + Travel + Telecom:** a single commerce/service doorway for purchases, rides, travel and supported telecom actions.

The machine-readable catalogue is available at `GET /api/v1/capabilities`.

### One app, one identity, many services

The intended user experience is conversational:

`order food` → `request a ride` → `send groceries to family` → `buy airtime` → `check a loan workflow` → `file a tax/service request`.

NahaOS decides which safe workflow and service adapter to invoke. External providers remain behind integration boundaries and must be supplied with approved contracts/credentials before production execution is enabled.


## Stakeholder self-onboarding

NahaOS now has a generic Partner Integration Hub. A platform administrator creates a short-lived secure onboarding link for a stakeholder. The stakeholder opens the link and can:

1. enter its API base URL and credentials;
2. optionally import an OpenAPI JSON document to discover operations;
3. map request/response fields;
4. run a live connectivity test;
5. activate production.

Changing a contract automatically disables the live integration until the new configuration passes a fresh test. Secrets are encrypted server-side. External integrations remain configuration-driven; provider-specific API changes do not require NahaLabs source-code changes.

## Rural + low-connectivity operation

NahaOS is designed for unreliable connectivity:

- Web is installable as a lightweight PWA shell.
- Frequently visited pages can be cached locally.
- An IndexedDB outbox can store approved, idempotent requests while offline and retry them when connectivity returns.
- The user sees a clear online/offline state and queued-work count.
- WhatsApp and USSD remain channel options for people who cannot use the web app reliably.
- Critical financial, identity and other consequential actions are never silently treated as completed while offline; they remain queued/pending until the server confirms execution.

Offline mode is therefore **store-and-forward**, not fake disconnected execution.
