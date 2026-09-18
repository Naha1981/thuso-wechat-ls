# NahaOS Economic Operating System

NahaOS is the single Lesotho digital doorway for citizens, families, merchants, businesses and service providers. Former standalone concepts are now modules inside the same platform.

## Core principle

**One identity → one conversation → one policy layer → many services → one ledger/audit trail.**

Channels can include WhatsApp first, Web, USSD and future voice.

## Product modules

| Module | Purpose |
|---|---|
| Identity | One profile, consent, sessions and permissions |
| Government | Public services, applications, certificates and status |
| Health | Appointments, referrals and health journeys |
| Education | Schools, exams, qualifications and bursaries |
| Justice | Cases, documents and legal-aid workflows |
| Jobs & Skills | CVs, jobs, applications and verification |
| Food | Restaurants, menus, checkout, delivery and tracking |
| Transport | Ride requests, offers and tracking |
| Shopping | Product discovery, ordering and fulfilment |
| Ramalaisha | Diaspora-to-family grocery/retail fulfilment |
| SME Business / SkyPay | POS, sales, inventory and expenses |
| Payments | Banks, wallets and payment routing |
| Credit | Eligibility, financing and repayments |
| Tax & Trade | VAT, tax reporting, customs and trade |
| Agriculture | Farmer services, inputs, markets and forecasting |
| Telecom | Airtime, bundles and telecom commerce |
| Travel | Transport, accommodation and itinerary services |
| Logistics | Dispatch, tracking and proof of delivery |
| Financial Literacy | WhatsApp tutoring for money and business |
| AegisGrid | Fraud, risk, anomaly and credit intelligence |
| AI Gateway | AI routing, tool selection and traceability |
| Integration Hub | External service/provider adapters |

## Architecture

```text
WhatsApp / Web / USSD / Voice
          ↓
Identity + Consent + Permissions
          ↓
NahaOS AI Gateway / Agent
          ↓
Policy + Tool Registry
          ↓
Service Gateway
          ↓
Government / Commerce / Transport / Payments / Telecom / Enterprise APIs
          ↓
Core systems + Ledger + Audit + Receipts
```

### AI provider boundary

```text
Econet AI
   ↓
EconetAIProvider
   ↓
AIProvider
   ↓
NahaOS Agent + Policy + Tools
```

Econet is an AI provider, not the definition of the NahaOS product. Other approved AI providers can sit behind the same contract.

## Status vocabulary

- **live_foundation:** already represented by working NahaOS primitives.
- **wired:** part of the platform product model and agent vocabulary, ready for provider/workflow implementation.
- **provider_required:** an external API/contract/credential is needed before production execution.

The catalogue is exposed through `GET /api/v1/capabilities` so Web, WhatsApp operators and future apps can discover the same NahaOS service map.

## Economic operating loops

### SkyPay
Merchant → sale/expense → inventory movement → ledger → daily summary → risk/credit signal.

### Ramalaisha
Diaspora sender → family/recipient → grocery basket → retailer fulfilment → OTP/pickup or delivery → payment → receipt.

### AegisGrid
Transaction/service events → fraud/risk/anomaly signals → controlled decision support → audit.

### Credit
Verified business/transaction history → eligibility → application → approval by authorised lender/policy → disbursement → repayment tracking.

### Tax & trade
Sales/import/export events → classification → tax/customs records → reporting → anomaly signals.

### Agriculture
Farmer profile → inputs/market data → orders/services → harvest/yield signals → supply planning.

### Financial literacy
User question → personalised micro-lesson → practical action → follow-up insight.

All consequential financial, government or partner actions must remain deterministic, authorised and auditable; AI may assist but does not silently execute them.
