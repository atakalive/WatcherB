"""LLM provider status polling thread (periodic, cooperative shutdown)."""

import logging
import time

import requests
from PySide6.QtCore import QMutex, QMutexLocker, QThread, Signal

import config

_logger = logging.getLogger(__name__)

# Statuspage v2 の status.indicator → 内部レベル。
# 正規 indicator は none/minor/major/critical のみ。maintenance（計画メンテ）は
# 「障害が検知されたときだけ表示」というユーザー確定事項に従い "ok"（非障害）に倒す。
# 未知/欠落は "unknown"（取得成功だがスキーマ不一致）。 (dijkstra R1 P2-3 対応)
_STATUSPAGE_LEVELS: dict[str, str] = {
    "none": "ok",
    "maintenance": "ok",
    "minor": "minor",
    "major": "major",
    "critical": "major",
}

# Statuspage component status → 人間向けラベル。
# operational / under_maintenance は除外（"maintenance = 非障害" 既定に一致）。
# これは Statuspage component status enum の全集合であり、ここに無い値は障害扱いしない。
_STATUSPAGE_COMPONENT_STATUS: dict[str, str] = {
    "degraded_performance": "Degraded Performance",
    "partial_outage": "Partial Outage",
    "major_outage": "Major Outage",
}


def _normalize_statuspage(data: object) -> tuple[str, str]:
    """Statuspage /api/v2/summary.json の top-level status から (level, description) を返す純関数。

    level は "ok"/"minor"/"major"/"unknown"。HTTP には一切触れない。
    data が dict でない・status キーが無い/dict でない・indicator が未知/欠落の場合は
    ("unknown", "") にフォールバックする（KeyError で落とさない）。
    """
    if not isinstance(data, dict):
        return "unknown", ""
    status = data.get("status")
    if not isinstance(status, dict):
        return "unknown", ""
    level = _STATUSPAGE_LEVELS.get(status.get("indicator"), "unknown")
    description = status.get("description") or ""
    return level, description


def _normalize_gcp(incidents: object, match: list[str]) -> tuple[str, str]:
    """GCP incidents.json の list から (level, description) を返す純関数。

    進行中の判定: incident["end"] が None / 空文字 / 欠落（= falsy）なら進行中。
      GCP は進行中インシデントの end を null/欠落にし、解決時にタイムスタンプ文字列を入れる仕様。
      タイムスタンプ等の非空値が入っていれば解決済みとみなす（pascal R1 P2-4: end 判定の意図を明記）。
    抽出条件: 進行中 かつ affected_products[].title のいずれかが match 語（大小無視・部分一致）を含む。
      product は dict、かつ title は str のものだけを対象にする。title が非文字列（int 等の truthy 値）
      の product はスキップして TypeError を出さない（euler R2 P2: 型ガードの徹底）。
    集約: 該当が無ければ ("ok", "")。該当のうち severity=="high"（大小無視）が1つでもあれば
      ("major", その先頭の external_desc)、それ以外は ("minor", 先頭該当の external_desc)。
    incidents が list でない場合は ("unknown", "")。各要素・各 product は型ガードして例外を出さない。

    実装メモ（pascal R1 P2-3 への設計判断）: incidents.json は全履歴を含み数百 KB になりうるが、
      GCP は配列の時系列ソート順を仕様で保証していないため「古い要素で break」最適化は進行中
      インシデントの取りこぼし（偽陰性）を招く。10分間隔・進行中フィルタは end の有無を見るだけの
      軽量判定であり、数百 KB の全件走査コストは無視できる。よって正しさ優先で全件走査を維持する。
    """
    if not isinstance(incidents, list):
        return "unknown", ""
    match_lower = [m.lower() for m in match]
    matched: list[dict] = []
    for inc in incidents:
        if not isinstance(inc, dict) or inc.get("end"):
            continue  # end が truthy = 解決済み
        products = inc.get("affected_products") or []
        titles = " ".join(
            p["title"] for p in products
            if isinstance(p, dict) and isinstance(p.get("title"), str)
        ).lower()
        if any(m in titles for m in match_lower):
            matched.append(inc)
    if not matched:
        return "ok", ""
    high = [inc for inc in matched if (inc.get("severity") or "").lower() == "high"]
    chosen = high[0] if high else matched[0]
    level = "major" if high else "minor"
    return level, (chosen.get("external_desc") or "")


