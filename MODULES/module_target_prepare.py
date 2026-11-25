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

import csv
import importlib.util
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from MODULES import platform_utils

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
    engine: str = ""            # what wrote the PDBQT: "ADFRsuite prepare_receptor" or "Meeko mk_prepare_receptor"


def _which_or_none(name: str) -> Optional[str]:
    return shutil.which(name)


def _venv_scripts_dir() -> str:
    """Pasta dos executáveis do venv do CODOC (Scripts\\ no Windows, bin/ no Linux)."""
    return platform_utils.venv_scripts_dir(platform_utils.default_venv_dir())


def find_pdb2pqr(venv_bin_dir: Optional[str] = None) -> str:
    candidates: List[Optional[str]] = []
    venv_bin_dir = venv_bin_dir or _venv_scripts_dir()
    suffixes = ("", ".exe") if platform_utils.IS_WINDOWS else ("",)
    for suffix in suffixes:
        candidates.append(os.path.join(venv_bin_dir, "pdb2pqr30" + suffix))
        candidates.append(os.path.join(venv_bin_dir, "pdb2pqr" + suffix))
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


ENGINE_ADFR = "ADFRsuite prepare_receptor"
ENGINE_MEEKO = "Meeko mk_prepare_receptor"

# The SG-SG distance of a disulfide bridge is 2.05 A; crystal structures and the PDB2PQR output show up to ~2.6 A.
_DISULFIDE_MAX_DISTANCE = 2.6


def meeko_available() -> bool:
    """True when the Meeko package (already used for the ligands) can prepare the receptor too."""
    return importlib.util.find_spec("meeko") is not None


def available_receptor_engines() -> List[str]:
    """The PDBQT writers that can run now, in the order CODOC tries them: ADFRsuite when it is installed (the
    reference tool), otherwise - or when it fails - Meeko, which needs nothing beyond the pip packages."""
    engines = []
    if platform_utils.find_adfr_prepare_receptor():
        engines.append(ENGINE_ADFR)
    if meeko_available():
        engines.append(ENGINE_MEEKO)
    return engines


def _venv_python() -> str:
    python = os.path.join(_venv_scripts_dir(), "python.exe" if platform_utils.IS_WINDOWS else "python")
    return python if os.path.isfile(python) else sys.executable


def _protein_only_pdb(protonated_pdb: str, destination: str) -> int:
    """Copy of the PDB2PQR output for Meeko: only ATOM records (PDB2PQR keeps the co-crystallised ligands as
    HETATM, which Meeko refuses; ADFRsuite drops them by itself) and disulfide cysteines named CYX without
    their HG, as Meeko needs. Returns the number of disulfide bridges found."""
    with open(protonated_pdb, "r", encoding="utf-8", errors="replace") as handle:
        lines = [line for line in handle if not line.startswith("HETATM")]
    sulfurs = {}
    for line in lines:
        if line.startswith("ATOM") and line[12:16].strip() == "SG" and line[17:20] == "CYS":
            sulfurs[(line[21], line[22:27])] = (float(line[30:38]), float(line[38:46]), float(line[46:54]))
    keys = list(sulfurs)
    bridged = set()
    for i, first in enumerate(keys):
        for second in keys[i + 1:]:
            if math.dist(sulfurs[first], sulfurs[second]) <= _DISULFIDE_MAX_DISTANCE:
                bridged.update((first, second))
    cleaned = []
    for line in lines:
        if line.startswith("ATOM") and (line[21], line[22:27]) in bridged:
            if line[12:16].strip() == "HG":
                continue
            line = line[:17] + "CYX" + line[20:]
        cleaned.append(line)
    with open(destination, "w", encoding="utf-8") as handle:
        handle.writelines(cleaned)
    return len(bridged) // 2


def _write_pdbqt_with_adfr(protonated_pdb: str, output_pdbqt_path: str) -> Tuple[bool, str]:
    prepare_receptor = platform_utils.find_adfr_prepare_receptor()
    if prepare_receptor is None:
        return False, "ADFRsuite prepare_receptor is not installed."
    # prepare_receptor (a shell/Python 2 script) fails when a path has a space - a project name never has one, but
    # the folder of a Windows user may -, so it writes inside the temporary folder and the file is copied after.
    scratch = os.path.join(os.path.dirname(protonated_pdb), "adfr_receptor.pdbqt")
    result = _run([prepare_receptor, "-r", protonated_pdb, "-o", scratch, "-A", "checkhydrogens", "-e"])
    ok = result.returncode == 0 and os.path.isfile(scratch)
    if ok:
        shutil.copyfile(scratch, output_pdbqt_path)
    return ok, result.stdout.strip()


