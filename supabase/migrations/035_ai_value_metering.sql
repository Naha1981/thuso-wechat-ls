create table if not exists ai_usage_events (
  id uuid primary key default gen_random_uuid(),
  trace_id uuid not null,
  user_id uuid,
  provider text not null,
  model text,
  channel text,
  event_type text not null,
  input_units integer,
  output_units integer,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_ai_usage_events_created_at on ai_usage_events(created_at);
create index if not exists idx_ai_usage_events_provider on ai_usage_events(provider);
create index if not exists idx_ai_usage_events_user on ai_usage_events(user_id);

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

create index if not exists idx_business_outcomes_occurred_at on business_outcome_events(occurred_at);
create index if not exists idx_business_outcomes_type on business_outcome_events(outcome_type);
create index if not exists idx_business_outcomes_trace on business_outcome_events(trace_id);

comment on table ai_usage_events is 'Operational AI usage events for provider cost, usage and product analytics.';
comment on table business_outcome_events is 'Observed outcomes used to prove attributable commercial value. Never treat estimated value as booked revenue.';
