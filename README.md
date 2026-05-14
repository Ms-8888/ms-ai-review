# ms-ai-review

CLI code reviewer powered by the Claude API — streaming output, structured tool use, prompt caching.

Connects to [ms-webhook-api](https://github.com/Ms-8888/ms-webhook-api) for a live demo of the exact patterns it reviews.

---

## Quick start

```bash
git clone https://github.com/Ms-8888/ms-ai-review
cd ms-ai-review
pip install -e .
echo "ANTHROPIC_API_KEY=your-key" > .env
python -m ms_ai_review review examples/sample_bad_code.py
```

Or with options:

```bash
python -m ms_ai_review review app/worker.py --context "async Redis worker"
python -m ms_ai_review review app/auth.py --output review.md
```

---

## Output

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

Python 3.12 · Anthropic SDK · Typer · pytest
