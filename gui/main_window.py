"""
Scryware 3D Studio - main window.
"""
import subprocess
import threading

from PyQt6.QtWidgets import QMainWindow, QTabWidget, QMessageBox, QLabel
from PyQt6.QtCore import Qt, QTimer

from gui.generate_tab import GenerateTab
from gui.rig_tab import RigTab
from gui.animate_tab import AnimateTab
from backend.wsl_bridge import WslRunner, _session_log_path


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
        def _wlog(msg):
            try:
                from datetime import datetime
                ts = datetime.now().strftime("%H:%M:%S")
                with open(_session_log_path(), "a", encoding="utf-8",
                          errors="replace") as f:
                    f.write(f"[warmup {ts}] {msg}\n")
            except Exception:
                pass

        def _go():
            # Do NOT capture output via pipes: wsl.exe deadlocks with piped
            # stdout/stderr while the VM is cold-booting. Redirect to the
            # session log file instead (file redirect is safe, pipes are not).
            _wlog("starting")
            try:
                cmd = [self.runner.wsl_exe, "-d", self.runner.distro,
                       "-e", "true"]
                _wlog(f"cmd: {' '.join(cmd)}")
                log_path = _session_log_path()
                with open(log_path, "a", encoding="utf-8",
                           errors="replace") as lf:
                    lf.write(f"[warmup] launching wsl.exe...\n")
                    lf.flush()
                    proc = subprocess.run(
                        cmd,
                        stdout=lf,
                        stderr=subprocess.STDOUT,
                        stdin=subprocess.DEVNULL,
                        timeout=120,
                    )
                _wlog(f"done rc={proc.returncode}")
                ok = proc.returncode == 0
            except subprocess.TimeoutExpired:
                _wlog("TIMEOUT after 120s")
                ok = False
            except Exception as e:
                _wlog(f"EXCEPTION: {type(e).__name__}: {e}")
                ok = False
            # update the status bar back on the GUI thread
            QTimer.singleShot(0, lambda: self._warmup_done(ok))

        _wlog("thread starting")
        threading.Thread(target=_go, daemon=True).start()

    def _warmup_done(self, ok):
        distro = self.runner.distro if self.runner else "none"
        if ok:
            self.statusBar().showMessage(f"WSL distro: {distro} — ready")
        else:
            self.statusBar().showMessage(
                f"WSL distro: {distro} — warmup failed, will boot on first run")
        self.gen_tab.set_wsl_ready(ok)
        self.rig_tab.set_wsl_ready(ok)

    def on_model_ready(self, win_path):
        if win_path:
            self.rig_tab.set_input(win_path)
