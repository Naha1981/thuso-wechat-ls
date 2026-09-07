-- v1.5: operational reconciliation, payout state machine and exceptions
create table if not exists public.reconciliation_items (
 id uuid primary key default gen_random_uuid(),
 batch_id uuid not null references public.reconciliation_batches(id) on delete cascade,
 external_reference varchar(180),
 payment_id uuid references public.payments(id),
 payout_id uuid references public.provider_payouts(id),
 amount numeric(14,2) not null,
 currency char(3) not null,
 external_status varchar(40),
 internal_status varchar(40),
 match_status varchar(20) not null default 'unmatched' check(match_status in ('matched','unmatched','exception')),
 mismatch_code varchar(60),
 metadata jsonb not null default '{}'::jsonb,
 created_at timestamptz not null default now(),
 unique(batch_id,external_reference)
);
create index if not exists reconciliation_items_batch_idx on public.reconciliation_items(batch_id,match_status);
create index if not exists reconciliation_items_payment_idx on public.reconciliation_items(payment_id);

create table if not exists public.reconciliation_exceptions (
 id uuid primary key default gen_random_uuid(),
 batch_id uuid not null references public.reconciliation_batches(id) on delete cascade,
 item_id uuid references public.reconciliation_items(id) on delete cascade,
 code varchar(60) not null,
 severity varchar(20) not null default 'high' check(severity in ('low','medium','high','critical')),
 description text not null,
 status varchar(20) not null default 'open' check(status in ('open','resolved','ignored')),
 resolution text,
 created_at timestamptz not null default now(),
 resolved_at timestamptz
);
create index if not exists reconciliation_exceptions_batch_idx on public.reconciliation_exceptions(batch_id,status);

create table if not exists public.payout_destinations (
 id uuid primary key default gen_random_uuid(),
 provider_id uuid not null references public.providers(id) on delete cascade,
 rail varchar(40) not null,
 destination_ref varchar(180) not null,
 currency char(3) not null default 'LSL',
 status varchar(20) not null default 'pending' check(status in ('pending','verified','suspended')),
 metadata jsonb not null default '{}'::jsonb,
 created_at timestamptz not null default now(),
 verified_at timestamptz,
 unique(provider_id,rail,destination_ref)
);
create index if not exists payout_destinations_provider_idx on public.payout_destinations(provider_id,status);

alter table public.reconciliation_items enable row level security;
alter table public.reconciliation_exceptions enable row level security;
alter table public.payout_destinations enable row level security;
