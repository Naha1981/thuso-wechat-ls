create extension if not exists pgcrypto;

create table if not exists public.provider_capabilities (
 id uuid primary key default gen_random_uuid(),
 provider_id uuid not null references public.providers(id) on delete cascade,
 capability varchar(80) not null,
 enabled boolean not null default true,
 created_at timestamptz not null default now(),
 unique(provider_id, capability)
);
create index if not exists provider_capabilities_lookup_idx on public.provider_capabilities(capability, enabled, provider_id);

create table if not exists public.service_offers (
 id uuid primary key default gen_random_uuid(),
 service_request_id uuid not null references public.service_requests(id) on delete cascade,
 provider_id uuid not null references public.providers(id),
 status varchar(20) not null default 'pending' check(status in ('pending','accepted','rejected','expired','cancelled')),
 quoted_amount numeric(14,2) check(quoted_amount >= 0),
 eta_seconds integer check(eta_seconds >= 0),
 expires_at timestamptz,
 created_at timestamptz not null default now(),
 responded_at timestamptz,
 unique(service_request_id, provider_id)
);
create index if not exists service_offers_request_status_idx on public.service_offers(service_request_id,status);
create index if not exists service_offers_provider_status_idx on public.service_offers(provider_id,status);

alter table public.service_requests add column if not exists accepted_provider_id uuid references public.providers(id);
alter table public.service_requests add column if not exists version bigint not null default 1;
alter table public.service_requests add column if not exists cancelled_at timestamptz;
alter table public.service_requests add column if not exists completed_at timestamptz;
create index if not exists service_requests_provider_status_idx on public.service_requests(accepted_provider_id,status);

create table if not exists public.provider_locations (
 provider_id uuid primary key references public.providers(id) on delete cascade,
 location geography(point,4326) not null,
 heading numeric(6,2),
 speed_kmh numeric(8,2),
 updated_at timestamptz not null default now()
);
create index if not exists provider_locations_geo_idx on public.provider_locations using gist(location);

create table if not exists public.payments (
 id uuid primary key default gen_random_uuid(),
 user_id uuid references public.users(id),
 provider_id uuid references public.providers(id),
 service_request_id uuid references public.service_requests(id),
 reference varchar(120) not null unique,
 provider_reference varchar(160),
 amount numeric(14,2) not null check(amount>=0),
 currency char(3) not null default 'ZAR',
 status varchar(20) not null default 'pending' check(status in ('pending','authorized','paid','failed','refunded','cancelled')),
 metadata jsonb not null default '{}'::jsonb,
 created_at timestamptz not null default now(),
 updated_at timestamptz not null default now()
);
create index if not exists payments_user_created_idx on public.payments(user_id,created_at desc);
create index if not exists payments_request_idx on public.payments(service_request_id);

create table if not exists public.ledger_accounts (
 id uuid primary key default gen_random_uuid(),
 owner_user_id uuid references public.users(id),
 owner_provider_id uuid references public.providers(id),
 currency char(3) not null default 'ZAR',
 created_at timestamptz not null default now(),
 check ((owner_user_id is not null) <> (owner_provider_id is not null))
);
create unique index if not exists ledger_user_currency_uq on public.ledger_accounts(owner_user_id,currency) where owner_user_id is not null;
create unique index if not exists ledger_provider_currency_uq on public.ledger_accounts(owner_provider_id,currency) where owner_provider_id is not null;

create table if not exists public.wallet_ledger_entries (
 id uuid primary key default gen_random_uuid(),
 account_id uuid not null references public.ledger_accounts(id),
 reference varchar(160) not null,
 direction varchar(10) not null check(direction in ('credit','debit')),
 amount numeric(14,2) not null check(amount>0),
 currency char(3) not null default 'ZAR',
 metadata jsonb not null default '{}'::jsonb,
 created_at timestamptz not null default now(),
 unique(account_id,reference,direction)
);
create index if not exists wallet_ledger_entries_account_created_idx on public.wallet_ledger_entries(account_id,created_at desc);

create table if not exists public.outbox_events (
 id uuid primary key default gen_random_uuid(),
 aggregate_type varchar(60) not null,
 aggregate_id uuid not null,
 event_type varchar(100) not null,
 payload jsonb not null,
 status varchar(20) not null default 'pending' check(status in ('pending','processing','published','failed')),
 attempts integer not null default 0,
 available_at timestamptz not null default now(),
 locked_at timestamptz,
 created_at timestamptz not null default now(),
 published_at timestamptz
);
create index if not exists outbox_pending_idx on public.outbox_events(status,available_at,created_at) where status='pending';

create table if not exists public.audit_events (
 id uuid primary key default gen_random_uuid(),
 actor_user_id uuid references public.users(id),
 event_type varchar(100) not null,
 entity_type varchar(60),
 entity_id uuid,
 request_id varchar(120),
 payload jsonb not null default '{}'::jsonb,
 created_at timestamptz not null default now()
);
create index if not exists audit_entity_idx on public.audit_events(entity_type,entity_id,created_at desc);

alter table public.provider_capabilities enable row level security;
alter table public.service_offers enable row level security;
alter table public.provider_locations enable row level security;
alter table public.payments enable row level security;
alter table public.ledger_accounts enable row level security;
alter table public.wallet_ledger_entries enable row level security;
alter table public.outbox_events enable row level security;
alter table public.audit_events enable row level security;
