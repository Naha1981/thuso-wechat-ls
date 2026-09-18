-- NahaOS webhook idempotency
create unique index if not exists partner_webhook_event_unique_idx
  on public.partner_webhook_events(provider_key, event_id)
  where event_id is not null;
