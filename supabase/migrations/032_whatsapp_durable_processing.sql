-- v2.13: durable WhatsApp processing, traceability and worker leases.
alter table public.whatsapp_inbox_events
  add column if not exists trace_id uuid;

create index if not exists whatsapp_inbox_trace_idx
  on public.whatsapp_inbox_events(trace_id)
  where trace_id is not null;

create index if not exists whatsapp_inbox_stale_processing_idx
  on public.whatsapp_inbox_events(locked_at)
  where status='processing';

-- A processing lease is deliberately short-lived. Workers may safely reclaim
-- events after a crash; the external-event uniqueness constraint prevents a
-- duplicate WhatsApp event from entering the inbox twice.