def _write_pdbqt_with_meeko(protonated_pdb: str, output_pdbqt_path: str, work_dir: str) -> Tuple[bool, str]:
    if not meeko_available():
        return False, "Meeko is not installed (Install Requirements > Python Libraries > meeko)."
    protein_pdb = os.path.join(work_dir, "protonated_protein_only.pdb")
    bridges = _protein_only_pdb(protonated_pdb, protein_pdb)
    if os.path.isfile(output_pdbqt_path):
        os.remove(output_pdbqt_path)
    # Charges are Gasteiger, as in AutoDock; the heavy-atom coordinates and hydrogens are the ones PDB2PQR placed.
    code = "import sys; from meeko.cli.mk_prepare_receptor import main; sys.argv[0] = 'mk_prepare_receptor'; sys.exit(main())"
    result = _run([_venv_python(), "-c", code, "--read_pdb", protein_pdb, "-o", os.path.join(work_dir, "meeko_receptor"),
                   "-p", output_pdbqt_path])
    ok = result.returncode == 0 and os.path.isfile(output_pdbqt_path)
    text = result.stdout.strip()
    if bridges:
        text += f"\n[{bridges} disulfide bridge(s) renamed CYX before Meeko]"
    return ok, text


def _run(cmd: List[str], env: Optional[dict] = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)


