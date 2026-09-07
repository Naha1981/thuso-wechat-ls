-- v1.9: delivery & logistics engine
alter table public.service_requests
  add column if not exists delivery_job_id uuid;

create table if not exists public.delivery_jobs (
 id uuid primary key default gen_random_uuid(),
 service_request_id uuid unique not null references public.service_requests(id) on delete cascade,
 order_id uuid unique references public.commerce_orders(id) on delete set null,
 pickup_provider_id uuid references public.providers(id),
 courier_provider_id uuid references public.providers(id),
 status varchar(32) not null default 'searching' check(status in ('searching','assigned','at_pickup','picked_up','in_transit','delivered','failed','cancelled')),
 pickup_lat numeric(9,6) not null,
 pickup_lng numeric(9,6) not null,
 dropoff_lat numeric(9,6) not null,
 dropoff_lng numeric(9,6) not null,
 distance_m integer,
 eta_seconds integer,
 delivery_fee numeric(14,2) not null default 0 check(delivery_fee>=0),
 proof_type varchar(24),
 proof_value text,
 failure_reason text,
 assigned_at timestamptz,
 picked_up_at timestamptz,
 delivered_at timestamptz,
 failed_at timestamptz,
 cancelled_at timestamptz,
 created_at timestamptz not null default now(),
 updated_at timestamptz not null default now()
);
create index if not exists delivery_jobs_status_idx on public.delivery_jobs(status,created_at desc);
create index if not exists delivery_jobs_courier_idx on public.delivery_jobs(courier_provider_id,status,created_at desc);

create table if not exists public.delivery_events (
 id uuid primary key default gen_random_uuid(),
 delivery_job_id uuid not null references public.delivery_jobs(id) on delete cascade,
 event_type varchar(64) not null,
 actor_type varchar(32) not null,
 actor_id uuid,
 payload jsonb not null default '{}'::jsonb,
 created_at timestamptz not null default now()
);
create index if not exists delivery_events_job_idx on public.delivery_events(delivery_job_id,created_at desc);

create table if not exists public.delivery_tracking_points (
 id bigserial primary key,
 delivery_job_id uuid not null references public.delivery_jobs(id) on delete cascade,
 courier_provider_id uuid not null references public.providers(id),
 location geography(point,4326) not null,
 heading numeric(6,2),
 speed_kmh numeric(8,2),
 recorded_at timestamptz not null default now()
);
create index if not exists delivery_tracking_points_job_idx on public.delivery_tracking_points(delivery_job_id,recorded_at desc);
create index if not exists delivery_tracking_points_location_gix on public.delivery_tracking_points using gist(location);

create table if not exists public.delivery_proofs (
 id uuid primary key default gen_random_uuid(),
 delivery_job_id uuid unique not null references public.delivery_jobs(id) on delete cascade,
 proof_type varchar(24) not null check(proof_type in ('otp','photo','signature','recipient_confirmation')),
 proof_hash varchar(128),
 metadata jsonb not null default '{}'::jsonb,
 created_at timestamptz not null default now()
);

alter table public.delivery_jobs enable row level security;
alter table public.delivery_events enable row level security;
alter table public.delivery_tracking_points enable row level security;
alter table public.delivery_proofs enable row level security;
