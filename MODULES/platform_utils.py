# -*- coding: utf-8 -*-

# SPDX-License-Identifier: GPL-3.0-or-later
#
# CODOC - Python Molecular Docking Tool
# Copyright (C) 2024-2026 Moises Maia
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.

"""O que muda entre Linux e Windows no CODOC, num só lugar (só biblioteca padrão, sem Qt).

Os demais módulos perguntam aqui em que sistema estão rodando e onde ficam as ferramentas externas
(AutoDock Vina, Open Babel, ADFRsuite, P2Rank), em vez de cada um repetir o seu `if`. No Linux nada
muda: tudo continua nos mesmos caminhos de antes.
"""

from __future__ import annotations

import glob
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

IS_WINDOWS = sys.platform.startswith("win")

AUTODOCK_VINA_VERSION = "1.2.5"


# ----------------------------------------------------------------------------- processos filhos
def install_subprocess_defaults() -> None:
    """Windows: faz todo processo filho nascer sem janela de console e com um stdin válido.

    O CODOC aberto pelo atalho roda em `pythonw.exe` (sem console): sem isso cada `pip`, `obabel`,
    `vina` ou `nvidia-smi` abriria uma janela preta e, sem stdin, o subprocess falharia com "handle
    inválido". Também decodifica a saída das ferramentas com `errors="replace"`, para um byte fora
    da página de código do Windows não derrubar a leitura do log. No Linux não faz nada."""
    if not IS_WINDOWS or getattr(subprocess.Popen, "_codoc_patched", False):
        return
    original_init = subprocess.Popen.__init__
    no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

    def patched_init(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        if not kwargs.get("creationflags"):
            kwargs["creationflags"] = no_window
        if kwargs.get("stdin") is None and (sys.stdin is None or not sys.stdin.isatty()):
            kwargs["stdin"] = subprocess.DEVNULL
        text_mode = kwargs.get("text") or kwargs.get("universal_newlines") or kwargs.get("encoding") or kwargs.get("errors")
        if text_mode and kwargs.get("errors") is None:
            kwargs["errors"] = "replace"
        original_init(self, *args, **kwargs)

    subprocess.Popen.__init__ = patched_init  # type: ignore[method-assign]
    subprocess.Popen._codoc_patched = True    # type: ignore[attr-defined]


# ----------------------------------------------------------------------------- pastas
def home_dir() -> str:
    return str(Path.home())


def state_dir() -> Path:
    """Onde ficam os arquivos de estado do CODOC (log da sessão do Help > Terminal)."""
    if IS_WINDOWS:
        return Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local")) / "CODOC"
    return Path.home() / ".local" / "state" / "CODOC"


def default_venv_dir() -> str:
    """O ambiente virtual do CODOC: $HOME/.venv/CODOC (Linux) ou %USERPROFILE%\\.venv\\CODOC (Windows)."""
    return os.path.join(home_dir(), ".venv", "CODOC")


def venv_scripts_dir(venv_dir: str) -> str:
    """Pasta dos executáveis do venv: Scripts\\ no Windows, bin/ no Linux."""
    return os.path.join(venv_dir, "Scripts" if IS_WINDOWS else "bin")


def _program_dirs() -> list[str]:
    folders = []
    for variable in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432"):
        value = os.environ.get(variable)
        if value and value not in folders:
            folders.append(value)
    local = os.environ.get("LOCALAPPDATA")
    if local:
        folders.append(os.path.join(local, "Programs"))
    return folders


# ----------------------------------------------------------------------------- AutoDock Vina
def vina_binary_names() -> tuple[str, str]:
    """(vina, vina_split) como são distribuídos na release v1.2.5 do AutoDock Vina."""
    if IS_WINDOWS:
        return (f"vina_{AUTODOCK_VINA_VERSION}_win.exe", f"vina_split_{AUTODOCK_VINA_VERSION}_win.exe")
    return (f"vina_{AUTODOCK_VINA_VERSION}_linux_x86_64", f"vina_split_{AUTODOCK_VINA_VERSION}_linux_x86_64")


def vina_binary_paths(bin_dir: str) -> tuple[str, str]:
    vina, vina_split = vina_binary_names()
    return os.path.join(bin_dir, vina), os.path.join(bin_dir, vina_split)


# ----------------------------------------------------------------------------- Open Babel
def find_obabel(venv_dir: Optional[str] = None) -> Optional[str]:
    """O `obabel`: no PATH, no venv do CODOC (o pacote pip openbabel-wheel, usado no Windows, o
    instala em Scripts\\) e, no Windows, nas pastas de instalação do Open Babel."""
    found = shutil.which("obabel")
    if found:
        return found
    venv_dir = venv_dir or default_venv_dir()
    if venv_dir:
        # openbabel-wheel (Windows): the real obabel.exe is inside the package; Scripts\\obabel.exe only starts
        # Python to call it, which would cost a Python start-up per ligand.
        candidates = [os.path.join(venv_dir, "Lib", "site-packages", "openbabel", "bin", "obabel.exe")]
        candidates += [os.path.join(venv_scripts_dir(venv_dir), name) for name in ("obabel.exe", "obabel")]
        for candidate in candidates:
            if os.path.isfile(candidate):
                return candidate
    if IS_WINDOWS:
        for base in _program_dirs():
            for pattern in ("OpenBabel*", "Open Babel*"):
                for folder in sorted(glob.glob(os.path.join(base, pattern)), reverse=True):
                    candidate = os.path.join(folder, "obabel.exe")
                    if os.path.isfile(candidate):
                        return candidate
    return None


# ----------------------------------------------------------------------------- ADFRsuite
def adfr_prepare_receptor_candidates() -> list[str]:
    """Onde o `prepare_receptor` do ADFRsuite 1.0 pode estar. No Linux é a pasta fixa de sempre
    ($HOME/ADFRsuite-1.0); no Windows o instalador do ADFRsuite escolhe a pasta, então procura nas
    mais comuns (e aceita prepare_receptor.bat / .exe)."""
    roots = [os.path.join(home_dir(), "ADFRsuite-1.0")]
    names = ["prepare_receptor"]
    if IS_WINDOWS:
        names = ["prepare_receptor.bat", "prepare_receptor.exe", "prepare_receptor"]
        for base in _program_dirs():
            roots.extend(sorted(glob.glob(os.path.join(base, "ADFRsuite*"))))
            roots.extend(sorted(glob.glob(os.path.join(base, "*", "ADFRsuite*"))))
    return [os.path.join(root, "bin", name) for root in roots for name in names]


def find_adfr_prepare_receptor() -> Optional[str]:
    for candidate in adfr_prepare_receptor_candidates():
        if os.path.isfile(candidate):
            return candidate
    return None


# ----------------------------------------------------------------------------- Java (P2Rank)
def find_java() -> Optional[str]:
    """O `java`: no PATH, em JAVA_HOME e, no Windows, nas pastas onde os instaladores comuns o colocam. Logo
    depois de instalar o Java pelo winget o PATH deste processo ainda é o antigo, e por isso a procura."""
    found = shutil.which("java")
    if found:
        return found
    names = ["java.exe"] if IS_WINDOWS else ["java"]
    java_home = os.environ.get("JAVA_HOME")
    if java_home:
        for name in names:
            candidate = os.path.join(java_home, "bin", name)
            if os.path.isfile(candidate):
                return candidate
    if IS_WINDOWS:
        for base in _program_dirs():
            for pattern in ("Microsoft/jdk-*", "Eclipse Adoptium/*", "Java/*", "Zulu/*", "Amazon Corretto/*", "BellSoft/*"):
                for folder in sorted(glob.glob(os.path.join(base, *pattern.split("/"))), reverse=True):
                    candidate = os.path.join(folder, "bin", "java.exe")
                    if os.path.isfile(candidate):
                        return candidate
    return None


def java_environment() -> dict:
    """Ambiente para rodar programas Java (P2Rank): se o java só foi achado fora do PATH, o inclui."""
    environment = os.environ.copy()
    java = find_java()
    if java and not shutil.which("java"):
        bin_dir = os.path.dirname(java)
        environment["PATH"] = bin_dir + os.pathsep + environment.get("PATH", "")
        environment.setdefault("JAVA_HOME", os.path.dirname(bin_dir))
    return environment


# ----------------------------------------------------------------------------- P2Rank
def p2rank_launcher_names() -> list[str]:
    return ["prank.bat", "prank"] if IS_WINDOWS else ["prank"]


# ----------------------------------------------------------------------------- abrir pastas
def open_path(path: str) -> None:
    """Abre um arquivo ou pasta no programa padrão do sistema (gerenciador de arquivos)."""
    if IS_WINDOWS:
        os.startfile(path)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])
