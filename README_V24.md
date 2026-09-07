# v2.4 — WhatsApp Intelligence & Document Processing

v2.4 turns received WhatsApp media into asynchronous intelligence resources without coupling the product to a single model provider.

## Capabilities

- Voice note transcription jobs
- Image understanding
- PDF/document extraction
- Receipt extraction
- Structured extraction stored as JSON
- Provider/model provenance
- Retryable processing jobs with exponential backoff
- Owner-scoped result access
- KIE.ai multimodal provider adapter
- Provider-agnostic domain contracts

KIE is the default intelligence provider. The adapter targets KIE's OpenAI-compatible multimodal endpoint; the model is configurable because KIE's model catalog changes over time.

## Flow

WhatsApp media → media_objects → processing job → intelligence provider → structured result → agent/domain context

No intelligence call happens inside the WhatsApp webhook transaction.

## Security

- KIE credentials remain server-side.
- External providers receive short-lived signed media URLs rather than storage credentials.
- Local development storage cannot be sent to external providers.
- Results are scoped to the media owner's user identity.
- Failed provider jobs retry up to five attempts, then fail closed.

## Next slice

v2.5 should add a durable worker process for these jobs plus provider callbacks/polling, conversation-context injection, and domain-specific document schemas for invoices, IDs, customs documents, menus, and receipts.
