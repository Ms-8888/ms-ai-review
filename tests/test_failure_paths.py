"""Failure-path tests: every API interaction is mocked, no network or key needed."""
from unittest.mock import MagicMock, patch

import pytest
from anthropic import APIConnectionError, APIStatusError, RateLimitError
from typer.testing import CliRunner

from ms_ai_review.cli import app
from ms_ai_review.reviewer import review_file
from tests.conftest import (
    _ContentBlockDeltaEvent,
    _ContentBlockStartEvent,
    _ContentBlockStopEvent,
    _FakeStream,
    _InputJsonDelta,
    _make_tool_events,
    _ToolUseBlock,
)


@pytest.fixture(autouse=True)
def set_api_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")


@pytest.fixture
def code_file(tmp_path):
    f = tmp_path / "code.py"
    f.write_text("x = 1\n")
    return f


def _response(status: int) -> MagicMock:
    return MagicMock(status_code=status, headers={})


class _ExplodingStream:
    """Yields the given events, then raises the given exception mid-stream."""

    def __init__(self, events, exc):
        self._events = events
        self._exc = exc

    def __enter__(self):
        def gen():
            yield from self._events
            raise self._exc

        return gen()

    def __exit__(self, *args):
        pass


def test_rate_limit_error_propagates_without_retry(code_file):
    err = RateLimitError("rate limited", response=_response(429), body=None)
    with patch("ms_ai_review.reviewer.Anthropic") as MockClient:
        MockClient.return_value.messages.create.side_effect = err
        with pytest.raises(RateLimitError):
            review_file(code_file)
        assert MockClient.return_value.messages.create.call_count == 1


def test_server_error_on_request_propagates(code_file):
    err = APIStatusError("overloaded", response=_response(529), body=None)
    with patch("ms_ai_review.reviewer.Anthropic") as MockClient:
        MockClient.return_value.messages.create.side_effect = err
        with pytest.raises(APIStatusError):
            review_file(code_file)


def test_error_mid_stream_propagates_and_writes_no_output(tmp_path, code_file):
    events = _make_tool_events(
        {"severity": "WARNING", "line": 1, "message": "first finding arrived"}
    )
    exc = APIConnectionError(request=MagicMock())
    out = tmp_path / "review.md"
    with patch("ms_ai_review.reviewer.Anthropic") as MockClient:
        MockClient.return_value.messages.create.return_value = _ExplodingStream(events, exc)
        with pytest.raises(APIConnectionError):
            review_file(code_file, output=out)
    assert not out.exists()


def test_timeout_mid_stream_propagates(code_file):
    with patch("ms_ai_review.reviewer.Anthropic") as MockClient:
        MockClient.return_value.messages.create.return_value = _ExplodingStream(
            [], TimeoutError("stream stalled")
        )
        with pytest.raises(TimeoutError):
            review_file(code_file)


def test_malformed_tool_json_is_skipped_and_other_findings_kept(code_file):
    bad = [
        _ContentBlockStartEvent(content_block=_ToolUseBlock()),
        _ContentBlockDeltaEvent(delta=_InputJsonDelta(partial_json='{"severity": "CRIT')),
        _ContentBlockStopEvent(),
    ]
    good = _make_tool_events({"severity": "INFO", "line": 2, "message": "kept"})
    with patch("ms_ai_review.reviewer.Anthropic") as MockClient:
        MockClient.return_value.messages.create.return_value = _FakeStream(bad + good)
        findings = review_file(code_file)
    assert [f.message for f in findings] == ["kept"]


def test_tool_output_missing_required_field_is_skipped(code_file, capsys):
    events = _make_tool_events({"severity": "CRITICAL", "message": "no line number"})
    with patch("ms_ai_review.reviewer.Anthropic") as MockClient:
        MockClient.return_value.messages.create.return_value = _FakeStream(events)
        findings = review_file(code_file)
    assert findings == []
    assert "malformed finding" in capsys.readouterr().out


def test_empty_tool_output_is_ignored(code_file):
    events = [
        _ContentBlockStartEvent(content_block=_ToolUseBlock()),
        _ContentBlockStopEvent(),
    ]
    with patch("ms_ai_review.reviewer.Anthropic") as MockClient:
        MockClient.return_value.messages.create.return_value = _FakeStream(events)
        assert review_file(code_file) == []


def test_unknown_severity_does_not_crash(tmp_path, code_file):
    events = _make_tool_events({"severity": "BLOCKER", "line": 3, "message": "odd level"})
    out = tmp_path / "review.md"
    with patch("ms_ai_review.reviewer.Anthropic") as MockClient:
        MockClient.return_value.messages.create.return_value = _FakeStream(events)
        findings = review_file(code_file, output=out)
    assert findings[0].severity == "BLOCKER"
    assert "odd level" in out.read_text()


def test_missing_file_raises_before_any_api_call(tmp_path):
    with patch("ms_ai_review.reviewer.Anthropic") as MockClient:
        with pytest.raises(FileNotFoundError):
            review_file(tmp_path / "nope.py")
        MockClient.return_value.messages.create.assert_not_called()


def test_cli_rejects_missing_file(tmp_path):
    result = CliRunner().invoke(app, [str(tmp_path / "nope.py")])
    assert result.exit_code == 2


def test_file_that_is_not_python_is_still_sent_to_the_model(tmp_path):
    f = tmp_path / "broken.py"
    f.write_text("def (:\n  this is not python\n")
    with patch("ms_ai_review.reviewer.Anthropic") as MockClient:
        MockClient.return_value.messages.create.return_value = _FakeStream([])
        assert review_file(f) == []
        sent = MockClient.return_value.messages.create.call_args.kwargs["messages"][0]["content"]
    assert "this is not python" in sent


def test_file_at_line_limit_is_accepted_and_one_over_is_rejected(tmp_path):
    ok = tmp_path / "ok.py"
    ok.write_text("x = 1\n" * 1999)  # 1999 newlines + 1 = 2000 lines
    over = tmp_path / "over.py"
    over.write_text("x = 1\n" * 2000)  # 2001 lines
    with patch("ms_ai_review.reviewer.Anthropic") as MockClient:
        MockClient.return_value.messages.create.return_value = _FakeStream([])
        assert review_file(ok) == []
        with pytest.raises(SystemExit, match="limit"):
            review_file(over)


def test_file_over_warn_threshold_prints_warning(tmp_path, capsys):
    f = tmp_path / "medium.py"
    f.write_text("x = 1\n" * 600)
    with patch("ms_ai_review.reviewer.Anthropic") as MockClient:
        MockClient.return_value.messages.create.return_value = _FakeStream([])
        review_file(f)
    assert "Warning" in capsys.readouterr().out
