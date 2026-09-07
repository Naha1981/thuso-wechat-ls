-- v1.2 deterministic payment routing policy
create table if not exists public.payment_route_policies (
 id uuid primary key default gen_random_uuid(),
 country_code varchar(2) not null,
 currency varchar(3) not null,
 provider varchar(40) not null,
 channel varchar(40) not null,
 priority integer not null default 100 check(priority >= 0),
 fee_fixed numeric(18,2) not null default 0 check(fee_fixed >= 0),
 fee_rate numeric(9,6) not null default 0 check(fee_rate >= 0 and fee_rate <= 1),
 max_amount numeric(18,2),
 enabled boolean not null default true,
 health_status varchar(20) not null default 'healthy' check(health_status in ('healthy','degraded','down')),
 supports_refund boolean not null default true,
 supports_payout boolean not null default false,
 metadata jsonb not null default '{}'::jsonb,
 created_at timestamptz not null default now(),
 updated_at timestamptz not null default now(),
 unique(country_code,currency,provider,channel)
);
create index if not exists payment_route_lookup_idx on public.payment_route_policies(country_code,currency,enabled,health_status,priority);
create table if not exists public.payment_route_decisions (
 id uuid primary key default gen_random_uuid(),
 payment_id uuid references public.payments(id) on delete set null,
 country_code varchar(2) not null,
 currency varchar(3) not null,
 amount numeric(18,2) not null,
 selected_provider varchar(40) not null,
 selected_channel varchar(40) not null,
 estimated_fee numeric(18,2) not null default 0,
 score numeric(18,6) not null,
 fallbacks jsonb not null default '[]'::jsonb,
 reason text not null,
 created_at timestamptz not null default now()
);
create index if not exists payment_route_decisions_payment_idx on public.payment_route_decisions(payment_id,created_at desc);
alter table public.payment_route_policies enable row level security;
alter table public.payment_route_decisions enable row level security;
