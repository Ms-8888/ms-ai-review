"""
Mock helpers for the Claude streaming API.

The Anthropic SDK's messages.create(stream=True) returns a Stream that yields
RawMessageStreamEvent objects. This module provides a minimal fake that emits
the same event shape so tests don't need a real API key.
"""
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Iterator
from unittest.mock import patch

import pytest


@dataclass
class _ToolUseBlock:
    type: str = "tool_use"
    id: str = "toolu_01"
    name: str = "report_finding"


@dataclass
class _TextBlock:
    type: str = "text"
    text: str = ""


@dataclass
class _ContentBlockStartEvent:
    type: str = "content_block_start"
    content_block: object = field(default_factory=_ToolUseBlock)


@dataclass
class _InputJsonDelta:
    type: str = "input_json_delta"
    partial_json: str = ""


@dataclass
class _ContentBlockDeltaEvent:
    type: str = "content_block_delta"
    delta: object = field(default_factory=_InputJsonDelta)


@dataclass
class _ContentBlockStopEvent:
    type: str = "content_block_stop"


def _make_tool_events(payload: dict) -> list:
    """Build the sequence of streaming events for a single tool call."""
    import json
    raw = json.dumps(payload)
    return [
        _ContentBlockStartEvent(content_block=_ToolUseBlock()),
        _ContentBlockDeltaEvent(delta=_InputJsonDelta(partial_json=raw)),
        _ContentBlockStopEvent(),
    ]


class _FakeStream:
    """Fake context manager that iterates over pre-built events."""

    def __init__(self, events: list):
        self._events = events

    def __enter__(self):
        return iter(self._events)

    def __exit__(self, *args):
        pass


@pytest.fixture
def mock_stream_one_finding():
    """Patch Anthropic to emit a single CRITICAL finding."""
    events = _make_tool_events(
        {"severity": "CRITICAL", "line": 5, "message": "SQL injection", "fix": "Use parameterized queries"}
    )

    with patch("ms_ai_review.reviewer.Anthropic") as MockClient:
        MockClient.return_value.messages.create.return_value = _FakeStream(events)
        yield MockClient


@pytest.fixture
def mock_stream_no_findings():
    """Patch Anthropic to emit no tool calls (no findings)."""
    with patch("ms_ai_review.reviewer.Anthropic") as MockClient:
        MockClient.return_value.messages.create.return_value = _FakeStream([])
        yield MockClient


@pytest.fixture
def mock_stream_multiple_findings():
    """Patch Anthropic to emit CRITICAL + WARNING + INFO findings."""
    events = (
        _make_tool_events({"severity": "CRITICAL", "line": 10, "message": "Timing attack", "fix": "hmac.compare_digest"})
        + _make_tool_events({"severity": "WARNING", "line": 20, "message": "Weak random", "fix": "Use secrets module"})
        + _make_tool_events({"severity": "INFO", "line": 30, "message": "Missing type hint"})
    )
    with patch("ms_ai_review.reviewer.Anthropic") as MockClient:
        MockClient.return_value.messages.create.return_value = _FakeStream(events)
        yield MockClient
