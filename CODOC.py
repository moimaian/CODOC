#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pyright: reportAttributeAccessIssue=false, reportOptionalMemberAccess=false, reportMissingImports=false

from __future__ import annotations

import csv
import importlib
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
from dataclasses import asdict, dataclass
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

from PyQt5.QtCore import QThread, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QGuiApplication, QIcon, QPixmap
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QDoubleSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from MODULES.module_requirements import RequirementsInstaller, detect_hardware, detect_opencl_devices, get_boost_version, get_vina_gpu_version, venv_paths
from MODULES.module_target_prepare import TargetPrepareError, find_pdb2pqr, prepare_receptor_with_protonation, summarize_pka_table
from MODULES.splash_screen import SplashScreen

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
    color: #2ECC71;
}
QLabel {
    background: transparent;
}
QLineEdit, QComboBox, QPlainTextEdit, QTextEdit, QTableWidget, QSpinBox, QDoubleSpinBox {
    border: 1px solid #2A4A6B;
    border-radius: 4px;
    padding: 4px 8px;
    background: #1C3249;
    color: #C9D1D9;
    selection-background-color: #27AE60;
}
QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus, QTextEdit:focus, QTableWidget:focus {
    border: 2px solid #2ECC71;
}
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
QMenuBar {
    background: #0D1B2A;
    color: #C9D1D9;
    border-bottom: 1px solid #2A4A6B;
}
QMenuBar::item:selected {
    background: #1C3249;
    color: #2ECC71;
}
QMenu {
    background: #14253A;
    color: #C9D1D9;
    border: 1px solid #2A4A6B;
}
QMenu::item:selected {
    background: #1C3249;
    color: #2ECC71;
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
    color: #2ECC71;
    border-bottom: 3px solid #2ECC71;
}
QProgressBar {
    border: 1px solid #2A4A6B;
    border-radius: 4px;
    text-align: center;
    background: #1C3249;
}
QProgressBar::chunk {
    background: #1E8449;
}
"""

_SS_BTN_NAV = """
QPushButton {
    background: transparent;
    border: none;
    color: #6E8CA8;
    font-size: 12pt;
    font-weight: bold;
    padding: 4px 10px;
}
QPushButton:hover {
    color: #C9D1D9;
}
QPushButton:pressed {
    color: #2ECC71;
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
    opencl_platform_id: int = -1
    opencl_device_id: int = -1
    split_results: bool = False
    cpu_threads: int = max(1, os.cpu_count() or 1)
    cpu_parallelism: int = min(10, max(1, os.cpu_count() or 1))
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


@dataclass
class LigandSettings:
    min_file_size: int = 10
    ph: float = 7.4
    max_ligands_per_folder: int = 50000
    rejected_elements: str = "nan|As|Bi|Si|B"
    conversion_engine: str = "RDKit"
    conversion_workers: int = max(1, os.cpu_count() or 1)
    speed_first: str = "med"
    speed_second: str = "slow"
    timeout_first: int = max(10, 10 * max(1, os.cpu_count() or 1))
    timeout_second: int = max(30, 30 * max(1, os.cpu_count() or 1))
    minimization_steps: int = 1500
    mw_min: float = 0.0
    mw_max: float = 500.0
    logp_min: float = -5.0
    logp_max: float = 5.0
    rotatable_bonds_max: int = 10
    h_donor_max: int = 5
    h_acceptor_max: int = 10
    tpsa_max: float = 140.0


@dataclass
class ResultViewSettings:
    top_results: int = 20
    rmsd_limit: float = 2.0


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
        settings: DockingSettings,
        docking_type: str,
        processing_type: str,
        run_type: str,
        selected_result: str,
    ) -> None:
        super().__init__()
        self.app_dir = app_dir
        self.ligands_dir = ligands_dir
        self.targets_dir = targets_dir
        self.results_dir = results_dir
        self.settings = settings
        self.docking_type = docking_type
        self.processing_type = processing_type
        self.run_type = run_type
        self.selected_result = selected_result
        self.vina = os.path.join(app_dir, "bin", "vina_1.2.5_linux_x86_64")
        self.vina_split = os.path.join(app_dir, "bin", "vina_split_1.2.5_linux_x86_64")
        self.vina_gpu = os.path.join(str(Path.home()), "Vina-GPU-2.1", "AutoDock-Vina-GPU-2.1", "AutoDock-Vina-GPU-2-1")

    def run(self) -> None:
        try:
            self._validate_environment()
            result_folder = self._prepare_result_folder()
            pending_jobs = self._build_pending_jobs(result_folder)
            if not pending_jobs:
                self.finished_ok.emit(f"No pending docking jobs were found in {os.path.basename(result_folder)}.")
                return

            if self.processing_type == "GPU":
                self._run_gpu_jobs(result_folder, pending_jobs)
            else:
                self._run_cpu_jobs(result_folder, pending_jobs)
            self.finished_ok.emit(f"Docking finished. Results available in {result_folder}.")
        except Exception as exc:
            self.failed.emit(str(exc))

    def _validate_environment(self) -> None:
        if not os.path.isdir(self.ligands_dir):
            raise RuntimeError(f"Ligands directory not found: {self.ligands_dir}")
        if not os.path.isdir(self.targets_dir):
            raise RuntimeError(f"Targets directory not found: {self.targets_dir}")
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
        os.makedirs(self.results_dir, exist_ok=True)
        if self.run_type == "RESTART":
            if not self.selected_result:
                raise RuntimeError("Select a result folder to restart.")
            result_folder = os.path.join(self.results_dir, self.selected_result)
            if not os.path.isdir(result_folder):
                raise RuntimeError(f"Result folder not found: {result_folder}")
            return result_folder

        current_date = datetime.now().strftime("%Y_%m_%d")
        suffix = f"{self.docking_type.upper()}_DOCKING_RESULT_{self.processing_type.upper()}"
        base_name = f"{current_date}_{suffix}"
        result_folder = os.path.join(self.results_dir, base_name)
        counter = 1
        while os.path.isdir(result_folder):
            result_folder = os.path.join(self.results_dir, f"{base_name}_{counter}")
            counter += 1
        os.makedirs(result_folder, exist_ok=True)
        for target_dir in sorted(Path(self.targets_dir).glob("*/")):
            os.makedirs(os.path.join(result_folder, target_dir.name), exist_ok=True)
        return result_folder

    def _build_pending_jobs(self, result_folder: str) -> list[dict[str, str]]:
        jobs: list[dict[str, str]] = []
        for target_path in sorted(Path(self.targets_dir).glob("*/")):
            target_name = target_path.name
            target_requirements = self._target_requirements(target_path)
            result_target_dir = os.path.join(result_folder, target_name)
            os.makedirs(result_target_dir, exist_ok=True)
            for lig_group in sorted(Path(self.ligands_dir).glob("*/")):
                lig_group_name = lig_group.name
                lig_result_group_dir = os.path.join(result_target_dir, lig_group_name)
                os.makedirs(lig_result_group_dir, exist_ok=True)
                for ligand_file in sorted(lig_group.glob("*.pdbqt")):
                    ligand_name = ligand_file.stem
                    ligand_out_dir = os.path.join(lig_result_group_dir, ligand_name)
                    ligand_out_file = os.path.join(ligand_out_dir, f"{ligand_name}.pdbqt")
                    if self.run_type == "RESTART" and os.path.isfile(ligand_out_file):
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
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                parts = line.strip().split()
                if len(parts) >= 4 and parts[0] == "center":
                    grid["center_x"] = float(parts[1])
                    grid["center_y"] = float(parts[2])
                    grid["center_z"] = float(parts[3])
                elif len(parts) >= 4 and parts[0] == "npts":
                    grid["size_x"] = int(float(parts[1]))
                    grid["size_y"] = int(float(parts[2]))
                    grid["size_z"] = int(float(parts[3]))
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
        result_name = os.path.basename(result_folder)
        return os.path.join(result_folder, f"{result_name}.csv")

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
# worker PROCESSES via ProcessPoolExecutor. This is the Python/RDKit analogue of the
# `parallel -j "$cpu" -a "$list" process_smi1D {}` step in CODOC.sh: instead of GNU
# parallel forking one shell process per ligand, each ligand is submitted as a job to a
# pool of worker processes, which run truly in parallel (bypassing the GIL, unlike a
# thread pool, since RDKit embedding/optimization is CPU-bound Python+C code).
# --------------------------------------------------------------------------------------

def _lig_require_rdkit() -> None:
    if Chem is None or AllChem is None:
        raise RuntimeError("RDKit is not available in the current environment. Install RDKit to run this ligand routine.")


def _lig_require_obabel() -> str:
    obabel = shutil.which("obabel")
    if not obabel:
        raise RuntimeError("OpenBabel was not found in PATH. Install it before running this ligand routine.")
    return obabel


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


def _lig_prepare_3d_molecule(mol: Any, minimization_steps: int) -> Optional[Any]:
    try:
        working = Chem.AddHs(Chem.Mol(mol))
        params = AllChem.ETKDGv3()
        params.randomSeed = 0xC0D0
        embed = AllChem.EmbedMolecule(working, params)
        if embed != 0:
            return None
        try:
            AllChem.MMFFOptimizeMolecule(working, maxIters=minimization_steps)
        except Exception:
            try:
                AllChem.UFFOptimizeMolecule(working, maxIters=minimization_steps)
            except Exception:
                pass
        return Chem.RemoveHs(working)
    except Exception:
        return None


def _lig_export_rdkit_mol_to_pdbqt(mol: Any, output_path: Path, ph: float, minimization_steps: int) -> str:
    obabel = _lig_require_obabel()
    with tempfile.TemporaryDirectory(prefix="codoc_rdkit_") as temp_dir:
        temp_sdf = Path(temp_dir) / f"{output_path.stem}.sdf"
        writer = Chem.SDWriter(str(temp_sdf))
        writer.write(mol)
        writer.close()
        result = _lig_run_command([
            obabel,
            str(temp_sdf),
            "-O",
            str(output_path),
            "-p",
            str(ph),
            "--partialcharge",
            "gasteiger",
            "--minimize",
            "--sd",
            "--steps",
            str(minimization_steps),
            "--ff",
            "GAFF",
            "-r",
        ])
    if result.returncode != 0:
        return f"Failed to export {output_path.name} to PDBQT:\n{result.stdout}"
    return ""


