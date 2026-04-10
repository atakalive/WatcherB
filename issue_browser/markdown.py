"""Minimal Markdown to HTML converter for QTextBrowser rendering."""

import html
import re
import secrets

_FENCED_RE = re.compile(r'```[^\n]*\n(.*?)```', re.DOTALL)
_INLINE_CODE_RE = re.compile(r'`([^`\x00]+?)`')


def _extract_fenced_blocks(
    text: str,
    placeholders: dict[str, str],
    sentinel: str,
) -> str:
    """Extract fenced code blocks and replace with placeholders.

    Language specifier after ``` is accepted but ignored.
    Content is already html.escape()'d at this point.
    """
    counter = len(placeholders)

    def _replace(m: re.Match) -> str:
        nonlocal counter
        key = f'{sentinel}FENCED_{counter}{sentinel}'
        placeholders[key] = f'<pre><code>{m.group(1)}</code></pre>'
        counter += 1
        return key

    return _FENCED_RE.sub(_replace, text)


def _extract_inline_code(
    text: str,
    placeholders: dict[str, str],
    sentinel: str,
) -> str:
    """Extract inline code and replace with placeholders.

    Content is already html.escape()'d at this point.
    """
    counter = len(placeholders)

    def _replace(m: re.Match) -> str:
        nonlocal counter
        key = f'{sentinel}INLINE_{counter}{sentinel}'
        placeholders[key] = f'<code>{m.group(1)}</code>'
        counter += 1
        return key

    return _INLINE_CODE_RE.sub(_replace, text)


def md_to_html(text: str) -> str:
    """Convert minimal Markdown to HTML for QTextBrowser rendering.

    Conversion order is security-critical: html.escape() must run first.
    """
    if not text:
        return ""

    # 1. HTML エスケープ（全入力に対して最初に実行）
    text = html.escape(text)

    # Per-call sentinel for placeholder keys (collision-resistant)
    sentinel = f"\x00{secrets.token_hex(8)}\x00"
    placeholders: dict[str, str] = {}

    # 2. フェンスドコードブロック抽出 → プレースホルダ置換
    text = _extract_fenced_blocks(text, placeholders, sentinel)

    # 3. インラインコード抽出 → プレースホルダ置換
    text = _extract_inline_code(text, placeholders, sentinel)

    # 4. **bold** → <b>bold</b>
    #    \x00 を除外して sentinel 境界を跨がないようにする
    text = re.sub(r'\*\*([^*\x00]+?)\*\*', r'<b>\1</b>', text)

    # 5. 改行 → <br>
    text = text.replace('\n', '<br>\n')

    # 6. プレースホルダ復元
    for key, fragment in placeholders.items():
        text = text.replace(key, fragment)

    return text
