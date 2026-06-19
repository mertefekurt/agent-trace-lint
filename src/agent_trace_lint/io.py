"""Load OpenAI-style agent traces from JSON and JSONL."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent_trace_lint.errors import InputError
from agent_trace_lint.models import Message, ToolCall, Trace


def load_traces(path: Path) -> list[Trace]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise InputError(f"cannot read {path}: {exc}") from exc

    if not raw.strip():
        raise InputError(f"{path} is empty")

    records = _decode_records(raw, path)
    return [_parse_trace(record, index) for index, record in enumerate(records)]


def _decode_records(raw: str, path: Path) -> list[Any]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        records: list[Any] = []
        for line_number, line in enumerate(raw.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise InputError(
                    f"{path}:{line_number}: invalid JSON: {exc.msg}"
                ) from exc
        return records

    return parsed if isinstance(parsed, list) else [parsed]


def _parse_trace(value: Any, index: int) -> Trace:
    if not isinstance(value, dict):
        raise InputError(f"trace {index + 1} must be a JSON object")

    messages = value.get("messages")
    if not isinstance(messages, list) or not messages:
        raise InputError(f"trace {index + 1} must contain a non-empty messages array")

    trace_id = str(value.get("id", value.get("trace_id", f"trace-{index + 1}")))
    return Trace(
        trace_id=trace_id,
        messages=tuple(
            _parse_message(message, index, i) for i, message in enumerate(messages)
        ),
    )


def _parse_message(value: Any, trace_index: int, message_index: int) -> Message:
    location = f"trace {trace_index + 1}, message {message_index}"
    if not isinstance(value, dict):
        raise InputError(f"{location} must be a JSON object")

    role = value.get("role")
    if not isinstance(role, str) or not role:
        raise InputError(f"{location} requires a string role")

    content = value.get("content")
    if content is not None and not isinstance(content, str):
        content = json.dumps(content, ensure_ascii=False)

    raw_calls = value.get("tool_calls", [])
    if not isinstance(raw_calls, list):
        raise InputError(f"{location} tool_calls must be an array")

    return Message(
        role=role,
        content=content,
        tool_calls=tuple(_parse_tool_call(call, location) for call in raw_calls),
        tool_call_id=_optional_string(value.get("tool_call_id")),
        metadata=value.get("metadata")
        if isinstance(value.get("metadata"), dict)
        else {},
    )


def _parse_tool_call(value: Any, location: str) -> ToolCall:
    if not isinstance(value, dict):
        raise InputError(f"{location} contains a non-object tool call")

    function = value.get("function", {})
    if not isinstance(function, dict):
        function = {}

    call_id = value.get("id")
    name = function.get("name", value.get("name"))
    arguments = function.get("arguments", value.get("arguments", "{}"))
    if not isinstance(call_id, str) or not call_id:
        raise InputError(f"{location} contains a tool call without an id")
    if not isinstance(name, str) or not name:
        raise InputError(f"{location} tool call {call_id!r} has no function name")
    if not isinstance(arguments, str):
        arguments = json.dumps(arguments, ensure_ascii=False)
    return ToolCall(id=call_id, name=name, arguments=arguments)


def _optional_string(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None
