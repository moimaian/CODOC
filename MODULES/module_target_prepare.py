# -*- coding: utf-8 -*-
# pyright: reportAttributeAccessIssue=false

"""Receptor preparation with pH/microenvironment-aware protonation.

This module reproduces everything AutoDockTools' ``prepare_receptor4.py``
already does (strip everything that is not the protein, repair/complete
hydrogens, assign Gasteiger charges and write AutoDock4 PDBQT atom types)
by delegating that proven pipeline to ADFRsuite's ``prepare_receptor``
binary, but it first runs a dedicated protonation step with PDB2PQR/PROPKA
so that every ionizable side chain (Asp, Glu, His, Cys, Tyr, Lys, Arg and
the N-/C-termini) is protonated according to its own pKa, computed from the
local 3D microenvironment, at the pH chosen by the user -- instead of the
generic, pH-blind hydrogen placement ``prepare_receptor`` performs on its
own.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

PDB2PQR_FORCEFIELD = "AMBER"

_IONIZABLE_RESIDUES = {"ASP", "GLU", "HIS", "CYS", "TYR", "LYS", "ARG", "N+", "C-"}

_PKA_LINE_RE = re.compile(
    r"^\s*([A-Za-z][A-Za-z0-9+\-]{0,2})\s*(-?\d+)\s+([A-Za-z0-9])\s+(-?\d+\.\d+)\*?\s+(-?\d+\.\d+)"
)


class TargetPrepareError(RuntimeError):
    """Raised when any step of the receptor preparation pipeline fails."""


@dataclass
class ResiduePka:
    residue: str
    resnum: str
    chain: str
    pka: float
    model_pka: float


@dataclass
class ReceptorPrepareResult:
    pdbqt_path: str
    ph: float
    pka_table: List[ResiduePka]
    log: str
    log_path: Optional[str] = None


def _which_or_none(name: str) -> Optional[str]:
    return shutil.which(name)


def find_pdb2pqr(venv_bin_dir: Optional[str] = None) -> str:
    candidates: List[Optional[str]] = []
    if venv_bin_dir:
        candidates.append(os.path.join(venv_bin_dir, "pdb2pqr30"))
        candidates.append(os.path.join(venv_bin_dir, "pdb2pqr"))
    candidates.append(_which_or_none("pdb2pqr30"))
    candidates.append(_which_or_none("pdb2pqr"))
    for candidate in candidates:
        if candidate and os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    raise TargetPrepareError(
        "pdb2pqr (PROPKA-based protonation engine) was not found.\n"
        "Install the 'pdb2pqr' Python package (it pulls in 'propka' automatically) "
        "via 'Install Requirements' before preparing a target."
    )


def find_prepare_receptor() -> str:
    path = os.path.join(str(Path.home()), "ADFRsuite-1.0", "bin", "prepare_receptor")
    if not os.path.isfile(path):
        raise TargetPrepareError(f"prepare_receptor was not found at {path}.")
    return path


def _run(cmd: List[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


def _normalize_to_pdb(input_path: str, work_dir: str) -> str:
    """Convert any receptor source format supported by CODOC into a plain PDB.

    PDB2PQR only reliably parses PDB/mmCIF, while target files selected in
    STEP 3 may be .pdb, .pdbqt, .mol2 or .ent. Open Babel (already a CODOC
    dependency) normalizes any of those into a clean PDB before protonation.
    """
    if Path(input_path).suffix.lower() in (".pdb", ".ent"):
        return input_path
    obabel = _which_or_none("obabel")
    if not obabel:
        raise TargetPrepareError(
            f"Open Babel ('obabel') is required to convert {input_path} to PDB before protonation."
        )
    normalized_path = os.path.join(work_dir, "input_normalized.pdb")
    result = _run([obabel, input_path, "-O", normalized_path])
    if result.returncode != 0 or not os.path.isfile(normalized_path):
        raise TargetPrepareError(f"Failed to convert {input_path} to PDB with Open Babel:\n{result.stdout}")
    return normalized_path


def _parse_pka_table(pdb2pqr_stdout: str, ph: float) -> List[ResiduePka]:
    lines = pdb2pqr_stdout.splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if "SUMMARY OF THIS PREDICTION" in line) + 2
    except StopIteration:
        return []

    table: List[ResiduePka] = []
    for line in lines[start:]:
        if not line.strip():
            break
        match = _PKA_LINE_RE.match(line)
        if not match:
            continue
        residue, resnum, chain, pka_text, model_pka_text = match.groups()
        residue = residue.strip()
        if residue not in _IONIZABLE_RESIDUES:
            continue
        table.append(
            ResiduePka(
                residue=residue,
                resnum=resnum,
                chain=chain,
                pka=float(pka_text),
                model_pka=float(model_pka_text),
            )
        )
    return table


def summarize_pka_table(pka_table: List[ResiduePka], ph: float) -> str:
    if not pka_table:
        return f"PROPKA did not report any ionizable residue at pH {ph:.2f}."

    def protonated_at(pka: float) -> bool:
        return ph < pka

    altered = [r for r in pka_table if protonated_at(r.pka) != protonated_at(r.model_pka)]
    lines = [f"PROPKA evaluated {len(pka_table)} ionizable residue(s) at pH {ph:.2f}."]
    if altered:
        lines.append(
            f"{len(altered)} residue(s) shifted from the standard protonation state "
            "due to their local microenvironment:"
        )
        for residue in altered:
            state = "protonated" if protonated_at(residue.pka) else "deprotonated"
            lines.append(
                f"  - {residue.residue}{residue.resnum} {residue.chain}: "
                f"pKa {residue.pka:.2f} (model {residue.model_pka:.2f}) -> {state}"
            )
    else:
        lines.append("All ionizable residues kept their standard protonation state at this pH.")
    return "\n".join(lines)


def prepare_receptor_with_protonation(
    input_path: str,
    output_pdbqt_path: str,
    ph: float = 7.4,
    venv_bin_dir: Optional[str] = None,
    log_path: Optional[str] = None,
) -> ReceptorPrepareResult:
    """Prepare a rigid receptor PDBQT with pH-aware protonation.

    Performs, in order:
      1. Normalize the input structure to PDB (Open Babel) if needed.
      2. Run PDB2PQR with PROPKA titration at the requested pH: this removes
         waters and any non-protein heteroatoms (ligands, cofactors, ions)
         and rebuilds hydrogens according to the per-residue pKa computed
         from the 3D microenvironment.
      3. Hand the protonated structure to ADFRsuite's ``prepare_receptor``
         (``-A checkhydrogens`` keeps the hydrogens just placed, ``-e`` is
         kept as a safety net) to assign Gasteiger charges, AutoDock4 atom
         types and write the final PDBQT -- i.e. every function
         ``prepare_receptor4.py`` performed before.
    """
    if not os.path.isfile(input_path):
        raise TargetPrepareError(f"Target file not found: {input_path}")

    pdb2pqr = find_pdb2pqr(venv_bin_dir)
    prepare_receptor = find_prepare_receptor()

    work_dir = tempfile.mkdtemp(prefix="codoc_target_prep_")
    try:
        normalized_pdb = _normalize_to_pdb(input_path, work_dir)
        protonated_pdb = os.path.join(work_dir, "protonated.pdb")
        pqr_path = os.path.join(work_dir, "protonated.pqr")

        pdb2pqr_cmd = [
            pdb2pqr,
            "--ff", PDB2PQR_FORCEFIELD,
            "--titration-state-method", "propka",
            "--with-ph", f"{ph}",
            "--drop-water",
            "--pdb-output", protonated_pdb,
            normalized_pdb,
            pqr_path,
        ]
        pdb2pqr_result = _run(pdb2pqr_cmd)
        if pdb2pqr_result.returncode != 0 or not os.path.isfile(protonated_pdb):
            raise TargetPrepareError(
                f"PROPKA/PDB2PQR protonation failed at pH {ph:.2f}:\n{pdb2pqr_result.stdout}"
            )

        pka_table = _parse_pka_table(pdb2pqr_result.stdout, ph)

        receptor_cmd = [
            prepare_receptor,
            "-r", protonated_pdb,
            "-o", output_pdbqt_path,
            "-A", "checkhydrogens",
            "-e",
        ]
        receptor_result = _run(receptor_cmd)
        if receptor_result.returncode != 0 or not os.path.isfile(output_pdbqt_path):
            raise TargetPrepareError(
                f"prepare_receptor failed while writing the PDBQT:\n{receptor_result.stdout}"
            )

        log_text = "\n".join(
            [
                f"[PDB2PQR/PROPKA] Protonation at pH {ph:.2f}",
                pdb2pqr_result.stdout.strip(),
                "",
                "[prepare_receptor] PDBQT generation",
                receptor_result.stdout.strip(),
                "",
                summarize_pka_table(pka_table, ph),
            ]
        )

        saved_log_path = None
        if log_path:
            try:
                Path(log_path).write_text(log_text, encoding="utf-8")
                saved_log_path = log_path
            except OSError:
                saved_log_path = None

        return ReceptorPrepareResult(
            pdbqt_path=output_pdbqt_path,
            ph=ph,
            pka_table=pka_table,
            log=log_text,
            log_path=saved_log_path,
        )
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
