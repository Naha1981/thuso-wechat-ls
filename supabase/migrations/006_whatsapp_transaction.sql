-- v0.6: WhatsApp transaction lifecycle + verified payment webhooks
alter table public.outbox_messages add column if not exists locked_at timestamptz;
alter table public.outbox_messages add column if not exists last_error text;
create index if not exists outbox_messages_processing_idx on public.outbox_messages(status,locked_at);

create table if not exists public.payment_webhook_events (
 id uuid primary key default gen_random_uuid(),
 provider varchar(40) not null,
 external_id varchar(200) not null,
 signature_valid boolean not null,
 payload jsonb not null,
 received_at timestamptz not null default now(),
 processed_at timestamptz,
 unique(provider,external_id)
);
create index if not exists payment_webhook_events_pending_idx on public.payment_webhook_events(received_at) where processed_at is null;
alter table public.payment_webhook_events enable row level security;
