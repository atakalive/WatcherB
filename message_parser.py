"""WatcherB message parser — classify and structure Discord messages."""

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

# Regex for extracting project name
_PROJECT_RE = re.compile(r"\[([^\]]+)\]")

# General state transition pattern: [PJ] STATE_A → STATE_B
_TRANSITION_RE = re.compile(r"\[.+?\]\s+\w+\s*→\s*\w+")

# State change extraction: STATE_A → STATE_B
_STATE_CHANGE_RE = re.compile(r"(\w+)\s*→\s*(\w+)")


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

    Returns one of: "blocked", "done", "transition", "info".
    blocked/done are special cases of transition, checked first.
    """
    if "→ BLOCKED" in content:
        return "blocked"
    if "→ DONE" in content:
        return "done"
    if _TRANSITION_RE.search(content):
        return "transition"
    return "info"


def _extract_project(content: str) -> Optional[str]:
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
    project = _extract_project(content)
    timestamp = created_at.strftime("%H:%M")

    extra = {}
    if msg_type in ("transition", "blocked", "done"):
        transition = extract_transition(content)
        if transition:
            extra["from_state"] = transition[0]
            extra["to_state"] = transition[1]

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
