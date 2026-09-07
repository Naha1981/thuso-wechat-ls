create extension if not exists pgcrypto;
create extension if not exists postgis;

create table if not exists public.users (
  id uuid primary key default gen_random_uuid(),
  phone_e164 varchar(20) not null unique,
  display_name varchar(120),
  locale varchar(12) not null default 'en-ZA',
  created_at timestamptz not null default now()
);

create table if not exists public.providers (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid not null references public.users(id),
  category varchar(40) not null,
  business_name varchar(160) not null,
  status varchar(20) not null default 'pending',
  metadata jsonb not null default '{}'::jsonb,
  location geography(point,4326),
  created_at timestamptz not null default now()
);

create index if not exists providers_category_status_idx on public.providers(category, status);
create index if not exists providers_location_gix on public.providers using gist(location);

create table if not exists public.service_requests (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id),
  category varchar(40) not null,
  status varchar(24) not null default 'open',
  pickup_lat numeric(9,6),
  pickup_lng numeric(9,6),
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create index if not exists service_requests_user_created_idx on public.service_requests(user_id, created_at desc);
create index if not exists service_requests_category_status_idx on public.service_requests(category, status);

create table if not exists public.messages (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references public.users(id),
  direction varchar(10) not null check (direction in ('inbound','outbound')),
  provider varchar(30) not null default 'whatsapp',
  external_id varchar(200) not null,
  message_type varchar(30) not null,
  body text,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique(provider, external_id)
);
create index if not exists messages_user_created_idx on public.messages(user_id, created_at desc);

create table if not exists public.ledger_entries (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id),
  direction varchar(10) not null check (direction in ('credit','debit')),
  amount numeric(14,2) not null check (amount >= 0),
  currency char(3) not null default 'ZAR',
  reference varchar(160) not null unique,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create index if not exists ledger_user_created_idx on public.ledger_entries(user_id, created_at desc);

create table if not exists public.webhook_events (
  id uuid primary key default gen_random_uuid(),
  provider varchar(40) not null,
  external_id varchar(200) not null,
  event_type varchar(100),
  payload jsonb not null,
  received_at timestamptz not null default now(),
  processed_at timestamptz,
  error text,
  unique(provider, external_id)
);
create index if not exists webhook_events_unprocessed_idx on public.webhook_events(received_at) where processed_at is null;

create table if not exists public.outbox_messages (
  id uuid primary key default gen_random_uuid(),
  channel varchar(30) not null,
  recipient varchar(200) not null,
  message_type varchar(40) not null,
  payload jsonb not null,
  status varchar(20) not null default 'pending',
  attempts int not null default 0,
  available_at timestamptz not null default now(),
  sent_at timestamptz,
  last_error text,
  created_at timestamptz not null default now()
);
create index if not exists outbox_pending_idx on public.outbox_messages(status, available_at) where status='pending';

alter table public.users enable row level security;
alter table public.providers enable row level security;
alter table public.service_requests enable row level security;
alter table public.messages enable row level security;
alter table public.ledger_entries enable row level security;
alter table public.webhook_events enable row level security;
alter table public.outbox_messages enable row level security;

-- API workers use the Supabase service role and bypass RLS. Browser clients should never receive it.
