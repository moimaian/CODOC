#################################################################################################################
#                                                     CODOC                                                     #
#                                        Computational Molecular Docking Platform                               #
#################################################################################################################

CODOC is a graphical tool (Python 3.10 and PyQt5) that automates multi-target virtual screening by molecular
docking. It prepares ligand libraries and protein targets and runs AutoDock Vina 1.2.5 (CPU) or AutoDock
Vina-GPU 2.1 (GPU), organising everything it produces in "projects". The CONFIG tab and four sequential steps:

  CONFIG  Projects (create a new project or resume a previous one) and performance options (CPU/GPU,
          threads, OpenCL)
  STEP 1  Ligand preparation (import files and folders, split, druggability filter, conversion to PDBQT with
          RDKit/Meeko or Open Babel)
  STEP 2  Target preparation (PDB2PQR/PROPKA protonation, ADFRsuite, grid box, P2Rank pockets, redocking tools)
  STEP 3  Docking parameters (scoring function, exhaustiveness, poses...), execution and live monitor
  STEP 4  Results (tables, filters, plots, redocking RMSD and the final report in .docx)

The interface is bilingual (English and Portuguese: flags at the top right) and every titled group can be
collapsed by clicking on its title. The complete description is in the user manual (TUTORIALS folder):
  - TUTORIALS/user_manual.pdf               (English)
  - TUTORIALS/manual_do_usuario_CODOC.pdf   (Portuguese)

The version number is in MODULES/versao.py; it is also shown in the HOME tab and in Help > About.

################################################################################################################
#                                           1. INSTALLATION                                                    #
################################################################################################################

CODOC runs on Linux. It was developed and tested on Linux Mint 21 (Ubuntu 22.04 base) with an NVIDIA GPU.
It will probably work on Ubuntu and its flavors; other distributions are not guaranteed.

# Option A - .deb package (Debian, Ubuntu, Linux Mint)

  sudo apt install ./codoc_<version>_amd64.deb

The package installs the program in /opt/codoc, the launcher /usr/bin/codoc and the CODOC entry in the
application menu. The first click on CODOC copies /opt/codoc to $HOME/CODOC (never touching the PROJECTS and
BASE folders) and starts the program. To generate the package from the source code:

  packaging/deb/build.sh

See packaging/VERSIONING.md (version numbering rules) and packaging/deb/README.md (package details).

# Option B - source code

  1. Download https://github.com/moimaian/CODOC/archive/refs/heads/main.zip
  2. Extract it to $HOME/CODOC (the program must reside in this folder):

       unzip CODOC-main.zip -d $HOME/Downloads && mv $HOME/Downloads/CODOC-main $HOME/CODOC

  3. Run it:

       cd $HOME/CODOC && python3 CODOC.py

# First run

CODOC creates a Python virtual environment at $HOME/.venv/CODOC with Python 3.10.12 (when this Python is not
available it builds it with pyenv, which asks for the administrator password) and restarts itself inside it.
A startup screen then creates the missing working folders, installs the essential packages (PyQt5, pandas and
psutil) and writes the menu shortcut $HOME/.local/share/applications/CODOC.desktop. The terminal that
launched the program shows the confirmation prompt and the progress messages.

Opened from the menu shortcut, CODOC shows no terminal window. Help > Terminal opens one on demand: a shell
already inside the CODOC Python environment (python and pip of the venv, current folder $HOME/CODOC) that
shows the output of the running program and accepts any command. The session output is also kept in
$HOME/.local/state/CODOC/terminal.log. Without a terminal, installations that need administrator rights ask
for the password in a graphical dialog (pkexec).

# Requirements

Open the window with the "Install Requirements" button of the HOME tab (or Help > Install Requirements),
check the components and click "Install Selected":

  - Python libraries: PyQt5, pandas, matplotlib, numpy, scipy, psutil, gemmi, RDKit, Meeko, Dimorphite-DL,
    PDB2PQR (PROPKA), python-docx;
  - Open Babel 3.x (apt);
  - AutoDock Vina 1.2.5 and vina_split (downloaded to the BIN folder);
  - Boost 1.84 and Vina-GPU 2.1 custom fork (built from the archives of the BIN folder; if they are missing
    they are downloaded from the "deps-v1" release of the project repository);
  - ADFRsuite 1.0 (prepare_receptor): install it manually in $HOME/ADFRsuite-1.0; the installer only checks it;
  - P2Rank (optional, pocket search in STEP 2): needs a Java runtime 17 or newer and the P2Rank folder
    extracted in your home folder (or pointed to by the P2RANK_HOME variable).

