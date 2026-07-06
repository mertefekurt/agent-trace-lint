# Agent Trace Lint

![Agent Trace Lint cover](assets/readme-cover.svg)

## What I keep this for

Offline linting for AI agent tool-call traces.

It is a small repo, so the README focuses on the path from clone to first useful output.

## Clone and run

```bash
git clone https://github.com/mertefekurt/agent-trace-lint.git
cd agent-trace-lint
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
agent-trace-lint examples/broken-trace.json
agent-trace-lint examples/broken-trace.json --json
```

## Checks before changing it

```bash
ruff check .
pytest
python -m agent_trace_lint --help
```
