"""
Scryware 3D Studio - Generate tab.

Pick an image -> run TRELLIS.2 in WSL -> get a .glb on Windows.
"""
import os
import re
import subprocess
import webbrowser

from PyQt6.QtCore import Qt, pyqtSignal, QUrl
from PyQt6.QtGui import QPixmap, QDesktopServices
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFileDialog,
    QComboBox, QSpinBox, QProgressBar, QTextEdit, QGroupBox, QSplitter,
)

from backend.wsl_bridge import win_to_wsl, sh_escape

# Where run_trellis.py lives inside WSL after deploy
RUNNER_WSL_PATH = "~/miniconda3/TRELLIS.2/scryware_run_trellis.py"
TRELLIS_WSL_DIR = "~/miniconda3/TRELLIS.2"
CONDA_ENV = "trellis2"

# tqdm line: "Sampling shape SLat: 100%|####| 12/12 [00:03<00:00, 3.19it/s]"
TQDM_RE = re.compile(r"^(.+?):\s+(\d+)%\|")

# Map pipeline stage -> (progress_start, progress_end)
STAGE_RANGES = {
    "loading": (0, 8),
    "sparse": (8, 25),
    "shape": (25, 55),
    "texture": (55, 75),
    "export": (75, 95),
    "meshing": (80, 95),
}


def stage_for_tqdm(desc):
    d = desc.lower()
    if "sparse structure" in d:
        return "sparse"
    if "shape slat" in d:
        return "shape"
    if "texture slat" in d:
        return "texture"
    return None


