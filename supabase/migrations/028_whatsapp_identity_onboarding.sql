-- v2.9 WhatsApp identity + account ownership/onboarding
alter table public.wa_accounts
  add column if not exists owner_user_id uuid references public.users(id) on delete set null;
alter table public.wa_accounts
  add column if not exists label varchar(120);
alter table public.wa_accounts
  add column if not exists purpose varchar(30) not null default 'platform';
alter table public.wa_accounts
  add column if not exists paired_at timestamptz;
alter table public.wa_accounts
  add column if not exists revoked_at timestamptz;

create index if not exists wa_accounts_owner_idx on public.wa_accounts(owner_user_id, status);
create unique index if not exists wa_accounts_owner_purpose_label_idx
  on public.wa_accounts(owner_user_id, purpose, label)
  where owner_user_id is not null and revoked_at is null and label is not null;

create table if not exists public.whatsapp_onboarding_sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  wa_account_id uuid not null references public.wa_accounts(id) on delete cascade,
  status varchar(24) not null default 'created',
  started_at timestamptz not null default now(),
  expires_at timestamptz not null,
  completed_at timestamptz,
  cancelled_at timestamptz,
  metadata jsonb not null default '{}'::jsonb
);
create index if not exists wa_onboarding_user_idx on public.whatsapp_onboarding_sessions(user_id, started_at desc);
create index if not exists wa_onboarding_active_idx
  on public.whatsapp_onboarding_sessions(user_id, expires_at)
  where completed_at is null and cancelled_at is null;

create table if not exists public.whatsapp_identity_events (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references public.users(id) on delete set null,
  channel_identity_id uuid references public.channel_identities(id) on delete set null,
  wa_account_id uuid references public.wa_accounts(id) on delete set null,
  event_type varchar(80) not null,
  external_message_id varchar(200),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create index if not exists whatsapp_identity_events_user_idx
  on public.whatsapp_identity_events(user_id, created_at desc);

-- Backfill paired_at where the operator already has a successful connection.
update public.wa_accounts set paired_at = coalesce(paired_at, last_connected_at)
where status = 'connected' and last_connected_at is not null;
