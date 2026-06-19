"""Render findings for humans and CI systems."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from agent_trace_lint.models import Finding, Severity


def render_text(findings: list[Finding], source: Path) -> str:
    if not findings:
        return f"✓ {source}: no findings"

    lines = []
    for finding in findings:
        location = f"{finding.trace_id}:message[{finding.message_index}]"
        if finding.tool_call_id:
            location += f":call[{finding.tool_call_id}]"
        lines.append(
            f"{finding.severity.value.upper():7} {finding.rule_id} "
            f"{location} {finding.message}"
        )

    counts = Counter(finding.severity for finding in findings)
    lines.append(
        f"\n{len(findings)} finding(s): "
        f"{counts[Severity.ERROR]} error(s), {counts[Severity.WARNING]} warning(s)"
    )
    return "\n".join(lines)


def render_json(findings: list[Finding]) -> str:
    return json.dumps(
        [
            {**asdict(finding), "severity": finding.severity.value}
            for finding in findings
        ],
        indent=2,
    )


def render_sarif(findings: list[Finding], source: Path) -> str:
    rule_ids = sorted({finding.rule_id for finding in findings})
    payload = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "agent-trace-lint",
                        "rules": [{"id": rule_id} for rule_id in rule_ids],
                    }
                },
                "results": [
                    {
                        "ruleId": finding.rule_id,
                        "level": finding.severity.value,
                        "message": {"text": finding.message},
                        "locations": [
                            {
                                "physicalLocation": {
                                    "artifactLocation": {"uri": str(source)},
                                    "region": {"startLine": finding.message_index + 1},
                                }
                            }
                        ],
                    }
                    for finding in findings
                ],
            }
        ],
    }
    return json.dumps(payload, indent=2)
