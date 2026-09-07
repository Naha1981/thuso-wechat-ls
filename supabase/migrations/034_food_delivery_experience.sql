-- v2.15: customer Food + Delivery experience primitives
create table if not exists public.customer_addresses (
 id uuid primary key default gen_random_uuid(),
 user_id uuid not null references public.users(id) on delete cascade,
 label varchar(120) not null default 'Saved location',
 latitude numeric(9,6) not null check(latitude between -90 and 90),
 longitude numeric(9,6) not null check(longitude between -180 and 180),
 is_default boolean not null default false,
 created_at timestamptz not null default now(),
 updated_at timestamptz not null default now()
);
create unique index if not exists customer_addresses_one_default_idx
 on public.customer_addresses(user_id) where is_default=true;
create index if not exists customer_addresses_user_idx on public.customer_addresses(user_id,updated_at desc);
alter table public.customer_addresses enable row level security;

create index if not exists commerce_events_order_created_idx on public.commerce_events(order_id,created_at asc);
create index if not exists delivery_events_job_created_idx on public.delivery_events(delivery_job_id,created_at asc);
