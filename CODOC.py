#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pyright: reportAttributeAccessIssue=false, reportOptionalMemberAccess=false, reportMissingImports=false

# SPDX-License-Identifier: GPL-3.0-or-later
#
# GitFace – A management interface for Git tools
# Copyright (C) 2024-2026 Moisés Maia
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.


from __future__ import annotations

import csv
import importlib
import importlib.metadata
import json
import multiprocessing
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import webbrowser
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field, fields as dataclass_fields
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

os.environ.setdefault("PYTHONNOUSERSITE", "1")


def _bootstrap_codoc_venv() -> None:
    if os.environ.get("CODOC_VENV_ACTIVE") == "1":
        return
    try:
        from MODULES.module_requirements import bootstrap_pyqt5
    except Exception as exc:
        print(f"[CODOC] Failed to import bootstrap module: {exc}")
        sys.exit(1)
    if not bootstrap_pyqt5(interactive=True, reexec=True, env_name="CODOC"):
        sys.exit(1)


_bootstrap_codoc_venv()

try:
    import pandas as pd
except Exception:
    pd = None

try:
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.backends.backend_qt import NavigationToolbar2QT as NavigationToolbar
except Exception:
    plt = None
    FigureCanvas = None
    NavigationToolbar = None

try:
    import psutil
except Exception:
    psutil = None

try:
    from rdkit import Chem
    from rdkit.Chem import AllChem, Crippen, Descriptors, Lipinski, MolSurf
except Exception:
    Chem = None
    AllChem = None
    Crippen = None
    Descriptors = None
    Lipinski = None
    MolSurf = None

try:
    from meeko import MoleculePreparation, PDBQTMolecule, PDBQTWriterLegacy, RDKitMolCreate
except Exception:
    MoleculePreparation = None
    PDBQTMolecule = None
    PDBQTWriterLegacy = None
    RDKitMolCreate = None

try:
    import dimorphite_dl
except Exception:
    dimorphite_dl = None

try:
    from MODULES import module_compound_names
except Exception:
    module_compound_names = None

from PyQt5.QtCore import QSettings, QSize, QThread, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QFontMetrics, QGuiApplication, QIcon, QPixmap
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QAction,
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHeaderView,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QDoubleSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QTreeView,
    QListView,
    QVBoxLayout,
    QWidget,
)

from MODULES.versao import VERSAO
from MODULES.module_requirements import RequirementsInstaller, detect_hardware, detect_opencl_devices, get_boost_version, get_vina_gpu_version, venv_paths
from MODULES.module_target_prepare import (
    TargetPrepareError,
    detect_pockets_p2rank,
    find_pdb2pqr,
    prepare_receptor_with_protonation,
    summarize_pka_table,
)
from MODULES.module_report import generate_final_report as _generate_final_report_docx, load_job_settings
from MODULES.splash_screen import SplashScreen
from MODULES import i18n
from MODULES import module_cocrystal
from MODULES import terminal as codoc_terminal
from MODULES.projects import (
    ProjectManager,
    clean_project_name,
    create_project,
    list_projects,
    migrate_legacy_jobs_dir,
    projects_root,
)

_QtGroupBox = QGroupBox   # original Qt class (QGroupBox is rebound to the collapsible version below)


class CollapsibleGroupBox(_QtGroupBox):
    """QGroupBox that collapses/expands when its title is clicked (same behaviour as the groups of
    CODRUG). Every QGroupBox of CODOC is of this class (see the rebind right below), so the
    groups pile up under the title of the one that was collapsed and the tab content moves up.
    Groups without a title do not collapse (there is nowhere to click).

    Collapsing hides only the DIRECT child widgets of the group (nested ones disappear with them,
    keeping their own visibility state) and fixes the height to that of the title; expanding shows
    again only the ones that were visible before and restores the original minimum/maximum height.
    An arrow in the title shows the state."""

    _ARROW_OPEN = "\u25BE "
    _ARROW_CLOSED = "\u25B8 "

    # Emitted only when the USER collapses/expands by clicking the title (not by set_collapsed()
    # called from code); the argument is the new "collapsed" state.
    userToggled = pyqtSignal(bool)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._collapsed = False
        self._base_title = _QtGroupBox.title(self)
        self._restore_visible: list = []
        self._restore_min_h = 0
        self._restore_max_h = 16777215
        self._refresh_title()

    # ---- title (the clean text stays available through title()) ----
    def setTitle(self, title):
        self._base_title = str(title or "")
        self._refresh_title()

    def title(self):
        return self._base_title

    def _refresh_title(self):
        if not self._base_title:
            _QtGroupBox.setTitle(self, "")
            return
        arrow = self._ARROW_CLOSED if self._collapsed else self._ARROW_OPEN
        _QtGroupBox.setTitle(self, arrow + self._base_title)

    # ---- collapse ----
    def is_collapsed(self):
        return self._collapsed

    def _direct_child_widgets(self):
        return [c for c in self.children() if isinstance(c, QWidget) and not c.isWindow()]

    def _collapsed_height(self):
        return max(28, self.fontMetrics().height() + 14)

    def set_collapsed(self, collapsed):
        collapsed = bool(collapsed) and bool(self._base_title)
        if collapsed == self._collapsed:
            return
        if collapsed:
            children = self._direct_child_widgets()
            # only a widget explicitly hidden by the program counts as "hidden on purpose"
            self._restore_visible = [
                w for w in children
                if not (w.isHidden() and w.testAttribute(Qt.WA_WState_ExplicitShowHide))
            ]
            self._restore_min_h = self.minimumHeight()
            self._restore_max_h = self.maximumHeight()
            for w in children:
                w.setVisible(False)
            self._collapsed = True
            self.setFixedHeight(self._collapsed_height())
        else:
            self._collapsed = False
            self.setMinimumHeight(self._restore_min_h)
            self.setMaximumHeight(self._restore_max_h)
            for w in self._restore_visible:
                w.setVisible(True)
            self._restore_visible = []
        self._refresh_title()
        self.updateGeometry()

    def mousePressEvent(self, event):
        if (event.button() == Qt.LeftButton and self._base_title
                and event.pos().y() <= self._collapsed_height()):
            self.set_collapsed(not self._collapsed)
            event.accept()
            self.userToggled.emit(self._collapsed)
            return
        super().mousePressEvent(event)


# Colour palette (the accent follows the CODOC logo, teal #006680):
#   ACCENT  #29B6D8  selected tab, group titles, focus, primary buttons
#   ACCENT2 #1893B3  hover and text selection
#   LOGO    #006680  pressed buttons and progress bars
# Green stays only where it means "ok" (project open, CPU/GPU monitor).

# Every QGroupBox created from here on in CODOC is collapsible.
QGroupBox = CollapsibleGroupBox


APP_NAME = "CODOC"
APP_DIR_NAME = "CODOC"

_SS_MAIN = """
QMainWindow, QWidget {
    background-color: #0D1B2A;
    color: #C9D1D9;
    font-family: 'DejaVu Sans', 'Segoe UI', sans-serif;
    font-size: 10pt;
}
QGroupBox {
    font-weight: bold;
    border: 1.5px solid #2A4A6B;
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 8px;
    background: transparent;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: #29B6D8;
}
QLabel {
    background: transparent;
}
QLabel:disabled {
    color: #4A5A66;
}
QLineEdit, QComboBox, QPlainTextEdit, QTextEdit, QTableWidget, QSpinBox, QDoubleSpinBox {
    border: 1px solid #2A4A6B;
    border-radius: 4px;
    padding: 4px 8px;
    background: #1C3249;
    color: #C9D1D9;
    selection-background-color: #1893B3;
}
QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus, QTextEdit:focus, QTableWidget:focus {
    border: 2px solid #29B6D8;
}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {
    background: #17222E;
    color: #4A5A66;
    border-color: #22374A;
}
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
QMenuBar {
    background: #0D1B2A;
    color: #C9D1D9;
    border-bottom: 1px solid #2A4A6B;
}
QMenuBar::item:selected {
    background: #1C3249;
    color: #29B6D8;
}
QMenu {
    background: #14253A;
    color: #C9D1D9;
    border: 1px solid #2A4A6B;
}
QMenu::item:selected {
    background: #1C3249;
    color: #29B6D8;
}
QTabWidget::pane {
    border: 1px solid #2A4A6B;
    border-radius: 6px;
    background: #14253A;
}
QTabBar::tab {
    background: #0D1B2A;
    color: #6E8CA8;
    padding: 7px 14px;
    min-width: 80px;
    font-weight: bold;
}
QTabBar::tab:selected {
    background: #14253A;
    color: #29B6D8;
    border-bottom: 3px solid #29B6D8;
}
QCheckBox { color: #C9D1D9; spacing: 6px; }
QCheckBox::indicator {
    width: 14px; height: 14px;
    border: 1px solid #2A4A6B;
    border-radius: 3px;
    background: #1C3249;
}
QCheckBox::indicator:checked {
    background: #29B6D8;
    border-color: #29B6D8;
}
QCheckBox::indicator:disabled {
    background: #17222E;
    border-color: #22374A;
}
QCheckBox::indicator:checked:disabled {
    background: #1B5A6B;
    border-color: #1B5A6B;
}
QProgressBar {
    border: 1px solid #2A4A6B;
    border-radius: 4px;
    text-align: center;
    background: #1C3249;
}
QProgressBar::chunk {
    background: #006680;
}
"""

_SS_BTN_NAV = """
QPushButton {
    background: transparent;
    border: none;
    color: #6E8CA8;
    font-size: 10pt;
    font-weight: bold;
    padding: 4px 10px;
}
QPushButton:hover {
    color: #C9D1D9;
}
QPushButton:pressed {
    color: #29B6D8;
}
QPushButton:disabled {
    color: #2A4A6B;
}
"""

_SS_BTN_SECONDARY = """
QPushButton {
    background: #243746;
    color: #A9BED1;
    font-weight: bold;
    border: 1px solid #6E8CA8;
    border-radius: 5px;
    padding: 6px 16px;
}
QPushButton:hover { background: #37536C; color: #C9D1D9; }
QPushButton:pressed { background: #1C3249; color: #FFF; }
QPushButton:disabled { background: #1B2730; color: #4F6577; border-color: #344654; }
"""


@dataclass
class DockingSettings:
    scoring_function: str = "vina"
    docking_mode: str = "normal"
    docking_type: str = "Rigid"
    processing_type: str = "CPU"
    opencl_platform_id: int = -1
    opencl_device_id: int = -1
    split_results: bool = False
    cpu_threads: int = max(1, os.cpu_count() or 1)
    exhaustiveness: int = max(1, os.cpu_count() or 1)
    gpu_threads: int = 8000
    poses: int = 9
    min_rmsd: float = 1.0
    energy_range: float = 3.0
    spacing: float = 1.0
    grid_x_size: int = 30
    grid_y_size: int = 30
    grid_z_size: int = 30
    grid_x_center: float = 0.0
    grid_y_center: float = 0.0
    grid_z_center: float = 0.0
    target_ph: float = 7.4


# The limits of the Druggability Filter (STEP 1): LigandSettings attribute names, in the order shown.
DRUGGABILITY_LIMITS = (
    "mw_min", "mw_max", "logp_min", "logp_max",
    "h_donor_max", "h_acceptor_max", "rotatable_bonds_max", "tpsa_max",
)


@dataclass
class LigandSettings:
    min_file_size: int = 10
    ph: float = 7.4
    max_ligands_per_folder: int = 50000
    rejected_elements: str = "nan|As|Bi|Si|B"
    conversion_engine: str = "RDKit"
    conversion_workers: int = max(1, os.cpu_count() or 1)
    minimization_steps: int = 1500
    minimization_algorithm: str = "Conjugate Gradient"
    minimization_forcefield: str = "GAFF"
    mw_min: float = 0.0
    mw_max: float = 500.0
    logp_min: float = -5.0
    logp_max: float = 5.0
    rotatable_bonds_max: int = 10
    h_donor_max: int = 5
    h_acceptor_max: int = 10
    tpsa_max: float = 140.0
    # Which of the eight limits above "Apply druggability filter" applies (settings attribute name -> on/off).
    druggability_enabled: dict[str, bool] = field(default_factory=lambda: dict.fromkeys(DRUGGABILITY_LIMITS, True))
    # Files and folders the user imported into this project (STEP 1 "Ligands" > Browse). Only a
    # record - the copies live in CONVERSION/LIGANDS; the originals are never touched.
    ligand_sources: list[str] = field(default_factory=list)


@dataclass
class TargetSettings:
    """What the STEP 2 form held when it was last saved (the grid numbers, pH and spacing live in
    DockingSettings because the docking worker and the final report read them from there)."""
    mode_index: int = 0           # 0 = Rigid Docking, 1 = Flexible Docking
    target_name: str = ""
    target_file: str = ""
    rigid_file: str = ""
    flex_file: str = ""
    grid_file: str = ""
    grid_ligand_file: str = ""


@dataclass
class ResultViewSettings:
    top_results: int = 20
    rmsd_limit: float = 2.0


def _known_dataclass_kwargs(dataclass_type: type, data: dict[str, Any]) -> dict[str, Any]:
    """Drops any key in `data` that isn't a current field of `dataclass_type`, so loading an
    older project .json file - saved before a field was removed (e.g. the old ligand-conversion
    speed_first/speed_second/timeout_first/timeout_second knobs) - degrades to that field's
    current default instead of TypeError'ing the whole settings load."""
    valid_names = {field.name for field in dataclass_fields(dataclass_type)}
    return {key: value for key, value in data.items() if key in valid_names}


