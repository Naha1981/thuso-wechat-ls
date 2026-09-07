create table if not exists public.agent_sessions (
 id uuid primary key default gen_random_uuid(),
 user_id uuid not null references public.users(id) on delete cascade,
 channel varchar(30) not null default 'whatsapp',
 state jsonb not null default '{}'::jsonb,
 status varchar(20) not null default 'active' check(status in ('active','expired','closed')),
 expires_at timestamptz not null,
 created_at timestamptz not null default now(),
 updated_at timestamptz not null default now()
);
create index if not exists agent_sessions_user_active_idx on public.agent_sessions(user_id,updated_at desc) where status='active';

create table if not exists public.agent_actions (
 id uuid primary key default gen_random_uuid(),
 user_id uuid not null references public.users(id) on delete cascade,
 session_id uuid references public.agent_sessions(id) on delete set null,
 action varchar(80) not null,
 risk varchar(20) not null check(risk in ('low','medium','high')),
 status varchar(24) not null default 'pending' check(status in ('pending','approved','declined','executed','failed','expired')),
 payload jsonb not null default '{}'::jsonb,
 result jsonb,
 idempotency_key varchar(160) unique,
 created_at timestamptz not null default now(),
 approved_at timestamptz,
 executed_at timestamptz
);
create index if not exists agent_actions_user_created_idx on public.agent_actions(user_id,created_at desc);
create index if not exists agent_actions_pending_idx on public.agent_actions(status,created_at) where status='pending';

create table if not exists public.agent_receipts (
 id uuid primary key default gen_random_uuid(),
 action_id uuid not null references public.agent_actions(id) on delete cascade,
 user_id uuid not null references public.users(id) on delete cascade,
 action varchar(80) not null,
 authority varchar(80) not null default 'one_time_confirmation',
 result jsonb not null default '{}'::jsonb,
 created_at timestamptz not null default now()
);
create index if not exists agent_receipts_user_created_idx on public.agent_receipts(user_id,created_at desc);

alter table public.agent_sessions enable row level security;
alter table public.agent_actions enable row level security;
alter table public.agent_receipts enable row level security;