def _lig_prepend_pdbqt_metadata(pdbqt_path: Path, ligand_name: str, smiles: str) -> None:
    if not pdbqt_path.exists():
        return
    content = pdbqt_path.read_text(encoding="utf-8", errors="ignore")
    content = re.sub(r"^REMARK\s+Name.*\n?", "", content, flags=re.MULTILINE)
    header = [f"REMARK  Name = {ligand_name}"]
    if smiles:
        header.append(f"REMARK SMILES {smiles}")
    pdbqt_path.write_text("\n".join(header) + "\n" + content, encoding="utf-8")


def _lig_convert_single_rdkit(input_path: Path, output_path: Path, ph: float, minimization_steps: int) -> Optional[str]:
    mol = _lig_mol_from_file(input_path)
    if mol is None:
        return f"Failed to read molecule from {input_path.name} with RDKit."
    smiles = _lig_canonical_smiles(mol)
    prepared = _lig_prepare_3d_molecule(mol, minimization_steps)
    if prepared is None:
        return f"Failed to generate a 3D conformation for {input_path.name}."
    export_error = _lig_export_rdkit_mol_to_pdbqt(prepared, output_path, ph, minimization_steps)
    if export_error:
        return export_error
    _lig_prepend_pdbqt_metadata(output_path, input_path.stem, smiles)
    return None


def _lig_convert_single_openbabel(input_path: Path, output_path: Path, ph: float, minimization_steps: int) -> Optional[str]:
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
                "--minimize",
                "--sd",
                "--steps",
                str(minimization_steps),
                "--ff",
                "MMFF94",
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
            "--minimize",
            "--sd",
            "--steps",
            str(minimization_steps),
            "--ff",
            "GAFF",
            "-r",
        ])
    if second.returncode != 0:
        return f"OpenBabel failed to convert {input_path.name} to PDBQT:\n{second.stdout}"
    _lig_prepend_pdbqt_metadata(output_path, input_path.stem, smiles)
    return None


