# WatcherB — GitLab Issue Browser Specification

## Change History

| Rev | Date       | Description |
|-----|------------|-------------|
| 1   | 2026-04-10 | Initial draft |
| 2   | 2026-04-10 | Review integration (pascal C-1/C-2/M-1/M-2/m-1, dijkstra C-1~C-7, euler C-1~C-5) |
| 3   | 2026-04-10 | Review integration (pascal C-1/M-1/M-2/m-1, dijkstra C-1~C-6, euler C-1~C-4) |
| 4   | 2026-04-10 | Review integration (pascal C-4, euler C-1~C-3, dijkstra C-1~C-2) |
| 5   | 2026-04-10 | Review integration (euler C-1~C-2, dijkstra C-1) |

### Rev 2 Changes

- `[v2] pascal:C-1` §9.4, §9.5: Issue list pagination via Link header — fetch all pages before emitting signal
- `[v2] pascal:C-2` §9.6: Cache stores complete (all-pages-fetched) list only; key remains `(project, state_filter)`
- `[v2] pascal:M-1` §9.5: Issue notes pagination — same Link header approach as issue list
- `[v2] pascal:M-2 + dijkstra:C-7` §8.4: Markdown conversion reordered — code blocks extracted first via placeholders
- `[v2] pascal:m-1 + euler:C-5` §3, §9.5: `GITLAB_PROJECTS` uses full path (`namespace/project`); API URL-encodes entire path
- `[v2] dijkstra:C-1` §9.1: Clarified architecture difference from DiscordThread (sync HTTP + QWaitCondition, not asyncio)
- `[v2] dijkstra:C-2 + euler:C-4` §12: shutdown only on `_force_quit=True`; tray minimize keeps GitLabThread alive
- `[v2] dijkstra:C-3` §12: Added `terminate()` fallback after `wait(2000)` timeout (DiscordThread parity)
- `[v2] dijkstra:C-4 + euler:C-2` §9.2, §9.7: Request ID generation + stale response filtering in UI handlers
- `[v2] dijkstra:C-5` §4.3: Normal Mode restores QStackedWidget to index 0 explicitly
- `[v2] dijkstra:C-6` §7.2: QComboBox itemData stores API values (`opened`/`closed`/`all`)
- `[v2] euler:C-1` §9.2: error_occurred split into `list_error` and `detail_error` with structured parameters
- `[v2] euler:C-3` §7.5, §8.3: Detail pane resets on project/filter change; selection handling rules defined
- `[v2] pascal:m-2` **Deferred**: Request priority queue — FIFO is acceptable for initial release; optimization deferred to post-v1
- `[v2] dijkstra:C-8` **Deferred**: Fenced code block language specifier — finding was truncated; QTextBrowser lacks syntax highlighting, so language hint provides no rendering benefit

### Rev 3 Changes

- `[v3] pascal:C-1` §9.3, §9.4, §12: Shutdown calls `Session.close()` to interrupt blocking HTTP; `terminate()` removed; `wait(5000)` replaces `wait(2000)`
- `[v3] pascal:M-1` §9.4: Pagination error handling — try/except around each page request; on error, discard partial data and emit error signal
- `[v3] pascal:M-2` §8.4: Bold regex tightened to `[^*\x00]+?` to prevent crossing placeholders or spanning escaped HTML
- `[v3] pascal:m-1` §9.7: Stale responses no longer update cache — both UI and cache updates are skipped
- `[v3] euler:C-1 + euler:C-2` §3.2, §5.1, §5.3, §5.4: ProjectCard data model defined with `display_name` + `project_path`; Discord short name → full path resolution map; display name uniqueness validated at startup
- `[v3] euler:C-3` §7.5: Selection re-select limited to same-context reload only; project switch and filter change always clear selection
- `[v3] euler:C-4` §9.4: Shutdown during pagination raises `_ShutdownInterrupt`; process() catches it and skips signal/cache emission
- `[v3] dijkstra:C-1` §7.3: `reload_requested` and `filter_changed` split into separate signals
- `[v3] dijkstra:C-2` §3.1, §3.2, §9.5: Added `GITLAB_URL` config for API base URL (scheme + authority)
- `[v3] dijkstra:C-3` §5.1: Added pseudocode for `_state=None` handling that bypasses STATE_COLORS/STATE_PROGRESS
- `[v3] dijkstra:C-4` §4.3: Clarified "click different PJ name → Issues tab forced active"
- `[v3] dijkstra:C-5` §8.2: System notes filtered by GitLab API note object's `system` boolean field
- `[v3] dijkstra:C-6` §9.4, §14: Added `MAX_PAGES = 20` constant (2000 issues max per fetch)

### Rev 4 Changes

- `[v4] pascal:C-4` §9.4: Added explicit `next_url = None` before `break` in MAX_PAGES guard for defensive clarity
- `[v4] euler:C-1 + dijkstra:C-2` §5.3: Cards with `project_path=None` do NOT emit `clicked` signal and do NOT show selection highlight; eliminates Signal(str)+None type mismatch and undefined state transitions
- `[v4] euler:C-2 + dijkstra:C-1` §5.4: `_name_to_path` collision handling — conflicting short names are excluded from the map; Discord messages with colliding names create dynamic cards
- `[v4] euler:C-3` §9.2, §9.4, §7.4: `_fetch_all_pages` returns `(list, bool)` with `truncated` flag; `issues_loaded` signal gains `truncated` parameter; list widget shows "Showing first N issues" warning when truncated

