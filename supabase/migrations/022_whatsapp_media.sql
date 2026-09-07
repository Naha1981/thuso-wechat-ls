-- v2.3: WhatsApp media/content infrastructure

create table if not exists public.media_objects (
  id uuid primary key default gen_random_uuid(),
  channel text not null default 'whatsapp',
  account_key text,
  external_media_id text,
  external_message_id text,
  owner_user_id uuid references public.users(id) on delete set null,
  media_type text not null check (media_type in ('image','video','audio','document','sticker')),
  mime_type text,
  detected_mime_type text,
  original_filename text,
  size_bytes bigint,
  sha256 text,
  storage_key text,
  status text not null default 'pending' check (status in ('pending','ready','quarantined','rejected','deleted')),
  scan_status text not null default 'pending' check (scan_status in ('pending','clean','infected','unavailable')),
  encryption jsonb not null default '{}'::jsonb,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  expires_at timestamptz
);

create unique index if not exists media_objects_external_unique_idx
  on public.media_objects(channel, account_key, external_message_id)
  where external_message_id is not null;

create index if not exists media_objects_hash_idx
  on public.media_objects(channel, sha256)
  where sha256 is not null;

create index if not exists media_objects_owner_idx
  on public.media_objects(owner_user_id, created_at desc);
create index if not exists media_objects_status_idx
  on public.media_objects(status, created_at);
create index if not exists media_objects_message_idx
  on public.media_objects(account_key, external_message_id);

create table if not exists public.media_access_grants (
  id uuid primary key default gen_random_uuid(),
  media_id uuid not null references public.media_objects(id) on delete cascade,
  audience_user_id uuid references public.users(id) on delete cascade,
  scope text not null default 'read',
  token_hash text not null,
  expires_at timestamptz not null,
  created_at timestamptz not null default now(),
  revoked_at timestamptz
);
create index if not exists media_access_grants_lookup_idx
  on public.media_access_grants(media_id, token_hash)
  where revoked_at is null;

create table if not exists public.media_events (
  id uuid primary key default gen_random_uuid(),
  media_id uuid not null references public.media_objects(id) on delete cascade,
  event_type text not null,
  actor_type text not null,
  actor_id uuid,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create index if not exists media_events_media_idx
  on public.media_events(media_id, created_at desc);

create table if not exists public.voice_transcriptions (
  id uuid primary key default gen_random_uuid(),
  media_id uuid not null unique references public.media_objects(id) on delete cascade,
  status text not null default 'pending' check (status in ('pending','processing','completed','failed')),
  language text,
  text text,
  provider text,
  model text,
  error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  completed_at timestamptz
);

create table if not exists public.media_processing_jobs (
  id uuid primary key default gen_random_uuid(),
  media_id uuid not null references public.media_objects(id) on delete cascade,
  job_type text not null check (job_type in ('ingest','scan','transcribe')),
  status text not null default 'pending' check (status in ('pending','processing','completed','failed')),
  attempts integer not null default 0,
  available_at timestamptz not null default now(),
  last_error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(media_id, job_type)
);
create index if not exists media_processing_jobs_claim_idx
  on public.media_processing_jobs(status, available_at, created_at);

create table if not exists public.wa_media_message_cache (
  id uuid primary key default gen_random_uuid(),
  account_key text not null,
  external_message_id text not null,
  remote_jid text,
  message jsonb not null,
  created_at timestamptz not null default now(),
  expires_at timestamptz not null default (now() + interval '7 days'),
  unique(account_key, external_message_id)
);
create index if not exists wa_media_message_cache_expiry_idx
  on public.wa_media_message_cache(expires_at);

alter table public.media_objects enable row level security;
alter table public.media_access_grants enable row level security;
alter table public.media_events enable row level security;
alter table public.voice_transcriptions enable row level security;
alter table public.media_processing_jobs enable row level security;
alter table public.wa_media_message_cache enable row level security;

-- Backend services use the Supabase service role / direct Postgres connection.
-- No client-facing policies are granted by this migration.
