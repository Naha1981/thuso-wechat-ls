from __future__ import annotations

import json
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.services.media import MediaError


@dataclass(frozen=True)
class IntelligenceResult:
    task_type: str
    provider: str
    model: str | None
    text_content: str | None
    structured: dict[str, Any]
    confidence: float | None = None
    provider_task_id: str | None = None


RECEIPT_TOTAL = re.compile(r"(?:total|amount due|grand total)\s*[:=]?\s*(?:LSL|ZAR|R)?\s*([0-9][0-9,]*(?:\.\d{1,2})?)", re.I)
RECEIPT_CURRENCY = re.compile(r"\b(LSL|ZAR|USD|EUR|GBP)\b", re.I)
PHONE = re.compile(r"\+?[0-9][0-9 ()-]{7,20}[0-9]")


def normalize_text(value: str | None, limit: int = 12000) -> str | None:
    if value is None:
        return None
    value = value.replace("\x00", " ")
    value = re.sub(r"\s+", " ", value).strip()
    return value[:limit] or None


def extract_receipt_fields(text_content: str) -> dict[str, Any]:
    text_content = text_content or ""
    total = None
    m = RECEIPT_TOTAL.search(text_content)
    if m:
        try:
            total = str(Decimal(m.group(1).replace(",", "")))
        except InvalidOperation:
            total = None
    currency = None
    c = RECEIPT_CURRENCY.search(text_content)
    if c:
        currency = c.group(1).upper()
    phones = sorted(set(PHONE.findall(text_content)))[:5]
    return {"total": total, "currency": currency, "phones": phones}


def build_task_type(media_type: str, mime_type: str | None, requested: str | None = None) -> str:
    if requested:
        if requested not in {"transcription", "vision", "document", "receipt"}:
            raise MediaError("unsupported intelligence task")
        return requested
    if media_type == "audio":
        return "transcription"
    if media_type == "document":
        return "document"
    if media_type in {"image", "video", "sticker"}:
        return "vision"
    raise MediaError("media type is not processable")


class IntelligenceProvider:
    name = "base"

    async def analyze(self, *, media_url: str, mime_type: str | None, task_type: str, prompt: str) -> IntelligenceResult:
        raise NotImplementedError


class KIEIntelligenceProvider(IntelligenceProvider):
    """KIE multimodal adapter.

    KIE exposes an OpenAI-compatible Gemini endpoint and supports image/audio/video/PDF
    URLs through its unified media message structure. The endpoint/model are configurable
    so the platform is not coupled to one model.
    """

    name = "kie"

    def __init__(self) -> None:
        s = get_settings()
        if not s.kie_api_key:
            raise MediaError("KIE_API_KEY is not configured")
        self.base_url = s.kie_base_url.rstrip("/")
        self.model = s.kie_multimodal_model
        self.timeout = s.kie_timeout_seconds
        self.max_output = s.intelligence_max_output_chars
        self.key = s.kie_api_key

    async def analyze(self, *, media_url: str, mime_type: str | None, task_type: str, prompt: str) -> IntelligenceResult:
        system = (
            "You are a production document/media extraction service. "
            "Return concise factual results. Never invent missing values. "
            "For receipt/document tasks, return JSON with keys: text, fields. "
            "For transcription, return JSON with keys: text, language. "
            "For vision, return JSON with keys: text, objects, description."
        )
        user = {
            "task": task_type,
            "instructions": prompt,
            "media_url": media_url,
            "mime_type": mime_type,
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": [
                    {"type": "text", "text": json.dumps(user, ensure_ascii=False)},
                    {"type": "image_url", "image_url": {"url": media_url}},
                ]},
            ],
            "temperature": 0,
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/{self.model}/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"},
                json=payload,
            )
        if response.status_code >= 300:
            raise MediaError(f"intelligence provider failed: {response.status_code}")
        body = response.json()
        choices = body.get("choices") or []
        if not choices:
            raise MediaError("intelligence provider returned no result")
        content = choices[0].get("message", {}).get("content", "")
        if isinstance(content, list):
            content = " ".join(str(x.get("text", "")) for x in content if isinstance(x, dict))
        content = normalize_text(str(content), self.max_output) or ""
        structured: dict[str, Any] = {}
        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                structured = parsed
                text_content = normalize_text(str(parsed.get("text") or parsed.get("description") or ""), self.max_output)
            else:
                text_content = content
        except json.JSONDecodeError:
            text_content = content
        return IntelligenceResult(task_type, self.name, self.model, text_content, structured)


def provider_for_task() -> IntelligenceProvider:
    provider = get_settings().intelligence_provider.lower()
    if provider == "kie":
        return KIEIntelligenceProvider()
    raise MediaError(f"unsupported intelligence provider: {provider}")


async def create_intelligence_job(db: AsyncSession, media_id: UUID, task_type: str | None = None) -> dict:
    row = (await db.execute(text("select id,media_type,detected_mime_type,status from media_objects where id=:id"), {"id": media_id})).mappings().first()
    if not row or row["status"] != "ready":
        raise MediaError("media must be ready before intelligence processing")
    resolved = build_task_type(row["media_type"], row["detected_mime_type"], task_type)
    job_type = {"transcription": "transcribe", "vision": "understand", "document": "extract_document", "receipt": "extract_receipt"}[resolved]
    await db.execute(text("""
      insert into media_processing_jobs(media_id,job_type,status)
      values(:id,:job,'pending')
      on conflict(media_id,job_type) do update set status='pending',available_at=now(),updated_at=now(),last_error=null
    """), {"id": media_id, "job": job_type})
    result = (await db.execute(text("""
      insert into media_intelligence_results(media_id,task_type,status)
      values(:id,:task,'pending')
      on conflict(media_id,task_type) do update set status='pending',updated_at=now(),error=null
      returning id,media_id,task_type,status
    """), {"id": media_id, "task": resolved})).mappings().one()
    return dict(result)


