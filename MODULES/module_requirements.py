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
from typing import Any, List, Optional, cast

from MODULES import platform_utils
from MODULES.platform_utils import IS_WINDOWS

platform_utils.install_subprocess_defaults()      # Windows: filhos sem janela de console (no-op no Linux)

# Python exato do venv. No Linux é compilado pelo pyenv (3.10.12); no Windows vem do instalador
# oficial do python.org, e a 3.10.11 é a última 3.10 que ele distribui com instalador binário.
TARGET_VENV_PYTHON_LINUX = "3.10.12"
TARGET_VENV_PYTHON_WINDOWS = "3.10.11"
TARGET_VENV_PYTHON = TARGET_VENV_PYTHON_WINDOWS if IS_WINDOWS else TARGET_VENV_PYTHON_LINUX
PYTHON_WINDOWS_INSTALLER_URL = (
    f"https://www.python.org/ftp/python/{TARGET_VENV_PYTHON_WINDOWS}/"
    f"python-{TARGET_VENV_PYTHON_WINDOWS}-amd64.exe"
)
PYTHON_WINGET_ID = "Python.Python.3.10"
# Windows: runtime Visual C++ que as DLLs do Qt5 (PyQt5), do NumPy e do RDKit exigem.
VCREDIST_WINGET_ID = "Microsoft.VCRedist.2015+.x64"
VCREDIST_DOWNLOAD_URL = "https://aka.ms/vs/17/release/vc_redist.x64.exe"
JAVA_WINGET_ID = "Microsoft.OpenJDK.17"
OPENBABEL_PIP_SPEC = "openbabel-wheel>=3.1"        # Windows: obabel.exe vem no pacote pip, em Scripts\
# Códigos de saída do winget que também significam "já está instalado" (PACKAGE_ALREADY_INSTALLED e
# UPDATE_NOT_APPLICABLE); quem chama confere o resultado depois.
_WINGET_ALREADY_OK = {0, 0x8A150061 - (1 << 32), 0x8A15010D - (1 << 32)}
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
    "propka": "propka>=3.5,<4.0",
    "scipy": "scipy>=1.10,<1.14",
    "gemmi": "gemmi>=0.6,<1.0",
    "meeko": "meeko>=0.5,<0.8",
    "dimorphite-dl": "dimorphite-dl>=2.0,<3.0",
    "python-docx": "python-docx>=1.1,<2.0",
}

# display name -> apt package. Besides Open Babel (an engine), these are what the other tools
# need to be installed and to work: Java for P2Rank, clinfo for the OpenCL device lists, wget for
# every download of this dialog, the compilers and the OpenCL headers to build Boost and Vina-GPU,
# xdg-utils for the "Open ... folder" buttons.
CODOC_SYSTEM_DEFAULTS = {
    "openbabel": "openbabel",
    "Java JRE 17 (P2Rank)": "openjdk-17-jre-headless",
    "clinfo (OpenCL devices)": "clinfo",
    "wget (downloads)": "wget",
    "build-essential (Boost, Vina-GPU)": "build-essential",
    "opencl-headers (Vina-GPU)": "opencl-headers",
    "ocl-icd-opencl-dev (Vina-GPU)": "ocl-icd-opencl-dev",
    "xdg-utils (open folders)": "xdg-utils",
}

VINA_VERSION = "1.2.5"
VINA_GPU_VERSION = "2.1"
ADFR_VERSION = "1.0"
P2RANK_VERSION = "2.5.1"
JAVA_MIN_MAJOR = 17          # P2Rank 2.5 needs Java 17 or newer

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
    "P2Rank": ("p2rank", P2RANK_VERSION),
}


def tool_defaults() -> dict[str, tuple[str, str]]:
    """Programas externos que o sistema atual precisa instalar. No Windows não há Boost: o Vina-GPU vem
    do zip com os executáveis já compilados."""
    if IS_WINDOWS:
        return {name: value for name, value in CODOC_TOOL_DEFAULTS.items() if value[0] != "boost"}
    return dict(CODOC_TOOL_DEFAULTS)


def system_package_rows() -> list[tuple[str, str, str]]:
    """(nome exibido, pacote/especificação, tipo) das linhas de pacotes do sistema de External Programs:
    Linux -> pacotes do apt; Windows -> o equivalente (winget, pip no venv ou o instalador da Microsoft)."""
    if IS_WINDOWS:
        return [
            ("Open Babel (obabel)", OPENBABEL_PIP_SPEC, "pip"),
            ("Java JRE 17 (P2Rank)", JAVA_WINGET_ID, "winget"),
            ("Visual C++ runtime (Qt5)", VCREDIST_WINGET_ID, "vcredist"),
        ]
    return [(name, _system_package_spec(package), "apt") for name, package in CODOC_SYSTEM_DEFAULTS.items()]

VINA_RELEASE_URL = "https://github.com/ccsb-scripps/AutoDock-Vina/releases/download/v1.2.5"
VINA_URL = f"{VINA_RELEASE_URL}/{platform_utils.vina_binary_names()[0]}"
VINA_SPLIT_URL = f"{VINA_RELEASE_URL}/{platform_utils.vina_binary_names()[1]}"
P2RANK_URL = f"https://github.com/rdk/p2rank/releases/download/{P2RANK_VERSION}/p2rank_{P2RANK_VERSION}.tar.gz"
VINA_GPU_ARCHIVE = "Vina-GPU-2.1.zip"
BOOST_ARCHIVE = "boost_1_84_0.tar.gz"