def _normalize_to_pdb(input_path: str, work_dir: str) -> str:
    """Convert any receptor source format supported by CODOC into a plain PDB.

    PDB2PQR only reliably parses PDB/mmCIF, while target files selected in
    STEP 2 may be .pdb, .pdbqt, .mol2 or .ent. Open Babel (already a CODOC
    dependency) normalizes any of those into a clean PDB before protonation.
    """
    if Path(input_path).suffix.lower() in (".pdb", ".ent"):
        return input_path
    obabel = platform_utils.find_obabel()
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
      3. Write the final PDBQT (Gasteiger charges, AutoDock4 atom types) with
         ADFRsuite's ``prepare_receptor`` (``-A checkhydrogens`` keeps the
         hydrogens just placed, ``-e`` is kept as a safety net) when it is
         installed and, if it is not or it fails, with Meeko's
         ``mk_prepare_receptor``. ``result.engine`` tells which one did.
    """
    if not os.path.isfile(input_path):
        raise TargetPrepareError(f"Target file not found: {input_path}")

    pdb2pqr = find_pdb2pqr(venv_bin_dir)
    engines = available_receptor_engines()
    if not engines:
        raise TargetPrepareError(
            "No program is available to write the receptor PDBQT. Install the Meeko package (Install Requirements > "
            "Python Libraries) or ADFRsuite (https://ccsb.scripps.edu/adfr/downloads/)."
        )

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

        # Step 3: the PDBQT (Gasteiger charges, AutoDock atom types, merged non-polar hydrogens). ADFRsuite first when
        # it is installed; if it is missing or fails, Meeko. Which one wrote the file goes to the log and the message.
        writers = {ENGINE_ADFR: lambda: _write_pdbqt_with_adfr(protonated_pdb, output_pdbqt_path),
                   ENGINE_MEEKO: lambda: _write_pdbqt_with_meeko(protonated_pdb, output_pdbqt_path, work_dir)}
        engine, attempts = "", []
        for candidate in engines:
            ok, text = writers[candidate]()
            if ok:
                engine = candidate
                receptor_output = text
                break
            attempts.append(f"[{candidate}] failed:\n{text}")
        if not engine:
            raise TargetPrepareError("The receptor PDBQT could not be written:\n\n" + "\n\n".join(attempts))
        if attempts:
            receptor_output = "\n\n".join(attempts) + f"\n\n[{engine}] used instead:\n{receptor_output}"

        log_text = "\n".join(
            [
                f"[PDB2PQR/PROPKA] Protonation at pH {ph:.2f}",
                pdb2pqr_result.stdout.strip(),
                "",
                f"[{engine}] PDBQT generation",
                receptor_output,
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
            engine=engine,
        )
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Heuristic pocket search (P2Rank)
# ---------------------------------------------------------------------------

P2RANK_INSTALL_HINT = (
    "P2Rank was not found. Install it with Install Requirements (External Programs: 'Java JRE 17 (P2Rank)' "
    "and 'P2Rank'), or by hand:\n"
    "  sudo apt install openjdk-17-jre-headless\n"
    "  wget https://github.com/rdk/p2rank/releases/download/2.5.1/p2rank_2.5.1.tar.gz\n"
    "  tar -xzf p2rank_2.5.1.tar.gz -C ~/\n"
    "Then export P2RANK_HOME=~/p2rank_2.5.1 or add its folder to PATH.\n"
    "P2Rank requires Java 17 or newer."
)
P2RANK_JAVA_HINT = (
    "P2Rank is a Java program and no Java was found. Install it with Install Requirements "
    "(External Programs: 'Java JRE 17 (P2Rank)') or: sudo apt install openjdk-17-jre-headless"
)


@dataclass
class Pocket:
    rank: int
    name: str
    score: float
    probability: Optional[float]
    center: Tuple[float, float, float]
    n_residues: int


def find_p2rank(search_root: Optional[str] = None) -> Optional[str]:
    """Locate the P2Rank ``prank`` launcher script.

    Search order: the ``P2RANK_HOME`` environment variable, PATH,
    ``<search_root>/BIN/p2rank*/prank`` (CODOC's own BIN folder, when a
    search_root is given) and finally the user's home directory and /opt --
    the two most common places a manual P2Rank install ends up in.
    """
    env_home = os.environ.get("P2RANK_HOME")
    if env_home:
        for launcher in platform_utils.p2rank_launcher_names():
            candidate = Path(env_home) / launcher
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return str(candidate)

    for launcher in platform_utils.p2rank_launcher_names():
        found = _which_or_none(launcher)
        if found:
            return found

    search_bases = []
    if search_root:
        search_bases.append(Path(search_root) / "BIN")
    search_bases.append(Path.home())
    if not platform_utils.IS_WINDOWS:
        search_bases.append(Path("/opt"))
    for base in search_bases:
        if not base.is_dir():
            continue
        try:
            for launcher in platform_utils.p2rank_launcher_names():
                for candidate in sorted(base.glob(f"p2rank*/{launcher}")):
                    if candidate.is_file() and os.access(candidate, os.X_OK):
                        return str(candidate)
        except OSError:
            continue
    return None


def detect_pockets_p2rank(
    structure_path: str,
    search_root: Optional[str] = None,
    max_pockets: int = 10,
) -> List[Pocket]:
    """Predict ligand-binding pockets with P2Rank, ranked by score.

    P2Rank (Krivak & Hoksza, 2018; MIT license) scores solvent-accessible
    surface points for ligandability and clusters the highest-scoring ones
    into pockets. It needs neither a co-crystallized ligand nor a homologous
    structure, which makes it a reasonable heuristic to seed the docking
    grid center when the target has no bound ligand to derive it from.

    ``structure_path`` may be any format STEP 2 accepts as a target file
    (.pdb, .pdbqt, .mol2, .ent) -- it is normalized to a plain PDB with the
    same Open Babel conversion used before protonation, since P2Rank picks
    its parser from the file extension and does not recognize .pdbqt/.mol2.

    Raises TargetPrepareError (with install instructions) if the ``prank``
    binary cannot be found, or if P2Rank runs but reports no pocket at all --
    deliberately, instead of silently falling back to some other guess.

    Returns pockets sorted by rank (best first): each has .center (x, y, z).
    """
    if not os.path.isfile(structure_path):
        raise TargetPrepareError(f"Target file not found: {structure_path}")

    prank = find_p2rank(search_root)
    if prank is None:
        raise TargetPrepareError(P2RANK_INSTALL_HINT)
    if platform_utils.find_java() is None:
        raise TargetPrepareError(P2RANK_JAVA_HINT)

    work_dir = tempfile.mkdtemp(prefix="codoc_p2rank_")
    try:
        pdb_for_p2rank = _normalize_to_pdb(structure_path, work_dir)
        # P2Rank picks its parser from the file extension - make sure it is
        # exactly ".pdb" even when _normalize_to_pdb returned the original
        # path unchanged under a recognized-but-different suffix (".ent").
        if Path(pdb_for_p2rank).suffix.lower() != ".pdb":
            renamed = os.path.join(work_dir, "input.pdb")
            shutil.copyfile(pdb_for_p2rank, renamed)
            pdb_for_p2rank = renamed

        out_dir = os.path.join(work_dir, "p2rank_out")
        result = _run([prank, "predict", "-f", pdb_for_p2rank, "-o", out_dir], env=platform_utils.java_environment())
        if result.returncode != 0:
            tail = "\n".join((result.stdout or "").strip().splitlines()[-6:])
            raise TargetPrepareError(
                f"P2Rank failed (exit code {result.returncode}):\n{tail}\n\n"
                "If the error mentions a class file version or "
                "UnsupportedClassVersionError, the installed Java is older than 17."
            )

        predictions = sorted(Path(out_dir).glob("*_predictions.csv"))
        if not predictions:
            raise TargetPrepareError(
                f"P2Rank finished without producing a *_predictions.csv file in {out_dir}. "
                "Check that the structure has a readable protein chain."
            )

        pockets: List[Pocket] = []
        with open(predictions[0], newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                # P2Rank's CSV header has leading spaces in the column names.
                record = {(key or "").strip(): (value or "").strip() for key, value in row.items()}
                try:
                    probability = record.get("probability")
                    pockets.append(
                        Pocket(
                            rank=int(record.get("rank") or len(pockets) + 1),
                            name=record.get("name") or f"pocket{len(pockets) + 1}",
                            score=float(record["score"]),
                            probability=float(probability) if probability else None,
                            center=(
                                float(record["center_x"]),
                                float(record["center_y"]),
                                float(record["center_z"]),
                            ),
                            n_residues=len([r for r in (record.get("residue_ids") or "").split() if r]),
                        )
                    )
                except (KeyError, ValueError):
                    continue
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

    if not pockets:
        raise TargetPrepareError(
            "P2Rank did not find any pocket in this structure. "
            "Enter the grid center coordinates manually."
        )

    pockets.sort(key=lambda pocket: pocket.rank)
    return pockets[:max_pockets]
