# CODOC_PY Tests

Suggested smoke tests:

1. Run `python3 /home/moises/CODOC_PY/CODOC.py`.
2. Confirm the splash screen creates `LIGANDS`, `TARGETS`, `RESULTS`, `bin`, `JOBS`, `MODULES`, `TEST`, and `ICONS`.
3. Open `Install Requirements` and confirm the installer window loads.
4. Save docking settings and reopen the app to verify persistence.
5. Prepare a target and verify `grid.txt` and `protein.pdbqt` are created.
6. Run a small CPU docking set and verify the target CSV appears under `RESULTS/DOCKING`.
