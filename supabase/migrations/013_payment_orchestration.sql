create table if not exists public.payment_attempts (
 id uuid primary key default gen_random_uuid(),
 payment_id uuid not null references public.payments(id) on delete cascade,
 provider varchar(40) not null,
 channel varchar(40) not null,
 attempt_no integer not null,
 status varchar(30) not null,
 provider_reference varchar(160),
 checkout_url text,
 error_code varchar(80),
 error_message text,
 created_at timestamptz not null default now(),
 completed_at timestamptz,
 unique(payment_id,attempt_no)
);
create index if not exists payment_attempts_payment_idx on public.payment_attempts(payment_id,attempt_no desc);
alter table public.payment_attempts enable row level security;
