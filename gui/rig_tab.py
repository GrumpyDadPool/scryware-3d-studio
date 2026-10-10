"""
Scryware 3D Studio - Rig tab.

Takes a generated .glb and runs SkinTokens auto-rigging in WSL.
SkinTokens is not installed yet -> the tab shows setup guidance until it is.
"""
import os

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFileDialog,
    QTextEdit, QProgressBar, QGroupBox,
)

from backend.wsl_bridge import win_to_wsl, sh_escape

SKINTOKENS_WSL_DIR = "~/SkinTokens"
# Command template run inside the SkinTokens dir. {input} / {output} are WSL paths.
# Verified 2026-10-10: demo.py with --use_transfer preserves texture and scale.
# Uses .venv/bin/python directly to avoid conda/venv PATH stacking issues.
RIG_CMD_TEMPLATE = (
    ".venv/bin/python demo.py --input {input} --output {output} --use_transfer"
)


class RigTab(QWidget):
    def __init__(self, runner=None, parent=None):
        super().__init__(parent)
        self.runner = runner
        self.proc = None
        self.input_path = ""
        self.output_dir = os.path.join(os.path.expanduser("~"), "Documents", "Scryware3D")
        self.skintokens_ready = False
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)

        self.status_box = QGroupBox("SkinTokens status")
        sb = QVBoxLayout(self.status_box)
        self.sk_status = QLabel("Checking...")
        sb.addWidget(self.sk_status)
        self.setup_hint = QLabel(
            "SkinTokens isn't installed yet. Follow the setup guide "
            "(trellis-setup-guide.md, 'Auto-rigging' section), then press Re-check."
        )
        self.setup_hint.setWordWrap(True)
        sb.addWidget(self.setup_hint)
        self.recheck_btn = QPushButton("Re-check")
        self.recheck_btn.clicked.connect(self.check_skintokens)
        sb.addWidget(self.recheck_btn)
        root.addWidget(self.status_box)

        row = QHBoxLayout()
        self.pick_btn = QPushButton("Pick .glb to rig...")
        self.pick_btn.clicked.connect(self.pick_model)
        row.addWidget(self.pick_btn)
        self.file_label = QLabel("(none)")
        self.file_label.setWordWrap(True)
        row.addWidget(self.file_label, 1)
        root.addLayout(row)

        self.rig_btn = QPushButton("Rig character")
        self.rig_btn.setMinimumHeight(40)
        self.rig_btn.clicked.connect(self.start_rig)
        root.addWidget(self.rig_btn)

        self.status = QLabel("Idle.")
        root.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        root.addWidget(self.progress)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setFontFamily("Consolas")
        self.log.setMaximumHeight(180)
        root.addWidget(QLabel("Log:"))
        root.addWidget(self.log)
        root.addStretch(1)

    def set_runner(self, runner):
        self.runner = runner
        self.check_skintokens()

    def set_wsl_ready(self, ready):
        """Called by the main window when WSL warmup finishes."""
        if ready:
            self.check_skintokens()
        else:
            self.sk_status.setText("WSL not ready.")
            self.rig_btn.setEnabled(False)

    def set_input(self, win_path):
        """Called when the Generate tab finishes a model."""
        if win_path and os.path.exists(win_path):
            self.input_path = win_path
            self.file_label.setText(win_path)

    def check_skintokens(self):
        if not self.runner:
            self.sk_status.setText("WSL runner not initialized.")
            return
        ok = self.runner.path_exists(SKINTOKENS_WSL_DIR)
        self.skintokens_ready = ok
        if ok:
            self.sk_status.setText("SkinTokens found in WSL. Ready to rig.")
            self.setup_hint.setText("")
        else:
            self.sk_status.setText("SkinTokens NOT found at ~/SkinTokens in WSL.")
        self.rig_btn.setEnabled(ok)

    def pick_model(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Pick .glb to rig", self.output_dir,
            "3D models (*.glb *.gltf *.obj *.fbx)",
        )
        if path:
            self.set_input(path)

    def start_rig(self):
        if not self.runner or not self.skintokens_ready:
            return
        if not self.input_path:
            self.status.setText("Pick a .glb first.")
            return
        if self.proc:
            self.status.setText("Already running.")
            return

        os.makedirs(self.output_dir, exist_ok=True)
        base = os.path.splitext(os.path.basename(self.input_path))[0]
        out_win = os.path.join(self.output_dir, base + "_rigged.glb")

        in_wsl = win_to_wsl(self.input_path)
        out_wsl = win_to_wsl(out_win)
        cmd = RIG_CMD_TEMPLATE.format(input=sh_escape(in_wsl), output=sh_escape(out_wsl))

        self.log.clear()
        self.log.append(f"$ {cmd}")
        self.progress.setValue(5)
        self.status.setText("Rigging...")
        self.rig_btn.setEnabled(False)

        def on_line(line):
            self.log.append(line)

        def on_done(rc):
            self.proc = None
            self.rig_btn.setEnabled(True)
            if rc == 0 and os.path.exists(out_win):
                self.progress.setValue(100)
                self.status.setText(f"Rigged: {out_win}")
            else:
                self.progress.setValue(0)
                self.status.setText(f"Rigging failed (exit {rc}). See log.")

        self.proc = self.runner.run(cmd, on_line=on_line, on_done=on_done,
                                    workdir=SKINTOKENS_WSL_DIR)
