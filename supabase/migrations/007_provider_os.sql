create table if not exists public.provider_onboarding_sessions (
 id uuid primary key default gen_random_uuid(),
 owner_user_id uuid not null references public.users(id) on delete cascade,
 status varchar(20) not null default 'collecting' check(status in ('collecting','submitted','approved','rejected','cancelled')),
 category varchar(40),
 business_name varchar(160),
 metadata jsonb not null default '{}'::jsonb,
 expires_at timestamptz not null default now() + interval '30 minutes',
 created_at timestamptz not null default now(),
 updated_at timestamptz not null default now()
);
create index if not exists provider_onboarding_owner_idx on public.provider_onboarding_sessions(owner_user_id,status);

alter table public.providers add column if not exists phone_e164 varchar(20);
alter table public.providers add column if not exists rating numeric(3,2) not null default 0 check(rating>=0 and rating<=5);
alter table public.providers add column if not exists jobs_completed bigint not null default 0 check(jobs_completed>=0);
alter table public.providers add column if not exists last_active_at timestamptz;
create unique index if not exists providers_phone_uq on public.providers(phone_e164) where phone_e164 is not null;
create index if not exists providers_status_active_idx on public.providers(status,last_active_at desc);

alter table public.service_offers add column if not exists notified_at timestamptz;
alter table public.service_offers add column if not exists response_note text;

create table if not exists public.provider_earnings (
 id uuid primary key default gen_random_uuid(),
 provider_id uuid not null references public.providers(id) on delete cascade,
 service_request_id uuid references public.service_requests(id),
 amount numeric(14,2) not null check(amount>=0),
 currency char(3) not null default 'ZAR',
 status varchar(20) not null default 'pending' check(status in ('pending','available','paid','reversed')),
 reference varchar(160) not null unique,
 metadata jsonb not null default '{}'::jsonb,
 created_at timestamptz not null default now(),
 paid_at timestamptz
);
create index if not exists provider_earnings_provider_idx on public.provider_earnings(provider_id,created_at desc);

create table if not exists public.provider_action_dedup (
 provider_id uuid not null references public.providers(id) on delete cascade,
 external_message_id varchar(200) not null,
 created_at timestamptz not null default now(),
 primary key(provider_id,external_message_id)
);

alter table public.provider_onboarding_sessions enable row level security;
alter table public.provider_earnings enable row level security;
alter table public.provider_action_dedup enable row level security;
