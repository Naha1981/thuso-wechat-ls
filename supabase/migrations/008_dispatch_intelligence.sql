-- v0.8: deterministic marketplace dispatch intelligence
alter table public.providers add column if not exists response_rate numeric(5,4) not null default 0 check(response_rate>=0 and response_rate<=1);
alter table public.service_offers add column if not exists dispatch_score numeric(10,8);
alter table public.service_offers add column if not exists dispatch_wave integer not null default 1;
create index if not exists service_offers_wave_idx on public.service_offers(service_request_id,dispatch_wave,status);

create table if not exists public.dispatch_attempts (
 id uuid primary key default gen_random_uuid(),
 service_request_id uuid not null references public.service_requests(id) on delete cascade,
 wave integer not null,
 candidate_count integer not null default 0,
 offered_count integer not null default 0,
 status varchar(20) not null default 'sent' check(status in ('sent','timeout','accepted','cancelled')),
 created_at timestamptz not null default now(),
 completed_at timestamptz
);
create unique index if not exists dispatch_attempt_wave_uq on public.dispatch_attempts(service_request_id,wave);
create index if not exists dispatch_attempt_request_idx on public.dispatch_attempts(service_request_id,created_at desc);
alter table public.dispatch_attempts enable row level security;
