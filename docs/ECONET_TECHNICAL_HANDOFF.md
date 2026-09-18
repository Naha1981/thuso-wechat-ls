# Econet Technical Handoff

## What Econet needs to provide

The NahaOS core does not require direct API access during development. For production integration, Econet provides the approved:

- API base URL
- authentication method and credential issuance process
- OAuth scopes or API permissions
- model/service identifiers
- request/response schema
- rate limits
- timeout/retry rules
- webhook/event specification
- error codes
- sandbox/test credentials
- production promotion process
- data residency/privacy requirements
- approved transaction/action capabilities

## What NahaLabs will not guess

No endpoint path, header, scope, payload field, payment status or transaction semantics will be invented. The adapter is implemented from the signed/approved technical contract.

## Configuration boundary

The deployment environment supplies the partner configuration. Secrets are never stored in GitHub source.

Example:

`AI_PROVIDER=http`
`AI_PROVIDER_NAME=econet`
`AI_BASE_URL=<Econet-approved-base-url>`
`AI_API_KEY=<secret-store-reference>`
`AI_MODEL=<Econet-approved-model>`

If Econet uses a non-OpenAI-compatible API, NahaLabs implements an `EconetAIProvider` adapter that translates between the partner schema and the internal `AIProvider` contract. Citizen-facing code does not change.

## Acceptance test

Before production, Econet and NahaLabs should jointly execute:

1. authentication test
2. health/capability test
3. simple AI request
4. timeout/retry test
5. rate-limit test
6. malformed-response test
7. audit/trace test
8. data/privacy test
9. load test
10. rollback/fallback test

Only after these pass is the provider promoted from demo/sandbox to production.