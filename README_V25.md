# Naha SuperApp v2.5 — Media Intelligence Worker

v2.5 turns the v2.4 intelligence job tables into a continuously running worker pipeline:

WhatsApp/Baileys → media storage → `media_processing_jobs` → Redis Stream → consumer group → KIE multimodal processing → result/context → optional WhatsApp response.

## Durable design

- PostgreSQL remains the source of truth.
- Redis Streams provides distributed worker delivery and backpressure.
- A periodic DB sweep republishes pending jobs if Redis was unavailable after job creation.
- Consumers re-check DB state before processing, making duplicate stream entries harmless.
- Failed provider calls are recorded by the existing retry/backoff logic.
- Automatic responses are **off by default** (`INTELLIGENCE_AUTO_REPLY=false`).
- Consequential actions still go through the existing agent confirmation/risk layer.

## Worker

```bash
python -m app.services.media_intelligence_worker
```

The worker requires Redis and the existing database/provider environment.

## KIE

The KIE Gemini OpenAI-compatible endpoint uses one `image_url` content item for image, video, audio and document URLs; this is the documented unified media structure. The model endpoint is configurable.

## Next

v2.6 should connect completed intelligence context directly into the WhatsApp agent/router, add provider/model routing and cost budgets, and add dead-letter/recovery handling for Redis pending entries.
