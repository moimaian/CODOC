# -*- coding: utf-8 -*-
"""Co-crystallized ligand tools for redocking (STEP 3 / STEP 5).

Three things a redocking study needs, all independent of PyQt:
  1. find the ligands already complexed in a PDB target (HETATM groups that are not water, ions
     or modified amino acids) and derive a docking grid (center + box size) from one of them;
  2. export that ligand into CODOC's LIGANDS folder (group "REDOCK") so it goes through the
     normal STEP 2 preparation, keeping the crystallographic pose aside as the reference;
  3. after docking, compare each docked pose against the reference pose (symmetry-aware,
     heavy-atom RMSD without re-alignment, since the receptor never moves).

Bond orders for the exported ligand come from the RCSB chemical-component SMILES when it can be
fetched (assigned onto the crystal geometry with RDKit), otherwise from Open Babel's perception.
The RMSD itself never depends on bond orders: both poses are compared through a distance-based
heavy-atom connectivity graph, so it works for PDBQT files written by either conversion engine.
"""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import urllib.request
from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple

try:
    import numpy as np
except Exception:  # pragma: no cover - numpy ships with the RDKit/pandas stack
    np = None

try:
    from rdkit import Chem
    from rdkit.Chem import AllChem
except Exception:  # pragma: no cover
    Chem = None
    AllChem = None

REDOCK_GROUP = "REDOCK"
REDOCK_REFERENCE_DIRNAME = "REDOCK_REFERENCE"
RCSB_CHEMCOMP_URL = "https://data.rcsb.org/rest/v1/core/chemcomp/{code}"

_WATER_NAMES = {"HOH", "WAT", "H2O", "DOD", "TIP", "TIP3", "SOL"}
_BACKBONE_ATOMS = {"N", "CA", "C", "O"}
_TWO_LETTER_ELEMENTS = {"CL", "BR", "FE", "ZN", "MG", "MN", "CU", "CO", "NI", "CA", "NA", "SE", "AL", "SI", "LI"}


class CocrystalError(RuntimeError):
    """Raised when a co-crystal ligand cannot be read, exported or compared."""


@dataclass
class CocrystalLigand:
    resname: str
    chain: str
    resnum: int
    icode: str
    # (atom name, element, (x, y, z), original PDB line)
    atoms: List[Tuple[str, str, Tuple[float, float, float], str]] = field(default_factory=list)

    @property
    def heavy_coords(self) -> List[Tuple[float, float, float]]:
        return [xyz for _name, element, xyz, _line in self.atoms if element != "H"]

    @property
    def n_heavy(self) -> int:
        return len(self.heavy_coords)

    @property
    def center(self) -> Tuple[float, float, float]:
        coords = self.heavy_coords
        count = max(1, len(coords))
        return tuple(sum(c[axis] for c in coords) / count for axis in range(3))  # type: ignore[return-value]

    @property
    def extent(self) -> Tuple[float, float, float]:
        coords = self.heavy_coords
        if not coords:
            return (0.0, 0.0, 0.0)
        return tuple(max(c[axis] for c in coords) - min(c[axis] for c in coords) for axis in range(3))  # type: ignore[return-value]

    @property
    def label(self) -> str:
        return f"{self.resname} {self.chain}{self.resnum}{self.icode} ({self.n_heavy} heavy atoms)".replace("  ", " ")

    def pdb_block(self) -> str:
        lines = []
        for _name, _element, _xyz, line in self.atoms:
            lines.append("HETATM" + line[6:] if line.startswith("ATOM") else line)
        return "\n".join(lines) + "\nEND\n"


def _element_from_pdb_line(line: str) -> str:
    element = line[76:78].strip() if len(line) >= 78 else ""
    if not element:
        name = line[12:16].strip()
        letters = re.sub(r"[^A-Za-z]", "", name)
        if len(letters) >= 2 and letters[:2].upper() in _TWO_LETTER_ELEMENTS and line[12:13].strip():
            element = letters[:2]
        else:
            element = letters[:1]
    element = element.capitalize()
    return "H" if element == "D" else element


