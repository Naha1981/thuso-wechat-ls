from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.services.partner_integrations import load_active_partner_by_provider_key
from app.services.partner_webhooks import (
    parse_webhook_payload,
    record_webhook_event,
    verify_webhook,
    webhook_operation,
)

router = APIRouter(prefix="/partner/webhooks", tags=["partner-webhooks"])


@router.post("/{provider_key}/{operation}")
async def receive_webhook(
    provider_key: str,
    operation: str,
    request: Request,
    db: AsyncSession = __import__("fastapi").Depends(get_db),
):
    config = await load_active_partner_by_provider_key(db, provider_key=provider_key)
    if not config:
        raise HTTPException(404, "Active partner integration not found")

    body = await request.body()
    headers = {key.lower(): value for key, value in request.headers.items()}
    trace_id = uuid4()

    try:
        verify_webhook(config, headers=headers, body=body)
    except PermissionError as exc:
        await record_webhook_event(
            db,
            provider_key=config.provider_key,
            service_domain=config.service_domain,
            operation=operation,
            trace_id=str(trace_id),
            event_id=headers.get("x-event-id"),
            verification_status="rejected",
            payload={"error": str(exc)},
        )
        await db.commit()
        raise HTTPException(401, "Webhook verification failed") from exc

    try:
        payload = parse_webhook_payload(config, body, request.headers.get("content-type", ""))
        resolved_operation = webhook_operation(config, payload, operation)
        await record_webhook_event(
            db,
            provider_key=config.provider_key,
            service_domain=config.service_domain,
            operation=resolved_operation,
            trace_id=str(trace_id),
            event_id=headers.get("x-event-id"),
            verification_status="verified",
            payload=payload,
        )
        await db.commit()
        return {
            "accepted": True,
            "provider": config.provider_key,
            "service_domain": config.service_domain,
            "operation": resolved_operation,
            "trace_id": str(trace_id),
        }
    except (ValueError, RuntimeError) as exc:
        await db.rollback()
        raise HTTPException(422, "Webhook payload could not be processed") from exc
