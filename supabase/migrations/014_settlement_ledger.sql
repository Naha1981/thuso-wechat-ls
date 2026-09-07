-- v1.4: immutable settlement journal, provider reserves and payout execution
create table if not exists public.financial_journals (
 id uuid primary key default gen_random_uuid(),
 journal_type varchar(40) not null,
 reference varchar(180) not null unique,
 currency char(3) not null,
 description text,
 created_at timestamptz not null default now()
);
create table if not exists public.financial_journal_lines (
 id uuid primary key default gen_random_uuid(),
 journal_id uuid not null references public.financial_journals(id) on delete cascade,
 account_code varchar(60) not null,
 direction varchar(10) not null check(direction in ('debit','credit')),
 amount numeric(14,2) not null check(amount>0),
 entity_type varchar(40), entity_id uuid,
 metadata jsonb not null default '{}'::jsonb
);
create index if not exists financial_journal_lines_journal_idx on public.financial_journal_lines(journal_id);
create index if not exists financial_journal_lines_entity_idx on public.financial_journal_lines(entity_type,entity_id);

create table if not exists public.payment_settlements (
 id uuid primary key default gen_random_uuid(),
 payment_id uuid not null references public.payments(id) on delete cascade,
 service_request_id uuid references public.service_requests(id),
 provider_id uuid references public.providers(id),
 currency char(3) not null,
 gross_amount numeric(14,2) not null check(gross_amount>0),
 platform_fee numeric(14,2) not null default 0 check(platform_fee>=0),
 provider_amount numeric(14,2) not null check(provider_amount>=0),
 status varchar(24) not null default 'pending' check(status in ('pending','settled','reversed','partially_reversed')),
 journal_id uuid references public.financial_journals(id),
 settled_at timestamptz,
 created_at timestamptz not null default now(),
 unique(payment_id)
);

create table if not exists public.provider_balance_reserves (
 id uuid primary key default gen_random_uuid(),
 provider_id uuid not null references public.providers(id),
 payment_id uuid references public.payments(id),
 amount numeric(14,2) not null check(amount>0),
 currency char(3) not null,
 status varchar(20) not null default 'held' check(status in ('held','released','consumed')),
 reference varchar(180) not null unique,
 created_at timestamptz not null default now(),
 released_at timestamptz
);
create index if not exists provider_reserves_provider_idx on public.provider_balance_reserves(provider_id,status,currency);

create table if not exists public.payout_attempts (
 id uuid primary key default gen_random_uuid(),
 payout_id uuid not null references public.provider_payouts(id) on delete cascade,
 provider varchar(40) not null,
 channel varchar(40) not null,
 attempt_no integer not null,
 status varchar(24) not null default 'pending' check(status in ('pending','processing','succeeded','failed')),
 external_reference varchar(180),
 error text,
 created_at timestamptz not null default now(),
 completed_at timestamptz,
 unique(payout_id,attempt_no)
);

create table if not exists public.reconciliation_batches (
 id uuid primary key default gen_random_uuid(),
 provider varchar(40) not null,
 currency char(3) not null,
 period_start timestamptz not null,
 period_end timestamptz not null,
 status varchar(20) not null default 'open' check(status in ('open','matched','exception')),
 matched_count integer not null default 0,
 exception_count integer not null default 0,
 created_at timestamptz not null default now(),
 closed_at timestamptz
);

alter table public.financial_journals enable row level security;
alter table public.financial_journal_lines enable row level security;
alter table public.payment_settlements enable row level security;
alter table public.provider_balance_reserves enable row level security;
alter table public.payout_attempts enable row level security;
alter table public.reconciliation_batches enable row level security;
