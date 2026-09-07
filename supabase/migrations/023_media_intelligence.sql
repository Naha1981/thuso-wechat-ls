-- v2.4: Media intelligence, OCR/document extraction and voice transcription

alter table public.media_processing_jobs
  drop constraint if exists media_processing_jobs_job_type_check;
alter table public.media_processing_jobs
  add constraint media_processing_jobs_job_type_check
  check (job_type in ('ingest','scan','transcribe','understand','extract_document','extract_receipt'));

create table if not exists public.media_intelligence_results (
  id uuid primary key default gen_random_uuid(),
  media_id uuid not null references public.media_objects(id) on delete cascade,
  task_type text not null check (task_type in ('transcription','vision','document','receipt')),
  status text not null default 'pending' check (status in ('pending','processing','completed','failed')),
  provider text,
  model text,
  language text,
  text_content text,
  structured jsonb not null default '{}'::jsonb,
  confidence numeric(5,4),
  provider_task_id text,
  error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  completed_at timestamptz,
  unique(media_id, task_type)
);
create index if not exists media_intelligence_media_idx on public.media_intelligence_results(media_id, created_at desc);
create index if not exists media_intelligence_status_idx on public.media_intelligence_results(status, created_at);

create table if not exists public.media_intelligence_events (
  id uuid primary key default gen_random_uuid(),
  result_id uuid references public.media_intelligence_results(id) on delete cascade,
  media_id uuid not null references public.media_objects(id) on delete cascade,
  event_type text not null,
  actor_type text not null,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create index if not exists media_intelligence_events_media_idx on public.media_intelligence_events(media_id, created_at desc);

alter table public.media_intelligence_results enable row level security;
alter table public.media_intelligence_events enable row level security;

-- Keep intelligence provider credentials server-side only.
