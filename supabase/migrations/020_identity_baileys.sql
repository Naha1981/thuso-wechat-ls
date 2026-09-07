-- v2.0 Identity + Baileys operator persistence
create table if not exists public.channel_identities (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  channel varchar(30) not null,
  external_subject varchar(200) not null,
  phone_e164 varchar(20),
  status varchar(20) not null default 'active',
  verified_at timestamptz,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(channel, external_subject)
);
create index if not exists channel_identities_user_idx on public.channel_identities(user_id);
create index if not exists channel_identities_phone_idx on public.channel_identities(phone_e164);

create table if not exists public.auth_sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  channel_identity_id uuid references public.channel_identities(id) on delete set null,
  token_hash varchar(128) not null unique,
  expires_at timestamptz not null,
  revoked_at timestamptz,
  last_seen_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  metadata jsonb not null default '{}'::jsonb
);
create index if not exists auth_sessions_user_active_idx on public.auth_sessions(user_id, expires_at) where revoked_at is null;

create table if not exists public.user_roles (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  role varchar(40) not null,
  scope_type varchar(40),
  scope_id uuid,
  created_at timestamptz not null default now(),
  unique(user_id, role, scope_type, scope_id)
);
create index if not exists user_roles_user_idx on public.user_roles(user_id);

create table if not exists public.otp_challenges (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  channel_identity_id uuid references public.channel_identities(id) on delete cascade,
  purpose varchar(40) not null,
  code_hash varchar(128) not null,
  attempts integer not null default 0,
  max_attempts integer not null default 5,
  expires_at timestamptz not null,
  consumed_at timestamptz,
  created_at timestamptz not null default now()
);
create index if not exists otp_challenges_active_idx on public.otp_challenges(user_id, purpose, expires_at) where consumed_at is null;

create table if not exists public.identity_events (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references public.users(id) on delete set null,
  channel_identity_id uuid references public.channel_identities(id) on delete set null,
  event_type varchar(80) not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create index if not exists identity_events_user_created_idx on public.identity_events(user_id, created_at desc);

create table if not exists public.wa_accounts (
  id uuid primary key default gen_random_uuid(),
  account_key varchar(120) not null unique,
  phone_e164 varchar(20),
  status varchar(30) not null default 'stopped',
  connection_state varchar(30) not null default 'close',
  qr_code text,
  qr_created_at timestamptz,
  last_connected_at timestamptz,
  last_disconnect_at timestamptz,
  last_disconnect_code integer,
  last_disconnect_message text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists wa_accounts_status_idx on public.wa_accounts(status, connection_state);

create table if not exists public.wa_auth_keys (
  account_id uuid not null references public.wa_accounts(id) on delete cascade,
  key_type varchar(80) not null,
  key_id varchar(240) not null,
  value jsonb not null,
  updated_at timestamptz not null default now(),
  primary key(account_id, key_type, key_id)
);

create table if not exists public.wa_auth_creds (
  account_id uuid primary key references public.wa_accounts(id) on delete cascade,
  value jsonb not null,
  updated_at timestamptz not null default now()
);

create index if not exists wa_auth_keys_updated_idx on public.wa_auth_keys(account_id, updated_at desc);
