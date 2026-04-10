"""Root conftest: ensure project root is on sys.path for pytest discovery."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# Enable offscreen rendering for GUI tests when no display is available
if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
