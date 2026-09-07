# Naha SuperApp Backend v1.6 — Financial Risk, KYC & Operations Controls

v1.6 adds deterministic financial risk controls and a KYC/KYB foundation without pretending Naha itself is the regulated identity verifier. The platform stores verification state and provider/reviewer references; identity-document collection and regulated verification should be delegated to approved providers or controlled operations workflows.

## Risk controls
- deterministic transaction risk score
- high-value and velocity signals
- failed-payment signal
- account-age signal
- KYC-status signal
- payout/new-destination risk
- ALLOW / REVIEW / BLOCK decision
- persistent risk-assessment schema
- configurable risk-limit schema
- fraud-case schema

## KYC foundation
- customer/provider/business subjects
- verification level and status
- reviewer/reference tracking
- verified/rejected/expired states
- no raw identity documents stored by this milestone

## Regulatory posture
The Central Bank of Lesotho oversees payment systems and licensing of payment-system operators/service providers. Lesotho's regulatory framework includes Payment Systems legislation, KYC guidance and AML/CFT requirements. Naha should therefore treat KYC/AML as a compliance boundary, not as a chatbot feature. Production onboarding requires the applicable licensed/approved verification and payment partners.

## New APIs
- POST /api/v1/risk/score
- POST /api/v1/kyc/profiles
- POST /api/v1/kyc/profiles/{profile_id}/status

## Safety
Risk decisions are server-side and deterministic. The agent cannot lower a risk score, bypass a block, approve its own exception, or change KYC status.
