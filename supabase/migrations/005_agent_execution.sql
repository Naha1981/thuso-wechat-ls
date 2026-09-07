-- v0.5: transactional agent execution + inbound/outbound WhatsApp state
create table if not exists public.agent_message_dedup (
  id uuid primary key default gen_random_uuid(),
  channel varchar(30) not null,
  external_message_id varchar(200) not null,
  user_id uuid references public.users(id) on delete set null,
  received_at timestamptz not null default now(),
  unique(channel, external_message_id)
);

create table if not exists public.agent_action_events (
  id uuid primary key default gen_random_uuid(),
  action_id uuid not null references public.agent_actions(id) on delete cascade,
  event_type varchar(40) not null,
  actor_user_id uuid references public.users(id),
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create index if not exists agent_action_events_action_idx on public.agent_action_events(action_id, created_at);

create table if not exists public.conversation_messages (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  channel varchar(30) not null default 'whatsapp',
  direction varchar(10) not null check(direction in ('inbound','outbound')),
  external_message_id varchar(200),
  message_type varchar(30) not null default 'text',
  body text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique(channel, external_message_id)
);
create index if not exists conversation_messages_user_created_idx on public.conversation_messages(user_id, created_at desc);

alter table public.agent_message_dedup enable row level security;
alter table public.agent_action_events enable row level security;
alter table public.conversation_messages enable row level security;