# Vina-GPU (this project's custom progress-bar fork) and Boost are too large to keep in the git
# repo's BIN/ folder, so a fresh clone won't have them bundled locally. CODOC's own GitHub
# Release hosts both as a fallback download source for Install Requirements.
CODOC_DEPS_RELEASE_URL = "https://github.com/moimaian/CODOC/releases/download/deps-v1"
VINA_GPU_ARCHIVE_URL = f"{CODOC_DEPS_RELEASE_URL}/{VINA_GPU_ARCHIVE}"
BOOST_ARCHIVE_URL = f"{CODOC_DEPS_RELEASE_URL}/{BOOST_ARCHIVE}"

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
    background: #0F3A48;
    color: #29B6D8;
    font-weight: bold;
    border: 1px solid #29B6D8;
    border-radius: 5px;
    padding: 6px 16px;
}
QPushButton:hover { background: #1893B3; color: #0D1B2A; }
QPushButton:pressed { background: #006680; color: #FFF; }
QPushButton:disabled { background: #13262E; color: #3D7285; border-color: #2A4F5E; }
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


def _assume_yes() -> bool:
    """CODOC_ASSUME_YES=1 (definida pelo Install-CODOC.ps1 / CODOC_Windows.bat): responde "S" sozinho às
    confirmações do bootstrap, para o usuário do Windows não precisar digitar nada num terminal."""
    return os.environ.get("CODOC_ASSUME_YES") == "1"


def _stdin_is_tty() -> bool:
    try:
        return sys.stdin is not None and sys.stdin.isatty()
    except Exception:
        return False


def _prompt_yes_no(message: str, default_yes: bool = True) -> bool:
    if _assume_yes() or not _stdin_is_tty():
        print(f"{message} -> Y")
        return True
    suffix = "[S/n]" if default_yes else "[s/N]"
    try:
        answer = input(f"{message} {suffix}: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    if not answer:
        return default_yes
    return answer in ("s", "sim", "y", "yes")


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


# ----------------------------------------------------------------------------- Windows
def _winget_available() -> bool:
    return IS_WINDOWS and _which("winget") is not None


def _winget_install(pkg_id: str, extra: Optional[list] = None) -> bool:
    """winget install -e --id <pkg_id> ...; True se instalou ou se já estava instalado."""
    command = ["winget", "install", "--id", pkg_id, "-e", "--silent",
               "--accept-package-agreements", "--accept-source-agreements"] + list(extra or [])
    print(f"[{APP_NAME}] " + " ".join(command))
    code = _run(command).returncode
    if code > 0x7FFFFFFF:
        code -= 1 << 32
    return code in _WINGET_ALREADY_OK


def _download_file(url: str, destination: str) -> bool:
    """Download só com a biblioteca padrão (o Windows não tem wget)."""
    import urllib.request

    try:
        print(f"[{APP_NAME}] Downloading {url}")
        urllib.request.urlretrieve(url, destination)
        return os.path.isfile(destination) and os.path.getsize(destination) > 0
    except Exception as exc:
        print(f"[{APP_NAME}] Download failed: {url}: {exc}")
        return False


def _vcredist_installed() -> bool:
    """True se o runtime Visual C++ 2015-2022 (x64) está instalado (chave de registro do instalador)."""
    if not IS_WINDOWS:
        return True
    try:
        import winreg
    except ImportError:
        return True
    for key in (r"SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64",
                r"SOFTWARE\WOW6432Node\Microsoft\VisualStudio\14.0\VC\Runtimes\x64"):
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key) as handle:
                if int(winreg.QueryValueEx(handle, "Installed")[0]) == 1:
                    return True
        except OSError:
            continue
    return False


def ensure_vcredist_windows() -> bool:
    """Garante o runtime Visual C++ (x64) que as DLLs do Qt5 exigem: sem ele o import do PyQt5 falha com
    "DLL load failed". Usa o winget e, sem ele, o instalador oficial da Microsoft; o Windows pede a
    confirmação de administrador (UAC) uma vez."""
    if not IS_WINDOWS or _vcredist_installed():
        return True
    print(f"[{APP_NAME}] Visual C++ runtime (x64) not found - the Qt5 libraries need it. Installing...")
    ok = _winget_install(VCREDIST_WINGET_ID) if _winget_available() else False
    if not ok and not _vcredist_installed():
        installer = os.path.join(tempfile.gettempdir(), "codoc_vc_redist.x64.exe")
        if _download_file(VCREDIST_DOWNLOAD_URL, installer):
            # 1638: já há uma versão mais nova; 3010: pede reinício do Windows
            ok = _run([installer, "/install", "/quiet", "/norestart"]).returncode in (0, 1638, 3010)
    if _vcredist_installed() or ok:
        print(f"[{APP_NAME}] Visual C++ runtime available.")
        return True
    print(f"[{APP_NAME}] Could not install the Visual C++ runtime. Install it by hand:\n"
          f"         winget install --id {VCREDIST_WINGET_ID} -e\n         or {VCREDIST_DOWNLOAD_URL}")
    return False


def _windows_python_candidates() -> List[str]:
    """Pythons 3.10 prováveis no Windows (py launcher, pastas padrão dos instaladores, PATH)."""
    found: List[str] = []
    if _which("py"):
        result = _run(["py", "-3.10", "-c", "import sys; print(sys.executable)"])
        if result.returncode == 0 and result.stdout.strip():
            found.append(result.stdout.strip().splitlines()[-1])
    local = os.environ.get("LOCALAPPDATA", "")
    if local:
        found.append(os.path.join(local, "Programs", "Python", "Python310", "python.exe"))
    for variable in ("ProgramFiles", "ProgramFiles(x86)"):
        base = os.environ.get(variable, "")
        if base:
            found.append(os.path.join(base, "Python310", "python.exe"))
    for name in ("python", "python3"):
        path = _which(name)
        if path:
            found.append(path)
    found.append(sys.executable)
    unique: List[str] = []
    seen = set()
    for path in found:
        key = os.path.normcase(os.path.abspath(path))
        if key not in seen and os.path.isfile(path):
            seen.add(key)
            unique.append(path)
    return unique


def _find_windows_python(version: str) -> Optional[str]:
    for path in _windows_python_candidates():
        if _python_version_string(path) == version:
            return path
    return None


def ensure_python310_windows(version: str = TARGET_VENV_PYTHON_WINDOWS) -> str:
    """Windows: devolve o python.exe da versão exata (3.10.11). Se não existir, instala pelo winget
    (--scope user) ou, sem winget, pelo instalador do python.org (por usuário, sem administrador)."""
    found = _find_windows_python(version)
    if found:
        return found
    print(f"[{APP_NAME}] Python {version} was not found on this Windows.")
    if not _prompt_yes_no(f"[{APP_NAME}] Install Python {version} now?"):
        raise RuntimeError(f"Python {version} is required to create the {APP_NAME} environment.")
    if _winget_available():
        _winget_install(PYTHON_WINGET_ID, ["--version", version, "--scope", "user"])
        found = _find_windows_python(version)
        if found:
            return found
    installer = os.path.join(tempfile.gettempdir(), f"python-{version}-amd64.exe")
    if _download_file(PYTHON_WINDOWS_INSTALLER_URL, installer):
        _run([installer, "/quiet", "InstallAllUsers=0", "PrependPath=0", "Include_launcher=0",
              "Include_test=0", "Include_pip=1"])
        found = _find_windows_python(version)
        if found:
            return found
    raise RuntimeError(
        f"Could not install Python {version}. Install it by hand and start {APP_NAME} again:\n"
        f"  winget install --id {PYTHON_WINGET_ID} -e --version {version}\n"
        f"  or {PYTHON_WINDOWS_INSTALLER_URL}"
    )


def _windows_known_folder(csidl: int) -> str:
    """Pasta especial do Windows (Área de Trabalho, Menu Iniciar), mesmo redirecionada pelo OneDrive."""
    try:
        import ctypes

        buffer = ctypes.create_unicode_buffer(260)
        if ctypes.windll.shell32.SHGetFolderPathW(None, csidl, None, 0, buffer) == 0 and buffer.value:  # type: ignore[attr-defined]
            return buffer.value
    except Exception:
        pass
    return ""


_SHORTCUT_POWERSHELL = r"""
$ErrorActionPreference = 'Stop'
$shell = New-Object -ComObject WScript.Shell
foreach ($path in ($env:CODOC_LNK_PATHS -split '\|')) {
  if (-not $path) { continue }
  $link = $shell.CreateShortcut($path)
  $link.TargetPath = $env:CODOC_LNK_TARGET
  $q = [char]34
  $link.Arguments = '-X utf8 ' + $q + $env:CODOC_LNK_SCRIPT + $q
  $link.WorkingDirectory = $env:CODOC_LNK_WORKDIR
  $link.Description = 'CODOC - Computational Molecular Docking Platform'
  if ($env:CODOC_LNK_ICON -and (Test-Path $env:CODOC_LNK_ICON)) { $link.IconLocation = $env:CODOC_LNK_ICON }
  $link.Save()
}
"""


def windows_shortcut_paths() -> List[str]:
    """Onde ficam os atalhos CODOC.lnk: Área de Trabalho e Menu Iniciar > Programas."""
    paths = []
    for csidl in (0x10, 0x02):          # CSIDL_DESKTOPDIRECTORY, CSIDL_PROGRAMS
        folder = _windows_known_folder(csidl)
        if folder:
            paths.append(os.path.join(folder, "CODOC.lnk"))
    return paths


def ensure_windows_shortcuts(script_path: str, env_name: str = APP_NAME, force: bool = False) -> bool:
    """Cria/atualiza CODOC.lnk na Área de Trabalho e no Menu Iniciar. O atalho abre o CODOC.py com o
    pythonw.exe do venv (sem janela de console; a saída vai para Help > Terminal). Só recria quando
    falta um atalho ou o destino mudou. Devolve True se os atalhos existem."""
    if not IS_WINDOWS:
        return False
    paths = venv_paths(env_name)
    target = paths["pythonw"] if os.path.isfile(paths["pythonw"]) else paths["python"]
    if not os.path.isfile(target):
        return False
    script = os.path.abspath(script_path)
    app_dir = os.path.dirname(script)
    icon = os.path.join(app_dir, "ICONS", "CODOC.ico")
    links = windows_shortcut_paths()
    if not links:
        return False
    signature = "\n".join([target, script, icon if os.path.isfile(icon) else ""] + links)
    marker = os.path.join(paths["venv_dir"], ".codoc_shortcuts")
    try:
        current = Path(marker).read_text(encoding="utf-8")
    except Exception:
        current = ""
    if not force and current == signature and all(os.path.isfile(link) for link in links):
        return True
    environment = os.environ.copy()
    environment.update({
        "CODOC_LNK_PATHS": "|".join(links),
        "CODOC_LNK_TARGET": target,
        "CODOC_LNK_SCRIPT": script,
        "CODOC_LNK_WORKDIR": app_dir,
        "CODOC_LNK_ICON": icon if os.path.isfile(icon) else "",
    })
    try:
        result = _run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                       "-Command", _SHORTCUT_POWERSHELL], env=environment)
    except Exception as exc:
        print(f"[{APP_NAME}] Could not create the shortcuts: {exc}")
        return False
    if result.returncode != 0:
        print(f"[{APP_NAME}] Could not create the CODOC.lnk shortcuts:\n{result.stdout}")
        return False
    try:
        Path(marker).write_text(signature, encoding="utf-8")
    except Exception:
        pass
    print(f"[{APP_NAME}] CODOC.lnk shortcuts created on the Desktop and in the Start Menu.")
    return all(os.path.isfile(link) for link in links)


def codoc_script_path() -> str:
    """CODOC.py (pai da pasta MODULES/ deste módulo)."""
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "CODOC.py")