def find_cocrystal_ligands(structure_path: str) -> List[CocrystalLigand]:
    """Return the HETATM groups of a PDB/ENT file that look like real ligands, largest first.

    Skipped: waters, single-atom groups (ions), residues listed in MODRES records and anything
    carrying a complete N/CA/C/O backbone (modified amino acids). Only the first model and the
    first alternate location are read."""
    suffix = os.path.splitext(structure_path)[1].lower()
    if suffix not in (".pdb", ".ent"):
        raise CocrystalError(
            "Co-crystal ligands can only be read from a PDB (.pdb/.ent) target file - "
            f"'{os.path.basename(structure_path)}' has no HETATM records to inspect."
        )
    if not os.path.isfile(structure_path):
        raise CocrystalError(f"Target file not found: {structure_path}")

    groups: dict[tuple, CocrystalLigand] = {}
    modres: set[str] = set()
    with open(structure_path, "r", encoding="utf-8", errors="ignore") as handle:
        for raw in handle:
            record = raw[:6].strip()
            if record == "MODRES":
                modres.add(raw[12:15].strip().upper())
            elif record == "ENDMDL":
                break
            elif record == "HETATM":
                line = raw.rstrip("\n")
                if len(line) < 54:
                    continue
                if line[16] not in (" ", "A", "1"):
                    continue
                resname = line[17:20].strip().upper()
                if resname in _WATER_NAMES:
                    continue
                try:
                    resnum = int(line[22:26])
                    xyz = (float(line[30:38]), float(line[38:46]), float(line[46:54]))
                except ValueError:
                    continue
                chain = line[21].strip()
                icode = line[26].strip()
                key = (resname, chain, resnum, icode)
                ligand = groups.setdefault(key, CocrystalLigand(resname, chain, resnum, icode))
                ligand.atoms.append((line[12:16].strip(), _element_from_pdb_line(line), xyz, line))

    ligands = []
    for ligand in groups.values():
        names = {name for name, _el, _xyz, _line in ligand.atoms}
        if ligand.resname in modres or _BACKBONE_ATOMS <= names:
            continue
        if ligand.n_heavy < 2:
            continue
        ligands.append(ligand)
    ligands.sort(key=lambda item: item.n_heavy, reverse=True)
    return ligands


def suggest_grid(
    ligand: CocrystalLigand, padding: float = 6.0, min_size: float = 20.0, max_size: float = 500.0
) -> Tuple[Tuple[float, float, float], Tuple[int, int, int]]:
    """Grid centered on the ligand's heavy-atom centroid, sized (in Angstrom, as CODOC's grid size
    is passed straight to Vina) as the ligand's extent plus `padding` on each side, never smaller
    than `min_size`."""
    sizes = tuple(
        int(min(max_size, max(min_size, math.ceil(extent + 2.0 * padding)))) for extent in ligand.extent
    )
    return ligand.center, sizes  # type: ignore[return-value]


# --------------------------------------------------------------------------------------
# Export for redocking
# --------------------------------------------------------------------------------------

def _rcsb_template_smiles(resname: str) -> Optional[str]:
    """Best-effort SMILES of a PDB chemical component (network); None on any failure."""
    try:
        request = urllib.request.Request(
            RCSB_CHEMCOMP_URL.format(code=resname), headers={"User-Agent": "CODOC/1.0 (redocking-export)"}
        )
        with urllib.request.urlopen(request, timeout=8) as response:
            data = json.loads(response.read().decode("utf-8", errors="replace"))
    except Exception:
        return None
    descriptor = data.get("rcsb_chem_comp_descriptor") or {}
    for key in ("smiles", "smiles_stereo"):
        if descriptor.get(key):
            return str(descriptor[key])
    for item in data.get("pdbx_chem_comp_descriptor") or []:
        if "SMILES" in str(item.get("type", "")).upper() and item.get("descriptor"):
            return str(item["descriptor"])
    return None


