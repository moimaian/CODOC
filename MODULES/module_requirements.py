# -*- coding: utf-8 -*-
# pyright: reportAttributeAccessIssue=false

from __future__ import annotations

import importlib
import importlib.util
import os
import platform
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Optional, cast

TARGET_VENV_PYTHON = "3.10.12"
APP_NAME = "CODOC"
APP_DIR_NAME = "CODOC_PY"
PYENV_APT_BUILD_DEPS = [
    "build-essential",
    "libssl-dev",
    "zlib1g-dev",
    "libbz2-dev",
    "libreadline-dev",
    "libsqlite3-dev",
    "curl",
    "git",
    "libncursesw5-dev",
    "xz-utils",
    "tk-dev",
    "libxml2-dev",
    "libxmlsec1-dev",
    "libffi-dev",
    "liblzma-dev",
]

PYTHON_PACKAGES = {
    "PyQt5": "PyQt5>=5.15,<5.16",
    "pandas": "pandas>=2.1,<2.3",
    "psutil": "psutil>=5.9,<6.0",
}

CODOC_PYTHON_DEFAULTS = {
    "PyQt5": "PyQt5>=5.15,<5.16",
    "pandas": "pandas>=2.1,<2.3",
    "psutil": "psutil>=5.9,<6.0",
    "matplotlib": "matplotlib>=3.8,<3.10",
    "numpy": "numpy<2",
    "rdkit-pypi": "rdkit-pypi==2022.9.5",
}

CODOC_SYSTEM_DEFAULTS = {
    "parallel": "parallel",
    "gnuplot": "gnuplot",
    "openbabel": "openbabel",
}

SYSTEM_REQUIREMENTS = {
    "build-essential": ["sudo", "apt-get", "install", "-y", "build-essential", "wget", "unzip", "cmake", "git"],
    "parallel": ["sudo", "apt-get", "install", "-y", "parallel"],
    "gnuplot": ["sudo", "apt-get", "install", "-y", "gnuplot"],
    "openbabel": ["sudo", "apt-get", "install", "-y", "openbabel"],
}

VINA_URL = "https://github.com/ccsb-scripps/AutoDock-Vina/releases/download/v1.2.5/vina_1.2.5_linux_x86_64"
VINA_SPLIT_URL = "https://github.com/ccsb-scripps/AutoDock-Vina/releases/download/v1.2.5/vina_split_1.2.5_linux_x86_64"

_PYQT_IMPORT_ERROR = None
pyqtSignal = cast(Any, None)
try:
    from PyQt5.QtCore import Qt, pyqtSignal as _pyqtSignal
    from PyQt5.QtWidgets import (
        QApplication,
        QCheckBox,
        QDialog,
        QFrame,
        QGroupBox,
        QGridLayout,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMessageBox,
        QProgressBar,
        QPushButton,
        QScrollArea,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )
    pyqtSignal = _pyqtSignal
    _PYQT_AVAILABLE = True
except Exception as exc:
    _PYQT_IMPORT_ERROR = exc
    _PYQT_AVAILABLE = False

    class _DummySignal:
        def connect(self, *args: Any, **kwargs: Any) -> None:
            return None

        def emit(self, *args: Any, **kwargs: Any) -> None:
            return None

    pyqtSignal = cast(Any, lambda *args, **kwargs: _DummySignal())

    class _DummyQt:
        ApplicationModal = 0
        RichText = 0

    class _DummyWidget:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def __getattr__(self, _name: str) -> Any:
            def _dummy(*args: Any, **kwargs: Any) -> Any:
                return None
            return _dummy

    Qt = cast(Any, _DummyQt())
    QApplication = QCheckBox = QDialog = QFrame = QGroupBox = QGridLayout = QHBoxLayout = QLabel = QLineEdit = cast(Any, _DummyWidget)
    QMessageBox = QProgressBar = QPushButton = QScrollArea = QTextEdit = QVBoxLayout = QWidget = cast(Any, _DummyWidget)