def restart_codoc() -> bool:
    """Reinicia o CODOC num processo novo, para importar as bibliotecas recém-instaladas (o import delas
    acontece uma única vez, na inicialização). Linux: substitui o processo (execve) e não retorna.
    Windows: inicia o novo processo destacado, com pythonw.exe, e devolve True - quem chamou encerra o atual.
    CODOC_RESTARTED=1 impede um laço de reinícios."""
    script = codoc_script_path()
    if not os.path.isfile(script):
        return False
    environment = os.environ.copy()
    environment["CODOC_RESTARTED"] = "1"
    environment["CODOC_VENV_ACTIVE"] = "1"
    arguments = [sys.executable, script] + [a for a in sys.argv[1:] if a != "--setup"]
    print(f"[{APP_NAME}] Restarting to load the installed libraries...")
    try:
        if IS_WINDOWS:
            pythonw = os.path.join(os.path.dirname(os.path.abspath(sys.executable)), "pythonw.exe")
            if os.path.isfile(pythonw):
                arguments[0] = pythonw
            environment["PYTHONUTF8"] = "1"
            flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            subprocess.Popen(arguments, env=environment, cwd=os.path.dirname(script), stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)
            return True
        os.execve(sys.executable, arguments, environment)
    except Exception as exc:
        print(f"[{APP_NAME}] Could not restart: {exc}")
    return False



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
    scripts = platform_utils.venv_scripts_dir(venv_dir)       # Windows: Scripts\ ; Linux: bin/
    suffix = ".exe" if IS_WINDOWS else ""
    python = os.path.join(scripts, "python" + suffix)
    return {
        "app_dir": app_dir,
        "venv_dir": venv_dir,
        "python": python,
        "pip": os.path.join(scripts, "pip" + suffix),
        # Windows: pythonw.exe abre a interface sem janela de console (o atalho usa este)
        "pythonw": os.path.join(scripts, "pythonw.exe") if IS_WINDOWS else python,
    }


