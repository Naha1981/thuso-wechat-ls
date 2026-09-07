# Naha SuperApp v2.7 — Conversation Memory & Context Engine

v2.7 adds durable, bounded conversation context while keeping authorization, financial state, credentials, and sensitive domain records outside model memory.

## Flow

WhatsApp → conversation_messages → context engine → agent/router → action/risk/confirmation

## Added
- conversation_summaries: bounded deterministic rolling summary
- conversation_memory: scoped preference/fact/task_context records with expiry
- conversation_context_events: auditable context events
- recent_context() for bounded retrieval
- upsert_memory() for explicit domain-controlled memory
- agent turns now record context and refresh summaries

Memory is channel-scoped and user-scoped. Expiring task context is preferred over permanent memory. Consequential actions still use the existing action/confirmation/risk subsystem.

## Migration
`026_conversation_memory.sql`

## Verification
Run `pytest -q` and `python -m compileall app`.
