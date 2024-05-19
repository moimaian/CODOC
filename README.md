This is a tool to automate the virtual screening process by preparing ligands using Open babel 3.1.1 and executing molecular docking calculations using AutoDock Vina 1.2.5.

This tool was written in Bash to run on a Linux terminal.

For every executable in Linux, permission must be given to run as a program. This is possible graphically in a file manager like Nemo:
# Right-click on the program (example the codoc.sh bash script);
# In the menu select properties;
# In the opened window select permissions;
# Check the box to allow execution as a program;

Or using the command in the terminal:
$ chmod +x ./codoc.sh

Prerequisites:
- MGL Tools 1.5.7: https://ccsb.scripps.edu/mgltools/downloads/
- OpenBabel 3.1.1: https://github.com/openbabel/openbabel
- AutoDock Vina: https://github.com/ccsb-scripps/AutoDock-Vina/releases

Installation instructions and directory organization:
MGL Tools 1.5.7:
Executing the file downloaded from the link, the Autodock tool must be installed in your home folder, that is, in the $HOME variable. It is important that this variable is configured among the PATH environment variables. Check in the terminal by running:
$ echo $HOME
Something like this should appear as a result: "/home/your_user_name"

OpenBabel 3.1.1:
I recommend installing OpenBabel from your Linux distribution's own application store. It is important that the obabel variable is also among the PATH environment variables. Check in the terminal by running:
$ obabel -V
Expected response, something like: Open Babel 3.1.1 -- Feb 7 2022 -- 06:51:49

AutoDock Vina:
Download the Vina and Vina-split run files and transfer them both to the bin folder inside MGLTools in $HOME/MGLTools-1.5.7/bin via your file manager or Use the command in the terminal:
$ cd ~/Downloads && mv "vina_1.2.5_linux_x86_64.sh" "$HOME/MGLTools-1.5.7/bin/"

DIRECTORY ORGANIZATION:
Create a working folder inside the "$HOME/MGLTools-1.5.7" folder called just "doc", that is, you must have the address: "$HOME/MGLTools-1.5.7/doc". Inside this doc folder create two folders: LIGANDS and TARGETS. Leave only your codoc.sh script out of them.

Ready! Enjoy! I hope it is useful in your work!