For GPU docking an OpenCL-capable driver is needed. If the machine has a Windows dual boot with Secure Boot
enabled, disable it in the BIOS, otherwise Vina-GPU may not be authorised to access the OpenCL platform.

################################################################################################################
#                                      2. USE AND DIRECTORY ORGANIZATION                                       #
################################################################################################################

CODOC/
  CODOC.py          main program
  MODULES/          interface texts, installer, projects, report, target and redocking tools, version
  ICONS/            logos and language flags
  BIN/              vina, vina_split and the Boost and Vina-GPU archives
  BASE/             your libraries: ligand files/folders and target structures (STEP 1 and STEP 2 open here)
  PROJECTS/         one folder per project (everything CODOC produces)
  TUTORIALS/        user manuals
  packaging/        .deb packaging and versioning rules

Older versions kept the work in a JOBS folder, in common LIGANDS and TARGETS folders and in a single
.codoc_settings.json. The first start of this version renames JOBS to PROJECTS (nothing is copied or deleted);
every job appears in "Load Previous Project" and its results can be opened in STEP 4. LIGANDS, TARGETS and
.codoc_settings.json are no longer used and can be removed once their content has been moved to BASE.

# PROJECTS

In CONFIG > Projects, "New Project" creates PROJECTS/<date>_<time>_<name>/ and "Load Previous Project" reopens
one, restoring the .json file of each step. CODOC always starts with no project open and "New Project" selected;
the last project used is shown, disabled, in "Previous project". Everything of a project stays inside its own folder:

  CONVERSION/        STEP 1
    LIGANDS/           working folder of the ligands: the imported files, the files after the split and, in
                       the end, the converted .pdbqt files (one subfolder per file/folder imported)
    CONVERSION_FAILURES, NO_DRUGGABILITY, EMPTY_LIGANDS, MACROCYCLES, NOT_RECOGNIZED_LIGANDS, DATAFRAMES,
    actions.log, databank_formats.json
    ligand_settings.json
  TARGETS/           STEP 2
    <target>/          protein.pdbqt (or protein_rigid.pdbqt and protein_flex.pdbqt), grid.txt, a copy of the
                       source file and the protonation log
    target_settings.json
  DOCKING/           STEP 3 and STEP 4
    <project>.csv      energies, RMSD and compound names
    <target>/<databank>/<ligand>/<ligand>.pdbqt   the poses
    docking_settings.json (CONFIG and the grid of STEP 2), results_settings.json, reports and exports
  REDOCK_REFERENCE/  crystal poses of the ligands exported for redocking

Running the docking again in the same project resumes it: ligands that already have a result are skipped.

# LIGANDS

In STEP 1, Ligands > Browse opens the BASE folder: choose one or more multi-ligand files and/or one or more
folders of individual ligands (Ctrl/Shift to select several). They are copied to CONVERSION/LIGANDS of the
project (the originals are never changed): a file becomes a group after "Split multimodel files" and a folder
is a group by itself. Each group should hold one file format (.sdf, .smi, .mol2, .pdb or .pdbqt).
You can then: split multi-model files and large folders; filter by druggability (MW, LogP, H-bond
donors/acceptors, rotatable bonds, TPSA); convert to PDBQT (protonation at a chosen pH, 3D generation, energy
minimisation) with RDKit/Meeko/Dimorphite-DL or Open Babel; reject or recover failed conversions; move empty
files; write SMI/CSV tables with Lipinski descriptors; and fix macrocycles for Vina-GPU (GPU only).

# TARGETS

In STEP 2 each target (.pdb, .pdbqt, .mol2 or .ent file; the file dialog opens in BASE) becomes a folder in the
TARGETS folder of the project. The grid box can be typed, read from a grid.txt, centred on the co-crystallised
ligand or on the pocket found by P2Rank. The co-crystallised ligand can be exported for redocking, whose RMSD is
computed in STEP 4. Water molecules and heteroatoms are removed during the conversion, and the protonation of
the receptor follows the chosen pH (PDB2PQR/PROPKA). The docking runs every ligand group against every target
of the project.

################################################################################################################
#                                       3. AUTHORS, LICENSE AND CONTACT                                        #
################################################################################################################

Developed by Allan Michael Junkert, Gustavo Henrique Scheiffer, Moises Maia Neto and Roberto Pontarolo,
Universidade Federal do Parana (UFPR), Brazil.
Contact: moimaian@gmail.com
Repository: https://github.com/moimaian/CODOC
License: GNU General Public License v3.0 (see LICENSE.txt).
