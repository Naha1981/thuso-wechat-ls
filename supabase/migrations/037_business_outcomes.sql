-- NahaOS commercial outcome attribution
create table if not exists business_outcome_events (
  id uuid primary key default gen_random_uuid(),
  trace_id uuid not null,
  user_id uuid,
  outcome_type text not null,
  status text not null,
  amount numeric(18,2),
  currency text,
  provider text,
  service_domain text,
  metadata jsonb not null default '{}'::jsonb,
  occurred_at timestamptz not null default now()
);

create index if not exists idx_business_outcome_trace on business_outcome_events(trace_id);
create index if not exists idx_business_outcome_provider_time on business_outcome_events(provider, occurred_at desc);
create index if not exists idx_business_outcome_type_time on business_outcome_events(outcome_type, occurred_at desc);

comment on table business_outcome_events is 'Observed or attributed business outcomes linked to NahaOS trace IDs. Estimated values must be explicitly labelled in metadata.';