def _os_release_text() -> str:
    try:
        return Path("/etc/os-release").read_text(encoding="utf-8").lower()
    except Exception:
        return ""


def _has_controlling_terminal() -> bool:
    """True when sudo can ask for a password on a terminal. CODOC started from the menu has none
    (its launcher is Terminal=false), so a plain `sudo` would just fail there."""
    if IS_WINDOWS:
        return sys.stdin is not None and sys.stdin.isatty()
    try:
        with open("/dev/tty"):
            return True
    except OSError:
        return False


def root_command(command: list[str]) -> list[str]:
    """Prefix for commands that need root: `sudo` on a terminal, otherwise `pkexec`, which asks for
    the password in a graphical dialog."""
    if not _has_controlling_terminal() and _which("pkexec"):
        return ["pkexec"] + command
    return ["sudo"] + command


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
    result = subprocess.run(root_command(["apt-get", "update"]))
    if result.returncode != 0:
        raise RuntimeError("Failed to run 'apt-get update'.")
    install_cmd = root_command(["apt-get", "install", "-y"] + PYENV_APT_BUILD_DEPS)
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
    if IS_WINDOWS:
        return ensure_python310_windows(TARGET_VENV_PYTHON)
    candidate = _which("python3.10")
    if candidate and _is_target_python(candidate):
        return candidate
    return ensure_python310_with_pyenv(TARGET_VENV_PYTHON)


def ensure_venv(env_name: str = APP_NAME) -> dict[str, str]:
    paths = venv_paths(env_name)
    os.makedirs(paths["app_dir"], exist_ok=True)
    if IS_WINDOWS:
        ensure_vcredist_windows()        # as DLLs do Qt5 precisam do runtime Visual C++

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
        paths = venv_paths(env_name)
        if IS_WINDOWS:
            # o atalho abre o CODOC com pythonw.exe (sem console): é o mesmo venv que python.exe
            allowed = {os.path.normcase(os.path.abspath(paths["python"])), os.path.normcase(os.path.abspath(paths["pythonw"]))}
            return os.path.normcase(os.path.abspath(sys.executable)) in allowed
        return Path(sys.executable).resolve() == Path(paths["python"]).resolve()
    except Exception:
        return False


def bootstrap_pyqt5(interactive: bool = True, reexec: bool = False, env_name: str = APP_NAME) -> bool:
    if os.environ.get(f"{env_name}_VENV_ACTIVE") == "1" and _running_in_target_venv(env_name):
        return True

    if IS_WINDOWS and _running_in_target_venv(env_name) and _has_module(venv_paths(env_name)["python"], "PyQt5"):
        # Windows: já dentro do venv (atalho/pythonw). Marca o ambiente para que os processos filhos
        # (multiprocessing "spawn" reimporta o CODOC.py) não repitam o bootstrap.
        os.environ[f"{env_name}_VENV_ACTIVE"] = "1"
        return True

    target_paths = venv_paths(env_name)
    if interactive and not _running_in_target_venv(env_name) and not _stdin_is_tty() and not _assume_yes():
        # Sem terminal para responder à pergunta: com o venv pronto basta reiniciar dentro dele;
        # sem venv, a configuração inicial precisa de um terminal (no Windows: o CODOC_Windows.bat).
        if not (os.path.isdir(target_paths["venv_dir"]) and os.path.isfile(target_paths["python"])):
            print(f"[{APP_NAME}] The first run needs a terminal to set up the environment "
                  f"({target_paths['venv_dir']}). Run 'python CODOC.py' in a terminal"
                  + (" or double-click CODOC_Windows.bat." if IS_WINDOWS else "."))
            return False
        interactive = False
    if interactive and not _running_in_target_venv(env_name):
        print("\n" + "═" * 62)
        print(f"  {APP_NAME} — Python Environment Setup")
        print("═" * 62)
        print(f"  Current Python : {sys.executable}")
        print(f"  Version        : {sys.version.split()[0]}")
        print(f"  Target venv    : {target_paths['venv_dir']}")
        print(f"  Target Python  : {TARGET_VENV_PYTHON}")
        if _assume_yes():
            print("  Continue? [S/n]: S")
        else:
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
        current_python = os.path.normcase(os.path.realpath(sys.executable))
        target_python = os.path.normcase(os.path.realpath(paths["python"]))
        if current_python != target_python:
            env = os.environ.copy()
            env[f"{env_name}_VENV_ACTIVE"] = "1"
            if IS_WINDOWS:
                # O Windows não tem exec(): os.execve criaria um processo novo e encerraria este logo em
                # seguida, soltando o terminal. Executa o filho (pythonw sem terminal) e espera.
                env["PYTHONUTF8"] = "1"
                exe = paths["python"] if _stdin_is_tty() or not os.path.isfile(paths["pythonw"]) else paths["pythonw"]
                sys.exit(subprocess.call([exe] + sys.argv, env=env))
            os.execve(paths["python"], [paths["python"]] + sys.argv, env)
    return True


def run_setup() -> int:
    """`python CODOC.py --setup` (usado pelo Install-CODOC.ps1): prepara tudo sem abrir a interface -
    venv, runtime Visual C++, pacotes essenciais e, no Windows, os atalhos CODOC.lnk. Devolve 0 se deu certo."""
    try:
        paths = ensure_venv(APP_NAME)
        _ensure_rdkit_numpy_compat(paths["python"])
        packages = [PYTHON_PACKAGES["PyQt5"], PYTHON_PACKAGES["pandas"], PYTHON_PACKAGES["psutil"]]
        print(f"[{APP_NAME}] Installing the essential packages: {', '.join(packages)}")
        result = install_python_packages(paths["python"], packages)
        if result.returncode != 0:
            print(result.stdout)
            return 1
        Path(os.path.join(paths["venv_dir"], ".codoc_minimal_done")).write_text("ok", encoding="utf-8")
        if IS_WINDOWS:
            try:        # the Windows build of AutoDock Vina 1.2.5 (about 2 MB): CPU docking works right after the setup
                ensure_vina_binaries(os.path.join(os.path.dirname(codoc_script_path()), "BIN"))
            except Exception as exc:
                print(f"[{APP_NAME}] AutoDock Vina was not downloaded ({exc}); tick it in Install Requirements.")
            ensure_windows_shortcuts(codoc_script_path(), force=True)
        print(f"[{APP_NAME}] Setup finished: {paths['venv_dir']}")
        return 0
    except Exception as exc:
        print(f"[{APP_NAME}] Setup failed: {exc}")
        return 1


