import json

import pytest

from agent_trace_lint.errors import InputError
from agent_trace_lint.io import load_traces


def test_loads_jsonl_and_assigns_fallback_id(tmp_path):
    path = tmp_path / "traces.jsonl"
    records = [
        {"id": "first", "messages": [{"role": "user", "content": "hello"}]},
        {"messages": [{"role": "assistant", "content": "done"}]},
    ]
    path.write_text("\n".join(json.dumps(record) for record in records))

    traces = load_traces(path)

    assert [trace.trace_id for trace in traces] == ["first", "trace-2"]


def test_rejects_empty_messages(tmp_path):
    path = tmp_path / "trace.json"
    path.write_text('{"messages": []}')

    with pytest.raises(InputError, match="non-empty messages"):
        load_traces(path)


def test_accepts_compact_tool_call_shape(tmp_path):
    path = tmp_path / "trace.json"
    path.write_text(
        json.dumps(
            {
                "messages": [
                    {
                        "role": "assistant",
                        "tool_calls": [
                            {"id": "c1", "name": "search", "arguments": {"q": "x"}}
                        ],
                    }
                ]
            }
        )
    )

    trace = load_traces(path)[0]

    assert trace.messages[0].tool_calls[0].arguments == '{"q": "x"}'