### Rev 5 Changes

- `[v5] euler:C-1 + dijkstra:C-1` §9.6, §9.7: Cache type changed from `dict[..., list[dict]]` to `dict[..., tuple[list[dict], bool]]` storing `(issues, truncated)` pair; cache hit path passes `truncated` to `populate()` so truncation warning persists across re-visits
- `[v5] euler:C-2` §9.2, §9.4, §8.3: `detail_dict` gains `_notes_truncated: bool` key populated by `_process_detail_request`; `IssueDetailWidget` shows "Showing first N comments (list may be incomplete)" warning when notes are truncated

---

## 1. Overview

### 1.1 Problem Statement

gokrax manages 16 projects via GitLab Issues. Checking issue status requires opening dozens of browser tabs, which is cumbersome and disrupts workflow.

### 1.2 Goals

Integrate a GitLab Issue browsing panel into WatcherB so that issue lists and details can be viewed entirely within the existing GUI, without opening a browser.

### 1.3 Scope

- Add GitLab API integration for fetching issues and comments
- Add an Issue browsing mode activated by clicking a project name in the left panel
- Add a `GITLAB_PROJECTS` config to pre-populate the project panel
- Preserve the existing Pipeline view behavior exactly as-is

### 1.4 Out of Scope

- Issue creation, editing, or commenting from within WatcherB
- GitLab merge request browsing
- Real-time issue update notifications (polling or webhooks)

---

## 2. Architecture

### 2.1 Component Overview

```
┌─────────────────────────────────────────────────────┐
│ MainWindow                                          │
│ ┌──────────┐ ┌────────────────────────────────────┐ │
│ │ Project  │ │ Right Panel                        │ │
│ │ Panel    │ │ ┌────────────────────────────────┐ │ │
│ │          │ │ │ QTabBar (hidden in normal mode) │ │ │
│ │ [click]──┼─┼─│ [Pipeline] [Issues]             │ │ │
│ │          │ │ ├────────────────────────────────┤ │ │
│ │          │ │ │ QStackedWidget                 │ │ │
│ │          │ │ │   idx 0: MessageLog            │ │ │
│ │          │ │ │   idx 1: Issue Splitter        │ │ │
│ │          │ │ │     ┌──────────┬──────────┐    │ │ │
│ │          │ │ │     │ IssueList│ IssueDtl │    │ │ │
│ │          │ │ │     └──────────┴──────────┘    │ │ │
│ │          │ │ └────────────────────────────────┘ │ │
│ └──────────┘ └────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
         │
         │ fetch_issues / fetch_detail
         ▼
   GitLabThread (QThread, persistent)
         │
         ▼
   GitLab API v4 (requests)
```

### 2.2 Directory Structure

New code is placed under `issue_browser/` to separate concerns from the existing pipeline monitoring code.

```
WatcherB/
├── watcher.py              # Modified: right panel restructure, mode switching
├── widgets.py              # Modified: ProjectCard click, ProjectPanel pre-population
├── config.py               # Modified: new config keys
├── discord_client.py       # Unchanged
├── message_parser.py       # Unchanged
├── issue_browser/          # NEW: all issue browsing code
│   ├── __init__.py
│   ├── gitlab_client.py    # GitLabThread (QThread API client)
│   ├── widgets.py          # IssueListWidget, IssueDetailWidget
│   └── markdown.py         # Minimal Markdown-to-HTML converter
└── .env                    # Modified: new entries
```

### 2.3 Modified Files

| File | Changes |
|------|---------|
| `config.py` | `GITLAB_URL`, `GITLAB_TOKEN`, `GITLAB_PROJECTS`, `ISSUE_LIST_WIDTH` |
| `widgets.py` | ProjectCard data model (`display_name` + `project_path`), click + selection, ProjectPanel pre-population + name resolution map + click signal |
| `watcher.py` | Right panel restructure (QTabBar + QStackedWidget), mode switching, GitLab wiring, stale response filtering, QSS |
| `.env` | `GITLAB_URL`, `GITLAB_TOKEN`, `GITLAB_PROJECTS` entries |
| `requirements.txt` | `requests>=2.28` |

---

## 3. Configuration

### 3.1 New .env Entries

<!-- [v3] dijkstra:C-2: added GITLAB_URL for API base -->

| Key | Required | Default | Description |
|-----|----------|---------|-------------|
| `GITLAB_URL` | No | `"https://gitlab.com"` | GitLab instance URL (scheme + authority). Used as the API base URL. For self-hosted instances: e.g. `https://gitlab.mycompany.com` |
| `GITLAB_TOKEN` | No | `""` | GitLab personal access token (for private repos). Without it, only public repos are accessible and rate limits are stricter (10 req/min) |
| `GITLAB_PROJECTS` | No | `""` | Comma-separated list of full project paths to always show in the left panel (e.g. `atakalive/gokrax,atakalive/WatcherB,atakalive/TrajOpt`). Each entry is `namespace/project` or `group/subgroup/project` for subgroups |

### 3.2 New config.py Constants

