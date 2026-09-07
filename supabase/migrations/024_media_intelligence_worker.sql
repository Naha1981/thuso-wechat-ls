-- v2.5: durable Redis-stream media intelligence worker + agent context projection

create table if not exists public.media_intelligence_context (
  id uuid primary key default gen_random_uuid(),
  media_id uuid not null references public.media_objects(id) on delete cascade,
  owner_user_id uuid references public.users(id) on delete cascade,
  task_type text not null check (task_type in ('transcription','vision','document','receipt')),
  text_content text,
  structured jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(media_id, task_type)
);
create index if not exists media_intelligence_context_owner_idx
  on public.media_intelligence_context(owner_user_id, updated_at desc);
create index if not exists media_intelligence_context_media_idx
  on public.media_intelligence_context(media_id, updated_at desc);

alter table public.media_intelligence_context enable row level security;

-- Automatic WhatsApp responses are deliberately opt-in. Consequential actions remain
-- behind the existing agent confirmation/risk controls.
