-- v2.2: first-class courier/customer WhatsApp delivery operations
-- Proof is mandatory before delivered.
alter table public.delivery_jobs
  add column if not exists proof_required boolean not null default true;

create index if not exists delivery_jobs_courier_active_idx
  on public.delivery_jobs(courier_provider_id, status, updated_at desc);

create index if not exists delivery_events_type_idx
  on public.delivery_events(delivery_job_id, event_type, created_at desc);