def _statuspage_details(data: object) -> list[dict]:
    """summary.json の dict から劣化中の subsystem を [{"what","how"}, ...] で返す純関数。

    優先: 非 operational component（status が _STATUSPAGE_COMPONENT_STATUS のキー）を列挙する。
      group container（c["group"] が truthy）は子の status がロールアップされた親なので除外し、
      子コンポーネントとの重複行を防ぐ（dijkstra P2-2）。
    component が 1 件も無ければ active incidents（summary.json は未解決分のみ列挙）にフォールバックする。
      防御として status が "resolved"/"postmortem"（大小無視）の incident は除外する（pascal P2-2）。
      impact を minor→"Minor" / major→"Major" / critical→"Critical" / それ以外→"Incident" に写像する。
    data/各要素/各フィールドを型ガードし、例外は出さない。
    """
    if not isinstance(data, dict):
        return []
    details: list[dict] = []
    components = data.get("components")
    if isinstance(components, list):
        for c in components:
            if not isinstance(c, dict) or c.get("group"):
                continue
            status = c.get("status")
            name = c.get("name")
            if isinstance(status, str) and status in _STATUSPAGE_COMPONENT_STATUS and isinstance(name, str):
                details.append({"what": name, "how": _STATUSPAGE_COMPONENT_STATUS[status]})
    if details:
        return details
    incidents = data.get("incidents")
    if isinstance(incidents, list):
        for inc in incidents:
            if not isinstance(inc, dict):
                continue
            inc_status = inc.get("status")
            if isinstance(inc_status, str) and inc_status.lower() in ("resolved", "postmortem"):
                continue
            name = inc.get("name")
            if not isinstance(name, str):
                continue
            impact = inc.get("impact")
            how = {"minor": "Minor", "major": "Major", "critical": "Critical"}.get(
                impact if isinstance(impact, str) else "", "Incident"
            )
            details.append({"what": name, "how": how})
    return details


def _gcp_details(incidents: object, match: list[str]) -> list[dict]:
    """incidents.json の list から進行中の該当インシデントを [{"what","how"}, ...] で返す純関数。

    進行中: incident["end"] が falsy（_normalize_gcp と同一判定）。
    該当判定: 全 product title を " " 連結し小文字化したものに match 語（小文字化）のいずれかが
      部分一致するか。_normalize_gcp と完全に同一の判定なので、両関数が食い違わない
      （"Vertex AI" 等の空白入り match 語でも一致が崩れない。dijkstra P2-1）。
    what: 個別 title が match したものを ", " 連結。個別一致が無い（空白跨ぎ）場合は全 title を連結し
      what が空にならないようにする。how は external_desc（str 以外/欠落は ""）。
    incidents が list でない場合は []。各要素・各 product を型ガードし、例外は出さない。
    """
    if not isinstance(incidents, list):
        return []
    match_lower = [m.lower() for m in match]
    details: list[dict] = []
    for inc in incidents:
        if not isinstance(inc, dict) or inc.get("end"):
            continue
        products = inc.get("affected_products") or []
        if not isinstance(products, list):
            continue
        titles = [
            p["title"] for p in products
            if isinstance(p, dict) and isinstance(p.get("title"), str)
        ]
        joined = " ".join(titles).lower()
        if not any(m in joined for m in match_lower):
            continue  # _normalize_gcp と同一の relevance 判定
        matched_titles = [t for t in titles if any(m in t.lower() for m in match_lower)]
        desc = inc.get("external_desc")
        details.append({
            "what": ", ".join(matched_titles) if matched_titles else ", ".join(titles),
            "how": desc if isinstance(desc, str) else "",
        })
    return details


