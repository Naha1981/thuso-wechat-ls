-- NahaOS generic stakeholder integration hub + self-onboarding
create table if not exists public.partner_invites (
  id uuid primary key default gen_random_uuid(),
  token_hash varchar(128) not null unique,
  stakeholder_name varchar(200) not null,
  stakeholder_type varchar(80) not null,
  service_domain varchar(100) not null,
  expires_at timestamptz not null,
  consumed_at timestamptz,
  integration_id uuid,
  created_by uuid references public.admin_users(id),
  created_at timestamptz not null default now()
);
create index if not exists partner_invites_expiry_idx on public.partner_invites(expires_at);

create table if not exists public.partner_integrations (
  id uuid primary key default gen_random_uuid(),
  partner_invite_id uuid references public.partner_invites(id) on delete set null,
  stakeholder_name varchar(200) not null,
  stakeholder_type varchar(80) not null,
  service_domain varchar(100) not null,
  provider_key varchar(120) not null unique,
  environment varchar(30) not null default 'production',
  enabled boolean not null default false,
  base_url text not null,
  api_spec_url text,
  health_endpoint_path varchar(500),
  auth_scheme varchar(30) not null default 'bearer',
  auth_header_name varchar(120) not null default 'Authorization',
  timeout_seconds integer not null default 30,
  request_defaults jsonb not null default '{}'::jsonb,
  operation_configs jsonb not null default '{}'::jsonb,
  response_mappings jsonb not null default '{}'::jsonb,
  secret_ciphertext text,
  last_test_at timestamptz,
  last_test_status varchar(30),
  last_test_operation varchar(120),
  last_test_error text,
  version integer not null default 1,
  allow_private_network boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists partner_integrations_domain_idx on public.partner_integrations(service_domain);
create index if not exists partner_integrations_enabled_idx on public.partner_integrations(enabled) where enabled=true;

alter table public.partner_invites enable row level security;
alter table public.partner_integrations enable row level security;

comment on table public.partner_integrations is
  'Generic stakeholder service API contracts. Production secrets are encrypted; external schemas are mapped through configuration.';