def _mol_with_bond_orders(ligand: CocrystalLigand) -> Tuple[Any, str]:
    """RDKit molecule (heavy atoms, crystal coordinates) with proper bond orders + method used."""
    if Chem is None:
        raise CocrystalError("RDKit is not available in the current environment.")
    block = ligand.pdb_block()
    raw = Chem.MolFromPDBBlock(block, sanitize=False, removeHs=False, proximityBonding=True)
    if raw is None:
        raise CocrystalError(f"RDKit could not read the coordinates of ligand {ligand.label}.")
    heavy = Chem.RemoveHs(raw, sanitize=False)

    smiles = _rcsb_template_smiles(ligand.resname)
    if smiles:
        try:
            template = Chem.MolFromSmiles(smiles)
            if template is not None:
                fixed = AllChem.AssignBondOrdersFromTemplate(template, heavy)
                Chem.SanitizeMol(fixed)
                return fixed, "RCSB chemical-component template"
        except Exception:
            pass

    obabel = shutil.which("obabel")
    if obabel:
        with tempfile.TemporaryDirectory(prefix="codoc_cocrystal_") as work_dir:
            pdb_path = os.path.join(work_dir, "ligand.pdb")
            sdf_path = os.path.join(work_dir, "ligand.sdf")
            with open(pdb_path, "w", encoding="utf-8") as handle:
                handle.write(block)
            subprocess.run(
                [obabel, pdb_path, "-O", sdf_path], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
            )
            if os.path.isfile(sdf_path):
                mol = Chem.MolFromMolFile(sdf_path, removeHs=False)
                if mol is not None:
                    return Chem.RemoveHs(mol), "Open Babel bond-order perception"
    raise CocrystalError(
        f"Could not determine bond orders for ligand {ligand.label}: no RCSB template was reachable "
        "and Open Babel could not perceive a valid molecule from the crystal coordinates."
    )


def reference_dir(app_dir: str) -> str:
    return os.path.join(app_dir, REDOCK_REFERENCE_DIRNAME)


def export_ligand_for_redocking(
    ligand: CocrystalLigand, ligand_name: str, target_name: str, ligands_dir: str, app_dir: str
) -> dict[str, str]:
    """Write the ligand as <ligands_dir>/REDOCK/<ligand_name>.sdf (picked up by STEP 2) and keep the
    crystallographic pose as <app_dir>/REDOCK_REFERENCE/<ligand_name>.pdb (+ .json naming the target
    it belongs to), for the STEP 5 redocking RMSD. The reference lives outside TARGETS/ on purpose:
    a TARGETS subfolder without grid.txt makes the docking run abort."""
    mol, method = _mol_with_bond_orders(ligand)
    mol.SetProp("_Name", ligand_name)

    group_dir = os.path.join(ligands_dir, REDOCK_GROUP)
    os.makedirs(group_dir, exist_ok=True)
    sdf_path = os.path.join(group_dir, f"{ligand_name}.sdf")
    writer = Chem.SDWriter(sdf_path)
    try:
        writer.write(mol)
    finally:
        writer.close()

    ref_dir = reference_dir(app_dir)
    os.makedirs(ref_dir, exist_ok=True)
    reference_path = os.path.join(ref_dir, f"{ligand_name}.pdb")
    with open(reference_path, "w", encoding="utf-8") as handle:
        handle.write(ligand.pdb_block())
    with open(os.path.join(ref_dir, f"{ligand_name}.json"), "w", encoding="utf-8") as handle:
        json.dump(
            {
                "target": target_name,
                "resname": ligand.resname,
                "chain": ligand.chain,
                "resnum": ligand.resnum,
                "bond_orders": method,
            },
            handle,
            indent=2,
        )
    return {
        "sdf_path": sdf_path,
        "reference_path": reference_path,
        "smiles": Chem.MolToSmiles(mol),
        "method": method,
    }


def load_reference_info(app_dir: str, ligand_name: str) -> Optional[dict[str, Any]]:
    path = os.path.join(reference_dir(app_dir), f"{ligand_name}.json")
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            info = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None
    info["reference_path"] = os.path.join(reference_dir(app_dir), f"{ligand_name}.pdb")
    return info if os.path.isfile(info["reference_path"]) else None


# --------------------------------------------------------------------------------------
# Redocking RMSD
# --------------------------------------------------------------------------------------

def _pdbqt_element(atom_type: str, atom_name: str) -> str:
    """AutoDock atom type -> element (A = aromatic C, NA/OA/SA = acceptors, HD = polar H)."""
    mapping = {"A": "C", "NA": "N", "OA": "O", "SA": "S", "HD": "H", "HS": "H"}
    if atom_type in mapping:
        return mapping[atom_type]
    letters = re.sub(r"[^A-Za-z]", "", atom_type) or re.sub(r"[^A-Za-z]", "", atom_name)
    if len(letters) >= 2 and letters[:2].upper() in _TWO_LETTER_ELEMENTS:
        return letters[:2].capitalize()
    return letters[:1].upper()


