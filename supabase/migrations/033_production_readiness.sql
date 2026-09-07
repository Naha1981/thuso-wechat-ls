-- v2.14: production readiness, account routing and end-to-end traceability.
alter table public.channel_identities
  add column if not exists wa_account_id uuid references public.wa_accounts(id) on delete set null;
create index if not exists channel_identities_wa_account_idx
  on public.channel_identities(wa_account_id,phone_e164)
  where channel='whatsapp' and wa_account_id is not null;

alter table public.outbox_messages
  add column if not exists trace_id uuid;
create index if not exists outbox_messages_trace_idx
  on public.outbox_messages(trace_id) where trace_id is not null;

alter table public.whatsapp_inbox_events
  alter column trace_id set default gen_random_uuid();

-- Prevent a single phone identity from being silently rebound to multiple platform accounts.
create unique index if not exists whatsapp_identity_phone_account_unique
  on public.channel_identities(phone_e164,wa_account_id)
  where channel='whatsapp' and phone_e164 is not null and wa_account_id is not null;
