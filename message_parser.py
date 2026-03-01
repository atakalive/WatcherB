"""WatcherB message parser — Discord メッセージの分類と構造化."""

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

# プロジェクト名抽出用正規表現
_PROJECT_RE = re.compile(r"\[([^\]]+)\]")

# 汎用状態遷移パターン: [PJ] STATE_A → STATE_B
_TRANSITION_RE = re.compile(r"\[.+?\]\s+\w+\s*→\s*\w+")

# 状態変更抽出: STATE_A → STATE_B
_STATE_CHANGE_RE = re.compile(r"(\w+)\s*→\s*(\w+)")


@dataclass
class ParsedMessage:
    """解析済みメッセージ."""

    msg_type: str
    project: Optional[str]
    raw_text: str
    timestamp: str
    extra: dict = field(default_factory=dict)


def classify(content: str) -> str:
    """メッセージ内容から種別を判定する.

    優先度順に評価し、最初にマッチした種別を返す。
    blocked/done は transition の特殊ケースなので先に判定する。
    """
    # 特殊遷移（汎用遷移より先に判定）
    if "→ BLOCKED" in content:
        return "blocked"
    if "→ DONE" in content:
        return "done"

    # CC進捗
    if "CC Plan 開始" in content or "CC Impl 開始" in content:
        return "cc_start"
    if "CC Plan 完了" in content or "CC Impl 完了" in content:
        return "cc_done"

    # 催促
    if "催促" in content:
        return "nudge"

    # REVISE
    if "REVISE対象:" in content:
        return "revise"

    # マージサマリー
    if "マージサマリー" in content:
        return "merge_summary"

    # Issue一覧
    if "対象Issue:" in content:
        return "issue_list"

    # 汎用状態遷移
    if _TRANSITION_RE.search(content):
        return "transition"

    return "unknown"


def _extract_project(content: str) -> Optional[str]:
    """[PJ] or [Queue][PJ] プレフィクスからプロジェクト名を抽出."""
    matches = _PROJECT_RE.findall(content)
    if not matches:
        return None
    # [Queue][PJ] の場合、"Queue" を飛ばして次のブラケットを返す
    for m in matches:
        if m != "Queue":
            return m
    return None


def extract_transition(content: str) -> Optional[tuple]:
    """状態遷移メッセージから (from_state, to_state) を抽出.

    Returns None if the message is not a state transition.
    """
    match = _STATE_CHANGE_RE.search(content)
    if match:
        return (match.group(1), match.group(2))
    return None


def parse_message(content: str, created_at: datetime) -> ParsedMessage:
    """メッセージを分類し構造化データとして返す."""
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
