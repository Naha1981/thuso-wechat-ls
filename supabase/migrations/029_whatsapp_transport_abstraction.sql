-- v2.10 transport abstraction: Baileys now, Meta Cloud later.
alter table public.wa_accounts
  add column if not exists transport varchar(32) not null default 'baileys';

alter table public.wa_accounts
  add column if not exists transport_account_ref varchar(200);

create index if not exists wa_accounts_transport_idx
  on public.wa_accounts(transport, status);

create table if not exists public.whatsapp_transport_events (
  id uuid primary key default gen_random_uuid(),
  wa_account_id uuid references public.wa_accounts(id) on delete set null,
  transport varchar(32) not null,
  event_type varchar(80) not null,
  external_event_id varchar(200),
  status varchar(24) not null default 'received',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create index if not exists whatsapp_transport_events_account_idx
  on public.whatsapp_transport_events(wa_account_id, created_at desc);
create unique index if not exists whatsapp_transport_events_dedup_idx
  on public.whatsapp_transport_events(transport, external_event_id)
  where external_event_id is not null;

-- Existing accounts are explicitly Baileys; future Meta accounts must opt in.
update public.wa_accounts set transport='baileys' where transport is null;
