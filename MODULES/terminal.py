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

"""Terminal do CODOC (Help > Terminal).

O CODOC é aberto pelo menu sem terminal. Para quem quiser ver as saídas do programa ou rodar
comandos no mesmo ambiente Python, duas peças trabalham juntas:

  * setup_capture()  copia tudo o que o processo escreve em stdout/stderr (inclusive o que os
                     programas filhos e as bibliotecas em C imprimem) para
                     ~/.local/state/CODOC/terminal.log, sem alterar o que vai ao terminal de origem;
  * open_terminal()  abre um emulador de terminal com um bash interativo já dentro do venv do CODOC
                     (python/pip do venv no PATH, pasta do CODOC como diretório atual) que mostra as
                     últimas linhas do log e continua acompanhando as novas enquanto o usuário
                     digita seus comandos.
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import Optional

from MODULES import platform_utils

STATE_DIR = platform_utils.state_dir()          # Linux: ~/.local/state/CODOC ; Windows: %LOCALAPPDATA%\\CODOC
LOG_FILE = STATE_DIR / "terminal.log"
RC_FILE = STATE_DIR / "terminal.bashrc"
HISTORY_LINES = 200          # linhas do log mostradas ao abrir o terminal


class _TeeStream:
    """Windows (sem dup2/pipe de descritores): copia o que o CODOC imprime para o console, se houver, e
    para o log da sessão. Aberto pelo atalho (pythonw.exe) não há console e tudo vai só para o log."""

    def __init__(self, console, log_file) -> None:
        self._console = console
        self._log = log_file

    def write(self, text: str) -> int:
        for stream in (self._console, self._log):
            if stream is None:
                continue
            try:
                stream.write(text)
            except Exception:
                pass
        return len(text)

    def flush(self) -> None:
        for stream in (self._console, self._log):
            try:
                if stream is not None:
                    stream.flush()
            except Exception:
                pass

    def isatty(self) -> bool:
        return False

    encoding = "utf-8"
    errors = "replace"

    def writable(self) -> bool:
        return True

    def fileno(self) -> int:
        # whoever asks for a descriptor (a subprocess given sys.stdout, faulthandler) gets the log file
        return self._log.fileno()


def _setup_capture_windows() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    log_file = open(LOG_FILE, "w", encoding="utf-8", errors="replace", buffering=1)
    console = sys.stdout if (sys.stdout is not None and sys.stdout.isatty()) else None
    sys.stdout = sys.stderr = _TeeStream(console, log_file)


def setup_capture() -> None:
    """Duplica stdout/stderr (nível de descritor de arquivo) para LOG_FILE. Chamar uma única vez,
    no processo principal. Nunca impede o programa de iniciar."""
    if platform_utils.IS_WINDOWS:
        try:
            _setup_capture_windows()
        except Exception:
            pass
        return
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        log_fp = open(LOG_FILE, "wb", buffering=0)
        origin = []
        for fd in (1, 2):
            try:
                origin.append(os.dup(fd))
            except OSError:               # started without stdout/stderr (e.g. from the menu)
                origin.append(-1)
        read_fd, write_fd = os.pipe()
        os.dup2(write_fd, 1)
        os.dup2(write_fd, 2)
        os.close(write_fd)
        origin_out = origin[0]

        def pump() -> None:
            while True:
                try:
                    chunk = os.read(read_fd, 65536)
                except OSError:
                    return
                if not chunk:
                    return
                try:
                    log_fp.write(chunk)
                except OSError:
                    pass
                if origin_out >= 0:
                    try:
                        os.write(origin_out, chunk)
                    except OSError:
                        pass                # the original terminal was closed

        threading.Thread(target=pump, name="codoc-terminal-capture", daemon=True).start()
        for stream in (sys.stdout, sys.stderr):
            try:
                stream.reconfigure(line_buffering=True)
            except Exception:
                pass
    except Exception:
        pass


def _write_rc(app_dir: str, venv_dir: str) -> None:
    activate = os.path.join(venv_dir, "bin", "activate")
    lines = [
        '[ -f "$HOME/.bashrc" ] && . "$HOME/.bashrc"',
        f"[ -f {shlex.quote(activate)} ] && . {shlex.quote(activate)}",
        "export PYTHONNOUSERSITE=1",
        f"cd {shlex.quote(app_dir)}",
        "set +m",
        f"tail -n {HISTORY_LINES} -F {shlex.quote(str(LOG_FILE))} 2>/dev/null &",
        "CODOC_TAIL_PID=$!",
        "disown",
        "trap 'kill $CODOC_TAIL_PID 2>/dev/null' EXIT",
        'echo "[CODOC] Terminal - Python: $(command -v python)"',
        'echo "[CODOC] The lines above are the output of the running CODOC; type any command below."',
    ]
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    RC_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def terminal_command(emulator: str, shell_cmd: list[str]) -> list[str]:
    """Command line that runs `shell_cmd` inside terminal emulator `emulator`."""
    name = os.path.basename(emulator)
    if name == "gnome-terminal":
        return [emulator, "--title=CODOC Terminal", "--"] + shell_cmd
    if name == "xfce4-terminal":
        return [emulator, "--title=CODOC Terminal", "--command", " ".join(shlex.quote(a) for a in shell_cmd)]
    if name == "xterm":
        return [emulator, "-T", "CODOC Terminal", "-e"] + shell_cmd
    return [emulator, "-e"] + shell_cmd          # x-terminal-emulator, konsole, ...


def _windows_terminal_script(app_dir: str, venv_dir: str) -> str:
    def quote(text: str) -> str:
        return "'" + text.replace("'", "''") + "'"

    activate = os.path.join(venv_dir, "Scripts", "Activate.ps1")
    return "\n".join([
        "$Host.UI.RawUI.WindowTitle = 'CODOC Terminal'",
        f"if (Test-Path -LiteralPath {quote(activate)}) {{ . {quote(activate)} }}",
        "$env:PYTHONNOUSERSITE = '1'",
        f"Set-Location -LiteralPath {quote(app_dir)}",
        f"$log = {quote(str(LOG_FILE))}",
        f"if (Test-Path -LiteralPath $log) {{ Get-Content -LiteralPath $log -Tail {HISTORY_LINES} }}",
        # segue o log ao vivo numa tarefa em segundo plano, como o `tail -F &` do Linux
        "$follow = [powershell]::Create().AddScript({ param($f)",
        "  $stream = [System.IO.File]::Open($f, 'Open', 'Read', 'ReadWrite')",
        "  $reader = New-Object System.IO.StreamReader($stream)",
        "  $null = $reader.ReadToEnd()",
        "  while ($true) { $line = $reader.ReadLine(); if ($null -ne $line) { [Console]::WriteLine($line) } else { Start-Sleep -Milliseconds 300 } }",
        "}).AddArgument($log)",
        "if (Test-Path -LiteralPath $log) { $null = $follow.BeginInvoke() }",
        "Write-Host '[CODOC] Terminal - Python:' (Get-Command python).Source",
        "Write-Host '[CODOC] The lines above are the output of the running CODOC; type any command below.'",
    ])


def _open_terminal_windows(app_dir: str, venv_dir: str) -> bool:
    import base64

    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        encoded = base64.b64encode(_windows_terminal_script(app_dir, venv_dir).encode("utf-16-le")).decode("ascii")
        subprocess.Popen(
            ["powershell", "-NoLogo", "-NoProfile", "-NoExit", "-ExecutionPolicy", "Bypass", "-EncodedCommand", encoded],
            cwd=app_dir, creationflags=subprocess.CREATE_NEW_CONSOLE,
        )
        return True
    except OSError:
        return False


def open_terminal(app_dir: str, venv_dir: str) -> bool:
    """Abre o terminal descrito no cabeçalho do módulo. Devolve False se não há emulador instalado."""
    if platform_utils.IS_WINDOWS:
        return _open_terminal_windows(app_dir, venv_dir)
    try:
        _write_rc(app_dir, venv_dir)
    except OSError:
        return False
    shell_cmd = ["bash", "--rcfile", str(RC_FILE), "-i"]
    for emulator in ("x-terminal-emulator", "gnome-terminal", "konsole", "xfce4-terminal", "xterm"):
        path: Optional[str] = shutil.which(emulator)
        if not path:
            continue
        try:
            subprocess.Popen(terminal_command(path, shell_cmd), cwd=app_dir, start_new_session=True)
            return True
        except OSError:
            continue
    return False
