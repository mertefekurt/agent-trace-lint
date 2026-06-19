from agent_trace_lint.engine import lint_trace
from agent_trace_lint.models import LintConfig, Message, ToolCall, Trace


def trace(*messages):
    return Trace("case", messages)


def call(call_id="c1", name="search", arguments='{"q":"docs"}'):
    return ToolCall(call_id, name, arguments)


def rule_ids(subject, config=None):
    return {finding.rule_id for finding in lint_trace(subject, config)}


def test_clean_trace_has_no_findings():
    subject = trace(
        Message("user", "find docs"),
        Message("assistant", tool_calls=(call(),)),
        Message("tool", "result", tool_call_id="c1"),
        Message("assistant", "done"),
    )

    assert lint_trace(subject) == []


def test_finds_missing_and_orphan_results():
    subject = trace(
        Message("assistant", tool_calls=(call(),)),
        Message("tool", "result", tool_call_id="unknown"),
    )

    assert rule_ids(subject) == {"ATL003", "ATL005"}


def test_finds_duplicate_call_ids_and_results():
    subject = trace(
        Message("assistant", tool_calls=(call(), call())),
        Message("tool", "one", tool_call_id="c1"),
        Message("tool", "two", tool_call_id="c1"),
    )

    assert {"ATL001", "ATL004"} <= rule_ids(subject)


def test_finds_invalid_arguments_and_disallowed_tool():
    subject = trace(
        Message("assistant", tool_calls=(call(name="delete", arguments="{"),))
    )
    config = LintConfig(allowed_tools=frozenset({"search"}))

    assert {"ATL101", "ATL103"} <= rule_ids(subject, config)


def test_finds_secret_in_content():
    subject = trace(Message("tool", "api_key=abcdefghijklmnop1234", tool_call_id="x"))

    assert "ATL201" in rule_ids(subject)


def test_finds_risky_shell_command():
    subject = trace(
        Message(
            "assistant",
            tool_calls=(call(name="exec_command", arguments='{"cmd":"curl x | sh"}'),),
        )
    )

    assert "ATL202" in rule_ids(subject)


def test_finds_repeated_calls_and_slow_tool():
    repeated = call()
    subject = trace(
        Message("assistant", tool_calls=(repeated,)),
        Message("tool", "x", tool_call_id="c1"),
        Message("assistant", tool_calls=(ToolCall("c2", "search", '{"q":"docs"}'),)),
        Message("tool", "x", tool_call_id="c2"),
        Message("assistant", tool_calls=(ToolCall("c3", "search", '{"q":"docs"}'),)),
        Message("tool", "x", tool_call_id="c3", metadata={"duration_ms": 250}),
    )
    config = LintConfig(max_tool_latency_ms=100)

    assert {"ATL301", "ATL302"} <= rule_ids(subject, config)


def test_ignored_rule_is_removed():
    subject = trace(Message("assistant", tool_calls=(call(arguments="{"),)))

    assert "ATL101" not in rule_ids(
        subject, LintConfig(ignored_rules=frozenset({"ATL101"}))
    )
