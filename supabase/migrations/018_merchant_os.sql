create extension if not exists pgcrypto;

alter table public.commerce_orders
  add column if not exists rejection_reason text,
  add column if not exists accepted_at timestamptz,
  add column if not exists preparing_at timestamptz,
  add column if not exists ready_at timestamptz,
  add column if not exists completed_at timestamptz,
  add column if not exists delivery_request_id uuid references public.service_requests(id);

create index if not exists commerce_orders_delivery_request_idx
  on public.commerce_orders(delivery_request_id)
  where delivery_request_id is not null;

create table if not exists public.merchant_action_dedup (
  id uuid primary key default gen_random_uuid(),
  merchant_id uuid not null references public.providers(id) on delete cascade,
  external_action_id varchar(200) not null,
  action_type varchar(60) not null,
  created_at timestamptz not null default now(),
  unique(merchant_id, external_action_id)
);

create table if not exists public.merchant_events (
  id uuid primary key default gen_random_uuid(),
  merchant_id uuid not null references public.providers(id) on delete cascade,
  order_id uuid references public.commerce_orders(id) on delete cascade,
  event_type varchar(80) not null,
  actor_type varchar(30) not null,
  actor_id uuid,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create index if not exists merchant_events_order_idx
  on public.merchant_events(order_id, created_at desc);
create index if not exists merchant_events_merchant_idx
  on public.merchant_events(merchant_id, created_at desc);

alter table public.merchant_action_dedup enable row level security;
alter table public.merchant_events enable row level security;
