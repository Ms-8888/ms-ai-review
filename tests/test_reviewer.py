import os
from pathlib import Path

import pytest

from ms_ai_review.reviewer import review_file
from ms_ai_review.tools import Finding


@pytest.fixture(autouse=True)
def set_api_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")


def test_returns_one_finding(tmp_path, mock_stream_one_finding):
    f = tmp_path / "code.py"
    f.write_text("x = 1\n")
    findings = review_file(f)
    assert len(findings) == 1
    assert findings[0].severity == "CRITICAL"
    assert findings[0].line == 5
    assert findings[0].message == "SQL injection"
    assert findings[0].fix == "Use parameterized queries"


def test_returns_no_findings_for_clean_code(tmp_path, mock_stream_no_findings):
    f = tmp_path / "clean.py"
    f.write_text("x = 1\n")
    findings = review_file(f)
    assert findings == []


def test_returns_multiple_findings(tmp_path, mock_stream_multiple_findings):
    f = tmp_path / "bad.py"
    f.write_text("x = 1\n")
    findings = review_file(f)
    assert len(findings) == 3
    assert findings[0].severity == "CRITICAL"
    assert findings[1].severity == "WARNING"
    assert findings[2].severity == "INFO"
    assert findings[2].fix is None


def test_raises_on_missing_api_key(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    f = tmp_path / "code.py"
    f.write_text("x = 1\n")
    with pytest.raises(SystemExit, match="ANTHROPIC_API_KEY"):
        review_file(f)


def test_raises_on_file_too_large(tmp_path, mock_stream_no_findings):
    f = tmp_path / "big.py"
    f.write_text("x = 1\n" * 2001)
    with pytest.raises(SystemExit, match="limit"):
        review_file(f)


def test_saves_markdown_output(tmp_path, mock_stream_one_finding):
    code = tmp_path / "code.py"
    code.write_text("x = 1\n")
    out = tmp_path / "review.md"
    review_file(code, output=out)
    assert out.exists()
    text = out.read_text()
    assert "CRITICAL" in text
    assert "SQL injection" in text


def test_passes_context_to_api(tmp_path, mock_stream_no_findings):
    f = tmp_path / "worker.py"
    f.write_text("x = 1\n")
    review_file(f, context="async Redis worker")
    call_kwargs = mock_stream_no_findings.return_value.messages.create.call_args
    assert "async Redis worker" in str(call_kwargs)
