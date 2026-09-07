create table if not exists public.pos_products (
 id uuid primary key default gen_random_uuid(),
 merchant_id uuid not null references public.providers(id),
 name varchar(160) not null,
 sku varchar(80) not null,
 price numeric(14,2) not null check(price>=0),
 stock_quantity numeric(14,3) not null default 0 check(stock_quantity>=0),
 created_at timestamptz not null default now(),
 unique(merchant_id,sku)
);
create index if not exists pos_products_merchant_idx on public.pos_products(merchant_id);
create table if not exists public.pos_orders (
 id uuid primary key default gen_random_uuid(),
 merchant_id uuid not null references public.providers(id),
 status varchar(20) not null default 'pending',
 total numeric(14,2) not null check(total>=0),
 created_at timestamptz not null default now()
);
create index if not exists pos_orders_merchant_created_idx on public.pos_orders(merchant_id,created_at desc);
create table if not exists public.pos_order_items (
 id uuid primary key default gen_random_uuid(),
 order_id uuid not null references public.pos_orders(id) on delete cascade,
 product_id uuid not null references public.pos_products(id),
 quantity numeric(14,3) not null check(quantity>0),
 unit_price numeric(14,2) not null check(unit_price>=0),
 line_total numeric(14,2) not null check(line_total>=0)
);
create index if not exists pos_order_items_order_idx on public.pos_order_items(order_id);
alter table public.pos_products enable row level security;
alter table public.pos_orders enable row level security;
alter table public.pos_order_items enable row level security;