<!-- [v3] dijkstra:C-2: added GITLAB_URL -->
<!-- [v3] euler:C-1 + euler:C-2: display name uniqueness constraint -->

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `GITLAB_URL` | `str` | `"https://gitlab.com"` | Loaded from .env. Trailing slash stripped |
| `GITLAB_TOKEN` | `str` | `""` | Loaded from .env |
| `GITLAB_PROJECTS` | `list[str]` | `[]` | Parsed from comma-separated .env value. Each element is a full project path (e.g. `atakalive/gokrax`) |
| `ISSUE_LIST_WIDTH` | `int` | `280` | Width of the issue list pane in pixels |

The display name for each project in the left panel is the **last path segment** (e.g. `atakalive/gokrax` → `gokrax`). The full path is used for API requests, caching, and all internal identification.

**Startup validation**: If two entries in `GITLAB_PROJECTS` share the same display name (last segment), the application logs a warning and uses the **full path** as display name for both conflicting entries (e.g. `group1/foo` and `group2/foo` → displayed as `group1/foo` and `group2/foo`). This prevents ambiguity in the UI while avoiding a fatal startup error.

---

## 4. UI Modes

### 4.1 Normal Mode (default)

Identical to the current WatcherB behavior:

- Left panel: ProjectPanel (project cards with state, progress, issues)
- Right panel: MessageLog only
- No tab bar visible

### 4.2 Issue Mode

Activated by clicking a project name in the left panel:

- Tab bar appears at top of right panel: **[Pipeline]** | **[Issues]**
- Issues tab is active initially
- Selected project is indicated with a left accent border on its card

### 4.3 State Transitions

<!-- [v2] dijkstra:C-5: Normal Mode explicitly resets stack to index 0 -->
<!-- [v3] dijkstra:C-4: clarified PJ switch forces Issues tab -->

```
Normal Mode
    │
    │ click PJ name (project_path is not None)
    ▼
Issue Mode (Issues tab active)
    │
    ├── click [Pipeline] tab → show MessageLog (tab bar stays)
    ├── click [Issues] tab → show Issue pane
    ├── click same PJ name → Normal Mode (tab bar hides, stack switches to index 0)
    ├── press Esc → Normal Mode (tab bar hides, stack switches to index 0)
    └── click different PJ name → switch to that PJ's issues (Issues tab forced active)
```

When transitioning to Normal Mode, `_right_stack.setCurrentIndex(0)` is called **before** hiding the tab bar, ensuring MessageLog is always the visible widget in Normal Mode.

When switching to a different project (including from Pipeline tab), the Issues tab is **forced active** and the issue list is fetched for the new project.

<!-- [v4] euler:C-1 + dijkstra:C-2: clicking a card with project_path=None does not enter Issue Mode -->

Cards with `project_path = None` (dynamic-only, no GitLab API target) do **not** trigger mode transitions. Clicks on such cards are no-ops.

---

## 5. Left Panel Changes

### 5.1 Pre-population

On startup, create ProjectCards for all entries in `GITLAB_PROJECTS`, even if no Discord messages have been received for them.

<!-- [v3] dijkstra:C-3: pseudocode for _state=None handling -->

Pre-populated cards without pipeline state use a distinct initial display:
- `_state` is set to `None` (not `"IDLE"`)
- When `_state is None`, the card **bypasses** `STATE_COLORS` and `STATE_PROGRESS` lookups entirely:

```python
# [v3] dijkstra:C-3: None state bypasses STATE_COLORS/STATE_PROGRESS
if state is None:
    self._state_label.setText("─")
    self._state_label.setStyleSheet(f"color: {COLORS['subtext']}")
    self._progress_bar.setValue(0)
    self._update_time_label.setText("")
else:
    # existing logic using STATE_COLORS[state] and STATE_PROGRESS[state]
    ...
```

- When a Discord message later arrives for this project, `update_state()` overwrites `_state` with a valid string key, and normal STATE_COLORS/STATE_PROGRESS logic resumes

### 5.2 Dynamic Addition

Projects not listed in `GITLAB_PROJECTS` still appear dynamically when Discord messages arrive (existing behavior, unchanged). Dynamically added cards have `project_path = None` (no GitLab API access) and `display_name` set to the Discord `[PJ]` name.

### 5.3 Click Behavior

<!-- [v4] euler:C-1 + dijkstra:C-2: cards with project_path=None do not emit clicked -->

- `ProjectCard` emits a `clicked(str)` signal on left mouse button press **only if `project_path` is not `None`**, passing `project_path` (full path)
- Cards with `project_path = None` do **not** emit `clicked` and do **not** show selection highlight. They are display-only in the context of issue browsing
- Cursor changes to `PointingHandCursor` on hover (only for cards with `project_path`)
- `ProjectPanel` relays clicks via `project_clicked(str)` signal
- Selected card shows a 3px left border in accent color

This design eliminates the `Signal(str)` + `None` type mismatch: the signal parameter is always a valid `str`. No None-handling logic is needed in `MainWindow`.

### 5.4 Project Name Resolution

<!-- [v3] euler:C-1 + euler:C-2: ProjectCard data model and Discord name resolution -->
<!-- [v4] euler:C-2 + dijkstra:C-1: collision-safe _name_to_path -->

**ProjectCard data model**:

| Field | Type | Description |
|-------|------|-------------|
| `project_path` | `str \| None` | Full GitLab path (e.g. `atakalive/gokrax`). `None` for cards created only by Discord messages |
| `display_name` | `str` | Shown in UI. Last segment of `project_path`, or full path if display name conflicts (§3.2). For dynamic cards: Discord `[PJ]` name |

**Discord short name → full path resolution**:

