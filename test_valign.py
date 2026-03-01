import sys
from PySide6.QtWidgets import QApplication, QTextBrowser

app = QApplication(sys.argv)
tb = QTextBrowser()
tb.setStyleSheet("background-color: #1e1e2e; color: #cdd6f4; font-size: 14px;")

# Test valign middle with rowspan
tb.append('<table cellpadding="0" cellspacing="0" width="100%"><tr><td width="42" valign="middle" rowspan="3"><font color="#a6adc8">14:00</font></td><td><font color="#cdd6f4">Line 1</font></td></tr><tr><td><font color="#cdd6f4">Line 2</font></td></tr><tr><td><font color="#cdd6f4">Line 3</font></td></tr></table>')

# Test with padding
tb.append('<table cellpadding="4" cellspacing="0" width="100%"><tr><td width="42"><font color="#a6adc8">14:01</font></td><td><font color="#cdd6f4">Single line with cellpadding=4</font></td></tr></table>')

tb.resize(600, 300)
tb.show()
sys.exit(app.exec())
