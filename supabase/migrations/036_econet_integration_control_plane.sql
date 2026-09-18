-- v2.19: self-service production integration control plane
create table if not exists public.admin_users (
  id uuid primary key default gen_random_uuid(),
  email varchar(320) not null unique,
  password_hash text not null,
  role varchar(50) not null default 'platform_admin',
  status varchar(20) not null default 'active',
  failed_login_attempts integer not null default 0,
  locked_until timestamptz,
  last_login_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.admin_sessions (
  id uuid primary key default gen_random_uuid(),
  admin_user_id uuid not null references public.admin_users(id) on delete cascade,
  token_hash varchar(128) not null unique,
  csrf_hash varchar(128) not null,
  expires_at timestamptz not null,
  revoked_at timestamptz,
  last_seen_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  ip_address inet,
  user_agent text
);
create index if not exists admin_sessions_user_active_idx
  on public.admin_sessions(admin_user_id, expires_at)
  where revoked_at is null;

create table if not exists public.integration_configs (
  id uuid primary key default gen_random_uuid(),
  provider varchar(80) not null,
  environment varchar(30) not null default 'production',
  enabled boolean not null default false,
  base_url text not null,
  chat_endpoint_path varchar(500) not null default '/chat/completions',
  health_endpoint_path varchar(500),
  auth_scheme varchar(30) not null default 'bearer',
  auth_header_name varchar(120) not null default 'Authorization',
  model varchar(160) not null default 'default',
  timeout_seconds integer not null default 60,
  request_template jsonb not null default '{}'::jsonb,
  response_mapping jsonb not null default '{}'::jsonb,
  secret_ciphertext text,
  last_test_at timestamptz,
  last_test_status varchar(30),
  last_test_error text,
  version integer not null default 1,
  allow_private_network boolean not null default false,
  created_by uuid references public.admin_users(id),
  updated_by uuid references public.admin_users(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(provider, environment)
);

create table if not exists public.admin_audit_events (
  id uuid primary key default gen_random_uuid(),
  admin_user_id uuid references public.admin_users(id) on delete set null,
  action varchar(120) not null,
  target_type varchar(80) not null,
  target_id uuid,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create index if not exists admin_audit_events_created_idx
  on public.admin_audit_events(created_at desc);
create index if not exists admin_audit_events_admin_idx
  on public.admin_audit_events(admin_user_id, created_at desc);

alter table public.admin_users enable row level security;
alter table public.admin_sessions enable row level security;
alter table public.integration_configs enable row level security;
alter table public.admin_audit_events enable row level security;

comment on table public.integration_configs is
  'Encrypted, self-service provider integration configuration. Secret values are never stored in plaintext.';