`ProjectPanel` maintains a `_name_to_path: dict[str, str]` lookup, built at startup from `GITLAB_PROJECTS`:

```python
# [v4] euler:C-2 + dijkstra:C-1: collision-safe name resolution map
# Conflicting short names are excluded — neither side gets auto-resolved
_name_to_path = {}
_seen = {}
for path in GITLAB_PROJECTS:
    short_name = path.rsplit("/", 1)[-1]  # e.g. "gokrax"
    if short_name in _seen:
        # Collision detected: remove the first entry too
        _name_to_path.pop(short_name, None)
    else:
        _seen[short_name] = path
        _name_to_path[short_name] = path
```

When a Discord message arrives with `[PJ]` name (e.g. `gokrax`):
1. Look up `_name_to_path.get("gokrax")` → `"atakalive/gokrax"`
2. If found, update the **existing** pre-populated card (matched by `project_path`)
3. If not found (including colliding short names), create a new dynamic card with `project_path = None` (§5.2)

For colliding short names (e.g. `group1/foo` and `group2/foo`): neither is auto-resolved from Discord `[foo]` messages. Both pre-populated cards exist with their own `project_path`, but Discord updates for `[foo]` create a separate dynamic card. This matches §3.2's display name conflict handling and avoids silent misdirection.

---

## 6. Right Panel Structure

### 6.1 Widget Hierarchy

```python
right_container (QWidget)
└── QVBoxLayout
    ├── _tab_bar (QTabBar)           # hidden in normal mode
    │     tab 0: "Pipeline"
    │     tab 1: "Issues"
    ├── _right_stack (QStackedWidget)
    │     index 0: MessageLog         # always alive, accumulates messages
    │     index 1: _issue_splitter (QSplitter, horizontal)
    │               ├── IssueListWidget (left, ISSUE_LIST_WIDTH)
    │               └── IssueDetailWidget (right, fills remaining)
    └── _send_input (QLineEdit)      # only if SEND_ENABLED
```

### 6.2 MessageLog Preservation

The `MessageLog` instance is never destroyed or recreated. It stays at index 0 of the `QStackedWidget` and continues to receive Discord messages regardless of which mode/tab is active.

### 6.3 QTabBar Initialization

`QTabBar.currentChanged` is connected **after** all tabs are added and the tab bar is hidden. In `_on_tab_changed`, a guard checks `self._selected_project is not None` to ignore spurious signals during initialization.

---

## 7. Issue List Widget

Located at `issue_browser/widgets.py`.

### 7.1 Layout

```
┌──────────────────────────────────┐
│ [Open ▼]              [Reload]   │
├──────────────────────────────────┤
│ #301  Fix review hang  [bug]     │
│ #299  Add timeout config         │
│ #295  Refactor pipeline [enhance]│
│ #290  Queue batch support        │
│                                  │
│                                  │
└──────────────────────────────────┘
```

### 7.2 Components

<!-- [v2] dijkstra:C-6: QComboBox itemData stores API values -->

| Component | Type | Description |
|-----------|------|-------------|
| Filter combo | `QComboBox` | Display labels: "Open", "Closed", "All". API values stored via `addItem(label, userData)`: `"opened"`, `"closed"`, `"all"`. Current API value retrieved via `currentData()`. Default: "Open" (`"opened"`) |
| Reload button | `QPushButton` | Invalidates cache and refetches |
| Issue list | `QListWidget` | Each item shows `#iid  title  [labels]`. Selected item emits `issue_selected(int)` |

Each list item displays: `#iid  title` followed by labels in brackets (e.g. `[bug]`, `[enhancement, watchdog]`). Labels are shown in subtext color.

### 7.3 Signals

<!-- [v3] dijkstra:C-1: split reload and filter change into separate signals -->

| Signal | Type | Trigger |
|--------|------|---------|
| `issue_selected` | `Signal(int)` | User clicks an issue in the list |
| `reload_requested` | `Signal()` | Reload button clicked |
| `filter_changed` | `Signal(str)` | Filter combo `currentIndexChanged`. Emits the new API value (e.g. `"opened"`) |

`MainWindow` connects these separately:
- `reload_requested` → invalidate all cache entries for the current project, then fetch
- `filter_changed` → fetch with the new filter; other filters' caches are retained

### 7.4 Loading and Empty States

<!-- [v4] euler:C-3: added Truncated state -->

| State | Display |
|-------|---------|
| Loading | Single list item: "Loading..." (disabled, non-selectable) |
| Empty (no issues) | Single list item: "No issues found" (disabled, non-selectable) |
| Error | Single list item: "Error: {message}" (disabled, non-selectable, red text) |
| Truncated | After populating the list, append a final disabled item: "Showing first {N} issues (list may be incomplete)" in `subtext` color. Displayed whenever the `truncated` flag is `True` — both on fresh fetch via `issues_loaded` and on cache hit (§9.7) |

### 7.5 Context Change Behavior

<!-- [v2] euler:C-3: detail pane reset and selection handling on context change -->
<!-- [v3] euler:C-3: selection re-select limited to reload only -->

When the **context** changes (project switch, filter change, or reload), the following rules apply:

| Trigger | Issue list action | Detail pane action | Selection behavior |
|---------|-------------------|--------------------|--------------------|
| Project switch | Clear and show Loading state | Reset to blank ("No issue selected") | Clear selection unconditionally |
| Filter change | Clear and show Loading state | Reset to blank ("No issue selected") | Clear selection unconditionally |
| Reload (same project + same filter) | Clear and show Loading state | Reset to blank ("No issue selected") | After issues loaded: if previously selected iid exists in new list, re-select it and fetch detail. Otherwise, clear selection |

