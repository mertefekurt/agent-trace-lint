"""Rule execution and result filtering."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from agent_trace_lint.models import Finding, LintConfig, Trace
from agent_trace_lint.rules import (
    argument_findings,
    protocol_findings,
    reliability_findings,
    safety_findings,
)

Rule = Callable[[Trace, LintConfig], Iterable[Finding]]
RULES: tuple[Rule, ...] = (
    protocol_findings,
    argument_findings,
    safety_findings,
    reliability_findings,
)


def lint_trace(trace: Trace, config: LintConfig | None = None) -> list[Finding]:
    active_config = config or LintConfig()
    findings = [
        finding
        for rule in RULES
        for finding in rule(trace, active_config)
        if finding.rule_id not in active_config.ignored_rules
    ]
    return sorted(findings, key=lambda item: (item.message_index, item.rule_id))


def lint_traces(
    traces: Iterable[Trace], config: LintConfig | None = None
) -> list[Finding]:
    return [finding for trace in traces for finding in lint_trace(trace, config)]
