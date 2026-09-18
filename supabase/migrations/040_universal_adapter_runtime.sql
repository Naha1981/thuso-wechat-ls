-- NahaOS universal adapter runtime extensions
alter table public.partner_integrations
  add column if not exists adapter_type varchar(40) not null default 'rest_json';
alter table public.partner_integrations
  add column if not exists auth_config jsonb not null default '{}'::jsonb;
alter table public.partner_integrations
  add column if not exists webhook_config jsonb not null default '{}'::jsonb;
alter table public.partner_integrations
  add column if not exists workflow_configs jsonb not null default '{}'::jsonb;

create index if not exists partner_integrations_adapter_idx
  on public.partner_integrations(adapter_type);

create table if not exists public.partner_webhook_events (
  id uuid primary key default gen_random_uuid(),
  provider_key varchar(120) not null,
  service_domain varchar(100) not null,
  operation varchar(120) not null,
  trace_id uuid not null,
  event_id varchar(200),
  verification_status varchar(30) not null,
  payload jsonb not null default '{}'::jsonb,
  received_at timestamptz not null default now()
);
create index if not exists partner_webhook_events_provider_idx
  on public.partner_webhook_events(provider_key, received_at desc);
create index if not exists partner_webhook_events_trace_idx
  on public.partner_webhook_events(trace_id);

alter table public.partner_webhook_events enable row level security;

comment on column public.partner_integrations.adapter_type is
  'Built-in protocol adapter: rest_json, graphql, form_urlencoded, soap_xml.';
comment on column public.partner_integrations.auth_config is
  'Non-secret authentication/signing configuration. Secret values stay in secret_ciphertext.';
comment on column public.partner_integrations.webhook_config is
  'Inbound webhook verification/parsing configuration.';
comment on column public.partner_integrations.workflow_configs is
  'Optional multi-step operation workflows using configured operations.';
