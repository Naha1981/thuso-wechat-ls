-- v1.1: Lesotho payment-provider abstraction and mobile-money channels
alter table public.payments add column if not exists provider varchar(40);
alter table public.payments add column if not exists channel varchar(40);
alter table public.payments add column if not exists checkout_url text;
alter table public.payments add column if not exists initiated_at timestamptz;
create index if not exists payments_provider_idx on public.payments(provider,created_at desc);
create table if not exists public.payment_provider_accounts (
 id uuid primary key default gen_random_uuid(),
 user_id uuid not null references public.users(id) on delete cascade,
 provider varchar(40) not null,
 channel varchar(40) not null,
 external_customer_ref varchar(200),
 phone_e164 varchar(32),
 status varchar(20) not null default 'active' check(status in ('active','pending','disabled')),
 metadata jsonb not null default '{}'::jsonb,
 created_at timestamptz not null default now(),
 updated_at timestamptz not null default now(),
 unique(user_id,provider,channel)
);
create index if not exists payment_provider_accounts_phone_idx on public.payment_provider_accounts(phone_e164);
alter table public.payment_provider_accounts enable row level security;
