"""Deterministic rules for agent protocol, safety, and reliability."""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Iterable
from typing import Any

from agent_trace_lint.models import Finding, LintConfig, Severity, Trace

SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(
        r"(?i)\b(?:api[_-]?key|access[_-]?token|secret)\b\s*[:=]\s*[\"']?[A-Za-z0-9_./+=-]{12,}"
    ),
)
RISKY_SHELL_PATTERNS = (
    (re.compile(r"(^|\s)rm\s+-[^\n]*r[^\n]*f\s+/(?:\s|$)"), "recursive deletion of /"),
    (re.compile(r"\bcurl\b[^\n|]*\|\s*(?:ba)?sh\b"), "remote script piped to a shell"),
    (re.compile(r"\bwget\b[^\n|]*\|\s*(?:ba)?sh\b"), "remote script piped to a shell"),
    (re.compile(r"\bsudo\b"), "privileged command"),
    (re.compile(r"\bchmod\s+(?:-R\s+)?777\b"), "world-writable permissions"),
    (re.compile(r"\bgit\s+reset\s+--hard\b"), "destructive git reset"),
)
SHELL_TOOL_NAMES = frozenset(
    {"bash", "shell", "exec", "exec_command", "run_command", "terminal"}
)


def protocol_findings(trace: Trace, _: LintConfig) -> Iterable[Finding]:
    calls: dict[str, tuple[int, str]] = {}
    results: Counter[str] = Counter()

    for index, message in enumerate(trace.messages):
        for call in message.tool_calls:
            if call.id in calls:
                yield _finding(
                    "ATL001",
                    Severity.ERROR,
                    f"duplicate tool call id {call.id!r}",
                    trace,
                    index,
                    call.id,
                )
            else:
                calls[call.id] = (index, call.name)

        if message.role == "tool":
            if message.tool_call_id is None:
                yield _finding(
                    "ATL002",
                    Severity.ERROR,
                    "tool result is missing tool_call_id",
                    trace,
                    index,
                )
            elif message.tool_call_id not in calls:
                yield _finding(
                    "ATL003",
                    Severity.ERROR,
                    f"tool result references unknown call {message.tool_call_id!r}",
                    trace,
                    index,
                    message.tool_call_id,
                )
            else:
                results[message.tool_call_id] += 1
                if results[message.tool_call_id] > 1:
                    yield _finding(
                        "ATL004",
                        Severity.ERROR,
                        f"multiple results returned for call {message.tool_call_id!r}",
                        trace,
                        index,
                        message.tool_call_id,
                    )

    for call_id, (index, name) in calls.items():
        if results[call_id] == 0:
            yield _finding(
                "ATL005",
                Severity.ERROR,
                f"tool call {name!r} has no result",
                trace,
                index,
                call_id,
            )


def argument_findings(trace: Trace, config: LintConfig) -> Iterable[Finding]:
    for index, message in enumerate(trace.messages):
        for call in message.tool_calls:
            try:
                arguments = json.loads(call.arguments)
            except json.JSONDecodeError as exc:
                arguments = None
                yield _finding(
                    "ATL101",
                    Severity.ERROR,
                    f"{call.name!r} arguments are invalid JSON: {exc.msg}",
                    trace,
                    index,
                    call.id,
                )

            if arguments is not None and not isinstance(arguments, dict):
                yield _finding(
                    "ATL102",
                    Severity.ERROR,
                    f"{call.name!r} arguments must decode to an object",
                    trace,
                    index,
                    call.id,
                )

            if (
                config.allowed_tools is not None
                and call.name not in config.allowed_tools
            ):
                yield _finding(
                    "ATL103",
                    Severity.ERROR,
                    f"tool {call.name!r} is not in the allowlist",
                    trace,
                    index,
                    call.id,
                )


def safety_findings(trace: Trace, _: LintConfig) -> Iterable[Finding]:
    for index, message in enumerate(trace.messages):
        for text, call_id in _message_text(message):
            if any(pattern.search(text) for pattern in SECRET_PATTERNS):
                yield _finding(
                    "ATL201",
                    Severity.ERROR,
                    "possible secret exposed in trace content",
                    trace,
                    index,
                    call_id,
                )

        for call in message.tool_calls:
            if call.name.casefold() not in SHELL_TOOL_NAMES:
                continue
            command = _extract_command(call.arguments)
            if command is None:
                continue
            for pattern, description in RISKY_SHELL_PATTERNS:
                if pattern.search(command):
                    yield _finding(
                        "ATL202",
                        Severity.ERROR,
                        f"risky shell operation: {description}",
                        trace,
                        index,
                        call.id,
                    )


def reliability_findings(trace: Trace, config: LintConfig) -> Iterable[Finding]:
    streak_signature: tuple[str, str] | None = None
    streak = 0

    for index, message in enumerate(trace.messages):
        for call in message.tool_calls:
            signature = (call.name, _canonical_arguments(call.arguments))
            if signature == streak_signature:
                streak += 1
            else:
                streak_signature = signature
                streak = 1
            if streak == config.repeat_limit:
                yield _finding(
                    "ATL301",
                    Severity.WARNING,
                    f"identical tool call repeated {streak} times; possible agent loop",
                    trace,
                    index,
                    call.id,
                )

        latency = message.metadata.get("duration_ms")
        if (
            message.role == "tool"
            and config.max_tool_latency_ms is not None
            and isinstance(latency, (int, float))
            and not isinstance(latency, bool)
            and latency > config.max_tool_latency_ms
        ):
            yield _finding(
                "ATL302",
                Severity.WARNING,
                (
                    f"tool latency {latency:g} ms exceeds "
                    f"{config.max_tool_latency_ms:g} ms"
                ),
                trace,
                index,
                message.tool_call_id,
            )


def _message_text(message: Any) -> Iterable[tuple[str, str | None]]:
    if message.content:
        yield message.content, message.tool_call_id
    for call in message.tool_calls:
        yield call.arguments, call.id


def _extract_command(arguments: str) -> str | None:
    try:
        value = json.loads(arguments)
    except json.JSONDecodeError:
        return None
    if not isinstance(value, dict):
        return None
    for key in ("cmd", "command", "script"):
        command = value.get(key)
        if isinstance(command, str):
            return command
    return None


def _canonical_arguments(arguments: str) -> str:
    try:
        return json.dumps(json.loads(arguments), sort_keys=True, separators=(",", ":"))
    except json.JSONDecodeError:
        return arguments.strip()


def _finding(
    rule_id: str,
    severity: Severity,
    message: str,
    trace: Trace,
    index: int,
    call_id: str | None = None,
) -> Finding:
    return Finding(rule_id, severity, message, trace.trace_id, index, call_id)
