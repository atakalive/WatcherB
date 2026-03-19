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

    Evaluates in priority order, returning the first match.
    blocked/done are special cases of transition, so check them first.
    """
    # Special transitions (check before general transition)
    if "→ BLOCKED" in content:
        return "blocked"
    if "→ DONE" in content:
        return "done"

    # CC progress
    if "CC Plan 開始" in content or "CC Impl 開始" in content:
        return "cc_start"
    if "CC Plan 完了" in content or "CC Impl 完了" in content:
        return "cc_done"

    # Nudge
    if "催促" in content:
        return "nudge"

    # REVISE
    if "REVISE対象:" in content:
        return "revise"

    # Merge summary
    if "マージサマリー" in content:
        return "merge_summary"

    # Issue list
    if "対象Issue:" in content:
        return "issue_list"

    # General state transition
    if _TRANSITION_RE.search(content):
        return "transition"

    return "unknown"


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

    return ParsedMessage(
        msg_type=msg_type,
        project=project,
        raw_text=content,
        timestamp=timestamp,
        extra=extra,
    )
