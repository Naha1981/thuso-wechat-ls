-- v2.6: media intelligence -> agent bridge
create table if not exists public.media_agent_turns (
  id uuid primary key default gen_random_uuid(),
  media_id uuid not null references public.media_objects(id) on delete cascade,
  owner_user_id uuid not null references public.users(id) on delete cascade,
  source_task_type text not null check (source_task_type in ('transcription','vision','document','receipt')),
  source_result_id uuid references public.media_intelligence_results(id) on delete set null,
  input_text text not null,
  agent_reply text,
  intent text,
  confidence numeric(5,4),
  trace_id uuid,
  action_id uuid,
  status text not null default 'completed' check (status in ('processing','completed','failed')),
  error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(media_id, source_task_type)
);
create index if not exists media_agent_turns_owner_idx on public.media_agent_turns(owner_user_id, created_at desc);
create index if not exists media_agent_turns_media_idx on public.media_agent_turns(media_id, created_at desc);
alter table public.media_agent_turns enable row level security;