def read_pdbqt_poses(path: str) -> List[List[Tuple[str, Tuple[float, float, float]]]]:
    """Heavy atoms (element, xyz) of every MODEL of a PDBQT (a single pose if it has no MODEL)."""
    poses: List[List[Tuple[str, Tuple[float, float, float]]]] = []
    current: List[Tuple[str, Tuple[float, float, float]]] = []
    with open(path, "r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            if line.startswith("ENDMDL"):
                poses.append(current)
                current = []
            elif line.startswith(("ATOM", "HETATM")) and len(line) >= 54:
                tokens = line.split()
                try:
                    xyz = (float(line[30:38]), float(line[38:46]), float(line[46:54]))
                except ValueError:
                    continue
                element = _pdbqt_element(tokens[-1] if len(tokens) > 9 else "", line[12:16].strip())
                if element != "H":
                    current.append((element, xyz))
    if current:
        poses.append(current)
    return [pose for pose in poses if pose]


def _read_reference_heavy_atoms(path: str) -> List[Tuple[str, Tuple[float, float, float]]]:
    atoms = []
    with open(path, "r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            if line.startswith(("ATOM", "HETATM")) and len(line) >= 54:
                element = _element_from_pdb_line(line.rstrip("\n"))
                if element != "H":
                    atoms.append((element, (float(line[30:38]), float(line[38:46]), float(line[46:54]))))
    return atoms


def _connectivity_graph(atoms: List[Tuple[str, Tuple[float, float, float]]]) -> Any:
    """Generic heavy-atom graph: nodes are elements, every bond a plain single bond, bonded when
    closer than 1.15x the sum of the covalent radii. Identical treatment for both poses."""
    table = Chem.GetPeriodicTable()
    graph = Chem.RWMol()
    atomic_numbers = []
    for element, _xyz in atoms:
        number = table.GetAtomicNumber(element)
        atomic_numbers.append(number)
        graph.AddAtom(Chem.Atom(number))
    for i in range(len(atoms)):
        for j in range(i + 1, len(atoms)):
            distance = math.dist(atoms[i][1], atoms[j][1])
            limit = 1.15 * (table.GetRcovalent(atomic_numbers[i]) + table.GetRcovalent(atomic_numbers[j]))
            if 0.4 < distance < limit:
                graph.AddBond(i, j, Chem.BondType.SINGLE)
    return graph.GetMol()


def pose_rmsd(
    reference: List[Tuple[str, Tuple[float, float, float]]],
    pose: List[Tuple[str, Tuple[float, float, float]]],
    max_matches: int = 20000,
) -> float:
    """Minimum heavy-atom RMSD over all symmetry-equivalent atom mappings, no re-alignment."""
    if Chem is None or np is None:
        raise CocrystalError("RDKit and numpy are required to compute the redocking RMSD.")
    if len(reference) != len(pose):
        raise CocrystalError(
            f"heavy-atom count differs (crystal {len(reference)} vs docked {len(pose)})"
        )
    reference_graph = _connectivity_graph(reference)
    pose_graph = _connectivity_graph(pose)
    matches = pose_graph.GetSubstructMatches(reference_graph, uniquify=False, maxMatches=max_matches)
    if not matches:
        raise CocrystalError("docked pose and crystal ligand do not share the same heavy-atom connectivity")
    reference_xyz = np.array([xyz for _el, xyz in reference], dtype=float)
    pose_xyz = np.array([xyz for _el, xyz in pose], dtype=float)
    mapping = np.array(matches, dtype=int)  # mapping[m, i] = pose atom matched to reference atom i
    deltas = pose_xyz[mapping] - reference_xyz[None, :, :]
    return float(np.sqrt((deltas ** 2).sum(axis=2).mean(axis=1)).min())


def compute_redock_rmsd(reference_pdb: str, docked_pdbqt: str) -> dict[str, Any]:
    """RMSD of the best-scored pose (MODEL 1) and the minimum over all poses, in Angstrom."""
    reference = _read_reference_heavy_atoms(reference_pdb)
    poses = read_pdbqt_poses(docked_pdbqt)
    if not reference:
        raise CocrystalError("reference ligand has no heavy atoms")
    if not poses:
        raise CocrystalError("docked PDBQT has no atoms")
    values = [pose_rmsd(reference, pose) for pose in poses]
    best_index = min(range(len(values)), key=lambda idx: values[idx])
    return {
        "best_pose_rmsd": values[0],
        "min_rmsd": values[best_index],
        "min_rmsd_pose": best_index + 1,
        "n_poses": len(values),
    }