The detail pane is **always** reset when context changes, preventing stale data from a different project/filter from persisting. Selection re-select is **only** permitted on reload within the same context, never on project switch or filter change. This prevents cross-project iid collision (GitLab iid is per-project).

---

## 8. Issue Detail Widget

Located at `issue_browser/widgets.py`.

### 8.1 Layout

```
┌─────────────────────────────────────────┐
│ #301 Fix review hang                    │
│                                         │
│ OPEN        bug, watchdog               │
│                                         │
│ watchdog fails to detect review         │
│ completion when the reviewer agent      │
│ disconnects mid-review...               │
│                                         │
│ --- Comments (3) ---                    │
│                                         │
│ kaneko  2026-04-09 14:32                │
│ Implemented timeout fallback in...      │
│                                         │
│ dijkstra  2026-04-09 15:10              │
│ P1: The timeout value should be...      │
│                                         │
└─────────────────────────────────────────┘
```

### 8.2 Rendering

- Based on `QTextBrowser` (same as MessageLog)
- Issue body rendered with minimal Markdown-to-HTML conversion (§8.4)
- System notes are hidden: filtered by the `system` boolean field on each GitLab note object (`note["system"] is True` → exclude)
- Colors follow Catppuccin Mocha theme (§10)

<!-- [v3] dijkstra:C-5: explicit system note filtering method -->

### 8.3 Loading and Empty States

<!-- [v5] euler:C-2: added Notes truncated state -->

| State | Display |
|-------|---------|
| No issue selected | Empty (blank widget) |
| Loading detail | "Loading..." in subtext color, centered |
| Error | "Error: {message}" in red |
| Notes truncated | After rendering all comments, append a separator and "Showing first {N} comments (list may be incomplete)" in `subtext` color. Displayed when `detail_dict["_notes_truncated"]` is `True` |

<!-- [v2] euler:C-3: detail pane resets to blank on context change (project/filter/reload) — see §7.5 -->

### 8.4 Markdown Conversion

<!-- [v2] pascal:M-2 + dijkstra:C-7: reordered conversion to prevent double-conversion inside code blocks -->
<!-- [v3] pascal:M-2: tightened bold regex -->

Located at `issue_browser/markdown.py`. A single function `md_to_html(text: str) -> str`.

**Conversion order** (critical — code blocks must be extracted before inline transforms):

```python
def md_to_html(text: str) -> str:
    # [v2] pascal:M-2 + dijkstra:C-7: extract code blocks first to prevent
    # double-conversion of content inside them

    # 1. html.escape() the entire input
    text = html.escape(text)

    # 2. Extract fenced code blocks (```...```) → replace with placeholders
    #    Content inside is already escaped; wrap in <pre><code>...</code></pre>
    #    Store in placeholder map: {placeholder_key: html_fragment}
    placeholders = {}
    text = _extract_fenced_code_blocks(text, placeholders)

    # 3. Extract inline code (`...`) → replace with placeholders
    #    Content inside is already escaped; wrap in <code>...</code>
    text = _extract_inline_code(text, placeholders)

    # 4. **bold** → <b>bold</b>
    # [v3] pascal:M-2: tightened regex — disallow * and placeholder chars inside bold
    text = re.sub(r'\*\*([^*\x00]+?)\*\*', r'<b>\1</b>', text)

    # 5. Newlines → <br>  (but NOT inside <pre> blocks — already handled by placeholders)
    text = text.replace('\n', '<br>\n')

    # 6. Restore all placeholders
    for key, fragment in placeholders.items():
        text = text.replace(key, fragment)

    return text
```

Placeholder keys use a format unlikely to appear in user content (e.g. `\x00CODE_BLOCK_0\x00`).

**Security property**: Since `html.escape()` runs first on the entire input, all user-supplied `<`, `>`, `&`, `"` are neutralized before any HTML tags are generated. The `<b>`, `<code>`, `<pre>` tags are introduced only by the converter itself, never from user input. The bold regex `[^*\x00]+?` ensures bold spans cannot cross placeholder boundaries or contain nested `*` sequences.

---

## 9. GitLab API Client

Located at `issue_browser/gitlab_client.py`.

### 9.1 Architecture

<!-- [v2] dijkstra:C-1: clarified architecture difference from DiscordThread -->

`GitLabThread` extends `QThread`, similar to the existing `DiscordThread` in that both are persistent `QThread` subclasses. However, the internal architecture differs:

- **DiscordThread**: Runs an asyncio event loop inside the thread to drive `discord.Client`'s async API
- **GitLabThread**: Uses `QWaitCondition` + `QMutex` for request queuing, and synchronous `requests` library for HTTP calls. No asyncio involved

### 9.2 Signals

<!-- [v2] euler:C-1: split error_occurred into list_error/detail_error with structured parameters -->
<!-- [v2] dijkstra:C-4 + euler:C-2: added request_id to all signals for stale response filtering -->
<!-- [v4] euler:C-3: issues_loaded gains truncated flag -->
<!-- [v5] euler:C-2: detail_dict includes _notes_truncated -->

