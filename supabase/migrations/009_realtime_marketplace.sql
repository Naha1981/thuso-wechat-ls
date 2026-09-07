-- v0.9: real-time marketplace event pipeline
alter table public.outbox_events add column if not exists status varchar(20) not null default 'pending';
alter table public.outbox_events add column if not exists attempts integer not null default 0;
alter table public.outbox_events add column if not exists available_at timestamptz not null default now();
alter table public.outbox_events add column if not exists locked_at timestamptz;
alter table public.outbox_events add column if not exists processed_at timestamptz;
alter table public.outbox_events add column if not exists last_error text;
create index if not exists outbox_events_pending_idx on public.outbox_events(status,available_at,created_at) where status='pending';
create index if not exists outbox_events_aggregate_idx on public.outbox_events(aggregate_type,aggregate_id,created_at desc);

create table if not exists public.dispatch_locks (
  service_request_id uuid primary key references public.service_requests(id) on delete cascade,
  lease_until timestamptz not null,
  owner varchar(120) not null,
  updated_at timestamptz not null default now()
);

create table if not exists public.marketplace_event_log (
  id uuid primary key default gen_random_uuid(),
  event_id uuid not null references public.outbox_events(id) on delete cascade,
  event_type varchar(120) not null,
  aggregate_type varchar(60) not null,
  aggregate_id uuid not null,
  stream_id varchar(200),
  delivered_at timestamptz not null default now(),
  unique(event_id)
);
create index if not exists marketplace_event_log_aggregate_idx on public.marketplace_event_log(aggregate_type,aggregate_id,delivered_at desc);

alter table public.dispatch_locks enable row level security;
alter table public.marketplace_event_log enable row level security;