def _parse_vina_pose_data(output_file: str) -> tuple[str, str, str]:
    """Read a multi-model Vina PDBQT and return (best energy, mean RMSD across all poses, SMILES).

    Each MODEL's "REMARK VINA RESULT:" line reports that pose's RMSD lower bound
    relative to pose 1 (the reference pose, whose own RMSD is always 0.000), so the
    mean must be computed across every pose in the file rather than reading pose 1 alone.
    The ligand's SMILES is repeated as a "REMARK SMILES" line on every pose, so the
    first occurrence found is used.
    """
    energy = ""
    smiles = ""
    rmsd_values: list[float] = []
    if os.path.isfile(output_file):
        with open(output_file, "r", encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                if not smiles and line.startswith("REMARK SMILES"):
                    smiles = line.split("REMARK SMILES", 1)[1].strip()
                elif "REMARK VINA RESULT:" in line:
                    parts = line.strip().split()
                    if len(parts) >= 5:
                        if not energy:
                            energy = parts[3]
                        try:
                            rmsd_values.append(float(parts[4]))
                        except ValueError:
                            pass
    rmsd_mean = f"{sum(rmsd_values) / len(rmsd_values):.3f}" if rmsd_values else ""
    return energy, rmsd_mean, smiles


RESULT_CSV_HEADER = ["LIGAND", "SMILES", "LIGAND DATABANK", "TARGET", "BINDING ENERGY (Kcal/mol)", "RMSD (mean)"]


def _parse_grid_file(path: str) -> dict[str, float | int]:
    """Values found in a grid.txt (`spacing`, `npts` = box size and `center` lines): any of
    spacing, size_x/y/z and center_x/y/z that the file holds."""
    grid: dict[str, float | int] = {}
    with open(path, "r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            parts = line.strip().split()
            if len(parts) >= 4 and parts[0] == "center":
                grid.update(center_x=float(parts[1]), center_y=float(parts[2]), center_z=float(parts[3]))
            elif len(parts) >= 4 and parts[0] == "npts":
                grid.update(size_x=int(float(parts[1])), size_y=int(float(parts[2])), size_z=int(float(parts[3])))
            elif len(parts) >= 2 and parts[0] == "spacing":
                grid["spacing"] = float(parts[1])
    return grid


class DockingWorker(QThread):
    progress_value = pyqtSignal(int)
    progress_text = pyqtSignal(str)
    finished_ok = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(
        self,
        app_dir: str,
        ligands_dir: str,
        targets_dir: str,
        results_dir: str,
        job_name: str,
        settings: DockingSettings,
        docking_type: str,
        processing_type: str,
    ) -> None:
        super().__init__()
        self.app_dir = app_dir
        self.ligands_dir = ligands_dir
        self.targets_dir = targets_dir
        self.results_dir = results_dir
        self.job_name = job_name
        self.settings = settings
        self.docking_type = docking_type
        self.processing_type = processing_type
        self.skipped_existing = 0   # ligands whose result is already in the project (resume)
        self.vina = os.path.join(app_dir, "BIN", "vina_1.2.5_linux_x86_64")
        self.vina_split = os.path.join(app_dir, "BIN", "vina_split_1.2.5_linux_x86_64")
        self.vina_gpu = os.path.join(str(Path.home()), "Vina-GPU-2.1", "AutoDock-Vina-GPU-2.1", "AutoDock-Vina-GPU-2-1")

    def run(self) -> None:
        try:
            self._validate_environment()
            result_folder = self._prepare_result_folder()
            pending_jobs = self._build_pending_jobs(result_folder)
            if self.skipped_existing:
                self.progress_text.emit(
                    f"Resuming project {self.job_name}: {self.skipped_existing} ligand(s) already docked were skipped."
                )
            if not pending_jobs:
                if self.skipped_existing:
                    self.finished_ok.emit(f"No pending docking jobs were found in {self.job_name}: every ligand is already docked.")
                else:
                    self.failed.emit(
                        f"No PDBQT ligands were found in {self.ligands_dir}. Import and convert ligands in STEP 1 first."
                    )
                return

            if self.processing_type == "GPU":
                self._run_gpu_jobs(result_folder, pending_jobs)
            else:
                self._run_cpu_jobs(result_folder, pending_jobs)
            self.finished_ok.emit(f"Docking finished for project {self.job_name}. Results available in {result_folder}.")
        except Exception as exc:
            self.failed.emit(str(exc))

    def _validate_environment(self) -> None:
        if not os.path.isdir(self.ligands_dir):
            raise RuntimeError(f"Ligands directory not found: {self.ligands_dir}")
        if not os.path.isdir(self.targets_dir) or not any(p.is_dir() for p in Path(self.targets_dir).iterdir()):
            raise RuntimeError(
                f"No prepared targets found in {self.targets_dir}. Prepare at least one target in STEP 2 first."
            )
        if self.processing_type == "GPU" and self.settings.docking_mode != "normal":
            raise RuntimeError("score_only and local_only are available only for CPU runs with AutoDock Vina.")
        if self.processing_type == "GPU":
            if not os.path.isfile(self.vina_gpu):
                raise RuntimeError(
                    "Vina-GPU executable not found at "
                    f"{self.vina_gpu}. Install the GPU backend first."
                )
        elif not os.path.isfile(self.vina):
            raise RuntimeError(f"AutoDock Vina not found: {self.vina}")

    def _prepare_result_folder(self) -> str:
        # `self.results_dir` is the DOCKING folder of the open project. Running docking again in the
        # same project resumes it: ligands that already have a result are skipped (see
        # _build_pending_jobs). No per-run subfolder is created.
        os.makedirs(self.results_dir, exist_ok=True)
        for target_dir in sorted(p for p in Path(self.targets_dir).glob("*/") if p.is_dir()):
            os.makedirs(os.path.join(self.results_dir, target_dir.name), exist_ok=True)
        return self.results_dir

    def _build_pending_jobs(self, result_folder: str) -> list[dict[str, str]]:
        jobs: list[dict[str, str]] = []
        for target_path in sorted(p for p in Path(self.targets_dir).glob("*/") if p.is_dir()):
            target_name = target_path.name
            target_requirements = self._target_requirements(target_path)
            result_target_dir = os.path.join(result_folder, target_name)
            os.makedirs(result_target_dir, exist_ok=True)
            for lig_group in sorted(p for p in Path(self.ligands_dir).glob("*/") if p.is_dir()):
                lig_group_name = lig_group.name
                lig_result_group_dir = os.path.join(result_target_dir, lig_group_name)
                os.makedirs(lig_result_group_dir, exist_ok=True)
                for ligand_file in sorted(lig_group.glob("*.pdbqt")):
                    ligand_name = ligand_file.stem
                    ligand_out_dir = os.path.join(lig_result_group_dir, ligand_name)
                    ligand_out_file = os.path.join(ligand_out_dir, f"{ligand_name}.pdbqt")
                    if os.path.isfile(ligand_out_file):
                        self.skipped_existing += 1
                        continue
                    jobs.append(
                        {
                            "target_name": target_name,
                            "target_dir": str(target_path),
                            "ligand_group": lig_group_name,
                            "ligand_file": str(ligand_file),
                            "ligand_name": ligand_name,
                            "output_dir": ligand_out_dir,
                            "output_file": ligand_out_file,
                            **target_requirements,
                        }
                    )
        return jobs

    def _target_requirements(self, target_path: Path) -> dict[str, str]:
        grid_path = target_path / "grid.txt"
        if not grid_path.is_file():
            raise RuntimeError(f"Missing grid.txt in {target_path}")

        if self.docking_type == "Flexible":
            rigid_path = target_path / "protein_rigid.pdbqt"
            flex_path = target_path / "protein_flex.pdbqt"
            if not rigid_path.is_file() or not flex_path.is_file():
                raise RuntimeError(f"Missing flexible receptor files in {target_path}")
            receptor_path = str(rigid_path)
            flex_receptor = str(flex_path)
        else:
            protein_path = target_path / "protein.pdbqt"
            if not protein_path.is_file():
                raise RuntimeError(f"Missing protein.pdbqt in {target_path}")
            receptor_path = str(protein_path)
            flex_receptor = ""

        grid = self._read_grid_file(grid_path)
        return {
            "receptor": receptor_path,
            "flex_receptor": flex_receptor,
            "center_x": str(grid["center_x"]),
            "center_y": str(grid["center_y"]),
            "center_z": str(grid["center_z"]),
            "size_x": str(grid["size_x"]),
            "size_y": str(grid["size_y"]),
            "size_z": str(grid["size_z"]),
        }

    def _read_grid_file(self, path: Path) -> dict[str, float | int]:
        grid = {
            "center_x": self.settings.grid_x_center,
            "center_y": self.settings.grid_y_center,
            "center_z": self.settings.grid_z_center,
            "size_x": self.settings.grid_x_size,
            "size_y": self.settings.grid_y_size,
            "size_z": self.settings.grid_z_size,
        }
        grid.update(_parse_grid_file(str(path)))
        return grid

    def _run_cpu_jobs(self, result_folder: str, jobs: list[dict[str, str]]) -> None:
        total = len(jobs)
        csv_path = self._run_csv_path(result_folder)
        self._ensure_result_csv(csv_path)
        for index, job in enumerate(jobs, start=1):
            os.makedirs(job["output_dir"], exist_ok=True)
            config_path = os.path.join(job["output_dir"], "config.txt")
            self._write_cpu_config(config_path, job)
            self.progress_value.emit(int(index * 100 / max(total, 1)))
            self.progress_text.emit(
                f"Running {self.docking_type} docking on {job['ligand_name']} against {job['target_name']} "
                f"({index}/{total})"
            )
            result = subprocess.run([self.vina, "--config", config_path], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            if result.returncode != 0:
                raise RuntimeError(
                    f"Docking failed for ligand {job['ligand_name']} and target {job['target_name']}:\n{result.stdout}"
                )
            if self.settings.split_results and os.path.isfile(self.vina_split):
                subprocess.run([self.vina_split, "--input", job["output_file"]], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            self._append_csv_result(csv_path, job["target_name"], job["ligand_group"], job["ligand_name"], job["output_file"])

    def _run_gpu_jobs(self, result_folder: str, jobs: list[dict[str, str]]) -> None:
        grouped: dict[tuple[str, str], list[dict[str, str]]] = {}
        for job in jobs:
            grouped.setdefault((job["target_name"], job["ligand_group"]), []).append(job)

        total = len(grouped)
        csv_path = self._run_csv_path(result_folder)
        self._ensure_result_csv(csv_path)
        self.progress_text.emit(
            f"Using OpenCL selection: platform_id={self.settings.opencl_platform_id} "
            f"device_id={self.settings.opencl_device_id}"
        )
        for index, ((target_name, ligand_group), group_jobs) in enumerate(grouped.items(), start=1):
            ligand_dir = str(Path(group_jobs[0]["ligand_file"]).parent)
            output_dir = os.path.join(result_folder, target_name, ligand_group)
            config_path = os.path.join(output_dir, "gpu_config.txt")
            self._write_gpu_config(config_path, group_jobs[0], ligand_dir, output_dir)
            self.progress_text.emit(f"Running GPU docking on group {ligand_group} against {target_name} ({index}/{total})")
            result = subprocess.run(
                [self.vina_gpu, "--config", config_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=self.app_dir,
            )
            if result.returncode != 0:
                raise RuntimeError(f"GPU docking failed for {target_name}/{ligand_group}:\n{result.stdout}")

            for job in group_jobs:
                flat_output = os.path.join(output_dir, f"{job['ligand_name']}_out.pdbqt")
                if not os.path.isfile(flat_output):
                    alt_output = os.path.join(output_dir, f"{job['ligand_name']}.pdbqt")
                    if os.path.isfile(alt_output):
                        flat_output = alt_output
                    else:
                        continue
                os.makedirs(job["output_dir"], exist_ok=True)
                shutil.move(flat_output, job["output_file"])
                self._append_csv_result(csv_path, target_name, ligand_group, job["ligand_name"], job["output_file"])

    def _write_cpu_config(self, config_path: str, job: dict[str, str]) -> None:
        lines = [
            f"receptor = {job['receptor']}",
            f"ligand = {job['ligand_file']}",
            f"scoring = {self.settings.scoring_function}",
            f"center_x = {job['center_x']}",
            f"center_y = {job['center_y']}",
            f"center_z = {job['center_z']}",
            f"size_x = {job['size_x']}",
            f"size_y = {job['size_y']}",
            f"size_z = {job['size_z']}",
            f"out = {job['output_file']}",
            f"cpu = {self.settings.cpu_threads}",
            f"exhaustiveness = {self.settings.exhaustiveness}",
            f"num_modes = {self.settings.poses}",
            f"min_rmsd = {self.settings.min_rmsd}",
            f"energy_range = {self.settings.energy_range}",
            f"spacing = {self.settings.spacing}",
        ]
        if self.settings.docking_mode == "score_only":
            lines.append("score_only = true")
        elif self.settings.docking_mode == "local_only":
            lines.append("local_only = true")
        if self.docking_type == "Flexible":
            lines.insert(1, f"flex = {job['flex_receptor']}")
        with open(config_path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")

    def _write_gpu_config(self, config_path: str, job: dict[str, str], ligand_dir: str, output_dir: str) -> None:
        lines = [
            f"receptor = {job['receptor']}",
            f"ligand_directory = {ligand_dir}",
            f"output_directory = {output_dir}",
            f"opencl_binary_path = {Path(self.vina_gpu).parent}",
            f"center_x = {job['center_x']}",
            f"center_y = {job['center_y']}",
            f"center_z = {job['center_z']}",
            f"size_x = {job['size_x']}",
            f"size_y = {job['size_y']}",
            f"size_z = {job['size_z']}",
            f"thread = {self.settings.gpu_threads}",
        ]
        if self.settings.opencl_platform_id >= 0:
            lines.append(f"platform_id = {self.settings.opencl_platform_id}")
        if self.settings.opencl_device_id >= 0:
            lines.append(f"device_id = {self.settings.opencl_device_id}")
        if self.docking_type == "Flexible":
            lines.insert(1, f"flex = {job['flex_receptor']}")
        with open(config_path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")

    def _run_csv_path(self, result_folder: str) -> str:
        return os.path.join(result_folder, f"{self.job_name}.csv")

    def _ensure_result_csv(self, csv_path: str) -> None:
        if os.path.isfile(csv_path):
            return
        with open(csv_path, "w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(RESULT_CSV_HEADER)

    def _append_csv_result(self, csv_path: str, target_name: str, ligand_group: str, ligand_name: str, output_file: str) -> None:
        energy, rmsd_mean, smiles = _parse_vina_pose_data(output_file)
        with open(csv_path, "a", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow([ligand_name, smiles, ligand_group, target_name, energy, rmsd_mean])


# --------------------------------------------------------------------------------------
# Standalone (module-level) helpers used by the ligand -> PDBQT conversion worker pool.
#
# These mirror the equivalent LigandToolsWorker methods below, but are kept as free
# functions (no `self`, no Qt objects) so they can be pickled and shipped to separate
# worker PROCESSES via ProcessPoolExecutor: each ligand is submitted as a job to a pool of
# worker processes, which run truly in parallel (bypassing the GIL, unlike a thread pool,
# since RDKit embedding/optimization is CPU-bound Python+C code).
# --------------------------------------------------------------------------------------

def _lig_require_rdkit() -> None:
    if Chem is None or AllChem is None:
        raise RuntimeError("RDKit is not available in the current environment. Install RDKit to run this ligand routine.")


def _lig_require_obabel() -> str:
    obabel = shutil.which("obabel")
    if not obabel:
        raise RuntimeError("OpenBabel was not found in PATH. Install it before running this ligand routine.")
    return obabel


def _lig_require_meeko() -> None:
    if MoleculePreparation is None or PDBQTWriterLegacy is None:
        raise RuntimeError("Meeko is not available in the current environment. Install meeko to run the RDKit conversion engine.")


def _lig_require_meeko_reader() -> None:
    if PDBQTMolecule is None or RDKitMolCreate is None:
        raise RuntimeError("Meeko is not available in the current environment. Install meeko to chemically validate PDBQT files.")


def _lig_require_dimorphite() -> None:
    if dimorphite_dl is None:
        raise RuntimeError("Dimorphite-DL is not available in the current environment. Install dimorphite-dl to run the RDKit conversion engine.")


def _lig_run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


def _lig_mol_from_file(file_path: Path) -> Optional[Any]:
    _lig_require_rdkit()
    suffix = file_path.suffix.lower()
    try:
        if suffix == ".smi":
            lines = file_path.read_text(encoding="utf-8", errors="ignore").strip().splitlines()
            if not lines:
                return None
            smiles = lines[0].split()[0]
            mol = Chem.MolFromSmiles(smiles)
            if mol is not None:
                mol.SetProp("_Name", file_path.stem)
            return mol
        if suffix == ".sdf":
            supplier = Chem.SDMolSupplier(str(file_path), removeHs=False)
            for mol in supplier:
                if mol is not None:
                    if not mol.HasProp("_Name"):
                        mol.SetProp("_Name", file_path.stem)
                    return mol
            return None
        if suffix == ".mol2":
            mol = Chem.MolFromMol2File(str(file_path), removeHs=False)
            if mol is not None and not mol.HasProp("_Name"):
                mol.SetProp("_Name", file_path.stem)
            return mol
        if suffix in {".mol", ".mdl"}:
            mol = Chem.MolFromMolFile(str(file_path), removeHs=False)
            if mol is not None and not mol.HasProp("_Name"):
                mol.SetProp("_Name", file_path.stem)
            return mol
        if suffix in {".pdb", ".ent"}:
            mol = Chem.MolFromPDBFile(str(file_path), removeHs=False)
            if mol is not None and not mol.HasProp("_Name"):
                mol.SetProp("_Name", file_path.stem)
            return mol
    except Exception:
        return None
    return None


def _lig_canonical_smiles(mol: Any) -> str:
    return Chem.MolToSmiles(mol, canonical=True) if mol is not None else ""


def _lig_rdkit_optimize(working: Any, minimization_steps: int, forcefield: str) -> None:
    try:
        if forcefield == "UFF":
            AllChem.UFFOptimizeMolecule(working, maxIters=minimization_steps)
        elif forcefield == "MMFF94s":
            AllChem.MMFFOptimizeMolecule(working, mmffVariant="MMFF94s", maxIters=minimization_steps)
        else:
            AllChem.MMFFOptimizeMolecule(working, maxIters=minimization_steps)
    except Exception:
        try:
            AllChem.UFFOptimizeMolecule(working, maxIters=minimization_steps)
        except Exception:
            pass


def _lig_obabel_minimize_flags(minimization_steps: int, forcefield: str, algorithm: str) -> list[str]:
    flags = ["--minimize"]
    if algorithm == "Steepest Descent":
        flags.append("--sd")
    flags += ["--steps", str(minimization_steps), "--ff", forcefield]
    return flags


def _lig_prepare_3d_molecule(mol: Any, minimization_steps: int, forcefield: str, remove_hs: bool = True) -> Optional[Any]:
    try:
        working = Chem.AddHs(Chem.Mol(mol))
        params = AllChem.ETKDGv3()
        params.randomSeed = 0xC0D0
        embed = AllChem.EmbedMolecule(working, params)
        if embed != 0:
            return None
        _lig_rdkit_optimize(working, minimization_steps, forcefield)
        return Chem.RemoveHs(working) if remove_hs else working
    except Exception:
        return None


def _lig_protonate_smiles(smiles: str, ph: float) -> str:
    """Return the dominant ionization state of `smiles` at `ph`, per Dimorphite-DL's SMARTS/pKa rules.

    pKa precision 0 asks Dimorphite-DL for the single state that predominates at exactly `ph`. With
    a wider precision it also returns the neighbouring states (e.g. both the neutral and the
    protonated amine) in an order that changes from one run to the next, so taking the first one
    picked the ionization state by chance. If several states still come back (a pH sitting right on
    a pKa), the choice is made deterministic by sorting them.

    Supports both the current Dimorphite-DL API (module-level `protonate_smiles`, >=2.0) and the
    legacy `DimorphiteDL` class API (<2.0), since either may be present in the target environment.
    """
    _lig_require_dimorphite()
    try:
        protonate_fn = getattr(dimorphite_dl, "protonate_smiles", None)
        if protonate_fn is not None:
            variants = protonate_fn(smiles, ph_min=ph, ph_max=ph, precision=0.0)
        else:
            variants = dimorphite_dl.DimorphiteDL(min_ph=ph, max_ph=ph, pka_precision=0.0).protonate(smiles)
    except Exception:
        return smiles
    return sorted(variants)[0] if variants else smiles


def _lig_prepend_pdbqt_metadata(pdbqt_path: Path, ligand_name: str, smiles: str) -> None:
    """Gives a freshly written PDBQT its `REMARK  Name` header line.

    A PDBQT written by Meeko already carries `REMARK SMILES` - the SMILES of the PROTONATED molecule
    that was actually prepared, which Meeko's own index map (`SMILES IDX`) and `H PARENT` refer to -
    so it is kept as it is: that is the form that docks, the one the results CSV and the report must
    show, and the one Meeko needs to rebuild the molecule when validating the file. Only a PDBQT
    without it (OpenBabel's) gets `REMARK SMILES` from `smiles`, the ligand's SMILES as read from its
    input."""
    if not pdbqt_path.exists():
        return
    content = pdbqt_path.read_text(encoding="utf-8", errors="ignore")
    content = re.sub(r"^REMARK\s+Name.*\n?", "", content, flags=re.MULTILINE)
    header = [f"REMARK  Name = {ligand_name}"]
    if smiles and "REMARK SMILES IDX" not in content:
        header.append(f"REMARK SMILES {smiles}")
    pdbqt_path.write_text("\n".join(header) + "\n" + content, encoding="utf-8")


def _lig_meeko_prepare_and_write(
    mol: Any, ph: float, minimization_steps: int, forcefield: str, ligand_name: str, output_path: Path
) -> Optional[str]:
    """Native RDKit pipeline: Dimorphite-DL decides the pH-dependent protonation state,
    RDKit embeds/minimizes the 3D conformation, and Meeko writes AutoDock-typed PDBQT.
    No OpenBabel process is involved anywhere in this path."""
    _lig_require_rdkit()
    _lig_require_meeko()
    smiles = _lig_canonical_smiles(mol)
    protonated_smiles = _lig_protonate_smiles(smiles, ph)
    protonated_mol = Chem.MolFromSmiles(protonated_smiles) if protonated_smiles else None
    if protonated_mol is None:
        protonated_mol = Chem.Mol(mol)
    protonated_mol.SetProp("_Name", ligand_name)
    prepared = _lig_prepare_3d_molecule(protonated_mol, minimization_steps, forcefield, remove_hs=False)
    if prepared is None:
        return f"Failed to generate a 3D conformation for {ligand_name}."
    try:
        molsetups = MoleculePreparation().prepare(prepared)
    except Exception as exc:
        return f"Meeko failed to prepare {ligand_name}: {exc}"
    if not molsetups:
        return f"Meeko produced no output for {ligand_name}."
    pdbqt_string, success, error_msg = PDBQTWriterLegacy.write_string(molsetups[0])
    if not success:
        return f"Meeko failed to write PDBQT for {ligand_name}: {error_msg}"
    output_path.write_text(pdbqt_string, encoding="utf-8")
    _lig_prepend_pdbqt_metadata(output_path, ligand_name, smiles)
    return None


def _lig_convert_single_rdkit(
    input_path: Path, output_path: Path, ph: float, minimization_steps: int, forcefield: str, algorithm: str
) -> Optional[str]:
    # `algorithm` only affects OpenBabel's minimizer (see _lig_convert_single_openbabel); the
    # RDKit engine's own MMFF/UFF optimizer has no user-selectable steepest-descent/conjugate-
    # gradient switch, so it is accepted here only to keep a uniform call signature.
    mol = _lig_mol_from_file(input_path)
    if mol is None:
        return f"Failed to read molecule from {input_path.name} with RDKit."
    return _lig_meeko_prepare_and_write(mol, ph, minimization_steps, forcefield, input_path.stem, output_path)


def _lig_convert_single_openbabel(
    input_path: Path, output_path: Path, ph: float, minimization_steps: int, forcefield: str, algorithm: str
) -> Optional[str]:
    obabel = _lig_require_obabel()
    smiles = ""
    try:
        mol = _lig_mol_from_file(input_path)
        if mol is not None:
            smiles = _lig_canonical_smiles(mol)
    except Exception:
        smiles = ""

    if input_path.suffix.lower() == ".smi":
        with tempfile.TemporaryDirectory(prefix="codoc_convert_") as temp_dir:
            tmp_mol2 = Path(temp_dir) / f"{output_path.stem}.mol2"
            first = _lig_run_command([obabel, str(input_path), "-O", str(tmp_mol2), "--gen3d", "-r"])
            if first.returncode != 0:
                return f"OpenBabel failed to generate 3D coordinates for {input_path.name}:\n{first.stdout}"
            second = _lig_run_command([
                obabel,
                str(tmp_mol2),
                "-O",
                str(output_path),
                "-p",
                str(ph),
                *_lig_obabel_minimize_flags(minimization_steps, forcefield, algorithm),
            ])
    else:
        second = _lig_run_command([
            obabel,
            str(input_path),
            "-O",
            str(output_path),
            "-p",
            str(ph),
            "--partialcharge",
            "gasteiger",
            *_lig_obabel_minimize_flags(minimization_steps, forcefield, algorithm),
            "-r",
        ])
    if second.returncode != 0:
        return f"OpenBabel failed to convert {input_path.name} to PDBQT:\n{second.stdout}"
    _lig_prepend_pdbqt_metadata(output_path, input_path.stem, smiles)
    return None


def _lig_pdbqt_has_atoms(path: Path) -> bool:
    """True when `path` is a PDBQT with at least one ATOM line. A conversion tool can exit without an
    error and still leave an empty file, or only the REMARK header CODOC adds."""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as handle:
            return any(line.startswith(("ATOM", "HETATM")) for line in handle)
    except OSError:
        return False


def _lig_convert_with_engine(
    engine: str, input_path: Path, output_path: Path, ph: float, minimization_steps: int, forcefield: str, algorithm: str
) -> Optional[str]:
    """Converts one ligand with `engine`. Returns None on success, otherwise the reason. A run that
    reports no error but leaves no PDBQT behind (OpenBabel can exit with status 0 and write
    nothing) counts as a failure, and any partial output is removed."""
    convert = _lig_convert_single_openbabel if engine == "OpenBabel" else _lig_convert_single_rdkit
    try:
        error = convert(input_path, output_path, ph, minimization_steps, forcefield, algorithm)
    except Exception as exc:
        error = f"Unexpected error converting {input_path.name} with {engine}: {exc}"
    if error is None and not _lig_pdbqt_has_atoms(output_path):
        error = f"{engine} produced no PDBQT output for {input_path.name}."
    if error is not None:
        output_path.unlink(missing_ok=True)
    return error


def _lig_convert_worker(
    payload: tuple[str, str, str, str, float, int, str, str]
) -> tuple[str, Optional[str], Optional[str]]:
    """Entry point executed inside each worker process of the conversion pool. Tries the selected
    engine and, when it fails, the other one (RDKit <-> OpenBabel). Returns (input, error, note):
    `error` is set only when both engines failed; `note` says that the fallback engine converted it."""
    input_str, output_str, _group_name, engine, ph, minimization_steps, forcefield, algorithm = payload
    input_path = Path(input_str)
    output_path = Path(output_str)
    settings = (ph, minimization_steps, forcefield, algorithm)
    error = _lig_convert_with_engine(engine, input_path, output_path, *settings)
    if error is None:
        return (input_str, None, None)
    fallback_engine = "RDKit" if engine == "OpenBabel" else "OpenBabel"
    fallback_error = _lig_convert_with_engine(fallback_engine, input_path, output_path, *settings)
    if fallback_error is None:
        return (input_str, None, f"{input_path.name}: {engine} failed, converted with {fallback_engine} (fallback).")
    return (input_str, f"{error}\n{fallback_error}", None)


class LigandToolsWorker(QThread):
    progress_value = pyqtSignal(int)
    progress_text = pyqtSignal(str)
    finished_ok = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(
        self,
        app_dir: str,
        ligands_dir: str,
        conversion_dir: str,
        settings: LigandSettings,
        operation: str,
        sources: Optional[list[str]] = None,
    ) -> None:
        super().__init__()
        self.app_dir = app_dir
        # ligands_dir is <project>/CONVERSION/LIGANDS: the base folder every ligand routine works on
        # (imported files, split results and, in the end, the converted .pdbqt files).
        self.ligands_dir = ligands_dir
        self.conversion_dir = conversion_dir
        self.settings = settings
        self.operation = operation
        self.sources = list(sources or [])
        self.failure_dir = os.path.join(conversion_dir, "CONVERSION_FAILURES")
        self.drug_dir = os.path.join(conversion_dir, "NO_DRUGGABILITY")
        self.empty_dir = os.path.join(conversion_dir, "EMPTY_LIGANDS")
        self.dataframes_dir = os.path.join(conversion_dir, "DATAFRAMES")
        self.macrocycles_dir = os.path.join(conversion_dir, "MACROCYCLES")

    def run(self) -> None:
        try:
            os.makedirs(self.conversion_dir, exist_ok=True)
            operations = {
                "import_ligands": self._import_ligand_sources,
                "split_multimodel": self._split_multimodel_files,
                "split_large_folders": self._split_large_folders,
                "generate_lipinski": self._generate_lipinski_tables,
                "druggability_filter": self._run_druggability_filter,
                "move_empty": self._move_empty_files,
                "convert_pdbqt": self._convert_ligands_to_pdbqt,
                "reject_pdbqt": self._reject_invalid_pdbqt,
                "recover_pdbqt": self._recover_failed_pdbqt,
                "fix_macrocycles": self._fix_macrocycles,
            }
            handler = operations.get(self.operation)
            if handler is None:
                raise RuntimeError(f"Unsupported ligand operation: {self.operation}")
            message = handler()
            self.finished_ok.emit(message)
        except Exception as exc:
            self.failed.emit(str(exc))

    def _emit_progress(self, index: int, total: int, text: str) -> None:
        value = int(index * 100 / max(total, 1))
        self.progress_value.emit(value)
        self.progress_text.emit(text)

    def _sanitize_name(self, value: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value).strip())
        return cleaned.strip("._") or "ligand"

    def _require_obabel(self) -> str:
        obabel = shutil.which("obabel")
        if not obabel:
            raise RuntimeError("OpenBabel was not found in PATH. Install it before running this ligand routine.")
        return obabel

    def _require_rdkit(self) -> None:
        if Chem is None or AllChem is None or Descriptors is None or Crippen is None or Lipinski is None or MolSurf is None:
            raise RuntimeError("RDKit is not available in the current environment. Install RDKit to run this ligand routine.")

    def _run_command(self, command: list[str], cwd: Optional[str] = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    def _import_ligand_sources(self) -> str:
        """Copy the files / folders picked in STEP 1 into <project>/CONVERSION/LIGANDS.

        * a file (single or multi-ligand) is copied to the root of CONVERSION/LIGANDS, where
          "Split multimodel files" turns it into a group folder named after the file;
        * a folder of individual ligands is copied to CONVERSION/LIGANDS/<folder name> (a group).

        The originals are only read, never moved or deleted. Importing is idempotent: anything
        already present in the project (the file itself, its split group - a group folder that
        holds files, an empty one does not count - or a file of the same name inside a group
        folder) is skipped, so repeating the selection never duplicates ligands."""
        root = Path(self.ligands_dir)
        root.mkdir(parents=True, exist_ok=True)
        if not self.sources:
            return "No ligand files or folders were selected."
        copied_files = 0
        already_there: list[str] = []
        not_found: list[str] = []
        total = len(self.sources)
        for index, raw in enumerate(self.sources, start=1):
            source = Path(raw)
            self._emit_progress(index - 1, total, f"Importing {source.name}")
            if source.is_file():
                group_name = self._sanitize_name(source.stem)
                destination = root / source.name
                group_dir = root / group_name
                if destination.exists() or (group_dir.is_dir() and any(group_dir.iterdir())):
                    already_there.append(source.name)
                    continue
                shutil.copy2(str(source), destination)
                copied_files += 1
            elif source.is_dir():
                group_dir = root / self._sanitize_name(source.name)
                group_dir.mkdir(parents=True, exist_ok=True)
                files = [item for item in sorted(source.iterdir()) if item.is_file()]
                if not files:
                    self.progress_text.emit(f"Folder {source.name} has no ligand files directly inside it - nothing to copy.")
                for file_path in files:
                    destination = group_dir / file_path.name
                    if destination.exists():
                        continue
                    shutil.copy2(str(file_path), destination)
                    copied_files += 1
                if not any(group_dir.iterdir()):
                    group_dir.rmdir()
            else:
                not_found.append(source.name)
        self._emit_progress(total, total, "Import finished")
        message = f"Imported {copied_files} file(s) into {root}."
        if already_there:
            message += "\nAlready in the project (skipped): " + ", ".join(already_there)
        if not_found:
            message += "\nNot found (skipped): " + ", ".join(not_found)
        return message

    def _mol_from_file(self, file_path: Path) -> Optional[Any]:
        self._require_rdkit()
        suffix = file_path.suffix.lower()
        try:
            if suffix == ".smi":
                line = file_path.read_text(encoding="utf-8", errors="ignore").strip().splitlines()
                if not line:
                    return None
                smiles = line[0].split()[0]
                mol = Chem.MolFromSmiles(smiles)
                if mol is not None:
                    mol.SetProp("_Name", file_path.stem)
                return mol
            if suffix == ".sdf":
                supplier = Chem.SDMolSupplier(str(file_path), removeHs=False)
                for mol in supplier:
                    if mol is not None:
                        if not mol.HasProp("_Name"):
                            mol.SetProp("_Name", file_path.stem)
                        return mol
                return None
            if suffix == ".mol2":
                mol = Chem.MolFromMol2File(str(file_path), removeHs=False)
                if mol is not None and not mol.HasProp("_Name"):
                    mol.SetProp("_Name", file_path.stem)
                return mol
            if suffix in {".mol", ".mdl"}:
                mol = Chem.MolFromMolFile(str(file_path), removeHs=False)
                if mol is not None and not mol.HasProp("_Name"):
                    mol.SetProp("_Name", file_path.stem)
                return mol
            if suffix in {".pdb", ".ent"}:
                mol = Chem.MolFromPDBFile(str(file_path), removeHs=False)
                if mol is not None and not mol.HasProp("_Name"):
                    mol.SetProp("_Name", file_path.stem)
                return mol
        except Exception:
            return None
        return None

    def _canonical_smiles(self, mol: Any) -> str:
        self._require_rdkit()
        return Chem.MolToSmiles(mol, canonical=True) if mol is not None else ""

    def _mol_name(self, mol: Any, fallback: str) -> str:
        self._require_rdkit()
        if mol is not None and mol.HasProp("_Name"):
            return self._sanitize_name(mol.GetProp("_Name"))
        for key in ("id", "zinc_id", "COMPOUND_ID", "coconut_id", "chembl_id"):
            if mol is not None and mol.HasProp(key):
                return self._sanitize_name(mol.GetProp(key))
        return self._sanitize_name(fallback)

    def _compute_lipinski_properties(self, mol: Any) -> dict[str, float]:
        self._require_rdkit()
        return {
            "MW": float(Descriptors.MolWt(mol)),
            "logP": float(Crippen.MolLogP(mol)),
            "HBA2": float(Lipinski.NumHAcceptors(mol)),
            "HBD": float(Lipinski.NumHDonors(mol)),
            "rotors": float(Lipinski.NumRotatableBonds(mol)),
            "TPSA": float(MolSurf.TPSA(mol)),
        }

    def _iter_sdf_molecules(self, file_path: Path) -> list[Any]:
        self._require_rdkit()
        molecules = []
        supplier = Chem.SDMolSupplier(str(file_path), removeHs=False)
        for idx, mol in enumerate(supplier, start=1):
            if mol is None:
                continue
            if not mol.HasProp("_Name") or not mol.GetProp("_Name").strip():
                mol.SetProp("_Name", f"{file_path.stem}_{idx:05d}")
            molecules.append(mol)
        return molecules

    def _split_multimodel_files(self) -> str:
        root_files = [path for path in sorted(Path(self.ligands_dir).iterdir()) if path.is_file()]
        if not root_files:
            return "No multi-model ligand files were found in the ligands root directory."

        unsupported_dir = Path(self.conversion_dir) / "NOT_RECOGNIZED_LIGANDS"
        unsupported_dir.mkdir(parents=True, exist_ok=True)
        total = len(root_files)
        for index, file_path in enumerate(root_files, start=1):
            self._emit_progress(index, total, f"Splitting {file_path.name}")
            suffix = file_path.suffix.lower()
            if suffix == ".smi":
                self._split_smi_file(file_path)
            elif suffix == ".sdf":
                self._split_sdf_file(file_path)
            elif suffix in {".mol2", ".pdb", ".pdbqt"}:
                self._split_file_with_obabel(file_path)
            else:
                shutil.move(str(file_path), unsupported_dir / file_path.name)
        return "Ligand splitting completed."

    def _split_smi_file(self, file_path: Path) -> None:
        self._require_rdkit()
        group_dir = Path(self.ligands_dir) / self._sanitize_name(file_path.stem)
        group_dir.mkdir(parents=True, exist_ok=True)
        moved_path = group_dir / file_path.name
        shutil.move(str(file_path), moved_path)
        with open(moved_path, "r", encoding="utf-8", errors="ignore") as handle:
            lines = [line.strip() for line in handle if line.strip()]
        for idx, line in enumerate(lines, start=1):
            parts = line.split()
            if not parts:
                continue
            mol = Chem.MolFromSmiles(parts[0])
            if mol is None:
                continue
            smiles = self._canonical_smiles(mol)
            title = self._sanitize_name("_".join(parts[1:]) if len(parts) > 1 else f"{moved_path.stem}_{idx:05d}")
            output_path = group_dir / f"{title}.smi"
            counter = 1
            while output_path.exists():
                output_path = group_dir / f"{title}_{counter}.smi"
                counter += 1
            output_path.write_text(f"{smiles}\t{title}\n", encoding="utf-8")
        moved_path.unlink(missing_ok=True)

    def _split_sdf_file(self, file_path: Path) -> None:
        self._require_rdkit()
        group_dir = Path(self.ligands_dir) / self._sanitize_name(file_path.stem)
        group_dir.mkdir(parents=True, exist_ok=True)
        moved_path = group_dir / file_path.name
        shutil.move(str(file_path), moved_path)
        molecules = self._iter_sdf_molecules(moved_path)
        for idx, mol in enumerate(molecules, start=1):
            ligand_name = self._mol_name(mol, f"{moved_path.stem}_{idx:05d}")
            output_path = group_dir / f"{ligand_name}.sdf"
            counter = 1
            while output_path.exists():
                output_path = group_dir / f"{ligand_name}_{counter}.sdf"
                counter += 1
            writer = Chem.SDWriter(str(output_path))
            writer.write(mol)
            writer.close()
        moved_path.unlink(missing_ok=True)

    def _guess_sdf_name(self, block: str, fallback: str) -> str:
        tag_order = ["id", "zinc_id", "COMPOUND_ID", "coconut_id", "chembl_id"]
        for tag in tag_order:
            pattern = rf">\s*<{re.escape(tag)}>\s*\n([^\n]+)"
            match = re.search(pattern, block, flags=re.IGNORECASE)
            if match:
                return self._sanitize_name(match.group(1))
        first_line = block.splitlines()[0] if block.splitlines() else fallback
        return self._sanitize_name(first_line or fallback)

    def _split_file_with_obabel(self, file_path: Path) -> None:
        obabel = self._require_obabel()
        group_dir = Path(self.ligands_dir) / self._sanitize_name(file_path.stem)
        group_dir.mkdir(parents=True, exist_ok=True)
        moved_path = group_dir / file_path.name
        shutil.move(str(file_path), moved_path)
        output_pattern = group_dir / f"{self._sanitize_name(file_path.stem)}{file_path.suffix.lower()}"
        result = self._run_command([obabel, str(moved_path), "-m", "-O", str(output_pattern)])
        if result.returncode != 0:
            raise RuntimeError(f"OpenBabel failed while splitting {file_path.name}:\n{result.stdout}")
        moved_path.unlink(missing_ok=True)
        if file_path.suffix.lower() == ".pdbqt":
            for generated in group_dir.glob("*.pdbqt"):
                lines = generated.read_text(encoding="utf-8", errors="ignore").splitlines()
                cleaned = [line for line in lines if line.strip() not in {"MODEL 1", "ENDMDL"}]
                generated.write_text("\n".join(cleaned) + "\n", encoding="utf-8")

    def _split_large_folders(self) -> str:
        ligand_dirs = [path for path in sorted(Path(self.ligands_dir).glob("*/")) if path.is_dir()]
        total = len(ligand_dirs)
        for index, folder in enumerate(ligand_dirs, start=1):
            files = [item for item in sorted(folder.iterdir()) if item.is_file()]
            self._emit_progress(index, total, f"Checking folder size: {folder.name}")
            if len(files) <= self.settings.max_ligands_per_folder:
                continue
            chunk_size = max(1, self.settings.max_ligands_per_folder)
            for chunk_idx, start in enumerate(range(0, len(files), chunk_size), start=1):
                new_folder = folder.parent / f"{folder.name}_{chunk_idx}"
                new_folder.mkdir(parents=True, exist_ok=True)
                for file_path in files[start:start + chunk_size]:
                    shutil.move(str(file_path), new_folder / file_path.name)
            if not any(folder.iterdir()):
                folder.rmdir()
        return "Large ligand folders were split successfully."

    def _generate_lipinski_tables(self) -> str:
        self._require_rdkit()
        os.makedirs(self.dataframes_dir, exist_ok=True)
        ligand_dirs = [path for path in sorted(Path(self.ligands_dir).glob("*/")) if path.is_dir()]
        total = len(ligand_dirs)
        for index, folder in enumerate(ligand_dirs, start=1):
            self._emit_progress(index, total, f"Generating Lipinski tables for {folder.name}")
            files = [item for item in sorted(folder.iterdir()) if item.is_file()]
            if not files:
                continue
            out_dir = Path(self.dataframes_dir) / folder.name
            out_dir.mkdir(parents=True, exist_ok=True)
            smi_rows: list[list[str]] = []
            lip_rows: list[list[Any]] = []
            for file_path in files:
                mol = self._mol_from_file(file_path)
                if mol is None:
                    continue
                smiles = self._canonical_smiles(mol)
                if not smiles:
                    continue
                props = self._compute_lipinski_properties(mol)
                smi_rows.append([file_path.stem, smiles])
                lip_rows.append([
                    file_path.stem,
                    smiles,
                    props["MW"],
                    props["logP"],
                    props["HBA2"],
                    props["HBD"],
                    props["rotors"],
                    props["TPSA"],
                ])
            with open(out_dir / f"{folder.name}.smi", "w", encoding="utf-8") as handle:
                for name, smiles in smi_rows:
                    handle.write(f"{smiles}\t{name}\n")
            with open(out_dir / f"{folder.name}.csv", "w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["name", "smiles"])
                writer.writerows(smi_rows)
            with open(out_dir / f"{folder.name}_lip.csv", "w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["name", "smiles", "MW", "logP", "HBA2", "HBD", "rotors", "TPSA"])
                writer.writerows(lip_rows)
        return f"Lipinski exports created in {self.dataframes_dir}."

    def _run_druggability_filter(self) -> str:
        self._require_rdkit()
        ligand_dirs = [path for path in sorted(Path(self.ligands_dir).glob("*/")) if path.is_dir()]
        total = sum(1 for folder in ligand_dirs for item in folder.iterdir() if item.is_file())
        os.makedirs(self.drug_dir, exist_ok=True)
        counter = 0
        for folder in ligand_dirs:
            destination = Path(self.drug_dir) / folder.name
            destination.mkdir(parents=True, exist_ok=True)
            for file_path in sorted(folder.iterdir()):
                if not file_path.is_file():
                    continue
                counter += 1
                self._emit_progress(counter, total, f"Applying druggability filter to {file_path.name}")
                mol = self._mol_from_file(file_path)
                if mol is None:
                    shutil.move(str(file_path), destination / file_path.name)
                    continue
                props = self._compute_lipinski_properties(mol)
                limits = {
                    "mw_min": props["MW"] > self.settings.mw_min,
                    "mw_max": props["MW"] < self.settings.mw_max,
                    "logp_min": props["logP"] > self.settings.logp_min,
                    "logp_max": props["logP"] < self.settings.logp_max,
                    "h_donor_max": props["HBD"] < self.settings.h_donor_max,
                    "h_acceptor_max": props["HBA2"] < self.settings.h_acceptor_max,
                    "rotatable_bonds_max": props["rotors"] < self.settings.rotatable_bonds_max,
                    "tpsa_max": props["TPSA"] < self.settings.tpsa_max,
                }
                # only the limits whose checkbox is on take part in the filter
                passed = all(met for key, met in limits.items() if self.settings.druggability_enabled.get(key, True))
                if not passed:
                    shutil.move(str(file_path), destination / file_path.name)
        return f"Druggability filter finished. Rejected ligands were moved to {self.drug_dir}."

    def _move_empty_files(self) -> str:
        ligand_dirs = [path for path in sorted(Path(self.ligands_dir).glob("*/")) if path.is_dir()]
        total = sum(1 for folder in ligand_dirs for item in folder.iterdir() if item.is_file())
        os.makedirs(self.empty_dir, exist_ok=True)
        counter = 0
        for folder in ligand_dirs:
            destination = Path(self.empty_dir) / folder.name
            destination.mkdir(parents=True, exist_ok=True)
            for file_path in sorted(folder.iterdir()):
                if not file_path.is_file():
                    continue
                counter += 1
                self._emit_progress(counter, total, f"Checking file size for {file_path.name}")
                if file_path.stat().st_size < self.settings.min_file_size:
                    shutil.move(str(file_path), destination / file_path.name)
            if folder.exists() and not any(folder.iterdir()):
                folder.rmdir()
        return f"Files smaller than {self.settings.min_file_size} bytes were moved to {self.empty_dir}."

    def _convert_ligands_to_pdbqt(self) -> str:
        self._require_rdkit()
        os.makedirs(self.failure_dir, exist_ok=True)
        ligand_dirs = [path for path in sorted(Path(self.ligands_dir).glob("*/")) if path.is_dir()]
        selected_engine = (self.settings.conversion_engine or "RDKit").strip()
        if selected_engine != "OpenBabel":
            _lig_require_meeko()
            _lig_require_dimorphite()

        jobs: list[tuple[Path, Path, str]] = []
        for folder in ligand_dirs:
            (Path(self.failure_dir) / folder.name).mkdir(parents=True, exist_ok=True)
            for file_path in sorted(folder.iterdir()):
                if not file_path.is_file() or file_path.suffix.lower() == ".pdbqt":
                    continue
                output_path = folder / f"{file_path.stem}.pdbqt"
                jobs.append((file_path, output_path, folder.name))

        total = len(jobs)
        if total == 0:
            return "No pending ligand files were found for PDBQT conversion."
        self._record_source_formats(jobs)

        requested_workers = int(getattr(self.settings, "conversion_workers", os.cpu_count() or 1) or 1)
        workers = max(1, min(requested_workers, total))

        # Each ligand is dispatched to a pool of OS processes instead of a single serial loop,
        # so the conversion actually uses the available CPU cores.
        mp_context = multiprocessing.get_context("fork") if "fork" in multiprocessing.get_all_start_methods() else multiprocessing.get_context()

        counter = 0
        fallback_count = 0
        finished_inputs: list[Path] = []
        fallback_engine = "RDKit" if selected_engine == "OpenBabel" else "OpenBabel"
        self.progress_text.emit(
            f"Converting {total} ligand(s) to PDBQT using {selected_engine} (failures are retried with {fallback_engine}) "
            f"with {workers} parallel worker process(es)..."
        )
        with ProcessPoolExecutor(max_workers=workers, mp_context=mp_context) as executor:
            future_map = {
                executor.submit(
                    _lig_convert_worker,
                    (
                        str(input_path),
                        str(output_path),
                        group_name,
                        selected_engine,
                        self.settings.ph,
                        self.settings.minimization_steps,
                        self.settings.minimization_forcefield,
                        self.settings.minimization_algorithm,
                    ),
                ): (input_path, output_path, group_name)
                for input_path, output_path, group_name in jobs
            }
            for future in as_completed(future_map):
                input_path, output_path, group_name = future_map[future]
                counter += 1
                note = None
                try:
                    _, error, note = future.result()
                except Exception as exc:
                    error = f"Worker process failed for {input_path.name}: {exc}"
                self._emit_progress(counter, total, f"Converting {input_path.name} to PDBQT using {selected_engine}")
                if note:
                    fallback_count += 1
                    self.progress_text.emit(note)
                if error is not None:
                    failure_group = Path(self.failure_dir) / group_name
                    failure_group.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(input_path), failure_group / input_path.name)
                    self.progress_text.emit(error)
                    finished_inputs.append(input_path)       # a copy now lives in CONVERSION_FAILURES
                elif output_path.is_file():
                    finished_inputs.append(input_path)       # its .pdbqt replaces it

        # CONVERSION/LIGANDS ends up holding only the converted .pdbqt files: the split inputs that
        # were converted (or copied to CONVERSION_FAILURES) are removed. The user's originals, outside
        # the project, are never touched.
        for input_path in finished_inputs:
            input_path.unlink(missing_ok=True)
        return (
            f"Ligand conversion to PDBQT completed ({total} file(s), {workers} worker process(es), "
            f"{fallback_count} converted by the fallback engine). "
            f"Converted inputs were replaced by their .pdbqt in {self.ligands_dir}; failures are in {self.failure_dir}."
        )

    def _record_source_formats(self, jobs: list[tuple[Path, Path, str]]) -> None:
        """Remember each group's original file format (e.g. ".sdf") in CONVERSION/databank_formats.json
        before the inputs are replaced by their .pdbqt, so the Final Report can still state it. The
        first recording of a group wins: a later partial pass would only see the leftovers."""
        counts: dict[str, dict[str, int]] = {}
        for input_path, _output, group_name in jobs:
            per_group = counts.setdefault(group_name, {})
            extension = input_path.suffix.lower()
            per_group[extension] = per_group.get(extension, 0) + 1
        path = Path(self.conversion_dir) / "databank_formats.json"
        try:
            recorded = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        except (OSError, json.JSONDecodeError):
            recorded = {}
        for group_name, per_group in counts.items():
            recorded.setdefault(group_name, max(per_group, key=lambda ext: per_group[ext]))
        try:
            path.write_text(json.dumps(recorded, indent=2), encoding="utf-8")
        except OSError:
            pass

    def _reject_invalid_pdbqt(self) -> str:
        ligand_dirs = [path for path in sorted(Path(self.ligands_dir).glob("*/")) if path.is_dir()]
        total = sum(1 for folder in ligand_dirs for item in folder.glob("*.pdbqt"))
        counter = 0
        os.makedirs(self.failure_dir, exist_ok=True)
        for folder in ligand_dirs:
            failure_group = Path(self.failure_dir) / folder.name
            failure_group.mkdir(parents=True, exist_ok=True)
            for file_path in sorted(folder.glob("*.pdbqt")):
                counter += 1
                self._emit_progress(counter, total, f"Checking PDBQT integrity for {file_path.name}")
                reason = self._invalid_pdbqt_reason(file_path)
                if reason:
                    shutil.move(str(file_path), failure_group / file_path.name)
                    self.progress_text.emit(f"Moved {file_path.name} to failures: {reason}")
        return f"Rejected invalid PDBQT ligands to {self.failure_dir}."

    def _invalid_pdbqt_reason(self, file_path: Path) -> str:
        """Validates a PDBQT with the check that fits the engine that wrote it, told by its content
        (a file may come from either engine now that a failed conversion is retried with the other
        one): Meeko's "REMARK SMILES IDX" metadata allows the chemical round-trip; OpenBabel files
        get the text/geometry heuristics."""
        try:
            written_by_meeko = "REMARK SMILES IDX" in file_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            written_by_meeko = False
        if written_by_meeko:
            return self._invalid_pdbqt_reason_rdkit(file_path)
        return self._invalid_pdbqt_reason_heuristic(file_path)

    def _invalid_pdbqt_reason_rdkit(self, file_path: Path) -> str:
        """Chemical validation for PDBQTs written by the RDKit+Meeko engine: Meeko rebuilds the
        molecule from the REMARK SMILES / index map / H PARENT it wrote, and RDKit's sanitizer
        checks it (valence, aromaticity, ring perception). Only when Meeko cannot rebuild the
        molecule at all - e.g. a file from an older CODOC, whose REMARK SMILES had been replaced by
        the pre-protonation SMILES - are the text/geometry checks of the ATOM lines used instead."""
        try:
            self._require_rdkit()
            _lig_require_meeko_reader()
        except Exception as exc:
            return f"cannot validate chemically: {exc}"
        try:
            pdbqt_mol = PDBQTMolecule.from_file(str(file_path))
            mols = RDKitMolCreate.from_pdbqt_mol(pdbqt_mol)
        except Exception:
            return self._invalid_pdbqt_reason_heuristic(file_path)
        if not mols or mols[0] is None:
            return self._invalid_pdbqt_reason_heuristic(file_path)
        try:
            Chem.SanitizeMol(mols[0])
        except Exception as exc:
            return f"failed chemical sanitization: {exc}"
        return ""

    # Coordinates beyond this magnitude (Angstrom) cannot belong to a real docked ligand -
    # unlike counting digits, this correctly ignores decimal precision (e.g. "0.1234567").
    _PDBQT_MAX_COORDINATE = 9999.0
    _PDBQT_ZERO_TOLERANCE = 1e-3

    def _invalid_pdbqt_reason_heuristic(self, file_path: Path) -> str:
        """Text/geometry sanity checks used for the OpenBabel engine, whose PDBQTs don't carry
        the metadata that the RDKit+Meeko chemical round-trip relies on."""
        atom_lines = []
        torsdof_count = 0
        with open(file_path, "r", encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                if line.startswith("ATOM"):
                    atom_lines.append(line.rstrip("\n"))
                elif line.startswith("TORSDOF"):
                    torsdof_count += 1

        if not atom_lines:
            return "contains no atoms"
        reject_regex = re.compile(rf"\b({self.settings.rejected_elements})\b")
        previous_coords: Optional[tuple[float, float, float]] = None
        zero_issue_count = 0
        total_atoms = 0
        for line in atom_lines:
            if reject_regex.search(line):
                return "contains atoms not recognized by Vina-GPU"
            parts = line.split()
            if len(parts) < 9:
                continue
            total_atoms += 1
            try:
                coords = (float(parts[5]), float(parts[6]), float(parts[7]))
            except ValueError:
                return "contains non-numeric coordinate values"
            if any(abs(value) > self._PDBQT_MAX_COORDINATE for value in coords):
                return "contains abnormally large coordinate values"
            if coords == previous_coords:
                return "repeated atom coordinates"
            previous_coords = coords
            if sum(1 for value in coords if abs(value) < self._PDBQT_ZERO_TOLERANCE) >= 2:
                zero_issue_count += 1

        # Only reject on a cluster of near-origin atoms (a real sign of a failed/degenerate
        # embedding), scaled to ligand size so small, coincidental overlaps with an axis in an
        # otherwise valid conformer (common for linear/planar or symmetric ligands) don't count.
        zero_issue_threshold = max(3, total_atoms // 4)
        if zero_issue_count > zero_issue_threshold:
            return "contains multiple zero coordinates"
        if torsdof_count > 1:
            return "contains repeated TORSDOF sections"
        return ""

    def _recover_failed_pdbqt(self) -> str:
        recovered_root = Path(self.ligands_dir) / "RECOVERED"
        failure_groups = [path for path in sorted(Path(self.failure_dir).glob("*/")) if path.is_dir()]
        total = sum(1 for folder in failure_groups for item in folder.glob("*.pdbqt"))
        counter = 0
        conversion_engine = (self.settings.conversion_engine or "RDKit").strip()
        recovery_engine = "OpenBabel" if conversion_engine == "RDKit" else "RDKit"
        for folder in failure_groups:
            recovered_group = recovered_root / folder.name
            recovered_group.mkdir(parents=True, exist_ok=True)
            for file_path in sorted(folder.glob("*.pdbqt")):
                counter += 1
                self._emit_progress(counter, total, f"Recovering {file_path.name} using {recovery_engine}")
                smiles = self._extract_smiles_from_pdbqt(file_path)
                if not smiles:
                    self.progress_text.emit(f"Skipped {file_path.name}: missing REMARK SMILES")
                    continue
                output_path = recovered_group / file_path.name
                if recovery_engine == "RDKit":
                    recovered, message = self._recover_with_rdkit(smiles, output_path, file_path.name)
                else:
                    recovered, message = self._recover_with_openbabel(smiles, output_path, file_path.name)
                if recovered and not _lig_pdbqt_has_atoms(output_path):
                    recovered, message = False, f"{recovery_engine} recovery produced no PDBQT output for {file_path.name}."
                if not recovered:
                    self.progress_text.emit(message)
                    output_path.unlink(missing_ok=True)
                    continue
                self.progress_text.emit(f"Recovered {file_path.name} using {recovery_engine}.")
                _lig_prepend_pdbqt_metadata(output_path, file_path.stem, smiles)
                reason = self._invalid_pdbqt_reason(output_path)
                if reason:
                    output_path.unlink(missing_ok=True)
                    self.progress_text.emit(f"Recovered file {file_path.name} is still invalid: {reason}")
        # Nothing recovered -> no empty RECOVERED folders left behind in LIGANDS.
        if recovered_root.is_dir():
            for group_dir in sorted(recovered_root.iterdir()):
                if group_dir.is_dir() and not any(group_dir.iterdir()):
                    group_dir.rmdir()
            if not any(recovered_root.iterdir()):
                recovered_root.rmdir()
        recovered_total = sum(len(names) for _dir, _dirs, names in os.walk(recovered_root))
        if not recovered_total:
            return "Recovery attempt completed. No ligand could be recovered."
        return f"Recovery attempt completed. {recovered_total} ligand(s) recovered under {recovered_root}."

    def _recover_with_rdkit(self, smiles: str, output_path: Path, ligand_name: str) -> tuple[bool, str]:
        try:
            self._require_rdkit()
            _lig_require_meeko()
        except Exception as exc:
            return False, f"RDKit recovery unavailable for {ligand_name}: {exc}"
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return False, f"RDKit recovery failed for {ligand_name}: invalid SMILES '{smiles}'"
        error = _lig_meeko_prepare_and_write(
            mol,
            self.settings.ph,
            self.settings.minimization_steps,
            self.settings.minimization_forcefield,
            ligand_name,
            output_path,
        )
        if error:
            return False, f"RDKit recovery failed for {ligand_name}: {error}"
        return True, ""

    def _recover_with_openbabel(self, smiles: str, output_path: Path, ligand_name: str) -> tuple[bool, str]:
        try:
            obabel = self._require_obabel()
        except Exception as exc:
            return False, f"OpenBabel recovery unavailable for {ligand_name}: {exc}"
        with tempfile.TemporaryDirectory(prefix="codoc_recover_") as temp_dir:
            tmp_mol2 = Path(temp_dir) / f"{output_path.stem}.mol2"
            first = self._run_command([
                obabel,
                f"-:{smiles}",
                "-O",
                str(tmp_mol2),
                "-h",
                "--gen3d",
                "--partialcharge",
                "gasteiger",
            ])
            if first.returncode != 0:
                return False, f"OpenBabel recovery failed for {ligand_name}: {first.stdout.strip()}"
            second = self._run_command([
                obabel,
                str(tmp_mol2),
                "-O",
                str(output_path),
                "-p",
                str(self.settings.ph),
                *_lig_obabel_minimize_flags(
                    self.settings.minimization_steps, self.settings.minimization_forcefield, self.settings.minimization_algorithm
                ),
                "-r",
            ])
            if second.returncode != 0:
                return False, f"OpenBabel recovery failed to export {ligand_name}: {second.stdout.strip()}"
        return True, ""

    def _extract_smiles_from_pdbqt(self, file_path: Path) -> str:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                if line.startswith("REMARK SMILES"):
                    return line.split("REMARK SMILES", 1)[1].strip()
        return ""

    def _fix_macrocycles(self) -> str:
        ligand_dirs = [path for path in sorted(Path(self.ligands_dir).glob("*/")) if path.is_dir()]
        total = sum(1 for folder in ligand_dirs for item in folder.glob("*.pdbqt"))
        counter = 0
        os.makedirs(self.macrocycles_dir, exist_ok=True)
        replacements = {
            "CG0": "C  ",
            "CG1": "C  ",
            "CG2": "C  ",
            "CG3": "C  ",
            "CG": "C ",
            "G0": "C ",
            "G1": "C ",
            "G2": "C ",
            "G3": "C ",
        }
        for folder in ligand_dirs:
            destination = Path(self.macrocycles_dir) / folder.name
            destination.mkdir(parents=True, exist_ok=True)
            for file_path in sorted(folder.glob("*.pdbqt")):
                counter += 1
                self._emit_progress(counter, total, f"Checking macrocycles in {file_path.name}")
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                if not re.search(r"^ATOM.*\bG\d?\b", content, flags=re.MULTILINE):
                    continue
                shutil.copy2(str(file_path), destination / file_path.name)
                lines = []
                for line in content.splitlines():
                    if line.startswith("ATOM"):
                        for source, target in replacements.items():
                            line = re.sub(rf"\b{source}\b", target, line)
                        line = re.sub(r"\bG\b", "C", line)
                    lines.append(line)
                file_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return f"Macrocyclic ring fixes completed. Backups are in {self.macrocycles_dir}."

class LigandSourcesDialog(QFileDialog):
    """File dialog that lets the user pick files AND folders in one go (Ctrl/Shift to select several).

    Qt's own modes cannot do it: the "directory" mode lists files too but refuses to accept a
    selection whose first item is a file, and the "files" mode refuses folders. So this one uses the
    directory mode, turns on extended selection in its views and accepts any non-empty selection."""

    def __init__(self, parent: QWidget, title: str, start_dir: str) -> None:
        super().__init__(parent, title, start_dir)
        self.setFileMode(QFileDialog.Directory)
        self.setOption(QFileDialog.DontUseNativeDialog, True)
        self.setOption(QFileDialog.ShowDirsOnly, False)
        for view in self.findChildren((QListView, QTreeView)):
            view.setSelectionMode(QAbstractItemView.ExtendedSelection)
            view.selectionModel().selectionChanged.connect(self._enable_accept_button)
        self._accept_button = None
        buttons = self.findChild(QDialogButtonBox)
        if buttons is not None:
            for button in buttons.buttons():
                if buttons.buttonRole(button) == QDialogButtonBox.AcceptRole:
                    self._accept_button = button

    def _has_choice(self) -> bool:
        """True when something is highlighted in the list/tree or typed in the name box. (With nothing
        chosen Qt would answer "the folder being shown", which here would import a whole BASE folder.)"""
        name_box = self.findChild(QLineEdit, "fileNameEdit")
        typed = bool(name_box is not None and name_box.text().strip())
        highlighted = any(view.selectionModel().hasSelection() for view in self.findChildren((QListView, QTreeView)))
        return (typed or highlighted) and bool(self.selectedFiles())

    def _enable_accept_button(self, *_args) -> None:
        # Qt disables the button for a file-first selection (see above); re-enable it after Qt's own update.
        if self._accept_button is not None:
            QTimer.singleShot(0, lambda: self._accept_button.setEnabled(self._has_choice()))

    def accept(self) -> None:
        if self._has_choice():
            QDialog.accept(self)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        # Idioma da interface (PT-BR/EN, ver MODULES/i18n.py): lido de QSettings para persistir
        # entre sessões, com o mesmo padrão de bandeiras BR/UK do CODRUG (i18n.py + widget de
        # bandeiras ao lado do monitor de CPU/GPU). self._i18n_registry guarda (chave, apply_fn,
        # kwargs) para cada texto traduzido, permitindo reaplicar tudo instantaneamente ao trocar
        # de idioma sem precisar reconstruir nenhum widget.
        self._idioma = QSettings("CODOC", "CODOC").value("idioma", i18n.IDIOMA_PADRAO)
        if self._idioma not in ("en", "pt"):
            self._idioma = i18n.IDIOMA_PADRAO
        self._i18n_registry: list[tuple[str, Any, dict[str, Any]]] = []

        self.app_dir = os.path.abspath(os.path.dirname(__file__))
        migrate_legacy_jobs_dir(self.app_dir)   # JOBS/ -> PROJECTS/ (older versions)
        self.settings = DockingSettings()
        self.ligand_settings = LigandSettings()
        self.target_settings = TargetSettings()
        self.result_view_settings = ResultViewSettings()
        self.project = ProjectManager(self.app_dir, self)
        self._init_paths()
        self._ensure_runtime_dirs()

        self.setStyleSheet(_SS_MAIN)
        logo_path = os.path.join(self.app_dir, "ICONS", "logo_codocP.png")
        if os.path.isfile(logo_path):
            self.setWindowIcon(QIcon(logo_path))

        screen_obj = QGuiApplication.primaryScreen()
        screen = screen_obj.availableGeometry() if screen_obj is not None else self.geometry()

        self._build_menu()
        self.tabs = QTabWidget()
        self.tabs.setObjectName("main_tabs")
        self.setCentralWidget(self.tabs)
        self._build_tabs()
        self.project.changed.connect(self._on_project_changed)
        self._refresh_project_texts()
        self._apply_initial_window_size(screen)
        self._start_hw_monitor()

    def _init_paths(self) -> None:
        self.base_dir = os.path.join(self.app_dir, "BASE")   # where the file dialogs for ligands/targets start
        self.bin_dir = os.path.join(self.app_dir, "BIN")

    # Folders of the open project ("" while no project is open).
    @property
    def ligands_dir(self) -> str:
        return self.project.ligands_dir

    @property
    def targets_dir(self) -> str:
        return self.project.targets_dir

    @property
    def conversion_dir(self) -> str:
        return self.project.conversion_dir

    @property
    def docking_dir(self) -> str:
        return self.project.docking_dir

    def _ensure_runtime_dirs(self) -> None:
        for folder in (
            projects_root(self.app_dir),
            self.base_dir,
            self.bin_dir,
            os.path.join(self.app_dir, "TEST"),
            os.path.join(self.app_dir, "MODULES"),
            os.path.join(self.app_dir, "ICONS"),
        ):
            os.makedirs(folder, exist_ok=True)

    def _t(self, key: str, **kwargs) -> str:
        """Text of `key` in the current interface language (for texts built at the moment they are shown)."""
        return i18n.t(key, self._idioma, **kwargs)

    # ------------------------------------------------------------------ projects ------------------------------------------------------------------
    def _require_project(self) -> bool:
        """Every step works inside the open project; warn when there is none."""
        if self.project.is_open:
            return True
        QMessageBox.warning(self, APP_NAME, self._t("msg_no_project"))
        return False

    def _refresh_previous_projects(self, select: str = "") -> None:
        # At startup nothing is open: "Previous project" (disabled while New Project is selected)
        # shows the last project that was open when CODOC was closed.
        last_open = str(QSettings("CODOC", "CODOC").value("last_project", "") or "")
        current = select or self.cb_prev_project.currentText() or self.project.name or last_open
        self.cb_prev_project.blockSignals(True)
        self.cb_prev_project.clear()
        self.cb_prev_project.addItems(list_projects(self.app_dir))
        index = self.cb_prev_project.findText(current)
        if index >= 0:
            self.cb_prev_project.setCurrentIndex(index)
        self.cb_prev_project.blockSignals(False)

    def _sync_project_mode(self) -> None:
        load_mode = self.rb_proj_load.isChecked()
        self.ed_proj_name.setEnabled(not load_mode)
        self.cb_prev_project.setEnabled(load_mode)
        if load_mode:
            self._refresh_previous_projects()
        self._update_project_date()

    def _update_project_date(self) -> None:
        """Date stamp a new project would receive (only meaningful in "new project" mode)."""
        if not self.rb_proj_load.isChecked():
            self.lbl_proj_date.setText(datetime.now().strftime("%Y-%m-%d_%H-%M"))

    def _leave_current_project(self) -> None:
        """Before another project is opened: keep the settings of the one being left if it was saved
        at least once (so edits made after the last click on Save are not lost). A project that was
        only opened for viewing - e.g. one made by an older version, with no .json files - is not
        given settings it never had."""
        if self.project.is_open and os.path.isfile(self.project.docking_settings_path):
            self._save_settings()

    def _project_create_or_load(self) -> None:
        if self.rb_proj_load.isChecked():
            name = self.cb_prev_project.currentText().strip()
            if not name:
                QMessageBox.warning(self, APP_NAME, self._t("cfg_proj_select_prev"))
                return
            path = os.path.join(projects_root(self.app_dir), name)
            if not os.path.isdir(path):
                QMessageBox.warning(self, APP_NAME, self._t("cfg_proj_not_found", path=path))
                self._refresh_previous_projects()
                return
            if os.path.abspath(path) != self.project.path:
                self._leave_current_project()
            self.project.open(path)
            return
        name = clean_project_name(self.ed_proj_name.text())
        if not name:
            QMessageBox.warning(self, APP_NAME, self._t("cfg_proj_name_required"))
            return
        self._leave_current_project()
        try:
            path = create_project(self.app_dir, name)
        except FileExistsError:
            QMessageBox.warning(self, APP_NAME, self._t("cfg_proj_exists"))
            return
        except OSError as exc:
            QMessageBox.warning(self, APP_NAME, str(exc))
            return
        self.ed_proj_name.clear()
        self._refresh_previous_projects(select=os.path.basename(path))
        self.project.open(path)
        # A brand-new project starts with the settings now on screen, saved as its own .json files.
        self._save_settings()

    def _update_project_status(self) -> None:
        if not hasattr(self, "lbl_proj_status"):
            return
        # Only the warning is shown: once a project is open, Project ID already names it.
        self.lbl_proj_status.setVisible(not self.project.is_open)
        self.lbl_proj_status.setText(self._t("cfg_proj_none"))
        self.lbl_proj_status.setStyleSheet("font-size:9pt;color:#B5766F;")

    def _update_window_title(self) -> None:
        title = self._t("app_titulo")
        self.setWindowTitle(f"{title}  -  {self.project.name}" if self.project.is_open else title)

    def _refresh_project_texts(self) -> None:
        """Texts that depend on the open project AND on the language (window title, status line)."""
        self._update_window_title()
        self._update_project_status()
        if hasattr(self, "lbl_proj_id"):
            self.lbl_proj_id.setText(self.project.name or "-")      # the project open now, not the selected one
        if hasattr(self, "lbl_results_project"):
            self.lbl_results_project.setText(self._t("s4_lbl_project", name=self.project.name or "-"))

    def _on_project_changed(self, path: str) -> None:
        if path:
            QSettings("CODOC", "CODOC").setValue("last_project", os.path.basename(path))
            self._load_project_settings()
            self.rb_proj_load.setChecked(True)          # shows the open project in "load" mode
            self._refresh_previous_projects(select=self.project.name)
            self.cb_prev_project.setCurrentText(self.project.name)
        self._refresh_project_texts()
        self._refresh_ligand_monitor()
        self._refresh_targets_summary()
        self._populate_prepared_targets()
        self._refresh_result_selectors()

    def _build_menu(self) -> None:
        menu_bar = self.menuBar()
        menu = menu_bar.addMenu("Menu")

        action_home = QAction(self)
        self._tr("menu_home", action_home.setText)
        action_home.triggered.connect(lambda: self.tabs.setCurrentIndex(0))
        menu.addAction(action_home)

        for tab_index, menu_key in enumerate(("menu_config", "menu_step1", "menu_step2", "menu_step3", "menu_step4"), start=1):
            action = QAction(self)
            self._tr(menu_key, action.setText)
            action.triggered.connect(lambda _checked=False, i=tab_index: self.tabs.setCurrentIndex(i))
            menu.addAction(action)

        menu.addSeparator()

        action_exit = QAction(self)
        self._tr("menu_exit", action_exit.setText)
        action_exit.triggered.connect(self._close_from_action)
        menu.addAction(action_exit)

        help_menu = menu_bar.addMenu("")
        self._tr("menu_help", help_menu.setTitle)

        action_install = QAction(self)
        self._tr("menu_install_requirements", action_install.setText)
        action_install.triggered.connect(self.show_requirements_installer)
        help_menu.addAction(action_install)

        action_terminal = QAction(self)
        self._tr("menu_terminal", action_terminal.setText)
        action_terminal.triggered.connect(self.open_terminal)
        help_menu.addAction(action_terminal)

        help_menu.addSeparator()

        action_github = QAction(self)
        self._tr("menu_github", action_github.setText)
        action_github.triggered.connect(self.open_github_page)
        help_menu.addAction(action_github)

        # "About Us" is a first-level item of the bar (Menu | Help | About Us), not an entry of Help:
        # an action added straight to the QMenuBar is a clickable title that triggers it.
        action_about = QAction(self)
        self._tr("menu_about", action_about.setText)
        action_about.triggered.connect(self.show_about)
        menu_bar.addAction(action_about)

    def _close_from_action(self) -> None:
        self.close()

    def open_terminal(self) -> None:
        """Terminal inside the CODOC Python environment, showing the output of this session."""
        if not codoc_terminal.open_terminal(self.app_dir, venv_paths("CODOC")["venv_dir"]):
            QMessageBox.warning(self, APP_NAME, self._t("msg_terminal_unavailable"))

    def open_github_page(self) -> None:
        webbrowser.open("https://github.com/moimaian")

    def show_about(self) -> None:
        QMessageBox.about(
            self,
            i18n.t("msg_title_about", self._idioma),
            i18n.t("msg_about_body", self._idioma) + f"\n\n{i18n.t('msg_about_version', self._idioma)}: {VERSAO}",
        )

    def _tr(self, chave: str, apply_fn, **kwargs) -> None:
        """Registra apply_fn (ex.: label.setText, btn.setToolTip, lambda txt: self.tabs.setTabText(0, txt))
        para ser reexecutado sempre que o idioma da interface mudar, e já aplica o texto do idioma
        atual imediatamente. chave/kwargs sao repassados para i18n.t() a cada reaplicacao, entao
        strings com placeholders dinamicos continuam corretas apos trocar de idioma."""
        self._i18n_registry.append((chave, apply_fn, kwargs))
        apply_fn(i18n.t(chave, self._idioma, **kwargs))

    def _definir_idioma(self, idioma: str) -> None:
        if idioma == self._idioma:
            return
        self._idioma = idioma
        QSettings("CODOC", "CODOC").setValue("idioma", idioma)
        for chave, apply_fn, kwargs in self._i18n_registry:
            apply_fn(i18n.t(chave, self._idioma, **kwargs))
            # A traducao para PT costuma ser mais longa que o texto original em EN - botoes com
            # largura fixa (a maioria) foram dimensionados uma unica vez na construcao da interface,
            # para o texto do idioma inicial. _ensure_button_text_fits so AUMENTA a largura quando
            # necessario (nunca reduz), entao o layout permanece estavel ao alternar os idiomas.
            target = getattr(apply_fn, "__self__", None)
            if isinstance(target, QPushButton):
                self._ensure_button_text_fits(target)
        self._refresh_project_texts()

    @staticmethod
    def _ensure_button_text_fits(button: QPushButton) -> None:
        text = button.text() or ""
        if not text.strip() or button.property("uniform_width"):
            return
        button.ensurePolished()
        required_width = button.sizeHint().width() + 8
        if button.icon() and not button.icon().isNull():
            required_width += button.iconSize().width()

        current_min = button.minimumWidth()
        current_max = button.maximumWidth()
        has_fixed_width = current_min > 0 and current_min == current_max

        if has_fixed_width:
            if current_min < required_width:
                button.setFixedWidth(required_width)
            return

        if current_min < required_width:
            button.setMinimumWidth(required_width)

    def _title(self, key: str) -> QLabel:
        label = QLabel()
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("font-size: 14pt; font-weight: bold;")
        self._tr(key, label.setText)
        return label

    def _nav_buttons_row(self, previous_index: Optional[int], next_index: Optional[int]) -> QHBoxLayout:
        row = QHBoxLayout()

        back_button = QPushButton()
        back_button.setFixedWidth(200)
        back_button.setStyleSheet(_SS_BTN_NAV)
        back_button.setEnabled(previous_index is not None)
        self._tr("btn_back", back_button.setText)
        if previous_index is not None:
            back_button.clicked.connect(lambda: self.tabs.setCurrentIndex(previous_index))

        next_button = QPushButton()
        next_button.setFixedWidth(200)
        next_button.setStyleSheet(_SS_BTN_NAV)
        next_button.setEnabled(next_index is not None)
        self._tr("btn_next", next_button.setText)
        if next_index is not None:
            next_button.clicked.connect(lambda: self.tabs.setCurrentIndex(next_index))

        row.addWidget(back_button, alignment=Qt.AlignLeft)
        row.addWidget(next_button, alignment=Qt.AlignRight)
        return row

    def _apply_initial_window_size(self, screen) -> None:
        hint = self.sizeHint()
        home_hint = self.tabs.widget(0).sizeHint() if hasattr(self, "tabs") and self.tabs.count() else hint
        # Every tab fits in its own minimum width (the step tabs' 1000 px groups; HOME's groups are the
        # same width), so the window opens only a little wider than that, with no horizontal scroll.
        width_hint = hint.width() + 24
        height_hint = max(hint.height() + 110, home_hint.height() + 220)
        width = min(width_hint, int(screen.width() * 0.78))
        height = min(max(height_hint, 980), int(screen.height() * 0.94))
        self.resize(width, height)
        self.move((screen.width() - self.width()) // 2, (screen.height() - self.height()) // 2)

    def _build_tabs(self) -> None:
        self._build_home_tab()
        self._build_config_tab()
        self._build_ligands_tab()
        self._build_targets_tab()
        self._build_docking_tab()
        self._build_results_tab()
        self._apply_settings_to_widgets()
        # Buttons are created with fixed widths sized by eye; grow any whose text is clipped
        # (the same helper already runs after a language switch for the longer Portuguese texts).
        for button in self.tabs.findChildren(QPushButton):
            self._ensure_button_text_fits(button)

    def _build_home_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(9, 32, 9, 24)      # same side margins as the step tabs
        inner_layout.setSpacing(16)
        scroll.setWidget(inner)

        logo = QLabel()
        logo_path = os.path.join(self.app_dir, "ICONS", "LOGO_CODOC2.png")
        if os.path.isfile(logo_path):
            pix = QPixmap(logo_path).scaled(120, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo.setPixmap(pix)
        logo.setAlignment(Qt.AlignCenter)
        inner_layout.addWidget(logo)

        title = QLabel()
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 16pt; font-weight: bold;")
        self._tr("home_title", title.setText)
        inner_layout.addWidget(title)

        subtitle = QLabel()
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("font-size: 11pt; color: #6E8CA8;")
        self._tr("home_subtitle", subtitle.setText)
        inner_layout.addWidget(subtitle)

        top_separator = QFrame()
        top_separator.setFrameShape(QFrame.HLine)
        top_separator.setFrameShadow(QFrame.Sunken)
        top_separator.setStyleSheet("color:#2A4A6B;")
        inner_layout.addWidget(top_separator)

        hw_row = QHBoxLayout()
        hw_row.setSpacing(14)
        home_group_style = (
            "QGroupBox { background-color: transparent; border: 1.5px solid #2A4A6B; border-radius: 6px; }"
            "QGroupBox::title { color: #29B6D8; }"
        )

        def add_centered_group(widget: QWidget, group_width: int = 1000) -> None:
            # 1000 px like the groups of the step tabs, so HOME never needs more width than they do
            widget.setMinimumWidth(group_width)
            widget.setMaximumWidth(group_width)
            row_wrap = QHBoxLayout()
            row_wrap.addStretch(1)
            row_wrap.addWidget(widget)
            row_wrap.addStretch(1)
            inner_layout.addLayout(row_wrap)

        for title_key, rows in (
            ("home_grp_cpu", self._home_hw_cpu_info()),
            ("home_grp_gpu", self._home_hw_gpu_info()),
            ("home_grp_storage", self._home_hw_storage_info()),
        ):
            hw_grp = QGroupBox()
            self._tr(title_key, hw_grp.setTitle)
            hw_grp.setStyleSheet(home_group_style)
            hw_form = QFormLayout(hw_grp)
            hw_form.setHorizontalSpacing(16)
            hw_form.setVerticalSpacing(4)
            for label_text, value_text in rows:
                key_label = QLabel(label_text)
                key_label.setStyleSheet("color:#6E8CA8;font-size:9pt;")
                value_label = QLabel(value_text)
                value_label.setStyleSheet("font-weight:bold;font-size:9pt;color:#C9D1D9;")
                value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
                value_label.setWordWrap(True)
                hw_form.addRow(key_label, value_label)
            hw_row.addWidget(hw_grp, hw_grp.sizeHint().width())     # share the row by content width; all three get the height of the tallest

        hw_wrap = QWidget()
        hw_wrap.setLayout(hw_row)
        add_centered_group(hw_wrap)

        sw_grp = QGroupBox()
        self._tr("home_grp_sw", sw_grp.setTitle)
        sw_grp.setStyleSheet(home_group_style)
        sw_grid = QGridLayout(sw_grp)
        # Three (name, version) pairs separated by a spacer column: the name sits right next to its
        # version, and the first pair gets most of the spare width so the long "Platform" value
        # does not need to wrap, while the narrower versions of the other two pairs stay compact.
        sw_grid.setHorizontalSpacing(8)
        sw_grid.setVerticalSpacing(4)
        cols = 3
        for pair in range(cols):
            if pair:
                sw_grid.setColumnMinimumWidth(pair * 3 - 1, 28)
            sw_grid.setColumnStretch(pair * 3 + 1, 4 if pair == 0 else 1)
        sw_items = self._home_sw_versions()
        for idx, (name, version) in enumerate(sw_items):
            row = idx // cols
            col = (idx % cols) * 3
            ok = version != "not installed"
            name_label = QLabel(name)
            name_label.setStyleSheet("color:#6E8CA8;font-size:9pt;")
            version_label = QLabel(version)
            version_label.setStyleSheet(
                f"font-weight:bold;font-size:9pt;color:{'#C9D1D9' if ok else '#E74C3C'};"
            )
            version_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            version_label.setWordWrap(True)
            sw_grid.addWidget(name_label, row, col)
            sw_grid.addWidget(version_label, row, col + 1)
        add_centered_group(sw_grp)

        pipe_grp = QGroupBox()
        self._tr("home_grp_pipeline", pipe_grp.setTitle)
        pipe_grp.setStyleSheet(home_group_style)
        pipe_grid = QGridLayout(pipe_grp)
        pipe_grid.setHorizontalSpacing(20)
        pipe_grid.setVerticalSpacing(6)
        pipe_grid.setColumnStretch(1, 1)
        steps = [
            ("home_config_name", "home_config_desc"),
            ("home_step1_name", "home_step1_desc"),
            ("home_step2_name", "home_step2_desc"),
            ("home_step3_name", "home_step3_desc"),
            ("home_step4_name", "home_step4_desc"),
        ]
        for row, (name_key, desc_key) in enumerate(steps):
            step_label = QLabel()
            step_label.setStyleSheet("color:#C9D1D9;font-size:9pt;")
            self._tr(name_key, lambda txt, w=step_label: w.setText(f"<b>{txt}</b>"))
            desc_label = QLabel()
            desc_label.setStyleSheet("color:#6E8CA8;font-size:9pt;")
            desc_label.setWordWrap(True)
            self._tr(desc_key, desc_label.setText)
            pipe_grid.addWidget(step_label, row, 0)
            pipe_grid.addWidget(desc_label, row, 1)
        add_centered_group(pipe_grp)

        bottom_separator = QFrame()
        bottom_separator.setFrameShape(QFrame.HLine)
        bottom_separator.setFrameShadow(QFrame.Sunken)
        bottom_separator.setStyleSheet("color:#2A4A6B;")
        inner_layout.addWidget(bottom_separator)

        btn_start = QPushButton()
        btn_start.setFixedWidth(240)
        self._tr("home_btn_start", btn_start.setText)
        btn_start.clicked.connect(lambda: self.tabs.setCurrentIndex(1))
        inner_layout.addWidget(btn_start, alignment=Qt.AlignCenter)

        btn_install = QPushButton()
        btn_install.setFixedWidth(240)
        btn_install.setStyleSheet(_SS_BTN_NAV)
        self._tr("home_btn_install", btn_install.setText)
        btn_install.clicked.connect(self.show_requirements_installer)
        inner_layout.addWidget(btn_install, alignment=Qt.AlignCenter)

        inner_layout.addStretch(1)

        footer_label = QLabel(f"v{VERSAO}  ·  © 2024–2026 CEB/UFPR  ·  GPL-3.0")
        footer_label.setAlignment(Qt.AlignCenter)
        footer_label.setStyleSheet("font-size:8pt;color:#6E8CA8;margin-top:6px;")
        inner_layout.addWidget(footer_label)

        layout.addWidget(scroll)

        home_tab_index = self.tabs.addTab(tab, "")
        self._tr("tab_home", lambda txt, i=home_tab_index: self.tabs.setTabText(i, txt))

    def _home_hw_cpu_info(self) -> list[tuple[str, str]]:
        rows: list[tuple[str, str]] = []
        model = ""
        base_mhz = 0.0
        max_mhz = 0.0
        cores_phys = 0
        cores_log = 0
        sockets = 1
        l2_cache = ""
        l3_cache = ""

        try:
            out = subprocess.check_output(["lscpu"], text=True, stderr=subprocess.DEVNULL)
            for line in out.splitlines():
                key, _, value = line.partition(":")
                key = key.strip()
                value = value.strip()
                if key == "Model name":
                    model = value
                elif key == "Socket(s)":
                    try:
                        sockets = int(value)
                    except Exception:
                        pass
                elif key == "Core(s) per socket":
                    try:
                        cores_phys = int(value) * sockets
                    except Exception:
                        pass
                elif key == "CPU(s)":
                    try:
                        cores_log = int(value)
                    except Exception:
                        pass
                elif key in ("CPU MHz", "CPU base MHz", "Frequency (MHz)"):
                    try:
                        base_mhz = float(value)
                    except Exception:
                        pass
                elif key == "CPU max MHz":
                    try:
                        max_mhz = float(value)
                    except Exception:
                        pass
                elif key == "L2 cache":
                    l2_cache = value
                elif key == "L3 cache":
                    l3_cache = value
        except Exception:
            pass

        try:
            with open("/proc/cpuinfo", "r", encoding="utf-8", errors="ignore") as handle:
                cpuinfo = handle.read()
            if not model:
                match = re.search(r"model name\s*:\s*(.+)", cpuinfo)
                if match:
                    model = match.group(1).strip()
            if base_mhz == 0.0:
                match = re.search(r"cpu MHz\s*:\s*([\d.]+)", cpuinfo)
                if match:
                    base_mhz = float(match.group(1))
            if cores_phys == 0:
                cores_matches = re.findall(r"cpu cores\s*:\s*(\d+)", cpuinfo)
                phys_ids = set(re.findall(r"physical id\s*:\s*(\d+)", cpuinfo))
                if cores_matches:
                    cores_phys = int(cores_matches[0]) * (len(phys_ids) or 1)
        except Exception:
            pass

        if psutil is not None:
            try:
                if cores_phys == 0:
                    cores_phys = psutil.cpu_count(logical=False) or 0
                if cores_log == 0:
                    cores_log = psutil.cpu_count(logical=True) or 0
                freq = psutil.cpu_freq()
                if freq:
                    if base_mhz == 0.0 and freq.current:
                        base_mhz = freq.current
                    if max_mhz == 0.0 and freq.max:
                        max_mhz = freq.max
            except Exception:
                pass

        if not model:
            model = platform.processor() or "N/A"

        rows.append(("Architecture", platform.machine()))
        rows.append(("Model", model or "N/A"))
        rows.append(("Base clock", f"{base_mhz / 1000:.2f} GHz" if base_mhz else "N/A"))
        rows.append(("Max clock", f"{max_mhz / 1000:.2f} GHz" if max_mhz else "N/A"))
        rows.append(("Physical cores", str(cores_phys) if cores_phys else "N/A"))
        rows.append(("Logical threads", str(cores_log) if cores_log else "N/A"))
        if l2_cache:
            rows.append(("L2 cache", l2_cache))
        if l3_cache:
            rows.append(("L3 cache", l3_cache))

        if psutil is not None:
            try:
                mem = psutil.virtual_memory()
                rows.append(("RAM total", f"{mem.total / 1073741824:.1f} GB"))
                rows.append(("RAM available", f"{mem.available / 1073741824:.1f} GB"))
            except Exception:
                pass

        return rows

    def _home_hw_gpu_info(self) -> list[tuple[str, str]]:
        rows: list[tuple[str, str]] = []
        if not shutil.which("nvidia-smi"):
            rows.append(("GPU", "nvidia-smi not found"))
            return rows
        try:
            fields = "name,memory.total,clocks.max.sm,clocks.max.memory,power.limit,driver_version,compute_cap"
            raw = subprocess.check_output(
                ["nvidia-smi", f"--query-gpu={fields}", "--format=csv,noheader,nounits"],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=4,
            ).strip().splitlines()[0]
            parts = [part.strip() for part in raw.split(",")]
            labels = [
                "Model",
                "VRAM total (MiB)",
                "Max SM clock (MHz)",
                "Max mem clock (MHz)",
                "TDP (W)",
                "Driver",
                "Compute capability",
            ]
            rows.extend(zip(labels, parts))
            rows = [(k, v[:-3] if k == "TDP (W)" and v.endswith(".00") else v) for k, v in rows]
        except Exception as exc:
            rows.append(("Error", str(exc)))
            return rows

        # Highest CUDA version the driver supports (header of a plain nvidia-smi call).
        try:
            header = subprocess.check_output(
                ["nvidia-smi"], text=True, stderr=subprocess.DEVNULL, timeout=4
            )
            match = re.search(r"CUDA Version:\s*([\d.]+)", header)
            if match:
                rows.append(("CUDA max (driver)", match.group(1)))
        except Exception:
            pass

        # Streaming multiprocessors come from OpenCL (Max compute units = SMs on NVIDIA), since
        # nvidia-smi does not report them. CUDA cores and FP32 throughput are estimates derived
        # from the SM count, the compute capability and the maximum SM clock.
        try:
            values = dict(rows)
            gpu_name = values.get("Model", "")
            sm_count = next(
                (
                    int(dev.get("compute_units") or 0)
                    for dev in detect_opencl_devices()
                    if gpu_name and gpu_name in str(dev.get("device_name", ""))
                ),
                0,
            )
            if sm_count:
                rows.append(("Multiprocessors (SM)", str(sm_count)))
                capability = tuple(int(x) for x in values.get("Compute capability", "0.0").split(".")[:2])
                if capability in ((8, 0), (6, 0)) or capability[0] in (7,):
                    cores_per_sm = 64
                else:
                    cores_per_sm = 128
                total_cores = sm_count * cores_per_sm
                rows.append(("CUDA cores (est.)", str(total_cores)))
                sm_clock = float(values.get("Max SM clock (MHz)", "0") or 0)
                if sm_clock:
                    rows.append(("FP32 perf. (TFLOPs, est.)", f"{total_cores * 2 * sm_clock / 1e6:.1f}"))
        except Exception:
            pass
        return rows

    def _avg_docking_result_bytes(self, sample_limit: int = 300) -> float:
        """Average disk size of the result of ONE docked ligand (DOCKING/<target>/<group>/<ligand>/),
        measured over up to `sample_limit` ligand folders of the existing projects, newest first.
        0 when no project holds a docking result yet."""
        sizes: list[int] = []
        for project in list_projects(self.app_dir):
            docking = os.path.join(projects_root(self.app_dir), project, "DOCKING")
            try:
                for target in os.scandir(docking):
                    for group in (os.scandir(target.path) if target.is_dir() else []):
                        for ligand in (os.scandir(group.path) if group.is_dir() else []):
                            if not ligand.is_dir():
                                continue
                            with os.scandir(ligand.path) as files:
                                sizes.append(sum(f.stat().st_size for f in files if f.is_file()))
                            if len(sizes) >= sample_limit:
                                return sum(sizes) / len(sizes)
            except OSError:
                continue
        return sum(sizes) / len(sizes) if sizes else 0.0

    def _home_hw_storage_info(self) -> list[tuple[str, str]]:
        """Disk where CODOC is installed (PROJECTS/, BASE/ and every docking result live there)."""
        rows: list[tuple[str, str]] = []
        try:
            usage = shutil.disk_usage(self.app_dir)
        except Exception as exc:
            rows.append(("Error", str(exc)))
            return rows
        rows.append(("Mount point", self.app_dir))
        rows.append(("Total", f"{usage.total / 1e9:.1f} GB"))
        rows.append(("Used", f"{usage.used / 1e9:.1f} GB ({usage.used * 100 / usage.total:.0f}%)"))
        rows.append(("Free", f"{usage.free / 1e9:.1f} GB"))

        # Media type from /sys/block/<dev>/queue/rotational (0 = SSD/NVMe, 1 = spinning disk).
        try:
            device = ""
            if psutil is not None:
                best = ""
                for part in psutil.disk_partitions(all=False):
                    if self.app_dir.startswith(part.mountpoint) and len(part.mountpoint) >= len(best):
                        best, device = part.mountpoint, part.device
            if device:
                rows.append(("Device", device))
                base = os.path.basename(device)
                base = base.split("p")[0] if base.startswith("nvme") else base.rstrip("0123456789")
                rotational = Path(f"/sys/block/{base}/queue/rotational")
                if rotational.exists():
                    if rotational.read_text().strip() == "1":
                        media = "HDD (rotational)"
                    else:
                        media = "NVMe SSD" if base.startswith("nvme") else "SSD"
                    rows.append(("Media type", media))
        except Exception:
            pass

        # How many more docked ligands the free space holds, from the measured size of the results
        # already on disk. CODOC stores no float32/float16 data, so both lines give the same estimate.
        average = self._avg_docking_result_bytes()
        estimate = f"~{int(usage.free / average):,} ligands".replace(",", ".") if average else "N/A"
        rows.append(("Fits (float32)", estimate))
        rows.append(("Fits (float16)", estimate))
        return rows

    def _home_sw_versions(self) -> list[tuple[str, str]]:
        hardware = detect_hardware()
        rows: list[tuple[str, str]] = [
            ("Platform", str(hardware.get("platform", "unknown"))),
            ("Python", sys.version.split()[0]),
        ]

        def version_or_availability(
            command_name: str,
            version_args: list[str],
            local_file: str,
            line_index: int = 0,
        ) -> str:
            def extract_numeric_version(text: str) -> Optional[str]:
                match = re.search(r"\b\d+(?:\.\d+)+\b", text)
                return match.group(0) if match else None

            command_path = shutil.which(command_name)
            if command_path:
                try:
                    result = subprocess.run(
                        [command_path] + version_args,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                    )
                    if result.returncode == 0:
                        lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
                        if lines:
                            index = min(max(line_index, 0), len(lines) - 1)
                            return extract_numeric_version(lines[index]) or lines[index]
                except Exception:
                    pass
            return "available" if os.path.isfile(local_file) else "unavailable"

        libraries = [
            ("PyQt5", "PyQt5.QtCore", "PYQT_VERSION_STR"),
            ("Pandas", "pandas", "__version__"),
            ("Matplotlib", "matplotlib", "__version__"),
            ("psutil", "psutil", "__version__"),
            ("RDKit", "rdkit", "__version__"),
            ("Meeko", "meeko", "__version__"),
            ("python-docx", "docx", "__version__"),
        ]
        for display, module_name, attr_name in libraries:
            try:
                module = importlib.import_module(module_name)
                version = getattr(module, attr_name, "available")
            except Exception:
                version = "not installed"
            rows.append((display, str(version)))
        try:
            importlib.import_module("dimorphite_dl")
            dimorphite_version = importlib.metadata.version("dimorphite-dl")
        except Exception:
            dimorphite_version = "not installed"
        rows.append(("Dimorphite-DL", str(dimorphite_version)))
        rows.append(("Boost", get_boost_version() or "not installed"))
        rows.append((
            "OpenBabel",
            version_or_availability(
                "obabel",
                ["-V"],
                os.path.join(self.bin_dir, "openbabel-3-0-0.tar.gz"),
            ),
        ))
        rows.append((
            "AutoDock Vina",
            version_or_availability(
                "vina",
                ["--version"],
                os.path.join(self.bin_dir, "vina_1.2.5_linux_x86_64"),
            ),
        ))
        rows.append((
            "vina_split",
            version_or_availability(
                "vina_split",
                ["--version"],
                os.path.join(self.bin_dir, "vina_split_1.2.5_linux_x86_64"),
            ),
        ))
        rows.append(("ADFRsuite", "available" if os.path.isfile(os.path.join(str(Path.home()), "ADFRsuite-1.0", "bin", "prepare_receptor")) else "not installed"))
        rows.append(("Vina-GPU", get_vina_gpu_version() or "not installed"))
        # PDB2PQR (protonation) and PROPKA (the pKa predictor it calls) are separate packages with their own versions
        try:
            find_pdb2pqr(os.path.join(venv_paths("CODOC")["venv_dir"], "bin"))
            try:
                pdb2pqr_status = importlib.metadata.version("pdb2pqr")
            except importlib.metadata.PackageNotFoundError:
                pdb2pqr_status = "available"
        except TargetPrepareError:
            pdb2pqr_status = "not installed"
        rows.append(("PDB2PQR", pdb2pqr_status))
        try:
            propka_status = importlib.metadata.version("propka")
        except importlib.metadata.PackageNotFoundError:
            propka_status = "not installed"
        rows.append(("PROPKA", propka_status))
        return rows

    def _settings_buttons_row(self) -> QHBoxLayout:
        """Save/Reload settings buttons, centred under the Performance Options group."""
        row = QHBoxLayout()
        row.addStretch(1)
        btn_save = QPushButton()
        btn_save.setFixedWidth(180)
        self._tr("cfg_btn_save_settings", btn_save.setText)
        btn_save.clicked.connect(self._save_settings_clicked)
        btn_reload = QPushButton()
        btn_reload.setFixedWidth(180)
        btn_reload.setStyleSheet(_SS_BTN_SECONDARY)
        self._tr("cfg_btn_reload_settings", btn_reload.setText)
        btn_reload.clicked.connect(self._reload_settings_clicked)
        row.addWidget(btn_save)
        row.addWidget(btn_reload)
        row.addStretch(1)
        return row

    def _build_config_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(self._title("title_config"))

        config_group_width = 1000

        def add_centered_group(widget: QWidget, group_width: int = config_group_width) -> None:
            widget.setMinimumWidth(group_width)
            widget.setMaximumWidth(group_width)
            row_wrap = QHBoxLayout()
            row_wrap.addStretch(1)
            row_wrap.addWidget(widget)
            row_wrap.addStretch(1)
            layout.addLayout(row_wrap)

        # ---------------------------------------------------------------- Projects
        # Same structure as the CODYN/CODEEP "Projects" group: create a PROJECTS/<date>_<name>/ folder or
        # reopen a previous one (its ligands, targets, results and the .json settings of every step).
        proj_box = QGroupBox()
        self._tr("cfg_grp_projects", proj_box.setTitle)
        proj_form = QFormLayout(proj_box)
        proj_form.setHorizontalSpacing(18)
        proj_form.setVerticalSpacing(10)
        self.rb_proj_new, self.rb_proj_load = QCheckBox(), QCheckBox()
        self._tr("cfg_proj_new", self.rb_proj_new.setText)
        self._tr("cfg_proj_load", self.rb_proj_load.setText)
        self._proj_modes = QButtonGroup(self)          # the two check boxes are mutually exclusive
        self._proj_modes.setExclusive(True)
        self._proj_modes.addButton(self.rb_proj_new)
        self._proj_modes.addButton(self.rb_proj_load)
        self.rb_proj_new.setChecked(True)
        self.lbl_proj_date = QLabel()
        self.lbl_proj_date.setStyleSheet("font-weight:bold;")
        self.ed_proj_name = QLineEdit()
        self.ed_proj_name.setMaximumWidth(340)
        self._tr("cfg_proj_ph_name", self.ed_proj_name.setPlaceholderText)
        self.cb_prev_project = QComboBox()
        self.cb_prev_project.setMaximumWidth(340)
        self.cb_prev_project.setEnabled(False)
        self._tr("cfg_proj_prev_tip", self.cb_prev_project.setToolTip)
        self.lbl_proj_id = QLabel("-")
        self.lbl_proj_id.setStyleSheet("font-weight:bold;color:#29B6D8;")
        self.lbl_proj_status = QLabel()
        self.lbl_proj_status.setWordWrap(True)
        self.lbl_proj_status.setAlignment(Qt.AlignCenter)
        self.lbl_proj_status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        btn_project = QPushButton()
        btn_project.setFixedSize(230, 38)
        self._tr("cfg_proj_btn", btn_project.setText)

        def add_form_label_row(key: str, widget: QWidget) -> None:
            label = QLabel(); self._tr(key, label.setText)
            proj_form.addRow(label, widget)

        add_form_label_row("cfg_proj_date", self.lbl_proj_date)
        proj_form.addRow(self.rb_proj_new)
        add_form_label_row("cfg_proj_name", self.ed_proj_name)
        proj_form.addRow(self.rb_proj_load)
        add_form_label_row("cfg_proj_prev", self.cb_prev_project)
        add_form_label_row("cfg_proj_id", self.lbl_proj_id)
        btn_wrap = QWidget()
        btn_wrap_layout = QHBoxLayout(btn_wrap)
        btn_wrap_layout.setContentsMargins(0, 6, 0, 0)
        btn_wrap_layout.addStretch(1)
        btn_wrap_layout.addWidget(btn_project)
        btn_wrap_layout.addStretch(1)
        proj_form.addRow(btn_wrap)
        proj_form.addRow(self.lbl_proj_status)
        self.rb_proj_new.toggled.connect(self._sync_project_mode)
        self.ed_proj_name.textChanged.connect(self._update_project_date)
        btn_project.clicked.connect(self._project_create_or_load)

        # ---------------------------------------------------------------- Performance Options
        perf_box = QGroupBox()
        self._tr("cfg_grp_performance", perf_box.setTitle)
        perf_form = QFormLayout(perf_box)
        perf_form.setHorizontalSpacing(18)
        perf_form.setVerticalSpacing(10)
        perf_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.cb_processing_type = QComboBox(); self.cb_processing_type.addItems(["CPU", "GPU"])
        self.sp_cpu_threads = QSpinBox(); self.sp_cpu_threads.setRange(1, 512)
        self.sp_gpu_threads = QSpinBox(); self.sp_gpu_threads.setRange(1, 500000)
        self.cb_opencl_platform = QComboBox()
        self.cb_opencl_device = QComboBox()
        self.cb_opencl_platform.currentIndexChanged.connect(self._update_opencl_device_choices)
        self.cb_processing_type.currentTextChanged.connect(self._toggle_docking_mode_options)
        for key, widget in (
            ("cfg_lbl_processing_type", self.cb_processing_type),
            ("cfg_lbl_cpu_threads", self.sp_cpu_threads),
            ("cfg_lbl_gpu_threads", self.sp_gpu_threads),
            ("cfg_lbl_opencl_platform", self.cb_opencl_platform),
            ("cfg_lbl_opencl_device", self.cb_opencl_device),
        ):
            label = QLabel(); self._tr(key, label.setText)
            perf_form.addRow(label, widget)

        # Projects, Performance Options and the Save/Reload buttons stack in one centred column that takes
        # half of the window width (both groups have that same width).
        top_row = QHBoxLayout()
        top_row.setSpacing(14)
        left_col = QVBoxLayout()
        left_col.setSpacing(10)
        left_col.addWidget(proj_box)
        left_col.addWidget(perf_box)
        left_col.addLayout(self._settings_buttons_row())
        left_col.addStretch(1)
        top_row.addStretch(1)
        top_row.addLayout(left_col, 2)         # stretch 1 : 2 : 1 keeps the column at half the window, centred
        top_row.addStretch(1)
        layout.addLayout(top_row)

        self._load_opencl_choices()

        layout.addStretch(1)
        layout.addLayout(self._nav_buttons_row(0, 2))
        config_tab_index = self.tabs.addTab(tab, "")
        self._tr("tab_config", lambda txt, i=config_tab_index: self.tabs.setTabText(i, txt))
        self._refresh_previous_projects()
        self._sync_project_mode()

    def _build_ligands_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(self._title("title_step1"))

        ligands_group_width = 1000
        ligand_monitor_width = 280

        def add_centered_group(widget: QWidget, group_width: int = ligands_group_width) -> None:
            widget.setMinimumWidth(group_width)
            widget.setMaximumWidth(group_width)
            row_wrap = QHBoxLayout()
            row_wrap.addStretch(1)
            row_wrap.addWidget(widget)
            row_wrap.addStretch(1)
            layout.addLayout(row_wrap)

        box = QGroupBox()
        self._tr("s1_grp_prep_settings", box.setTitle)
        box_layout = QVBoxLayout(box)

        # "Ligands": Browse opens the BASE folder; the chosen files / folders are copied into the
        # project's CONVERSION/LIGANDS (the common LIGANDS folder no longer exists).
        self.ed_ligands = QLineEdit()
        self.ed_ligands.setReadOnly(True)
        self._tr("s1_ph_ligands", self.ed_ligands.setPlaceholderText)
        self._tr("s1_tip_ligands", self.ed_ligands.setToolTip)
        ligands_row = QHBoxLayout()
        lbl_ligands = QLabel(); self._tr("s1_lbl_ligands", lbl_ligands.setText)
        ligands_row.addWidget(lbl_ligands)
        ligands_row.addWidget(self._path_row(self.ed_ligands, self._browse_ligand_sources), 1)
        box_layout.addLayout(ligands_row)

        settings_form = QGridLayout()
        self.sp_lig_file_size = QSpinBox(); self.sp_lig_file_size.setRange(1, 1000000)
        self.sp_lig_ph = QDoubleSpinBox(); self.sp_lig_ph.setRange(0.0, 100.0); self.sp_lig_ph.setDecimals(2)
        self.sp_lig_max_folder = QSpinBox(); self.sp_lig_max_folder.setRange(1, 1000000)
        self.ed_lig_reject = QLineEdit()
        self.cb_lig_conversion_engine = QComboBox(); self.cb_lig_conversion_engine.addItems(["RDKit", "OpenBabel"])
        self.cb_lig_conversion_engine.currentTextChanged.connect(self._sync_lig_conversion_settings_state)
        self.sp_lig_workers = QSpinBox(); self.sp_lig_workers.setRange(1, max(1, (os.cpu_count() or 1) * 4))
        self.sp_lig_steps = QSpinBox(); self.sp_lig_steps.setRange(1, 1000000)
        self.sp_lig_mw_min = QDoubleSpinBox(); self.sp_lig_mw_min.setRange(-10000.0, 10000.0); self.sp_lig_mw_min.setDecimals(3)
        self.sp_lig_mw_max = QDoubleSpinBox(); self.sp_lig_mw_max.setRange(-10000.0, 10000.0); self.sp_lig_mw_max.setDecimals(3)
        self.sp_lig_logp_min = QDoubleSpinBox(); self.sp_lig_logp_min.setRange(-1000.0, 1000.0); self.sp_lig_logp_min.setDecimals(3)
        self.sp_lig_logp_max = QDoubleSpinBox(); self.sp_lig_logp_max.setRange(-1000.0, 1000.0); self.sp_lig_logp_max.setDecimals(3)
        self.sp_lig_rot = QSpinBox(); self.sp_lig_rot.setRange(0, 1000)
        self.sp_lig_hd = QSpinBox(); self.sp_lig_hd.setRange(0, 1000)
        self.sp_lig_ha = QSpinBox(); self.sp_lig_ha.setRange(0, 1000)
        self.sp_lig_tpsa = QDoubleSpinBox(); self.sp_lig_tpsa.setRange(0.0, 100000.0); self.sp_lig_tpsa.setDecimals(3)
        self.cb_lig_min_algorithm = QComboBox()
        self.cb_lig_min_algorithm.addItems(["Conjugate Gradient", "Steepest Descent"])
        self.cb_lig_min_algorithm.setToolTip(
            "Local optimization algorithm used to minimize ligand geometry.\n"
            "Only affects conversions done by OpenBabel (the selected engine, or the fallback of a\n"
            "failed RDKit conversion). RDKit + Meeko + Dimorphite-DL uses RDKit's own MMFF/UFF\n"
            "minimizer, which has no steepest-descent/conjugate-gradient switch."
        )
        self.cb_lig_min_forcefield = QComboBox()
        self.cb_lig_min_forcefield.addItems(["GAFF", "Ghemical", "MMFF94", "MMFF94s", "UFF"])
        self.cb_lig_min_forcefield.setToolTip(
            "Force field used to minimize ligand geometry.\n"
            "With OpenBabel selected as the conversion engine, it is applied by OpenBabel's own\n"
            "minimizer. With RDKit selected, it is used by RDKit's own conformer optimization step\n"
            "instead - GAFF and Ghemical are OpenBabel-only force fields, so they are left out of\n"
            "this list whenever RDKit is the selected conversion engine."
        )
        self.ed_lig_reject.setToolTip(
            "Regex of element symbols to reject during PDBQT validation (see 'Reject invalid\n"
            "PDBQT'). Applied to the PDBQT files written by OpenBabel (the selected engine or the\n"
            "fallback of a failed RDKit conversion); the files written by RDKit/Meeko are validated\n"
            "chemically instead (reconstructing the molecule and running RDKit's sanitizer)."
        )

        # These 9 widgets stay in "Ligand preparation settings"; the 8 druggability/Lipinski
        # ones below move to their own "Druggability Filter" group. Each group gets its own
        # uniform width, sized to its own widest label/value, now that they are visually separate.
        # The group shares the 1000 px row with the Monitor, so its boxes are kept narrow: the left
        # column holds numbers and the engine name, the right one the widest texts (algorithm names).
        for box_widget in (
            self.sp_lig_file_size, self.sp_lig_ph, self.sp_lig_max_folder,
            self.cb_lig_conversion_engine, self.sp_lig_workers,
        ):
            box_widget.setFixedWidth(100)
        for box_widget in (
            self.sp_lig_steps, self.ed_lig_reject, self.cb_lig_min_algorithm, self.cb_lig_min_forcefield,
        ):
            box_widget.setFixedWidth(180)

        lig_druggability_boxes = [
            self.sp_lig_mw_min, self.sp_lig_mw_max, self.sp_lig_logp_min, self.sp_lig_logp_max,
            self.sp_lig_rot, self.sp_lig_hd, self.sp_lig_ha, self.sp_lig_tpsa,
        ]
        lig_druggability_box_width = max(w.sizeHint().width() for w in lig_druggability_boxes)
        for box_widget in lig_druggability_boxes:
            box_widget.setFixedWidth(lig_druggability_box_width)

        def add_field_row(
            target_form: QGridLayout, row_idx: int, label_col: int, label_key: str, widget: QWidget,
            label_max_width: int = 0,
        ) -> None:
            label_widget = QLabel(); self._tr(label_key, label_widget.setText)
            if label_max_width:
                # long captions (more so in Portuguese) wrap instead of widening the group
                label_widget.setWordWrap(True)
                label_widget.setMaximumWidth(label_max_width)
            target_form.addWidget(label_widget, row_idx, label_col)
            target_form.addWidget(widget, row_idx, label_col + 1)

        # 9 fields in 2 columns (5 + 4): conversion/general settings on the left, minimization and
        # the validation regex on the right. Three columns did not fit in the
        # 1000 px group (labels overlapped the neighbouring field and the last column was clipped).
        column_1 = [
            ("s1_lbl_conversion_engine", self.cb_lig_conversion_engine),
            ("s1_lbl_max_folder", self.sp_lig_max_folder),
            ("s1_lbl_min_file_size", self.sp_lig_file_size),
            ("s1_lbl_workers", self.sp_lig_workers),
            ("s1_lbl_ph", self.sp_lig_ph),
        ]
        column_2 = [
            ("s1_lbl_min_algorithm", self.cb_lig_min_algorithm),
            ("s1_lbl_min_forcefield", self.cb_lig_min_forcefield),
            ("s1_lbl_min_steps", self.sp_lig_steps),
            ("s1_lbl_rejected", self.ed_lig_reject),
        ]
        settings_form.setHorizontalSpacing(8)            # label -> box
        settings_form.setColumnMinimumWidth(2, 16)       # gap between the two columns of fields
        for column_idx, column in enumerate((column_1, column_2)):
            label_col = column_idx * 3
            for row_idx, (label_key, widget) in enumerate(column):
                add_field_row(settings_form, row_idx, label_col, label_key, widget, label_max_width=190)
        box_layout.addLayout(settings_form)

        row = QHBoxLayout()
        row.setAlignment(Qt.AlignCenter)
        row.setSpacing(10)
        btn_refresh = QPushButton()
        btn_refresh.setFixedWidth(220)
        btn_refresh.setStyleSheet(_SS_BTN_SECONDARY)
        self._tr("s1_btn_refresh_monitor", btn_refresh.setText)
        btn_refresh.clicked.connect(self._refresh_ligand_monitor)
        btn_save_lig = QPushButton()
        btn_save_lig.setFixedWidth(220)
        self._tr("s1_btn_save_lig_settings", btn_save_lig.setText)
        btn_save_lig.clicked.connect(self._save_settings_clicked)
        row.addWidget(btn_refresh)
        row.addWidget(btn_save_lig)
        box_layout.addLayout(row)

        # Monitor (right of "Ligand preparation settings"): how many ligands each stage holds,
        # counted over every group folder (each one is a databank or a piece of one that exceeded
        # "Max ligands/folder"). Refreshed while an action runs and whenever one finishes.
        monitor_box = QGroupBox()
        self._tr("s1_grp_monitor", monitor_box.setTitle)
        monitor_box.setFixedWidth(ligand_monitor_width)
        monitor_layout = QVBoxLayout(monitor_box)
        self.tbl_lig_monitor = QTableWidget(len(self._LIGAND_MONITOR_ROWS), 2)
        self.tbl_lig_monitor.verticalHeader().setVisible(False)
        self.tbl_lig_monitor.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tbl_lig_monitor.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tbl_lig_monitor.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tbl_lig_monitor.setSelectionMode(QAbstractItemView.NoSelection)
        self.tbl_lig_monitor.setFocusPolicy(Qt.NoFocus)
        self.tbl_lig_monitor.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._tr("s1_mon_col_type", lambda txt: self.tbl_lig_monitor.setHorizontalHeaderItem(0, QTableWidgetItem(txt)))
        self._tr("s1_mon_col_count", lambda txt: self.tbl_lig_monitor.setHorizontalHeaderItem(1, QTableWidgetItem(txt)))
        for row_idx, (label_key, _counter) in enumerate(self._LIGAND_MONITOR_ROWS):
            name_item = QTableWidgetItem()
            self.tbl_lig_monitor.setItem(row_idx, 0, name_item)
            self._tr(label_key, name_item.setText)
            count_item = QTableWidgetItem("-")
            count_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.tbl_lig_monitor.setItem(row_idx, 1, count_item)
        # All rows always show: they share the table's height, which never goes below what the font needs.
        self.tbl_lig_monitor.verticalHeader().setSectionResizeMode(QHeaderView.Stretch)
        row_min = self.tbl_lig_monitor.fontMetrics().height() + 10
        self.tbl_lig_monitor.setMinimumHeight(
            row_min * (self.tbl_lig_monitor.rowCount() + 1) + 2 * self.tbl_lig_monitor.frameWidth()
        )
        monitor_layout.addWidget(self.tbl_lig_monitor, 1)
        btn_open = QPushButton()
        btn_open.setFixedWidth(220)
        btn_open.setStyleSheet(_SS_BTN_SECONDARY)
        self._tr("s1_btn_open_ligands_folder", btn_open.setText)
        btn_open.clicked.connect(lambda: self._open_path(self.ligands_dir))
        monitor_layout.addWidget(btn_open, 0, Qt.AlignHCenter)

        self.ligand_monitor_timer = QTimer(self)
        self.ligand_monitor_timer.setInterval(2000)
        self.ligand_monitor_timer.timeout.connect(self._refresh_ligand_monitor)

        settings_row = QHBoxLayout()
        settings_row.setSpacing(14)
        settings_row.addWidget(box, 1)        # same height as the Monitor next to it
        settings_row.addWidget(monitor_box, 0)
        settings_wrap = QWidget()
        settings_wrap.setLayout(settings_row)
        add_centered_group(settings_wrap)

        # Druggability Filter (left) and Ligand actions (right) share one row; together they take the same
        # 1000 px as the other groups.
        druggability_box = QGroupBox()
        self._tr("s1_grp_druggability", druggability_box.setTitle)
        druggability_form = QGridLayout(druggability_box)
        # Each limit has a checkbox (captioned with the limit's name) that turns it on or off for the
        # filter; an off limit also disables its box.
        druggability_rows = [
            ("mw_min", "s1_lbl_mw_min", self.sp_lig_mw_min),
            ("mw_max", "s1_lbl_mw_max", self.sp_lig_mw_max),
            ("logp_min", "s1_lbl_logp_min", self.sp_lig_logp_min),
            ("logp_max", "s1_lbl_logp_max", self.sp_lig_logp_max),
            ("h_donor_max", "s1_lbl_hdonor_max", self.sp_lig_hd),
            ("h_acceptor_max", "s1_lbl_hacceptor_max", self.sp_lig_ha),
            ("rotatable_bonds_max", "s1_lbl_rot_max", self.sp_lig_rot),
            ("tpsa_max", "s1_lbl_tpsa_max", self.sp_lig_tpsa),
        ]
        self.chk_lig_drug: dict[str, QCheckBox] = {}
        for row_idx, (limit_key, label_key, widget) in enumerate(druggability_rows):
            check = QCheckBox()
            self._tr(label_key, check.setText)
            check.setChecked(True)
            check.toggled.connect(widget.setEnabled)
            self.chk_lig_drug[limit_key] = check
            druggability_form.addWidget(check, row_idx, 0)
            druggability_form.addWidget(widget, row_idx, 1)

        btn_druggability_filter = QPushButton()
        self._tr("s1_act_druggability_filter", btn_druggability_filter.setText)
        btn_druggability_filter.setFixedWidth(255)
        btn_druggability_filter.clicked.connect(lambda: self._run_ligand_tool("druggability_filter"))
        druggability_form.addWidget(btn_druggability_filter, len(druggability_rows), 0, 1, 2, Qt.AlignCenter)

        actions_box = QGroupBox()
        self._tr("s1_grp_actions", actions_box.setTitle)
        actions_layout = QGridLayout(actions_box)
        # (label key, handler, gray) - "gray" applies _SS_BTN_SECONDARY; the one exception left at
        # its default accent styling is Convert to PDBQT, the main/primary action here.
        ligand_actions = [
            ("s1_act_split_multimodel", lambda: self._run_ligand_tool("split_multimodel"), True),
            ("s1_act_split_large_folders", lambda: self._run_ligand_tool("split_large_folders"), True),
            ("s1_act_move_empty", lambda: self._run_ligand_tool("move_empty"), True),
            ("s1_act_convert_pdbqt", lambda: self._run_ligand_tool("convert_pdbqt"), False),
            ("s1_act_reject_pdbqt", lambda: self._run_ligand_tool("reject_pdbqt"), True),
            ("s1_act_recover_pdbqt", lambda: self._run_ligand_tool("recover_pdbqt"), True),
            ("s1_act_generate_lipinski", lambda: self._run_ligand_tool("generate_lipinski"), True),
            ("s1_act_fix_macrocycles", lambda: self._run_ligand_tool("fix_macrocycles"), True),
        ]
        action_buttons: list[QPushButton] = []
        for idx, (label_key, handler, is_gray) in enumerate(ligand_actions):
            button = QPushButton()
            self._tr(label_key, button.setText)
            if is_gray:
                button.setStyleSheet(_SS_BTN_SECONDARY)
            button.setProperty("uniform_width", True)      # sized below, not by _ensure_button_text_fits
            button.clicked.connect(handler)
            actions_layout.addWidget(button, idx // 2, idx % 2)       # two buttons per row
            action_buttons.append(button)
            if label_key == "s1_act_fix_macrocycles":
                self.btn_lig_fix_macrocycles = button
        # One width for all eight: the widest caption of either language, so it never clips after a switch.
        # the buttons' font is set by the application stylesheet (10pt bold), which a button not yet
        # shown in the window has not received - so the metrics are taken from that same font.
        bold_font = QFont("DejaVu Sans", 10, QFont.Bold)
        bold_metrics = QFontMetrics(bold_font)
        action_button_width = max(
            bold_metrics.horizontalAdvance(i18n.t(label_key, language)) + 2 * 16 + 2 * 1 + 8   # padding, border, margin
            for _button, (label_key, _handler, _gray) in zip(action_buttons, ligand_actions)
            for language in ("en", "pt")
        )
        for button in action_buttons:
            button.setFixedWidth(action_button_width)
        actions_layout.setHorizontalSpacing(12)
        actions_layout.setVerticalSpacing(10)
        actions_layout.setAlignment(Qt.AlignCenter)

        druggability_actions_row = QHBoxLayout()
        druggability_actions_row.setSpacing(14)
        druggability_actions_row.addWidget(druggability_box, 1)
        druggability_actions_row.addWidget(actions_box, 0)
        druggability_actions_wrap = QWidget()
        druggability_actions_wrap.setLayout(druggability_actions_row)
        add_centered_group(druggability_actions_wrap)

        # "Fix macrocycles for GPU" only matters for a GPU docking run (CONFIG Processing type) -
        # enabled/disabled in sync with that combo instead of being always-on regardless of it.
        self.cb_processing_type.currentTextChanged.connect(self._sync_fix_macrocycles_button)
        self._sync_fix_macrocycles_button()

        self.pb_ligand = QProgressBar()
        self.pb_ligand.setValue(0)
        add_centered_group(self.pb_ligand)
        self.txt_ligand_log = QPlainTextEdit()
        self.txt_ligand_log.setReadOnly(True)
        add_centered_group(self.txt_ligand_log)
        layout.addStretch(1)
        layout.addLayout(self._nav_buttons_row(1, 3))
        step2_tab_index = self.tabs.addTab(tab, "")
        self._tr("tab_step1", lambda txt, i=step2_tab_index: self.tabs.setTabText(i, txt))
        self._sync_lig_conversion_settings_state()
        self._refresh_ligand_monitor()

    def _build_targets_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(self._title("title_step2"))

        targets_group_width = 1000

        def add_centered_group(widget: QWidget, group_width: int = targets_group_width) -> None:
            widget.setMinimumWidth(group_width)
            widget.setMaximumWidth(group_width)
            row_wrap = QHBoxLayout()
            row_wrap.addStretch(1)
            row_wrap.addWidget(widget)
            row_wrap.addStretch(1)
            layout.addLayout(row_wrap)

        # Two groups side by side (1000 px in all): "Target Parameters" (how the receptor is prepared) and
        # "Grid Parameters" (where docking is run). Every label sits above its field, a file box takes the
        # whole row with its Select button below it, and "Prepare target" is under both groups.
        bold_metrics = QFontMetrics(QFont("DejaVu Sans", 10, QFont.Bold))

        def button_width(*label_keys: str) -> int:
            """Width that fits the widest caption of the given buttons in either language."""
            return max(
                bold_metrics.horizontalAdvance(i18n.t(key, language)) + 2 * 16 + 2 + 8
                for key in label_keys for language in ("en", "pt")
            )

        action_button_width = button_width(
            "s2_btn_choose_target", "s2_btn_choose_rigid", "s2_btn_choose_flex", "s2_btn_choose_grid",
            "s2_btn_select_ligand", "s2_btn_generate_grid", "s2_btn_export_redock",
        )

        def gray_button(label_key: str, handler) -> QPushButton:
            button = QPushButton()
            self._tr(label_key, button.setText)
            button.setStyleSheet(_SS_BTN_SECONDARY)
            button.setFixedWidth(action_button_width)
            button.clicked.connect(handler)
            return button

        def stacked(field: QWidget, button: QPushButton) -> QWidget:
            """The field on a full row and its (fixed width) button centred right below it."""
            column = QVBoxLayout()
            column.setContentsMargins(0, 0, 0, 0)
            column.setSpacing(6)
            column.addWidget(field)
            column.addWidget(button, 0, Qt.AlignHCenter)
            wrap = QWidget(); wrap.setLayout(column)
            return wrap

        def add_row(form: QFormLayout, label_key: str, field: QWidget) -> None:
            label = QLabel(); self._tr(label_key, label.setText)
            form.addRow(label, field)

        # ---------------------------------------------------------------- Target Parameters
        # Two ways to prepare the receptor, chosen like the grid methods (ticking one disables the other):
        # 1. Rigid Docking (a structure file is protonated and converted) and 2. Flexible Docking (the
        # rigid and flexible receptor PDBQT files are given ready).
        target_box = QGroupBox()
        self._tr("s2_grp_target_params", target_box.setTitle)
        target_layout = QVBoxLayout(target_box)
        target_layout.setSpacing(6)
        self._target_modes: dict[str, tuple[QCheckBox, list[QWidget]]] = {}
        self._target_mode_group = QButtonGroup(self)      # exactly one of the two is always ticked
        self._target_mode_group.setExclusive(True)

        def add_mode(mode: str, title_key: str, widgets: list[QWidget]) -> QCheckBox:
            check = QCheckBox()
            self._tr(title_key, check.setText)
            check.toggled.connect(lambda _checked: self._sync_target_modes())
            self._target_mode_group.addButton(check)
            self._target_modes[mode] = (check, widgets)
            return check

        def captioned(label_key: str, field: QWidget) -> QWidget:
            """A label above its field (or field block)."""
            column = QVBoxLayout()
            column.setContentsMargins(0, 0, 0, 0)
            column.setSpacing(3)
            label = QLabel(); self._tr(label_key, label.setText)
            column.addWidget(label)
            column.addWidget(field)
            wrap = QWidget(); wrap.setLayout(column)
            return wrap

        def inline(label_key: str, field: QWidget) -> tuple[QWidget, QLabel]:
            """A label with its field on the same line."""
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(8)
            label = QLabel(); self._tr(label_key, label.setText)
            row.addWidget(label)
            row.addWidget(field, 1)
            wrap = QWidget(); wrap.setLayout(row)
            return wrap, label

        self.ed_target_name = QLineEdit()
        self._tr("s2_ph_target_name", self.ed_target_name.setPlaceholderText)
        self.ed_target_file = QLineEdit()
        self.ed_target_file.textChanged.connect(self._on_target_structure_changed)
        self.ed_target_rigid_file = QLineEdit()
        self.ed_target_rigid_file.textChanged.connect(self._on_target_structure_changed)
        self.ed_target_flex_file = QLineEdit()

        # Target name (the name of the target's folder) is common to both modes: first, label and box on one line
        name_block, _name_label = inline("s2_lbl_target_name", self.ed_target_name)
        target_layout.addWidget(name_block)

        # 1. Rigid Docking: the Target file and, right after its Select button, the Protonation pH (only the
        # rigid preparation protonates the receptor; a flexible one is given already protonated)
        self.sp_target_ph = QDoubleSpinBox()
        self.sp_target_ph.setRange(0.0, 14.0)
        self.sp_target_ph.setDecimals(2)
        self.sp_target_ph.setSingleStep(0.1)
        self.sp_target_ph.setValue(7.4)
        self.sp_target_ph.setToolTip(
            "Environment pH used by PROPKA to compute each ionizable residue's pKa "
            "(considering its 3D microenvironment) and protonate the receptor accordingly."
        )
        rigid_file_block = captioned("s2_lbl_target_file", stacked(self.ed_target_file, gray_button("s2_btn_choose_target", self._choose_target_file)))
        ph_block, _ph_label = inline("s2_lbl_protonation_ph", self.sp_target_ph)
        self.chk_target_rigid = add_mode("rigid", "s2_opt_rigid", [rigid_file_block, ph_block])
        target_layout.addSpacing(12)
        target_layout.addWidget(self.chk_target_rigid)
        target_layout.addWidget(rigid_file_block)
        target_layout.addWidget(ph_block)

        # 2. Flexible Docking: the rigid and the flexible receptor files
        rigid_receptor_block = captioned("s2_lbl_rigid_receptor", stacked(
            self.ed_target_rigid_file,
            gray_button("s2_btn_choose_rigid", lambda: self._choose_pdbqt_file(self.ed_target_rigid_file, "Select rigid receptor PDBQT")),
        ))
        flex_receptor_block = captioned("s2_lbl_flex_receptor", stacked(
            self.ed_target_flex_file,
            gray_button("s2_btn_choose_flex", lambda: self._choose_pdbqt_file(self.ed_target_flex_file, "Select flexible receptor PDBQT")),
        ))
        self.chk_target_flexible = add_mode("flexible", "s2_opt_flexible", [rigid_receptor_block, flex_receptor_block])
        target_layout.addSpacing(12)
        target_layout.addWidget(self.chk_target_flexible)
        target_layout.addWidget(rigid_receptor_block)
        target_layout.addWidget(flex_receptor_block)

        # ligands found in the PDB of "Target file", offered both for the redocking export (here) and
        # as a grid source (option 4 of Grid Parameters)
        self.cb_redock_ligand = QComboBox()
        btn_export_redock = gray_button("s2_btn_export_redock", self.export_cocrystal_ligand_for_redocking)
        self._tr("s2_tooltip_export_redock", btn_export_redock.setToolTip)
        target_layout.addSpacing(12)
        target_layout.addWidget(captioned("s2_lbl_redock_ligand", self.cb_redock_ligand))
        target_layout.addWidget(btn_export_redock, 0, Qt.AlignHCenter)
        target_layout.addStretch(1)

        # ---------------------------------------------------------------- Grid Parameters
        # Five ways to get the grid. Ticking one disables the others; each one, when run, fills the
        # Grid center / size / spacing boxes below, and "Prepare target" writes grid.txt from them.
        grid_box = QGroupBox()
        self._tr("s2_grp_grid_params", grid_box.setTitle)
        grid_layout = QVBoxLayout(grid_box)
        grid_layout.setSpacing(4)
        self._grid_options: dict[str, tuple[QCheckBox, QWidget]] = {}
        self._grid_method_group = QButtonGroup(self)      # exactly one method is always ticked
        self._grid_method_group.setExclusive(True)

        def add_option(method: str, title_key: str, body_layout) -> None:
            check = QCheckBox()
            self._tr(title_key, check.setText)
            check.toggled.connect(lambda checked, m=method: self._sync_grid_methods(m, checked))
            self._grid_method_group.addButton(check)
            body = QWidget(); body.setLayout(body_layout)
            body_layout.setContentsMargins(22, 0, 0, 6)
            grid_layout.addWidget(check)
            grid_layout.addWidget(body)
            self._grid_options[method] = (check, body)

        # 1. Heuristic search (P2Rank): the pocket Rank to use, its Score, and the Detect button
        self.sp_pocket_rank = QSpinBox(); self.sp_pocket_rank.setRange(1, 1); self.sp_pocket_rank.setFixedWidth(90)
        self.sp_pocket_rank.valueChanged.connect(self._on_pocket_rank_changed)
        self.ed_pocket_score = QLineEdit(); self.ed_pocket_score.setReadOnly(True); self.ed_pocket_score.setFixedWidth(150)
        self._tr("s2_tooltip_pocket_rank", self.sp_pocket_rank.setToolTip)
        self._tr("s2_tooltip_pocket_score", self.ed_pocket_score.setToolTip)
        btn_detect_pocket = QPushButton()
        self._tr("s2_btn_detect_pocket", btn_detect_pocket.setText)
        self._tr("s2_tooltip_detect_pocket", btn_detect_pocket.setToolTip)
        btn_detect_pocket.clicked.connect(self.detect_pocket_p2rank)
        heuristic_layout = QGridLayout()
        heuristic_layout.setHorizontalSpacing(10)
        heuristic_layout.setVerticalSpacing(6)
        lbl_rank = QLabel(); self._tr("s2_lbl_rank", lbl_rank.setText)
        lbl_score = QLabel(); self._tr("s2_lbl_score", lbl_score.setText)
        heuristic_layout.addWidget(lbl_rank, 0, 0)
        heuristic_layout.addWidget(self.sp_pocket_rank, 0, 1)
        heuristic_layout.addWidget(lbl_score, 1, 0)
        heuristic_layout.addWidget(self.ed_pocket_score, 1, 1)
        heuristic_layout.addWidget(btn_detect_pocket, 1, 2)
        heuristic_layout.setColumnStretch(3, 1)
        add_option("heuristic", "s2_opt_heuristic", heuristic_layout)

        # 2. Existing grid file
        self.ed_target_grid_file = QLineEdit()
        self.ed_target_grid_file.setReadOnly(True)
        existing_layout = QVBoxLayout()
        existing_layout.setSpacing(6)
        existing_layout.addWidget(self.ed_target_grid_file)
        existing_layout.addWidget(gray_button("s2_btn_choose_grid", self.select_existing_grid), 0, Qt.AlignHCenter)
        add_option("existing", "s2_opt_existing", existing_layout)

        # 3. Selected ligand (any ligand file with 3D coordinates)
        self.ed_grid_ligand_file = QLineEdit()
        self.ed_grid_ligand_file.setReadOnly(True)
        ligand_layout = QVBoxLayout()
        ligand_layout.setSpacing(6)
        ligand_layout.addWidget(self.ed_grid_ligand_file)
        ligand_layout.addWidget(gray_button("s2_btn_select_ligand", self.select_ligand_for_grid), 0, Qt.AlignHCenter)
        add_option("ligand", "s2_opt_ligand", ligand_layout)

        # 4. Co-crystal ligand: picking one in the list runs the method
        self.cb_cocrystal_ligand = QComboBox()
        self._cocrystal_ligands: list = []
        self.cb_cocrystal_ligand.activated.connect(self._apply_cocrystal_grid)
        self._tr("s2_tooltip_cocrystal_combo", self.cb_cocrystal_ligand.setToolTip)
        cocrystal_layout = QVBoxLayout()
        cocrystal_layout.addWidget(self.cb_cocrystal_ligand)
        add_option("cocrystal", "s2_opt_cocrystal", cocrystal_layout)

        # 5. Generate manually, from the numbers typed in the boxes below
        manual_layout = QVBoxLayout()
        manual_layout.addWidget(gray_button("s2_btn_generate_grid", self.generate_manual_grid), 0, Qt.AlignHCenter)
        add_option("manual", "s2_opt_manual", manual_layout)

        self.sp_center_x = QDoubleSpinBox(); self.sp_center_x.setRange(-9999.0, 9999.0); self.sp_center_x.setDecimals(3)
        self.sp_center_y = QDoubleSpinBox(); self.sp_center_y.setRange(-9999.0, 9999.0); self.sp_center_y.setDecimals(3)
        self.sp_center_z = QDoubleSpinBox(); self.sp_center_z.setRange(-9999.0, 9999.0); self.sp_center_z.setDecimals(3)
        self.sp_grid_x = QSpinBox(); self.sp_grid_x.setRange(1, 500)
        self.sp_grid_y = QSpinBox(); self.sp_grid_y.setRange(1, 500)
        self.sp_grid_z = QSpinBox(); self.sp_grid_z.setRange(1, 500)
        self.sp_spacing = QDoubleSpinBox(); self.sp_spacing.setRange(0.1, 20.0); self.sp_spacing.setDecimals(3)

        # centre (X, Y, Z) and size (X, Y, Z) as two rows of three boxes, each with its caption above it
        grid_params_grid = QGridLayout()
        grid_params_grid.setHorizontalSpacing(10)
        grid_params_grid.setVerticalSpacing(2)
        grid_param_rows = [
            (("s2_lbl_grid_center_x", self.sp_center_x), ("s2_lbl_grid_center_y", self.sp_center_y), ("s2_lbl_grid_center_z", self.sp_center_z)),
            (("s2_lbl_grid_x_size", self.sp_grid_x), ("s2_lbl_grid_y_size", self.sp_grid_y), ("s2_lbl_grid_z_size", self.sp_grid_z)),
        ]
        for block, cells in enumerate(grid_param_rows):
            for col, (label_key, spin) in enumerate(cells):
                caption = QLabel(); self._tr(label_key, caption.setText)
                grid_params_grid.addWidget(caption, block * 2, col)
                grid_params_grid.addWidget(spin, block * 2 + 1, col)
            grid_params_grid.setRowMinimumHeight(block * 2 + 2, 6)
        grid_layout.addLayout(grid_params_grid)
        lbl_grid_spacing = QLabel(); self._tr("s2_lbl_grid_spacing", lbl_grid_spacing.setText)
        grid_layout.addWidget(lbl_grid_spacing)
        grid_layout.addWidget(self.sp_spacing)
        grid_layout.addStretch(1)

        target_row = QHBoxLayout()
        target_row.setSpacing(14)
        for group in (target_box, grid_box):
            group.setFixedWidth((targets_group_width - 14) // 2)       # exactly half of the 1000 px each
            target_row.addWidget(group)
        target_wrap = QWidget(); target_wrap.setLayout(target_row)
        add_centered_group(target_wrap)

        btn_prepare = QPushButton()
        self._tr("s2_btn_prepare_target", btn_prepare.setText)
        btn_prepare.setFixedWidth(180)
        btn_prepare.clicked.connect(self.prepare_target)
        layout.addWidget(btn_prepare, alignment=Qt.AlignCenter)

        self._pockets: list = []
        self._grid_applied: set[str] = set()      # grid methods that have already filled the boxes

        manage_box = QGroupBox()
        self._tr("s2_grp_prepared_targets", manage_box.setTitle)
        manage_layout = QVBoxLayout(manage_box)
        manage_row = QHBoxLayout()
        self.cb_prepared_targets = QComboBox()
        self.cb_prepared_targets.setMaximumWidth(200)
        btn_refresh_targets = QPushButton()
        self._tr("s2_btn_refresh_targets", btn_refresh_targets.setText)
        btn_refresh_targets.setFixedWidth(170)
        btn_refresh_targets.setStyleSheet(_SS_BTN_SECONDARY)
        btn_refresh_targets.clicked.connect(self._populate_prepared_targets)
        btn_open_target = QPushButton()
        self._tr("s2_btn_open_target", btn_open_target.setText)
        btn_open_target.setFixedWidth(170)
        btn_open_target.setStyleSheet(_SS_BTN_SECONDARY)
        btn_open_target.clicked.connect(self._open_selected_target_folder)
        btn_remove_target = QPushButton()
        self._tr("s2_btn_remove_target", btn_remove_target.setText)
        btn_remove_target.setFixedWidth(170)
        btn_remove_target.setStyleSheet(_SS_BTN_SECONDARY)
        btn_remove_target.clicked.connect(self._remove_selected_target)
        manage_row.addWidget(self.cb_prepared_targets)
        manage_row.addWidget(btn_refresh_targets)
        manage_row.addWidget(btn_open_target)
        manage_row.addWidget(btn_remove_target)
        manage_layout.addLayout(manage_row)
        add_centered_group(manage_box)

        self.txt_targets = QPlainTextEdit()
        self.txt_targets.setReadOnly(True)
        self.txt_targets.setFixedHeight(220)
        add_centered_group(self.txt_targets)
        layout.addStretch(1)
        layout.addLayout(self._nav_buttons_row(2, 4))
        step3_tab_index = self.tabs.addTab(tab, "")
        self._tr("tab_step2", lambda txt, i=step3_tab_index: self.tabs.setTabText(i, txt))
        self._refresh_targets_summary()
        self._populate_prepared_targets()
        # preselected: 1. Rigid Docking and 1. Heuristic Search
        self.chk_target_rigid.setChecked(True)
        self._grid_options["heuristic"][0].setChecked(True)
        self._sync_target_modes()
        self._sync_grid_methods("heuristic", True)

    def _build_docking_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(self._title("title_step3"))

        docking_group_width = 1000

        def add_centered_group(widget: QWidget, group_width: int = docking_group_width) -> None:
            widget.setMinimumWidth(group_width)
            widget.setMaximumWidth(group_width)
            row_wrap = QHBoxLayout()
            row_wrap.addStretch(1)
            row_wrap.addWidget(widget)
            row_wrap.addStretch(1)
            layout.addLayout(row_wrap)

        # Docking parameters (left of the monitor): everything DockingWorker needs besides the
        # CONFIG performance options; nothing in STEP 1 or STEP 2 depends on them.
        settings_box = QGroupBox()
        self._tr("s3_grp_params", settings_box.setTitle)
        settings_form = QFormLayout(settings_box)
        settings_form.setHorizontalSpacing(18)
        settings_form.setVerticalSpacing(8)
        settings_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.cb_scoring = QComboBox()
        self.cb_scoring.addItems(["vina", "ad4", "vinardo"])
        self.cb_split = QComboBox()
        self.cb_split.addItems(["no", "yes"])
        self.sp_exhaustiveness = QSpinBox(); self.sp_exhaustiveness.setRange(1, 32768)
        self.sp_poses = QSpinBox(); self.sp_poses.setRange(1, 100)
        self.sp_min_rmsd = QDoubleSpinBox(); self.sp_min_rmsd.setRange(0.0, 100.0); self.sp_min_rmsd.setDecimals(3)
        self.sp_energy = QDoubleSpinBox(); self.sp_energy.setRange(0.0, 100.0); self.sp_energy.setDecimals(3)
        self.cb_docking_type = QComboBox(); self.cb_docking_type.addItems(["Rigid", "Flexible"])
        self.cb_docking_mode = QComboBox(); self.cb_docking_mode.addItems(["normal", "score_only", "local_only"])
        for key, widget in (
            ("s3_lbl_scoring_function", self.cb_scoring),
            ("s3_lbl_docking_type", self.cb_docking_type),
            ("s3_lbl_vina_mode", self.cb_docking_mode),
            ("s3_lbl_exhaustiveness", self.sp_exhaustiveness),
            ("s3_lbl_poses", self.sp_poses),
            ("s3_lbl_energy_range", self.sp_energy),
            ("s3_lbl_min_rmsd", self.sp_min_rmsd),
            ("s3_lbl_split_results", self.cb_split),
        ):
            label = QLabel(); self._tr(key, label.setText)
            settings_form.addRow(label, widget)
        self._toggle_docking_mode_options()

        monitor_group = QGroupBox()
        self._tr("s3_grp_monitor", monitor_group.setTitle)
        monitor_group.setMinimumWidth(480)
        monitor_group.setMaximumWidth(480)
        monitor_layout = QVBoxLayout(monitor_group)

        interval_row = QHBoxLayout()
        lbl_update_interval = QLabel(); self._tr("s3_lbl_update_interval", lbl_update_interval.setText)
        interval_row.addWidget(lbl_update_interval)
        self.cb_monitor_interval = QComboBox()
        for seconds in (1, 2, 5, 10, 15, 30, 60):
            self.cb_monitor_interval.addItem(f"{seconds} s", seconds)
        self.cb_monitor_interval.setCurrentIndex(2)
        self.cb_monitor_interval.currentIndexChanged.connect(self._update_monitor_interval)
        interval_row.addWidget(self.cb_monitor_interval)
        interval_row.addStretch(1)
        monitor_layout.addLayout(interval_row)

        monitor_form = QFormLayout()
        self.lbl_monitor_docked = QLabel("-")
        self.lbl_monitor_total = QLabel("-")
        self.lbl_monitor_percent = QLabel("-")
        self.lbl_monitor_eta = QLabel("-")
        self.lbl_monitor_running_time = QLabel("-")
        self.lbl_monitor_completion = QLabel("-")
        lbl_docked = QLabel(); self._tr("s3_lbl_docked", lbl_docked.setText)
        monitor_form.addRow(lbl_docked, self.lbl_monitor_docked)
        lbl_total = QLabel(); self._tr("s3_lbl_total", lbl_total.setText)
        monitor_form.addRow(lbl_total, self.lbl_monitor_total)
        lbl_percent = QLabel(); self._tr("s3_lbl_percent", lbl_percent.setText)
        monitor_form.addRow(lbl_percent, self.lbl_monitor_percent)
        lbl_eta = QLabel(); self._tr("s3_lbl_eta", lbl_eta.setText)
        monitor_form.addRow(lbl_eta, self.lbl_monitor_eta)
        lbl_running_time = QLabel(); self._tr("s3_lbl_running_time", lbl_running_time.setText)
        monitor_form.addRow(lbl_running_time, self.lbl_monitor_running_time)
        lbl_completion = QLabel(); self._tr("s3_lbl_completion", lbl_completion.setText)
        monitor_form.addRow(lbl_completion, self.lbl_monitor_completion)
        monitor_layout.addLayout(monitor_form)

        btn_run = QPushButton()
        self._tr("s3_btn_run_docking", btn_run.setText)
        btn_run.setFixedWidth(180)
        btn_run.clicked.connect(self.run_docking)

        self.monitor_timer = QTimer(self)
        self.monitor_timer.timeout.connect(self._refresh_docking_monitor)

        params_row = QHBoxLayout()
        params_row.setContentsMargins(0, 0, 0, 0)
        params_row.setSpacing(14)
        params_row.addWidget(settings_box, 1, Qt.AlignTop)
        # Run docking sits outside the monitor group, centred right below it
        monitor_column = QVBoxLayout()
        monitor_column.setSpacing(10)
        monitor_column.addWidget(monitor_group)
        monitor_column.addWidget(btn_run, 0, Qt.AlignHCenter)
        monitor_column.addStretch(1)
        params_row.addLayout(monitor_column, 0)
        params_wrap = QWidget()
        params_wrap.setLayout(params_row)
        add_centered_group(params_wrap)

        self.pb_docking = QProgressBar()
        self.pb_docking.setValue(0)
        add_centered_group(self.pb_docking)
        self.txt_docking_log = QPlainTextEdit()
        self.txt_docking_log.setReadOnly(True)
        self.txt_docking_log.setFixedHeight(220)
        add_centered_group(self.txt_docking_log)
        layout.addStretch(1)
        layout.addLayout(self._nav_buttons_row(3, 5))
        step4_tab_index = self.tabs.addTab(tab, "")
        self._tr("tab_step3", lambda txt, i=step4_tab_index: self.tabs.setTabText(i, txt))
        self._refresh_result_selectors()

    def _build_results_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(self._title("title_step4"))

        results_group_width = 1000

        def add_centered_group(widget: QWidget, group_width: int = results_group_width) -> None:
            widget.setMinimumWidth(group_width)
            widget.setMaximumWidth(group_width)
            row_wrap = QHBoxLayout()
            row_wrap.addStretch(1)
            row_wrap.addWidget(widget)
            row_wrap.addStretch(1)
            layout.addLayout(row_wrap)

        filters_box = QGroupBox()
        self._tr("s4_grp_filters", filters_box.setTitle)
        filters_form = QFormLayout(filters_box)
        self.sp_result_top_n = QSpinBox(); self.sp_result_top_n.setRange(1, 100000)
        self.sp_result_rmsd = QDoubleSpinBox(); self.sp_result_rmsd.setRange(0.0, 1000.0); self.sp_result_rmsd.setDecimals(4)
        lbl_top_ligands = QLabel(); self._tr("s4_lbl_top_ligands", lbl_top_ligands.setText)
        filters_form.addRow(lbl_top_ligands, self.sp_result_top_n)
        lbl_rmsd_threshold = QLabel(); self._tr("s4_lbl_rmsd_threshold", lbl_rmsd_threshold.setText)
        filters_form.addRow(lbl_rmsd_threshold, self.sp_result_rmsd)
        add_centered_group(filters_box)

        controls_box = QGroupBox()
        self._tr("s4_grp_controls", controls_box.setTitle)
        controls_layout = QVBoxLayout(controls_box)
        selectors_row = QHBoxLayout()
        self.lbl_results_project = QLabel()
        self.lbl_results_project.setStyleSheet("font-weight:bold;color:#29B6D8;")
        self.cb_results_target = QComboBox()
        self.cb_results_target.setMaximumWidth(260)
        self.cb_results_databank = QComboBox()
        self.cb_results_databank.setMaximumWidth(260)
        btn_refresh = QPushButton()
        self._tr("s4_btn_refresh", btn_refresh.setText)
        btn_refresh.setFixedWidth(255)
        btn_refresh.clicked.connect(self._refresh_result_selectors)
        btn_open = QPushButton()
        self._tr("s4_btn_open_result_folder", btn_open.setText)
        btn_open.setFixedWidth(255)
        btn_open.clicked.connect(self._open_current_result_folder)
        btn_load = QPushButton()
        self._tr("s4_btn_load_raw_csv", btn_load.setText)
        btn_load.setFixedWidth(255)
        btn_load.clicked.connect(self.preview_selected_result)
        btn_filtered = QPushButton()
        self._tr("s4_btn_load_filtered", btn_filtered.setText)
        btn_filtered.setFixedWidth(255)
        btn_filtered.clicked.connect(self.preview_filtered_result)
        btn_export = QPushButton()
        self._tr("s4_btn_export_csv", btn_export.setText)
        btn_export.setFixedWidth(255)
        btn_export.clicked.connect(self.export_filtered_result)
        btn_plot = QPushButton()
        self._tr("s4_btn_plot_filtered", btn_plot.setText)
        btn_plot.setFixedWidth(255)
        btn_plot.clicked.connect(self.plot_filtered_result)
        selectors_row.addStretch(1)
        selectors_row.addWidget(self.lbl_results_project)
        selectors_row.addWidget(self.cb_results_target)
        selectors_row.addWidget(self.cb_results_databank)
        selectors_row.addStretch(1)
        controls_layout.addLayout(selectors_row)

        buttons_grid = QGridLayout()
        buttons_grid.setHorizontalSpacing(12)
        buttons_grid.setVerticalSpacing(10)
        buttons_grid.setAlignment(Qt.AlignCenter)
        btn_redock = QPushButton()
        self._tr("s4_btn_redock_rmsd", btn_redock.setText)
        self._tr("s4_tooltip_redock_rmsd", btn_redock.setToolTip)
        btn_redock.setFixedWidth(255)
        btn_redock.clicked.connect(self.compute_redocking_rmsd)
        result_buttons = [
            btn_refresh,
            btn_open,
            btn_load,
            btn_filtered,
            btn_export,
            btn_plot,
            btn_redock,
        ]
        for idx, button in enumerate(result_buttons):
            buttons_grid.addWidget(button, idx // 3, idx % 3)
        controls_layout.addLayout(buttons_grid)
        add_centered_group(controls_box)

        self.tbl_results = QTableWidget()
        self.tbl_results.setFixedHeight(500)
        add_centered_group(self.tbl_results)

        btn_report = QPushButton()
        self._tr("s4_btn_generate_report", btn_report.setText)
        btn_report.setFixedWidth(255)
        btn_report.clicked.connect(self.generate_final_report)
        layout.addWidget(btn_report, alignment=Qt.AlignCenter)

        layout.addStretch(1)
        layout.addLayout(self._nav_buttons_row(4, None))
        step5_tab_index = self.tabs.addTab(tab, "")
        self._tr("tab_step4", lambda txt, i=step5_tab_index: self.tabs.setTabText(i, txt))
        self._refresh_result_selectors()

    def _path_row(self, editor: QLineEdit, callback) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(editor)
        button = QPushButton()
        self._tr("btn_browse", button.setText)
        button.clicked.connect(callback)
        layout.addWidget(button)
        return widget

    def _browse_directory(self, current: str) -> Optional[str]:
        path = QFileDialog.getExistingDirectory(self, "Select directory", current)
        return path or None

    def _browse_ligand_sources(self) -> None:
        """STEP 1 > Ligands > Browse: opens the BASE folder so the user can pick one or more multi-ligand
        files and/or one or more folders of individual ligands, which are then copied into the project."""
        if not self._require_project():
            return
        start = self.base_dir if os.path.isdir(self.base_dir) else self.app_dir
        dialog = LigandSourcesDialog(self, self._t("s1_dlg_pick_ligands"), start)
        if dialog.exec_() != QDialog.Accepted:
            return
        picked = [path for path in dialog.selectedFiles() if os.path.exists(path)]
        if not picked:
            return
        known = list(self.ligand_settings.ligand_sources)
        self.ligand_settings.ligand_sources = known + [path for path in picked if path not in known]
        self.ed_ligands.setText("; ".join(self.ligand_settings.ligand_sources))
        self.ed_ligands.setToolTip("\n".join(self.ligand_settings.ligand_sources))
        self._run_ligand_tool("import_ligands", sources=picked)

    @staticmethod
    def _opencl_device_score(device: dict[str, Any]) -> tuple[int, int, int, int]:
        device_type = str(device.get("device_type", "")).upper()
        type_score = 2 if "GPU" in device_type else 1 if "ACCELERATOR" in device_type else 0
        return (
            type_score,
            int(device.get("memory_bytes", 0)),
            int(device.get("compute_units", 0)),
            int(device.get("clock_mhz", 0)),
        )

    def _load_opencl_choices(self) -> None:
        if not hasattr(self, "cb_opencl_platform") or not hasattr(self, "cb_opencl_device"):
            return
        devices = detect_opencl_devices()
        gpu_devices = [device for device in devices if "GPU" in str(device.get("device_type", "")).upper()]
        self._opencl_devices = gpu_devices or devices
        self._opencl_platform_map: dict[int, list[dict[str, Any]]] = {}
        for device in self._opencl_devices:
            platform_id = int(device.get("platform_id", -1))
            self._opencl_platform_map.setdefault(platform_id, []).append(device)

        self.cb_opencl_platform.blockSignals(True)
        self.cb_opencl_platform.clear()
        if not self._opencl_platform_map:
            self.cb_opencl_platform.addItem("No OpenCL devices detected", -1)
            self.cb_opencl_device.clear()
            self.cb_opencl_device.addItem("No OpenCL devices detected", -1)
            self.cb_opencl_platform.setEnabled(False)
            self.cb_opencl_device.setEnabled(False)
            self.cb_opencl_platform.blockSignals(False)
            return

        self.cb_opencl_platform.setEnabled(True)
        self.cb_opencl_device.setEnabled(True)
        sorted_platform_ids = sorted(self._opencl_platform_map)
        best_device = max(self._opencl_devices, key=self._opencl_device_score)
        self._default_opencl_platform_id = int(best_device.get("platform_id", -1))
        self._default_opencl_device_id = int(best_device.get("device_id", -1))
        for platform_id in sorted_platform_ids:
            platform_name = self._opencl_platform_map[platform_id][0].get("platform_name", f"Platform {platform_id}")
            self.cb_opencl_platform.addItem(f"P{platform_id}: {platform_name}", platform_id)
        preferred_platform_id = self.settings.opencl_platform_id if self.settings.opencl_platform_id in self._opencl_platform_map else self._default_opencl_platform_id
        index = self.cb_opencl_platform.findData(preferred_platform_id)
        self.cb_opencl_platform.setCurrentIndex(index if index >= 0 else 0)
        self.cb_opencl_platform.blockSignals(False)
        self._update_opencl_device_choices()

    def _update_opencl_device_choices(self) -> None:
        if not hasattr(self, "cb_opencl_platform") or not hasattr(self, "cb_opencl_device"):
            return
        platform_id = self.cb_opencl_platform.currentData()
        devices = list(self._opencl_platform_map.get(int(platform_id), [])) if hasattr(self, "_opencl_platform_map") and platform_id is not None else []
        self.cb_opencl_device.blockSignals(True)
        self.cb_opencl_device.clear()
        if not devices:
            self.cb_opencl_device.addItem("No OpenCL devices detected", -1)
            self.cb_opencl_device.setEnabled(False)
            self.cb_opencl_device.blockSignals(False)
            return

        self.cb_opencl_device.setEnabled(True)
        for device in devices:
            memory_bytes = int(device.get("memory_bytes", 0))
            memory_gb = memory_bytes / 1073741824 if memory_bytes else 0.0
            label = (
                f"D{device['device_id']}: {device['device_name']} "
                f"[{device.get('device_type', 'Unknown')}, {memory_gb:.1f} GB, "
                f"{int(device.get('compute_units', 0))} CU, {int(device.get('clock_mhz', 0))} MHz]"
            )
            self.cb_opencl_device.addItem(label, int(device.get("device_id", -1)))
        best_device = max(devices, key=self._opencl_device_score)
        preferred_device_id = self.settings.opencl_device_id if any(int(device.get("device_id", -1)) == self.settings.opencl_device_id for device in devices) else int(best_device.get("device_id", -1))
        index = self.cb_opencl_device.findData(preferred_device_id)
        self.cb_opencl_device.setCurrentIndex(index if index >= 0 else 0)
        self.cb_opencl_device.blockSignals(False)

    # (i18n key of the stage, counter) - the Monitor table of STEP 1, in this order.
    _LIGAND_MONITOR_ROWS = (
        ("s1_mon_groups", "groups"),
        ("s1_mon_multimodels", "multimodels"),
        ("s1_mon_splitted", "splitted"),
        ("s1_mon_empty", "empty"),
        ("s1_mon_converted", "converted"),
        ("s1_mon_rejected", "rejected"),
        ("s1_mon_recovered", "recovered"),
    )

    @staticmethod
    def _walk_file_names(folder: str):
        """Names of every file under `folder`, whatever the depth (nothing if it does not exist)."""
        for _dirpath, _dirnames, filenames in os.walk(folder):
            yield from filenames

    def _ligand_monitor_counts(self) -> dict[str, int]:
        """Ligands at each stage of the open project, totalled over ALL group folders of CONVERSION/LIGANDS
        (every folder is a databank, or a piece of one that exceeded "Max ligands/folder"):

        groups       folders in LIGANDS (RECOVERED is not a group)
        multimodels  multi-ligand files loose in LIGANDS, waiting for "Split multimodel files"
        splitted     single-ligand files in the groups, not converted yet
        empty        files moved to EMPTY_LIGANDS (smaller than "Minimum file size")
        converted    .pdbqt files in the groups
        rejected     files in CONVERSION_FAILURES
        recovered    files in LIGANDS/RECOVERED"""
        counts = dict.fromkeys((counter for _key, counter in self._LIGAND_MONITOR_ROWS), 0)
        ligands_dir = self.ligands_dir
        if os.path.isdir(ligands_dir):
            with os.scandir(ligands_dir) as entries:
                for entry in entries:
                    if entry.is_file():
                        counts["multimodels"] += 1
                    elif entry.name == "RECOVERED":
                        counts["recovered"] += sum(1 for _ in self._walk_file_names(entry.path))
                    elif entry.is_dir():
                        counts["groups"] += 1
                        for name in self._walk_file_names(entry.path):
                            counts["converted" if name.lower().endswith(".pdbqt") else "splitted"] += 1
        counts["empty"] = sum(1 for _ in self._walk_file_names(os.path.join(self.conversion_dir, "EMPTY_LIGANDS")))
        counts["rejected"] = sum(1 for _ in self._walk_file_names(os.path.join(self.conversion_dir, "CONVERSION_FAILURES")))
        return counts

    def _refresh_ligand_monitor(self) -> None:
        if not hasattr(self, "tbl_lig_monitor"):
            return
        counts = self._ligand_monitor_counts() if self.project.is_open else {}
        for row_idx, (_label_key, counter) in enumerate(self._LIGAND_MONITOR_ROWS):
            self.tbl_lig_monitor.item(row_idx, 1).setText(f"{counts[counter]:,}" if counter in counts else "-")
        if counts:
            self._write_ligand_monitor_csv(counts)

    def _write_ligand_monitor_csv(self, counts: dict[str, int]) -> None:
        """Keeps CONVERSION/ligand_monitor.csv equal to the Monitor table: same rows, in the same order,
        written every time the table is refreshed (only when the numbers changed). The stage names are
        always the English ones and the quantities plain integers, whatever the interface language."""
        path = self.project.ligand_monitor_path
        rows = [[i18n.t("s1_mon_col_type", "en"), i18n.t("s1_mon_col_count", "en")]]
        rows += [[i18n.t(label_key, "en"), counts[counter]] for label_key, counter in self._LIGAND_MONITOR_ROWS]
        if getattr(self, "_ligand_monitor_csv_last", None) == (path, rows) and os.path.isfile(path):
            return
        try:
            temp_path = path + ".tmp"
            with open(temp_path, "w", encoding="utf-8", newline="") as handle:
                csv.writer(handle).writerows(rows)
            os.replace(temp_path, path)         # a reader never sees a half-written file
            self._ligand_monitor_csv_last = (path, rows)
        except OSError:
            pass

    def _collect_ligand_settings_from_widgets(self) -> None:
        if hasattr(self, "sp_lig_file_size"):
            self.ligand_settings.min_file_size = self.sp_lig_file_size.value()
        if hasattr(self, "sp_lig_ph"):
            self.ligand_settings.ph = self.sp_lig_ph.value()
        if hasattr(self, "sp_lig_max_folder"):
            self.ligand_settings.max_ligands_per_folder = self.sp_lig_max_folder.value()
        if hasattr(self, "ed_lig_reject"):
            self.ligand_settings.rejected_elements = self.ed_lig_reject.text().strip()
        if hasattr(self, "cb_lig_conversion_engine"):
            self.ligand_settings.conversion_engine = self.cb_lig_conversion_engine.currentText().strip()
        if hasattr(self, "sp_lig_workers"):
            self.ligand_settings.conversion_workers = self.sp_lig_workers.value()
        if hasattr(self, "sp_lig_steps"):
            self.ligand_settings.minimization_steps = self.sp_lig_steps.value()
        if hasattr(self, "cb_lig_min_algorithm"):
            self.ligand_settings.minimization_algorithm = self.cb_lig_min_algorithm.currentText().strip()
        if hasattr(self, "cb_lig_min_forcefield"):
            self.ligand_settings.minimization_forcefield = self.cb_lig_min_forcefield.currentText().strip()
        if hasattr(self, "sp_lig_mw_min"):
            self.ligand_settings.mw_min = self.sp_lig_mw_min.value()
        if hasattr(self, "sp_lig_mw_max"):
            self.ligand_settings.mw_max = self.sp_lig_mw_max.value()
        if hasattr(self, "sp_lig_logp_min"):
            self.ligand_settings.logp_min = self.sp_lig_logp_min.value()
        if hasattr(self, "sp_lig_logp_max"):
            self.ligand_settings.logp_max = self.sp_lig_logp_max.value()
        if hasattr(self, "sp_lig_rot"):
            self.ligand_settings.rotatable_bonds_max = self.sp_lig_rot.value()
        if hasattr(self, "sp_lig_hd"):
            self.ligand_settings.h_donor_max = self.sp_lig_hd.value()
        if hasattr(self, "sp_lig_ha"):
            self.ligand_settings.h_acceptor_max = self.sp_lig_ha.value()
        if hasattr(self, "sp_lig_tpsa"):
            self.ligand_settings.tpsa_max = self.sp_lig_tpsa.value()
        if hasattr(self, "chk_lig_drug"):
            self.ligand_settings.druggability_enabled = {key: check.isChecked() for key, check in self.chk_lig_drug.items()}

    def _apply_ligand_settings_to_widgets(self) -> None:
        if hasattr(self, "ed_ligands"):
            self.ed_ligands.setText("; ".join(self.ligand_settings.ligand_sources))
            self.ed_ligands.setToolTip(
                "\n".join(self.ligand_settings.ligand_sources) or self._t("s1_tip_ligands")
            )
        if hasattr(self, "sp_lig_file_size"):
            self.sp_lig_file_size.setValue(self.ligand_settings.min_file_size)
        if hasattr(self, "sp_lig_ph"):
            self.sp_lig_ph.setValue(self.ligand_settings.ph)
        if hasattr(self, "sp_lig_max_folder"):
            self.sp_lig_max_folder.setValue(self.ligand_settings.max_ligands_per_folder)
        if hasattr(self, "ed_lig_reject"):
            self.ed_lig_reject.setText(self.ligand_settings.rejected_elements)
        if hasattr(self, "cb_lig_conversion_engine"):
            self.cb_lig_conversion_engine.setCurrentText(self.ligand_settings.conversion_engine)
            self._sync_lig_conversion_settings_state()
        if hasattr(self, "sp_lig_workers"):
            self.sp_lig_workers.setValue(self.ligand_settings.conversion_workers)
        if hasattr(self, "sp_lig_steps"):
            self.sp_lig_steps.setValue(self.ligand_settings.minimization_steps)
        if hasattr(self, "cb_lig_min_algorithm"):
            self.cb_lig_min_algorithm.setCurrentText(self.ligand_settings.minimization_algorithm)
        if hasattr(self, "cb_lig_min_forcefield"):
            self.cb_lig_min_forcefield.setCurrentText(self.ligand_settings.minimization_forcefield)
        if hasattr(self, "sp_lig_mw_min"):
            self.sp_lig_mw_min.setValue(self.ligand_settings.mw_min)
        if hasattr(self, "sp_lig_mw_max"):
            self.sp_lig_mw_max.setValue(self.ligand_settings.mw_max)
        if hasattr(self, "sp_lig_logp_min"):
            self.sp_lig_logp_min.setValue(self.ligand_settings.logp_min)
        if hasattr(self, "sp_lig_logp_max"):
            self.sp_lig_logp_max.setValue(self.ligand_settings.logp_max)
        if hasattr(self, "sp_lig_rot"):
            self.sp_lig_rot.setValue(self.ligand_settings.rotatable_bonds_max)
        if hasattr(self, "sp_lig_hd"):
            self.sp_lig_hd.setValue(self.ligand_settings.h_donor_max)
        if hasattr(self, "sp_lig_ha"):
            self.sp_lig_ha.setValue(self.ligand_settings.h_acceptor_max)
        if hasattr(self, "sp_lig_tpsa"):
            self.sp_lig_tpsa.setValue(self.ligand_settings.tpsa_max)
        if hasattr(self, "chk_lig_drug"):
            for key, check in self.chk_lig_drug.items():
                check.setChecked(self.ligand_settings.druggability_enabled.get(key, True))

    def _collect_result_settings_from_widgets(self) -> None:
        if hasattr(self, "sp_result_top_n"):
            self.result_view_settings.top_results = self.sp_result_top_n.value()
        if hasattr(self, "sp_result_rmsd"):
            self.result_view_settings.rmsd_limit = self.sp_result_rmsd.value()

    def _apply_result_settings_to_widgets(self) -> None:
        if hasattr(self, "sp_result_top_n"):
            self.sp_result_top_n.setValue(self.result_view_settings.top_results)
        if hasattr(self, "sp_result_rmsd"):
            self.sp_result_rmsd.setValue(self.result_view_settings.rmsd_limit)

    def _run_ligand_tool(self, operation: str, sources: Optional[list[str]] = None) -> None:
        if not self._require_project():
            return
        self._save_settings()
        self.pb_ligand.setValue(0)
        self.txt_ligand_log.clear()
        self._ligand_tool_operation = operation
        self._ligand_tool_conversion_dir = self.conversion_dir
        self.ligand_worker = LigandToolsWorker(
            app_dir=self.app_dir,
            ligands_dir=self.ligands_dir,
            conversion_dir=self.conversion_dir,
            settings=self.ligand_settings,
            operation=operation,
            sources=sources,
        )
        self.ligand_worker.progress_value.connect(self.pb_ligand.setValue)
        self.ligand_worker.progress_text.connect(self.txt_ligand_log.appendPlainText)
        self.ligand_worker.finished_ok.connect(self._on_ligand_tool_finished)
        self.ligand_worker.failed.connect(self._on_ligand_tool_failed)
        self.ligand_worker.start()
        self.ligand_monitor_timer.start()

    def _log_ligand_action(self, conversion_dir: str, operation: str) -> None:
        """Append a record of a successfully completed Step 1 action, so the Final Report
        (Step 4) can later tell which conversion actions actually ran for this project."""
        try:
            os.makedirs(conversion_dir, exist_ok=True)
            with open(os.path.join(conversion_dir, "actions.log"), "a", encoding="utf-8") as handle:
                handle.write(f"{datetime.now().isoformat(timespec='seconds')}\t{operation}\tOK\n")
        except OSError:
            pass

    def _on_ligand_tool_finished(self, message: str) -> None:
        self.pb_ligand.setValue(100)
        self.txt_ligand_log.appendPlainText(message)
        # importing is not one of the conversion actions the Final Report lists
        if getattr(self, "_ligand_tool_operation", "import_ligands") != "import_ligands" and hasattr(self, "_ligand_tool_conversion_dir"):
            self._log_ligand_action(self._ligand_tool_conversion_dir, self._ligand_tool_operation)
        self.ligand_monitor_timer.stop()
        self._refresh_ligand_monitor()
        QMessageBox.information(self, APP_NAME, message)

    def _on_ligand_tool_failed(self, message: str) -> None:
        self.ligand_monitor_timer.stop()
        self._refresh_ligand_monitor()
        self.txt_ligand_log.appendPlainText(message)
        QMessageBox.critical(self, APP_NAME, message)

    def _refresh_targets_summary(self) -> None:
        if not hasattr(self, "txt_targets"):
            return
        if not self.project.is_open:
            self.txt_targets.setPlainText(self._t("msg_no_project"))
            return
        lines = []
        for target in sorted(p for p in Path(self.targets_dir).glob("*/") if p.is_dir()):
            markers = []
            if (target / "protein.pdbqt").is_file():
                markers.append("rigid")
            if (target / "protein_rigid.pdbqt").is_file() and (target / "protein_flex.pdbqt").is_file():
                markers.append("flex")
            if (target / "grid.txt").is_file():
                markers.append("grid")
            lines.append(f"{target.name}: {', '.join(markers) if markers else 'missing prepared files'}")
        self.txt_targets.setPlainText("\n".join(lines) if lines else f"No prepared targets found in {self.targets_dir}.")

    def _choose_target_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select target file",
            self.base_dir,
            "Structure files (*.pdb *.pdbqt *.mol2 *.ent *.txt);;All files (*)",
        )
        if file_path:
            self.ed_target_file.setText(file_path)

    def _choose_pdbqt_file(self, editor: QLineEdit, title: str) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            title,
            self.base_dir,
            "PDBQT files (*.pdbqt);;All files (*)",
        )
        if file_path:
            editor.setText(file_path)

    def _target_mode(self) -> str:
        """'rigid' or 'flexible': whichever of the two Target Parameters checkboxes is ticked."""
        return next(mode for mode, (check, _widgets) in self._target_modes.items() if check.isChecked())

    def _flexible_mode(self) -> bool:
        return self.chk_target_flexible.isChecked()

    def _sync_target_modes(self) -> None:
        """Only the ticked mode keeps its fields enabled; both checkboxes stay clickable (ticking one unticks the other)."""
        for check, widgets in self._target_modes.values():
            for widget in widgets:
                widget.setEnabled(check.isChecked())
        self._on_target_structure_changed()

    def _populate_prepared_targets(self) -> None:
        if not hasattr(self, "cb_prepared_targets"):
            return
        current = self.cb_prepared_targets.currentText().strip()
        self.cb_prepared_targets.blockSignals(True)
        self.cb_prepared_targets.clear()
        targets = [path.name for path in sorted(Path(self.targets_dir).glob("*/")) if path.is_dir()] if self.project.is_open else []
        self.cb_prepared_targets.addItems(targets)
        if current and current in targets:
            self.cb_prepared_targets.setCurrentText(current)
        self.cb_prepared_targets.blockSignals(False)

    def _open_selected_target_folder(self) -> None:
        target_name = self.cb_prepared_targets.currentText().strip() if hasattr(self, "cb_prepared_targets") else ""
        if target_name:
            self._open_path(os.path.join(self.targets_dir, target_name))

    def _remove_selected_target(self) -> None:
        if not self._require_project():
            return
        target_name = self.cb_prepared_targets.currentText().strip() if hasattr(self, "cb_prepared_targets") else ""
        if not target_name:
            QMessageBox.warning(self, APP_NAME, "Select a target to remove.")
            return
        target_dir = os.path.join(self.targets_dir, target_name)
        if not os.path.isdir(target_dir):
            QMessageBox.warning(self, APP_NAME, f"Target folder not found: {target_dir}")
            return
        answer = QMessageBox.question(
            self,
            APP_NAME,
            f"Remove target '{target_name}' and all files inside it?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        shutil.rmtree(target_dir, ignore_errors=True)
        self._refresh_targets_summary()
        self._populate_prepared_targets()
        self._refresh_result_selectors()

    def prepare_target(self) -> None:
        if not self._require_project():
            return
        mode = self._target_mode()
        method = self._checked_grid_method()
        if method not in self._grid_applied:
            QMessageBox.warning(self, APP_NAME, self._t("msg_grid_method_not_run", method=self._grid_options[method][0].text()))
            return
        self._collect_settings_from_widgets()
        flexible_mode = mode == "flexible"
        target_name_input = self.ed_target_name.text().strip()      # blank: named after the structure / rigid file

        try:
            if flexible_mode:
                rigid_file = self.ed_target_rigid_file.text().strip()
                flex_file = self.ed_target_flex_file.text().strip()
                if not rigid_file or not os.path.isfile(rigid_file):
                    QMessageBox.warning(self, APP_NAME, "Select a valid protein_rigid.pdbqt file.")
                    return
                if not flex_file or not os.path.isfile(flex_file):
                    QMessageBox.warning(self, APP_NAME, "Select a valid protein_flex.pdbqt file.")
                    return
                target_base = target_name_input or Path(rigid_file).stem.replace("protein_rigid", "").strip("_-") or "flex_target"
                target_base = self._safe_target_name(target_base)
                target_dir = os.path.join(self.targets_dir, target_base)
                os.makedirs(target_dir, exist_ok=True)
                self._copy_if_different(rigid_file, os.path.join(target_dir, "protein_rigid.pdbqt"))
                self._copy_if_different(flex_file, os.path.join(target_dir, "protein_flex.pdbqt"))
                self._write_grid_file(os.path.join(target_dir, "grid.txt"), target_base)
                QMessageBox.information(self, APP_NAME, f"Flexible target registered in {target_dir}.")
            else:
                target_file = self.ed_target_file.text().strip()
                if not target_file or not os.path.isfile(target_file):
                    QMessageBox.warning(self, APP_NAME, "Select a valid target file first.")
                    return
                target_ph = self.sp_target_ph.value() if hasattr(self, "sp_target_ph") else 7.4

                target_base = self._safe_target_name(target_name_input or Path(target_file).stem)
                target_dir = os.path.join(self.targets_dir, target_base)
                os.makedirs(target_dir, exist_ok=True)
                copied_target = os.path.join(target_dir, os.path.basename(target_file))
                self._copy_if_different(target_file, copied_target)
                protein_out = os.path.join(target_dir, "protein.pdbqt")
                self._write_grid_file(os.path.join(target_dir, "grid.txt"), target_base)

                try:
                    prep_result = prepare_receptor_with_protonation(
                        input_path=copied_target,
                        output_pdbqt_path=protein_out,
                        ph=target_ph,
                        venv_bin_dir=os.path.join(venv_paths("CODOC")["venv_dir"], "bin"),
                        log_path=os.path.join(target_dir, "protonation_log.txt"),
                    )
                except TargetPrepareError as exc:
                    QMessageBox.critical(self, APP_NAME, f"Target preparation failed:\n{exc}")
                    return

                pka_summary = summarize_pka_table(prep_result.pka_table, prep_result.ph)
                QMessageBox.information(
                    self,
                    APP_NAME,
                    f"Target prepared in {target_dir}.\n\n{pka_summary}\n\nFull PROPKA/PDB2PQR log saved to:\n{prep_result.log_path}",
                )
        except Exception as exc:
            QMessageBox.critical(self, APP_NAME, f"Target preparation failed:\n{exc}")
            return

        self._refresh_targets_summary()
        self._populate_prepared_targets()
        self._refresh_result_selectors()

    # ------------------------------------------------------------------ grid methods (STEP 2) ------------------------------------------------------------------
    def _checked_grid_method(self) -> str:
        """The grid method whose checkbox is ticked (one always is)."""
        return next(method for method, (check, _body) in self._grid_options.items() if check.isChecked())

    def _sync_grid_methods(self, method: str, checked: bool) -> None:
        """Only the ticked grid method keeps its fields enabled; all the checkboxes stay clickable."""
        for check, body in self._grid_options.values():
            body.setEnabled(check.isChecked())
        if checked and method == "cocrystal" and self.cb_cocrystal_ligand.currentIndex() >= 0:
            self._apply_cocrystal_grid()

    def _set_grid_boxes(self, center: Optional[tuple] = None, size: Optional[tuple] = None, spacing: Optional[float] = None) -> None:
        """Show a method's result in the Grid center / size / spacing boxes."""
        if center is not None:
            self.sp_center_x.setValue(center[0]); self.sp_center_y.setValue(center[1]); self.sp_center_z.setValue(center[2])
        if size is not None:
            self.sp_grid_x.setValue(int(size[0])); self.sp_grid_y.setValue(int(size[1])); self.sp_grid_z.setValue(int(size[2]))
        if spacing is not None:
            self.sp_spacing.setValue(spacing)

    def _target_structure_path(self) -> str:
        """Structure the grid methods read: the Target file, or the rigid receptor in flexible mode."""
        return (self.ed_target_rigid_file if self._flexible_mode() else self.ed_target_file).text().strip()

    def _on_target_structure_changed(self) -> None:
        """A new target structure: what was derived from the old one (P2Rank pockets, the co-crystal
        ligands) no longer applies."""
        if not hasattr(self, "_grid_applied"):
            return
        self._pockets = []
        self._grid_applied -= {"heuristic", "cocrystal"}
        self.sp_pocket_rank.setRange(1, 1)
        self.ed_pocket_score.clear()
        self._cocrystal_ligands = []
        path = self.ed_target_file.text().strip()
        if not self._flexible_mode() and os.path.isfile(path) and os.path.splitext(path)[1].lower() in (".pdb", ".ent"):
            try:
                self._cocrystal_ligands = module_cocrystal.find_cocrystal_ligands(path)
            except Exception:
                self._cocrystal_ligands = []
        for combo in (self.cb_cocrystal_ligand, self.cb_redock_ligand):
            combo.clear()
            combo.addItems([ligand.label for ligand in self._cocrystal_ligands])

    # 1. Heuristic search
    def detect_pocket_p2rank(self) -> None:
        """Run a P2Rank heuristic pocket search on the target structure; the Rank box then chooses which
        of the pockets found (best first) gives the grid center."""
        flexible_mode = self._flexible_mode()
        structure_path = self._target_structure_path()
        if not structure_path or not os.path.isfile(structure_path):
            QMessageBox.warning(
                self,
                APP_NAME,
                "Select a valid protein_rigid.pdbqt file first." if flexible_mode else "Select a valid target file first.",
            )
            return

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            pockets = detect_pockets_p2rank(structure_path, search_root=self.app_dir)
        except Exception as exc:
            QMessageBox.critical(self, APP_NAME, f"P2Rank heuristic search failed:\n{exc}")
            return
        finally:
            QApplication.restoreOverrideCursor()

        self._pockets = pockets
        self.sp_pocket_rank.blockSignals(True)
        self.sp_pocket_rank.setRange(1, len(pockets))
        self.sp_pocket_rank.setValue(1)
        self.sp_pocket_rank.blockSignals(False)
        self._apply_selected_pocket()
        QMessageBox.information(
            self,
            APP_NAME,
            f"P2Rank found {len(pockets)} pocket(s) in {os.path.basename(structure_path)}.\n\n"
            "Rank 1 is in use; change Rank to use another pocket.",
        )

    def _on_pocket_rank_changed(self) -> None:
        if self._pockets:
            self._apply_selected_pocket()

    def _apply_selected_pocket(self) -> None:
        pocket = self._pockets[self.sp_pocket_rank.value() - 1]
        self._set_grid_boxes(center=pocket.center)
        probability = f" (p={pocket.probability:.2f})" if pocket.probability is not None else ""
        self.ed_pocket_score.setText(f"{pocket.score:.2f}{probability}")
        self._grid_applied.add("heuristic")

    # 2. Existing grid file
    def select_existing_grid(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, "Select grid.txt", self.base_dir, "Grid files (*.txt);;All files (*)")
        if not file_path:
            return
        try:
            grid = _parse_grid_file(file_path)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, APP_NAME, f"Could not read {os.path.basename(file_path)}:\n{exc}")
            return
        if not {"center_x", "size_x"} <= set(grid):
            QMessageBox.warning(self, APP_NAME, f"{os.path.basename(file_path)} has no 'center' and 'npts' lines - it is not a grid.txt.")
            return
        self.ed_target_grid_file.setText(file_path)
        self._set_grid_boxes(
            center=(grid["center_x"], grid["center_y"], grid["center_z"]),
            size=(grid["size_x"], grid["size_y"], grid["size_z"]),
            spacing=grid.get("spacing"),
        )
        self._grid_applied.add("existing")

    # 3. Selected ligand
    def select_ligand_for_grid(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Ligand", self.base_dir, "Ligand files (*.pdb *.pdbqt *.sdf *.mol *.mol2 *.ent);;All files (*)"
        )
        if not file_path:
            return
        try:
            ligand = module_cocrystal.ligand_from_file(file_path)
        except Exception as exc:
            QMessageBox.warning(self, APP_NAME, str(exc))
            return
        self.ed_grid_ligand_file.setText(file_path)
        self._grid_from_ligand(ligand, os.path.basename(file_path))
        self._grid_applied.add("ligand")

    def _grid_from_ligand(self, ligand: Any, description: str) -> None:
        """Center the grid on `ligand` and size the box to enclose it (+6 A per side, min 20 A)."""
        center, size = module_cocrystal.suggest_grid(ligand)
        self._set_grid_boxes(center=center, size=size)
        QMessageBox.information(
            self,
            APP_NAME,
            f"Grid set from {description}:\n"
            f"center = ({center[0]:.3f}, {center[1]:.3f}, {center[2]:.3f})\n"
            f"size = {size[0]} x {size[1]} x {size[2]} A (ligand extent + 6 A on each side, minimum 20 A).",
        )

    # 4. Co-crystal ligand
    def _apply_cocrystal_grid(self) -> None:
        index = self.cb_cocrystal_ligand.currentIndex()
        if 0 <= index < len(self._cocrystal_ligands):
            ligand = self._cocrystal_ligands[index]
            self._grid_from_ligand(ligand, ligand.label)
            self._grid_applied.add("cocrystal")

    # 5. Generate manually
    def generate_manual_grid(self) -> None:
        sizes = (self.sp_grid_x.value(), self.sp_grid_y.value(), self.sp_grid_z.value())
        if min(sizes) <= 0 or self.sp_spacing.value() <= 0:
            QMessageBox.warning(self, APP_NAME, "Grid size and Grid spacing must be greater than zero.")
            return
        self._grid_applied.add("manual")
        QMessageBox.information(
            self,
            APP_NAME,
            f"Grid defined from the boxes:\n"
            f"center = ({self.sp_center_x.value():.3f}, {self.sp_center_y.value():.3f}, {self.sp_center_z.value():.3f})\n"
            f"size = {sizes[0]} x {sizes[1]} x {sizes[2]} A, spacing = {self.sp_spacing.value():g}.",
        )

    def export_cocrystal_ligand_for_redocking(self) -> None:
        """Send the ligand picked in the redocking list to the REDOCKING group of the project's ligands (prepared
        by STEP 1) and keep its crystal pose as reference."""
        if not self._require_project():
            return
        index = self.cb_redock_ligand.currentIndex()
        if index < 0 or index >= len(self._cocrystal_ligands):
            QMessageBox.warning(self, APP_NAME, self._t("msg_no_cocrystal_ligand"))
            return
        ligand = self._cocrystal_ligands[index]
        path = self.ed_target_file.text().strip()
        target_name_input = self.ed_target_name.text().strip()
        target_base = self._safe_target_name(target_name_input or Path(path).stem)
        ligand_name = self._safe_target_name(f"{target_base}_{ligand.resname}_{ligand.chain}{ligand.resnum}")
        template_smiles = None
        while True:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                info = module_cocrystal.export_ligand_for_redocking(
                    ligand, ligand_name, target_base, self.ligands_dir, self.project.reference_dir, template_smiles
                )
                QApplication.restoreOverrideCursor()
                break
            except module_cocrystal.BondOrderError as exc:
                QApplication.restoreOverrideCursor()
                # No RCSB template and no valid perception: let the user give the structure.
                template_smiles, accepted = QInputDialog.getText(
                    self,
                    APP_NAME,
                    f"{exc}\n\nType the SMILES of {ligand.resname} (for example from the RCSB page of the PDB entry) "
                    "to use it as the bond-order template:",
                )
                template_smiles = (template_smiles or "").strip()
                if not accepted or not template_smiles:
                    return
            except Exception as exc:
                QApplication.restoreOverrideCursor()
                if template_smiles:
                    QMessageBox.warning(self, APP_NAME, f"Could not use that SMILES for {ligand.label}:\n{exc}")
                    template_smiles = None
                    continue
                QMessageBox.critical(self, APP_NAME, f"Could not export {ligand.label} for redocking:\n{exc}")
                return
        self._refresh_ligand_monitor()
        QMessageBox.information(
            self,
            APP_NAME,
            f"{ligand.label} exported as '{ligand_name}'.\n\n"
            f"Ligand file: {info['sdf_path']}\n"
            f"Crystal pose (reference): {info['reference_path']}\n"
            f"Bond orders from: {info['method']}\nSMILES: {info['smiles']}\n\n"
            f"Next: prepare the target named '{target_base}' (Prepare target), convert the REDOCKING group in STEP 1, "
            "run the docking and use 'Redocking RMSD' in STEP 4. Note the REDOCKING group is docked against every target of the project.",
        )

    def _copy_if_different(self, src: str, dst: str) -> None:
        """Merge into an existing target folder instead of crashing when the selected source
        file already is the destination file (e.g. Target name matches the folder the picked
        file already lives in)."""
        if os.path.exists(dst) and os.path.samefile(src, dst):
            return
        shutil.copy2(src, dst)

    def _safe_target_name(self, value: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
        return cleaned.strip("._") or "target"

    def _write_grid_file(self, grid_path: str, target_name: str) -> None:
        with open(grid_path, "w", encoding="utf-8") as handle:
            handle.write(
                f"{target_name}\n"
                f"spacing\t{self.sp_spacing.value()}\n"
                f"npts\t{self.sp_grid_x.value()}\t{self.sp_grid_y.value()}\t{self.sp_grid_z.value()}\n"
                f"center\t{self.sp_center_x.value()}\t{self.sp_center_y.value()}\t{self.sp_center_z.value()}\n"
            )

    def _toggle_docking_mode_options(self) -> None:
        if not hasattr(self, "cb_processing_type") or not hasattr(self, "cb_docking_mode"):
            return
        current_mode = self.cb_docking_mode.currentText().strip() or "normal"
        processing_type = self.cb_processing_type.currentText().strip()
        allowed_modes = ["normal"] if processing_type == "GPU" else ["normal", "score_only", "local_only"]
        self.cb_docking_mode.blockSignals(True)
        self.cb_docking_mode.clear()
        self.cb_docking_mode.addItems(allowed_modes)
        self.cb_docking_mode.setCurrentText(current_mode if current_mode in allowed_modes else "normal")
        self.cb_docking_mode.blockSignals(False)

    def _sync_lig_conversion_settings_state(self) -> None:
        """Keeps the Minimization force field list honest about the selected Conversion engine:
        GAFF/Ghemical are OpenBabel-only, so RDKit does not offer them (it used to silently fall
        back to MMFF94 if one was picked). The other fields stay enabled with either engine,
        because a failed conversion is retried with the other one."""
        if not hasattr(self, "cb_lig_conversion_engine") or not hasattr(self, "cb_lig_min_forcefield"):
            return
        current_forcefield = self.cb_lig_min_forcefield.currentText().strip() or "MMFF94"
        engine = self.cb_lig_conversion_engine.currentText().strip()
        allowed_forcefields = (
            ["MMFF94", "MMFF94s", "UFF"] if engine == "RDKit" else ["GAFF", "Ghemical", "MMFF94", "MMFF94s", "UFF"]
        )
        self.cb_lig_min_forcefield.blockSignals(True)
        self.cb_lig_min_forcefield.clear()
        self.cb_lig_min_forcefield.addItems(allowed_forcefields)
        self.cb_lig_min_forcefield.setCurrentText(current_forcefield if current_forcefield in allowed_forcefields else "MMFF94")
        self.cb_lig_min_forcefield.blockSignals(False)

    def _sync_fix_macrocycles_button(self) -> None:
        """"Fix macrocycles for GPU" only matters when the Processing type (CONFIG) is GPU (macrocycle
        handling is a GPU-only Vina-GPU limitation) - grayed out/disabled otherwise."""
        if not hasattr(self, "btn_lig_fix_macrocycles") or not hasattr(self, "cb_processing_type"):
            return
        self.btn_lig_fix_macrocycles.setEnabled(self.cb_processing_type.currentText().strip() == "GPU")

    def _refresh_result_selectors(self) -> None:
        """Targets / ligand groups offered in STEP 4, read from the open project's DOCKING folder."""
        self._refresh_result_targets()
        self._refresh_result_databanks()

    def _docked_target_dirs(self) -> list[Path]:
        if not self.project.is_open or not os.path.isdir(self.docking_dir):
            return []
        return [path for path in sorted(Path(self.docking_dir).glob("*/")) if path.is_dir()]

    def _refresh_result_targets(self) -> None:
        if not hasattr(self, "cb_results_target"):
            return
        self.cb_results_target.clear()
        if not self.project.is_open:
            return
        self.cb_results_target.addItem("All targets")
        self.cb_results_target.addItems([path.name for path in self._docked_target_dirs()])

    def _refresh_result_databanks(self) -> None:
        if not hasattr(self, "cb_results_databank"):
            return
        self.cb_results_databank.clear()
        if not self.project.is_open:
            return
        databanks: set[str] = set()
        for target_dir in self._docked_target_dirs():
            for group_dir in target_dir.glob("*/"):
                if group_dir.is_dir():
                    databanks.add(group_dir.name)
        self.cb_results_databank.addItem("All ligands")
        self.cb_results_databank.addItems(sorted(databanks))

    def _open_current_result_folder(self) -> None:
        if self._require_project():
            self._open_path(self.project.path)

    def _open_path(self, path: str) -> None:
        if not path or not os.path.exists(path):
            QMessageBox.warning(self, APP_NAME, f"Path not found: {path}")
            return
        subprocess.Popen(["xdg-open", path])

    def _collect_settings_from_widgets(self) -> None:
        self.settings.scoring_function = self.cb_scoring.currentText().strip()
        if hasattr(self, "cb_docking_mode"):
            self.settings.docking_mode = self.cb_docking_mode.currentText().strip()
        if hasattr(self, "cb_docking_type"):
            self.settings.docking_type = self.cb_docking_type.currentText().strip()
        if hasattr(self, "cb_processing_type"):
            self.settings.processing_type = self.cb_processing_type.currentText().strip()
        if hasattr(self, "cb_opencl_platform"):
            platform_id = self.cb_opencl_platform.currentData()
            self.settings.opencl_platform_id = int(platform_id) if platform_id is not None else -1
        if hasattr(self, "cb_opencl_device"):
            device_id = self.cb_opencl_device.currentData()
            self.settings.opencl_device_id = int(device_id) if device_id is not None else -1
        self.settings.split_results = self.cb_split.currentText().strip() == "yes"
        self.settings.cpu_threads = self.sp_cpu_threads.value()
        self.settings.exhaustiveness = self.sp_exhaustiveness.value()
        self.settings.gpu_threads = self.sp_gpu_threads.value()
        self.settings.poses = self.sp_poses.value()
        self.settings.min_rmsd = self.sp_min_rmsd.value()
        self.settings.energy_range = self.sp_energy.value()
        self.settings.spacing = self.sp_spacing.value()
        self.settings.grid_x_size = self.sp_grid_x.value()
        self.settings.grid_y_size = self.sp_grid_y.value()
        self.settings.grid_z_size = self.sp_grid_z.value()
        self.settings.grid_x_center = self.sp_center_x.value()
        self.settings.grid_y_center = self.sp_center_y.value()
        self.settings.grid_z_center = self.sp_center_z.value()
        self.settings.target_ph = self.sp_target_ph.value()
        self._collect_ligand_settings_from_widgets()
        self._collect_target_settings_from_widgets()
        self._collect_result_settings_from_widgets()

    def _collect_target_settings_from_widgets(self) -> None:
        if hasattr(self, "chk_target_rigid"):
            self.target_settings.mode_index = 1 if self._flexible_mode() else 0
            self.target_settings.target_name = self.ed_target_name.text().strip()
            self.target_settings.target_file = self.ed_target_file.text().strip()
            self.target_settings.rigid_file = self.ed_target_rigid_file.text().strip()
            self.target_settings.flex_file = self.ed_target_flex_file.text().strip()
            self.target_settings.grid_file = self.ed_target_grid_file.text().strip()
            self.target_settings.grid_ligand_file = self.ed_grid_ligand_file.text().strip()

    def _apply_target_settings_to_widgets(self) -> None:
        if hasattr(self, "chk_target_rigid"):
            (self.chk_target_flexible if self.target_settings.mode_index == 1 else self.chk_target_rigid).setChecked(True)
            self.ed_target_name.setText(self.target_settings.target_name)
            self.ed_target_file.setText(self.target_settings.target_file)
            self.ed_target_rigid_file.setText(self.target_settings.rigid_file)
            self.ed_target_flex_file.setText(self.target_settings.flex_file)
            self.ed_target_grid_file.setText(self.target_settings.grid_file)
            self.ed_grid_ligand_file.setText(self.target_settings.grid_ligand_file)
            self._sync_target_modes()

    def _apply_settings_to_widgets(self) -> None:
        if hasattr(self, "cb_scoring"):
            self.cb_scoring.setCurrentText(self.settings.scoring_function)
        if hasattr(self, "cb_docking_type"):
            self.cb_docking_type.setCurrentText(self.settings.docking_type)
        if hasattr(self, "cb_processing_type"):
            self.cb_processing_type.setCurrentText(self.settings.processing_type)
            self._toggle_docking_mode_options()
            self._sync_fix_macrocycles_button()
        if hasattr(self, "cb_docking_mode"):
            self.cb_docking_mode.setCurrentText(self.settings.docking_mode)
        if hasattr(self, "cb_opencl_platform"):
            self._load_opencl_choices()
            index = self.cb_opencl_platform.findData(self.settings.opencl_platform_id)
            if index >= 0:
                self.cb_opencl_platform.setCurrentIndex(index)
                self._update_opencl_device_choices()
        if hasattr(self, "cb_opencl_device"):
            index = self.cb_opencl_device.findData(self.settings.opencl_device_id)
            if index >= 0:
                self.cb_opencl_device.setCurrentIndex(index)
        if hasattr(self, "cb_split"):
            self.cb_split.setCurrentText("yes" if self.settings.split_results else "no")
        if hasattr(self, "sp_cpu_threads"):
            self.sp_cpu_threads.setValue(self.settings.cpu_threads)
        if hasattr(self, "sp_exhaustiveness"):
            self.sp_exhaustiveness.setValue(self.settings.exhaustiveness)
        if hasattr(self, "sp_gpu_threads"):
            self.sp_gpu_threads.setValue(self.settings.gpu_threads)
        if hasattr(self, "sp_poses"):
            self.sp_poses.setValue(self.settings.poses)
        if hasattr(self, "sp_min_rmsd"):
            self.sp_min_rmsd.setValue(self.settings.min_rmsd)
        if hasattr(self, "sp_energy"):
            self.sp_energy.setValue(self.settings.energy_range)
        if hasattr(self, "sp_spacing"):
            self.sp_spacing.setValue(self.settings.spacing)
        if hasattr(self, "sp_grid_x"):
            self.sp_grid_x.setValue(self.settings.grid_x_size)
        if hasattr(self, "sp_grid_y"):
            self.sp_grid_y.setValue(self.settings.grid_y_size)
        if hasattr(self, "sp_grid_z"):
            self.sp_grid_z.setValue(self.settings.grid_z_size)
        if hasattr(self, "sp_center_x"):
            self.sp_center_x.setValue(self.settings.grid_x_center)
        if hasattr(self, "sp_center_y"):
            self.sp_center_y.setValue(self.settings.grid_y_center)
        if hasattr(self, "sp_center_z"):
            self.sp_center_z.setValue(self.settings.grid_z_center)
        if hasattr(self, "sp_target_ph"):
            self.sp_target_ph.setValue(self.settings.target_ph)
        self._apply_ligand_settings_to_widgets()
        self._apply_target_settings_to_widgets()
        self._apply_result_settings_to_widgets()

    @staticmethod
    def _write_json(path: str, data: dict[str, Any]) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)

    @staticmethod
    def _read_json(path: str) -> dict[str, Any]:
        if not path or not os.path.isfile(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def _save_settings(self) -> None:
        """Write the settings now on screen into the .json file of each step, inside the open project:
        CONVERSION/ligand_settings.json (STEP 1), TARGETS/target_settings.json (STEP 2),
        DOCKING/docking_settings.json (CONFIG, grid of STEP 2) and DOCKING/results_settings.json (STEP 4).
        Without an open project there is nowhere to save to and nothing is written."""
        self._collect_settings_from_widgets()
        if not self.project.is_open:
            return
        try:
            self._write_json(self.project.ligand_settings_path, asdict(self.ligand_settings))
            self._write_json(self.project.target_settings_path, asdict(self.target_settings))
            self._write_json(self.project.docking_settings_path, asdict(self.settings))
            self._write_json(self.project.results_settings_path, asdict(self.result_view_settings))
        except OSError as exc:
            QMessageBox.warning(self, APP_NAME, f"Could not save the project settings:\n{exc}")
            return
        self._refresh_ligand_monitor()
        self._refresh_targets_summary()

    def _save_settings_clicked(self) -> None:
        if self._require_project():
            self._save_settings()

    def _load_project_settings(self) -> None:
        """Load the .json file of each step from the open project into the screen. A file that does not
        exist (new project, or one made by an older version) leaves the current numbers as they are;
        what belongs to a single project - the imported ligand sources and the STEP 2 form - starts empty."""
        ligand = self._read_json(self.project.ligand_settings_path)
        docking = self._read_json(self.project.docking_settings_path)
        target = self._read_json(self.project.target_settings_path)
        results_view = self._read_json(self.project.results_settings_path)
        self.settings = DockingSettings(**{**asdict(self.settings), **_known_dataclass_kwargs(DockingSettings, docking)})
        self.ligand_settings = LigandSettings(**{**asdict(self.ligand_settings), **_known_dataclass_kwargs(LigandSettings, ligand)})
        if "ligand_sources" not in ligand:
            self.ligand_settings.ligand_sources = []
        self.target_settings = TargetSettings(**_known_dataclass_kwargs(TargetSettings, target))
        self.result_view_settings = ResultViewSettings(
            **{**asdict(self.result_view_settings), **_known_dataclass_kwargs(ResultViewSettings, results_view)}
        )
        self._apply_settings_to_widgets()

    def _reload_settings_clicked(self) -> None:
        if self._require_project():
            self._load_project_settings()

    def _docking_monitor_path(self) -> str:
        """The bundled Vina-GPU fork has drifted across builds in what it names its live
        progress file - some write ".track_progress.log" (what CODOC expects), others write
        ".track_progress" with no extension. Re-checked on every call (the monitor polls this
        repeatedly while docking runs) so it always follows whichever file is actually being
        updated right now, instead of latching onto one name at startup."""
        preferred = os.path.join(self.app_dir, ".track_progress.log")
        legacy = os.path.join(self.app_dir, ".track_progress")
        if not os.path.isfile(preferred) and os.path.isfile(legacy):
            return legacy
        return preferred

    def _update_monitor_interval(self) -> None:
        if not hasattr(self, "monitor_timer"):
            return
        seconds = self.cb_monitor_interval.currentData()
        if seconds and self.monitor_timer.isActive():
            self.monitor_timer.setInterval(int(seconds) * 1000)

    def _clear_docking_monitor_log(self) -> None:
        """Remove any leftover progress file from a previous run before starting a new one.

        Without this, _refresh_docking_monitor() would read the stale file left behind by the
        last run on its first tick (the new Vina-GPU process needs a moment before it writes
        fresh progress) and briefly show that old run's numbers - e.g. 100% complete - as if the
        docking that was just started had already finished."""
        for path in (
            os.path.join(self.app_dir, ".track_progress.log"),
            os.path.join(self.app_dir, ".track_progress"),
        ):
            try:
                os.remove(path)
            except OSError:
                pass

    def _reset_docking_monitor(self) -> None:
        for label in (
            self.lbl_monitor_docked,
            self.lbl_monitor_total,
            self.lbl_monitor_percent,
            self.lbl_monitor_eta,
            self.lbl_monitor_running_time,
            self.lbl_monitor_completion,
        ):
            label.setText("-")

    _MONITOR_LINE_PATTERNS = (
        ("lbl_monitor_docked", re.compile(r"^(\d+)\s+ligands docked")),
        ("lbl_monitor_total", re.compile(r"^(\d+)\s+total ligands")),
        ("lbl_monitor_percent", re.compile(r"^([\d.]+%)\s+complete")),
        ("lbl_monitor_eta", re.compile(r"^(\d{2}:\d{2}:\d{2})\s+ETA")),
        ("lbl_monitor_running_time", re.compile(r"^(\d{2}:\d{2}:\d{2})\s+running time")),
        ("lbl_monitor_completion", re.compile(r"^(.+?)\s*\(Estim\. completion\)")),
    )
    _MONITOR_PERCENT_RE = re.compile(r"^([\d.]+)%")

    def _refresh_docking_monitor(self) -> None:
        if self.cb_processing_type.currentText().strip() != "GPU":
            self._reset_docking_monitor()
            return
        log_path = self._docking_monitor_path()
        try:
            lines = Path(log_path).read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            return

        percent_value: Optional[float] = None
        for line in lines:
            stripped = line.strip()
            for attr_name, pattern in self._MONITOR_LINE_PATTERNS:
                match = pattern.match(stripped)
                if not match:
                    continue
                getattr(self, attr_name).setText(match.group(1))
                if attr_name == "lbl_monitor_percent":
                    percent_match = self._MONITOR_PERCENT_RE.match(match.group(1))
                    if percent_match:
                        percent_value = float(percent_match.group(1))
                break

        if percent_value is not None and hasattr(self, "worker") and self.worker.isRunning():
            self.pb_docking.setValue(max(0, min(100, int(round(percent_value)))))

    def run_docking(self) -> None:
        if not self._require_project():
            return
        self._save_settings()
        self.pb_docking.setValue(0)
        self.txt_docking_log.clear()
        self._reset_docking_monitor()
        self._clear_docking_monitor_log()
        self.worker = DockingWorker(
            app_dir=self.app_dir,
            ligands_dir=self.ligands_dir,
            targets_dir=self.targets_dir,
            results_dir=self.docking_dir,
            job_name=self.project.name,
            settings=self.settings,
            docking_type=self.cb_docking_type.currentText().strip(),
            processing_type=self.cb_processing_type.currentText().strip(),
        )
        self.worker.progress_value.connect(self.pb_docking.setValue)
        self.worker.progress_text.connect(self.txt_docking_log.appendPlainText)
        self.worker.finished_ok.connect(self._on_docking_finished)
        self.worker.failed.connect(self._on_docking_failed)
        self.worker.start()
        interval_seconds = self.cb_monitor_interval.currentData() or 5
        self.monitor_timer.start(int(interval_seconds) * 1000)

    def _on_docking_finished(self, message: str) -> None:
        self.monitor_timer.stop()
        self.pb_docking.setValue(100)
        self.txt_docking_log.appendPlainText(message)
        self._refresh_result_selectors()
        QMessageBox.information(self, APP_NAME, message)

    def _on_docking_failed(self, message: str) -> None:
        self.monitor_timer.stop()
        self.txt_docking_log.appendPlainText(message)
        QMessageBox.critical(self, APP_NAME, message)

    def preview_selected_result(self) -> None:
        result_name = self.project.name
        target_name = self.cb_results_target.currentText().strip()
        databank_name = self.cb_results_databank.currentText().strip()
        if not result_name:
            QMessageBox.warning(self, APP_NAME, self._t("msg_no_project"))
            return
        result_folder = self.docking_dir
        if not os.path.isdir(result_folder):
            QMessageBox.warning(self, APP_NAME, f"Result folder not found: {result_folder}")
            return
        try:
            csv_path = self._rebuild_result_csv(result_folder, result_name)
        except OSError as exc:
            QMessageBox.critical(self, APP_NAME, f"Failed to rebuild the result CSV:\n{exc}")
            return
        frame = self._load_result_dataframe(csv_path)
        frame = self._filter_frame_by_target(frame, target_name)
        frame = self._filter_frame_by_databank(frame, databank_name)
        self._load_frame_into_table(frame)

    def preview_filtered_result(self) -> None:
        try:
            frame, result_name, target_name = self._build_filtered_result_frame()
        except Exception as exc:
            QMessageBox.warning(self, APP_NAME, str(exc))
            return
        self._load_frame_into_table(frame)
        self.txt_docking_log.appendPlainText(
            f"Loaded filtered results for {result_name}/{target_name}: top {self.result_view_settings.top_results}, RMSD < {self.result_view_settings.rmsd_limit}."
        )

    def export_filtered_result(self) -> None:
        try:
            frame, result_name, target_name = self._build_filtered_result_frame()
        except Exception as exc:
            QMessageBox.warning(self, APP_NAME, str(exc))
            return
        target_slug = self._safe_target_name(target_name)
        default_name = os.path.join(self.docking_dir, f"{target_slug}_top{self.result_view_settings.top_results}.csv")
        save_path, _ = QFileDialog.getSaveFileName(self, "Export filtered result", default_name, "CSV (*.csv)")
        if not save_path:
            return
        frame.to_csv(save_path, index=False)
        QMessageBox.information(self, APP_NAME, f"Filtered results exported to {save_path}.")

    def plot_filtered_result(self) -> None:
        if plt is None or FigureCanvas is None or NavigationToolbar is None:
            QMessageBox.warning(self, APP_NAME, "Matplotlib is not available in the current environment.")
            return
        try:
            frame, result_name, target_name = self._build_filtered_result_frame()
        except Exception as exc:
            QMessageBox.warning(self, APP_NAME, str(exc))
            return

        columns = self._locate_result_columns(frame)
        ligand_col, target_col, energy_col, rmsd_col = columns["ligand"], columns["target"], columns["energy"], columns["rmsd"]
        if ligand_col is None or energy_col is None or rmsd_col is None:
            QMessageBox.warning(self, APP_NAME, "Could not identify ligand, energy and RMSD columns to plot.")
            return

        plot_df = frame.copy()
        plot_df[energy_col] = pd.to_numeric(plot_df[energy_col], errors="coerce")
        plot_df[rmsd_col] = pd.to_numeric(plot_df[rmsd_col], errors="coerce")
        plot_df = plot_df.dropna(subset=[ligand_col, energy_col, rmsd_col])
        if plot_df.empty:
            QMessageBox.warning(self, APP_NAME, "There are no numeric filtered rows to plot.")
            return

        if target_col is not None and plot_df[target_col].nunique() > 1:
            labels = (plot_df[ligand_col].astype(str) + " (" + plot_df[target_col].astype(str) + ")").tolist()
        else:
            labels = plot_df[ligand_col].astype(str).tolist()

        fig, ax = plt.subplots(figsize=(12, 6))
        positions = list(range(len(plot_df)))
        width = 0.42
        ax.bar([pos - width / 2 for pos in positions], plot_df[energy_col].tolist(), width=width, label="Binding Energy", color="#006680")
        ax.bar([pos + width / 2 for pos in positions], plot_df[rmsd_col].tolist(), width=width, label="RMSD", color="#E67E22")
        ax.set_title(f"Top Ligands for {target_name} ({result_name})")
        ax.set_ylabel("Binding Energy / RMSD")
        ax.set_xticks(positions)
        ax.set_xticklabels(labels, rotation=45, ha="right")
        ax.legend()
        ax.grid(False)
        fig.tight_layout()

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Filtered Results Plot - {target_name}")
        dialog_layout = QVBoxLayout(dialog)
        canvas = FigureCanvas(fig)
        toolbar = NavigationToolbar(canvas, dialog)
        dialog_layout.addWidget(toolbar)
        dialog_layout.addWidget(canvas)

        button_row = QHBoxLayout()
        btn_save = QPushButton("Save Chart")
        btn_close = QPushButton("Close")
        btn_save.clicked.connect(lambda: self._save_result_plot(fig, result_name, target_name, dialog))
        btn_close.clicked.connect(dialog.accept)
        button_row.addWidget(btn_save)
        button_row.addWidget(btn_close)
        dialog_layout.addLayout(button_row)
        dialog.resize(1100, 720)
        dialog.exec_()

    def _save_result_plot(self, fig: Any, result_name: str, target_name: str, parent: QWidget) -> None:
        target_slug = self._safe_target_name(target_name)
        default_path = os.path.join(self.docking_dir, f"{target_slug}_top{self.result_view_settings.top_results}.png")
        file_path, _ = QFileDialog.getSaveFileName(parent, "Save chart", default_path, "PNG (*.png);;SVG (*.svg);;PDF (*.pdf)")
        if not file_path:
            return
        fig.savefig(file_path, bbox_inches="tight", dpi=300)
        QMessageBox.information(self, APP_NAME, f"Chart saved to {file_path}.")

    def compute_redocking_rmsd(self) -> None:
        """Compare every docked REDOCKING ligand against its crystal pose (heavy-atom, symmetry-aware RMSD)."""
        result_name = self.project.name
        if not result_name:
            QMessageBox.warning(self, APP_NAME, self._t("msg_no_project"))
            return
        docking_dir = Path(self.docking_dir)
        if not docking_dir.is_dir():
            QMessageBox.warning(self, APP_NAME, f"Result folder not found: {docking_dir}")
            return
        if pd is None:
            QMessageBox.warning(self, APP_NAME, "Pandas is required to show the redocking results.")
            return
        target_filter = self.cb_results_target.currentText().strip()
        databank_filter = self.cb_results_databank.currentText().strip()

        rows = []
        failures = []
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            for target_dir in sorted(p for p in docking_dir.glob("*/") if p.is_dir()):
                if target_filter and target_filter != "All targets" and target_dir.name != target_filter:
                    continue
                for group_dir in sorted(p for p in target_dir.glob("*/") if p.is_dir()):
                    if databank_filter and databank_filter != "All ligands" and group_dir.name != databank_filter:
                        continue
                    for ligand_dir in sorted(p for p in group_dir.glob("*/") if p.is_dir()):
                        info = module_cocrystal.load_reference_info(self.project.reference_dir, ligand_dir.name)
                        docked = ligand_dir / f"{ligand_dir.name}.pdbqt"
                        # A reference only means something for the target it was exported for.
                        if info is None or info.get("target") != target_dir.name or not docked.is_file():
                            continue
                        energy, _rmsd_mean, _smiles = _parse_vina_pose_data(str(docked))
                        try:
                            result = module_cocrystal.compute_redock_rmsd(info["reference_path"], str(docked))
                        except Exception as exc:
                            failures.append(f"{target_dir.name}/{ligand_dir.name}: {exc}")
                            continue
                        best = result["best_pose_rmsd"]
                        rows.append({
                            "TARGET": target_dir.name,
                            "LIGAND DATABANK": group_dir.name,
                            "LIGAND": ligand_dir.name,
                            "BINDING ENERGY (Kcal/mol)": energy,
                            "BEST-POSE RMSD (A)": round(best, 3),
                            "MIN RMSD (A)": round(result["min_rmsd"], 3),
                            "MIN-RMSD POSE": result["min_rmsd_pose"],
                            "POSES": result["n_poses"],
                            "REDOCKING": "success (<= 2.0 A)" if best <= 2.0 else "failed (> 2.0 A)",
                        })
        finally:
            QApplication.restoreOverrideCursor()

        if not rows:
            detail = ("\n\nProblems:\n" + "\n".join(failures)) if failures else ""
            QMessageBox.information(
                self,
                APP_NAME,
                "No redocking results were found in this project. Export a co-crystal ligand with 'Export ligand for redocking' "
                "in STEP 2, prepare the target with the same name, convert the REDOCKING group in STEP 1 and run the docking first."
                + detail,
            )
            return
        frame = pd.DataFrame(rows)
        self._load_frame_into_table(frame)
        csv_path = docking_dir / "redocking_rmsd.csv"
        try:
            frame.to_csv(csv_path, index=False)
            saved = f"\nSaved to {csv_path}."
        except OSError:
            saved = ""
        successes = int((frame["BEST-POSE RMSD (A)"] <= 2.0).sum())
        message = f"Redocking RMSD computed for {len(rows)} ligand(s): {successes} with best pose <= 2.0 A.{saved}"
        if failures:
            message += "\n\nCould not compare:\n" + "\n".join(failures)
        self.txt_docking_log.appendPlainText(message)
        QMessageBox.information(self, APP_NAME, message)

    def generate_final_report(self) -> None:
        result_name = self.project.name
        if not result_name:
            QMessageBox.warning(self, APP_NAME, self._t("msg_no_project"))
            return
        job_dir = self.project.path
        docking_dir = self.docking_dir
        if not os.path.isdir(docking_dir):
            QMessageBox.warning(self, APP_NAME, f"Result folder not found: {docking_dir}")
            return

        self._collect_result_settings_from_widgets()
        try:
            csv_path = self._rebuild_result_csv(docking_dir, result_name)
        except OSError as exc:
            QMessageBox.critical(self, APP_NAME, f"Failed to rebuild the result CSV:\n{exc}")
            return
        frame = self._load_result_dataframe(csv_path)

        # Prefer the settings snapshot saved inside the job itself (what was actually used to
        # produce these results); fall back to the live interface state for any job created
        # before that snapshot existed.
        job_docking_settings, job_ligand_settings = load_job_settings(job_dir)
        docking_settings = {**asdict(self.settings), **job_docking_settings}
        ligand_settings = {**asdict(self.ligand_settings), **job_ligand_settings}

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            output_path = _generate_final_report_docx(
                job_dir=job_dir,
                job_name=result_name,
                ligands_dir=self.ligands_dir,
                frame=frame,
                docking_settings=docking_settings,
                ligand_settings=ligand_settings,
                top_results=self.result_view_settings.top_results,
                rmsd_limit=self.result_view_settings.rmsd_limit,
            )
        except Exception as exc:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, APP_NAME, f"Failed to generate the final report:\n{exc}")
            return
        QApplication.restoreOverrideCursor()
        QMessageBox.information(self, APP_NAME, f"Final report saved to:\n{output_path}")

    def _run_csv_path(self, result_folder: str, result_name: str) -> str:
        return os.path.join(result_folder, f"{result_name}.csv")

    def _rebuild_result_csv(self, result_folder: str, result_name: str) -> str:
        """Rescan every ligand PDBQT under a result folder and rewrite its unified CSV."""
        csv_path = self._run_csv_path(result_folder, result_name)
        with open(csv_path, "w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(RESULT_CSV_HEADER)
            for target_dir in sorted(p for p in Path(result_folder).glob("*/") if p.is_dir()):
                target_name = target_dir.name
                for group_dir in sorted(p for p in target_dir.glob("*/") if p.is_dir()):
                    ligand_group = group_dir.name
                    for ligand_dir in sorted(p for p in group_dir.glob("*/") if p.is_dir()):
                        ligand_name = ligand_dir.name
                        output_file = ligand_dir / f"{ligand_name}.pdbqt"
                        if not output_file.is_file():
                            continue
                        energy, rmsd_mean, smiles = _parse_vina_pose_data(str(output_file))
                        writer.writerow([ligand_name, smiles, ligand_group, target_name, energy, rmsd_mean])
        return csv_path

    def _locate_result_columns(self, frame: Any) -> dict[str, Optional[str]]:
        lower_map = {str(col).strip().lower(): col for col in frame.columns}

        def find(exact: str, *contains: str) -> Optional[str]:
            if exact in lower_map:
                return lower_map[exact]
            for lower_name, original in lower_map.items():
                if any(token in lower_name for token in contains):
                    return original
            return None

        return {
            "ligand": find("ligand"),
            "smiles": find("smiles"),
            "databank": find("ligand databank", "databank"),
            "target": find("target"),
            "energy": find("binding energy (kcal/mol)", "binding energy", "binding_energy"),
            "rmsd": find("rmsd (mean)", "rmsd"),
        }

    def _filter_frame_by_target(self, frame: Any, target_name: str) -> Any:
        if not target_name or target_name == "All targets":
            return frame
        target_col = self._locate_result_columns(frame)["target"]
        if target_col is None:
            return frame
        return frame[frame[target_col] == target_name].reset_index(drop=True)

    def _filter_frame_by_databank(self, frame: Any, databank_name: str) -> Any:
        if not databank_name or databank_name == "All ligands":
            return frame
        databank_col = self._locate_result_columns(frame)["databank"]
        if databank_col is None:
            return frame
        return frame[frame[databank_col] == databank_name].reset_index(drop=True)

    def _build_filtered_result_frame(self) -> tuple[Any, str, str]:
        self._collect_result_settings_from_widgets()
        result_name = self.project.name
        target_name = self.cb_results_target.currentText().strip()
        databank_name = self.cb_results_databank.currentText().strip()
        if not result_name:
            raise RuntimeError(self._t("msg_no_project"))
        csv_path = self._run_csv_path(self.docking_dir, result_name)
        if not os.path.isfile(csv_path):
            raise RuntimeError(f"Result CSV not found: {csv_path}. Click 'Load raw CSV' first.")
        frame = self._load_result_dataframe(csv_path)
        frame = self._filter_frame_by_target(frame, target_name)
        frame = self._filter_frame_by_databank(frame, databank_name)
        columns = self._locate_result_columns(frame)
        energy_col, rmsd_col = columns["energy"], columns["rmsd"]
        if energy_col is None or rmsd_col is None:
            raise RuntimeError("The result file does not contain recognizable BINDING ENERGY and RMSD columns.")
        filtered = frame.copy()
        filtered[energy_col] = pd.to_numeric(filtered[energy_col], errors="coerce")
        filtered[rmsd_col] = pd.to_numeric(filtered[rmsd_col], errors="coerce")
        filtered = filtered[filtered[rmsd_col] < self.result_view_settings.rmsd_limit]
        filtered = filtered.sort_values(by=energy_col, ascending=True).head(self.result_view_settings.top_results)
        filtered = filtered.reset_index(drop=True)
        filtered = self._add_compound_name_column(filtered, result_name)
        return filtered, result_name, target_name

    def _add_compound_name_column(self, frame: Any, result_name: str) -> Any:
        """Adds a "COMPOUND NAME" column resolved by structure (SMILES) via PubChem - see
        MODULES/module_compound_names.py. This always matches by SMILES, never by the ligand
        ID's own namespace, so it works the same regardless of which ligand databank a compound
        came from (ZINC, ChEMBL, a custom folder, ...). Best-effort: silently leaves the column
        blank if module_compound_names/RDKit is unavailable, or a compound has no PubChem match -
        a missing name must never block loading or exporting the filtered results."""
        columns = self._locate_result_columns(frame)
        ligand_col, smiles_col = columns["ligand"], columns["smiles"]
        if module_compound_names is None or pd is None or ligand_col is None or smiles_col is None or frame.empty:
            frame["COMPOUND NAME"] = ""
            return frame
        id_to_smiles = dict(zip(frame[ligand_col].astype(str), frame[smiles_col].astype(str)))
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            names = module_compound_names.resolve_compound_names(
                list(frame[ligand_col].astype(str)),
                self.docking_dir,
                id_to_smiles=id_to_smiles,
            )
        except Exception:
            names = {}
        finally:
            QApplication.restoreOverrideCursor()
        frame["COMPOUND NAME"] = frame[ligand_col].astype(str).map(names).fillna("")
        return frame

    def _load_result_dataframe(self, csv_path: str) -> Any:
        if pd is None:
            raise RuntimeError("Pandas is required to read docking results in the Python interface.")
        try:
            return pd.read_csv(csv_path)
        except Exception as exc:
            raise RuntimeError(f"Could not read {csv_path}: {exc}") from exc

    def _load_frame_into_table(self, frame: Any) -> None:
        if pd is not None and hasattr(frame, "columns"):
            headers = [str(col) for col in frame.columns]
            rows = frame.astype(str).values.tolist()
        else:
            headers = []
            rows = []
        self.tbl_results.clear()
        self.tbl_results.setColumnCount(len(headers))
        self.tbl_results.setHorizontalHeaderLabels(headers)
        self.tbl_results.setRowCount(len(rows))
        for row_idx, row in enumerate(rows[:500]):
            for col_idx, value in enumerate(row):
                self.tbl_results.setItem(row_idx, col_idx, QTableWidgetItem(str(value)))
        self.tbl_results.resizeColumnsToContents()

    def show_requirements_installer(self) -> None:
        dialog = RequirementsInstaller(app_dir=self.app_dir, parent=self)
        dialog.setWindowModality(Qt.ApplicationModal)
        self._requirements_dialog = dialog
        dialog.exec_()

    def _start_hw_monitor(self) -> None:
        self._mon_widget = QWidget()
        self._mon_widget.setStyleSheet("background:transparent;")
        layout = QHBoxLayout(self._mon_widget)
        layout.setContentsMargins(0, 0, 4, 0)
        layout.setSpacing(6)

        # Bandeiras BR/UK de selecao de idioma (mesmo padrao do CODRUG, MODULES/i18n.py) - ao
        # lado do monitor de CPU/GPU, no canto superior direito da janela principal. Usa icones
        # SVG proprios (ICONS/flag_br.svg, ICONS/flag_gb.svg) em vez de emoji de bandeira: em
        # muitos ambientes Linux/Qt o emoji de bandeira (par de "Regional Indicator Symbols") nao
        # tem glifo colorido combinado disponivel na fonte do sistema e cai no fallback textual
        # (as duas letras do codigo do pais), em vez de desenhar a bandeira.
        flag_style = (
            "QPushButton{border:none;background:transparent;padding:0;}"
            "QPushButton:hover{background:#16283B;border-radius:4px;}"
        )
        flag_icon_size = QSize(24, 16)

        self.btn_bandeira_pt = QPushButton()
        self.btn_bandeira_pt.setIcon(QIcon(os.path.join(self.app_dir, "ICONS", "flag_br.svg")))
        self.btn_bandeira_pt.setIconSize(flag_icon_size)
        self.btn_bandeira_pt.setFlat(True)
        self.btn_bandeira_pt.setFixedSize(30, 22)
        self.btn_bandeira_pt.setStyleSheet(flag_style)
        self._tr("tooltip_bandeira_pt", self.btn_bandeira_pt.setToolTip)
        self.btn_bandeira_pt.clicked.connect(lambda: self._definir_idioma("pt"))
        layout.addWidget(self.btn_bandeira_pt)

        self.btn_bandeira_en = QPushButton()
        self.btn_bandeira_en.setIcon(QIcon(os.path.join(self.app_dir, "ICONS", "flag_gb.svg")))
        self.btn_bandeira_en.setIconSize(flag_icon_size)
        self.btn_bandeira_en.setFlat(True)
        self.btn_bandeira_en.setFixedSize(30, 22)
        self.btn_bandeira_en.setStyleSheet(flag_style)
        self._tr("tooltip_bandeira_en", self.btn_bandeira_en.setToolTip)
        self.btn_bandeira_en.clicked.connect(lambda: self._definir_idioma("en"))
        layout.addWidget(self.btn_bandeira_en)

        self.lbl_cpu_top = QLabel("CPU: --", self)
        self.lbl_cpu_top.setAlignment(Qt.AlignCenter)
        self.lbl_cpu_top.setMinimumWidth(280)
        self.lbl_cpu_top.setStyleSheet(self._mon_ss("#27AE60"))
        layout.addWidget(self.lbl_cpu_top)

        self.lbl_gpu_top = QLabel("GPU: --", self)
        self.lbl_gpu_top.setAlignment(Qt.AlignCenter)
        self.lbl_gpu_top.setMinimumWidth(160)
        self.lbl_gpu_top.setStyleSheet(self._mon_ss("#2980B9"))
        self._has_nvidia = shutil.which("nvidia-smi") is not None
        self.lbl_gpu_top.setVisible(self._has_nvidia)
        layout.addWidget(self.lbl_gpu_top)

        self.menuBar().setCornerWidget(self._mon_widget, Qt.TopRightCorner)
        self.hw_timer = QTimer(self)
        self.hw_timer.setInterval(1500)
        self.hw_timer.timeout.connect(self._update_hw)
        self.hw_timer.start()
        self._update_hw()

    @staticmethod
    def _mon_ss(color: str) -> str:
        return (
            f"QLabel{{padding:2px 8px;border:2px solid {color};"
            f"border-radius:6px;background:#0D1B2A;color:{color};"
            f"font-weight:bold;font-size:9pt;}}"
        )

    @staticmethod
    def _uc(percent: float) -> str:
        return "#F57C6F" if percent > 80 else "#E67E22" if percent > 50 else "#27AE60"

    @staticmethod
    def _tc(temp_celsius: float) -> str:
        return "#F57C6F" if temp_celsius > 80 else "#E67E22" if temp_celsius > 60 else "#27AE60"

    def _update_hw(self) -> None:
        if psutil is None:
            self.lbl_cpu_top.setText("CPU monitor unavailable")
            self.lbl_cpu_top.setTextFormat(Qt.PlainText)
            self.lbl_cpu_top.setStyleSheet(self._mon_ss("#E67E22"))
        else:
            try:
                per_core = psutil.cpu_percent(interval=None, percpu=True)
                if per_core:
                    cpu_avg = sum(per_core) / len(per_core)
                    cpu_max = max(per_core)
                else:
                    cpu_avg = 0.0
                    cpu_max = 0.0

                temp_suffix = ""
                try:
                    for key in ("coretemp", "k10temp", "acpitz", "cpu_thermal"):
                        readings = psutil.sensors_temperatures().get(key)
                        if readings:
                            temp_color = self._tc(readings[0].current)
                            temp_suffix = f" <span style='color:{temp_color};'>{readings[0].current:.0f}°C</span>"
                            break
                except Exception:
                    pass

                cpu_color = self._uc(cpu_max)
                mem = psutil.virtual_memory()
                mem_used_gb = (mem.total - mem.available) / 1073741824
                mem_total_gb = mem.total / 1073741824
                mem_suffix = f"  <span style='color:#2980B9;'>{mem_used_gb:.1f}/{mem_total_gb:.1f} GB</span>"
                self.lbl_cpu_top.setText(
                    f"<span style='color:{cpu_color};'>CPU avg {cpu_avg:.0f}%</span>"
                    f"  <span style='color:{cpu_color};'>max {cpu_max:.0f}%</span>{temp_suffix}{mem_suffix}"
                )
                self.lbl_cpu_top.setTextFormat(Qt.RichText)
                self.lbl_cpu_top.setStyleSheet(self._mon_ss(cpu_color))
            except Exception:
                self.lbl_cpu_top.setText("CPU: --")
                self.lbl_cpu_top.setTextFormat(Qt.PlainText)
                self.lbl_cpu_top.setStyleSheet(self._mon_ss("#27AE60"))

        if not getattr(self, "_has_nvidia", False):
            return

        try:
            raw = subprocess.check_output(
                [
                    "nvidia-smi",
                    "--query-gpu=utilization.gpu,temperature.gpu,memory.used,memory.total",
                    "--format=csv,noheader,nounits",
                ],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=2,
            ).strip()
            first_line = raw.splitlines()[0]
            gpu_util, gpu_temp, mem_used, mem_total = [part.strip() for part in first_line.split(",")[:4]]
            gpu_util_value = float(gpu_util)
            gpu_temp_value = float(gpu_temp)
            gpu_color = self._uc(gpu_util_value)
            temp_color = self._tc(gpu_temp_value)
            self.lbl_gpu_top.setText(
                f"<span style='color:{gpu_color};'>GPU {gpu_util_value:.0f}%</span>"
                f"  <span style='color:{temp_color};'>{gpu_temp_value:.0f}°C</span>"
                f"  <span style='color:#2980B9;'>{mem_used}/{mem_total} MB</span>"
            )
            self.lbl_gpu_top.setTextFormat(Qt.RichText)
            self.lbl_gpu_top.setStyleSheet(self._mon_ss(gpu_color))
        except Exception:
            self.lbl_gpu_top.setText("GPU: --")
            self.lbl_gpu_top.setTextFormat(Qt.PlainText)
            self.lbl_gpu_top.setStyleSheet(self._mon_ss("#2980B9"))


def main() -> int:
    codoc_terminal.setup_capture()      # keeps the session output for Help > Terminal
    app = QApplication(sys.argv)
    # Ties the running window to the CODOC.desktop launcher (StartupWMClass=CODOC there matches
    # this) so the panel/window-list picks up the same icon as the menu entry, instead of relying
    # only on setWindowIcon() below - matters most on Wayland, where WM_CLASS-based icon lookup
    # from a bare X11 icon hint is unreliable.
    app.setDesktopFileName("CODOC")
    dp_dir = os.path.abspath(os.path.dirname(__file__))
    splash = SplashScreen(dp_dir)
    splash.show()

    def start_mainwindow(_status: dict) -> None:
        splash.close()
        window = MainWindow()
        window.show()
        app._main_window = window

    splash.check_complete.connect(start_mainwindow)
    QTimer.singleShot(0, splash.start_checks)
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
