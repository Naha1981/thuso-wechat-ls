# THUSO / NahaOS

> **Ask THUSO. Get it done.**

**Current release: v2.18.0 — NahaOS/Econet AI integration foundation**

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

Configuration defaults to demo mode. For the Econet adapter use `AI_PROVIDER=econet` and supply only the credentials/endpoint values provided by Econet.

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

Run `pytest`, `ruff check .`, and `python -m compileall app`.

External provider, WhatsApp, Supabase and payment integrations require their respective credentials/contracts and are intentionally not fabricated.