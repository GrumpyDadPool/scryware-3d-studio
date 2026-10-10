"""
Scryware 3D Studio - main window.
"""
import threading

from PyQt6.QtWidgets import QMainWindow, QTabWidget, QMessageBox, QLabel
from PyQt6.QtCore import Qt, QTimer

from gui.generate_tab import GenerateTab
from gui.rig_tab import RigTab
from gui.animate_tab import AnimateTab
from backend.wsl_bridge import WslRunner


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Scryware 3D Studio")
        self.resize(1100, 800)

        self.runner = None
        try:
            self.runner = WslRunner()
        except RuntimeError as e:
            QMessageBox.warning(
                self, "WSL not ready",
                f"Could not initialize WSL bridge:\n{e}\n\n"
                "Generate/Rig tabs need WSL2 with the trellis2 setup.",
            )

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.gen_tab = GenerateTab(runner=self.runner)
        self.rig_tab = RigTab(runner=self.runner)
        self.anim_tab = AnimateTab()

        self.tabs.addTab(self.gen_tab, "1. Generate 3D")
        self.tabs.addTab(self.rig_tab, "2. Rig")
        self.tabs.addTab(self.anim_tab, "3. Animate (Mixamo)")

        # Wire: finished model -> rig tab input, rig tab -> animate tab
        self.gen_tab.model_ready.connect(self.on_model_ready)

        distro = self.runner.distro if self.runner else "none"
        self.statusBar().showMessage(f"WSL distro: {distro} — warming up...")
        # Warm up WSL at launch (in a thread) so the VM is already booted
        # by the time the user hits Generate. First boot takes 10-30s.
        if self.runner:
            QTimer.singleShot(500, self._warmup_wsl)

    def _warmup_wsl(self):
        def _go():
            try:
                rc, out = self.runner.run_simple("echo wsl-ready", timeout=120)
                ok = rc == 0 and "wsl-ready" in out
            except Exception:
                ok = False
            # update the status bar back on the GUI thread
            QTimer.singleShot(0, lambda: self._warmup_done(ok))

        threading.Thread(target=_go, daemon=True).start()

    def _warmup_done(self, ok):
        distro = self.runner.distro if self.runner else "none"
        if ok:
            self.statusBar().showMessage(f"WSL distro: {distro} — ready")
        else:
            self.statusBar().showMessage(
                f"WSL distro: {distro} — warmup failed, will boot on first run")

    def on_model_ready(self, win_path):
        if win_path:
            self.rig_tab.set_input(win_path)
