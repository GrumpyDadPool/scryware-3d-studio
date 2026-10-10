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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Scryware 3D Studio")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
