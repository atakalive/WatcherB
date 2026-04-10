from issue_browser.markdown import md_to_html


class TestMdToHtml:
    def test_empty_string(self):
        assert md_to_html("") == ""

    def test_plain_text(self):
        assert md_to_html("hello") == "hello"

    def test_bold(self):
        assert md_to_html("hello **world**") == "hello <b>world</b>"

    def test_xss_prevention(self):
        result = md_to_html("<script>alert(1)</script>")
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_inline_code(self):
        result = md_to_html("use `foo()` here")
        assert "<code>foo()</code>" in result

    def test_inline_code_escapes_html(self):
        result = md_to_html("use `<b>tag</b>` here")
        assert "<code>&lt;b&gt;tag&lt;/b&gt;</code>" in result

    def test_fenced_code_block(self):
        text = "before\n```\ncode line\n```\nafter"
        result = md_to_html(text)
        assert "<pre><code>" in result
        assert "code line" in result

    def test_fenced_block_no_bold_conversion(self):
        text = "```\n**not bold**\n```"
        result = md_to_html(text)
        assert "<b>" not in result
        assert "**not bold**" in result

    def test_fenced_block_with_language(self):
        text = "```python\nprint('hi')\n```"
        result = md_to_html(text)
        assert "<pre><code>" in result
        assert "print" in result

    def test_placeholder_char_blocks_bold(self):
        # \x00 inside ** should prevent bold conversion
        result = md_to_html("**a\x00b**")
        assert "<b>" not in result

    def test_newline(self):
        assert md_to_html("\n") == "<br>\n"

    def test_multiple_bold(self):
        result = md_to_html("**a** and **b**")
        assert result == "<b>a</b> and <b>b</b>"

    def test_nested_backtick_in_fenced(self):
        text = "```\n`inline` inside\n```"
        result = md_to_html(text)
        # backtick inside fenced block should NOT become <code>
        assert result.count("<code>") == 1  # only the <pre><code>

    def test_placeholder_like_input_not_corrupted(self):
        """User input containing placeholder-like strings must not be corrupted.

        Even if input contains \x00...\x00 patterns, the per-call random
        sentinel ensures no collision with actual placeholder keys.
        """
        # Simulate input that looks like a placeholder (but with a fake token)
        fake_placeholder = "\x00fake_token\x00FENCED_0\x00fake_token\x00"
        malicious = f"text {fake_placeholder} more text"
        result = md_to_html(malicious)
        # 1. The fake placeholder fragment must survive in the output (not be consumed)
        assert "fake_token" in result
        assert "FENCED_0" in result
        # 2. No spurious <pre><code> or <code> tags should be injected by
        #    the placeholder restoration step
        assert "<pre><code>" not in result
        assert "<code>" not in result
        # 3. Surrounding text must be intact
        assert "text" in result
        assert "more text" in result