def install_python_packages(pybin: str, packages: list[str]) -> subprocess.CompletedProcess[str]:
    return _run([pybin, "-m", "pip", "install", "--upgrade"] + packages)


def _require_commands(commands: list[str], apt_package: str, needed_for: str) -> None:
    """Fail with a message that names the External Programs row to tick, instead of a bare
    FileNotFoundError from subprocess."""
    missing = [command for command in commands if not _which(command)]
    if missing:
        raise RuntimeError(
            f"{', '.join(missing)} not found, which is needed {needed_for}. "
            f"Tick the External Programs row of the apt package '{apt_package}' (or run: sudo apt-get install {apt_package}) and try again."
        )


def _download(url: str, destination: str, label: str) -> None:
    if IS_WINDOWS:                                 # o Windows não tem wget
        if not _download_file(url, destination):
            if os.path.isfile(destination):
                os.remove(destination)
            raise RuntimeError(f"Failed to download {label} from {url}")
        return
    _require_commands(["wget"], "wget", f"to download {label}")
    result = _run(["wget", "-O", destination, url])
    if result.returncode != 0 or not os.path.isfile(destination):
        if os.path.isfile(destination):
            os.remove(destination)
        raise RuntimeError(f"Failed to download {label} from {url}:\n{result.stdout}")


def ensure_vina_binaries(bin_dir: str) -> str:
    os.makedirs(bin_dir, exist_ok=True)
    vina_path, vina_split_path = platform_utils.vina_binary_paths(bin_dir)     # Windows: vina_1.2.5_win.exe

    if not os.path.isfile(vina_path):
        _download(VINA_URL, vina_path, "vina")
        if not IS_WINDOWS:
            os.chmod(vina_path, 0o755)

    if not os.path.isfile(vina_split_path):
        _download(VINA_SPLIT_URL, vina_split_path, "vina_split")
        if not IS_WINDOWS:
            os.chmod(vina_split_path, 0o755)

    return vina_path


def _ensure_bundled_archive(archive_path: str, download_url: str, label: str) -> None:
    """Make sure `archive_path` exists, downloading it from CODOC's GitHub Release if it
    isn't already bundled in BIN/ (e.g. on a fresh clone that never had the large archives
    committed). Leaves a pre-existing bundled file untouched and never re-downloads it."""
    if os.path.isfile(archive_path):
        return
    os.makedirs(os.path.dirname(archive_path), exist_ok=True)
    _download(download_url, archive_path, label)


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

    _require_commands(["gcc", "g++", "make"], "build-essential", "to build Boost")
    archive_path = os.path.join(app_dir, "BIN", BOOST_ARCHIVE)
    _ensure_bundled_archive(archive_path, BOOST_ARCHIVE_URL, "Boost")

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


def get_java_version() -> Optional[str]:
    """Version of the Java runtime on the PATH ("17.0.21"), None when there is none."""
    java = platform_utils.find_java()
    if not java:
        return None
    result = _run([java, "-version"])
    match = re.search(r'version "([^"]+)"', result.stdout or "")
    return match.group(1) if result.returncode == 0 and match else None


def java_major(version: str) -> int:
    """Major number of a Java version string: "17.0.21" -> 17, "1.8.0_392" -> 8."""
    parts = re.split(r"[._\-+]", version)
    try:
        return int(parts[1]) if parts[0] == "1" and len(parts) > 1 else int(parts[0])
    except ValueError:
        return 0


def p2rank_paths(home_dir: Optional[str] = None) -> dict[str, str]:
    install_dir = os.path.join(home_dir or str(Path.home()), f"p2rank_{P2RANK_VERSION}")
    return {"install_dir": install_dir, "launcher": os.path.join(install_dir, platform_utils.p2rank_launcher_names()[0])}


def get_p2rank_version(app_dir: Optional[str] = None) -> Optional[str]:
    """Version of the P2Rank that STEP 2 would use (read from the name of its folder), None when
    P2Rank is not installed."""
    from MODULES.module_target_prepare import find_p2rank

    launcher = find_p2rank(app_dir)
    if not launcher:
        return None
    match = re.search(r"p2rank[_-]?(\d+(?:\.\d+)+)", os.path.basename(os.path.dirname(launcher)), re.IGNORECASE)
    return match.group(1) if match else "available"


def ensure_p2rank_installation(app_dir: str) -> str:
    """Download P2Rank to $HOME/p2rank_<version> (one of the places STEP 2 searches) unless some
    P2Rank is already found; returns the prank launcher."""
    from MODULES.module_target_prepare import find_p2rank

    existing = find_p2rank(app_dir)
    if existing:
        return existing
    paths = p2rank_paths()
    with tempfile.TemporaryDirectory(prefix="codoc-p2rank-") as temp_dir:
        archive_path = os.path.join(temp_dir, f"p2rank_{P2RANK_VERSION}.tar.gz")
        _download(P2RANK_URL, archive_path, f"P2Rank {P2RANK_VERSION} (about 280 MB)")
        shutil.unpack_archive(archive_path, temp_dir)
        extracted_dir = os.path.join(temp_dir, f"p2rank_{P2RANK_VERSION}")
        if not os.path.isfile(os.path.join(extracted_dir, platform_utils.p2rank_launcher_names()[0])):
            raise RuntimeError(f"Could not locate p2rank_{P2RANK_VERSION}/{platform_utils.p2rank_launcher_names()[0]} inside the downloaded archive.")
        shutil.copytree(extracted_dir, paths["install_dir"])
    if not IS_WINDOWS:
        os.chmod(paths["launcher"], 0o755)
    return paths["launcher"]