| Signal | Parameters | Description |
|--------|-----------|-------------|
| `issues_loaded` | `(str, str, int, bool, list)` | `(project, state_filter, request_id, truncated, issues)` — complete issue list (all pages, or truncated at MAX_PAGES) |
| `issue_detail_loaded` | `(str, int, int, dict)` | `(project, iid, request_id, detail_dict)` — detail dict includes `_notes` key with comments and `_notes_truncated` key (`bool`) indicating whether notes were truncated at MAX_PAGES |
| `list_error` | `(str, str, int, str)` | `(project, state_filter, request_id, message)` — error fetching issue list |
| `detail_error` | `(str, int, int, str)` | `(project, iid, request_id, message)` — error fetching issue detail |

### 9.3 Methods

<!-- [v3] pascal:C-1: added close_session to shutdown -->

| Method | Parameters | Returns | Description |
|--------|-----------|---------|-------------|
| `fetch_issues` | `project: str, state: str` | `int` | Queue issue list fetch. `state` is `"opened"`, `"closed"`, or `"all"`. Returns `request_id` |
| `fetch_issue_detail` | `project: str, iid: int` | `int` | Queue single issue + comments fetch. Returns `request_id` |
| `shutdown` | — | — | Set `_shutdown` flag, call `_session.close()` to interrupt in-flight HTTP, wake condition |

### 9.4 Request Processing

<!-- [v2] pascal:C-1: pagination — fetch all pages before emitting signal -->
<!-- [v3] pascal:C-1: Session.close() interrupts blocking HTTP -->
<!-- [v3] pascal:M-1: pagination error handling -->
<!-- [v3] euler:C-4: shutdown during pagination raises _ShutdownInterrupt -->
<!-- [v3] dijkstra:C-6: MAX_PAGES limit -->
<!-- [v4] pascal:C-4: explicit next_url=None before break -->
<!-- [v4] euler:C-3: _fetch_all_pages returns (list, bool) truncated flag -->

`GitLabThread` runs as a **persistent thread** (does not exit after each batch):

```
run():
    loop:
        mutex.lock()
        while _pending_requests is empty and not _shutdown:
            _condition.wait(mutex)
        if _shutdown:
            mutex.unlock()
            return
        request = _pending_requests.pop(0)
        mutex.unlock()
        try:
            process(request)
            # [v2] pascal:C-1: process() fetches ALL pages before emitting signal
        except _ShutdownInterrupt:
            # [v3] euler:C-4: shutdown during fetch — discard partial data, skip signal
            return
```

- `fetch_issues` / `fetch_issue_detail` append to `_pending_requests` under `QMutex`, then call `_condition.wakeOne()`
- `shutdown()` sets `_shutdown = True` under mutex, calls `_session.close()` then `_condition.wakeOne()`
- Thread exits only on shutdown. No race between queue check and thread exit

**Shutdown interruption**:

```python
def shutdown(self):
    """
    # [v3] pascal:C-1: close session to interrupt blocking HTTP requests
    """
    self._mutex.lock()
    self._shutdown = True
    self._session.close()   # interrupts any in-flight requests.get() with ConnectionError
    self._condition.wakeOne()
    self._mutex.unlock()
```

When `_session.close()` is called while a `self._session.get(...)` is in progress, the `requests` library raises a `ConnectionError`. This is caught by the pagination error handler or the process() function, which checks `_shutdown` and either raises `_ShutdownInterrupt` or returns early.

**Pagination** (applies to issue list and issue notes):

```python
MAX_PAGES = 20  # [v3] dijkstra:C-6: upper bound to prevent runaway fetches (20 * 100 = 2000 items)

class _ShutdownInterrupt(Exception):
    """Raised when shutdown is detected during fetch."""
    pass

def _fetch_all_pages(self, url: str, params: dict) -> tuple[list[dict], bool]:
    """
    # [v2] pascal:C-1: fetch all pages using Link header pagination
    # [v3] pascal:M-1: error handling per page
    # [v3] euler:C-4: raise _ShutdownInterrupt on shutdown
    # [v3] dijkstra:C-6: MAX_PAGES limit
    # [v4] euler:C-3: returns (items, truncated) tuple
    Fetches all pages from a paginated GitLab API endpoint.
    Returns (items, truncated) where truncated is True if MAX_PAGES was reached
    and more pages were available.
    Raises _ShutdownInterrupt if shutdown is detected.
    Raises requests.HTTPError on API error (partial data is discarded).
    """
    all_items = []
    next_url = url
    current_params = dict(params)
    page_count = 0
    truncated = False

    while next_url is not None:
        if self._shutdown:
            raise _ShutdownInterrupt()

        if page_count >= MAX_PAGES:
            # [v4] pascal:C-4: explicit next_url=None for defensive clarity
            next_url = None
            truncated = True  # [v4] euler:C-3: signal that results were cut short
            break

        try:
            resp = self._session.get(next_url, params=current_params, timeout=5)
            resp.raise_for_status()
        except Exception:
            if self._shutdown:
                raise _ShutdownInterrupt()
            raise  # [v3] pascal:M-1: re-raise to caller; partial data discarded

        all_items.extend(resp.json())
        page_count += 1

        # Parse Link header for next page
        next_url = None
        current_params = {}  # params are embedded in the Link URL
        link_header = resp.headers.get("Link", "")
        for part in link_header.split(","):
            if 'rel="next"' in part:
                # Extract URL between < and >
                next_url = part.split("<")[1].split(">")[0]
                break

    return all_items, truncated
```

