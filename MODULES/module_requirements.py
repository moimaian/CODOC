# -*- coding: utf-8 -*-
# pyright: reportAttributeAccessIssue=false

from __future__ import annotations

import importlib
import importlib.util
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any, Optional, cast

TARGET_VENV_PYTHON = "3.10.12"
APP_NAME = "CODOC"
APP_DIR_NAME = "CODOC"
BOOST_VERSION = "1.84.0"
BOOST_DIR_NAME = "boost_1_84_0"
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
    "pdb2pqr": "pdb2pqr>=3.6",
    "scipy": "scipy>=1.10,<1.14",
    "gemmi": "gemmi>=0.6,<1.0",
    "meeko": "meeko>=0.5,<0.8",
    "dimorphite-dl": "dimorphite-dl>=2.0,<3.0",
    "python-docx": "python-docx>=1.1,<2.0",
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

VINA_VERSION = "1.2.5"
VINA_GPU_VERSION = "2.1"
ADFR_VERSION = "1.0"

# name -> (internal key, pinned version shown/validated in the "Version / spec" field).
# CODOC.py hardcodes the exact binary/directory names below for these tools (e.g. the
# "vina_1.2.5_linux_x86_64" filename, "Vina-GPU-2.1"/"ADFRsuite-1.0" directories), so unlike the
# apt packages above these versions cannot be freely swapped from this dialog alone; the field
# is still editable, but installation is validated against the one version the rest of the app
# actually integrates with.
CODOC_TOOL_DEFAULTS = {
    "AutoDock Vina (+ vina_split)": ("vina", VINA_VERSION),
    "Boost": ("boost", BOOST_VERSION),
    "ADFRsuite / prepare_receptor": ("adfr", ADFR_VERSION),
    "Vina-GPU": ("vinagpu", VINA_GPU_VERSION),
}

VINA_URL = "https://github.com/ccsb-scripps/AutoDock-Vina/releases/download/v1.2.5/vina_1.2.5_linux_x86_64"
VINA_SPLIT_URL = "https://github.com/ccsb-scripps/AutoDock-Vina/releases/download/v1.2.5/vina_split_1.2.5_linux_x86_64"
VINA_GPU_ARCHIVE = "Vina-GPU-2.1.zip"
BOOST_ARCHIVE = "boost_1_84_0.tar.gz"

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


def _run(
    cmd: list[str],
    check: bool = False,
    env: Optional[dict[str, str]] = None,
    cwd: Optional[str] = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=check, env=env, cwd=cwd)


def _which(name: str) -> Optional[str]:
    return shutil.which(name)


def _apt_candidate_version(package_name: str) -> Optional[str]:
    apt_cache = _which("apt-cache")
    if not apt_cache:
        return None
    env = os.environ.copy()
    env["LC_ALL"] = "C"
    result = _run([apt_cache, "policy", package_name], env=env)
    if result.returncode != 0:
        return None
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if stripped.startswith("Candidate:"):
            version = stripped.split(":", 1)[1].strip()
            return version if version and version != "(none)" else None
    return None


def _system_package_spec(package_name: str) -> str:
    version = _apt_candidate_version(package_name)
    return f"{package_name}={version}" if version else package_name


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


def boost_paths(home_dir: Optional[str] = None) -> dict[str, str]:
    home_path = home_dir or str(Path.home())
    boost_dir = os.path.join(home_path, BOOST_DIR_NAME)
    return {
        "root": boost_dir,
        "bootstrap": os.path.join(boost_dir, "bootstrap.sh"),
        "version_header": os.path.join(boost_dir, "boost", "version.hpp"),
        "installed_version_header": os.path.join(boost_dir, "include", "boost", "version.hpp"),
    }