class GenerateTab(QWidget):
    # emitted with the Windows path of a finished .glb
    model_ready = pyqtSignal(str)
    # thread-safe log delivery: pump thread emits, GUI thread appends
    _log_line = pyqtSignal(str)

    def __init__(self, runner=None, parent=None):
        super().__init__(parent)
        self.runner = runner
        self.proc = None
        self.input_path = ""
        self.output_dir = os.path.join(os.path.expanduser("~"), "Documents", "Scryware3D")
        self.result_path = ""
        # batch log lines and flush to the widget on a timer so a tqdm
        # flood (hundreds of lines/sec) doesn't overwhelm Qt's paint engine
        self._log_batch = []
        self._log_line.connect(self._queue_log_line)
        from PyQt6.QtCore import QTimer
        self._log_timer = QTimer(self)
        self._log_timer.timeout.connect(self._flush_log_batch)
        self._log_timer.start(150)
        self._build_ui()

    def _queue_log_line(self, line):
        self._log_batch.append(line)

    def _flush_log_batch(self):
        if not self._log_batch:
            return
        batch, self._log_batch = self._log_batch, []
        # collapse redundant tqdm progress updates, keep the last per bar
        collapsed = []
        last_pct = {}
        for line in batch:
            m = TQDM_RE.match(line)
            if m:
                last_pct[m.group(1)] = line
            else:
                collapsed.append(line)
        collapsed.extend(last_pct.values())
        for line in collapsed:
            self.append_log(line)
            self._parse_progress(line)
        # keep the widget from growing unbounded
        doc = self.log.document()
        if doc.blockCount() > 2000:
            cursor = self.log.textCursor()
            cursor.movePosition(cursor.MoveMode.Start)
            cursor.movePosition(cursor.MoveMode.Down, cursor.MoveMode.KeepAnchor,
                                doc.blockCount() - 2000)
            cursor.removeSelectedText()

    # ---------- UI ----------
    def _build_ui(self):
        root = QVBoxLayout(self)

        # --- input row ---
        top = QHBoxLayout()
        self.thumb = QLabel("No image selected")
        self.thumb.setFixedSize(160, 160)
        self.thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb.setStyleSheet("border: 1px solid #555; background: #1e1e1e;")
        top.addWidget(self.thumb)

        form = QVBoxLayout()
        row1 = QHBoxLayout()
        self.pick_btn = QPushButton("Pick image...")
        self.pick_btn.clicked.connect(self.pick_image)
        row1.addWidget(self.pick_btn)
        self.img_label = QLabel("(none)")
        self.img_label.setWordWrap(True)
        row1.addWidget(self.img_label, 1)
        form.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Output folder:"))
        self.out_btn = QPushButton("Choose...")
        self.out_btn.clicked.connect(self.pick_output_dir)
        row2.addWidget(self.out_btn)
        self.out_label = QLabel(self.output_dir)
        self.out_label.setWordWrap(True)
        row2.addWidget(self.out_label, 1)
        form.addLayout(row2)

        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Quality:"))
        self.quality = QComboBox()
        self.quality.addItem("Fast (512)", "512")
        self.quality.addItem("High (1024 cascade)", "1024_cascade")
        row3.addWidget(self.quality)
        row3.addWidget(QLabel("Seed:"))
        self.seed = QSpinBox()
        self.seed.setRange(0, 999999)
        self.seed.setValue(42)
        row3.addWidget(self.seed)
        row3.addStretch(1)
        form.addLayout(row3)

        self.gen_btn = QPushButton("Generate 3D model")
        self.gen_btn.setMinimumHeight(40)
        self.gen_btn.clicked.connect(self.start_generate)
        self.gen_btn.setEnabled(False)
        self.gen_btn.setToolTip("Waiting for WSL to boot...")
        form.addWidget(self.gen_btn)
        top.addLayout(form, 1)
        root.addLayout(top)

        # --- progress ---
        self.status = QLabel("Idle.")
        root.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        root.addWidget(self.progress)

        # --- log ---
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setFontFamily("Consolas")
        self.log.setMaximumHeight(180)
        root.addWidget(QLabel("Log:"))
        root.addWidget(self.log)

        # --- result ---
        res_box = QGroupBox("Result")
        res_lay = QHBoxLayout(res_box)
        self.result_label = QLabel("No model generated yet.")
        self.result_label.setWordWrap(True)
        res_lay.addWidget(self.result_label, 1)
        self.show_btn = QPushButton("Show in folder")
        self.show_btn.clicked.connect(self.show_in_folder)
        self.show_btn.setEnabled(False)
        res_lay.addWidget(self.show_btn)
        self.blender_btn = QPushButton("Open in Blender")
        self.blender_btn.clicked.connect(self.open_in_blender)
        self.blender_btn.setEnabled(False)
        res_lay.addWidget(self.blender_btn)
        self.preview_btn = QPushButton("Preview in browser")
        self.preview_btn.clicked.connect(self.preview_in_browser)
        self.preview_btn.setEnabled(False)
        res_lay.addWidget(self.preview_btn)
        self.to_rig_btn = QPushButton("Send to Rig >>")
        self.to_rig_btn.clicked.connect(lambda: self.model_ready.emit(self.result_path))
        self.to_rig_btn.setEnabled(False)
        res_lay.addWidget(self.to_rig_btn)
        root.addWidget(res_box)

    # ---------- actions ----------
    def set_runner(self, runner):
        self.runner = runner

    def set_wsl_ready(self, ready):
        """Called by the main window when WSL warmup finishes."""
        self.gen_btn.setEnabled(ready)
        self.gen_btn.setToolTip(
            "" if ready else "Waiting for WSL to boot...")
        if ready:
            self.status.setText("Idle.")
        else:
            self.status.setText("WSL not ready.")

    def pick_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Pick input image", "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)",
        )
        if path:
            self.input_path = path
            self.img_label.setText(path)
            pix = QPixmap(path).scaled(
                160, 160, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.thumb.setPixmap(pix)

    def pick_output_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Output folder", self.output_dir)
        if d:
            self.output_dir = d
            self.out_label.setText(d)

    def append_log(self, line):
        self.log.append(line)

    def set_progress(self, pct, status=None):
        self.progress.setValue(int(pct))
        if status:
            self.status.setText(status)

    # ---------- generation ----------
    def start_generate(self):
        if not self.runner:
            self.append_log("ERROR: WSL runner not initialized.")
            return
        if not self.input_path:
            self.status.setText("Pick an input image first.")
            return
        if self.proc:
            self.status.setText("Already running.")
            return

        os.makedirs(self.output_dir, exist_ok=True)
        base = os.path.splitext(os.path.basename(self.input_path))[0]
        out_win = os.path.join(self.output_dir, base + ".glb")

        # Deploy the runner script into WSL (idempotent)
        try:
            with open(os.path.join(os.path.dirname(__file__), "..", "wsl", "run_trellis.py"),
                      encoding="utf-8") as f:
                runner_src = f.read()
        except OSError:
            # fallback: running from installed location
            runner_src = ""
        if runner_src:
            ok = self.runner.deploy_file(runner_src, RUNNER_WSL_PATH)
            if not ok:
                self.append_log("WARNING: could not deploy runner script to WSL.")

        in_wsl = win_to_wsl(self.input_path)
        out_wsl = win_to_wsl(out_win)
        ptype = self.quality.currentData()
        seed = self.seed.value()

        # Use the conda env's python directly instead of `conda run`:
        # no shell init needed, immune to PATH/login-shell issues.
        env_python = f"{self.runner.home}/miniconda3/envs/{CONDA_ENV}/bin/python"
        cmd = (
            f"cd {TRELLIS_WSL_DIR} && "
            f"{sh_escape(env_python)} {RUNNER_WSL_PATH} "
            f"{sh_escape(in_wsl)} {sh_escape(out_wsl)} "
            f"--pipeline-type {sh_escape(ptype)} --seed {seed}"
        )
        self.append_log(f"$ {cmd}")
        self.log.clear()
        self.set_progress(0, "Starting...")
        self.gen_btn.setEnabled(False)

        def on_line(line):
            # thread-safe: signal marshals to the GUI thread
            self._log_line.emit(line)

        def on_done(rc):
            self.proc = None
            self.gen_btn.setEnabled(True)
            if rc == 0 and os.path.exists(out_win):
                self.result_path = out_win
                self.set_progress(100, "Done.")
                self.result_label.setText(f"Saved: {out_win}")
                for b in (self.show_btn, self.blender_btn, self.preview_btn, self.to_rig_btn):
                    b.setEnabled(True)
                self.model_ready.emit(out_win)
            else:
                self.set_progress(0, f"Failed (exit {rc}). See log.")

        self.proc = self.runner.run(cmd, on_line=on_line, on_done=on_done,
                                    workdir=TRELLIS_WSL_DIR)

    def _parse_progress(self, line):
        if line.startswith("STAGE:"):
            stage = line.split("STAGE:")[1].strip()
            if stage == "loading":
                self.set_progress(4, "Loading models...")
            elif stage == "generating":
                self.set_progress(10, "Generating...")
            elif stage == "exporting":
                self.set_progress(80, "Exporting mesh...")
            return
        if line.startswith("DONE:"):
            self.set_progress(100, "Done.")
            return
        m = TQDM_RE.match(line)
        if m:
            desc, pct = m.group(1).strip(), int(m.group(2))
            stage = stage_for_tqdm(desc)
            if stage and stage in STAGE_RANGES:
                lo, hi = STAGE_RANGES[stage]
                overall = lo + (hi - lo) * pct / 100
                self.set_progress(overall, desc + "...")
            return
        low = line.lower()
        if "remeshing" in low or "dual contouring" in low or "xatlas" in low:
            self.set_progress(88, "Building mesh...")

    # ---------- result actions ----------
    def show_in_folder(self):
        if self.result_path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(self.result_path)))

    def open_in_blender(self):
        if not self.result_path:
            return
        # Try `blender` on PATH; else just reveal the file.
        try:
            subprocess.Popen(["blender", self.result_path])
        except OSError:
            self.show_in_folder()

    def preview_in_browser(self):
        if self.result_path:
            webbrowser.open("https://gltf-viewer.donmccurdy.com/")
            self.status.setText("Drag the .glb file into the viewer page.")
