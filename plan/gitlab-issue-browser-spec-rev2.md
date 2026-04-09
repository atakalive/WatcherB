# WatcherB — GitLab Issue Browser Specification

## Change History

| Rev | Date       | Description |
|-----|------------|-------------|
| 1   | 2026-04-10 | Initial draft |
| 2   | 2026-04-10 | Review integration (pascal C-1/C-2/M-1/M-2/m-1, dijkstra C-1~C-7, euler C-1~C-5) |

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
| `config.py` | `GITLAB_TOKEN`, `GITLAB_PROJECTS`, `ISSUE_LIST_WIDTH` |
| `widgets.py` | ProjectCard click + selection, ProjectPanel pre-population + click signal |
| `watcher.py` | Right panel restructure (QTabBar + QStackedWidget), mode switching, GitLab wiring, stale response filtering, QSS |
| `.env` | `GITLAB_TOKEN`, `GITLAB_PROJECTS` entries |
| `requirements.txt` | `requests>=2.28` |

---

## 3. Configuration

### 3.1 New .env Entries

| Key | Required | Default | Description |
|-----|----------|---------|-------------|
| `GITLAB_TOKEN` | No | `""` | GitLab personal access token (for private repos). Without it, only public repos are accessible and rate limits are stricter (10 req/min) |
| `GITLAB_PROJECTS` | No | `""` | Comma-separated list of full project paths to always show in the left panel (e.g. `atakalive/gokrax,atakalive/WatcherB,atakalive/TrajOpt`). Each entry is `namespace/project` or `group/subgroup/project` for subgroups |

<!-- [v2] pascal:m-1 + euler:C-5: GITLAB_PROJECTS now uses full path format -->

### 3.2 New config.py Constants

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `GITLAB_TOKEN` | `str` | `""` | Loaded from .env |
| `GITLAB_PROJECTS` | `list[str]` | `[]` | Parsed from comma-separated .env value. Each element is a full project path (e.g. `atakalive/gokrax`) |
| `ISSUE_LIST_WIDTH` | `int` | `280` | Width of the issue list pane in pixels |

<!-- [v2] pascal:m-1 + euler:C-5: display name for the left panel is the last segment of the path -->

The display name for each project in the left panel is the **last path segment** (e.g. `atakalive/gokrax` → `gokrax`). The full path is used only for API requests.

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

```
Normal Mode
    │
    │ click PJ name
    ▼
Issue Mode (Issues tab active)
    │
    ├── click [Pipeline] tab → show MessageLog (tab bar stays)
    ├── click [Issues] tab → show Issue pane
    ├── click same PJ name → Normal Mode (tab bar hides, stack switches to index 0)
    ├── press Esc → Normal Mode (tab bar hides, stack switches to index 0)
    └── click different PJ name → switch to that PJ's issues
```

When transitioning to Normal Mode, `_right_stack.setCurrentIndex(0)` is called **before** hiding the tab bar, ensuring MessageLog is always the visible widget in Normal Mode.

---

## 5. Left Panel Changes

### 5.1 Pre-population

On startup, create ProjectCards for all entries in `GITLAB_PROJECTS`, even if no Discord messages have been received for them.

Pre-populated cards without pipeline state use a distinct initial display:
- `_state` is set to `None` (not `"IDLE"`)
- State label shows `─` in subtext color
- Progress bar at 0%, no update time shown
- When a Discord message later arrives for this project, `update_state()` overwrites normally

### 5.2 Dynamic Addition

Projects not listed in `GITLAB_PROJECTS` still appear dynamically when Discord messages arrive (existing behavior, unchanged).

### 5.3 Click Behavior

- `ProjectCard` emits a `clicked(str)` signal on left mouse button press
- Cursor changes to `PointingHandCursor` on hover
- `ProjectPanel` relays clicks via `project_clicked(str)` signal
- Selected card shows a 3px left border in accent color

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

| Signal | Type | Trigger |
|--------|------|---------|
| `issue_selected` | `Signal(int)` | User clicks an issue in the list |
| `reload_requested` | `Signal()` | Reload button or filter change |

### 7.4 Loading and Empty States

| State | Display |
|-------|---------|
| Loading | Single list item: "Loading..." (disabled, non-selectable) |
| Empty (no issues) | Single list item: "No issues found" (disabled, non-selectable) |
| Error | Single list item: "Error: {message}" (disabled, non-selectable, red text) |

### 7.5 Context Change Behavior

<!-- [v2] euler:C-3: detail pane reset and selection handling on context change -->

