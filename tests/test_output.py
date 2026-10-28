
from ms_ai_review.output import format_finding, write_markdown
from ms_ai_review.tools import Finding


def test_format_critical_with_fix():
    f = Finding(severity="CRITICAL", line=23, message="Timing attack", fix="Use hmac.compare_digest")
    result = format_finding(f)
    assert "[CRITICAL]" in result
    assert "Line 23" in result
    assert "Timing attack" in result
    assert "hmac.compare_digest" in result


def test_format_info_without_fix():
    f = Finding(severity="INFO", line=5, message="Missing type hint")
    result = format_finding(f)
    assert "[INFO]" in result
    assert "Fix:" not in result


def test_write_markdown_creates_file(tmp_path):
    findings = [
        Finding(severity="CRITICAL", line=10, message="SQL injection", fix="Use params"),
        Finding(severity="WARNING", line=20, message="Weak random"),
    ]
    out = tmp_path / "review.md"
    write_markdown(findings, out, "auth.py", "claude-sonnet-4-6")
    text = out.read_text()
    assert "# Code Review: auth.py" in text
    assert "CRITICAL" in text
    assert "SQL injection" in text
    assert "1 critical" in text
    assert "claude-sonnet-4-6" in text


def test_write_markdown_no_findings(tmp_path):
    out = tmp_path / "review.md"
    write_markdown([], out, "clean.py", "claude-sonnet-4-6")
    text = out.read_text()
    assert "No issues found" in text
