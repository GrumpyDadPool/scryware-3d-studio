"""
Scryware 3D Studio - Animate tab.

Embedded Mixamo browser (Chromium via QWebEngineView) so the whole
pipeline stays in one app. Downloads are routed to the project folder.
"""
import os

from PyQt6.QtCore import QUrl
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QFileDialog,
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile


class AnimateTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_model = ""
        self.download_dir = os.path.join(os.path.expanduser("~"), "Documents", "Scryware3D")
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)

        # --- toolbar ---
        bar = QHBoxLayout()
        self.back_btn = QPushButton("<")
        self.back_btn.setFixedWidth(32)
        self.fwd_btn = QPushButton(">")
        self.fwd_btn.setFixedWidth(32)
        self.reload_btn = QPushButton("Reload")
        self.home_btn = QPushButton("Mixamo home")
        self.url = QLineEdit("https://www.mixamo.com/")
        self.url.returnPressed.connect(self.navigate)
        bar.addWidget(self.back_btn)
        bar.addWidget(self.fwd_btn)
        bar.addWidget(self.reload_btn)
        bar.addWidget(self.home_btn)
        bar.addWidget(self.url, 1)
        root.addLayout(bar)

        # --- browser ---
        try:
            self.view = QWebEngineView()
            # Route downloads to the project folder
            profile = self.view.page().profile()
            profile.setDownloadPath(self.download_dir)
            profile.downloadRequested.connect(self.on_download)
            self.view.urlChanged.connect(lambda u: self.url.setText(u.toString()))
            self.back_btn.clicked.connect(self.view.back)
            self.fwd_btn.clicked.connect(self.view.forward)
            self.reload_btn.clicked.connect(self.view.reload)
            self.home_btn.clicked.connect(lambda: self.view.setUrl(QUrl("https://www.mixamo.com/")))
            self.view.setUrl(QUrl("https://www.mixamo.com/"))
            root.addWidget(self.view, 1)
        except Exception as e:
            root.addWidget(QLabel(
                "Web view unavailable (PyQt6-WebEngine not installed).\n"
                f"{e}\n\nInstall with: pip install PyQt6-WebEngine"
            ))

        # --- helper row ---
        help_row = QHBoxLayout()
        help_row.addWidget(QLabel(
            "Log into Mixamo, upload your rigged character (FBX), pick animations, "
            "download — files land in your output folder."
        ))
        self.dl_btn = QPushButton("Download folder...")
        self.dl_btn.clicked.connect(self.pick_download_dir)
        help_row.addWidget(self.dl_btn)
        root.addLayout(help_row)

    def navigate(self):
        if hasattr(self, "view"):
            url = self.url.text().strip()
            if not url.startswith("http"):
                url = "https://" + url
            self.view.setUrl(QUrl(url))

    def on_download(self, download):
        # Accept and keep the profile's download path
        download.accept()

    def pick_download_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Download folder", self.download_dir)
        if d:
            self.download_dir = d
            if hasattr(self, "view"):
                self.view.page().profile().setDownloadPath(d)

    def set_model(self, win_path):
        """Called when a rigged model is ready (v2: one-click upload)."""
        self.current_model = win_path or ""
