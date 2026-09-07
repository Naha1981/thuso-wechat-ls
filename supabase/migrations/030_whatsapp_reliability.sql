-- v2.11: durable WhatsApp inbox/outbox, delivery receipts and account health
alter table public.outbox_messages
  add column if not exists account_key varchar(200);
alter table public.outbox_messages
  add column if not exists idempotency_key varchar(200);
alter table public.outbox_messages
  add column if not exists provider_message_id varchar(200);
alter table public.outbox_messages
  add column if not exists sent_at timestamptz;
alter table public.outbox_messages
  add column if not exists receipt_status varchar(32) not null default 'pending';
alter table public.outbox_messages
  add column if not exists receipt_at timestamptz;
create unique index if not exists outbox_messages_idempotency_idx
  on public.outbox_messages(idempotency_key) where idempotency_key is not null;
create index if not exists outbox_messages_receipt_idx
  on public.outbox_messages(receipt_status, receipt_at) where receipt_status in ('pending','sent','delivered','read','failed');

create table if not exists public.whatsapp_inbox_events (
  id uuid primary key default gen_random_uuid(),
  transport varchar(32) not null,
  account_key varchar(200),
  external_event_id varchar(200) not null,
  event_type varchar(80) not null default 'message',
  payload jsonb not null,
  status varchar(24) not null default 'received' check(status in ('received','processing','processed','failed','dead_letter')),
  attempts integer not null default 0,
  available_at timestamptz not null default now(),
  locked_at timestamptz,
  processed_at timestamptz,
  last_error text,
  created_at timestamptz not null default now(),
  unique(transport,account_key,external_event_id)
);
create index if not exists whatsapp_inbox_pending_idx
  on public.whatsapp_inbox_events(status,available_at,created_at) where status in ('received','failed');
create index if not exists whatsapp_inbox_account_idx
  on public.whatsapp_inbox_events(account_key,created_at desc);

create table if not exists public.whatsapp_delivery_receipts (
  id uuid primary key default gen_random_uuid(),
  outbox_message_id uuid not null references public.outbox_messages(id) on delete cascade,
  transport varchar(32) not null,
  provider_message_id varchar(200),
  status varchar(32) not null,
  occurred_at timestamptz not null default now(),
  metadata jsonb not null default '{}'::jsonb,
  unique(transport,provider_message_id,status) 
);
create index if not exists whatsapp_receipts_outbox_idx
  on public.whatsapp_delivery_receipts(outbox_message_id,occurred_at desc);

create table if not exists public.whatsapp_account_health (
  wa_account_id uuid primary key references public.wa_accounts(id) on delete cascade,
  transport varchar(32) not null,
  state varchar(32) not null default 'unknown',
  consecutive_failures integer not null default 0,
  last_success_at timestamptz,
  last_failure_at timestamptz,
  last_error text,
  circuit_open_until timestamptz,
  updated_at timestamptz not null default now()
);

alter table public.whatsapp_inbox_events enable row level security;
alter table public.whatsapp_delivery_receipts enable row level security;
alter table public.whatsapp_account_health enable row level security;
