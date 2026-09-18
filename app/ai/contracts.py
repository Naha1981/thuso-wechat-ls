from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class AIMessage:
    role: str
    content: str


@dataclass(frozen=True)
class AIRequest:
    messages: list[AIMessage]
    user_id: str | None = None
    session_id: str | None = None
    trace_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AIResponse:
    provider: str
    model: str
    content: str
    usage: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)


class AIProvider(Protocol):
    name: str

    async def chat(self, request: AIRequest) -> AIResponse:
        ...

    async def health(self) -> dict[str, Any]:
        ...

    def capabilities(self) -> dict[str, Any]:
        ...