async def claim_intelligence_jobs(db: AsyncSession, limit: int = 10) -> list[dict]:
    rows = (await db.execute(text("""
      with picked as (
        select id from media_processing_jobs
        where status='pending' and available_at<=now()
          and job_type in ('transcribe','understand','extract_document','extract_receipt')
        order by created_at
        for update skip locked limit :limit
      )
      update media_processing_jobs j set status='processing',attempts=attempts+1,updated_at=now()
      from picked where j.id=picked.id
      returning j.*
    """), {"limit": limit})).mappings().all()
    return [dict(r) for r in rows]


async def _media_signed_url(db: AsyncSession, media_id: UUID) -> str:
    s = get_settings()
    row = (await db.execute(text("select storage_key from media_objects where id=:id and status='ready'"), {"id": media_id})).mappings().first()
    if not row or not row["storage_key"]:
        raise MediaError("media object is not stored")
    if s.media_storage_backend.lower() == "local":
        raise MediaError("local media storage cannot be sent to external intelligence providers")
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(
            f"{s.supabase_url.rstrip('/')}/storage/v1/object/sign/{s.media_bucket}/{row['storage_key']}",
            headers={"Authorization": f"Bearer {s.supabase_service_role_key}", "apikey": s.supabase_service_role_key},
            json={"expiresIn": min(600, s.media_signed_url_ttl_seconds)},
        )
    if r.status_code >= 300:
        raise MediaError("failed to create provider media URL")
    signed = r.json().get("signedURL") or r.json().get("signedUrl")
    if not signed:
        raise MediaError("storage did not return a signed URL")
    return signed if signed.startswith("http") else s.supabase_url.rstrip("/") + "/storage/v1" + signed


async def process_intelligence_job(db: AsyncSession, job: dict) -> dict:
    media_id = job["media_id"]
    task_map = {"transcribe": "transcription", "understand": "vision", "extract_document": "document", "extract_receipt": "receipt"}
    task_type = task_map[job["job_type"]]
    result = (await db.execute(text("select * from media_intelligence_results where media_id=:id and task_type=:task for update"), {"id": media_id, "task": task_type})).mappings().first()
    media = (await db.execute(text("select detected_mime_type from media_objects where id=:id"), {"id": media_id})).mappings().first()
    if not result or not media:
        raise MediaError("intelligence result/media missing")
    try:
        provider = provider_for_task()
        url = await _media_signed_url(db, media_id)
        prompts = {
            "transcription": "Transcribe the spoken content verbatim. Identify the language if possible. Do not summarize.",
            "vision": "Describe the visible content, text, people/objects, and any obvious safety-relevant information. Do not infer identity or sensitive traits.",
            "document": "Extract readable text and identify document type, dates, names, reference numbers, totals and other explicit fields. Do not invent values.",
            "receipt": "Extract merchant, date, receipt/reference number, line items, subtotal, tax, total and currency when explicitly visible.",
        }[task_type]
        output = await provider.analyze(media_url=url, mime_type=media["detected_mime_type"], task_type=task_type, prompt=prompts)
        structured = dict(output.structured)
        if task_type == "receipt":
            structured.setdefault("receipt", extract_receipt_fields(output.text_content or ""))
        language = structured.get("language")
        await db.execute(text("""
          update media_intelligence_results
          set status='completed',provider=:provider,model=:model,language=:language,text_content=:text,
              structured=cast(:structured as jsonb),confidence=:confidence,provider_task_id=:task_id,
              error=null,updated_at=now(),completed_at=now()
          where id=:id
        """), {"id": result["id"], "provider": output.provider, "model": output.model, "language": language,
               "text": output.text_content, "structured": json.dumps(structured), "confidence": output.confidence,
               "task_id": output.provider_task_id})
        await db.execute(text("update media_processing_jobs set status='completed',updated_at=now(),last_error=null where id=:id"), {"id": job["id"]})
        await db.execute(text("""
          insert into media_intelligence_events(result_id,media_id,event_type,actor_type,payload)
          values(:rid,:mid,'completed','system',cast(:payload as jsonb))
        """), {"rid": result["id"], "mid": media_id, "payload": json.dumps({"task_type": task_type, "provider": output.provider})})
        return {"result_id": result["id"], "task_type": task_type, "text": output.text_content, "structured": structured}
    except Exception as exc:
        await db.execute(text("update media_intelligence_results set status='failed',error=:error,updated_at=now() where id=:id"), {"id": result["id"], "error": str(exc)[:2000]})
        await db.execute(text("update media_processing_jobs set status=case when attempts>=5 then 'failed' else 'pending' end,last_error=:error,available_at=now()+make_interval(secs=>least(300,power(2,attempts)::int*5)),updated_at=now() where id=:id"), {"id": job["id"], "error": str(exc)[:2000]})
        raise
