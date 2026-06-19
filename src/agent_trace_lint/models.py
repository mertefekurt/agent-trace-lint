"""Domain models used by the trace linter."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True, slots=True)
class ToolCall:
    id: str
    name: str
    arguments: str


@dataclass(frozen=True, slots=True)
class Message:
    role: str
    content: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()
    tool_call_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Trace:
    trace_id: str
    messages: tuple[Message, ...]


@dataclass(frozen=True, slots=True)
class Finding:
    rule_id: str
    severity: Severity
    message: str
    trace_id: str
    message_index: int
    tool_call_id: str | None = None


@dataclass(frozen=True, slots=True)
class LintConfig:
    repeat_limit: int = 3
    max_tool_latency_ms: float | None = 10_000
    allowed_tools: frozenset[str] | None = None
    ignored_rules: frozenset[str] = frozenset()
