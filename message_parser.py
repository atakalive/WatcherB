"""WatcherB message parser — classify and structure Discord messages."""

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import config

# Regex for extracting project name
_PROJECT_RE = re.compile(r"\[([^\]]+)\]")

# General state transition pattern: [PJ] STATE_A → STATE_B
_TRANSITION_RE = re.compile(r"\[.+?\]\s+\w+\s*→\s*\w+")

# State change extraction: STATE_A → STATE_B
_STATE_CHANGE_RE = re.compile(r"(\w+)\s*→\s*(\w+)")

# Progress notification regexes. The tool-call marker is built from
# config.PROGRESS_TOOL_MARKER via re.escape so the marker stays single-sourced.
_PROGRESS_TOOLCALLS_RE = re.compile(r"(\d+)\s*" + re.escape(config.PROGRESS_TOOL_MARKER))
_PROGRESS_AVG_RE = re.compile(r"avg\s*([\d.]+)/min")
_PROGRESS_NOW_RE = re.compile(r"now\s*([\d.]+)/min")
# finalized check: detect the in-progress signature "in progress — <N> tool calls".
# Requiring the separator —, a digit (tool-call count), and the tool marker right after
# "in progress" prevents false positives when a dynamic part (project name / STATE)
# merely contains "in progress —".
_PROGRESS_INPROGRESS_RE = re.compile(
    re.escape(config.PROGRESS_INPROGRESS_MARKER) + r"\s*—\s*\d+\s*"
    + re.escape(config.PROGRESS_TOOL_MARKER)
)
# elapsed: ⏱ (U+23F1) with optional VS16 (U+FE0F). Written with Unicode escapes so the
# pattern is pure ASCII and the optional ? applies only to the VS16, never the stopwatch.
_PROGRESS_ELAPSED_RE = re.compile(r"\u23f1\ufe0f?\s*(\S+)")


@dataclass
class ParsedMessage:
    """Parsed message."""

    msg_type: str
    project: Optional[str]
    raw_text: str
    timestamp: str
    extra: dict = field(default_factory=dict)


def classify(content: str) -> str:
    """Classify message content by type.

    Returns one of: "blocked", "done", "transition", "progress", "info".
    blocked/done are special cases of transition, checked first.
    """
    if "→ BLOCKED" in content:
        return "blocked"
    if "→ DONE" in content:
        return "done"
    if _TRANSITION_RE.search(content):
        return "transition"
    if config.PROGRESS_TOOL_MARKER in content:
        return "progress"
    return "info"


def extract_project(content: str) -> Optional[str]:
    """Extract project name from [PJ] or [Queue][PJ] prefix."""
    matches = _PROJECT_RE.findall(content)
    if not matches:
        return None
    # For [Queue][PJ], skip "Queue" and return the next bracket
    for m in matches:
        if m != "Queue":
            return m
    return None


def extract_transition(content: str) -> Optional[tuple]:
    """Extract (from_state, to_state) from a state transition message.

    Returns None if the message is not a state transition.
    """
    match = _STATE_CHANGE_RE.search(content)
    if match:
        return (match.group(1), match.group(2))
    return None


def parse_message(content: str, created_at: datetime) -> ParsedMessage:
    """Classify a message and return it as structured data."""
    msg_type = classify(content)
    project = extract_project(content)
    timestamp = created_at.strftime("%H:%M")

    extra = {}
    if msg_type in ("transition", "blocked", "done"):
        transition = extract_transition(content)
        if transition:
            extra["from_state"] = transition[0]
            extra["to_state"] = transition[1]

    if msg_type == "progress":
        m = _PROGRESS_TOOLCALLS_RE.search(content)
        if m:
            try:
                extra["tool_calls"] = int(m.group(1))
            except (ValueError, TypeError):
                pass
        m = _PROGRESS_AVG_RE.search(content)
        if m:
            try:
                extra["avg"] = float(m.group(1))
            except (ValueError, TypeError):
                pass
        m = _PROGRESS_NOW_RE.search(content)
        if m:
            try:
                extra["now"] = float(m.group(1))
            except (ValueError, TypeError):
                pass
        m = _PROGRESS_ELAPSED_RE.search(content)
        if m:
            extra["elapsed"] = m.group(1)   # str; no conversion needed
        extra["finalized"] = not _PROGRESS_INPROGRESS_RE.search(content)   # bool

    if msg_type == "info" and project and ("Target Issues:" in content or "対象Issue:" in content):
        issue_match = re.findall(r"^#(\d+):", content, re.MULTILINE)
        if issue_match:
            extra["issues"] = [int(n) for n in issue_match]

    return ParsedMessage(
        msg_type=msg_type,
        project=project,
        raw_text=content,
        timestamp=timestamp,
        extra=extra,
    )