**Error handling in process()**:

```python
def _process_list_request(self, project, state, request_id):
    try:
        issues, truncated = self._fetch_all_pages(url, params)
        # [v4] euler:C-3: pass truncated flag in signal
        self.issues_loaded.emit(project, state, request_id, truncated, issues)
    except _ShutdownInterrupt:
        raise  # propagate to run() loop
    except Exception as e:
        # [v3] pascal:M-1: on error, partial data is discarded; emit error
        self.list_error.emit(project, state, request_id, str(e))

def _process_detail_request(self, project, iid, request_id):
    try:
        # Fetch issue detail (single resource, no pagination)
        resp = self._session.get(detail_url, params={}, timeout=5)
        resp.raise_for_status()
        detail = resp.json()

        # Fetch notes with pagination
        notes, notes_truncated = self._fetch_all_pages(notes_url, notes_params)
        # [v5] euler:C-2: include notes_truncated in detail_dict
        detail["_notes"] = [n for n in notes if not n.get("system", False)]
        detail["_notes_truncated"] = notes_truncated

        self.issue_detail_loaded.emit(project, iid, request_id, detail)
    except _ShutdownInterrupt:
        raise
    except Exception as e:
        self.detail_error.emit(project, iid, request_id, str(e))
```

### 9.5 API Endpoints

<!-- [v2] pascal:m-1 + euler:C-5: project path is URL-encoded to support subgroups -->
<!-- [v2] pascal:C-1 + pascal:M-1: per_page set to 100; all pages fetched via _fetch_all_pages -->
<!-- [v3] dijkstra:C-2: API base URL from GITLAB_URL config -->

| Action | Endpoint | Parameters | Pagination |
|--------|----------|------------|------------|
| List issues | `GET {GITLAB_URL}/api/v4/projects/{encoded_path}/issues` | `state`, `per_page=100`, `order_by=updated_at` | Yes — all pages fetched (up to MAX_PAGES) |
| Issue detail | `GET {GITLAB_URL}/api/v4/projects/{encoded_path}/issues/{iid}` | — | No (single resource) |
| Issue notes | `GET {GITLAB_URL}/api/v4/projects/{encoded_path}/issues/{iid}/notes` | `order_by=created_at`, `sort=asc`, `per_page=100` | Yes — all pages fetched (up to MAX_PAGES) |

**API base URL**: `GITLAB_URL` from config (§3.2) provides the scheme + authority (e.g. `https://gitlab.com`). All API endpoints are constructed as `{GITLAB_URL}/api/v4/...`.

**Project path encoding**: The full project path from `GITLAB_PROJECTS` (e.g. `atakalive/gokrax` or `group/subgroup/project`) is URL-encoded using `urllib.parse.quote(path, safe="")`, producing `atakalive%2Fgokrax` or `group%2Fsubgroup%2Fproject`. This is used as `{encoded_path}` in all API URLs.

- `PRIVATE-TOKEN` header is included if `GITLAB_TOKEN` is set
- Request timeout: 5 seconds per individual HTTP request
- HTTP errors are caught per-request and emitted via `list_error` / `detail_error`

### 9.6 Caching

<!-- [v2] pascal:C-2: cache stores complete (all-pages) list only -->
<!-- [v3] dijkstra:C-1: reload vs filter change distinction -->
<!-- [v5] euler:C-1 + dijkstra:C-1: cache stores (issues, truncated) tuple -->

- `MainWindow` holds an in-memory cache: `dict[tuple[str, str], tuple[list[dict], bool]]` mapping `(project, state_filter)` to `(issues, truncated)`. The `truncated` flag indicates whether the list was cut short at MAX_PAGES
- **Cache stores only complete fetches**: `GitLabThread` fetches all pages (up to MAX_PAGES) before emitting `issues_loaded`. The cache entry stores both the issue list and the truncation status, ensuring the truncation warning is preserved on cache hit
- Cache is used on repeated project clicks with the same filter (avoids redundant API calls)
- **Reload** (`reload_requested` signal): invalidates all cache entries for the current project (all filter variants), then fetches
- **Filter change** (`filter_changed` signal): fetches with the new filter; cached results for other filters are retained
- No TTL-based expiration (manual reload only)

### 9.7 Stale Response Filtering

<!-- [v2] dijkstra:C-4 + euler:C-2: request_id based filtering -->
<!-- [v3] pascal:m-1: stale responses skip cache update too -->
<!-- [v4] euler:C-3: truncated flag in _on_issues_loaded -->
<!-- [v5] euler:C-1 + dijkstra:C-1: cache stores (issues, truncated); cache hit preserves warning -->

`MainWindow` maintains `_current_list_request_id: int` and `_current_detail_request_id: int`, updated each time a new fetch is initiated.

