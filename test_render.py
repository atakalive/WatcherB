"""QTextBrowser で実際にどうレンダリングされるかテスト."""
import sys
from PySide6.QtWidgets import QApplication, QTextBrowser

app = QApplication(sys.argv)
tb = QTextBrowser()
tb.setStyleSheet("background-color: #1e1e2e; color: #cdd6f4;")

# Test 1: border-left
tb.append('<div style="border-left: 3px solid #a6e3a1; padding: 3px 8px;">border-left test</div>')

# Test 2: span color
tb.append('<span style="color: #89b4fa; font-weight: bold;">DESIGN_PLAN</span> → <span style="color: #89b4fa; font-weight: bold;">DESIGN_REVIEW</span>')

# Test 3: padding-left for indent
tb.append('<div>14:00 First line</div><div style="padding-left: 3.8em;">Second line indented</div>')

# Test 4: table-based approach
tb.append('<table cellpadding="0" cellspacing="0"><tr><td style="width: 3.5em; color: #a6adc8;">14:01</td><td><span style="color: #89b4fa; font-weight: bold;">CODE_REVIEW</span> → <span style="color: #89b4fa; font-weight: bold;">DONE</span></td></tr></table>')

tb.resize(600, 400)
tb.show()
print("Check which styles actually render. Close window to exit.")
sys.exit(app.exec())