When the **context** changes (project switch, filter change, or reload), the following rules apply:

| Trigger | Issue list action | Detail pane action |
|---------|-------------------|--------------------|
| Project switch | Clear and show Loading state | Reset to blank ("No issue selected") |
| Filter change | Clear and show Loading state | Reset to blank ("No issue selected") |
| Reload | Clear and show Loading state | Reset to blank ("No issue selected") |
| Issues loaded (response matches current context) | Populate list. If previously selected iid exists in new list, re-select it and fetch detail. Otherwise, clear selection | (follows from selection logic) |

The detail pane is **always** reset when context changes, preventing stale data from a different project/filter from persisting.

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
- System notes (label changes, assignments, etc.) are hidden
- Colors follow Catppuccin Mocha theme (§10)

### 8.3 Loading and Empty States

| State | Display |
|-------|---------|
| No issue selected | Empty (blank widget) |
| Loading detail | "Loading..." in subtext color, centered |
| Error | "Error: {message}" in red |

<!-- [v2] euler:C-3: detail pane resets to blank on context change (project/filter/reload) — see §7.5 -->

### 8.4 Markdown Conversion

<!-- [v2] pascal:M-2 + dijkstra:C-7: reordered conversion to prevent double-conversion inside code blocks -->

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

    # 4. **bold** → <b>bold</b>  (only applies to non-placeholder text)
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)

    # 5. Newlines → <br>  (but NOT inside <pre> blocks — already handled by placeholders)
    text = text.replace('\n', '<br>\n')

    # 6. Restore all placeholders
    for key, fragment in placeholders.items():
        text = text.replace(key, fragment)

    return text
```

Placeholder keys use a format unlikely to appear in user content (e.g. `\x00CODE_BLOCK_0\x00`).

**Security property**: Since `html.escape()` runs first on the entire input, all user-supplied `<`, `>`, `&`, `"` are neutralized before any HTML tags are generated. The `<b>`, `<code>`, `<pre>` tags are introduced only by the converter itself, never from user input.

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

| Signal | Parameters | Description |
|--------|-----------|-------------|
| `issues_loaded` | `(str, str, int, list)` | `(project, state_filter, request_id, issues)` — complete issue list (all pages) |
| `issue_detail_loaded` | `(str, int, int, dict)` | `(project, iid, request_id, detail_dict)` — detail dict includes `_notes` key with comments |
| `list_error` | `(str, str, int, str)` | `(project, state_filter, request_id, message)` — error fetching issue list |
| `detail_error` | `(str, int, int, str)` | `(project, iid, request_id, message)` — error fetching issue detail |

### 9.3 Methods

| Method | Parameters | Returns | Description |
|--------|-----------|---------|-------------|
| `fetch_issues` | `project: str, state: str` | `int` | Queue issue list fetch. `state` is `"opened"`, `"closed"`, or `"all"`. Returns `request_id` |
| `fetch_issue_detail` | `project: str, iid: int` | `int` | Queue single issue + comments fetch. Returns `request_id` |
| `shutdown` | — | — | Signal the thread to exit its run loop |

### 9.4 Request Processing

<!-- [v2] pascal:C-1: pagination — fetch all pages before emitting signal -->

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
        process(request)
        # [v2] pascal:C-1: process() fetches ALL pages before emitting signal
```

- `fetch_issues` / `fetch_issue_detail` append to `_pending_requests` under `QMutex`, then call `_condition.wakeOne()`
- `shutdown()` sets `_shutdown = True` under mutex, calls `_condition.wakeOne()`
- Thread exits only on shutdown. No race between queue check and thread exit

**Pagination** (applies to issue list and issue notes):

```python
def _fetch_all_pages(self, url: str, params: dict) -> list[dict]:
    """
    # [v2] pascal:C-1: fetch all pages using Link header pagination
    Fetches all pages from a paginated GitLab API endpoint.
    Returns the concatenated list of all items across all pages.
    """
    all_items = []
    next_url = url
    current_params = dict(params)

    while next_url is not None:
        if self._shutdown:
            return all_items  # early exit on shutdown

        resp = self._session.get(next_url, params=current_params, timeout=15)
        resp.raise_for_status()
        all_items.extend(resp.json())

        # Parse Link header for next page
        next_url = None
        current_params = {}  # params are embedded in the Link URL
        link_header = resp.headers.get("Link", "")
        for part in link_header.split(","):
            if 'rel="next"' in part:
                # Extract URL between < and >
                next_url = part.split("<")[1].split(">")[0]
                break

    return all_items
