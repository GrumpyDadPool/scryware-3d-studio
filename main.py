"""
Scryware 3D Studio - v1

Windows GUI for the local 3D asset pipeline:
  1. Generate 3D  (TRELLIS.2 in WSL2)
  2. Rig          (SkinTokens in WSL2)
  3. Animate      (Mixamo, embedded browser)

Run on Windows:
    pip install -r requirements.txt
    python main.py

Prerequisites:
  - WSL2 with Ubuntu + the TRELLIS.2 setup from trellis-setup-guide.md
    (conda env 'trellis2', repo at ~/miniconda3/TRELLIS.2, SDPA patch applied)
  - Python 3.10+ on Windows
"""
import sys
import os
import traceback
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Crash + session logging: everything the app prints and any uncaught
# exception lands in scryware-3d-studio.log next to main.py, so a crash
# can be diagnosed after the window is gone.
LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "scryware-3d-studio.log")


class _Tee:
    def __init__(self, stream):
        self.stream = stream

    def write(self, data):
        try:
            self.stream.write(data)
            self.stream.flush()
        except Exception:
            pass
        try:
            with open(LOG_PATH, "a", encoding="utf-8", errors="replace") as f:
                f.write(data)
        except Exception:
            pass

    def flush(self):
        try:
            self.stream.flush()
        except Exception:
            pass


def _log_header():
    try:
        with open(LOG_PATH, "a", encoding="utf-8", errors="replace") as f:
            f.write(f"\n{'=' * 60}\n")
            f.write(f"Scryware 3D Studio session: "
                    f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"{'=' * 60}\n")
    except Exception:
        pass


def _excepthook(exc_type, exc_value, exc_tb):
    try:
        with open(LOG_PATH, "a", encoding="utf-8", errors="replace") as f:
            f.write("\n--- UNCAUGHT EXCEPTION ---\n")
            traceback.print_exception(exc_type, exc_value, exc_tb, file=f)
    except Exception:
        pass
    traceback.print_exception(exc_type, exc_value, exc_tb)


from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication
from gui.main_window import MainWindow


def main():
    _log_header()
    sys.stdout = _Tee(sys.stdout)
    sys.stderr = _Tee(sys.stderr)
    sys.excepthook = _excepthook
    app = QApplication(sys.argv)
    app.setApplicationName("Scryware 3D Studio")
    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "assets", "icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
