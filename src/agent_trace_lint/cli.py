"""Command-line interface for agent-trace-lint."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from agent_trace_lint.engine import lint_traces
from agent_trace_lint.errors import TraceLintError
from agent_trace_lint.io import load_traces
from agent_trace_lint.models import LintConfig, Severity
from agent_trace_lint.reporters import render_json, render_sarif, render_text


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-trace-lint",
        description=(
            "Lint recorded AI agent traces for protocol, safety, "
            "and reliability issues."
        ),
    )
    parser.add_argument("path", type=Path, help="JSON or JSONL trace file")
    parser.add_argument(
        "--format",
        choices=("text", "json", "sarif"),
        default="text",
        help="output format (default: text)",
    )
    parser.add_argument(
        "--allow-tool",
        action="append",
        default=None,
        metavar="NAME",
        help="allowed tool name; repeat to define an allowlist",
    )
    parser.add_argument(
        "--ignore",
        action="append",
        default=[],
        metavar="RULE",
        help="rule id to ignore; repeat as needed",
    )
    parser.add_argument(
        "--repeat-limit",
        type=int,
        default=3,
        help="identical calls before loop warning (default: 3)",
    )
    parser.add_argument(
        "--max-tool-latency-ms",
        type=float,
        default=10_000,
        help="latency warning threshold; negative disables it",
    )
    parser.add_argument(
        "--fail-on",
        choices=("error", "warning", "never"),
        default="error",
        help="exit non-zero threshold (default: error)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.repeat_limit < 2:
        parser.error("--repeat-limit must be at least 2")

    config = LintConfig(
        repeat_limit=args.repeat_limit,
        max_tool_latency_ms=(
            None if args.max_tool_latency_ms < 0 else args.max_tool_latency_ms
        ),
        allowed_tools=(
            frozenset(args.allow_tool) if args.allow_tool is not None else None
        ),
        ignored_rules=frozenset(args.ignore),
    )

    try:
        findings = lint_traces(load_traces(args.path), config)
    except TraceLintError as exc:
        print(f"agent-trace-lint: {exc}", file=sys.stderr)
        return 2

    renderers = {"text": render_text, "json": render_json, "sarif": render_sarif}
    renderer = renderers[args.format]
    output = (
        renderer(findings, args.path)
        if args.format in {"text", "sarif"}
        else renderer(findings)
    )
    print(output)

    if args.fail_on == "never":
        return 0
    if args.fail_on == "warning":
        return int(bool(findings))
    return int(any(item.severity is Severity.ERROR for item in findings))


if __name__ == "__main__":
    raise SystemExit(main())
