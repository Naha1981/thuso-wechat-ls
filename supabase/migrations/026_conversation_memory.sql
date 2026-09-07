-- v2.7: scoped conversation memory/context
create table if not exists public.conversation_summaries (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  channel varchar(30) not null default 'whatsapp',
  summary text not null,
  message_count integer not null default 0,
  last_message_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(user_id, channel)
);

create table if not exists public.conversation_memory (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  channel varchar(30) not null default 'whatsapp',
  memory_type varchar(40) not null check(memory_type in ('preference','fact','task_context')),
  memory_key varchar(120) not null,
  memory_value text not null,
  source_message_id uuid references public.conversation_messages(id) on delete set null,
  confidence numeric(5,4) not null default 1.0,
  expires_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(user_id, channel, memory_type, memory_key)
);
create index if not exists conversation_memory_lookup_idx on public.conversation_memory(user_id, channel, updated_at desc);
create index if not exists conversation_memory_expiry_idx on public.conversation_memory(expires_at);

create table if not exists public.conversation_context_events (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  channel varchar(30) not null,
  event_type varchar(50) not null,
  source_message_id uuid references public.conversation_messages(id) on delete set null,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create index if not exists conversation_context_events_user_idx on public.conversation_context_events(user_id, channel, created_at desc);

alter table public.conversation_summaries enable row level security;
alter table public.conversation_memory enable row level security;
alter table public.conversation_context_events enable row level security;