def vina_gpu_paths(home_dir: Optional[str] = None) -> dict[str, str]:
    home_path = home_dir or str(Path.home())
    install_root = os.path.join(home_path, "Vina-GPU-2.1")
    install_dir = os.path.join(install_root, "AutoDock-Vina-GPU-2.1")
    # Windows: o zip traz Vina-GPU+.exe (kernels já compilados) e Vina-GPU+_K.exe (compila os kernels ao
    # rodar); o Linux compila o seu próprio binário (ver _rebuild_vina_gpu).
    executable = os.path.join(install_dir, "Vina-GPU+.exe" if IS_WINDOWS else "AutoDock-Vina-GPU-2-1")
    source_executable = os.path.join(install_dir, "Vina-GPU+_K.exe" if IS_WINDOWS else "AutoDock-Vina-GPU-2-1_source")
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
    if IS_WINDOWS:
        # o executável do Windows é o da distribuição original: não imprime a versão com --version
        return "AutoDock-Vina-GPU 2.1 (Windows build)"
    result = _run([vina_gpu, "--version"])
    if result.returncode != 0:
        return None
    for line in result.stdout.splitlines():
        version = line.strip()
        if version:
            return version
    return None


def _detect_opencl_ctypes() -> list[dict[str, Any]]:
    """Lista plataformas e dispositivos OpenCL chamando a própria biblioteca OpenCL (OpenCL.dll no Windows,
    libOpenCL.so no Linux), sem o clinfo - que não existe no Windows. Mesmos campos do detect_opencl_devices."""
    import ctypes

    library = None
    for name in (["OpenCL.dll"] if IS_WINDOWS else ["libOpenCL.so.1", "libOpenCL.so"]):
        try:
            library = ctypes.WinDLL(name) if IS_WINDOWS else ctypes.CDLL(name)   # type: ignore[attr-defined]
            break
        except OSError:
            continue
    if library is None:
        return []

    void_p, uint, ulong, size_t = ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint64, ctypes.c_size_t
    # Without argtypes ctypes passes every integer as a 32-bit int, which corrupts the 64-bit sizes and pointers.
    library.clGetPlatformIDs.argtypes = [uint, ctypes.POINTER(void_p), ctypes.POINTER(uint)]
    library.clGetPlatformInfo.argtypes = [void_p, uint, size_t, void_p, ctypes.POINTER(size_t)]
    library.clGetDeviceIDs.argtypes = [void_p, ulong, uint, ctypes.POINTER(void_p), ctypes.POINTER(uint)]
    library.clGetDeviceInfo.argtypes = [void_p, uint, size_t, void_p, ctypes.POINTER(size_t)]
    for name in ("clGetPlatformIDs", "clGetPlatformInfo", "clGetDeviceIDs", "clGetDeviceInfo"):
        getattr(library, name).restype = ctypes.c_int32

    def text_info(function: Any, handle: Any, parameter: int) -> str:
        size = size_t(0)
        if function(handle, parameter, 0, None, ctypes.byref(size)) != 0 or not size.value:
            return ""
        buffer = ctypes.create_string_buffer(size.value)
        if function(handle, parameter, size.value, ctypes.addressof(buffer), None) != 0:
            return ""
        return buffer.value.decode("utf-8", "replace").strip()

    def number_info(handle: Any, parameter: int, kind: Any) -> int:
        value = kind(0)
        if library.clGetDeviceInfo(handle, parameter, ctypes.sizeof(value), ctypes.addressof(value), None) != 0:
            return 0
        return int(value.value)

    count = uint(0)
    if library.clGetPlatformIDs(0, None, ctypes.byref(count)) != 0 or not count.value:
        return []
    platforms = (void_p * count.value)()
    library.clGetPlatformIDs(count.value, platforms, None)

    devices: list[dict[str, Any]] = []
    for platform_index, platform_handle in enumerate(platforms):
        device_count = uint(0)
        # CL_DEVICE_TYPE_ALL = 0xFFFFFFFF
        if library.clGetDeviceIDs(platform_handle, 0xFFFFFFFF, 0, None, ctypes.byref(device_count)) != 0 or not device_count.value:
            continue
        handles = (void_p * device_count.value)()
        library.clGetDeviceIDs(platform_handle, 0xFFFFFFFF, device_count.value, handles, None)
        for device_index, device_handle in enumerate(handles):
            device_type = number_info(device_handle, 0x1000, ulong)        # CL_DEVICE_TYPE
            kind = "GPU" if device_type & 4 else "CPU" if device_type & 2 else "ACCELERATOR" if device_type & 8 else "Unknown"
            devices.append({
                "platform_id": platform_index,
                "platform_name": text_info(library.clGetPlatformInfo, platform_handle, 0x0902) or f"Platform {platform_index}",
                "platform_vendor": text_info(library.clGetPlatformInfo, platform_handle, 0x0903),
                "platform_version": text_info(library.clGetPlatformInfo, platform_handle, 0x0901),
                "device_id": device_index,
                "device_name": text_info(library.clGetDeviceInfo, device_handle, 0x102B),   # CL_DEVICE_NAME
                "device_type": kind,
                "compute_units": number_info(device_handle, 0x1002, uint),                  # MAX_COMPUTE_UNITS
                "clock_mhz": number_info(device_handle, 0x100C, uint),                      # MAX_CLOCK_FREQUENCY
                "memory_bytes": number_info(device_handle, 0x101F, ulong),                  # GLOBAL_MEM_SIZE
            })
    return devices


def detect_opencl_devices() -> list[dict[str, Any]]:
    clinfo = _which("clinfo")
    if not clinfo:
        try:
            return _detect_opencl_ctypes()      # no Windows não há clinfo: pergunta à OpenCL.dll
        except Exception:
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


