create extension if not exists pgcrypto;
create table if not exists kyc_profiles (
 id uuid primary key default gen_random_uuid(), subject_id uuid not null, subject_type text not null,
 level text not null default 'basic', status text not null default 'unverified', reviewer_ref text,
 rejection_reason text, verified_at timestamptz, created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
 unique(subject_id,subject_type), check(subject_type in ('customer','provider','business')),
 check(status in ('unverified','pending','verified','rejected','expired'))
);
create table if not exists risk_assessments (
 id uuid primary key default gen_random_uuid(), subject_id uuid, transaction_type text not null,
 amount numeric(20,2) not null, currency char(3) not null, score int not null, decision text not null,
 reasons jsonb not null default '[]'::jsonb, created_at timestamptz not null default now(),
 check(decision in ('allow','review','block'))
);
create index if not exists idx_risk_subject_created on risk_assessments(subject_id,created_at desc);
create table if not exists risk_limits (
 id uuid primary key default gen_random_uuid(), scope text not null, currency char(3) not null default 'LSL',
 max_txn_amount numeric(20,2), max_daily_amount numeric(20,2), max_daily_count int, active boolean not null default true,
 unique(scope,currency)
);
create table if not exists fraud_cases (
 id uuid primary key default gen_random_uuid(), subject_id uuid, transaction_id uuid, risk_assessment_id uuid references risk_assessments(id),
 status text not null default 'open', severity text not null default 'medium', reason text not null, resolution text,
 created_at timestamptz not null default now(), resolved_at timestamptz,
 check(status in ('open','investigating','resolved','dismissed')), check(severity in ('low','medium','high','critical'))
);
create index if not exists idx_fraud_open on fraud_cases(status,severity);
