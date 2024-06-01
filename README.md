**This is a tool to automate the virtual screening process by preparing ligands using Open babel 3.0.0 and executing molecular docking calculations using AutoDock Vina 1.2.5 or AutoDock Vina-GPU 2.1.
This tool was written in Bash to run on a Linux terminal.**

For every executable in Linux, permission must be given to run as a program. This is possible graphically in a file manager like Nemo
- Right-click on the program (example the codoc.sh bash script)
- In the menu select properties
- In the opened window select permissions
- Check the box to allow execution as a program
Or using the command in the terminal:
$ chmod +x ./codoc.sh

# **PREREQUISITES:**
- MGL Tools 1.5.7: https://ccsb.scripps.edu/mgltools/downloads/
  (For preparing the protein and grid file)
- OpenBabel 3.0.0: https://github.com/openbabel/openbabel/releases/tag/openbabel-3-0-0
- AutoDock Vina: https://github.com/ccsb-scripps/AutoDock-Vina/releases

# **INSTALLATION INSTRUCTIONS:**
Download all content to an appropriate working directory. Something like $HOME/doc.

MGL Tools 1.5.7:
Executing the file downloaded from the link, the Autodock tool must be installed in your home folder, that is, in the "$HOME" variable. 
It is important that this variable is configured among the PATH environment variables. Check in the terminal by running:
$ echo $HOME
Something like this should appear as a result: "/home/your_user_name"

OpenBabel 3.0.0:
I recommend installing OpenBabel from your Linux distribution's own application store. It is important that the obabel variable is also among the PATH environment variables. Check in the terminal by running:
$ obabel -V
Expected response, something like: Open Babel 3.0.0 -- May 30 2024 -- 19:19:04
You can install by compiling the codes downloaded from the link using the commands:
tar -xvjf ~/Downloads/openbabel-3.0.0-source.tar.bz2 -C ~/
cd ~/openbabel-3.0.0
mkdir build && cd build
cmake ..
make -j2
make test
sudo make install

AutoDock Vina:
They are provided here and should be downloaded together to the same folder where CODOC.sh is located.

# **DIRECTORY ORGANIZATION:**
Inside the folder where CODOC.sh and the vina and vina-split executables are located, there should be two folders: LIGANDS and TARGETS.
You must add multi-model files within the LIGANDS folder and single molecule files must be placed in subfolders containing an acronym that identifies the database (Ex.: ZINC_FDA, ZINC_NP, CHEMBL, COCONUT, ATLAS, CMNPD, IBIS... ). Each subfolder present within the LIGANDS directory must contain a single file format such as: .sdf, .smi, .mol2, .pdb or .pdbqt.

Ready! Enjoy! I hope it is useful in your work!
