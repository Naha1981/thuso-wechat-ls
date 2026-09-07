# v2.3 — WhatsApp Media & Content Infrastructure

The platform now treats WhatsApp media as a first-class asynchronous resource while keeping Baileys isolated in the standalone operator service.

## Flow

1. Operator receives a WhatsApp image/document/audio/video.
2. Operator forwards only normalized metadata to the main app.
3. Main app creates a pending `media_objects` row tied to the WhatsApp message and platform user.
4. Operator downloads/decrypts the media with Baileys and sends the raw bytes to the signed internal media endpoint.
5. Main app hashes, size-checks and magic-byte validates the content before marking it ready.
6. Raw bytes are never stored in PostgreSQL. `storage_key` is content-addressed for object storage.
7. Voice notes create a transcription job; delivery proof can reference the resulting media object.

## Security

- HMAC protects operator → main media ingress.
- User-facing media grants are short-lived and hashed at rest.
- Filenames are sanitized and never become storage paths.
- Declared MIME types are not trusted without content sniffing.
- Per-media-type size limits fail closed.
- No raw media is included in WhatsApp webhook payloads.

## Storage

`media_objects.storage_key` is provider-neutral (`sha256/aa/bb/<hash>.<ext>`). The next storage adapter can target Supabase Storage, S3-compatible storage, or another private object store without changing the domain model.
