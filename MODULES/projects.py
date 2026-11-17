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

"""Projetos do CODOC (mesmo formato do CODYN/CODEEP).

Cada projeto é uma pasta  PROJECTS/<AAAA-MM-DD_HH-MM>_<nome>/  na raiz do CODOC:

    CONVERSION/            preparo dos ligantes do projeto
        LIGANDS/           pasta-base da conversão: arquivos após o split e, no fim, os .pdbqt
        CONVERSION_FAILURES/, EMPTY_LIGANDS/, NO_DRUGGABILITY/, DATAFRAMES/, MACROCYCLES/ ...
        ligand_settings.json     parâmetros da ETAPA 1
    TARGETS/               alvos preparados (uma subpasta por alvo)
        target_settings.json     parâmetros da ETAPA 2
    DOCKING/               resultados do docking (<alvo>/<grupo de ligantes>/<ligante>/)
        docking_settings.json    parâmetros do CONFIG, grid da ETAPA 2 e opções da ETAPA 3
        results_settings.json    filtros da ETAPA 4
    REDOCK_REFERENCE/      poses cristalográficas de referência para o RMSD do redocking

Assim os arquivos de cada trabalho ficam separados dos de outros projetos/usuários e um projeto
pode ser retomado depois carregando os .json de cada etapa.

Este módulo não depende de PyQt além do ProjectManager (que emite o sinal `changed`).
"""

from __future__ import annotations

import os
import re
from datetime import datetime
from typing import List, Optional

from PyQt5.QtCore import QObject, pyqtSignal

PROJECTS_DIRNAME = "PROJECTS"
LEGACY_JOBS_DIRNAME = "JOBS"              # nome da pasta raiz nas versões anteriores
STAMP_FMT = "%Y-%m-%d_%H-%M"

CONVERSION_DIRNAME = "CONVERSION"
LIGANDS_DIRNAME = "LIGANDS"               # dentro de CONVERSION/
TARGETS_DIRNAME = "TARGETS"
DOCKING_DIRNAME = "DOCKING"
REFERENCE_DIRNAME = "REDOCK_REFERENCE"

LIGAND_SETTINGS_FILE = "ligand_settings.json"
TARGET_SETTINGS_FILE = "target_settings.json"
DOCKING_SETTINGS_FILE = "docking_settings.json"
RESULTS_SETTINGS_FILE = "results_settings.json"

# subpastas criadas (se faltarem) sempre que um projeto é criado ou aberto
SUBDIRS = (
    os.path.join(CONVERSION_DIRNAME, LIGANDS_DIRNAME),
    TARGETS_DIRNAME,
    DOCKING_DIRNAME,
)


def projects_root(app_dir: str) -> str:
    return os.path.join(app_dir, PROJECTS_DIRNAME)


def migrate_legacy_jobs_dir(app_dir: str) -> bool:
    """Renomeia a antiga pasta JOBS/ para PROJECTS/ (uma única vez, sem copiar nada: é um simples
    os.rename dentro do mesmo diretório). Só age se JOBS existir e PROJECTS não existir ou estiver
    vazia. Devolve True se renomeou."""
    old = os.path.join(app_dir, LEGACY_JOBS_DIRNAME)
    new = projects_root(app_dir)
    if not os.path.isdir(old):
        return False
    if os.path.isdir(new) and not os.listdir(new):
        os.rmdir(new)          # an empty PROJECTS (created at startup) must not block the rename
    if os.path.exists(new):
        return False
    try:
        os.rename(old, new)
    except OSError:
        return False
    return True


def list_projects(app_dir: str) -> List[str]:
    """Nomes das pastas de projeto, as mais recentes primeiro."""
    root = projects_root(app_dir)
    if not os.path.isdir(root):
        return []
    return sorted((d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d))), reverse=True)


def clean_project_name(name: str) -> str:
    """Nome seguro para pasta: sem espaços nem caracteres que quebrem caminhos/shell."""
    name = re.sub(r"\s+", "_", (name or "").strip())
    name = re.sub(r"[^\w.\-]", "", name, flags=re.UNICODE)
    return name.strip("._-")


def project_id(name: str, when: Optional[datetime] = None) -> str:
    name = clean_project_name(name)
    return f"{(when or datetime.now()).strftime(STAMP_FMT)}_{name}" if name else ""


def ensure_subdirs(path: str) -> None:
    for sub in SUBDIRS:
        os.makedirs(os.path.join(path, sub), exist_ok=True)


def create_project(app_dir: str, name: str, when: Optional[datetime] = None) -> str:
    """Cria PROJECTS/<data>_<nome>/ com as subpastas do projeto. Levanta ValueError (nome vazio)
    ou FileExistsError (projeto já existe)."""
    pid = project_id(name, when)
    if not pid:
        raise ValueError("empty project name")
    path = os.path.join(projects_root(app_dir), pid)
    if os.path.exists(path):
        raise FileExistsError(path)
    os.makedirs(path)
    ensure_subdirs(path)
    return path


class ProjectManager(QObject):
    """Projeto aberto no momento. Quem precisa das pastas consulta as propriedades abaixo e
    reage ao sinal `changed` (caminho do projeto ou '' quando nenhum está aberto)."""

    changed = pyqtSignal(str)

    def __init__(self, app_dir: str, parent=None):
        super().__init__(parent)
        self.app_dir = app_dir
        self._path = ""

    # ------------------------------------------------------------------ estado ------------------------------------------------------------------
    @property
    def path(self) -> str:
        return self._path

    @property
    def name(self) -> str:
        return os.path.basename(self._path) if self._path else ""

    @property
    def is_open(self) -> bool:
        return bool(self._path) and os.path.isdir(self._path)

    # ------------------------------------------------------------------ pastas (vazias enquanto nenhum projeto está aberto) ------------------------------------------------------------------
    def _sub(self, *parts: str) -> str:
        return os.path.join(self._path, *parts) if self._path else ""

    @property
    def conversion_dir(self) -> str:
        return self._sub(CONVERSION_DIRNAME)

    @property
    def ligands_dir(self) -> str:
        return self._sub(CONVERSION_DIRNAME, LIGANDS_DIRNAME)

    @property
    def targets_dir(self) -> str:
        return self._sub(TARGETS_DIRNAME)

    @property
    def docking_dir(self) -> str:
        return self._sub(DOCKING_DIRNAME)

    @property
    def reference_dir(self) -> str:
        return self._sub(REFERENCE_DIRNAME)

    # ------------------------------------------------------------------ arquivos .json de cada etapa ------------------------------------------------------------------
    @property
    def ligand_settings_path(self) -> str:
        return self._sub(CONVERSION_DIRNAME, LIGAND_SETTINGS_FILE)

    @property
    def target_settings_path(self) -> str:
        return self._sub(TARGETS_DIRNAME, TARGET_SETTINGS_FILE)

    @property
    def docking_settings_path(self) -> str:
        return self._sub(DOCKING_DIRNAME, DOCKING_SETTINGS_FILE)

    @property
    def results_settings_path(self) -> str:
        return self._sub(DOCKING_DIRNAME, RESULTS_SETTINGS_FILE)

    # ------------------------------------------------------------------ abrir / fechar ------------------------------------------------------------------
    def open(self, path: str) -> bool:
        """Abre um projeto existente (recria subpastas que tenham sido apagadas)."""
        if not path or not os.path.isdir(path):
            return False
        ensure_subdirs(path)
        self._path = os.path.abspath(path)
        self.changed.emit(self._path)
        return True

    def close(self) -> None:
        self._path = ""
        self.changed.emit("")
