import json
import os
from pathlib import Path

from anthropic import Anthropic

from ms_ai_review.output import print_finding, print_summary, write_markdown
from ms_ai_review.prompts import SYSTEM_PROMPT
from ms_ai_review.tools import TOOL, Finding

MODEL = "claude-sonnet-4-6"
MAX_LINES_HARD = 2000
MAX_LINES_WARN = 500


def review_file(
    file_path: Path,
    context: str | None = None,
    output: Path | None = None,
) -> list[Finding]:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit("Error: ANTHROPIC_API_KEY not set. Add it to .env or export it.")

    code = file_path.read_text(encoding="utf-8")
    line_count = code.count("\n") + 1

    if line_count > MAX_LINES_HARD:
        raise SystemExit(
            f"Error: {file_path.name} has {line_count} lines (limit: {MAX_LINES_HARD}). "
            "Split the file or review a smaller section."
        )
    if line_count > MAX_LINES_WARN:
        print(f"Warning: {file_path.name} has {line_count} lines — review may be slower.")

    user_content = f"Review this file (`{file_path.name}`):\n\n```python\n{code}\n```"
    if context:
        user_content += f"\n\nAdditional context: {context}"

    print(f"Reviewing {file_path.name} with {MODEL}...")
    print("Analyzing...", end="", flush=True)

    client = Anthropic(api_key=api_key)
    findings: list[Finding] = []

    # cache_control marks the system prompt for prompt caching.
    # The prompt must be >1024 tokens to qualify — our detailed rubric ensures this.
    # File content is the variable part and is not cached.
    with client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_content}],
        tools=[TOOL],
        tool_choice={"type": "auto"},
        stream=True,
    ) as stream:
        current_json: list[str] = []
        in_tool_use = False
        first_event = True

        for event in stream:
            if first_event:
                print("\r" + " " * 12 + "\r", end="", flush=True)  # clear "Analyzing..."
                first_event = False

            if event.type == "content_block_start":
                in_tool_use = event.content_block.type == "tool_use"
                current_json = []

            elif event.type == "content_block_delta" and in_tool_use:
                if hasattr(event.delta, "partial_json"):
                    current_json.append(event.delta.partial_json)

            elif event.type == "content_block_stop" and in_tool_use:
                raw = "".join(current_json)
                if raw:
                    data = json.loads(raw)
                    finding = Finding(
                        severity=data["severity"],
                        line=data["line"],
                        message=data["message"],
                        fix=data.get("fix"),
                    )
                    findings.append(finding)
                    print_finding(finding)
                in_tool_use = False

    print_summary(findings, output, file_path.name)

    if output:
        write_markdown(findings, output, file_path.name, MODEL)

    return findings
