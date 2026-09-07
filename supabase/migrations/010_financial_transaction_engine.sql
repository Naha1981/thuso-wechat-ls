-- v1.0: production financial transaction engine
create table if not exists public.pricing_quotes (
 id uuid primary key default gen_random_uuid(),
 service_request_id uuid not null references public.service_requests(id) on delete cascade,
 user_id uuid not null references public.users(id),
 currency char(3) not null default 'ZAR',
 subtotal numeric(14,2) not null check(subtotal>=0),
 platform_fee numeric(14,2) not null default 0 check(platform_fee>=0),
 provider_earning numeric(14,2) not null check(provider_earning>=0),
 total numeric(14,2) not null check(total>=0),
 status varchar(20) not null default 'quoted' check(status in ('quoted','accepted','expired','cancelled')),
 expires_at timestamptz not null,
 metadata jsonb not null default '{}'::jsonb,
 created_at timestamptz not null default now(),
 accepted_at timestamptz
);
create index if not exists pricing_quotes_request_idx on public.pricing_quotes(service_request_id,created_at desc);

alter table public.payments add column if not exists authorized_at timestamptz;
alter table public.payments add column if not exists captured_at timestamptz;
alter table public.payments add column if not exists refunded_amount numeric(14,2) not null default 0 check(refunded_amount>=0);
alter table public.payments add column if not exists idempotency_key varchar(160);
create unique index if not exists payments_idempotency_uq on public.payments(idempotency_key) where idempotency_key is not null;

create table if not exists public.payment_events (
 id uuid primary key default gen_random_uuid(),
 payment_id uuid references public.payments(id) on delete cascade,
 provider varchar(40) not null,
 external_event_id varchar(200) not null,
 event_type varchar(80) not null,
 status varchar(20) not null default 'received' check(status in ('received','processed','ignored','failed')),
 payload jsonb not null default '{}'::jsonb,
 created_at timestamptz not null default now(),
 processed_at timestamptz,
 error text,
 unique(provider,external_event_id)
);
create index if not exists payment_events_payment_idx on public.payment_events(payment_id,created_at desc);

create table if not exists public.refunds (
 id uuid primary key default gen_random_uuid(),
 payment_id uuid not null references public.payments(id),
 user_id uuid not null references public.users(id),
 amount numeric(14,2) not null check(amount>0),
 currency char(3) not null default 'ZAR',
 status varchar(20) not null default 'requested' check(status in ('requested','processing','succeeded','failed','cancelled')),
 reference varchar(160) not null unique,
 provider_reference varchar(160),
 reason varchar(160),
 created_at timestamptz not null default now(),
 processed_at timestamptz
);
create index if not exists refunds_payment_idx on public.refunds(payment_id,created_at desc);

create table if not exists public.disputes (
 id uuid primary key default gen_random_uuid(),
 payment_id uuid references public.payments(id),
 service_request_id uuid references public.service_requests(id),
 user_id uuid not null references public.users(id),
 provider_id uuid references public.providers(id),
 amount numeric(14,2) not null check(amount>=0),
 currency char(3) not null default 'ZAR',
 status varchar(24) not null default 'open' check(status in ('open','under_review','resolved_customer','resolved_provider','closed')),
 reason varchar(160) not null,
 description text,
 resolution_note text,
 created_at timestamptz not null default now(),
 resolved_at timestamptz
);
create index if not exists disputes_status_idx on public.disputes(status,created_at desc);

create table if not exists public.provider_payouts (
 id uuid primary key default gen_random_uuid(),
 provider_id uuid not null references public.providers(id),
 amount numeric(14,2) not null check(amount>0),
 currency char(3) not null default 'ZAR',
 status varchar(20) not null default 'requested' check(status in ('requested','processing','paid','failed','cancelled')),
 reference varchar(160) not null unique,
 provider_reference varchar(160),
 created_at timestamptz not null default now(),
 processed_at timestamptz
);
create index if not exists provider_payouts_provider_idx on public.provider_payouts(provider_id,created_at desc);

create table if not exists public.financial_reconciliation_items (
 id uuid primary key default gen_random_uuid(),
 provider varchar(40) not null,
 external_reference varchar(200) not null,
 internal_type varchar(60),
 internal_id uuid,
 expected_amount numeric(14,2),
 actual_amount numeric(14,2),
 currency char(3),
 status varchar(20) not null default 'unmatched' check(status in ('matched','unmatched','mismatch','ignored')),
 metadata jsonb not null default '{}'::jsonb,
 created_at timestamptz not null default now(),
 reconciled_at timestamptz,
 unique(provider,external_reference)
);

create table if not exists public.financial_risk_limits (
 scope varchar(40) primary key,
 max_transaction_amount numeric(14,2) not null default 50000,
 max_daily_amount numeric(14,2) not null default 200000,
 max_daily_count integer not null default 100,
 enabled boolean not null default true,
 updated_at timestamptz not null default now()
);
insert into public.financial_risk_limits(scope,max_transaction_amount,max_daily_amount,max_daily_count)
values ('default',50000,200000,100)
on conflict(scope) do nothing;

alter table public.pricing_quotes enable row level security;
alter table public.payment_events enable row level security;
alter table public.refunds enable row level security;
alter table public.disputes enable row level security;
alter table public.provider_payouts enable row level security;
alter table public.financial_reconciliation_items enable row level security;
alter table public.financial_risk_limits enable row level security;