_SS_BTN_PRIMARY = """
QPushButton {
    background: #1A4A30;
    color: #2ECC71;
    font-weight: bold;
    border: 1px solid #2ECC71;
    border-radius: 5px;
    padding: 6px 16px;
}
QPushButton:hover { background: #27AE60; color: #0D1B2A; }
QPushButton:pressed { background: #1E8449; color: #FFF; }
QPushButton:disabled { background: #1C2E20; color: #3D6B4A; border-color: #2A4A36; }
"""

_SS_BTN_DANGER = """
QPushButton {
    background: #4A2A2A;
    color: #F39A8A;
    font-weight: bold;
    border: 1px solid #F39A8A;
    border-radius: 5px;
    padding: 6px 16px;
}
QPushButton:hover { background: #F0AA9D; color: #0D1B2A; }
QPushButton:pressed { background: #D98979; color: #FFF; }
"""


def _run(cmd: list[str], check: bool = False, env: Optional[dict[str, str]] = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=check, env=env)


def _which(name: str) -> Optional[str]:
    return shutil.which(name)


def _has_module(pybin: str, module_name: str) -> bool:
    result = _run([pybin, "-c", f"import {module_name}"])
    return result.returncode == 0


def _python_version_string(pybin: str) -> Optional[str]:
    result = _run([pybin, "-c", "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}.{sys.version_info[2]}')"])
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _package_version(pybin: str, package_name: str) -> Optional[str]:
    result = _run(
        [
            pybin,
            "-c",
            (
                "from importlib import metadata; "
                f"print(metadata.version('{package_name}'))"
            ),
        ]
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _numpy_major(pybin: str) -> Optional[int]:
    version = _package_version(pybin, "numpy")
    if not version:
        return None
    try:
        return int(version.split(".", 1)[0])
    except Exception:
        return None


def _ensure_rdkit_numpy_compat(pybin: str) -> None:
    numpy_major = _numpy_major(pybin)
    if numpy_major is None or numpy_major < 2:
        return
    if _package_version(pybin, "rdkit-pypi") is None:
        return
    result = _run([pybin, "-m", "pip", "install", "--upgrade", "numpy<2"])
    if result.returncode != 0:
        raise RuntimeError(f"Failed to install NumPy compatibility package:\n{result.stdout}")


def _is_target_python(pybin: str, version: str = TARGET_VENV_PYTHON) -> bool:
    return _python_version_string(pybin) == version


def venv_paths(env_name: str = APP_NAME) -> dict[str, str]:
    home = str(Path.home())
    app_dir = os.path.join(home, APP_DIR_NAME)
    venv_dir = os.path.join(home, ".venv", env_name)
    return {
        "app_dir": app_dir,
        "venv_dir": venv_dir,
        "python": os.path.join(venv_dir, "bin", "python"),
        "pip": os.path.join(venv_dir, "bin", "pip"),
    }


def _os_release_text() -> str:
    try:
        return Path("/etc/os-release").read_text(encoding="utf-8").lower()
    except Exception:
        return ""


def _supports_apt_bootstrap() -> bool:
    return sys.platform == "linux" and bool(_which("apt-get")) and bool(_which("sudo"))


def _ensure_pyenv_linux(home: str) -> str:
    pyenv_root = os.path.join(home, ".pyenv")
    if not os.path.isdir(pyenv_root):
        result = _run(["git", "clone", "https://github.com/pyenv/pyenv.git", pyenv_root])
        if result.returncode != 0:
            raise RuntimeError(f"Failed to clone pyenv: {result.stdout}")
    return pyenv_root


def _maybe_install_pyenv_build_deps() -> None:
    if not _supports_apt_bootstrap():
        return
    print(f"[{APP_NAME}] Installing system build dependencies for Python {TARGET_VENV_PYTHON} ...")
    result = subprocess.run(["sudo", "apt-get", "update"])
    if result.returncode != 0:
        raise RuntimeError("Failed to run 'sudo apt-get update'.")
    install_cmd = ["sudo", "apt-get", "install", "-y"] + PYENV_APT_BUILD_DEPS
    result = subprocess.run(install_cmd)
    if result.returncode != 0:
        raise RuntimeError("Failed to install Python build dependencies.")


def ensure_python310_with_pyenv(version: str = TARGET_VENV_PYTHON) -> str:
    home = str(Path.home())
    pyenv_root = _ensure_pyenv_linux(home)
    target_python = os.path.join(pyenv_root, "versions", version, "bin", "python")
    if os.path.isfile(target_python):
        return target_python

    _maybe_install_pyenv_build_deps()
    env = os.environ.copy()
    env["PYENV_ROOT"] = pyenv_root
    env["PATH"] = os.path.join(pyenv_root, "bin") + os.pathsep + env.get("PATH", "")
    command = ["bash", "-lc", f'eval "$(pyenv init -)"; pyenv install -s {version}']
    result = _run(command, env=env)
    if result.returncode != 0:
        raise RuntimeError(f"Failed to install Python {version} via pyenv:\n{result.stdout}")
    return target_python


def _pick_python_for_venv() -> str:
    if _is_target_python(sys.executable):
        return sys.executable
    candidate = _which("python3.10")
    if candidate and _is_target_python(candidate):
        return candidate
    return ensure_python310_with_pyenv(TARGET_VENV_PYTHON)


def ensure_venv(env_name: str = APP_NAME) -> dict[str, str]:
    paths = venv_paths(env_name)
    os.makedirs(paths["app_dir"], exist_ok=True)

    recreate = False
    if os.path.isdir(paths["venv_dir"]) and os.path.isfile(paths["python"]):
        recreate = not _is_target_python(paths["python"])

    if recreate and os.path.isdir(paths["venv_dir"]):
        shutil.rmtree(paths["venv_dir"], ignore_errors=True)

    if recreate or not os.path.isdir(paths["venv_dir"]) or not os.path.isfile(paths["python"]):
        py_for_venv = _pick_python_for_venv()
        result = _run([py_for_venv, "-m", "venv", paths["venv_dir"]])
        if result.returncode != 0:
            raise RuntimeError(f"Failed to create venv: {result.stdout}")
        _run([paths["python"], "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"])

    current_version = _python_version_string(paths["python"])
    if current_version != TARGET_VENV_PYTHON:
        raise RuntimeError(
            f"The venv in {paths['venv_dir']} uses Python {current_version or 'unknown'}, "
            f"but {APP_NAME} requires Python {TARGET_VENV_PYTHON}."
        )
    return paths


def _running_in_target_venv(env_name: str = APP_NAME) -> bool:
    try:
        return Path(sys.executable).resolve() == Path(venv_paths(env_name)["python"]).resolve()
    except Exception:
        return False


def bootstrap_pyqt5(interactive: bool = True, reexec: bool = False, env_name: str = APP_NAME) -> bool:
    if os.environ.get(f"{env_name}_VENV_ACTIVE") == "1" and _running_in_target_venv(env_name):
        return True

    target_paths = venv_paths(env_name)
    if interactive and not _running_in_target_venv(env_name):
        print("\n" + "═" * 62)
        print(f"  {APP_NAME} — Python Environment Setup")
        print("═" * 62)
        print(f"  Current Python : {sys.executable}")
        print(f"  Version        : {sys.version.split()[0]}")
        print(f"  Target venv    : {target_paths['venv_dir']}")
        print(f"  Target Python  : {TARGET_VENV_PYTHON}")
        try:
            response = input("  Continue? [S/n]: ").strip().lower()
            if response in ("n", "nao", "não", "no"):
                return False
        except (EOFError, KeyboardInterrupt):
            return False

    paths = ensure_venv(env_name)
    _ensure_rdkit_numpy_compat(paths["python"])
    if not _has_module(paths["python"], "PyQt5"):
        result = _run([paths["python"], "-m", "pip", "install", "--upgrade", PYTHON_PACKAGES["PyQt5"]])
        if result.returncode != 0:
            print(result.stdout)
            return False

    if reexec:
        current_python = os.path.realpath(sys.executable)
        target_python = os.path.realpath(paths["python"])
        if current_python != target_python:
            env = os.environ.copy()
            env[f"{env_name}_VENV_ACTIVE"] = "1"
            os.execve(paths["python"], [paths["python"]] + sys.argv, env)
    return True


def install_python_packages(pybin: str, packages: list[str]) -> subprocess.CompletedProcess[str]:
    return _run([pybin, "-m", "pip", "install", "--upgrade"] + packages)


def ensure_vina_binaries(bin_dir: str) -> str:
    os.makedirs(bin_dir, exist_ok=True)
    vina_path = os.path.join(bin_dir, "vina_1.2.5_linux_x86_64")
    vina_split_path = os.path.join(bin_dir, "vina_split_1.2.5_linux_x86_64")

    if not os.path.isfile(vina_path):
        result = _run(["wget", "-O", vina_path, VINA_URL])
        if result.returncode != 0:
            raise RuntimeError(f"Failed to download vina:\n{result.stdout}")
        os.chmod(vina_path, 0o755)

    if not os.path.isfile(vina_split_path):
        result = _run(["wget", "-O", vina_split_path, VINA_SPLIT_URL])
        if result.returncode != 0:
            raise RuntimeError(f"Failed to download vina_split:\n{result.stdout}")
        os.chmod(vina_split_path, 0o755)

    return vina_path


def detect_hardware() -> dict[str, Any]:
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "cpu_count": os.cpu_count() or 1,
        "gpu_available": bool(_which("nvidia-smi")),
        "openbabel": bool(_which("obabel")),
        "parallel": bool(_which("parallel")),
        "gnuplot": bool(_which("gnuplot")),
        "adfr": os.path.isfile(os.path.join(str(Path.home()), "ADFRsuite-1.0", "bin", "prepare_receptor")),
    }


