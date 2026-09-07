create table if not exists public.commerce_carts (
 id uuid primary key default gen_random_uuid(),
 user_id uuid not null references public.users(id),
 merchant_id uuid not null references public.providers(id),
 status varchar(20) not null default 'active' check(status in ('active','checked_out','abandoned')),
 currency char(3) not null default 'LSL',
 created_at timestamptz not null default now(),
 updated_at timestamptz not null default now(),
 unique(user_id,merchant_id,status)
);
create index if not exists commerce_carts_user_idx on public.commerce_carts(user_id,status,updated_at desc);

create table if not exists public.commerce_cart_items (
 id uuid primary key default gen_random_uuid(),
 cart_id uuid not null references public.commerce_carts(id) on delete cascade,
 product_id uuid not null references public.pos_products(id),
 quantity numeric(14,3) not null check(quantity>0),
 unit_price numeric(14,2) not null check(unit_price>=0),
 created_at timestamptz not null default now(),
 updated_at timestamptz not null default now(),
 unique(cart_id,product_id)
);
create index if not exists commerce_cart_items_cart_idx on public.commerce_cart_items(cart_id);

create table if not exists public.commerce_orders (
 id uuid primary key default gen_random_uuid(),
 user_id uuid not null references public.users(id),
 merchant_id uuid not null references public.providers(id),
 cart_id uuid references public.commerce_carts(id),
 payment_id uuid unique references public.payments(id),
 status varchar(24) not null default 'pending_payment' check(status in ('pending_payment','paid','preparing','ready','out_for_delivery','completed','cancelled','refunded')),
 currency char(3) not null default 'LSL',
 subtotal numeric(14,2) not null check(subtotal>=0),
 delivery_fee numeric(14,2) not null default 0 check(delivery_fee>=0),
 total numeric(14,2) not null check(total>=0),
 delivery_lat numeric(9,6),
 delivery_lng numeric(9,6),
 metadata jsonb not null default '{}'::jsonb,
 created_at timestamptz not null default now(),
 updated_at timestamptz not null default now()
);
create index if not exists commerce_orders_user_idx on public.commerce_orders(user_id,created_at desc);
create index if not exists commerce_orders_merchant_idx on public.commerce_orders(merchant_id,status,created_at desc);

create table if not exists public.commerce_order_items (
 id uuid primary key default gen_random_uuid(),
 order_id uuid not null references public.commerce_orders(id) on delete cascade,
 product_id uuid not null references public.pos_products(id),
 product_name varchar(160) not null,
 quantity numeric(14,3) not null check(quantity>0),
 unit_price numeric(14,2) not null check(unit_price>=0),
 line_total numeric(14,2) not null check(line_total>=0)
);
create index if not exists commerce_order_items_order_idx on public.commerce_order_items(order_id);

create table if not exists public.commerce_events (
 id uuid primary key default gen_random_uuid(),
 order_id uuid not null references public.commerce_orders(id) on delete cascade,
 event_type varchar(80) not null,
 actor_type varchar(30) not null,
 actor_id uuid,
 payload jsonb not null default '{}'::jsonb,
 created_at timestamptz not null default now()
);
create index if not exists commerce_events_order_idx on public.commerce_events(order_id,created_at desc);

alter table public.commerce_carts enable row level security;
alter table public.commerce_cart_items enable row level security;
alter table public.commerce_orders enable row level security;
alter table public.commerce_order_items enable row level security;
alter table public.commerce_events enable row level security;