```python
def _on_project_clicked(self, project: str):
    # ... mode switching logic ...
    # [v5] euler:C-1 + dijkstra:C-1: check cache for (issues, truncated) tuple
    cached = self._issue_cache.get((project, state))
    if cached is not None:
        issues, truncated = cached
        self._issue_list.populate(issues, truncated=truncated)
        return
    rid = self._gitlab_thread.fetch_issues(project, state)
    self._current_list_request_id = rid
    # [v2] euler:C-3: reset detail pane on project switch
    self._issue_detail.show_blank()
    self._current_detail_request_id = -1

def _on_issues_loaded(self, project: str, state: str, request_id: int, truncated: bool, issues: list):
    # [v2] dijkstra:C-4 + euler:C-2: discard stale responses
    if request_id != self._current_list_request_id:
        # [v3] pascal:m-1: stale response — discard entirely (no cache, no UI)
        return
    # [v5] euler:C-1 + dijkstra:C-1: store (issues, truncated) in cache
    self._issue_cache[(project, state)] = (issues, truncated)
    # [v4] euler:C-3: pass truncated flag to widget
    self._issue_list.populate(issues, truncated=truncated)

def _on_issue_detail_loaded(self, project: str, iid: int, request_id: int, detail: dict):
    if request_id != self._current_detail_request_id:
        return  # stale — discard
    # [v5] euler:C-2: show_detail renders _notes_truncated warning if present
    self._issue_detail.show_detail(detail)

def _on_list_error(self, project: str, state: str, request_id: int, message: str):
    # [v2] euler:C-1: only show error if it matches the current request
    if request_id != self._current_list_request_id:
        return
    self._issue_list.show_error(message)

def _on_detail_error(self, project: str, iid: int, request_id: int, message: str):
    if request_id != self._current_detail_request_id:
        return
    self._issue_detail.show_error(message)
```

**Request ID generation**: `GitLabThread` holds an `_next_request_id: int` counter (starts at 1), incremented atomically under the existing `QMutex` when a request is enqueued. The ID is returned to the caller and included in the corresponding signal emission.

---

## 10. Styling

### 10.1 New QSS Rules

All new widgets use the existing Catppuccin Mocha color scheme from `config.COLORS`.

| Widget | Background | Text | Accent |
|--------|-----------|------|--------|
| QTabBar | `surface` | `subtext` (inactive), `text` (active) | `accent` underline on selected tab |
| QListWidget | `bg` | `text` | `accent` for selected item |
| QPushButton | `surface` | `text` | — |
| QComboBox | `surface` | `text` | `subtext` border |
| IssueDetailWidget | `bg` | `text` | `accent` for author names |

### 10.2 ProjectCard Selection Style

- Selected card: 3px left border in `accent` color
- Unselected card: no left border (transparent)
- QWidget QSS supports `border-left` (unlike QTextBrowser)

---

## 11. Keyboard Shortcuts

| Key | Action | Context |
|-----|--------|---------|
| `Esc` | Exit Issue Mode → Normal Mode | Issue Mode only (no-op in Normal Mode) |
| `Ctrl+=` / `Ctrl++` | Zoom in | Existing, unchanged |
| `Ctrl+-` | Zoom out | Existing, unchanged |
| `Ctrl+0` | Reset zoom | Existing, unchanged |

---

## 12. Shutdown

<!-- [v2] dijkstra:C-2 + euler:C-4: shutdown only on _force_quit=True -->
<!-- [v3] pascal:C-1: Session.close() replaces terminate(); wait extended to 5s -->

`GitLabThread` shutdown is tied to the application's **actual exit path** only:

```python
def closeEvent(self, event):
    if self._force_quit:
        # [v2] dijkstra:C-2 + euler:C-4: only shutdown on actual app exit
        # [v3] pascal:C-1: shutdown() calls _session.close() to interrupt HTTP
        self._gitlab_thread.shutdown()
        self._gitlab_thread.wait(5000)
        # ... existing DiscordThread shutdown ...
        event.accept()
    else:
        # Tray minimize — GitLabThread keeps running
        self.hide()
        event.ignore()
```

- `_force_quit=False` (window close → tray): `GitLabThread` is **not** stopped. Issue browsing remains functional when the window is re-shown
- `_force_quit=True` (Exit menu / system shutdown): `GitLabThread.shutdown()` is called, which sets `_shutdown=True` **and** calls `_session.close()`. The `close()` interrupts any in-flight `requests.get()` by raising `ConnectionError`, allowing the thread to exit promptly. `wait(5000)` provides ample time for the thread to clean up
- **No `terminate()` call**: `_session.close()` provides a cooperative interruption mechanism, making the dangerous `terminate()` unnecessary. The thread always exits via its normal code path

---

## 13. Dependencies

### 13.1 requirements.txt Changes

Add:
```
requests>=2.28
```

`requests` is not a dependency of `discord.py` (which uses `aiohttp`). It must be added explicitly.

---

## 14. Limitations

- Markdown rendering is minimal (bold, inline code, code blocks, line breaks only). Tables, images, and complex markdown will not render correctly in `QTextBrowser`
- Fenced code block language specifiers (e.g. ` ```python `) are accepted but ignored — no syntax highlighting in `QTextBrowser`
- No real-time issue updates. Users must click Reload to see changes
- Without `GITLAB_TOKEN`, only public repositories are accessible and API rate limit is 10 requests/minute
- System notes (label changes, milestone assignments, etc.) are hidden in the detail view
- Individual issue details (body + comments) are not cached; each click refetches from the API
- Request queue is FIFO; no priority ordering between list and detail requests
- Issue list and notes are fetched up to MAX_PAGES pages (2000 items at `per_page=100`). Projects exceeding this limit will show a truncation warning in the list widget; issues with truncated notes will show a similar warning in the detail pane
- Pagination errors discard all partial data and report the error. No retry or partial-result display
- Cards created dynamically by Discord messages (not in `GITLAB_PROJECTS`) cannot browse GitLab issues — they are display-only for pipeline state
