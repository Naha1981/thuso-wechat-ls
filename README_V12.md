# Naha SuperApp Backend v1.2

## Payment Routing Engine — Lesotho

v1.2 adds deterministic payment routing on top of the v1.1 provider abstraction.

### Design

The routing engine selects a payment route using server-side policy:

1. Country/currency eligibility
2. Requested channel/provider constraints
3. Provider enabled/health status
4. Transaction amount limits
5. Configured priority
6. Estimated provider fee
7. Deterministic fallback order

No LLM or agent is involved in selecting the financial rail.

### Important provider policy

The code distinguishes **licensed mobile-money issuers** from **payment gateways/aggregators**. A gateway such as MoPay or Pay Lesotho is not treated as a mobile-money issuer itself. Direct integrations are enabled only after the provider supplies its production API contract, credentials, webhook specification and commercial approval.

Current CBL directory data should be synchronized periodically rather than hard-coded as permanent truth. The Central Bank directory currently lists five mobile-money issuers: Chaperone Ltd, Lesotho Postbank, Smartel Money Ltd, VCL Financial Services (Pty) Ltd, and Sasai Econet Financial Services (Pty) Ltd.

### New database tables

- `payment_route_policies`
- `payment_route_decisions`

### API

`POST /api/v1/payment-routing/LS/quote`

Example:

```json
{
  "amount": 250,
  "currency": "LSL",
  "channel": "mpesa"
}
```

The response includes the selected provider, channel, estimated fee, score and deterministic fallbacks.

### Production note

Fee values and health state must be populated from approved merchant/provider configuration. The default in-memory policy is intentionally conservative and is not a claim about real provider pricing.
