-- v2.12: WhatsApp operations and observability indexes.
create index if not exists whatsapp_inbox_failures_idx
  on public.whatsapp_inbox_events(created_at desc)
  where status in ('failed','dead_letter');

create index if not exists whatsapp_inbox_processing_idx
  on public.whatsapp_inbox_events(locked_at)
  where status='processing';

create index if not exists whatsapp_health_state_idx
  on public.whatsapp_account_health(state,updated_at desc);

create index if not exists whatsapp_outbox_failed_idx
  on public.outbox_messages(created_at desc)
  where channel='whatsapp' and status='failed';

create index if not exists whatsapp_receipt_status_idx
  on public.whatsapp_delivery_receipts(status,occurred_at desc);