```

### 9.5 API Endpoints

<!-- [v2] pascal:m-1 + euler:C-5: project path is URL-encoded to support subgroups -->
<!-- [v2] pascal:C-1 + pascal:M-1: per_page set to 100; all pages fetched via _fetch_all_pages -->

| Action | Endpoint | Parameters | Pagination |
|--------|----------|------------|------------|
| List issues | `GET /api/v4/projects/{encoded_path}/issues` | `state`, `per_page=100`, `order_by=updated_at` | Yes — all pages fetched |
| Issue detail | `GET /api/v4/projects/{encoded_path}/issues/{iid}` | — | No (single resource) |
| Issue notes | `GET /api/v4/projects/{encoded_path}/issues/{iid}/notes` | `order_by=created_at`, `sort=asc`, `per_page=100` | Yes — all pages fetched |

**Project path encoding**: The full project path from `GITLAB_PROJECTS` (e.g. `atakalive/gokrax` or `group/subgroup/project`) is URL-encoded using `urllib.parse.quote(path, safe="")`, producing `atakalive%2Fgokrax` or `group%2Fsubgroup%2Fproject`. This is used as `{encoded_path}` in all API URLs.

- `PRIVATE-TOKEN` header is included if `GITLAB_TOKEN` is set
- Request timeout: 15 seconds per individual HTTP request
- HTTP errors are caught per-request and emitted via `list_error` / `detail_error`

### 9.6 Caching

<!-- [v2] pascal:C-2: cache stores complete (all-pages) list only -->

- `MainWindow` holds an in-memory cache: `dict[tuple[str, str], list[dict]]` mapping `(project, state_filter)` to issue list
- **Cache stores only complete lists**: `GitLabThread` fetches all pages before emitting `issues_loaded`. The cache entry is guaranteed to contain the full issue set, not a partial page
- Cache is used on repeated project clicks with the same filter (avoids redundant API calls)
- Cache is invalidated per-project (all filter variants) when the user clicks Reload
- Filter change fetches with the new filter; cached results for other filters are retained
- No TTL-based expiration (manual reload only)

### 9.7 Stale Response Filtering

<!-- [v2] dijkstra:C-4 + euler:C-2: request_id based filtering -->

`MainWindow` maintains `_current_list_request_id: int` and `_current_detail_request_id: int`, updated each time a new fetch is initiated.

```python
def _on_project_clicked(self, project: str):
    # ... mode switching logic ...
    rid = self._gitlab_thread.fetch_issues(project, state)
    self._current_list_request_id = rid
    # [v2] euler:C-3: reset detail pane on project switch
    self._issue_detail.show_blank()
    self._current_detail_request_id = -1

def _on_issues_loaded(self, project: str, state: str, request_id: int, issues: list):
    # [v2] dijkstra:C-4 + euler:C-2: discard stale responses
    if request_id != self._current_list_request_id:
        # Stale response — cache it but do not update UI
        self._issue_cache[(project, state)] = issues
        return
    # Update cache and UI
    self._issue_cache[(project, state)] = issues
    self._issue_list.populate(issues)

def _on_issue_detail_loaded(self, project: str, iid: int, request_id: int, detail: dict):
    if request_id != self._current_detail_request_id:
        return  # stale — discard
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
<!-- [v2] dijkstra:C-3: terminate() fallback after wait timeout -->

`GitLabThread` shutdown is tied to the application's **actual exit path** only:

```python
def closeEvent(self, event):
    if self._force_quit:
        # [v2] dijkstra:C-2 + euler:C-4: only shutdown on actual app exit
        self._gitlab_thread.shutdown()
        if not self._gitlab_thread.wait(2000):
            # [v2] dijkstra:C-3: terminate fallback (DiscordThread parity)
            self._gitlab_thread.terminate()
            self._gitlab_thread.wait(2000)
        # ... existing DiscordThread shutdown ...
        event.accept()
    else:
        # Tray minimize — GitLabThread keeps running
        self.hide()
        event.ignore()
```

- `_force_quit=False` (window close → tray): `GitLabThread` is **not** stopped. Issue browsing remains functional when the window is re-shown
- `_force_quit=True` (Exit menu / system shutdown): `GitLabThread.shutdown()` is called, followed by `wait(2000)`. If the thread does not exit within 2 seconds (e.g. blocked on an HTTP request with 15-second timeout), `terminate()` is called as a fallback, followed by another `wait(2000)`

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