def _lig_convert_worker(payload: tuple[str, str, str, str, float, int]) -> tuple[str, Optional[str]]:
    """Entry point executed inside each worker process (analogous to process_smi1D in CODOC.sh)."""
    input_str, output_str, _group_name, engine, ph, minimization_steps = payload
    input_path = Path(input_str)
    output_path = Path(output_str)
    try:
        if engine == "OpenBabel":
            error = _lig_convert_single_openbabel(input_path, output_path, ph, minimization_steps)
        else:
            error = _lig_convert_single_rdkit(input_path, output_path, ph, minimization_steps)
    except Exception as exc:
        error = f"Unexpected error converting {input_path.name}: {exc}"
    return (input_str, error)


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
    ) -> None:
        super().__init__()
        self.app_dir = app_dir
        self.ligands_dir = ligands_dir
        self.conversion_dir = conversion_dir
        self.settings = settings
        self.operation = operation
        self.failure_dir = os.path.join(conversion_dir, "CONVERSION_FAILURES")
        self.originals_dir = os.path.join(conversion_dir, "CONVERSION_ORIGINALS")
        self.drug_dir = os.path.join(conversion_dir, "NO_DRUGGABILITY")
        self.empty_dir = os.path.join(conversion_dir, "EMPTY_LIGANDS")
        self.dataframes_dir = os.path.join(conversion_dir, "DATAFRAMES")
        self.macrocycles_dir = os.path.join(conversion_dir, "MACROCYCLES")

    def run(self) -> None:
        try:
            os.makedirs(self.conversion_dir, exist_ok=True)
            operations = {
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

    def _archive_original_file(self, file_path: Path) -> None:
        destination_dir = Path(self.originals_dir) / file_path.parent.name
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = destination_dir / file_path.name
        counter = 1
        while destination.exists():
            destination = destination_dir / f"{file_path.stem}_{counter}{file_path.suffix}"
            counter += 1
        shutil.move(str(file_path), destination)

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
                passed = (
                    props["MW"] > self.settings.mw_min
                    and props["MW"] < self.settings.mw_max
                    and props["logP"] > self.settings.logp_min
                    and props["logP"] < self.settings.logp_max
                    and props["rotors"] < self.settings.rotatable_bonds_max
                    and props["HBA2"] < self.settings.h_acceptor_max
                    and props["HBD"] < self.settings.h_donor_max
                    and props["TPSA"] < self.settings.tpsa_max
                )
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
        os.makedirs(self.originals_dir, exist_ok=True)
        ligand_dirs = [path for path in sorted(Path(self.ligands_dir).glob("*/")) if path.is_dir()]
        selected_engine = (self.settings.conversion_engine or "RDKit").strip()

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

        requested_workers = int(getattr(self.settings, "conversion_workers", os.cpu_count() or 1) or 1)
        workers = max(1, min(requested_workers, total))

        # Analogous to `parallel -j "$cpu" -a "$list" process_smi1D {}` in CODOC.sh: each
        # ligand is dispatched to a pool of OS processes instead of a single serial loop,
        # so the conversion actually uses the available CPU cores.
        mp_context = multiprocessing.get_context("fork") if "fork" in multiprocessing.get_all_start_methods() else multiprocessing.get_context()

        counter = 0
        self.progress_text.emit(
            f"Converting {total} ligand(s) to PDBQT using {selected_engine} with {workers} parallel worker process(es)..."
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
                    ),
                ): (input_path, group_name)
                for input_path, output_path, group_name in jobs
            }
            for future in as_completed(future_map):
                input_path, group_name = future_map[future]
                counter += 1
                try:
                    _, error = future.result()
                except Exception as exc:
                    error = f"Worker process failed for {input_path.name}: {exc}"
                self._emit_progress(counter, total, f"Converting {input_path.name} to PDBQT using {selected_engine}")
                if error is not None:
                    failure_group = Path(self.failure_dir) / group_name
                    failure_group.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(input_path), failure_group / input_path.name)
                    self.progress_text.emit(error)

        for folder in ligand_dirs:
            for file_path in sorted(folder.iterdir()):
                if file_path.is_file() and file_path.suffix.lower() != ".pdbqt":
                    self._archive_original_file(file_path)
        return (
            f"Ligand conversion to PDBQT completed ({total} file(s), {workers} worker process(es)). "
            f"Original files were moved to {self.originals_dir}."
        )

    def _convert_single_ligand_rdkit(self, input_path: Path, output_path: Path) -> Optional[str]:
        mol = self._mol_from_file(input_path)
        if mol is None:
            return f"Failed to read molecule from {input_path.name} with RDKit."
        smiles = self._canonical_smiles(mol)
        prepared = self._prepare_3d_molecule(mol)
        if prepared is None:
            return f"Failed to generate a 3D conformation for {input_path.name}."
        export_error = self._export_rdkit_mol_to_pdbqt(prepared, output_path)
        if export_error:
            return export_error
        self._prepend_pdbqt_metadata(output_path, input_path.stem, smiles)
        return None

    def _convert_single_ligand_openbabel(self, input_path: Path, output_path: Path) -> Optional[str]:
        obabel = self._require_obabel()
        smiles = ""
        try:
            mol = self._mol_from_file(input_path)
            if mol is not None:
                smiles = self._canonical_smiles(mol)
        except Exception:
            smiles = ""

        if input_path.suffix.lower() == ".smi":
            with tempfile.TemporaryDirectory(prefix="codoc_convert_") as temp_dir:
                tmp_mol2 = Path(temp_dir) / f"{output_path.stem}.mol2"
                first = self._run_command([obabel, str(input_path), "-O", str(tmp_mol2), "--gen3d", "-r"])
                if first.returncode != 0:
                    return f"OpenBabel failed to generate 3D coordinates for {input_path.name}:\n{first.stdout}"
                second = self._run_command([
                    obabel,
                    str(tmp_mol2),
                    "-O",
                    str(output_path),
                    "-p",
                    str(self.settings.ph),
                    "--minimize",
                    "--sd",
                    "--steps",
                    str(self.settings.minimization_steps),
                    "--ff",
                    "MMFF94",
                ])
        else:
            second = self._run_command([
                obabel,
                str(input_path),
                "-O",
                str(output_path),
                "-p",
                str(self.settings.ph),
                "--partialcharge",
                "gasteiger",
                "--minimize",
                "--sd",
                "--steps",
                str(self.settings.minimization_steps),
                "--ff",
                "GAFF",
                "-r",
            ])
        if second.returncode != 0:
            return f"OpenBabel failed to convert {input_path.name} to PDBQT:\n{second.stdout}"
        self._prepend_pdbqt_metadata(output_path, input_path.stem, smiles)
        return None

    def _prepare_3d_molecule(self, mol: Any) -> Optional[Any]:
        self._require_rdkit()
        try:
            working = Chem.AddHs(Chem.Mol(mol))
            params = AllChem.ETKDGv3()
            params.randomSeed = 0xC0D0
            embed = AllChem.EmbedMolecule(working, params)
            if embed != 0:
                return None
            try:
                AllChem.MMFFOptimizeMolecule(working, maxIters=self.settings.minimization_steps)
            except Exception:
                try:
                    AllChem.UFFOptimizeMolecule(working, maxIters=self.settings.minimization_steps)
                except Exception:
                    pass
            return Chem.RemoveHs(working)
        except Exception:
            return None

    def _export_rdkit_mol_to_pdbqt(self, mol: Any, output_path: Path) -> str:
        obabel = self._require_obabel()
        with tempfile.TemporaryDirectory(prefix="codoc_rdkit_") as temp_dir:
            temp_sdf = Path(temp_dir) / f"{output_path.stem}.sdf"
            writer = Chem.SDWriter(str(temp_sdf))
            writer.write(mol)
            writer.close()
            result = self._run_command([
                obabel,
                str(temp_sdf),
                "-O",
                str(output_path),
                "-p",
                str(self.settings.ph),
                "--partialcharge",
                "gasteiger",
                "--minimize",
                "--sd",
                "--steps",
                str(self.settings.minimization_steps),
                "--ff",
                "GAFF",
                "-r",
            ])
        if result.returncode != 0:
            return f"Failed to export {output_path.name} to PDBQT:\n{result.stdout}"
        return ""

    def _prepend_pdbqt_metadata(self, pdbqt_path: Path, ligand_name: str, smiles: str) -> None:
        if not pdbqt_path.exists():
            return
        content = pdbqt_path.read_text(encoding="utf-8", errors="ignore")
        content = re.sub(r"^REMARK\s+Name.*\n?", "", content, flags=re.MULTILINE)
        header = [f"REMARK  Name = {ligand_name}"]
        if smiles:
            header.append(f"REMARK SMILES {smiles}")
        pdbqt_path.write_text("\n".join(header) + "\n" + content, encoding="utf-8")

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
        atom_lines = []
        torsdof_count = 0
        with open(file_path, "r", encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                if line.startswith("ATOM"):
                    atom_lines.append(line.rstrip("\n"))
                elif line.startswith("TORSDOF"):
                    torsdof_count += 1
        repeated = 0
        previous_coords: Optional[tuple[str, str, str]] = None
        reject_regex = re.compile(rf"\b({self.settings.rejected_elements})\b")
        zero_issue_count = 0
        for line in atom_lines:
            parts = line.split()
            if len(parts) >= 9:
                coords = (parts[5], parts[6], parts[7])
                zeros = sum(1 for value in coords if value in {"0.000", "-0.000"})
                if zeros >= 2:
                    zero_issue_count += 1
                if previous_coords == coords:
                    repeated += 1
                else:
                    repeated = 0
                previous_coords = coords
                if repeated >= 1:
                    return "repeated atom coordinates"
            if reject_regex.search(line):
                return "contains atoms not recognized by Vina-GPU"
            if re.search(r"ATOM.*[0-9]{6,}", line):
                return "contains abnormally large coordinate values"
        if zero_issue_count > 1:
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
                if not recovered:
                    self.progress_text.emit(message)
                    output_path.unlink(missing_ok=True)
                    continue
                self.progress_text.emit(f"Recovered {file_path.name} using {recovery_engine}.")
                self._prepend_pdbqt_metadata(output_path, file_path.stem, smiles)
                if self._invalid_pdbqt_reason(output_path):
                    output_path.unlink(missing_ok=True)
                    self.progress_text.emit(f"Recovered file {file_path.name} is still invalid.")
        return f"Recovery attempt completed. Recovered ligands are under {recovered_root}."

    def _recover_with_rdkit(self, smiles: str, output_path: Path, ligand_name: str) -> tuple[bool, str]:
        try:
            self._require_rdkit()
        except Exception as exc:
            return False, f"RDKit recovery unavailable for {ligand_name}: {exc}"
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return False, f"RDKit recovery failed for {ligand_name}: invalid SMILES '{smiles}'"
        prepared = self._prepare_3d_molecule(mol)
        if prepared is None:
            return False, f"RDKit recovery failed for {ligand_name}: could not generate 3D conformation"
        export_error = self._export_rdkit_mol_to_pdbqt(prepared, output_path)
        if export_error:
            return False, export_error.replace("Failed to export", "RDKit recovery failed to export")
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
                "--minimize",
                "--sd",
                "--steps",
                str(self.settings.minimization_steps),
                "--ff",
                "GAFF",
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

class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.app_dir = os.path.abspath(os.path.dirname(__file__))
        self.settings_path = os.path.join(self.app_dir, ".codoc_settings.json")
        self.legacy_codoc = os.path.join(str(Path.home()), "CODOC", "CODOC.sh")
        self.settings = DockingSettings()
        self.ligand_settings = LigandSettings()
        self.result_view_settings = ResultViewSettings()
        self._init_paths()
        self._ensure_runtime_dirs()
        self._load_settings()

        self.setWindowTitle("CODOC - Python Molecular Docking Tool")
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
        self._apply_initial_window_size(screen)
        self._start_hw_monitor()

    def _init_paths(self) -> None:
        self.ligands_dir = os.path.join(self.app_dir, "LIGANDS")
        self.targets_dir = os.path.join(self.app_dir, "TARGETS")
        self.results_dir = os.path.join(self.app_dir, "RESULTS", "DOCKING")
        self.conversion_results_dir = os.path.join(self.app_dir, "RESULTS", "CONVERSION")
        self.bin_dir = os.path.join(self.app_dir, "bin")

    def _ensure_runtime_dirs(self) -> None:
        for folder in (
            self.ligands_dir,
            self.targets_dir,
            self.results_dir,
            self.conversion_results_dir,
            self.bin_dir,
            os.path.join(self.app_dir, "JOBS"),
            os.path.join(self.app_dir, "TEST"),
            os.path.join(self.app_dir, "MODULES"),
            os.path.join(self.app_dir, "ICONS"),
        ):
            os.makedirs(folder, exist_ok=True)

    def _build_menu(self) -> None:
        menu_bar = self.menuBar()
        menu = menu_bar.addMenu("Menu")

        action_home = QAction("Home", self)
        action_home.triggered.connect(lambda: self.tabs.setCurrentIndex(0))
        menu.addAction(action_home)

        action_step1 = QAction("Step 1 - Docking Settings", self)
        action_step1.triggered.connect(lambda: self.tabs.setCurrentIndex(1))
        menu.addAction(action_step1)

        action_step2 = QAction("Step 2 - Prepare Ligands", self)
        action_step2.triggered.connect(lambda: self.tabs.setCurrentIndex(2))
        menu.addAction(action_step2)

        action_step3 = QAction("Step 3 - Prepare Targets", self)
        action_step3.triggered.connect(lambda: self.tabs.setCurrentIndex(3))
        menu.addAction(action_step3)

        action_step4 = QAction("Step 4 - Run Molecular Docking", self)
        action_step4.triggered.connect(lambda: self.tabs.setCurrentIndex(4))
        menu.addAction(action_step4)

        action_step5 = QAction("Step 5 - View Results", self)
        action_step5.triggered.connect(lambda: self.tabs.setCurrentIndex(5))
        menu.addAction(action_step5)

        menu.addSeparator()

        action_exit = QAction("Exit", self)
        action_exit.triggered.connect(self._close_from_action)
        menu.addAction(action_exit)

        help_menu = menu_bar.addMenu("Help")

        action_install = QAction("Install Requirements", self)
        action_install.triggered.connect(self.show_requirements_installer)
        help_menu.addAction(action_install)

        help_menu.addSeparator()

        action_github = QAction("Code and Tutorials (Github)", self)
        action_github.triggered.connect(self.open_github_page)
        help_menu.addAction(action_github)

        help_menu.addSeparator()

        action_about = QAction("About Us", self)
        action_about.triggered.connect(self.show_about)
        help_menu.addAction(action_about)

    def _close_from_action(self) -> None:
        self.close()

    def open_github_page(self) -> None:
        webbrowser.open("https://github.com/moimaian")

    def show_about(self) -> None:
        QMessageBox.about(
            self,
            "ABOUT US",
            "CODOC\n"
            "Computational Molecular Docking Platform\n"
            "\n"
            "Developed by:\n"
            "   Allan Michael Junkert\n"
            "   Gustavo Henrique Scheiffer\n"
            "   Moises Maia Neto\n"
            "   Roberto Pontarolo\n"
            "   Universidade Federal do Parana (UFPR), Brazil\n"
            "\n"
            "Contact:\n"
            "   moimaian@gmail.com\n"
            "\n"
            "Version 1.0 (beta)"
        )

    def _title(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("font-size: 14pt; font-weight: bold;")
        return label

    def _nav_buttons_row(self, previous_index: Optional[int], next_index: Optional[int]) -> QHBoxLayout:
        row = QHBoxLayout()

        back_button = QPushButton(" << BACK ")
        back_button.setFixedWidth(200)
        back_button.setStyleSheet(_SS_BTN_NAV)
        back_button.setEnabled(previous_index is not None)
        if previous_index is not None:
            back_button.clicked.connect(lambda: self.tabs.setCurrentIndex(previous_index))

        next_button = QPushButton(" NEXT >> ")
        next_button.setFixedWidth(200)
        next_button.setStyleSheet(_SS_BTN_NAV)
        next_button.setEnabled(next_index is not None)
        if next_index is not None:
            next_button.clicked.connect(lambda: self.tabs.setCurrentIndex(next_index))

        row.addWidget(back_button, alignment=Qt.AlignLeft)
        row.addWidget(next_button, alignment=Qt.AlignRight)
        return row

    def _apply_initial_window_size(self, screen) -> None:
        hint = self.sizeHint()
        home_hint = self.tabs.widget(0).sizeHint() if hasattr(self, "tabs") and self.tabs.count() else hint
        width_hint = max(hint.width() + 80, home_hint.width() + 120)
        height_hint = max(hint.height() + 110, home_hint.height() + 220)
        width = min(max(width_hint, 1220), int(screen.width() * 0.78))
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

    def _build_home_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(36, 32, 36, 24)
        inner_layout.setSpacing(16)
        scroll.setWidget(inner)

        logo = QLabel()
        logo_path = os.path.join(self.app_dir, "ICONS", "LOGO_CODOC2.png")
        if os.path.isfile(logo_path):
            pix = QPixmap(logo_path).scaled(180, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo.setPixmap(pix)
        logo.setAlignment(Qt.AlignCenter)
        inner_layout.addWidget(logo)

        title = QLabel("Computational Molecular Docking Plataform")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 16pt; font-weight: bold;")
        inner_layout.addWidget(title)

        subtitle = QLabel("Multi-target docking with Vina")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("font-size: 11pt; color: #6E8CA8;")
        inner_layout.addWidget(subtitle)

        top_separator = QFrame()
        top_separator.setFrameShape(QFrame.HLine)
        top_separator.setFrameShadow(QFrame.Sunken)
        top_separator.setStyleSheet("color:#2A4A6B;")
        inner_layout.addWidget(top_separator)

        hw_row = QHBoxLayout()
        hw_row.setSpacing(14)
        home_group_width = 1100
        home_group_style = (
            "QGroupBox { background-color: transparent; border: 1.5px solid #2A4A6B; border-radius: 6px; }"
            "QGroupBox::title { color: #2ECC71; }"
        )

        def add_centered_group(widget: QWidget, group_width: int = home_group_width) -> None:
            widget.setMinimumWidth(group_width)
            widget.setMaximumWidth(group_width)
            row = QHBoxLayout()
            row.addStretch(1)
            row.addWidget(widget)
            row.addStretch(1)
            inner_layout.addLayout(row)

        cpu_grp = QGroupBox("Hardware Specs - CPU")
        cpu_grp.setStyleSheet(home_group_style)
        cpu_form = QFormLayout(cpu_grp)
        cpu_form.setHorizontalSpacing(16)
        cpu_form.setVerticalSpacing(4)
        for label_text, value_text in self._home_hw_cpu_info():
            key_label = QLabel(label_text)
            key_label.setStyleSheet("color:#6E8CA8;font-size:9pt;")
            value_label = QLabel(value_text)
            value_label.setStyleSheet("font-weight:bold;font-size:9pt;color:#C9D1D9;")
            value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            cpu_form.addRow(key_label, value_label)
        hw_row.addWidget(cpu_grp, 1)

        gpu_grp = QGroupBox("Hardware Specs - GPU")
        gpu_grp.setStyleSheet(home_group_style)
        gpu_form = QFormLayout(gpu_grp)
        gpu_form.setHorizontalSpacing(16)
        gpu_form.setVerticalSpacing(4)
        for label_text, value_text in self._home_hw_gpu_info():
            key_label = QLabel(label_text)
            key_label.setStyleSheet("color:#6E8CA8;font-size:9pt;")
            value_label = QLabel(value_text)
            value_label.setStyleSheet("font-weight:bold;font-size:9pt;color:#C9D1D9;")
            value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            gpu_form.addRow(key_label, value_label)
        hw_row.addWidget(gpu_grp, 1)

        hw_wrap = QWidget()
        hw_wrap.setLayout(hw_row)
        add_centered_group(hw_wrap)

        sw_grp = QGroupBox("Software Specs")
        sw_grp.setStyleSheet(home_group_style)
        sw_grid = QGridLayout(sw_grp)
        sw_grid.setHorizontalSpacing(24)
        sw_grid.setVerticalSpacing(4)
        sw_items = self._home_sw_versions()
        cols = 3
        for idx, (name, version) in enumerate(sw_items):
            row = idx // cols
            col = (idx % cols) * 2
            ok = version != "not installed"
            name_label = QLabel(name)
            name_label.setStyleSheet("color:#6E8CA8;font-size:9pt;")
            version_label = QLabel(version)
            version_label.setStyleSheet(
                f"font-weight:bold;font-size:9pt;color:{'#27AE60' if ok else '#E74C3C'};"
            )
            version_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            sw_grid.addWidget(name_label, row, col)
            sw_grid.addWidget(version_label, row, col + 1)
        add_centered_group(sw_grp)

        pipe_grp = QGroupBox("Pipeline - Steps")
        pipe_grp.setStyleSheet(home_group_style)
        pipe_grid = QGridLayout(pipe_grp)
        pipe_grid.setHorizontalSpacing(20)
        pipe_grid.setVerticalSpacing(6)
        pipe_grid.setColumnStretch(1, 1)
        steps = [
            ("Step 1 - Docking Settings", "Configure directories, docking parameters and binary paths."),
            ("Step 2 - Prepare Ligands", "Split inputs, calculate ligand descriptors, filter, convert to PDBQT and recover failures."),
            ("Step 3 - Prepare Targets", "Prepare rigid or flexible receptors, build grid boxes and manage target folders."),
            ("Step 4 - Run Molecular Docking", "Launch rigid or flexible docking on CPU or GPU, including restart workflows."),
            ("Step 5 - View Results", "Inspect docking tables, filter top ligands by RMSD and plot ranked hits."),
        ]
        for row, (step_name, desc) in enumerate(steps):
            step_label = QLabel(f"<b>{step_name}</b>")
            step_label.setStyleSheet("color:#C9D1D9;font-size:9pt;")
            desc_label = QLabel(desc)
            desc_label.setStyleSheet("color:#6E8CA8;font-size:9pt;")
            desc_label.setWordWrap(False)
            pipe_grid.addWidget(step_label, row, 0)
            pipe_grid.addWidget(desc_label, row, 1)
        add_centered_group(pipe_grp)

        bottom_separator = QFrame()
        bottom_separator.setFrameShape(QFrame.HLine)
        bottom_separator.setFrameShadow(QFrame.Sunken)
        bottom_separator.setStyleSheet("color:#2A4A6B;")
        inner_layout.addWidget(bottom_separator)

        buttons = QHBoxLayout()
        btn_install = QPushButton("Install Requirements")
        btn_install.setFixedWidth(240)
        btn_install.clicked.connect(self.show_requirements_installer)
        btn_legacy = QPushButton("Open Legacy CODOC.sh")
        btn_legacy.setFixedWidth(300)
        btn_legacy.setStyleSheet(_SS_BTN_SECONDARY)
        btn_legacy.clicked.connect(self.launch_legacy_codoc)
        buttons.addWidget(btn_install)
        buttons.addWidget(btn_legacy)
        inner_layout.addLayout(buttons)
        inner_layout.addStretch(1)

        layout.addWidget(scroll)

        self.tabs.addTab(tab, "HOME")

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
            fields = "name,memory.total,clocks.max.sm,clocks.max.memory,power.limit,driver_version"
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
            ]
            rows.extend(zip(labels, parts))
        except Exception as exc:
            rows.append(("Error", str(exc)))
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
        ]
        for display, module_name, attr_name in libraries:
            try:
                module = importlib.import_module(module_name)
                version = getattr(module, attr_name, "available")
            except Exception:
                version = "not installed"
            rows.append((display, str(version)))
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
        try:
            find_pdb2pqr(os.path.join(venv_paths("CODOC")["venv_dir"], "bin"))
            pdb2pqr_status = "available"
        except TargetPrepareError:
            pdb2pqr_status = "not installed"
        rows.append(("PDB2PQR / PROPKA", pdb2pqr_status))
        return rows

    def _build_config_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(self._title("Step 1. Docking Settings"))

        self.ed_ligands_dir = QLineEdit(self.ligands_dir)
        self.ed_targets_dir = QLineEdit(self.targets_dir)

        settings_box = QGroupBox("Docking parameters")
        settings_box.setMinimumWidth(1000)
        settings_form = QGridLayout(settings_box)
        settings_form.setHorizontalSpacing(18)
        settings_form.setVerticalSpacing(8)
        self.cb_scoring = QComboBox()
        self.cb_scoring.addItems(["vina", "ad4", "vinardo"])
        self.cb_split = QComboBox()
        self.cb_split.addItems(["no", "yes"])
        self.sp_cpu_threads = QSpinBox(); self.sp_cpu_threads.setRange(1, 512)
        self.sp_cpu_parallel = QSpinBox(); self.sp_cpu_parallel.setRange(1, 512)
        self.sp_exhaustiveness = QSpinBox(); self.sp_exhaustiveness.setRange(1, 32768)
        self.sp_gpu_threads = QSpinBox(); self.sp_gpu_threads.setRange(1, 500000)
        self.sp_poses = QSpinBox(); self.sp_poses.setRange(1, 100)
        self.sp_min_rmsd = QDoubleSpinBox(); self.sp_min_rmsd.setRange(0.0, 100.0); self.sp_min_rmsd.setDecimals(3)
        self.sp_energy = QDoubleSpinBox(); self.sp_energy.setRange(0.0, 100.0); self.sp_energy.setDecimals(3)
        self.cb_opencl_platform = QComboBox()
        self.cb_opencl_device = QComboBox()
        self.cb_opencl_platform.currentIndexChanged.connect(self._update_opencl_device_choices)
        param_rows = [
            ("Scoring function", self.cb_scoring, "Split results", self.cb_split),
            ("CPU threads", self.sp_cpu_threads, "CPU parallelism", self.sp_cpu_parallel),
            ("Exhaustiveness", self.sp_exhaustiveness, "GPU threads", self.sp_gpu_threads),
            ("Poses", self.sp_poses, "Energy range", self.sp_energy),
            ("Minimum RMSD", self.sp_min_rmsd, "OpenCL platform", self.cb_opencl_platform),
        ]
        for row_idx, (label_left, widget_left, label_right, widget_right) in enumerate(param_rows):
            settings_form.addWidget(QLabel(label_left), row_idx, 0)
            settings_form.addWidget(widget_left, row_idx, 1)
            settings_form.addWidget(QLabel(label_right), row_idx, 2)
            settings_form.addWidget(widget_right, row_idx, 3)
        final_param_row = len(param_rows)
        settings_form.addWidget(QLabel("OpenCL device"), final_param_row, 0)
        settings_form.addWidget(self.cb_opencl_device, final_param_row, 1, 1, 3)
        settings_form.addWidget(QLabel("Ligands"), final_param_row + 1, 0)
        settings_form.addWidget(self._path_row(self.ed_ligands_dir, self._browse_ligands_dir), final_param_row + 1, 1, 1, 3)
        settings_form.addWidget(QLabel("Targets"), final_param_row + 2, 0)
        settings_form.addWidget(self._path_row(self.ed_targets_dir, self._browse_targets_dir), final_param_row + 2, 1, 1, 3)
        self._load_opencl_choices()
        settings_wrap = QHBoxLayout()
        settings_wrap.addStretch(1)
        settings_wrap.addWidget(settings_box)
        settings_wrap.addStretch(1)
        layout.addLayout(settings_wrap)

        row = QHBoxLayout()
        row.addStretch(1)
        btn_save = QPushButton("Save settings")
        btn_save.setFixedWidth(180)
        btn_save.clicked.connect(self._save_settings)
        btn_reload = QPushButton("Reload settings")
        btn_reload.setFixedWidth(180)
        btn_reload.setStyleSheet(_SS_BTN_SECONDARY)
        btn_reload.clicked.connect(self._load_settings)
        row.addWidget(btn_save)
        row.addWidget(btn_reload)
        row.addStretch(1)
        layout.addLayout(row)

        layout.addStretch(1)
        layout.addLayout(self._nav_buttons_row(0, 2))
        self.tabs.addTab(tab, "STEP 1")

    def _build_ligands_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(self._title("Step 2. Prepare Ligands"))

        ligands_group_width = 1000

        def add_centered_group(widget: QWidget, group_width: int = ligands_group_width) -> None:
            widget.setMinimumWidth(group_width)
            widget.setMaximumWidth(group_width)
            row_wrap = QHBoxLayout()
            row_wrap.addStretch(1)
            row_wrap.addWidget(widget)
            row_wrap.addStretch(1)
            layout.addLayout(row_wrap)

        box = QGroupBox("Ligand preparation settings")
        box_layout = QVBoxLayout(box)
        self.lbl_lig_summary = QLabel()
        box_layout.addWidget(self.lbl_lig_summary)

        settings_form = QGridLayout()
        self.sp_lig_file_size = QSpinBox(); self.sp_lig_file_size.setRange(1, 1000000); self.sp_lig_file_size.setMaximumWidth(130)
        self.sp_lig_ph = QDoubleSpinBox(); self.sp_lig_ph.setRange(0.0, 100.0); self.sp_lig_ph.setDecimals(2); self.sp_lig_ph.setMaximumWidth(110)
        self.sp_lig_max_folder = QSpinBox(); self.sp_lig_max_folder.setRange(1, 1000000); self.sp_lig_max_folder.setMaximumWidth(140)
        self.ed_lig_reject = QLineEdit(); self.ed_lig_reject.setMaximumWidth(180)
        self.cb_lig_conversion_engine = QComboBox(); self.cb_lig_conversion_engine.addItems(["RDKit", "OpenBabel"]); self.cb_lig_conversion_engine.setMaximumWidth(140)
        self.sp_lig_workers = QSpinBox(); self.sp_lig_workers.setRange(1, max(1, (os.cpu_count() or 1) * 4)); self.sp_lig_workers.setMaximumWidth(110)
        self.cb_lig_speed_first = QComboBox(); self.cb_lig_speed_first.addItems(["fastest", "fast", "med", "slow", "slowest", "dist"]); self.cb_lig_speed_first.setMaximumWidth(120)
        self.cb_lig_speed_second = QComboBox(); self.cb_lig_speed_second.addItems(["fastest", "fast", "med", "slow", "slowest", "dist"]); self.cb_lig_speed_second.setMaximumWidth(120)
        self.sp_lig_timeout_first = QSpinBox(); self.sp_lig_timeout_first.setRange(1, 1000000); self.sp_lig_timeout_first.setMaximumWidth(130)
        self.sp_lig_timeout_second = QSpinBox(); self.sp_lig_timeout_second.setRange(1, 1000000); self.sp_lig_timeout_second.setMaximumWidth(130)
        self.sp_lig_steps = QSpinBox(); self.sp_lig_steps.setRange(1, 1000000); self.sp_lig_steps.setMaximumWidth(130)
        self.sp_lig_mw_min = QDoubleSpinBox(); self.sp_lig_mw_min.setRange(-10000.0, 10000.0); self.sp_lig_mw_min.setDecimals(3); self.sp_lig_mw_min.setMaximumWidth(130)
        self.sp_lig_mw_max = QDoubleSpinBox(); self.sp_lig_mw_max.setRange(-10000.0, 10000.0); self.sp_lig_mw_max.setDecimals(3); self.sp_lig_mw_max.setMaximumWidth(130)
        self.sp_lig_logp_min = QDoubleSpinBox(); self.sp_lig_logp_min.setRange(-1000.0, 1000.0); self.sp_lig_logp_min.setDecimals(3); self.sp_lig_logp_min.setMaximumWidth(120)
        self.sp_lig_logp_max = QDoubleSpinBox(); self.sp_lig_logp_max.setRange(-1000.0, 1000.0); self.sp_lig_logp_max.setDecimals(3); self.sp_lig_logp_max.setMaximumWidth(120)
        self.sp_lig_rot = QSpinBox(); self.sp_lig_rot.setRange(0, 1000); self.sp_lig_rot.setMaximumWidth(110)
        self.sp_lig_hd = QSpinBox(); self.sp_lig_hd.setRange(0, 1000); self.sp_lig_hd.setMaximumWidth(110)
        self.sp_lig_ha = QSpinBox(); self.sp_lig_ha.setRange(0, 1000); self.sp_lig_ha.setMaximumWidth(110)
        self.sp_lig_tpsa = QDoubleSpinBox(); self.sp_lig_tpsa.setRange(0.0, 100000.0); self.sp_lig_tpsa.setDecimals(3); self.sp_lig_tpsa.setMaximumWidth(130)

        settings_form.addWidget(QLabel("Minimum file size"), 0, 0)
        settings_form.addWidget(self.sp_lig_file_size, 0, 1)
        settings_form.addWidget(QLabel("pH"), 0, 2)
        settings_form.addWidget(self.sp_lig_ph, 0, 3)
        settings_form.addWidget(QLabel("Max ligands/folder"), 0, 4)
        settings_form.addWidget(self.sp_lig_max_folder, 0, 5)

        settings_form.addWidget(QLabel("Rejected elements regex"), 1, 0)
        settings_form.addWidget(self.ed_lig_reject, 1, 1)
        settings_form.addWidget(QLabel("Conversion engine"), 1, 2)
        settings_form.addWidget(self.cb_lig_conversion_engine, 1, 3)
        settings_form.addWidget(QLabel("1st speed"), 1, 4)
        settings_form.addWidget(self.cb_lig_speed_first, 1, 5)

        settings_form.addWidget(QLabel("2nd speed"), 2, 0)
        settings_form.addWidget(self.cb_lig_speed_second, 2, 1)
        settings_form.addWidget(QLabel("1st timeout (s)"), 2, 2)
        settings_form.addWidget(self.sp_lig_timeout_first, 2, 3)
        settings_form.addWidget(QLabel("2nd timeout (s)"), 2, 4)
        settings_form.addWidget(self.sp_lig_timeout_second, 2, 5)

        settings_form.addWidget(QLabel("Minimization steps"), 3, 0)
        settings_form.addWidget(self.sp_lig_steps, 3, 1)
        settings_form.addWidget(QLabel("MW min"), 3, 2)
        settings_form.addWidget(self.sp_lig_mw_min, 3, 3)
        settings_form.addWidget(QLabel("MW max"), 3, 4)
        settings_form.addWidget(self.sp_lig_mw_max, 3, 5)

        settings_form.addWidget(QLabel("LogP min"), 4, 0)
        settings_form.addWidget(self.sp_lig_logp_min, 4, 1)
        settings_form.addWidget(QLabel("LogP max"), 4, 2)
        settings_form.addWidget(self.sp_lig_logp_max, 4, 3)
        settings_form.addWidget(QLabel("Rotatable bonds max"), 4, 4)
        settings_form.addWidget(self.sp_lig_rot, 4, 5)

        settings_form.addWidget(QLabel("H donor max"), 5, 0)
        settings_form.addWidget(self.sp_lig_hd, 5, 1)
        settings_form.addWidget(QLabel("H acceptor max"), 5, 2)
        settings_form.addWidget(self.sp_lig_ha, 5, 3)
        settings_form.addWidget(QLabel("TPSA max"), 5, 4)
        settings_form.addWidget(self.sp_lig_tpsa, 5, 5)

        settings_form.addWidget(QLabel("Conversion workers (parallel processes)"), 6, 0)
        settings_form.addWidget(self.sp_lig_workers, 6, 1)
        box_layout.addLayout(settings_form)

        row = QHBoxLayout()
        row.setAlignment(Qt.AlignCenter)
        row.setSpacing(10)
        btn_refresh = QPushButton("Refresh summary")
        btn_refresh.setFixedWidth(220)
        btn_refresh.setStyleSheet(_SS_BTN_SECONDARY)
        btn_refresh.clicked.connect(self._refresh_ligand_summary)
        btn_open = QPushButton("Open ligands folder")
        btn_open.setFixedWidth(220)
        btn_open.setStyleSheet(_SS_BTN_SECONDARY)
        btn_open.clicked.connect(lambda: self._open_path(self.ligands_dir))
        btn_save_lig = QPushButton("Save ligand settings")
        btn_save_lig.setFixedWidth(220)
        btn_save_lig.clicked.connect(self._save_settings)
        row.addWidget(btn_refresh)
        row.addWidget(btn_open)
        row.addWidget(btn_save_lig)
        box_layout.addLayout(row)
        add_centered_group(box)

        actions_box = QGroupBox("Ligand actions")
        actions_layout = QGridLayout(actions_box)
        action_button_width = 255
        ligand_actions = [
            ("Split multimodel files", lambda: self._run_ligand_tool("split_multimodel")),
            ("Split large folders", lambda: self._run_ligand_tool("split_large_folders")),
            ("Generate SMI/CSV + Lipinski", lambda: self._run_ligand_tool("generate_lipinski")),
            ("Apply druggability filter", lambda: self._run_ligand_tool("druggability_filter")),
            ("Move empty files", lambda: self._run_ligand_tool("move_empty")),
            ("Convert ligands to PDBQT", lambda: self._run_ligand_tool("convert_pdbqt")),
            ("Reject invalid PDBQT", lambda: self._run_ligand_tool("reject_pdbqt")),
            ("Recover failed ligands", lambda: self._run_ligand_tool("recover_pdbqt")),
            ("Fix macrocycles for GPU", lambda: self._run_ligand_tool("fix_macrocycles")),
        ]
        for idx, (label, handler) in enumerate(ligand_actions):
            button = QPushButton(label)
            button.setFixedWidth(action_button_width)
            button.clicked.connect(handler)
            actions_layout.addWidget(button, idx // 3, idx % 3)
        actions_layout.setHorizontalSpacing(12)
        actions_layout.setVerticalSpacing(10)
        actions_layout.setAlignment(Qt.AlignCenter)
        add_centered_group(actions_box)

        self.pb_ligand = QProgressBar()
        self.pb_ligand.setValue(0)
        add_centered_group(self.pb_ligand)
        self.txt_ligand_log = QPlainTextEdit()
        self.txt_ligand_log.setReadOnly(True)
        add_centered_group(self.txt_ligand_log)
        layout.addStretch(1)
        layout.addLayout(self._nav_buttons_row(1, 3))
        self.tabs.addTab(tab, "STEP 2")
        self._refresh_ligand_summary()

    def _build_targets_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(self._title("Step 3. Prepare Targets"))

        targets_group_width = 1000
        target_field_width = 320
        target_button_width = 240

        def add_centered_group(widget: QWidget, group_width: int = targets_group_width) -> None:
            widget.setMinimumWidth(group_width)
            widget.setMaximumWidth(group_width)
            row_wrap = QHBoxLayout()
            row_wrap.addStretch(1)
            row_wrap.addWidget(widget)
            row_wrap.addStretch(1)
            layout.addLayout(row_wrap)

        target_box = QGroupBox("Prepare receptor target")
        target_form = QFormLayout(target_box)
        target_form.setHorizontalSpacing(18)
        target_form.setVerticalSpacing(14)
        self.cb_target_mode = QComboBox()
        self.cb_target_mode.addItems(["Rigid target from source file", "Flexible target from prepared PDBQT files"])
        self.cb_target_mode.setFixedWidth(target_field_width)
        self.cb_target_mode.currentTextChanged.connect(self._toggle_target_mode)

        self.ed_target_name = QLineEdit()
        self.ed_target_name.setFixedWidth(target_field_width)
        self.ed_target_name.setPlaceholderText("Optional target folder name")

        self.ed_target_file = QLineEdit()
        self.ed_target_file.setFixedWidth(target_field_width)
        btn_choose_target = QPushButton("Select target file")
        btn_choose_target.setFixedWidth(target_button_width)
        btn_choose_target.clicked.connect(self._choose_target_file)
        row_target = QHBoxLayout()
        row_target.setContentsMargins(0, 0, 0, 0)
        row_target.setSpacing(10)
        row_target.addWidget(self.ed_target_file)
        row_target.addWidget(btn_choose_target)
        row_target.addStretch(1)
        wrap_target = QWidget(); wrap_target.setLayout(row_target)

        self.sp_target_ph = QDoubleSpinBox()
        self.sp_target_ph.setRange(0.0, 14.0)
        self.sp_target_ph.setDecimals(2)
        self.sp_target_ph.setSingleStep(0.1)
        self.sp_target_ph.setValue(7.4)
        self.sp_target_ph.setFixedWidth(target_field_width)
        self.sp_target_ph.setToolTip(
            "Environment pH used by PROPKA to compute each ionizable residue's pKa "
            "(considering its 3D microenvironment) and protonate the receptor accordingly."
        )

        self.ed_target_rigid_file = QLineEdit()
        self.ed_target_rigid_file.setFixedWidth(target_field_width)
        btn_choose_rigid = QPushButton("Select protein_rigid.pdbqt")
        btn_choose_rigid.setFixedWidth(target_button_width)
        btn_choose_rigid.clicked.connect(lambda: self._choose_pdbqt_file(self.ed_target_rigid_file, "Select rigid receptor PDBQT"))
        row_rigid = QHBoxLayout()
        row_rigid.setContentsMargins(0, 0, 0, 0)
        row_rigid.setSpacing(10)
        row_rigid.addWidget(self.ed_target_rigid_file)
        row_rigid.addWidget(btn_choose_rigid)
        row_rigid.addStretch(1)
        wrap_rigid = QWidget(); wrap_rigid.setLayout(row_rigid)

        self.ed_target_flex_file = QLineEdit()
        self.ed_target_flex_file.setFixedWidth(target_field_width)
        btn_choose_flex = QPushButton("Select protein_flex.pdbqt")
        btn_choose_flex.setFixedWidth(target_button_width)
        btn_choose_flex.clicked.connect(lambda: self._choose_pdbqt_file(self.ed_target_flex_file, "Select flexible receptor PDBQT"))
        row_flex = QHBoxLayout()
        row_flex.setContentsMargins(0, 0, 0, 0)
        row_flex.setSpacing(10)
        row_flex.addWidget(self.ed_target_flex_file)
        row_flex.addWidget(btn_choose_flex)
        row_flex.addStretch(1)
        wrap_flex = QWidget(); wrap_flex.setLayout(row_flex)

        self.ed_target_grid_file = QLineEdit()
        self.ed_target_grid_file.setFixedWidth(target_field_width)
        btn_choose_grid = QPushButton("Select existing grid.txt")
        btn_choose_grid.setFixedWidth(target_button_width)
        btn_choose_grid.clicked.connect(lambda: self._choose_grid_file(self.ed_target_grid_file, "Select grid.txt (optional)"))
        row_grid = QHBoxLayout()
        row_grid.setContentsMargins(0, 0, 0, 0)
        row_grid.setSpacing(10)
        row_grid.addWidget(self.ed_target_grid_file)
        row_grid.addWidget(btn_choose_grid)
        row_grid.addStretch(1)
        wrap_grid = QWidget(); wrap_grid.setLayout(row_grid)

        grid_param_field_width = 140
        self.sp_center_x = QDoubleSpinBox(); self.sp_center_x.setRange(-9999.0, 9999.0); self.sp_center_x.setDecimals(3); self.sp_center_x.setFixedWidth(grid_param_field_width)
        self.sp_center_y = QDoubleSpinBox(); self.sp_center_y.setRange(-9999.0, 9999.0); self.sp_center_y.setDecimals(3); self.sp_center_y.setFixedWidth(grid_param_field_width)
        self.sp_center_z = QDoubleSpinBox(); self.sp_center_z.setRange(-9999.0, 9999.0); self.sp_center_z.setDecimals(3); self.sp_center_z.setFixedWidth(grid_param_field_width)
        self.sp_grid_x = QSpinBox(); self.sp_grid_x.setRange(1, 500); self.sp_grid_x.setFixedWidth(grid_param_field_width)
        self.sp_grid_y = QSpinBox(); self.sp_grid_y.setRange(1, 500); self.sp_grid_y.setFixedWidth(grid_param_field_width)
        self.sp_grid_z = QSpinBox(); self.sp_grid_z.setRange(1, 500); self.sp_grid_z.setFixedWidth(grid_param_field_width)
        self.sp_spacing = QDoubleSpinBox(); self.sp_spacing.setRange(0.1, 20.0); self.sp_spacing.setDecimals(3); self.sp_spacing.setFixedWidth(target_field_width)

        grid_params_grid = QGridLayout()
        grid_params_grid.setHorizontalSpacing(18)
        grid_params_grid.setVerticalSpacing(14)
        grid_param_rows = [
            ("Grid center X", self.sp_center_x, "Grid x size", self.sp_grid_x),
            ("Grid center Y", self.sp_center_y, "Grid y size", self.sp_grid_y),
            ("Grid center Z", self.sp_center_z, "Grid z size", self.sp_grid_z),
        ]
        for row_idx, (label_left, widget_left, label_right, widget_right) in enumerate(grid_param_rows):
            grid_params_grid.addWidget(QLabel(label_left), row_idx, 0)
            grid_params_grid.addWidget(widget_left, row_idx, 1)
            grid_params_grid.addWidget(QLabel(label_right), row_idx, 2)
            grid_params_grid.addWidget(widget_right, row_idx, 3)
        grid_params_grid.setColumnStretch(4, 1)
        grid_params_widget = QWidget()
        grid_params_widget.setLayout(grid_params_grid)

        target_form.addRow("Preparation mode", self.cb_target_mode)
        target_form.addRow("Target name", self.ed_target_name)
        target_form.addRow("Target file", wrap_target)
        target_form.addRow("Protonation pH", self.sp_target_ph)
        target_form.addRow("Rigid receptor", wrap_rigid)
        target_form.addRow("Flexible receptor", wrap_flex)
        target_form.addRow("Existing grid", wrap_grid)
        target_form.addRow(grid_params_widget)
        target_form.addRow("Grid spacing", self.sp_spacing)

        btn_prepare = QPushButton("Prepare target")
        btn_prepare.setFixedWidth(180)
        btn_prepare.clicked.connect(self.prepare_target)
        target_form.addRow("", btn_prepare)
        add_centered_group(target_box)

        manage_box = QGroupBox("Prepared targets")
        manage_layout = QVBoxLayout(manage_box)
        manage_row = QHBoxLayout()
        self.cb_prepared_targets = QComboBox()
        self.cb_prepared_targets.setMaximumWidth(200)
        btn_refresh_targets = QPushButton("Refresh target list")
        btn_refresh_targets.setFixedWidth(170)
        btn_refresh_targets.clicked.connect(self._populate_prepared_targets)
        btn_open_target = QPushButton("Open target folder")
        btn_open_target.setFixedWidth(170)
        btn_open_target.clicked.connect(self._open_selected_target_folder)
        btn_remove_target = QPushButton("Remove target")
        btn_remove_target.setFixedWidth(170)
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
        self.tabs.addTab(tab, "STEP 3")
        self._refresh_targets_summary()
        self._populate_prepared_targets()
        self._toggle_target_mode()

    def _build_docking_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(self._title("Step 4. Run Molecular Docking"))

        docking_group_width = 1000
        docking_field_width = 320

        def add_centered_group(widget: QWidget, group_width: int = docking_group_width) -> None:
            widget.setMinimumWidth(group_width)
            widget.setMaximumWidth(group_width)
            row_wrap = QHBoxLayout()
            row_wrap.addStretch(1)
            row_wrap.addWidget(widget)
            row_wrap.addStretch(1)
            layout.addLayout(row_wrap)

        group = QGroupBox("Docking execution")
        group.setMinimumWidth(480)
        group.setMaximumWidth(480)
        form = QFormLayout(group)
        self.cb_docking_type = QComboBox(); self.cb_docking_type.addItems(["Rigid", "Flexible"]); self.cb_docking_type.setFixedWidth(docking_field_width)
        self.cb_processing_type = QComboBox(); self.cb_processing_type.addItems(["CPU", "GPU"]); self.cb_processing_type.setFixedWidth(docking_field_width)
        self.cb_docking_mode = QComboBox(); self.cb_docking_mode.addItems(["normal", "score_only", "local_only"]); self.cb_docking_mode.setFixedWidth(docking_field_width)
        self.cb_run_type = QComboBox(); self.cb_run_type.addItems(["NEW", "RESTART"]); self.cb_run_type.setFixedWidth(docking_field_width)
        self.cb_existing_result = QComboBox()
        self.cb_existing_result.setFixedWidth(docking_field_width)
        self.cb_processing_type.currentTextChanged.connect(self._toggle_docking_mode_options)
        self.cb_run_type.currentTextChanged.connect(self._toggle_restart_combo)
        form.addRow("Docking type", self.cb_docking_type)
        form.addRow("Processing type", self.cb_processing_type)
        form.addRow("Vina mode", self.cb_docking_mode)
        form.addRow("Run type", self.cb_run_type)
        form.addRow("Restart result", self.cb_existing_result)

        btn_run = QPushButton("Run docking")
        btn_run.setFixedWidth(180)
        btn_run.clicked.connect(self.run_docking)
        form.addRow("", btn_run)

        monitor_group = QGroupBox("Docking monitor")
        monitor_group.setMinimumWidth(480)
        monitor_group.setMaximumWidth(480)
        monitor_layout = QVBoxLayout(monitor_group)

        interval_row = QHBoxLayout()
        interval_row.addWidget(QLabel("Update interval"))
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
        monitor_form.addRow("Ligands docked", self.lbl_monitor_docked)
        monitor_form.addRow("Total ligands", self.lbl_monitor_total)
        monitor_form.addRow("Percent complete", self.lbl_monitor_percent)
        monitor_form.addRow("ETA", self.lbl_monitor_eta)
        monitor_form.addRow("Running time", self.lbl_monitor_running_time)
        monitor_form.addRow("Estim. completion", self.lbl_monitor_completion)
        monitor_layout.addLayout(monitor_form)
        monitor_layout.addStretch(1)

        self.monitor_timer = QTimer(self)
        self.monitor_timer.timeout.connect(self._refresh_docking_monitor)

        top_row = QHBoxLayout()
        top_row.addStretch(1)
        top_row.addWidget(group)
        top_row.addWidget(monitor_group)
        top_row.addStretch(1)
        layout.addLayout(top_row)

        self.pb_docking = QProgressBar()
        self.pb_docking.setValue(0)
        add_centered_group(self.pb_docking)
        self.txt_docking_log = QPlainTextEdit()
        self.txt_docking_log.setReadOnly(True)
        self.txt_docking_log.setFixedHeight(220)
        add_centered_group(self.txt_docking_log)
        layout.addStretch(1)
        layout.addLayout(self._nav_buttons_row(3, 5))
        self.tabs.addTab(tab, "STEP 4")
        self._refresh_result_folders()
        self._toggle_docking_mode_options()
        self._toggle_restart_combo()

    def _build_results_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(self._title("Step 5. View Results"))

        results_group_width = 1000

        def add_centered_group(widget: QWidget, group_width: int = results_group_width) -> None:
            widget.setMinimumWidth(group_width)
            widget.setMaximumWidth(group_width)
            row_wrap = QHBoxLayout()
            row_wrap.addStretch(1)
            row_wrap.addWidget(widget)
            row_wrap.addStretch(1)
            layout.addLayout(row_wrap)

        filters_box = QGroupBox("Result filters")
        filters_form = QFormLayout(filters_box)
        self.sp_result_top_n = QSpinBox(); self.sp_result_top_n.setRange(1, 100000)
        self.sp_result_rmsd = QDoubleSpinBox(); self.sp_result_rmsd.setRange(0.0, 1000.0); self.sp_result_rmsd.setDecimals(4)
        filters_form.addRow("Top ligands", self.sp_result_top_n)
        filters_form.addRow("RMSD threshold", self.sp_result_rmsd)
        add_centered_group(filters_box)

        controls_box = QGroupBox("Result controls")
        controls_layout = QVBoxLayout(controls_box)
        selectors_row = QHBoxLayout()
        self.cb_results_folder = QComboBox()
        self.cb_results_folder.setMaximumWidth(320)
        self.cb_results_target = QComboBox()
        self.cb_results_target.setMaximumWidth(260)
        self.cb_results_folder.currentTextChanged.connect(self._refresh_result_targets)
        btn_refresh = QPushButton("Refresh")
        btn_refresh.setFixedWidth(255)
        btn_refresh.clicked.connect(self._refresh_result_folders)
        btn_open = QPushButton("Open result folder")
        btn_open.setFixedWidth(255)
        btn_open.clicked.connect(self._open_current_result_folder)
        btn_load = QPushButton("Load raw CSV")
        btn_load.setFixedWidth(255)
        btn_load.clicked.connect(self.preview_selected_result)
        btn_filtered = QPushButton("Load filtered top results")
        btn_filtered.setFixedWidth(255)
        btn_filtered.clicked.connect(self.preview_filtered_result)
        btn_export = QPushButton("Export filtered CSV")
        btn_export.setFixedWidth(255)
        btn_export.clicked.connect(self.export_filtered_result)
        btn_plot = QPushButton("Plot filtered results")
        btn_plot.setFixedWidth(255)
        btn_plot.clicked.connect(self.plot_filtered_result)
        selectors_row.addStretch(1)
        selectors_row.addWidget(self.cb_results_folder)
        selectors_row.addWidget(self.cb_results_target)
        selectors_row.addStretch(1)
        controls_layout.addLayout(selectors_row)

        buttons_grid = QGridLayout()
        buttons_grid.setHorizontalSpacing(12)
        buttons_grid.setVerticalSpacing(10)
        buttons_grid.setAlignment(Qt.AlignCenter)
        result_buttons = [
            btn_refresh,
            btn_open,
            btn_load,
            btn_filtered,
            btn_export,
            btn_plot,
        ]
        for idx, button in enumerate(result_buttons):
            buttons_grid.addWidget(button, idx // 3, idx % 3)
        controls_layout.addLayout(buttons_grid)
        add_centered_group(controls_box)

        self.tbl_results = QTableWidget()
        self.tbl_results.setFixedHeight(500)
        add_centered_group(self.tbl_results)
        layout.addStretch(1)
        layout.addLayout(self._nav_buttons_row(4, None))
        self.tabs.addTab(tab, "STEP 5")
        self._refresh_result_folders()

    def _path_row(self, editor: QLineEdit, callback) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(editor)
        button = QPushButton("Browse")
        button.clicked.connect(callback)
        layout.addWidget(button)
        return widget

    def _browse_directory(self, current: str) -> Optional[str]:
        path = QFileDialog.getExistingDirectory(self, "Select directory", current)
        return path or None

    def _browse_ligands_dir(self) -> None:
        selected = self._browse_directory(self.ligands_dir)
        if selected:
            self.ligands_dir = selected
            self.ed_ligands_dir.setText(selected)
            self._save_settings()
            self._refresh_ligand_summary()

    def _browse_targets_dir(self) -> None:
        selected = self._browse_directory(self.targets_dir)
        if selected:
            self.targets_dir = selected
            self.ed_targets_dir.setText(selected)
            self._save_settings()
            self._refresh_targets_summary()

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

    def _refresh_ligand_summary(self) -> None:
        group_count = 0
        ligand_count = 0
        if os.path.isdir(self.ligands_dir):
            for group in Path(self.ligands_dir).glob("*/"):
                group_count += 1
                ligand_count += len(list(group.glob("*.pdbqt")))
        self.lbl_lig_summary.setText(
            f"Ligand groups: {group_count} | PDBQT ligands: {ligand_count} | Directory: {self.ligands_dir}\n"
            f"Conversion results: {self.conversion_results_dir}"
        )

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
        if hasattr(self, "cb_lig_speed_first"):
            self.ligand_settings.speed_first = self.cb_lig_speed_first.currentText().strip()
        if hasattr(self, "cb_lig_speed_second"):
            self.ligand_settings.speed_second = self.cb_lig_speed_second.currentText().strip()
        if hasattr(self, "sp_lig_timeout_first"):
            self.ligand_settings.timeout_first = self.sp_lig_timeout_first.value()
        if hasattr(self, "sp_lig_timeout_second"):
            self.ligand_settings.timeout_second = self.sp_lig_timeout_second.value()
        if hasattr(self, "sp_lig_steps"):
            self.ligand_settings.minimization_steps = self.sp_lig_steps.value()
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

    def _apply_ligand_settings_to_widgets(self) -> None:
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
        if hasattr(self, "sp_lig_workers"):
            self.sp_lig_workers.setValue(self.ligand_settings.conversion_workers)
        if hasattr(self, "cb_lig_speed_first"):
            self.cb_lig_speed_first.setCurrentText(self.ligand_settings.speed_first)
        if hasattr(self, "cb_lig_speed_second"):
            self.cb_lig_speed_second.setCurrentText(self.ligand_settings.speed_second)
        if hasattr(self, "sp_lig_timeout_first"):
            self.sp_lig_timeout_first.setValue(self.ligand_settings.timeout_first)
        if hasattr(self, "sp_lig_timeout_second"):
            self.sp_lig_timeout_second.setValue(self.ligand_settings.timeout_second)
        if hasattr(self, "sp_lig_steps"):
            self.sp_lig_steps.setValue(self.ligand_settings.minimization_steps)
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

    def _run_ligand_tool(self, operation: str) -> None:
        self._save_settings()
        self.pb_ligand.setValue(0)
        self.txt_ligand_log.clear()
        self.ligand_worker = LigandToolsWorker(
            app_dir=self.app_dir,
            ligands_dir=self.ligands_dir,
            conversion_dir=self.conversion_results_dir,
            settings=self.ligand_settings,
            operation=operation,
        )
        self.ligand_worker.progress_value.connect(self.pb_ligand.setValue)
        self.ligand_worker.progress_text.connect(self.txt_ligand_log.appendPlainText)
        self.ligand_worker.finished_ok.connect(self._on_ligand_tool_finished)
        self.ligand_worker.failed.connect(self._on_ligand_tool_failed)
        self.ligand_worker.start()

    def _on_ligand_tool_finished(self, message: str) -> None:
        self.pb_ligand.setValue(100)
        self.txt_ligand_log.appendPlainText(message)
        self._refresh_ligand_summary()
        QMessageBox.information(self, APP_NAME, message)

    def _on_ligand_tool_failed(self, message: str) -> None:
        self.txt_ligand_log.appendPlainText(message)
        QMessageBox.critical(self, APP_NAME, message)

    def _refresh_targets_summary(self) -> None:
        lines = []
        for target in sorted(Path(self.targets_dir).glob("*/")):
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
            self.targets_dir,
            "Structure files (*.pdb *.pdbqt *.mol2 *.ent *.txt);;All files (*)",
        )
        if file_path:
            self.ed_target_file.setText(file_path)

    def _choose_pdbqt_file(self, editor: QLineEdit, title: str) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            title,
            self.targets_dir,
            "PDBQT files (*.pdbqt);;All files (*)",
        )
        if file_path:
            editor.setText(file_path)

    def _choose_grid_file(self, editor: QLineEdit, title: str) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            title,
            self.targets_dir,
            "Grid files (*.txt);;All files (*)",
        )
        if file_path:
            editor.setText(file_path)

    def _toggle_target_mode(self) -> None:
        flexible_mode = hasattr(self, "cb_target_mode") and self.cb_target_mode.currentIndex() == 1
        self.ed_target_file.setEnabled(not flexible_mode)
        self.sp_target_ph.setEnabled(not flexible_mode)
        self.ed_target_rigid_file.setEnabled(flexible_mode)
        self.ed_target_flex_file.setEnabled(flexible_mode)

    def _populate_prepared_targets(self) -> None:
        if not hasattr(self, "cb_prepared_targets"):
            return
        current = self.cb_prepared_targets.currentText().strip()
        self.cb_prepared_targets.blockSignals(True)
        self.cb_prepared_targets.clear()
        targets = [path.name for path in sorted(Path(self.targets_dir).glob("*/")) if path.is_dir()]
        self.cb_prepared_targets.addItems(targets)
        if current and current in targets:
            self.cb_prepared_targets.setCurrentText(current)
        self.cb_prepared_targets.blockSignals(False)

    def _open_selected_target_folder(self) -> None:
        target_name = self.cb_prepared_targets.currentText().strip() if hasattr(self, "cb_prepared_targets") else ""
        if target_name:
            self._open_path(os.path.join(self.targets_dir, target_name))

    def _remove_selected_target(self) -> None:
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
        self._refresh_result_folders()

    def prepare_target(self) -> None:
        flexible_mode = self.cb_target_mode.currentIndex() == 1 if hasattr(self, "cb_target_mode") else False
        target_name_input = self.ed_target_name.text().strip() if hasattr(self, "ed_target_name") else ""

        if flexible_mode:
            rigid_file = self.ed_target_rigid_file.text().strip()
            flex_file = self.ed_target_flex_file.text().strip()
            grid_file = self.ed_target_grid_file.text().strip()
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
            shutil.copy2(rigid_file, os.path.join(target_dir, "protein_rigid.pdbqt"))
            shutil.copy2(flex_file, os.path.join(target_dir, "protein_flex.pdbqt"))
            if grid_file and os.path.isfile(grid_file):
                shutil.copy2(grid_file, os.path.join(target_dir, "grid.txt"))
            else:
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
            shutil.copy2(target_file, copied_target)
            protein_out = os.path.join(target_dir, "protein.pdbqt")
            grid_path = os.path.join(target_dir, "grid.txt")
            grid_file = self.ed_target_grid_file.text().strip()
            if grid_file and os.path.isfile(grid_file):
                shutil.copy2(grid_file, grid_path)
            else:
                self._write_grid_file(grid_path, target_base)

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

        self._refresh_targets_summary()
        self._populate_prepared_targets()
        self._refresh_result_folders()

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

    def _toggle_restart_combo(self) -> None:
        is_restart = self.cb_run_type.currentText() == "RESTART"
        self.cb_existing_result.setEnabled(is_restart)

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

    def _refresh_result_folders(self) -> None:
        folders = [path.name for path in sorted(Path(self.results_dir).glob("*/"))]
        if hasattr(self, "cb_existing_result"):
            self.cb_existing_result.clear()
            self.cb_existing_result.addItems(folders)
        if hasattr(self, "cb_results_folder"):
            self.cb_results_folder.clear()
            self.cb_results_folder.addItems(folders)
        if hasattr(self, "cb_results_target") and hasattr(self, "cb_results_folder"):
            self._refresh_result_targets()

    def _refresh_result_targets(self) -> None:
        if not hasattr(self, "cb_results_target") or not hasattr(self, "cb_results_folder"):
            return
        self.cb_results_target.clear()
        result_name = self.cb_results_folder.currentText().strip()
        if not result_name:
            return
        result_dir = Path(self.results_dir) / result_name
        targets = [path.name for path in sorted(result_dir.glob("*/")) if path.is_dir()]
        self.cb_results_target.addItem("All targets")
        self.cb_results_target.addItems(targets)

    def _open_current_result_folder(self) -> None:
        result_name = self.cb_results_folder.currentText().strip()
        if result_name:
            self._open_path(os.path.join(self.results_dir, result_name))

    def _open_path(self, path: str) -> None:
        if not path or not os.path.exists(path):
            QMessageBox.warning(self, APP_NAME, f"Path not found: {path}")
            return
        subprocess.Popen(["xdg-open", path])

    def _collect_settings_from_widgets(self) -> None:
        self.settings.scoring_function = self.cb_scoring.currentText().strip()
        if hasattr(self, "cb_docking_mode"):
            self.settings.docking_mode = self.cb_docking_mode.currentText().strip()
        if hasattr(self, "cb_opencl_platform"):
            platform_id = self.cb_opencl_platform.currentData()
            self.settings.opencl_platform_id = int(platform_id) if platform_id is not None else -1
        if hasattr(self, "cb_opencl_device"):
            device_id = self.cb_opencl_device.currentData()
            self.settings.opencl_device_id = int(device_id) if device_id is not None else -1
        self.settings.split_results = self.cb_split.currentText().strip() == "yes"
        self.settings.cpu_threads = self.sp_cpu_threads.value()
        self.settings.cpu_parallelism = self.sp_cpu_parallel.value()
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
        self._collect_result_settings_from_widgets()

    def _apply_settings_to_widgets(self) -> None:
        if hasattr(self, "cb_scoring"):
            self.cb_scoring.setCurrentText(self.settings.scoring_function)
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
        if hasattr(self, "sp_cpu_parallel"):
            self.sp_cpu_parallel.setValue(self.settings.cpu_parallelism)
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
        if hasattr(self, "ed_ligands_dir"):
            self.ed_ligands_dir.setText(self.ligands_dir)
        if hasattr(self, "ed_targets_dir"):
            self.ed_targets_dir.setText(self.targets_dir)
        self._apply_ligand_settings_to_widgets()
        self._apply_result_settings_to_widgets()

    def _save_settings(self) -> None:
        self._collect_settings_from_widgets()
        self.results_dir = os.path.join(self.app_dir, "RESULTS", "DOCKING")
        self.conversion_results_dir = os.path.join(self.app_dir, "RESULTS", "CONVERSION")
        self.bin_dir = os.path.join(self.app_dir, "bin")
        payload = {
            "ligands_dir": self.ed_ligands_dir.text().strip(),
            "targets_dir": self.ed_targets_dir.text().strip(),
            "results_dir": self.results_dir,
            "bin_dir": self.bin_dir,
            "docking": asdict(self.settings),
            "ligand": asdict(self.ligand_settings),
            "results_view": asdict(self.result_view_settings),
        }
        self.ligands_dir = payload["ligands_dir"]
        self.targets_dir = payload["targets_dir"]
        self.results_dir = payload["results_dir"]
        self.bin_dir = payload["bin_dir"]
        with open(self.settings_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        self._refresh_ligand_summary()
        self._refresh_targets_summary()
        self._refresh_result_folders()

    def _load_settings(self) -> None:
        if not os.path.isfile(self.settings_path):
            return
        try:
            with open(self.settings_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            self.ligands_dir = payload.get("ligands_dir", self.ligands_dir)
            self.targets_dir = payload.get("targets_dir", self.targets_dir)
            self.results_dir = os.path.join(self.app_dir, "RESULTS", "DOCKING")
            self.conversion_results_dir = os.path.join(self.app_dir, "RESULTS", "CONVERSION")
            self.bin_dir = os.path.join(self.app_dir, "bin")
            docking = payload.get("docking", {})
            ligand = payload.get("ligand", {})
            results_view = payload.get("results_view", {})
            self.settings = DockingSettings(**{**asdict(self.settings), **docking})
            self.ligand_settings = LigandSettings(**{**asdict(self.ligand_settings), **ligand})
            self.result_view_settings = ResultViewSettings(**{**asdict(self.result_view_settings), **results_view})
        except Exception as exc:
            QMessageBox.warning(self, APP_NAME, f"Failed to load settings: {exc}")

    def _docking_monitor_path(self) -> str:
        return os.path.join(self.app_dir, ".track_progress.log")

    def _update_monitor_interval(self) -> None:
        if not hasattr(self, "monitor_timer"):
            return
        seconds = self.cb_monitor_interval.currentData()
        if seconds and self.monitor_timer.isActive():
            self.monitor_timer.setInterval(int(seconds) * 1000)

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
        self._save_settings()
        self.pb_docking.setValue(0)
        self.txt_docking_log.clear()
        self._reset_docking_monitor()
        selected_result = self.cb_existing_result.currentText().strip() if self.cb_run_type.currentText() == "RESTART" else ""
        self.worker = DockingWorker(
            app_dir=self.app_dir,
            ligands_dir=self.ligands_dir,
            targets_dir=self.targets_dir,
            results_dir=self.results_dir,
            settings=self.settings,
            docking_type=self.cb_docking_type.currentText().strip(),
            processing_type=self.cb_processing_type.currentText().strip(),
            run_type=self.cb_run_type.currentText().strip(),
            selected_result=selected_result,
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
        self._refresh_result_folders()
        QMessageBox.information(self, APP_NAME, message)

    def _on_docking_failed(self, message: str) -> None:
        self.monitor_timer.stop()
        self.txt_docking_log.appendPlainText(message)
        QMessageBox.critical(self, APP_NAME, message)

    def preview_selected_result(self) -> None:
        result_name = self.cb_results_folder.currentText().strip()
        target_name = self.cb_results_target.currentText().strip()
        if not result_name:
            QMessageBox.warning(self, APP_NAME, "Select a result folder first.")
            return
        result_folder = os.path.join(self.results_dir, result_name)
        if not os.path.isdir(result_folder):
            QMessageBox.warning(self, APP_NAME, f"Result folder not found: {result_folder}")
            return
        try:
            csv_path = self._rebuild_result_csv(result_folder)
        except OSError as exc:
            QMessageBox.critical(self, APP_NAME, f"Failed to rebuild the result CSV:\n{exc}")
            return
        frame = self._load_result_dataframe(csv_path)
        frame = self._filter_frame_by_target(frame, target_name)
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
        default_name = os.path.join(self.results_dir, result_name, f"{target_slug}_top{self.result_view_settings.top_results}.csv")
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
        default_path = os.path.join(self.results_dir, result_name, f"{target_slug}_top{self.result_view_settings.top_results}.png")
        file_path, _ = QFileDialog.getSaveFileName(parent, "Save chart", default_path, "PNG (*.png);;SVG (*.svg);;PDF (*.pdf)")
        if not file_path:
            return
        fig.savefig(file_path, bbox_inches="tight", dpi=300)
        QMessageBox.information(self, APP_NAME, f"Chart saved to {file_path}.")

    def _run_csv_path(self, result_folder: str) -> str:
        return os.path.join(result_folder, f"{os.path.basename(result_folder)}.csv")

    def _rebuild_result_csv(self, result_folder: str) -> str:
        """Rescan every ligand PDBQT under a result folder and rewrite its unified CSV."""
        csv_path = self._run_csv_path(result_folder)
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

    def _build_filtered_result_frame(self) -> tuple[Any, str, str]:
        self._collect_result_settings_from_widgets()
        result_name = self.cb_results_folder.currentText().strip()
        target_name = self.cb_results_target.currentText().strip()
        if not result_name:
            raise RuntimeError("Select a result folder first.")
        csv_path = self._run_csv_path(os.path.join(self.results_dir, result_name))
        if not os.path.isfile(csv_path):
            raise RuntimeError(f"Result CSV not found: {csv_path}. Click 'Load raw CSV' first.")
        frame = self._load_result_dataframe(csv_path)
        frame = self._filter_frame_by_target(frame, target_name)
        columns = self._locate_result_columns(frame)
        energy_col, rmsd_col = columns["energy"], columns["rmsd"]
        if energy_col is None or rmsd_col is None:
            raise RuntimeError("The result file does not contain recognizable BINDING ENERGY and RMSD columns.")
        filtered = frame.copy()
        filtered[energy_col] = pd.to_numeric(filtered[energy_col], errors="coerce")
        filtered[rmsd_col] = pd.to_numeric(filtered[rmsd_col], errors="coerce")
        filtered = filtered[filtered[rmsd_col] < self.result_view_settings.rmsd_limit]
        filtered = filtered.sort_values(by=energy_col, ascending=True).head(self.result_view_settings.top_results)
        return filtered.reset_index(drop=True), result_name, target_name

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

    def launch_legacy_codoc(self) -> None:
        if not os.path.isfile(self.legacy_codoc):
            QMessageBox.warning(self, APP_NAME, f"Legacy script not found: {self.legacy_codoc}")
            return
        subprocess.Popen(["bash", self.legacy_codoc], cwd=os.path.dirname(self.legacy_codoc))

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
    app = QApplication(sys.argv)
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
