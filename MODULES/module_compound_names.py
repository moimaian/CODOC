"""Best-effort "common name" lookup for a compound, given only its structure (SMILES) - used to
enrich ligand IDs from anonymous/catalog namespaces (e.g. ZINC15, whose IDs carry no human name)
into a "ID (Name)" label, such as "ZINC000003875259 (Valsartan)".

Ported from CODRUG's MODULES/module_compound_names.py (same design, same cache format) so both
apps resolve names the same way. Design notes:
- ZINC15's own website AND its ".json" API endpoint are both gated behind a bot-verification
  challenge (redirect to /captcha/) - scraping/bypassing that is out of scope, so this module
  never talks to ZINC15 at all.
- Instead it matches by STRUCTURE against PubChem's public PUG-REST API (no key, no CAPTCHA,
  documented for programmatic use): compute the compound's InChIKey with RDKit from the SMILES
  CODOC already has in its results CSV, look that up exactly first (respects stereochemistry),
  and fall back to a "same connectivity" fastidentity SMILES search (ignores stereochemistry)
  when the exact InChIKey isn't registered - many database SMILES lack full stereo assignment.
  The lowest CID from that fallback is used as a heuristic (usually the most commonly registered
  form). Because this is always structure-based, it works identically regardless of which ligand
  databank (ZINC, ChEMBL, a custom folder, ...) a compound came from - there is nothing
  ZINC-specific about the lookup itself, only about the label it typically improves.
- Results (including "no match found") are cached to a small JSON file next to the job's docking
  results, keyed by InChIKey, so re-generating a report or re-loading filtered results never
  re-queries the same structure twice.
- Every network/RDKit failure is swallowed - a missing name must never block STEP 5 or the final
  report, it just means the compound is shown by its ID alone, as before.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional

try:
    from rdkit import Chem
    _RDKIT_AVAILABLE = True
except Exception:
    _RDKIT_AVAILABLE = False

_PUBCHEM_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
_USER_AGENT = "CODOC/1.0 (compound-name-lookup; https://github.com/moimaian/CODOC)"
_TIMEOUT_S = 8
# PubChem's usage policy caps automated PUG-REST use at 5 requests/second; 0.25s keeps us safely
# under that even accounting for scheduling jitter.
_MIN_INTERVAL_S = 0.25
_last_call_ts = 0.0

CACHE_FILENAME = "compound_name_cache.json"


def _cache_path(job_dir: str) -> str:
    return os.path.join(job_dir, CACHE_FILENAME)


def load_cache(job_dir: str) -> dict[str, Any]:
    path = _cache_path(job_dir)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_cache(job_dir: str, cache: dict[str, Any]) -> None:
    path = _cache_path(job_dir)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2, sort_keys=True)
    except Exception:
        pass


def _rate_limit() -> None:
    global _last_call_ts
    wait = _MIN_INTERVAL_S - (time.monotonic() - _last_call_ts)
    if wait > 0:
        time.sleep(wait)
    _last_call_ts = time.monotonic()


def _pubchem_get_json(path: str) -> Optional[dict]:
    url = f"{_PUBCHEM_BASE}/{path}"
    _rate_limit()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception:
        return None


def _title_by_inchikey(inchikey: str) -> Optional[str]:
    data = _pubchem_get_json(f"compound/inchikey/{inchikey}/property/Title/JSON")
    props = (data or {}).get("PropertyTable", {}).get("Properties", [])
    title = (props[0] or {}).get("Title") if props else None
    return title.strip() if isinstance(title, str) and title.strip() else None


def _title_by_connectivity(smiles: str) -> Optional[str]:
    """Fallback for SMILES whose exact (stereo-aware) InChIKey isn't registered on PubChem:
    "same connectivity" fastidentity search ignores stereochemistry. Picks the Title of the
    lowest CID returned (heuristic: usually the most commonly registered/parent form)."""
    quoted = urllib.parse.quote(smiles, safe="")
    data = _pubchem_get_json(f"compound/fastidentity/smiles/{quoted}/cids/JSON?identity_type=same_connectivity")
    cids = (data or {}).get("IdentifierList", {}).get("CID", [])
    if not cids:
        return None
    cid = min(cids)
    data = _pubchem_get_json(f"compound/cid/{cid}/property/Title/JSON")
    props = (data or {}).get("PropertyTable", {}).get("Properties", [])
    title = (props[0] or {}).get("Title") if props else None
    return title.strip() if isinstance(title, str) and title.strip() else None


def get_name_for_smiles(smiles: str, cache: dict[str, Any]) -> Optional[str]:
    """Returns a common/trade name for `smiles` (e.g. "Valsartan"), or None if RDKit is
    unavailable, the SMILES is invalid, or no PubChem match was found. `cache` is a plain dict
    (as returned by load_cache) mutated in place - call save_cache once after a batch of lookups,
    not after every single one."""
    if not _RDKIT_AVAILABLE or not smiles:
        return None
    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return None
        inchikey = Chem.MolToInchiKey(mol)
    except Exception:
        return None
    if not inchikey:
        return None

    if inchikey in cache:
        return cache[inchikey] or None

    name = _title_by_inchikey(inchikey)
    if not name:
        name = _title_by_connectivity(smiles)
    cache[inchikey] = name  # caches misses too (None), so they aren't retried every time
    return name


def format_hit_label(compound_id: Any, name: Optional[str]) -> str:
    """"ZINC000003875259" (+ "Valsartan") -> "ZINC000003875259 (Valsartan)"; unchanged if no name."""
    compound_id = str(compound_id)
    return f"{compound_id} ({name})" if name else compound_id


def resolve_compound_names(
    ids: list[str],
    job_dir: str,
    id_to_smiles: dict[str, str],
    max_lookups: int = 150,
) -> dict[str, Optional[str]]:
    """High-level entry point: for each id in `ids`, returns a common name (or None), matched by
    the SMILES `id_to_smiles` gives for that id - CODOC's results CSV already carries a SMILES
    column per ligand, so unlike CODRUG this never needs to scan other files for it. Loads/saves
    the on-disk cache once for the whole batch. Caps at `max_lookups` fresh network calls per call
    (cached hits don't count against the cap) so a very long, unfiltered results list can never
    turn into a multi-minute network loop."""
    ids = [str(i) for i in ids]
    cache = load_cache(job_dir)
    names: dict[str, Optional[str]] = {}
    fresh_lookups = 0
    dirty = False
    for cid in ids:
        smi = id_to_smiles.get(cid)
        if not smi:
            names[cid] = None
            continue
        before = len(cache)
        if fresh_lookups >= max_lookups:
            # Still honors an already-cached result even past the cap - only skips brand-new ones.
            try:
                mol = Chem.MolFromSmiles(smi) if _RDKIT_AVAILABLE else None
                key = Chem.MolToInchiKey(mol) if mol is not None else None
            except Exception:
                key = None
            names[cid] = cache.get(key) if key else None
            continue
        name = get_name_for_smiles(smi, cache)
        if len(cache) != before:
            fresh_lookups += 1
            dirty = True
        names[cid] = name
    if dirty:
        save_cache(job_dir, cache)
    return names