def _vina_gpu_startup_time_type(content: str) -> str:
    """Different Vina-GPU 2.1 releases have declared the `startup_time` parameter as either
    `std::chrono::duration<double>` (older) or plain `double` (newer) - detect which one this
    checkout actually uses so the patches below stay consistent with it everywhere, instead of
    hardcoding one and breaking on whichever release doesn't match."""
    match = re.search(r"(std::chrono::duration<double>|double)\s+startup_time", content)
    return match.group(1) if match else "double"


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
    startup_time_type = _vina_gpu_startup_time_type(main_header_content)
    main_header_content = _replace_regex(
        main_header_content,
        r"void main_procedure_cl\(cache& c, const std::vector<model>& ms, const precalculate& p, const parallel_mc par,\s*const vec& corner1, const vec& corner2, const int seed, std::vector<output_container>& out, std::string opencl_binary_path,\s*const std::vector<std::vector<std::string>> ligand_names, const int rilc_bfgs, "
        + re.escape(startup_time_type) + r" startup_time\);",
        f"void main_procedure_cl(cache& c, const std::vector<model>& ms, const precalculate& p, const parallel_mc par,\n\tconst vec& corner1, const vec& corner2, const int seed, std::vector<output_container>& out, std::string opencl_binary_path,\n\tconst int opencl_platform_id, const int opencl_device_id,\n\tconst std::vector<std::vector<std::string>> ligand_names, const int rilc_bfgs, {startup_time_type} startup_time);",
        main_header,
    )
    Path(main_header).write_text(main_header_content, encoding="utf-8")

    main_source_content = Path(main_source).read_text(encoding="utf-8")
    main_source_content = _replace_regex(
        main_source_content,
        r"void main_procedure_cl\(cache &c, const std::vector<model> &ms, const precalculate &p, const parallel_mc par,\s*const vec &corner1, const vec &corner2, const int seed, std::vector<output_container> &outs, std::string opencl_binary_path,\s*const std::vector<std::vector<std::string>> ligand_names, const int rilc_bfgs, "
        + re.escape(startup_time_type) + r" startup_time\)\n",
        f"void main_procedure_cl(cache &c, const std::vector<model> &ms, const precalculate &p, const parallel_mc par,\n                                           const vec &corner1, const vec &corner2, const int seed, std::vector<output_container> &outs, std::string opencl_binary_path,\n                                           const int opencl_platform_id, const int opencl_device_id,\n                                           const std::vector<std::vector<std::string>> ligand_names, const int rilc_bfgs, {startup_time_type} startup_time)\n",
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
        r"void main_procedure\(std::vector<model>& ms, const boost::optional<model>& ref, // m is non-const \(FIXME\?\)\s*const std::vector<std::string>& out_names,\s*bool score_only, bool local_only, bool randomize_only, bool no_cache,\s*const grid_dims& gd, int exhaustiveness,\s*const flv& weights,\s*int cpu, int seed, int verbosity, sz num_modes, fl energy_range,\s*tee& log, int search_depth, int thread, std::string opencl_binary_path, std::vector<std::vector<std::string>> ligand_names, int rilc_bfgs, "
        + re.escape(startup_time_type) + r" startup_time\) \{",
        f"void main_procedure(std::vector<model>& ms, const boost::optional<model>& ref, // m is non-const (FIXME?)\n\t\tconst std::vector<std::string>& out_names,\n\t\tbool score_only, bool local_only, bool randomize_only, bool no_cache,\n\t\tconst grid_dims& gd, int exhaustiveness,\n\t\tconst flv& weights,\n\t\tint cpu, int seed, int verbosity, sz num_modes, fl energy_range, \n\t\ttee& log, int search_depth, int thread, std::string opencl_binary_path, int opencl_platform_id, int opencl_device_id, std::vector<std::vector<std::string>> ligand_names, int rilc_bfgs, {startup_time_type} startup_time) {{",
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


def _opencl_root() -> Optional[str]:
    """Folder whose include/CL/cl.h holds the OpenCL headers Vina-GPU is built against: the CUDA
    toolkit when it is there, otherwise the system's (opencl-headers + ocl-icd-opencl-dev)."""
    for root in ("/usr/local/cuda", "/usr"):
        if os.path.isfile(os.path.join(root, "include", "CL", "cl.h")):
            return root
    return None


def _patch_vina_gpu_makefile(makefile_path: str, install_dir: str) -> None:
    boost_root = boost_paths()["root"]
    opencl_root = _opencl_root() or "/usr/local/cuda"
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
        "LIB_PATH=-L$(BOOST_LIB_PATH)/stage/lib -L$(OPENCL_LIB_PATH)/lib64 -L/usr/lib/x86_64-linux-gnu\n"
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
    _require_commands(["gcc", "g++", "make"], "build-essential", "to build Vina-GPU")
    if _opencl_root() is None:
        raise RuntimeError(
            "The OpenCL headers (CL/cl.h) were not found, which Vina-GPU needs to be built. Tick "
            "'opencl-headers' and 'ocl-icd-opencl-dev' in External Programs (or install the CUDA toolkit) and try again."
        )
    makefile_path = vina_gpu_paths()["makefile"]
    _patch_vina_gpu_backend_sources(install_dir)
    _patch_vina_gpu_makefile(makefile_path, install_dir)
    for command in (["make", "clean"], ["make", "source"], ["make", "clean"], ["make", "out"]):
        result = _run(command, cwd=install_dir)
        if result.returncode != 0:
            raise RuntimeError(result.stdout or f"Failed running {' '.join(command)} in {install_dir}")


def _prepare_vina_gpu_windows(install_dir: str) -> None:
    """Windows: o zip do Vina-GPU 2.1 traz os executáveis já compilados (Vina-GPU+.exe e Vina-GPU+_K.exe),
    de modo que não precisa de Visual Studio nem de Boost. O que falta é o kernel OpenCL da SUA placa:
    os Kernel1_Opt.bin / Kernel2_Opt.bin do zip foram gerados para outra GPU. O Vina-GPU+_K.exe os compila
    ao rodar um docking de exemplo (2bm2), e o Vina-GPU+.exe passa a usá-los."""
    paths = vina_gpu_paths()
    for key in ("executable", "source_executable"):
        if not os.path.isfile(paths[key]):
            raise RuntimeError(f"{os.path.basename(paths[key])} was not found in the Vina-GPU archive ({install_dir}).")
    for name in ("Kernel1_Opt.bin", "Kernel2_Opt.bin"):
        kernel = os.path.join(install_dir, name)
        if os.path.isfile(kernel):
            os.remove(kernel)
    example = os.path.join(install_dir, "input_file_example")
    receptor = os.path.join(example, "2bm2_protein.pdbqt")
    ligand = os.path.join(example, "2bm2_ligand.pdbqt")
    if not (os.path.isfile(receptor) and os.path.isfile(ligand)):
        raise RuntimeError(f"The Vina-GPU example files were not found in {example}.")
    with tempfile.TemporaryDirectory(prefix="codoc-vinagpu-kernels-") as work:
        ligand_dir = os.path.join(work, "ligands")
        output_dir = os.path.join(work, "out")
        os.makedirs(ligand_dir)
        os.makedirs(output_dir)
        shutil.copy(ligand, ligand_dir)
        config = os.path.join(work, "kernel_build.txt")
        lines = [
            f"receptor = {Path(receptor).as_posix()}",
            f"ligand_directory = {Path(ligand_dir).as_posix()}",
            f"output_directory = {Path(output_dir).as_posix()}",
            f"opencl_binary_path = {Path(install_dir).as_posix()}",
            "center_x = 40.415", "center_y = 110.986", "center_z = 82.673",
            "size_x = 30", "size_y = 30", "size_z = 30", "thread = 8000",
        ]
        Path(config).write_text("\n".join(lines) + "\n", encoding="utf-8")
        result = _run([paths["source_executable"], "--config", config], cwd=install_dir)
    missing = [n for n in ("Kernel1_Opt.bin", "Kernel2_Opt.bin") if not os.path.isfile(os.path.join(install_dir, n))]
    if missing:
        tail = "\n".join((result.stdout or "").strip().splitlines()[-8:])
        raise RuntimeError(
            "Vina-GPU could not build its OpenCL kernels for this GPU (" + ", ".join(missing) + " missing). "
            "It needs a GPU with an up-to-date OpenCL driver (NVIDIA, AMD or Intel).\n" + tail
        )


def ensure_vina_gpu_installation(app_dir: str) -> str:
    paths = vina_gpu_paths()
    archive_path = os.path.join(app_dir, "BIN", VINA_GPU_ARCHIVE)
    _ensure_bundled_archive(archive_path, VINA_GPU_ARCHIVE_URL, "Vina-GPU")

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

    if IS_WINDOWS:
        _prepare_vina_gpu_windows(paths["install_dir"])
    else:
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
        "openbabel": bool(platform_utils.find_obabel(venv_paths()["venv_dir"])),
        "adfr": platform_utils.find_adfr_prepare_receptor() is not None,
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
        self.bin_dir = os.path.join(self.app_dir, "BIN")
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

        system_box = QGroupBox("External Programs" + (" (Windows)" if IS_WINDOWS else ""))
        system_layout = QGridLayout(system_box)
        system_layout.addWidget(QLabel("Install"), 0, 0)
        system_layout.addWidget(QLabel("Program"), 0, 1)
        system_layout.addWidget(QLabel("Version / spec"), 0, 2)
        row_idx = 1
        self.system_kinds: dict[str, str] = {}
        for display_name, package_spec, kind in system_package_rows():
            checkbox = QCheckBox()
            name_label = QLabel(display_name)
            package_edit = QLineEdit(package_spec)
            self.system_kinds[display_name] = kind
            system_layout.addWidget(checkbox, row_idx, 0)
            system_layout.addWidget(name_label, row_idx, 1)
            system_layout.addWidget(package_edit, row_idx, 2)
            self.system_rows.append((checkbox, package_edit, display_name))
            row_idx += 1
        for display_name, (tool_key, version) in tool_defaults().items():
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
        pinned_tool_versions = {key: version for _name, (key, version) in tool_defaults().items()}
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
                kind = self.system_kinds.get(name, "apt")
                if kind == "apt":
                    command = root_command(["apt-get", "install", "-y", package_name])
                    self.log_signal.emit(f"Running: {' '.join(command)}\n")
                    result = _run(command)
                    if result.returncode != 0:
                        raise RuntimeError(result.stdout or f"Failed to install {package_name}")
                    self.log_signal.emit(result.stdout + "\n")
                elif kind == "winget":
                    if not _winget_available():
                        raise RuntimeError(
                            f"winget was not found (it comes with the Windows App Installer). Install {name} by hand: "
                            f"winget install --id {package_name} -e"
                        )
                    self.log_signal.emit(f"Running: winget install --id {package_name} -e\n")
                    if not _winget_install(package_name):
                        raise RuntimeError(f"Failed to install {name} with winget (id {package_name}).")
                    self.log_signal.emit(f"{name} installed.\n")
                elif kind == "pip":
                    self.log_signal.emit(f"Installing Python package: {name} -> {package_name}\n")
                    result = install_python_packages(pybin, [package_name])
                    if result.returncode != 0:
                        raise RuntimeError(result.stdout or f"Failed to install {package_name}")
                    self.log_signal.emit(result.stdout + "\n")
                elif kind == "vcredist":
                    if not ensure_vcredist_windows():
                        raise RuntimeError("The Visual C++ runtime could not be installed (see the terminal output).")
                    self.log_signal.emit("Visual C++ runtime available.\n")
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
                    prepare_receptor = platform_utils.find_adfr_prepare_receptor()
                    if prepare_receptor is None:
                        hint = (
                            "Download the Windows installer from https://ccsb.scripps.edu/adfr/downloads/ and run it, "
                            "then tick this row again (CODOC looks for prepare_receptor in $HOME/ADFRsuite-1.0 and in the "
                            "ADFRsuite folders of Program Files)."
                            if IS_WINDOWS else
                            f"Install it manually and ensure prepare_receptor exists at:\n"
                            f"{os.path.join(str(Path.home()), f'ADFRsuite-{pinned_version}', 'bin', 'prepare_receptor')}"
                        )
                        raise RuntimeError("ADFRsuite was not found. " + hint)
                    self.log_signal.emit(f"ADFRsuite validated at {prepare_receptor}\n")
                elif tool_key == "p2rank":
                    launcher = ensure_p2rank_installation(self.app_dir)
                    self.log_signal.emit(f"P2Rank {get_p2rank_version(self.app_dir) or 'installed'} available at {launcher}\n")
                    java_version = get_java_version()
                    if java_version is None or java_major(java_version) < JAVA_MIN_MAJOR:
                        self.log_signal.emit(
                            f"Warning: P2Rank needs Java {JAVA_MIN_MAJOR} or newer and "
                            + (f"Java {java_version} was found" if java_version else "no Java was found")
                            + ". Tick 'Java JRE 17 (P2Rank)' in External Programs to install it.\n"
                        )
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

