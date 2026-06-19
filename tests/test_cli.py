import json

from agent_trace_lint.cli import main


def test_cli_returns_one_for_error(tmp_path, capsys):
    path = tmp_path / "trace.json"
    path.write_text(
        json.dumps(
            {
                "messages": [
                    {
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "id": "c1",
                                "function": {"name": "search", "arguments": "{}"},
                            }
                        ],
                    }
                ]
            }
        )
    )

    assert main([str(path)]) == 1
    assert "ATL005" in capsys.readouterr().out


def test_cli_json_and_never_fail(tmp_path, capsys):
    path = tmp_path / "trace.json"
    path.write_text('{"messages":[{"role":"user","content":"hello"}]}')

    assert main([str(path), "--format", "json", "--fail-on", "never"]) == 0
    assert capsys.readouterr().out.strip() == "[]"
