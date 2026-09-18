alter table agent_actions add column if not exists trace_id uuid;
create index if not exists idx_agent_actions_trace_id on agent_actions(trace_id);