class StatusMonitorThread(QThread):
    """各 LLM プロバイダの公式ステータスを周期取得するワーカースレッド。"""

    statuses_updated = Signal(list)  # [{"key","name","level","description","details","page"}, ...] 全プロバイダ分

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mutex = QMutex()
        self._shutdown = False
        self._session = requests.Session()
        self._session.headers["User-Agent"] = "WatcherB"
        self._provider_unknown_streak: dict[str, int] = {}  # key -> 連続 unknown 回数

    def _is_shutdown(self) -> bool:
        with QMutexLocker(self._mutex):
            return self._shutdown

    def shutdown(self) -> None:
        """協調的シャットダウン。"""
        with QMutexLocker(self._mutex):
            self._shutdown = True
        self._session.close()

    def _sleep_interruptible(self, seconds: float) -> bool:
        """seconds を 0.2 秒刻みで sleep。途中で shutdown 要求が来たら True を返す。"""
        elapsed = 0.0
        step = 0.2
        while elapsed < seconds:
            if self._is_shutdown():
                return True
            time.sleep(min(step, seconds - elapsed))
            elapsed += step
        return self._is_shutdown()

    def _fetch_one(self, provider: dict) -> dict:
        """1プロバイダを取得・正規化し {"key","name","level","description","details","page"} を返す。

        安全境界（dijkstra R2 P2-b: 文と実装を一致させる）:
          - key/name は provider.get の既定値で防御する（try ではなく .get が安全境界）。
            将来 try の前で provider["..."] を直接引かないこと（KeyError→スレッド死の再発防止）。
          - HTTP/JSON/正規化の失敗は try/except Exception で捕捉し level="unknown" のまま返す。
        各プロバイダ独立に try するので、ここの失敗が他プロバイダの取得を止めない。
        timeout は (connect, read) タプルで明示（dijkstra R1 P1: 単一 get の上限を明確化）。
        """
        key = provider.get("key", "?")
        result = {
            "key": key,
            "name": provider.get("name", key),
            "level": "unknown",
            "description": "",
            "details": [],
            "page": provider.get("page") or provider.get("url", ""),
        }
        timeout = (config.STATUS_POLL_TIMEOUT, config.STATUS_POLL_TIMEOUT)
        try:
            if provider["type"] == "statuspage":
                resp = self._session.get(f"{provider['url']}/api/v2/summary.json", timeout=timeout)
                resp.raise_for_status()
                data = resp.json()
                level, desc = _normalize_statuspage(data)
                details = _statuspage_details(data)
            else:  # "gcp"
                resp = self._session.get(provider["url"], timeout=timeout)
                resp.raise_for_status()
                data = resp.json()
                match = provider.get("match", [])
                level, desc = _normalize_gcp(data, match)
                details = _gcp_details(data, match)
            result["level"] = level
            result["description"] = desc
            result["details"] = details
        except Exception:
            _logger.debug("status fetch failed for %s", key, exc_info=True)
        return result

    def _track_provider_unknown(self, result: dict) -> None:
        """単一プロバイダの連続 unknown を追跡し、閾値到達時に WARNING を1回出す。

        全プロバイダ同時 unknown(=回線断)は MainWindow 側 streak で UI 表示するが、
        一部 url だけが恒常 unknown(誤 url/ドメイン変更/非 Statuspage)のケースは全断 streak では
        捕捉できない(他が ok で毎回リセット)。プロバイダ毎の連続 unknown をログで可視化し、
        未検証 url の実機診断手段とする(dijkstra R2 P2-c)。UI 表示はしない。
        """
        key = result["key"]
        if result["level"] == "unknown":
            streak = self._provider_unknown_streak.get(key, 0) + 1
            self._provider_unknown_streak[key] = streak
            if streak == config.STATUS_POLL_PROVIDER_UNKNOWN_WARN:
                _logger.warning(
                    "provider %r unknown for %d consecutive polls (check URL/endpoint)", key, streak
                )
        else:
            self._provider_unknown_streak[key] = 0

    def run(self) -> None:
        while True:
            if self._is_shutdown():
                return
            statuses: list[dict] = []
            for provider in config.STATUS_PROVIDERS:
                if self._is_shutdown():
                    return  # プロバイダ間で停止確認。要求が来たら emit せず即終了
                result = self._fetch_one(provider)
                statuses.append(result)
                self._track_provider_unknown(result)
            if self._is_shutdown():
                return  # 取得直後の shutdown でも emit を抑止（破棄中 QLabel への emit 回避）
            self.statuses_updated.emit(statuses)
            _logger.debug("status poll done: %s", {s["key"]: s["level"] for s in statuses})
            if self._sleep_interruptible(config.STATUS_POLL_INTERVAL):
                return