class RequirementsInstaller(cast(Any, QDialog)):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    done_signal = pyqtSignal(bool, str)

    def __init__(self, app_dir: Optional[str] = None, parent: Any = None) -> None:
        if not _PYQT_AVAILABLE:
            raise RuntimeError(f"PyQt5 is required to open RequirementsInstaller: {_PYQT_IMPORT_ERROR}")
        super().__init__(parent)
        self.app_dir = app_dir or venv_paths()["app_dir"]
        self.bin_dir = os.path.join(self.app_dir, "bin")
        self.python_rows: list[Any] = []
        self.system_rows: list[Any] = []
        self.special_rows: dict[str, Any] = {}
        self.setWindowTitle(f"{APP_NAME} - Install Requirements")
        self.resize(860, 760)
        self._build_ui()
        self.log_signal.connect(self._append_log)
        self.progress_signal.connect(self._set_progress)
        self.done_signal.connect(self._finish_installation)

    def _build_ui(self) -> None:
        self.setModal(True)
        root = QVBoxLayout(self)

        hardware = detect_hardware()
        header = QLabel(
            f"Environment target: <b>{venv_paths()['venv_dir']}</b><br>"
            f"Python target: <b>{TARGET_VENV_PYTHON}</b><br>"
            f"CPU threads: <b>{hardware['cpu_count']}</b> | NVIDIA GPU: <b>{'yes' if hardware['gpu_available'] else 'no'}</b><br>"
            f"Application directory: <b>{self.app_dir}</b>"
        )
        header.setTextFormat(Qt.RichText)
        root.addWidget(header)

        note = QLabel(
            "Select the Python libraries and external programs used by CODOC. Versions are editable before installation. "
            "Python packages are installed in the dedicated CODOC virtual environment; external programs are installed system-wide."
        )
        note.setWordWrap(True)
        root.addWidget(note)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content_layout = QVBoxLayout(content)

        venv_box = QGroupBox("Virtual Environment")
        venv_layout = QGridLayout(venv_box)
        self.chk_venv = QCheckBox("Create or repair CODOC Python environment")
        self.chk_venv.setChecked(True)
        self.ed_python_version = QLineEdit(TARGET_VENV_PYTHON)
        venv_layout.addWidget(self.chk_venv, 0, 0)
        venv_layout.addWidget(QLabel("Python version"), 0, 1)
        venv_layout.addWidget(self.ed_python_version, 0, 2)
        content_layout.addWidget(venv_box)

        python_box = QGroupBox("Python Libraries")
        python_layout = QGridLayout(python_box)
        python_layout.addWidget(QLabel("Install"), 0, 0)
        python_layout.addWidget(QLabel("Component"), 0, 1)
        python_layout.addWidget(QLabel("Version / spec"), 0, 2)
        for row_idx, (display_name, spec) in enumerate(CODOC_PYTHON_DEFAULTS.items(), start=1):
            checkbox = QCheckBox()
            checkbox.setChecked(display_name == "PyQt5")
            name_label = QLabel(display_name)
            version_edit = QLineEdit(spec)
            python_layout.addWidget(checkbox, row_idx, 0)
            python_layout.addWidget(name_label, row_idx, 1)
            python_layout.addWidget(version_edit, row_idx, 2)
            self.python_rows.append((checkbox, version_edit, display_name))
        content_layout.addWidget(python_box)

        system_box = QGroupBox("External Programs")
        system_layout = QGridLayout(system_box)
        system_layout.addWidget(QLabel("Install"), 0, 0)
        system_layout.addWidget(QLabel("Program"), 0, 1)
        system_layout.addWidget(QLabel("Package name"), 0, 2)
        for row_idx, (display_name, package_name) in enumerate(CODOC_SYSTEM_DEFAULTS.items(), start=1):
            checkbox = QCheckBox()
            name_label = QLabel(display_name)
            package_edit = QLineEdit(package_name)
            system_layout.addWidget(checkbox, row_idx, 0)
            system_layout.addWidget(name_label, row_idx, 1)
            system_layout.addWidget(package_edit, row_idx, 2)
            self.system_rows.append((checkbox, package_edit, display_name))
        content_layout.addWidget(system_box)

        tools_box = QGroupBox("CODOC Tools")
        tools_layout = QGridLayout(tools_box)
        self.chk_vina = QCheckBox("Install AutoDock Vina and vina_split 1.2.5")
        self.chk_adfr = QCheckBox("Validate ADFRsuite / prepare_receptor")
        self.chk_vinagpu = QCheckBox("Validate Vina-GPU executable path")
        self.special_rows = {
            "vina": self.chk_vina,
            "adfr": self.chk_adfr,
            "vinagpu": self.chk_vinagpu,
        }
        tools_layout.addWidget(self.chk_vina, 0, 0, 1, 2)
        tools_layout.addWidget(self.chk_adfr, 1, 0, 1, 2)
        tools_layout.addWidget(self.chk_vinagpu, 2, 0, 1, 2)
        content_layout.addWidget(tools_box)
        content_layout.addStretch(1)

        scroll.setWidget(content)
        root.addWidget(scroll)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        root.addWidget(self.progress)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        root.addWidget(self.log)

        buttons = QHBoxLayout()
        self.btn_install = QPushButton("Install Selected")
        self.btn_install.setStyleSheet(_SS_BTN_PRIMARY)
        self.btn_install.clicked.connect(self.start_installation)
        self.btn_close = QPushButton("Close")
        self.btn_close.setStyleSheet(_SS_BTN_DANGER)
        self.btn_close.clicked.connect(self.reject)
        buttons.addWidget(self.btn_install)
        buttons.addWidget(self.btn_close)
        root.addLayout(buttons)

    def start_installation(self) -> None:
        selected_steps = int(self.chk_venv.isChecked())
        selected_steps += sum(1 for checkbox, _edit, _name in self.python_rows if checkbox.isChecked())
        selected_steps += sum(1 for checkbox, _edit, _name in self.system_rows if checkbox.isChecked())
        selected_steps += sum(1 for checkbox in self.special_rows.values() if checkbox.isChecked())
        if selected_steps == 0:
            QMessageBox.information(self, APP_NAME, "Select at least one requirement.")
            return
        self.progress.setMaximum(selected_steps)
        self.progress.setValue(0)
        self.log.clear()
        self.btn_install.setEnabled(False)
        threading.Thread(target=self._install_selected, daemon=True).start()

    def _install_selected(self) -> None:
        step = 0
        try:
            paths = ensure_venv(APP_NAME)
            pybin = paths["python"]
            if self.chk_venv.isChecked():
                self.log_signal.emit(f"[{APP_NAME}] venv ready at {paths['venv_dir']}\n")
                step += 1
                self.progress_signal.emit(step)

            for checkbox, version_edit, name in self.python_rows:
                if not checkbox.isChecked():
                    continue
                spec = version_edit.text().strip()
                self.log_signal.emit(f"Installing Python package: {name} -> {spec}\n")
                result = install_python_packages(pybin, [spec])
                if result.returncode != 0:
                    raise RuntimeError(result.stdout or f"Failed to install {name}")
                self.log_signal.emit(result.stdout + "\n")
                step += 1
                self.progress_signal.emit(step)

            for checkbox, package_edit, name in self.system_rows:
                if not checkbox.isChecked():
                    continue
                package_name = package_edit.text().strip() or name
                command = ["sudo", "apt-get", "install", "-y", package_name]
                self.log_signal.emit(f"Running: {' '.join(command)}\n")
                result = _run(command)
                if result.returncode != 0:
                    raise RuntimeError(result.stdout or f"Failed to install {package_name}")
                self.log_signal.emit(result.stdout + "\n")
                step += 1
                self.progress_signal.emit(step)

            if self.chk_vina.isChecked():
                vina_path = ensure_vina_binaries(self.bin_dir)
                self.log_signal.emit(f"Vina binaries available in {self.bin_dir}\nPrimary binary: {vina_path}\n")
                step += 1
                self.progress_signal.emit(step)

            if self.chk_adfr.isChecked():
                prepare_receptor = os.path.join(str(Path.home()), "ADFRsuite-1.0", "bin", "prepare_receptor")
                if not os.path.isfile(prepare_receptor):
                    raise RuntimeError(
                        "ADFRsuite was not found. Install it manually and ensure prepare_receptor exists at:\n"
                        f"{prepare_receptor}"
                    )
                self.log_signal.emit(f"ADFRsuite validated at {prepare_receptor}\n")
                step += 1
                self.progress_signal.emit(step)

            if self.chk_vinagpu.isChecked():
                vina_gpu = os.path.join(str(Path.home()), "Vina-GPU-2.1", "AutoDock-Vina-GPU-2.1", "AutoDock-Vina-GPU-2-1")
                if not os.path.isfile(vina_gpu):
                    raise RuntimeError(f"Vina-GPU executable not found at:\n{vina_gpu}")
                self.log_signal.emit(f"Vina-GPU validated at {vina_gpu}\n")
                step += 1
                self.progress_signal.emit(step)

            self.done_signal.emit(True, "Selected requirements were processed successfully.")
        except Exception as exc:
            self.done_signal.emit(False, str(exc))

    def _append_log(self, message: str) -> None:
        self.log.append(message.rstrip())

    def _set_progress(self, value: int) -> None:
        self.progress.setValue(value)

    def _finish_installation(self, ok: bool, message: str) -> None:
        self.btn_install.setEnabled(True)
        if ok:
            QMessageBox.information(self, APP_NAME, message)
        else:
            QMessageBox.critical(self, APP_NAME, message)

