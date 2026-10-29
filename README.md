# ms-ai-review

[![CI](https://github.com/Ms-8888/ms-ai-review/actions/workflows/ci.yml/badge.svg)](https://github.com/Ms-8888/ms-ai-review/actions/workflows/ci.yml)

CLI code reviewer powered by the Claude API — streaming output, structured tool use, prompt caching.

## Problem

Asking an LLM to "review this code" returns free-form prose that is hard to scan, hard to filter by severity, and hard to turn into a checklist. A long answer also appears all at once at the end.

## Solution

The tool sends one Python file to the Claude API and forces the answer through a `report_finding` tool, so each issue comes back as structured data: severity, line number, message and fix. Findings print as soon as the model finishes each one, and the long review rubric in the system prompt is cached so repeat reviews are cheaper and faster.

> No API key? [`examples/sample_review.md`](examples/sample_review.md) shows the output format. It is a pre-generated example, not a fresh run of the current version; run the tool yourself to reproduce it.

---

## Quick start

```bash
git clone https://github.com/Ms-8888/ms-ai-review
cd ms-ai-review
pip install -e .
export ANTHROPIC_API_KEY=your-key   # PowerShell: $env:ANTHROPIC_API_KEY="your-key"
python -m ms_ai_review review examples/sample_bad_code.py
```

Or with options:

```bash
python -m ms_ai_review review app/worker.py --context "async Redis worker"
python -m ms_ai_review review app/auth.py --output review.md
```

---

## Output

Example of the terminal format (illustrative):

```
Reviewing sample_bad_code.py with claude-sonnet-4-6...

[CRITICAL] Line 15 — Timing attack vulnerability
           Fix: Use hmac.compare_digest(token, stored_token)

[CRITICAL] Line 19 — SHA-256 is not suitable for password hashing
           Fix: Use bcrypt.hashpw(password.encode(), bcrypt.gensalt())

[CRITICAL] Line 24 — SQL injection via string formatting
           Fix: Use parameterized queries: cursor.execute("SELECT ...", (user_id,))

[WARNING]  Line 34 — Cryptographically weak token generation
           Fix: Use secrets.token_hex(32)

Summary: 3 critical, 1 warning, 1 info.
```

See [`examples/sample_review.md`](examples/sample_review.md) for the full pre-generated output.

---

## How it uses the Claude API

### 1. Streaming

The tool uses `messages.create(stream=True)` to iterate over raw server-sent events. Each event type is handled explicitly:

```python
with client.messages.create(stream=True, ...) as stream:
    for event in stream:
        if event.type == "content_block_start":
            in_tool_use = event.content_block.type == "tool_use"
        elif event.type == "content_block_delta" and in_tool_use:
            current_json.append(event.delta.partial_json)
        elif event.type == "content_block_stop" and in_tool_use:
            finding = Finding(**json.loads("".join(current_json)))
            print_finding(finding)  # appears as each finding is completed
```

Findings display one at a time as the model reports them — not after the full response.

### 2. Tool use (structured output)

The model calls `report_finding` once per issue, producing structured JSON instead of free-form text. This makes parsing reliable and eliminates regex extraction:

```python
TOOL = {
    "name": "report_finding",
    "input_schema": {
        "type": "object",
        "properties": {
            "severity": {"type": "string", "enum": ["CRITICAL", "WARNING", "INFO"]},
            "line":     {"type": "integer"},
            "message":  {"type": "string"},
            "fix":      {"type": "string"},
        },
        "required": ["severity", "line", "message"],
    },
}
```

### 3. Prompt caching

The system prompt (a detailed 1400-token review rubric) is marked for caching with `cache_control`. File content is the variable part and is not cached. Repeated reviews of different files in the same session reuse the cached prompt, reducing latency and cost.

```python
system=[
    {
        "type": "text",
        "text": SYSTEM_PROMPT,          # ~1400 tokens, cached after first call
        "cache_control": {"type": "ephemeral"},
    }
]
```

---

## Reproduce the example

```bash
python -m ms_ai_review review examples/sample_bad_code.py --output examples/my_review.md
```

`examples/sample_bad_code.py` is a deliberately flawed file with 4 critical security issues, 2 warnings, and 2 info findings.

---

## Stack

Python 3.11+ · Anthropic SDK · Typer · pytest

---

## Limitations

- Reviews one Python file at a time; no repository-wide context.
- Needs an `ANTHROPIC_API_KEY`; each review is a paid API call.
- Findings are model output and can be wrong. Treat them as a second pair of eyes, not a gate.
- Covered by 24 mocked unit tests; the live API path has no automated test.