def get_boost_version(home_dir: Optional[str] = None) -> Optional[str]:
    paths = boost_paths(home_dir)
    header_path = paths["installed_version_header"]
    if not os.path.isfile(header_path):
        header_path = paths["version_header"]
    if not os.path.isfile(header_path):
        return None
    try:
        for line in Path(header_path).read_text(encoding="utf-8", errors="ignore").splitlines():
            match = line.strip()
            if match.startswith("#define BOOST_VERSION"):
                parts = match.split()
                if len(parts) >= 3 and parts[2].isdigit():
                    version_number = int(parts[2])
                    major = version_number // 100000
                    minor = (version_number // 100) % 1000
                    patch = version_number % 100
                    return f"{major}.{minor}.{patch}"
            if match.startswith("#define BOOST_LIB_VERSION"):
                parts = match.split('"')
                if len(parts) >= 2:
                    return parts[1].replace("_", ".")
    except Exception:
        return None
    return None


def ensure_boost_installation(app_dir: str) -> str:
    paths = boost_paths()
    if get_boost_version() == BOOST_VERSION:
        return paths["root"]

    archive_path = os.path.join(app_dir, "bin", BOOST_ARCHIVE)
    if not os.path.isfile(archive_path):
        raise RuntimeError(f"Bundled Boost archive not found at:\n{archive_path}")

    with tempfile.TemporaryDirectory(prefix="codoc-boost-") as temp_dir:
        shutil.unpack_archive(archive_path, temp_dir)
        extracted_dir = os.path.join(temp_dir, BOOST_DIR_NAME)
        if not os.path.isdir(extracted_dir):
            raise RuntimeError(f"Could not locate {BOOST_DIR_NAME} inside the bundled archive.")
        if os.path.isdir(paths["root"]):
            shutil.rmtree(paths["root"])
        shutil.copytree(extracted_dir, paths["root"])

    bootstrap = paths["bootstrap"]
    if not os.path.isfile(bootstrap):
        raise RuntimeError(f"Boost bootstrap script not found at:\n{bootstrap}")

    commands = [
        [bootstrap, f"--prefix={paths['root']}"] ,
        ["./b2"],
        ["./b2", "headers"],
        ["./b2", "install"],
    ]
    for command in commands:
        result = _run(command, cwd=paths["root"])
        if result.returncode != 0:
            raise RuntimeError(result.stdout or f"Failed running {' '.join(command)}")
    version = get_boost_version()
    if version != BOOST_VERSION:
        raise RuntimeError(
            f"Boost installation finished but version {BOOST_VERSION} was not detected in {paths['root']}."
        )
    return paths["root"]


def vina_gpu_paths(home_dir: Optional[str] = None) -> dict[str, str]:
    home_path = home_dir or str(Path.home())
    install_root = os.path.join(home_path, "Vina-GPU-2.1")
    install_dir = os.path.join(install_root, "AutoDock-Vina-GPU-2.1")
    executable = os.path.join(install_dir, "AutoDock-Vina-GPU-2-1")
    source_executable = os.path.join(install_dir, "AutoDock-Vina-GPU-2-1_source")
    makefile = os.path.join(install_dir, "Makefile")
    return {
        "root": install_root,
        "install_dir": install_dir,
        "executable": executable,
        "source_executable": source_executable,
        "makefile": makefile,
    }


def get_vina_gpu_version(executable: Optional[str] = None) -> Optional[str]:
    vina_gpu = executable or vina_gpu_paths()["executable"]
    if not os.path.isfile(vina_gpu):
        return None
    result = _run([vina_gpu, "--version"])
    if result.returncode != 0:
        return None
    for line in result.stdout.splitlines():
        version = line.strip()
        if version:
            return version
    return None


def detect_opencl_devices() -> list[dict[str, Any]]:
    clinfo = _which("clinfo")
    if not clinfo:
        return []
    result = _run([clinfo])
    if result.returncode != 0:
        return []

    devices: list[dict[str, Any]] = []
    platform_meta: dict[str, Any] = {}
    current_platform_id = -1
    current_device: Optional[dict[str, Any]] = None
    current_device_id = -1

    def finalize_current_device() -> None:
        nonlocal current_device
        if current_device is not None:
            devices.append(current_device)
            current_device = None

    for raw_line in result.stdout.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped:
            continue

        platform_match = re.match(r"^Platform Name\s+(.+)$", stripped)
        if platform_match:
            platform_meta["platform_name"] = platform_match.group(1).strip()
            continue

        vendor_match = re.match(r"^Platform Vendor\s+(.+)$", stripped)
        if vendor_match:
            platform_meta["platform_vendor"] = vendor_match.group(1).strip()
            continue

        version_match = re.match(r"^Platform Version\s+(.+)$", stripped)
        if version_match:
            platform_meta["platform_version"] = version_match.group(1).strip()
            continue

        devices_match = re.match(r"^Number of devices\s+(\d+)$", stripped)
        if devices_match:
            finalize_current_device()
            current_platform_id += 1
            current_device_id = -1
            continue

        device_name_match = re.match(r"^Device Name\s+(.+)$", stripped)
        if device_name_match:
            finalize_current_device()
            current_device_id += 1
            current_device = {
                "platform_id": current_platform_id,
                "platform_name": platform_meta.get("platform_name", f"Platform {current_platform_id}"),
                "platform_vendor": platform_meta.get("platform_vendor", ""),
                "platform_version": platform_meta.get("platform_version", ""),
                "device_id": current_device_id,
                "device_name": device_name_match.group(1).strip(),
                "device_type": "",
                "compute_units": 0,
                "clock_mhz": 0,
                "memory_bytes": 0,
            }
            continue

        if current_device is None:
            continue

        device_type_match = re.match(r"^Device Type\s+(.+)$", stripped)
        if device_type_match:
            current_device["device_type"] = device_type_match.group(1).strip()
            continue

        compute_units_match = re.match(r"^Max compute units\s+(\d+)$", stripped)
        if compute_units_match:
            current_device["compute_units"] = int(compute_units_match.group(1))
            continue

        clock_match = re.match(r"^Max clock frequency\s+(\d+)MHz$", stripped)
        if clock_match:
            current_device["clock_mhz"] = int(clock_match.group(1))
            continue

        memory_match = re.match(r"^Global memory size\s+(\d+)\s+\(([^)]+)\)$", stripped)
        if memory_match:
            current_device["memory_bytes"] = int(memory_match.group(1))
            continue

    finalize_current_device()
    return devices


def _replace_exact(content: str, old: str, new: str, file_path: str) -> str:
    if old in content:
        return content.replace(old, new, 1)
    if new in content:
        return content
    raise RuntimeError(f"Expected snippet not found while patching {file_path}")


def _replace_regex(content: str, pattern: str, replacement: str, file_path: str) -> str:
    updated, count = re.subn(pattern, lambda _match: replacement, content, count=1, flags=re.S)
    if count:
        return updated
    if replacement in content:
        return content
    raise RuntimeError(f"Expected pattern not found while patching {file_path}")


def _patch_vina_gpu_backend_sources(install_dir: str) -> None:
    wrapcl_header = os.path.join(install_dir, "OpenCL", "inc", "wrapcl.h")
    wrapcl_source = os.path.join(install_dir, "OpenCL", "src", "wrapcl.cpp")
    main_header = os.path.join(install_dir, "lib", "main_procedure_cl.h")
    main_source = os.path.join(install_dir, "lib", "main_procedure_cl.cpp")
    main_cpp = os.path.join(install_dir, "main", "main.cpp")

    header_content = Path(wrapcl_header).read_text(encoding="utf-8")
    header_content = _replace_exact(
        header_content,
        "void SetupPlatform(cl_platform_id** platforms, cl_int* gpu_platform_id);\n"
        "void SetupDevice(cl_platform_id* platforms, cl_device_id** devices, cl_int gpu_platform_id);\n",
        "void SetupPlatform(cl_platform_id** platforms, cl_int* gpu_platform_id, cl_int requested_platform_id);\n"
        "void SetupDevice(cl_platform_id* platforms, cl_device_id** devices, cl_int gpu_platform_id, cl_int requested_device_id);\n",
        wrapcl_header,
    )
    Path(wrapcl_header).write_text(header_content, encoding="utf-8")

    wrapcl_content = Path(wrapcl_source).read_text(encoding="utf-8")
    wrapcl_content = _replace_exact(
        wrapcl_content,
        "void SetupPlatform(cl_platform_id** platforms, cl_int* gpu_platform) {",
        "void SetupPlatform(cl_platform_id** platforms, cl_int* gpu_platform, cl_int requested_platform_id) {",
        wrapcl_source,
    )
    wrapcl_content = _replace_exact(
        wrapcl_content,
        "void SetupDevice(cl_platform_id* platforms, cl_device_id** devices, cl_int gpu_platform) {",
        "void SetupDevice(cl_platform_id* platforms, cl_device_id** devices, cl_int gpu_platform, cl_int requested_device_id) {",
        wrapcl_source,
    )
    wrapcl_content = _replace_exact(
        wrapcl_content,
        "    err = clGetPlatformIDs(0, NULL, &num_platform); checkErr(err);\n"
        "    *platforms = (cl_platform_id*)malloc(sizeof(cl_platform_id) * (num_platform));\n"
        "    err = clGetPlatformIDs(num_platform, *platforms, NULL); checkErr(err);\n",
        "    err = clGetPlatformIDs(0, NULL, &num_platform); checkErr(err);\n"
        "    *platforms = (cl_platform_id*)malloc(sizeof(cl_platform_id) * (num_platform));\n"
        "    err = clGetPlatformIDs(num_platform, *platforms, NULL); checkErr(err);\n"
        "    if (requested_platform_id >= 0) {\n"
        "        if (requested_platform_id >= (cl_int)num_platform) {\n"
        "            printf(\"Invalid OpenCL platform_id %d\\n\", requested_platform_id); fflush(stdout);\n"
        "            exit(-1);\n"
        "        }\n"
        "        *gpu_platform = requested_platform_id;\n"
        "        err = clGetPlatformInfo((*platforms)[*gpu_platform], CL_PLATFORM_NAME, 0, NULL, &size); checkErr(err);\n"
        "        char* platform_name = (char*)malloc(sizeof(char) * size);\n"
        "        err = clGetPlatformInfo((*platforms)[*gpu_platform], CL_PLATFORM_NAME, size, platform_name, NULL); checkErr(err);\n"
        "        printf(\"GPU OpenCL Platform: %s\", platform_name);fflush(stdout);\n"
        "        free(platform_name);\n"
        "        return;\n"
        "    }\n",
        wrapcl_source,
    )
    wrapcl_content = _replace_regex(
        wrapcl_content,
        r"void SetupDevice\(cl_platform_id\* platforms, cl_device_id\*\* devices, cl_int gpu_platform, cl_int requested_device_id\) \{.*?\n\}\n\n\nvoid SetupContext",
        """
void SetupDevice(cl_platform_id* platforms, cl_device_id** devices, cl_int gpu_platform, cl_int requested_device_id) {
    cl_uint num_device;
    cl_int err;
    size_t device_name_size;
    cl_ulong mem_size;
    cl_int N = gpu_platform;
#ifdef INTEL_CPU_PLATFORM
    err = clGetDeviceIDs(platforms[N], CL_DEVICE_TYPE_CPU, 0, NULL, &num_device); checkErr(err);
#else
    err = clGetDeviceIDs(platforms[N], CL_DEVICE_TYPE_GPU, 0, NULL, &num_device); checkErr(err);
#endif
    cl_device_id* all_devices = (cl_device_id*)malloc(sizeof(cl_device_id) * num_device);
#ifdef INTEL_CPU_PLATFORM
    err = clGetDeviceIDs(platforms[N], CL_DEVICE_TYPE_CPU, num_device, all_devices, NULL); checkErr(err);
#else
    err = clGetDeviceIDs(platforms[N], CL_DEVICE_TYPE_GPU, num_device, all_devices, NULL); checkErr(err);
#endif
    for (int i = 0; i < num_device; i++) {
        err = clGetDeviceInfo(all_devices[i], CL_DEVICE_NAME, 0, NULL, &device_name_size); checkErr(err);
        char* device_name = (char*)malloc(sizeof(char) * device_name_size);
        err = clGetDeviceInfo(all_devices[i], CL_DEVICE_NAME, device_name_size, device_name, NULL); checkErr(err);
        printf("\\nGPU Device %d: %s", i, device_name);
        free(device_name);
#ifdef DISPLAY_ADDITION_INFO
        err = clGetDeviceInfo(all_devices[i], CL_DEVICE_GLOBAL_MEM_SIZE, sizeof(cl_ulong), &mem_size, NULL);
        printf("Platform %d global memory size:%f GB\\n", N, (double)mem_size/1000000000);
        err = clGetDeviceInfo(all_devices[i], CL_DEVICE_LOCAL_MEM_SIZE, sizeof(cl_ulong), &mem_size, NULL);
        printf("Platform %d local memory size:%f KB\\n", N, (double)mem_size / 1000);
#endif
    }
    cl_int selected_device_id = requested_device_id >= 0 ? requested_device_id : 0;
    if (selected_device_id >= (cl_int)num_device) {
        printf("Invalid OpenCL device_id %d for platform %d\\n", selected_device_id, N); fflush(stdout);
        free(all_devices);
        exit(-1);
    }
    *devices = (cl_device_id*)malloc(sizeof(cl_device_id));
    (*devices)[0] = all_devices[selected_device_id];
    printf("\\nUsing OpenCL selection: platform_id=%d device_id=%d\\n", N, selected_device_id); fflush(stdout);
    free(all_devices);
}


void SetupContext""",
        wrapcl_source,
    )
    Path(wrapcl_source).write_text(wrapcl_content, encoding="utf-8")

    main_header_content = Path(main_header).read_text(encoding="utf-8")
    main_header_content = _replace_regex(
        main_header_content,
        r"void main_procedure_cl\(cache& c, const std::vector<model>& ms, const precalculate& p, const parallel_mc par,\s*const vec& corner1, const vec& corner2, const int seed, std::vector<output_container>& out, std::string opencl_binary_path,\s*const std::vector<std::vector<std::string>> ligand_names, const int rilc_bfgs, std::chrono::duration<double> startup_time\);",
        "void main_procedure_cl(cache& c, const std::vector<model>& ms, const precalculate& p, const parallel_mc par,\n\tconst vec& corner1, const vec& corner2, const int seed, std::vector<output_container>& out, std::string opencl_binary_path,\n\tconst int opencl_platform_id, const int opencl_device_id,\n\tconst std::vector<std::vector<std::string>> ligand_names, const int rilc_bfgs, std::chrono::duration<double> startup_time);",
        main_header,
    )
    Path(main_header).write_text(main_header_content, encoding="utf-8")

    main_source_content = Path(main_source).read_text(encoding="utf-8")
    main_source_content = _replace_regex(
        main_source_content,
        r"void main_procedure_cl\(cache &c, const std::vector<model> &ms, const precalculate &p, const parallel_mc par,\s*const vec &corner1, const vec &corner2, const int seed, std::vector<output_container> &outs, std::string opencl_binary_path,\s*const std::vector<std::vector<std::string>> ligand_names, const int rilc_bfgs, std::chrono::duration<double> startup_time\)\n",
        "void main_procedure_cl(cache &c, const std::vector<model> &ms, const precalculate &p, const parallel_mc par,\n                                           const vec &corner1, const vec &corner2, const int seed, std::vector<output_container> &outs, std::string opencl_binary_path,\n                                           const int opencl_platform_id, const int opencl_device_id,\n                                           const std::vector<std::vector<std::string>> ligand_names, const int rilc_bfgs, std::chrono::duration<double> startup_time)\n",
        main_source,
    )
    main_source_content = _replace_regex(
        main_source_content,
        r"cl_command_queue queue;\s*cl_int gpu_platform_id = 0;\s*SetupPlatform\(&platforms, &gpu_platform_id\);\s*SetupDevice\(platforms, &devices, gpu_platform_id\);\s*SetupContext\(platforms, devices, &context, 1, gpu_platform_id\);\s*SetupQueue\(&queue, context, devices\);",
        "cl_command_queue queue;\n\tcl_int gpu_platform_id = opencl_platform_id;\n\tSetupPlatform(&platforms, &gpu_platform_id, opencl_platform_id);\n\tSetupDevice(platforms, &devices, gpu_platform_id, opencl_device_id);\n\tSetupContext(platforms, devices, &context, 1, gpu_platform_id);\n\tSetupQueue(&queue, context, devices);",
        main_source,
    )
    Path(main_source).write_text(main_source_content, encoding="utf-8")

    main_cpp_content = Path(main_cpp).read_text(encoding="utf-8")
    main_cpp_content = _replace_regex(
        main_cpp_content,
        r"int search_depth = 0;\s*int thread = 8000;\s*std::string ligand_directory, output_directory, opencl_binary_path;\s*opencl_binary_path = \"\.\";\s*int rilc_bfgs = 1;",
        "int search_depth = 0;\n\t\tint thread = 8000;\n\t\tint opencl_platform_id = -1;\n\t\tint opencl_device_id = -1;\n\t\tstd::string ligand_directory, output_directory, opencl_binary_path;\n\t\topencl_binary_path = \".\";\n\t\tint rilc_bfgs = 1;",
        main_cpp,
    )
    main_cpp_content = _replace_regex(
        main_cpp_content,
        r"\(\"search_depth\", value<int>\(&search_depth\), \"the number of search depth in monte carlo\"\)\s*\(\"opencl_binary_path\", value<std::string>\(&opencl_binary_path\)->default_value\(opencl_binary_path\), \"opencl precompiled binary file path\"\)\s*\(\"rilc_bfgs\",value<int>\(&rilc_bfgs\)->default_value\(rilc_bfgs\), \"rilc_bfgs enable or not\"\)",
        "(\"search_depth\", value<int>(&search_depth), \"the number of search depth in monte carlo\")\n\t\t\t(\"opencl_binary_path\", value<std::string>(&opencl_binary_path)->default_value(opencl_binary_path), \"opencl precompiled binary file path\")\n\t\t\t(\"platform_id\", value<int>(&opencl_platform_id)->default_value(opencl_platform_id), \"OpenCL platform index\")\n\t\t\t(\"device_id\", value<int>(&opencl_device_id)->default_value(opencl_device_id), \"OpenCL device index within the selected platform\")\n\t\t\t(\"rilc_bfgs\",value<int>(&rilc_bfgs)->default_value(rilc_bfgs), \"rilc_bfgs enable or not\")",
        main_cpp,
    )
    main_cpp_content = _replace_regex(
        main_cpp_content,
        r"void main_procedure\(std::vector<model>& ms, const boost::optional<model>& ref, // m is non-const \(FIXME\?\)\s*const std::vector<std::string>& out_names,\s*bool score_only, bool local_only, bool randomize_only, bool no_cache,\s*const grid_dims& gd, int exhaustiveness,\s*const flv& weights,\s*int cpu, int seed, int verbosity, sz num_modes, fl energy_range,\s*tee& log, int search_depth, int thread, std::string opencl_binary_path, std::vector<std::vector<std::string>> ligand_names, int rilc_bfgs, std::chrono::duration<double> startup_time\) \{",
        "void main_procedure(std::vector<model>& ms, const boost::optional<model>& ref, // m is non-const (FIXME?)\n\t\tconst std::vector<std::string>& out_names,\n\t\tbool score_only, bool local_only, bool randomize_only, bool no_cache,\n\t\tconst grid_dims& gd, int exhaustiveness,\n\t\tconst flv& weights,\n\t\tint cpu, int seed, int verbosity, sz num_modes, fl energy_range, \n\t\ttee& log, int search_depth, int thread, std::string opencl_binary_path, int opencl_platform_id, int opencl_device_id, std::vector<std::vector<std::string>> ligand_names, int rilc_bfgs, std::chrono::duration<double> startup_time) {",
        main_cpp,
    )
    main_cpp_content = _replace_regex(
        main_cpp_content,
        r"main_procedure_cl\(c, ms, prec, par, corner1, corner2, seed, out_conts, opencl_binary_path, ligand_names, rilc_bfgs, startup_time\);",
        "main_procedure_cl(c, ms, prec, par, corner1, corner2, seed, out_conts, opencl_binary_path, opencl_platform_id, opencl_device_id, ligand_names, rilc_bfgs, startup_time);",
        main_cpp,
    )
    main_cpp_content = _replace_regex(
        main_cpp_content,
        r"main_procedure\(ms, ref,\s*out_names_valid,\s*score_only, local_only, randomize_only, false, // no_cache == false\s*gd, exhaustiveness,\s*weights,\s*cpu, seed, verbosity, max_modes_sz, energy_range, log, search_depth, thread, opencl_binary_path, ligand_names, rilc_bfgs, startup_time\);",
        "main_procedure(ms, ref,\n\t\t\tout_names_valid,\n\t\t\tscore_only, local_only, randomize_only, false, // no_cache == false\n\t\t\tgd, exhaustiveness,\n\t\t\tweights,\n\t\t\tcpu, seed, verbosity, max_modes_sz, energy_range, log, search_depth, thread, opencl_binary_path, opencl_platform_id, opencl_device_id, ligand_names, rilc_bfgs, startup_time);",
        main_cpp,
    )
    Path(main_cpp).write_text(main_cpp_content, encoding="utf-8")


def _patch_vina_gpu_makefile(makefile_path: str, install_dir: str) -> None:
    boost_root = boost_paths()["root"]
    opencl_root = "/usr/local/cuda"
    content = (
        "# Need to be modified according to different users\n"
        f"WORK_DIR={install_dir}\n"
        f"BOOST_LIB_PATH={boost_root}\n"
        f"OPENCL_LIB_PATH={opencl_root}\n"
        "OPENCL_VERSION=-DOPENCL_3_0\n"
        "GPU_PLATFORM=\n"
        "DOCKING_BOX_SIZE=-DSMALL_BOX\n"
        "# CUSTOM_OPT=\n\n"
        "# Should not be modified\n"
        "BOOST_INC_PATH=-I$(BOOST_LIB_PATH) -I$(BOOST_LIB_PATH)/boost \n"
        "VINA_GPU_INC_PATH=-I$(WORK_DIR)/lib -I$(WORK_DIR)/OpenCL/inc \n"
        "OPENCL_INC_PATH=-I$(OPENCL_LIB_PATH)/include\n"
        "LIB1=-l:libboost_program_options.a -l:libboost_system.a -l:libboost_filesystem.a -lOpenCL\n"
        "LIB2=-lstdc++ -lstdc++fs\n"
        "LIB3=-lm -lpthread\n"
        "LIB_PATH=-L$(BOOST_LIB_PATH)/stage/lib -L$(OPENCL_LIB_PATH)/lib64\n"
        "SRC=./lib/*.cpp ./OpenCL/src/wrapcl.cpp $(BOOST_LIB_PATH)/libs/thread/src/pthread/thread.cpp $(BOOST_LIB_PATH)/libs/thread/src/pthread/once.cpp\n"
        "MACRO=$(OPENCL_VERSION) $(GPU_PLATFORM) $(DOCKING_BOX_SIZE) -DBOOST_TIMER_ENABLE_DEPRECATED $(CUSTOM_OPT)\n"
        "all:out\n"
        "out:./main/main.cpp\n"
        "\tgcc -o AutoDock-Vina-GPU-2-1 $(BOOST_INC_PATH) $(VINA_GPU_INC_PATH) $(OPENCL_INC_PATH) ./main/main.cpp -O3 $(SRC) $(LIB1) $(LIB2) $(LIB3) $(LIB_PATH) $(MACRO) $(OPTION) -DNDEBUG\n"
        "source:./main/main.cpp\n"
        "\tgcc -o AutoDock-Vina-GPU-2-1 $(BOOST_INC_PATH) $(VINA_GPU_INC_PATH) $(OPENCL_INC_PATH) ./main/main.cpp -O3 $(SRC) $(LIB1) $(LIB2) $(LIB3) $(LIB_PATH) $(MACRO) $(OPTION) -DNDEBUG -DBUILD_KERNEL_FROM_SOURCE \n"
        "debug:./main/main.cpp\n"
        "\tgcc -o AutoDock-Vina-GPU-2-1 $(BOOST_INC_PATH) $(VINA_GPU_INC_PATH) $(OPENCL_INC_PATH) ./main/main.cpp -g $(SRC) $(LIB1) $(LIB2) $(LIB3) $(LIB_PATH) $(MACRO) $(OPTION) -DBUILD_KERNEL_FROM_SOURCE\n"
        "clean:\n"
        "\trm -f AutoDock-Vina-GPU-2-1\n"
    )
    Path(makefile_path).write_text(content, encoding="utf-8")


def _rebuild_vina_gpu(install_dir: str) -> None:
    makefile_path = vina_gpu_paths()["makefile"]
    _patch_vina_gpu_backend_sources(install_dir)
    _patch_vina_gpu_makefile(makefile_path, install_dir)
    for command in (["make", "clean"], ["make", "source"], ["make", "clean"], ["make", "out"]):
        result = _run(command, cwd=install_dir)
        if result.returncode != 0:
            raise RuntimeError(result.stdout or f"Failed running {' '.join(command)} in {install_dir}")


def ensure_vina_gpu_installation(app_dir: str) -> str:
    paths = vina_gpu_paths()
    archive_path = os.path.join(app_dir, "bin", VINA_GPU_ARCHIVE)
    if not os.path.isfile(archive_path):
        raise RuntimeError(f"Bundled Vina-GPU archive not found at:\n{archive_path}")

    if not os.path.isdir(paths["install_dir"]):
        with tempfile.TemporaryDirectory(prefix="codoc-vinagpu-") as temp_dir:
            shutil.unpack_archive(archive_path, temp_dir)
            extracted_dir: Optional[Path] = None
            for candidate in Path(temp_dir).rglob("AutoDock-Vina-GPU-2.1"):
                if candidate.is_dir():
                    extracted_dir = candidate
                    break
            if extracted_dir is None:
                raise RuntimeError("Could not locate AutoDock-Vina-GPU-2.1 inside the bundled archive.")

            os.makedirs(paths["root"], exist_ok=True)
            if os.path.isdir(paths["install_dir"]):
                shutil.rmtree(paths["install_dir"])
            shutil.copytree(str(extracted_dir), paths["install_dir"])

    _rebuild_vina_gpu(paths["install_dir"])

    for binary_path in (paths["executable"], paths["source_executable"]):
        if os.path.isfile(binary_path):
            os.chmod(binary_path, 0o755)

    version = get_vina_gpu_version(paths["executable"])
    if not version:
        raise RuntimeError(
            "Vina-GPU was extracted but the executable is not functional at:\n"
            f"{paths['executable']}"
        )
    return paths["executable"]


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
        self.tool_rows: list[Any] = []
        self.setWindowTitle(f"{APP_NAME} - Install Requirements")
        self.resize(860, 760)
        self._build_ui()
        self.log_signal.connect(self._append_log)
        self.progress_signal.connect(self._set_progress)
        self.done_signal.connect(self._finish_installation)

    def _build_ui(self) -> None:
        self.setModal(True)
        root = QVBoxLayout(self)

        header = QLabel(
            f"Environment target: <b>{venv_paths()['venv_dir']}</b><br>"
            f"Application directory: <b>{self.app_dir}</b>"
        )
        header.setTextFormat(Qt.RichText)
        root.addWidget(header)

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
        system_layout.addWidget(QLabel("Version / spec"), 0, 2)
        row_idx = 1
        for display_name, package_name in CODOC_SYSTEM_DEFAULTS.items():
            checkbox = QCheckBox()
            name_label = QLabel(display_name)
            package_edit = QLineEdit(_system_package_spec(package_name))
            system_layout.addWidget(checkbox, row_idx, 0)
            system_layout.addWidget(name_label, row_idx, 1)
            system_layout.addWidget(package_edit, row_idx, 2)
            self.system_rows.append((checkbox, package_edit, display_name))
            row_idx += 1
        for display_name, (tool_key, version) in CODOC_TOOL_DEFAULTS.items():
            checkbox = QCheckBox()
            checkbox.setChecked(tool_key == "vina")
            name_label = QLabel(display_name)
            version_edit = QLineEdit(version)
            system_layout.addWidget(checkbox, row_idx, 0)
            system_layout.addWidget(name_label, row_idx, 1)
            system_layout.addWidget(version_edit, row_idx, 2)
            self.tool_rows.append((checkbox, version_edit, tool_key))
            row_idx += 1
        content_layout.addWidget(system_box)
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
        selected_steps += sum(1 for checkbox, _edit, _key in self.tool_rows if checkbox.isChecked())
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
        pinned_tool_versions = {key: version for _name, (key, version) in CODOC_TOOL_DEFAULTS.items()}
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

            for checkbox, version_edit, tool_key in self.tool_rows:
                if not checkbox.isChecked():
                    continue
                spec = version_edit.text().strip()
                pinned_version = pinned_tool_versions[tool_key]
                if spec and spec != pinned_version:
                    raise RuntimeError(
                        f"CODOC currently only integrates with version {pinned_version} of this tool "
                        f"(binary/directory names are hardcoded to it elsewhere in the app); "
                        f"got '{spec}'. Set the field back to {pinned_version} or leave it unchanged."
                    )

                if tool_key == "vina":
                    vina_path = ensure_vina_binaries(self.bin_dir)
                    self.log_signal.emit(f"Vina binaries available in {self.bin_dir}\nPrimary binary: {vina_path}\n")
                elif tool_key == "boost":
                    boost_root = ensure_boost_installation(self.app_dir)
                    boost_version = get_boost_version() or "installed"
                    self.log_signal.emit(f"Boost installed at {boost_root}\nVersion: {boost_version}\n")
                elif tool_key == "adfr":
                    prepare_receptor = os.path.join(str(Path.home()), f"ADFRsuite-{pinned_version}", "bin", "prepare_receptor")
                    if not os.path.isfile(prepare_receptor):
                        raise RuntimeError(
                            "ADFRsuite was not found. Install it manually and ensure prepare_receptor exists at:\n"
                            f"{prepare_receptor}"
                        )
                    self.log_signal.emit(f"ADFRsuite validated at {prepare_receptor}\n")
                elif tool_key == "vinagpu":
                    vina_gpu = ensure_vina_gpu_installation(self.app_dir)
                    vina_gpu_version = get_vina_gpu_version(vina_gpu) or "installed"
                    self.log_signal.emit(f"Vina-GPU installed or rebuilt at {vina_gpu}\nVersion: {vina_gpu_version}\n")

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

