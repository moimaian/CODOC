# -*- coding: utf-8 -*-
# pyright: reportAttributeAccessIssue=false, reportOptionalMemberAccess=false, reportMissingImports=false

from __future__ import annotations

import os
import sys
from pathlib import Path
from threading import Thread

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QGuiApplication, QPixmap
from PyQt5.QtWidgets import QApplication, QLabel, QProgressBar, QVBoxLayout, QWidget

from MODULES.module_requirements import ensure_venv, install_python_packages, venv_paths, PYTHON_PACKAGES

APP_NAME = "CODOC"
APP_DIR_NAME = "CODOC"
HOME = str(Path.home())
APP_DIR = os.path.join(HOME, APP_DIR_NAME)
VENV_PY = venv_paths(APP_NAME)["python"]
DESKTOP_DIR = os.path.join(HOME, ".local", "share", "applications")
DESKTOP_FILE = os.path.join(DESKTOP_DIR, f"{APP_NAME}.desktop")
MIN_MARKER = os.path.join(venv_paths(APP_NAME)["venv_dir"], ".codoc_minimal_done")

ESSENTIALS = [
    PYTHON_PACKAGES["PyQt5"],
    PYTHON_PACKAGES["pandas"],
    PYTHON_PACKAGES["psutil"],
]


def _icon_path(dp_dir: str) -> str:
    return os.path.join(dp_dir, "ICONS", "logo_codocP.png")


def _write_desktop(dp_dir: str) -> None:
    os.makedirs(DESKTOP_DIR, exist_ok=True)
    icon_path = _icon_path(dp_dir)
    exec_path = os.path.join(dp_dir, "CODOC.py")
    content = f"""[Desktop Entry]
Version=1.0
Name={APP_NAME}
Comment=Python and PyQt5 CODOC interface
Exec=bash -i -c \"env PYTHONNOUSERSITE=1 '{VENV_PY}' '{exec_path}'\"
Icon={icon_path}
Terminal=true
Type=Application
Categories=Qt;Science;Chemistry;
StartupNotify=false
StartupWMClass={APP_NAME}
"""
    with open(DESKTOP_FILE, "w", encoding="utf-8") as handle:
        handle.write(content)
    os.chmod(DESKTOP_FILE, 0o755)


def _desktop_icon_line(content: str) -> "str | None":
    for line in content.splitlines():
        if line.startswith("Icon="):
            return line[len("Icon="):].strip()
    return None


def ensure_desktop(dp_dir: str) -> None:
    """(Re)writes ~/.local/share/applications/CODOC.desktop when it is missing OR stale.

    Only checking the Exec path (as this used to do) meant that once the file existed with a
    matching Exec line, it was never touched again - so when the app's logo files moved from
    MIDIA/ to ICONS/ at some point, every existing installation kept pointing Icon= at the old,
    now-missing MIDIA/logo_codocP.png forever, and the launcher/menu/panel silently showed no
    icon at all for CODOC. Re-checking that the *current* Icon= target still exists on disk lets
    this self-heal on the next launch instead of requiring a manual desktop-file edit."""
    try:
        if not os.path.isfile(DESKTOP_FILE):
            _write_desktop(dp_dir)
            return
        content = Path(DESKTOP_FILE).read_text(encoding="utf-8")
        stale_exec = exec_path_token(dp_dir) not in content
        icon_line = _desktop_icon_line(content)
        stale_icon = not icon_line or not os.path.isfile(icon_line)
        if stale_exec or stale_icon:
            _write_desktop(dp_dir)
    except Exception:
        pass


def exec_path_token(dp_dir: str) -> str:
    return os.path.join(dp_dir, "CODOC.py")


def install_minimal_essentials(callback=None) -> None:
    try:
        if os.path.isfile(MIN_MARKER):
            if callback:
                callback(True, "Already installed.")
            return
        paths = ensure_venv(APP_NAME)
        result = install_python_packages(paths["python"], ESSENTIALS)
        ok = result.returncode == 0
        if ok:
            Path(MIN_MARKER).write_text("ok", encoding="utf-8")
        if callback:
            callback(ok, result.stdout or "done")
    except Exception as exc:
        if callback:
            callback(False, str(exc))


class SplashScreen(QWidget):
    check_complete = pyqtSignal(dict)
    essentials_done = pyqtSignal(bool, str)

    def __init__(self, dp_dir: str) -> None:
        super().__init__()
        self.dp_dir = dp_dir
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        screen = QGuiApplication.primaryScreen()
        geometry = screen.availableGeometry()
        width, height = 520, 320
        self.resize(width, height)
        self.move((geometry.width() - width) // 2, (geometry.height() - height) // 3)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        logo = QLabel()
        logo_path = os.path.join(dp_dir, "ICONS", "logo_codocP.png")
        if os.path.exists(logo_path):
            pix = QPixmap(logo_path).scaled(180, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo.setPixmap(pix)
        logo.setAlignment(Qt.AlignCenter)
        layout.addWidget(logo)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.progress)

        self.status = {
            "desktop_ok": False,
            "folders_ok": False,
            "essentials_installed": False,
        }
        self._target = 0
        self._timer = QTimer(self)
        self._timer.setInterval(20)
        self._timer.timeout.connect(self._advance_progress)
        self.essentials_done.connect(self._on_essentials_done)

    def start_checks(self) -> None:
        self.progress.setValue(0)
        self._target = 5
        self._timer.start()

        ensure_desktop(self.dp_dir)
        self.status["desktop_ok"] = True
        self._set_target(25)

        for folder in ("JOBS", "MODULES", "TEST", "ICONS", "LIGANDS", "TARGETS", "BIN"):
            os.makedirs(os.path.join(self.dp_dir, folder), exist_ok=True)
        self.status["folders_ok"] = True
        self._set_target(60)

        def _worker() -> None:
            def _callback(ok: bool, text: str) -> None:
                try:
                    self.essentials_done.emit(bool(ok), str(text or ""))
                except RuntimeError:
                    pass
            install_minimal_essentials(_callback)

        self._set_target(70)
        Thread(target=_worker, daemon=True).start()

    def _set_target(self, value: int) -> None:
        self._target = max(0, min(100, int(value)))

    def _advance_progress(self) -> None:
        current = self.progress.value()
        if current >= self._target:
            if self._target >= 100:
                self._finish()
            return
        step = max(1, (self._target - current) // 10)
        self.progress.setValue(min(current + step, self._target))

    def _on_essentials_done(self, ok: bool, _text: str) -> None:
        self.status["essentials_installed"] = ok
        self._set_target(100)

    def _finish(self) -> None:
        if self._timer.isActive():
            self._timer.stop()
        self.progress.setValue(100)
        self.check_complete.emit(self.status)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    widget = SplashScreen(APP_DIR)
    widget.show()
    QTimer.singleShot(0, widget.start_checks)
    sys.exit(app.exec_())
