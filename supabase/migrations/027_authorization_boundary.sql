-- v2.8 Production identity + authorization boundary
-- Roles are scoped capabilities; ownership remains the default authority.
create index if not exists user_roles_scope_idx on public.user_roles(role, scope_type, scope_id, user_id);
create index if not exists service_requests_user_status_idx on public.service_requests(user_id, status, created_at desc);
create index if not exists delivery_jobs_courier_status_idx on public.delivery_jobs(courier_provider_id, status, created_at desc);

-- Prevent accidental duplicate active sessions from becoming an authorization primitive.
create index if not exists auth_sessions_token_hash_idx on public.auth_sessions(token_hash) where revoked_at is null;
