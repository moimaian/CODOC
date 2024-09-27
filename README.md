
#                                            CODOC VERSION 2024.1.0:                                       #

This is a tool to automate the multi-target virtual screening process using several open-source software. 
CODOC allows the preparation of ligands (using Open Babel or RDkit) and targets (using ADRF/prepare_receptor.sh). 
It performs molecular docking calculations on a CPU (AutoDock Vina 1.2.5) or GPU (AutoDock Vina-GPU 2.1) basis. 
Dataframes in .csv format are generated with ligand information and pose results organized in folders by 
target and subfolders by ligand database. 
This tool was written in Shell/Bash and uses YAD to generate the graphical user interface (GUI).


#                                      1. **INSTALLATION INSTRUCTIONS:**                                  #


# **CODOC:**
**1**
Download the zipped file from:
https://github.com/moimaian/CODOC/archive/refs/heads/main.zip

**2**
Extract the file to a working folder, for example, "$HOME/CODOC":
This is possible graphically in a file manager like Nemo
- Create the folder $HOME/CODOC;
- Extract the contents of the CODOC-main.zip file to the $HOME/CODOC folder;

Or using the command in the terminal:
>$ sudo apt-get install
>$ unzip CODOC-main.zip -d $HOME/Downloads && mkdir $HOME/CODOC && mv $HOME/Downloads/CODOC-main/* $HOME/CODOC

**3**
Go to the working folder and give permissions for the CODOC.sh file to be executed as a program:
This is possible graphically in a file manager like Nemo
- Right-click on the program (CODOC.sh bash script)
- In the menu select properties;
- In the opened window select permissions;
- Check the box to allow execution as a program;

Or using the command in the terminal:
>$ chmod +x $HOME/CODOC/CODOC.sh

**4**
In a file manager double-click on the CODOC.sh icon and click on run in the terminal.
Or run in the terminal:
>$ cd $HOME/CODOC && ./CODOC.sh

**Notes:**
When executed it will:
- Check the presence of the essential folders (LIGANDS, TARGETS and bin);
- Check the presence of the CODOC.desktop menu shortcut;
When it does not find the shortcut, as in the first execution, it will direct you to install the prerequisites.
The other times it will promptly execute the main menu.

# **PREREQUISITES:**
All prerequisites must be installed and to facilitate this process there is an ALL button. However, if it is necessary to reinstall one or more, these can be selected in the checklist.
The prerequisites are:
- GNU-Parallel;
- AutoDock Vina 1.2.5 and AutoDock Split 1.2.5;
- AutoDockTools-MGLTools 1.5.7;
- ADRF-1.0;
- OpenBabel 3.0.0;
- Cuda Toolkit 11.6;
- Boost 1.84;
- Vina-GPU 2.1;
- Update of Environment Variables in the PATH file;
- Installation of Cogen3d prerequisites: Python3, pip, pandas, rdkit, dimorphite-dl, tqdm, meeko, xlsxwriter.


THIS APPLICATION WAS DEVELOPED AND TESTED ONLY ON LINUX MINT 21.3 WITH KERNEL 5.15.0 AND CUDA-TOOLKIT 12.4. 
IT WILL PROBABLY WORK WELL ON UBUNTU LINUX AND ITS FLAVORS, BUT I DO NOT GUARANTEE IT FOR OTHER LINUX DISTROS!

IF YOUR MACHINE HAS A WINDOWS DUAL BOOT SYSTEM, WITH TPM 2.0, YOU MUST ENTER THE BIOS AND DISABLE THIS
SECURITY BOOT SYSTEM! OTHERWISE THE VINA-GPU ON LINUX WILL NOT BE AUTHORIZED TO ACCESS THE OPENCL PLATFORM!


#                                   2. **USE AND DIRECTORY ORGANIZATION:**                               #


Inside the folder where CODOC.sh there should be four folders: LIGANDS, TARGETS, RESULTS AND BIN.

#**LIGANDS:**
You must add multi-model files within the LIGANDS folder and single molecule files must be placed in subfolders containing an acronym that identifies the database (Ex.: ZINC_FDA, ZINC_NP, CHEMBL, COCONUT, ATLAS, CMNPD, IBIS... ). Each subfolder present within the LIGANDS directory must contain a single file format such as: .sdf, .smi, .mol2, .pdb or .pdbqt.
In the "Prepare Ligands" option in the main menu, it will be possible to:
- Define the main parameters for configuration;
- Split multi-model files into individual files;
- Reduce the number of files per folder in order to optimize memory usage;
- Filter ligands by rules and druggability;
- Generate lists that can be used as dataframes in future Machine Learning approaches (.CSV file with physicochemical parameters);
- Remove ligands that, due to failure, generated empty files;
- Convert ligands to .PDBQT format with various treatments (Protonation for specified pH, energy minimization and salt removal);
- Reject files with conversion errors, such as lack of 3D coordinates, presence of unrecognized atoms or null values;

The conversion can also be performed using Cogen3D, which uses rdkit and not OpenBabel.
The Rigid macrocycles for Vina-GPU option converts the "dummy atoms" G0, G1, G2 and G3 that gave flexibility to the macrocycle, but are not recognized by Vina-GPU, into carbons.

#**TARGETS:**
In the "Prepare Targets" option in the main menu, you will be able to:
- Choose the file in .pdb format that will be converted to .pdbqt format;
- Generate the grid.txt file with the Gridbox information for that target;

In the TARGETS folder, there should be subfolders for each target named with the PDB_ID. Within these subfolders, there should be only two files: grid.txt and protein.pdbqt;

**Notes:**
During the target conversion, water molecules and other compounds that are not part of the chain residues (HETATOM) will be removed;
It is strongly recommended that adjustments be made to the protonation state of the protein according to the pH of the medium and the pKa calculated for the titratable residues: ASP, GLU, TYR, ARG, LYS and HIS. Special attention should be given to HIS because it presents different tautomeric forms.

ADT-MGLTools must be used to define the coordinates of the center of the box (passed to CODOC for construction of the grid.txt file) and ProPka 3.0 must be used to define the protonation state of the titratable residues and make adjustments to the ADT, if necessary.

#**RESULTS:**
The results folder will have two subfolders: CONVERSION and DOCKING;
In the CONVERSION folder we will have the following subfolders (within them the data will be organized by binder database):
- CONVERSION_FAILURE (containing files that presented failures in their structures that would compromise docking);
- EMPTY_LIGANDS (containing empty files that cannot be recovered);
- DATAFRAMES (containing information such as smiles code, name and physicochemical parameters of the ligands);

In the DOCKING folder we will have the subfolders containing each docking execution performed.
The names of these subfolders are organized as: TYPE OF DOCKING / HARDWARE USED / DATE OF PERFORMANCE
Ex.: RIGID_DOCKING_RESULT_GPU_26_05_2024
Within these docking results folders we will have:
- RESULT SUBPLAYERS FOR EACH TARGET;
- TOTAL_PERFORMANCE_RIGID_DOCKING_GPU_26_05_2024.txt: PERFORMANCE FILE CONTAINING NUMBER OF TARGETS, NUMBER OF LIGANDS, CROSSINGS AND TIME ELAPSED; - TOTAL_RESULT_RIGID_DOCKING_GPU_26_05_2024.csv: FILE CONTAINING THE LIST OF RESULTS BY TARGET WITH BINDING ENERGY AND RMSD.

Within the target folders, for example the 6TEK target, we will have:
- RESULT SUBPAGES FOR EACH BINDING BASE;
- RIGID_DOCKING_PERFORMANCE_GPU_6TEK_26_05_2024.txt: PERFORMANCE LOG FILE CONTAINING NUMBER OF BINDING BASE AND ELAPSED TIME;
- RIGID_DOCKING_RESULT_GPU_6TEK_26_05_2024.csv: FILE CONTAINING THE LIST OF RESULTS BY BINDING BASE WITH BINDING ENERGY AND RMSD.

#**BIN:**
In the bin folder there will be some executable binaries:
vina_1.2.5_linux_x86_64.sh
vina_split_1.2.5_linux_x86_64
CoGen3D.py

################################################################################################################
Ready! Enjoy! I hope it is useful in your work!
Moisés Maia - 26/09/2024
