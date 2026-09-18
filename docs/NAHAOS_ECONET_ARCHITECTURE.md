# NahaOS / THUSO — Econet AI Architecture

## Product decision

THUSO remains the existing Lesotho super-app codebase. It evolves into **NahaOS / THUSO**, an AI-orchestrated digital services platform.

Econet AI is a first-class provider, not a hard dependency.

## Layering

```
Channels
  WhatsApp | Web | USSD | Voice
       |
Identity + Consent + Permissions
       |
AI Gateway + Agent Orchestrator
       |
Policy Engine + Tool Registry
       |
Service Gateway
  Government | Education | Health | Justice | Business | Agriculture
       |
Payment Gateway
  EcoCash | M-Pesa | Banks | Other approved providers
       |
Systems of Record / Partner APIs
```

## AI provider contract

All AI providers implement the same internal contract.

```
AIProvider
  chat()
  health()
  capabilities()
```

The initial adapters are:
- demo provider
- generic HTTP provider
- future Econet/CAIMEx adapter

The Econet adapter must be the only place containing Econet-specific authentication, endpoint paths and payload mapping.

## Integration rule

Never guess partner endpoints, credentials, scopes or transaction semantics. The partner contract is the source of truth.

## Safety

AI may propose actions. High-impact actions require:
- authenticated identity
- permission check
- policy check
- explicit confirmation where required
- idempotency
- audit event
- receipt

Government records remain authoritative in their source systems.

## Vertical modules

Verticals are configuration and tool packages over the common platform, not separate applications:
- Citizen services
- Health
- Education
- Justice
- Employment
- Business/Government
- Payments
- Agriculture
- Commerce
- Geospatial intelligence

## Econet plug-in flow

```
NahaOS
  -> AIProvider contract
  -> Econet adapter
  -> Econet/Cassava approved endpoint
  -> response normalized
  -> agent/tool execution
```

Changing provider credentials or endpoint configuration must not require changes to citizen-facing workflows.
