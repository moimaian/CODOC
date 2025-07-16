#!/bin/bash
#################################################################################################################################
#                                               CODOC VERSION 2024.1:                                                           #
#                                                   15/07/2025                                                                 #
#################################################################################################################################

#################################################################################################################################
#                                               CODOC STARTUP PROCEDURES:                                                       #
#################################################################################################################################
# Create current data variable:
current_date=$(date +"%Y_%m_%d")

# Identifying the working directory where CODOC is located:
CURRENT_DIR=$(dirname "${BASH_SOURCE[0]}")
cd $CURRENT_DIR
CODOC_DIR=$(pwd)

# Create a LOG file:
LOGFILE="/tmp/codoc_$current_date.log"
exec > >(tee -a "$LOGFILE") 2>&1

# CHECK IF YAD IS INSTALLED:
if command -v yad &> /dev/null; then
    echo "yad CHECK !"
else
    echo "yad is not installed. Installing..."

    # Detect the distribution and install yad
    if [ -f /etc/debian_version ]; then
        # Debian-based distributions (Ubuntu, Debian, Linux Mint, etc.)
        sudo -S apt-get update
        sudo -S apt-get install -y yad
    elif [ -f /etc/redhat-release ]; then
        # Red Hat-based distributions (Fedora, CentOS, etc.)
        sudo -S dnf install -y yad
    else
        echo "Unsupported Linux distribution. Please install yad manually."
        exit 1
    fi
fi

# OPEN START WINDOW:
for ((i=1; i<=100; i++)) {
    echo $i
    echo "# $((i))%"
    sleep 0.035
} | yad --splash --progress \
  --image=$CODOC_DIR/icons/START.png \
  --auto-close \
  --skip-taskbar \
  --center --image-on-top\
  --no-buttons

# CHECK THE EXISTENCE OF THE ESSENTIAL FOLDERS:
if [ -d "LIGANDS" ]; then
    echo "LIGANDS FOLDER CHECK !"
    else
        yad --center --title="CODOC - NOTICE !" \
            --width=500 --borders=10 --on-top \
            --text="\n \nTHE DIRECTORY CONTAINING THE 'LIGANDS' IS MISSING! \nA DIRECTORY CALLED LIGANDS WILL BE CREATED!" \
            --text-align=center \
            --button="OK":0 --buttons-layout=edge \
            --image=$CODOC_DIR/icons/attentionP.png 

        if [ $? -eq 0 ]; then
            mkdir -p $CODOC_DIR/LIGANDS
        fi
fi
if [ -d "TARGETS" ]; then
    echo "TARGETS FOLDER CHECK !"
    else
        yad --center --title="CODOC - NOTICE !" \
            --width=500 --borders=10 --on-top \
            --text="\n \nTHE DIRECTORY CONTAINING THE 'TARGETS' IS MISSING! \nA DIRECTORY CALLED TARGETS WILL BE CREATED!" \
            --text-align=center \
            --button="OK":0 --buttons-layout=edge \
            --image=$CODOC_DIR/icons/attentionP.png

        if [ $? -eq 0 ]; then
            mkdir -p $CODOC_DIR/TARGETS
        fi
fi
if [ -d "bin" ]; then
    echo "BIN FOLDER CHECK !"
    else
        yad --center --title="CODOC - NOTICE !" \
            --width=500 --borders=10 --on-top \
            --text="\n \nTHE DIRECTORY CONTAINING THE 'BIN' IS MISSING! \nA DIRECTORY CALLED BIN WILL BE CREATED!" \
            --text-align=center \
            --button="OK":0 --buttons-layout=edge \
            --image=$CODOC_DIR/icons/attentionP.png 

        if [ $? -eq 0 ]; then
            mkdir -p $CODOC_DIR/bin
        fi
fi
if [ -d "RESULTS" ]; then
    echo "RESULTS FOLDER CHECK !"
    else
        yad --center --title="CODOC - NOTICE !" \
            --width=500 --borders=10 --on-top \
            --text="\n \nTHE DIRECTORY CONTAINING 'RESULTS' AND ITS SUB FOLDERS ARE MISSING! \nTHIS DIRECTORY AND ITS SUB FOLDERS WILL BE CREATED!" \
            --text-align=center \
            --button="OK":0 --buttons-layout=edge \
            --image=$CODOC_DIR/icons/attentionP.png 

        if [ $? -eq 0 ]; then
            mkdir -p $CODOC_DIR/RESULTS
            mkdir -p $CODOC_DIR/RESULTS/CONVERSION
            mkdir -p $CODOC_DIR/RESULTS/DOCKING            
        fi
fi

# Predefined global access address variables:
tag=" C O D O C - AN AUTOMATIZED MULTI-TARGET MOLECULAR DOCKING TOOL"
CODOC_NAME="CODOC"
CODOC_ICON="${CODOC_DIR}/icons/logo_codocP.png"
CODOC_EXEC="${CODOC_DIR}/CODOC.sh"
MENU_FILE="/usr/share/applications/${CODOC_NAME}.desktop"
DESKTOP_DIR=$(xdg-user-dir DESKTOP)
DESKTOP_SHORTCUT="$DESKTOP_DIR/${CODOC_NAME}.desktop"
ligands="$CODOC_DIR/LIGANDS"
targets="$CODOC_DIR/TARGETS"
data="$CODOC_DIR/.form_data.txt"
vina="$CODOC_DIR/bin/vina_1.2.5_linux_x86_64"
vina_split="$CODOC_DIR/bin/vina_split_1.2.5_linux_x86_64"
BOOST_VERSION="1.84.0"
BOOST_DIR="$HOME"/boost_"${BOOST_VERSION//./_}"
VINAGPU_DIR="$HOME/Vina-GPU-2.1/AutoDock-Vina-GPU-2.1"
vina_GPU="$HOME/Vina-GPU-2.1/AutoDock-Vina-GPU-2.1/AutoDock-Vina-GPU-2-1"
track_progress="$CODOC_DIR/.track_progress.log"
prepare_receptor=""$HOME"/ADFRsuite-1.0/bin/prepare_receptor"
opencl="/usr/local/cuda"
results_doc="$CODOC_DIR/RESULTS/DOCKING"
results_ligands="$CODOC_DIR/RESULTS/CONVERSION"
drug_dir="$results_ligands/NO_DRUGGABILITY"
failure_dir="$results_ligands/CONVERSION_FAILURES"
canceled="$results_ligands/CANCELED_JOBS"
CoGen3D="$CODOC_DIR/bin/CoGen3D.py"
COGEN3D_DIR="$CODOC_DIR/CoGen3D_CONVERSION"

# Predefined global access parameter variables:
sf="vina" # Type of scoring function used
cpu=$(nproc) # Number of Threads used on the CPU
ext=$((cpu)) # Exhaustiveness
threads="8000" # Number of Threads used on the GPU
cpu_parallel="10"
num_poses="9" # Number of output poses to generate
min_rmsd="1" # Minimum RMSD between poses
energy_range="3" # Maximum energy interval between poses
spacing="1" # grid spacing (Angstrom)
s_x="30" # Grid box x size
s_y="30" # Grid box y size
s_z="30" # Grid box z size
doc_type="Rigid"
proc_type="GPU"
file_size="10" # Minimum file size to be rejected in bytes
pH="7.4" # pH of the medium that will determine the protonation state of the ligands
max_lig="50000" # Maximum ligand number per folder
reject="nan|As|Bi|Si|B"
vel="med" # Specifying the speed of 3D coordinate generation - 1ª Attempt
vel2="slow" # Specifying the speed of 3D coordinate generation - 2ª Attempt
time_limit=$((10 * cpu)) # Maximum conversion time for each ligand for first attempt (in seconds)
time_limit2=$((30 * cpu)) # Maximum conversion time for each ligand for second attempt (in seconds)
steps="1500" # Energy minimization steps
mw_1="0" # Molar Weight minimum
mw_2="500" # Molar Weight maximum
lp_1="-5" # Partition coeficient log minimum
lp_2="5" # Partition coeficient log maximum
rb="10" # Rotatable bonds maximum
hd="5" # Number of H Bond donor maximum
ha="10" # Number of H Bond aceptor maximum
tpsa="140" # Topological Surface Area maximum
# 40 ≤ MR ≤ 130* MOLAR REFRACTIVITY
# 20 ≤ ATOMS NUMBER ≤ 70
n_result="20"
rmsd_limit="2.0"
echo "GLOBAL ACCESS VARIABLES CHECK !"

#################################################################################################################################
#                                       FUNCTION TO OPEN A INTERACTIVE GNOME TERMINAL:                                          #
#################################################################################################################################
open_terminal() {
    gnome-terminal -- bash -i -c "$CODOC_DIR/CODOC.sh; exec bash"
}

#################################################################################################################################
#                                       FUNCTION TO DISPLAY THE MAIN MENU:                                                      #
#################################################################################################################################
show_main_menu() {
    opcao=$(yad --list --center --title="$tag" \
        --height=250 --width=600 --borders=10 --on-top \
        --column="Select an option :" \
        --image="$CODOC_DIR/icons/logo_codoc2P.png" \
        --text-align=center \
        --button="EXIT":1 --button="TERMINAL":2 --button="INSTALL":3 --button="OK":0 --buttons-layout=edge \
        --separator "" \
        "STEP 1. Docking settings" \
        "STEP 2. Prepare Ligands" \
        "STEP 3. Prepare Targets" \
        "STEP 4. Run Molecular Docking" \
        "STEP 5. View Results" \
        "** USAGE INFORMATION **" \
        )

    # Check if the user selected an option or pressed a button
    case $? in
        0)  # OK button
            case "$opcao" in
                "STEP 1. Docking settings") docking_setting_form ;;
                "STEP 2. Prepare Ligands") show_ligand_menu ;;
                "STEP 3. Prepare Targets") run_target_prepare ;;
                "STEP 4. Run Molecular Docking") show_docking_menu ;;
                "STEP 5. View Results") show_docking_result ;;
                "** USAGE INFORMATION **") codoc_inform ;;
                *) remove_parameters; rm -f "$LOGFILE"; exit 0 ;;
            esac
            ;;
        1)  # Exit button
            remove_parameters
            rm -f "$LOGFILE"
            exit 0 
            ;;
        2)  # Terminal button
            kill $MENU_PID
            open_terminal
            ;;
        3)  # Prerequisites button
            run_CODOC_prerequisites
            ;;
    esac
}

################################################################################################################################
#                               FUNCTION FOR CODOC USAGE INFORMATION:                                                   #
################################################################################################################################
codoc_inform() {
readme="$CODOC_DIR"/README.txt

if [[ -f "$readme" ]]; then
    yad --text-info --back=black --title="CODOC - USAGE INFORMATION" --margins=10 < /"$CODOC_DIR"/README.txt \
        --center --width=1100 --height=600 --borders=10 --on-top \
        --button="Github webpage":1 --button="Main Menu":0 --buttons-layout=edge \
        --image="$CODOC_DIR/icons/infoP.png" 
        if [ $? -eq 0 ]; then
            show_main_menu
        elif [ $? -eq 1 ]; then
            xdg-open "https://github.com/moimaian/CODOC"
            show_main_menu
        fi
else
    # Commands to execute if the file does not exist:
    echo "The file $readme does not exist."
    yad --center --title="CODOC - WARNING!" \
        --width=500 --borders=10 --on-top \
        --text="\n \nTHE FILE README.txt IS MISSING! \nGET IT FROM GITHUB AND TRANSFER IT TO THE $CODOC_DIR FOLDER!" \
        --text-align=center \
        --button="OK":0 --buttons-layout=edge \
        --image=$CODOC_DIR/icons/warningP.png
        if [ $? -eq 0 ]; then
            xdg-open "https://github.com/moimaian/CODOC"
            show_main_menu
        fi
fi
}

################################################################################################################################
#                               FUNCTION TO INSTALL PREREQUISITES FOR CODOC:                                                   #
################################################################################################################################
run_CODOC_prerequisites() {

# SAVE THE LINUX ROOT PASSWORD FOR FUTURE INSTALLATIONS:
while true; do
    password=$(yad --entry --title="CODOC - PASSWORD" --text-align=center --text="Provide the linux root password:" \
        --entry-label="Password:" --skip-taskbar --center --width=400 --borders=10 --on-top \
        --button="OK":0 --buttons-layout=edge --hide-text --on-top \
        --image="$CODOC_DIR/icons/cadeadoP.png" )

    # Check if the password is correct using the sudo command
    echo "$password" | sudo -S -v >/dev/null 2>&1

    if [ $? -eq 0 ]; then
        # If the password is correct, proceed with the script
        echo "Password accepted. Proceeding..."
        break
    else
        # If the password is incorrect, display an error message and return to the password prompt
        yad --info --text-align=center --title="CODOC - WARNING" \
            --text="Incorrect password.\nPlease try again!" \
            --button="OK":0 --buttons-layout=center --skip-taskbar --center --width=400 --borders=10 --on-top \
            --image="$CODOC_DIR/icons/warningP.png"
    fi
done

    install_menu_entry() {
        # Content of the CODOC.desktop file:
DESKTOP_ENTRY="[Desktop Entry]
Version=2024.1
Name=CODOC
Comment=A AUTOMATIZED MULTI-TARGET DOCKING TOOL
Exec=bash -i -c "$CODOC_EXEC"
Icon="$CODOC_ICON"
Terminal=false
Type=Application
Categories=Qt;Science;Chemistry;Physics;Education;
StartupNotify=true
MimeType=chemical/x-cml;chemical/x-xyz;
"

        # Create the .desktop file in the applications menu if it doesn't exist (requires root permissions)
        echo "$password" | sudo -S touch "$MENU_FILE"
        touch "$DESKTOP_SHORTCUT"
        echo "$password" | sudo -S bash -c "echo '$DESKTOP_ENTRY' > $MENU_FILE"
        echo "$DESKTOP_ENTRY" > "$DESKTOP_SHORTCUT"
        echo "$password" | sudo -S chmod +x "$MENU_FILE"
        echo "$password" | sudo -S chmod +x "$DESKTOP_SHORTCUT"
        echo "Applications menu entry created successfully."
    }

    install_build() {
        echo "UPDATE AND INSTALL BUILD_ESSENTIAL ..."
        yad --info --center --title="CODOC - INSTALL !" \
            --text="Installing build-essential... \nFollow in the terminal and wait for the installation to finish !" \
            --text-align=center --no-buttons --width=500 --borders=10 --on-top \
            --image=$CODOC_DIR/icons/pcP.png &
        YAD_PID=$!

        ## Package Update:
        echo "$password" | sudo -S apt-get update

        ## Package with essential tools and libraries for building software from source code and basic dependencies:
        echo "$password" | sudo -S apt-get install build-essential
        echo "$password" | sudo -S apt-get install -y build-essential wget unzip cmake git
        kill $YAD_PID              
    }

    install_parallel() {
        echo "INSTALL GNU_PARALLEL FROM THE REPOSITORY ..."
        yad --info --center --title="CODOC - INSTALL !" \
            --text="Installing GNU-PARALLEL... \nFollow in the terminal and wait for the installation to finish !" \
            --text-align=center --no-buttons --width=500 --borders=10 --on-top \
            --image=$CODOC_DIR/icons/pcP.png &
        YAD_PID=$!

        echo "$password" | sudo -S apt-get install -y parallel

        kill $YAD_PID              
    }

    install_gnuplot() {
        echo "INSTALL GNU_PLOT ..."
        yad --info --center --title="CODOC - INSTALL !" \
            --text="Installing gnuplot... \nFollow in the terminal and wait for the installation to finish !" \
            --text-align=center --no-buttons --width=500 --borders=10 --on-top \
            --image=$CODOC_DIR/icons/pcP.png &
        YAD_PID=$!

        echo "$password" | sudo -S apt-get install -y gnuplot

        kill $YAD_PID              
    }

    install_vina() {
        echo "INSTALL VINA AND VINA_SPLIT 1.2.5 ..."
        yad --info --center --title="CODOC - INSTALL !" \
            --text="Installing Autodock-Vina and Vina-Split 1.2.5... \nFollow in the terminal and wait for the installation to finish !" \
            --text-align=center --no-buttons --width=500 --borders=10 --on-top \
            --image=$CODOC_DIR/icons/pcP.png &
        YAD_PID=$!
        ## Transfers the vina and vina_split binary files to the CODOC directory:
        echo "$password" | sudo -S apt-get install libboost-all-dev swig
        wget https://github.com/ccsb-scripps/AutoDock-Vina/releases/download/v1.2.5/vina_1.2.5_linux_x86_64
        wget https://github.com/ccsb-scripps/AutoDock-Vina/releases/download/v1.2.5/vina_split_1.2.5_linux_x86_64
        mv vina_1.2.5_linux_x86_64 "$CODOC_DIR"/bin/
        mv vina_split_1.2.5_linux_x86_64 "$CODOC_DIR"/bin/
        chmod +x "$CODOC_DIR"/bin/vina_1.2.5_linux_x86_64
        chmod +x "$CODOC_DIR"/bin/vina_split_1.2.5_linux_x86_64
        kill $YAD_PID
    }

    install_mgltools() {
        echo "Installing Mgltools-1.5.7 ..."
        yad --info --center --title="CODOC - INSTALL !" \
            --text="Installing Mgltools-1.5.7... \nFollow the instructions in the window for installation !" \
            --text-align=center --no-buttons --width=500 --borders=10 --on-top \
            --image=$CODOC_DIR/icons/pcP.png &
        YAD_PID=$!
        ## Installing MGLTools with the configuration file to the HOME directory:
        wget https://ccsb.scripps.edu/download/292/ -O mgltools_Linux-x86_64_1.5.7_install
        chmod +x ./mgltools_Linux-x86_64_1.5.7_install
        ./mgltools_Linux-x86_64_1.5.7_install
        mv mgltools_Linux-x86_64_1.5.7_install ""$CODOC_DIR"/bin"
        kill $YAD_PID
    }

    install_ADRF() {
        echo "Function for Option 3 executed"
        yad --info --center --title="CODOC - INSTALL !" \
            --text="Installing ADRF-1.0rc1... \nFollow in the terminal and wait for the installation to finish !" \
            --text-align=center --no-buttons --width=500 --borders=10 --on-top \
            --image=$CODOC_DIR/icons/pcP.png &
        YAD_PID=$!
        ## Installing MGLTools with the configuration file to the HOME directory:
        wget https://ccsb.scripps.edu/adfr/download/1028/ -O ADFRsuite_Linux-x86_64_1.0_install
        chmod +x ./ADFRsuite_Linux-x86_64_1.0_install
        ./ADFRsuite_Linux-x86_64_1.0_install
        mv ADFRsuite_Linux-x86_64_1.0_install ""$CODOC_DIR"/bin"
        kill $YAD_PID
    }

    install_obabel() {
        echo "INSTALL OPENBABEL 3.0.0 ..."
        yad --info --center --title="CODOC - INSTALL !" \
            --text="Installing OPENBABEL 3.0.0... \nFollow in the terminal and wait for the installation to finish !" \
            --text-align=center --no-buttons --width=500 --borders=10 --on-top \
            --image=$CODOC_DIR/icons/pcP.png &
        YAD_PID=$!
        ## Install Openbabel 3.0.0:
        echo "Installing Openbabel 3.0.0..."
        echo "$password" | sudo -S apt-get install cmake g++ make libeigen3-dev zlib1g-dev
        wget https://github.com/openbabel/openbabel/archive/refs/tags/openbabel-3-1-1.tar.gz
        tar -xzf openbabel-3-1-1.tar.gz -C "$HOME"
        cd "$HOME"/openbabel-openbabel-3-1-1
        mkdir build
        cd build
        cmake ..
        make
        echo "$password" | sudo -S make install
        mv "$CODOC_DIR"/openbabel-3-1-1.tar.gz ""$CODOC_DIR"/bin"
        kill $YAD_PID
        obabel_version=$(obabel -V)
        yad --text-info --title="Open Babel Version" --text="$obabel_version" \
            --button="OK":0 --buttons-layout=edge \
            --width=500 --height=300 --center
    }

    install_cuda() {
        echo "INSTALL NVIDIA-CUDA-TOOLKIT ..."
        ubuntu_version=$(cat /etc/upstream-release/lsb-release | awk 'NR==2')
        gcc_version=$(gcc --version)
        so_architecture=$(uname -m)
        yad --text-info --title="Pre-Requisites for Cuda Toolkit" \
            --text=" Recommended Ubuntu Release 22.04 / Your System: $ubuntu_version\n Recommended GCC version 12.3 / Your System: $gcc_version\n SO Architecture x86_64 / Your System: $so_architecture" \
            --button="CANCEL":1 --button="OK":0 --buttons-layout=edge \
            --width=500 --height=300 --center
        exit_code=$?
        if [[ $exit_code -eq 1 ]]; then
            cd $CODOC_DIR
            show_main_menu
        fi

        yad --info --center --title="CODOC - INSTALL !" \
            --text="Installing NVIDIA-CUDA-TOOLKIT 12.6... \nFollow in the terminal and wait for the installation to finish !\n Linux will then automatically reboot..." \
            --text-align=center --no-buttons --width=500 --borders=10 --on-top \
            --image=$CODOC_DIR/icons/pcP.png &
        YAD_PID=$!
        ## Install Nvidia-Cuda-Toolkit from repository (OLD VERSION - 11.5):
#        echo "Installing Nvidia-Cuda-Toolkit ..."
#        echo "$password" | sudo -S apt install -y nvidia-cuda-toolkit

        ## Install Nvidia-Cuda-Toolkit from Debian Installer (NEW VERSION - 12.6):
        echo "$password" | sudo apt-key del 7fa2af80
        wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-ubuntu2204.pin
        echo "$password" | sudo mv cuda-ubuntu2204.pin /etc/apt/preferences.d/cuda-repository-pin-600
        wget https://developer.download.nvidia.com/compute/cuda/12.6.2/local_installers/cuda-repo-ubuntu2204-12-6-local_12.6.2-560.35.03-1_amd64.deb
        echo "$password" | sudo dpkg -i cuda-repo-ubuntu2204-12-6-local_12.6.2-560.35.03-1_amd64.deb
        echo "$password" | sudo cp /var/cuda-repo-ubuntu2204-12-6-local/cuda-*-keyring.gpg /usr/share/keyrings/
        echo "$password" | sudo apt-get update
        echo "$password" | sudo apt-get -y install cuda-toolkit-12-6

       # Add environment variables and aliases to .bashrc
        echo "Adding environment variables and aliases to ~/.bashrc..."
        {
        export PATH=/usr/local/cuda-12.6/bin${PATH:+:${PATH}}
        export LD_LIBRARY_PATH=/usr/local/cuda-12.6/lib64\
                                 ${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}
        } >> ~/.bashrc
        source ~/.bashrc
        kill $YAD_PID

        cuda_version=$(nvcc --version)
        yad --text-info --title="CUDA Version" --text="$cuda_version" \
            --button="OK":0 --buttons-layout=edge \
            --width=500 --height=300 --center
        echo "$password" | sudo reboot
    }

    install_boost() {
        echo "INSTALL BOOST 1.84.0 ..."
        yad --info --center --title="CODOC - INSTALL !" \
            --text="Installing BOOST 1.84.0... \nFollow in the terminal and wait for the installation to finish !" \
            --text-align=center --no-buttons --width=500 --borders=10 --on-top \
            --image=$CODOC_DIR/icons/pcP.png &
        YAD_PID=$!

        # Define Variables:
        BOOST_TAR=boost_"${BOOST_VERSION//./_}".tar.gz

        if [ ! -d ""$HOME"/boost_"${BOOST_VERSION//./_}"/include/boost" ]; then
            echo "Installing Boost ${BOOST_VERSION}..."
            if [[ ! -f "${BOOST_TAR}" ]]; then
                wget -O ${BOOST_TAR} https://archives.boost.io/release/${BOOST_VERSION}/source/${BOOST_TAR}
            fi
            tar -xzf ${BOOST_TAR} -C "$HOME"            
            cd ${BOOST_DIR}
            ./bootstrap.sh --prefix="$BOOST_DIR"
            ./b2
            ./b2 headers
            ./b2 install
            touch test_boost.cpp
            test_file="$BOOST_DIR"/test_boost.cpp
            cat <<EOL > "$test_file"
#include <boost/version.hpp>
#include <iostream>

int main() {
std::cout << "Boost version: " << BOOST_LIB_VERSION << std::endl;
return 0;
}
EOL
            g++ test_boost.cpp -o test_boost -I"$HOME"/boost_"${BOOST_VERSION//./_}"/include -L"$HOME"/boost_"${BOOST_VERSION//./_}"/lib -lboost_system
            sleep 1
            kill $YAD_PID
            test_boost_output=$(./test_boost)
            yad --info --center \
                --title="CODOC - INSTALL !" \
                --text="$test_boost_output\n\nAre you seeing the correct version of Boost above?" \
                --text-align=center \
                --button="NO":1 --button="YES":0 --buttons-layout=edge \
                --width=500 --borders=10 --on-top \
                --image=$CODOC_DIR/icons/pcP.png
                case $? in
                    0) # Button YES
                        cd $CODOC_DIR
                        ;;
                    1) # Button NO
                        cd $CODOC_DIR
                        yad --title="CODOC - FAILURE" \
                            --text="Sorry :'( \nBoost and Vina-GPU installation failed!" \
                            --image="$CODOC_DIR/icons/failureP.png" \
                            --skip-taskbar --center --width=600 --borders=10 --on-top \
                            --button="OK":0 --buttons-layout=edge 
                        ;;
                esac
                mv ${BOOST_TAR} ""$CODOC_DIR"/bin"                  
        else
            kill $YAD_PID
            yad --title="CODOC - INFO" \
                --text="Boost ${BOOST_VERSION} is already installed.\n Remove Boost directory for new instalation!" \
                --image="$CODOC_DIR/icons/infoP.png" \
                --skip-taskbar --center --width=600 --borders=10 --on-top \
                --button="OK":0 --buttons-layout=edge 
        fi        
    }

    install_vinagpu() {
        echo "INSTALL VINA-GPU 2.1 ..."
        # Define Variables:
        VINA_ZIP=""$CODOC_DIR"/bin/Vina-GPU-2.1-pbar01.zip"

        if [ ! -d "${VINAGPU_DIR}" ]; then
            yad --info --center --title="CODOC - INSTALL !" \
                --text="Installing VINA-GPU 2.1... \nFollow in the terminal and wait for the installation to finish !" \
                --text-align=center --no-buttons --width=500 --borders=10 --on-top \
                --image=$CODOC_DIR/icons/pcP.png &
            YAD_PID=$!
            echo "Installing AutoDock Vina GPU 2.1..."
            unzip ${VINA_ZIP} -d "$HOME"
            cd ${VINAGPU_DIR}
            make_file="$VINAGPU_DIR"/Makefile      
            echo "" > "$make_file" 
            cat <<EOL > "$make_file"
# Need to be modified according to different users
WORK_DIR=$HOME/Vina-GPU-2.1/AutoDock-Vina-GPU-2.1
BOOST_LIB_PATH=$HOME/boost_1_84_0
OPENCL_LIB_PATH=/usr/local/cuda
OPENCL_VERSION=-DOPENCL_3_0
GPU_PLATFORM=-DNVIDIA_PLATFORM
DOCKING_BOX_SIZE=-DSMALL_BOX

BOOST_INC_PATH=-I\$(BOOST_LIB_PATH) -I\$(BOOST_LIB_PATH)/boost 
VINA_GPU_INC_PATH=-I\$(WORK_DIR)/lib -I\$(WORK_DIR)/OpenCL/inc 
OPENCL_INC_PATH=-I\$(OPENCL_LIB_PATH)/include
LIB1=-l:libboost_program_options.a -l:libboost_system.a -l:libboost_filesystem.a -lOpenCL
LIB2=-lstdc++ -lstdc++fs
LIB3=-lm -lpthread
LIB_PATH=-L\$(BOOST_LIB_PATH)/stage/lib -L\$(OPENCL_LIB_PATH)/lib64
SRC=./lib/*.cpp ./OpenCL/src/wrapcl.cpp \$(BOOST_LIB_PATH)/libs/thread/src/pthread/thread.cpp \$(BOOST_LIB_PATH)/libs/thread/src/pthread/once.cpp
MACRO=\$(OPENCL_VERSION) \$(GPU_PLATFORM) \$(DOCKING_BOX_SIZE) -DBOOST_TIMER_ENABLE_DEPRECATED \$(CUSTOM_OPT)
all:out
out:./main/main.cpp
	gcc -o AutoDock-Vina-GPU-2-1 \$(BOOST_INC_PATH) \$(VINA_GPU_INC_PATH) \$(OPENCL_INC_PATH) ./main/main.cpp -O3 \$(SRC) \$(LIB1) \$(LIB2) \$(LIB3) \$(LIB_PATH) \$(MACRO) \$(OPTION) -DNDEBUG
source:./main/main.cpp
	gcc -o AutoDock-Vina-GPU-2-1 \$(BOOST_INC_PATH) \$(VINA_GPU_INC_PATH) \$(OPENCL_INC_PATH) ./main/main.cpp -O3 \$(SRC) \$(LIB1) \$(LIB2) \$(LIB3) \$(LIB_PATH) \$(MACRO) \$(OPTION) -DNDEBUG -DBUILD_KERNEL_FROM_SOURCE 
debug:./main/main.cpp
	gcc -o AutoDock-Vina-GPU-2-1 \$(BOOST_INC_PATH) \$(VINA_GPU_INC_PATH) \$(OPENCL_INC_PATH) ./main/main.cpp -g \$(SRC) \$(LIB1) \$(LIB2) \$(LIB3) \$(LIB_PATH) \$(MACRO) \$(OPTION) -DBUILD_KERNEL_FROM_SOURCE
clean:
	rm AutoDock-Vina-GPU-2-1
EOL
            make clean && make source
            source ~/.bashrc
            cd "$HOME"/Vina-GPU-2.1/AutoDock-Vina-GPU-2.1/input_file_example
            sed -i "3c\opencl_binary_path = \"$VINAGPU_DIR\"" 2bm2_config.txt
            cd "$HOME"/Vina-GPU-2.1/AutoDock-Vina-GPU-2.1
            ./AutoDock-Vina-GPU-2-1 --config ./input_file_example/2bm2_config.txt            
            echo "$password" | sudo -S cp "$VINAGPU_DIR"/Kernel1_Opt.bin "$VINAGPU_DIR"/Kernel2_Opt.bin /usr/local/cuda
            make clean && make out
            kill $YAD_PID
            vinaGPU_version=$(./AutoDock-Vina-GPU-2-1 --version)
            yad --text-info --title="Vina-GPU Version" --text="$vinaGPU_version" \
                --button="OK":0 --buttons-layout=edge \
                --width=500 --height=300 --center
            cd "$CODOC_DIR"
        else
            echo "AutoDock Vina GPU 2.1 folder is already installed."
            yad --title="CODOC - INFO" \
                --text="Vina-GPU directory is already installed." \
                --image="$CODOC_DIR/icons/infoP.png" \
                --skip-taskbar --center --width=600 --borders=10 --on-top \
                --button="OK":0 --buttons-layout=edge 
        fi
    }

    install_cogen3d() {
        yad --info --center --title="CODOC - INSTALL !" \
            --text="Install CoGen3D Prerequisites... \nFollow the test in the terminal and wait to finish !" \
            --text-align=center --no-buttons --width=500 --borders=10 --on-top \
            --image=$CODOC_DIR/icons/pcP.png &
            YAD_PID=$!
            echo "$password" | sudo -S apt update
            echo "$password" | sudo -S apt install python3.10
            echo "$password" | sudo -S apt install python3-pip
            pip install pandas scipy rdkit dimorphite-dl tqdm meeko xlsxwriter

            kill $YAD_PID
    }

    install_environment_variables() {
        yad --info --center --title="CODOC - INSTALL !" \
            --text="Adding environment variables and aliases to ~/.bashrc...\n Wait to finish !" \
            --text-align=center --no-buttons --width=500 --borders=10 --on-top \
            --image=$CODOC_DIR/icons/pcP.png &
            YAD_PID=$!
       # Add environment variables and aliases to .bashrc
        echo "Adding environment variables and aliases to ~/.bashrc..."
        {
            echo "export PATH=\$PATH:'$VINAGPU_DIR/lib'"
            echo "export PATH=\$PATH:'$VINAGPU_DIR/main'"
            echo "export PATH=\$PATH:'$VINAGPU_DIR/OpenCL/inc'"
            echo "export PATH=\$PATH:'$VINAGPU_DIR'"
            echo "alias vina_GPU='$VINAGPU_DIR/AutoDock-Vina-GPU-2-1'"
            echo ""
            echo "export PATH=\$PATH:'$BOOST_DIR'"
            echo "export PATH=\$PATH:'$BOOST_DIR/bin.v2'"
            echo "export LD_LIBRARY_PATH=\$LD_LIBRARY_PATH:'$BOOST_DIR/stage/lib'"
            echo ""
            echo "export PATH=\$PATH:'/usr/local/cuda/bin'"
            echo "export PATH=\$PATH:'/usr/local/cuda/include'"
            echo "export LD_LIBRARY_PATH=\$LD_LIBRARY_PATH:'/usr/local/cuda/lib64'"
            echo ""
            echo "export PATH=\$PATH:'$HOME/ADFRsuite-1.0/bin'"
            echo "alias prepare_receptor='$HOME/ADFRsuite-1.0/bin/prepare_receptor'"
            echo "alias prepare_ligand='$HOME/ADFRsuite-1.0/bin/prepare_ligand'"
            echo ""
            echo "export PATH=\$PATH:'$HOME/MGLTools-1.5.7/bin'"
            echo "alias adt='$HOME/MGLTools-1.5.7/bin/adt'"
            echo "alias pythonsh='$HOME/MGLTools-1.5.7/bin/pythonsh'"
            echo ""
            echo "export PATH=\$PATH:'${CODOC_DIR}'"
            echo "alias CODOC='${CODOC_DIR}/CODOC.sh'"
            echo "export PATH=\$PATH:'${CODOC_DIR}/bin'"
            echo "export PATH=\$PATH:'${CODOC_DIR}/icons'"
            echo "alias vina='${CODOC_DIR}/bin/vina_1.2.5_linux_x86_64'"
            echo "alias vina_split='${CODOC_DIR}/bin/vina_split_1.2.5_linux_x86_64'"
        } >> ~/.bashrc
        source ~/.bashrc
            kill $YAD_PID
    }

function_install() {
    install_options=$(yad --list --checklist --title="CODOC - INSTALL PREREQUISITES" \
    --width=500 --height=500 --column="Select" --column="Options" \
    --button="MAIN MENU:1" --separator="\t" --button="ALL:2" --button="INSTALL:0" --buttons-layout=edge \
    --center --image=$CODOC_DIR/icons/pcP.png \
    false "1. Creating menu entry and shortcut" \
    false "2. Update Repository and Build Essentials" \
    false "3. GNU-Parallel" \
    false "4. GNU-Plot" \
    false "5. Autodock Vina and Vina Split 1.2.5" \
    false "6. Mgltools-1.5.7" \
    false "7. ADRF-1.0" \
    false "8. OpenBabel 3.0.0" \
    false "9. Nvidia-Cuda-Toolkit 12.6 (Attention! For Nvidia GPU only.)" \
    false "10. Boost 1.84.0" \
    false "11. AutoDock Vina-GPU 2.1" \
    false "12. CoGen3D Prerequisites" \
    false "13. Environment variables" )
    exit_code=$?

    if [[ $exit_code -eq 0 ]]; then    
        echo "SELECTED OPTIONS FOR INSTALL:"
        echo "$install_options"
        touch .install_data.txt
        echo "$install_options" > .install_data.txt
        run_install="$CODOC_DIR"/.install_data.txt
      
        while read -r line; do
            second_element=$(echo "$line" | awk '{print $2}')
            case "$second_element" in
                1.) install_menu_entry ;;
                2.) install_build ;;
                3.) install_parallel ;;
                4.) install_gnuplot ;;
                5.) install_vina ;;
                6.) install_mgltools ;;
                7.) install_ADRF ;;
                8.) install_obabel ;;
                9.) install_cuda ;;
                10.) install_boost ;;
                11.) install_vinagpu ;;
                12.) install_cogen3d ;;
                13.) install_environment_variables ;;
                *) echo "No valid option selected." ;;
            esac
        done < "$run_install"
        cd $CODOC_DIR
        show_main_menu
    elif [[ $exit_code -eq 1 ]]; then
        cd $CODOC_DIR
        show_main_menu
    elif [[ $exit_code -eq 2 ]]; then
        install_menu_entry
        install_build
        install_parallel
        install_gnuplot
        install_vina
        install_mgltools
        install_ADRF
        install_obabel
        install_cuda
        install_boost
        install_vinagpu
        install_cogen3d
        install_environment_variables
    else
        show_main_menu
    fi
    }
function_install
}

#################################################################################################################################
#                               FUNCTION TO CONFIGURE DOCKING PARAMETERS AND VARIABLES:                                         #
#################################################################################################################################
docking_setting_form() {
form_data1=$(yad --form --center --title "Docking Settings" \
    --text "    Change the fields below if necessary:" \
    --field="   Scoring function :":CBE "vina!ad4!vinardo" \
    --field="   split results :":CBE "no!yes" \
    --field="   CPU Threads :":NUM "$cpu" \
    --field="   CPU parallelism :":NUM "$cpu_parallel" \
    --field="   Exhaustiveness :":NUM "$ext" \
    --field="   GPU Threads :":NUM "$threads" \
    --field="   Poses :":NUM "$num_poses" \
    --field="   Minimum RMSD :":NUM "$min_rmsd" \
    --field="   Energy Range (Kcal/mol) :":NUM "$energy_range" \
    --field="   Grid Spacing :":NUM "$spacing" \
    --field="   Grid x size :":NUM "$s_x" \
    --field="   Grid y size :":NUM "$s_y" \
    --field="   Grid z size :":NUM "$s_z" \
    --text-align=center --borders=20 \
    --width=500 --height=600 --on-top --center \
    --separator="\n" \
    --image="$CODOC_DIR/icons/configP.png" \
    --button="MAIN MENU":1 --button="OK":0  --buttons-layout=edge \
)

    # Check if the user selected an option or pressed a button
    case $? in
        0)  # OK button
            touch .form_data1.txt
            echo -n > .form_data1.txt
            echo "$form_data1" > .form_data1.txt
            sed -i 's/,/./g' .form_data1.txt
            data1="$CODOC_DIR"/.form_data1.txt
            sf="$(sed -n '1p' $data1)"
            split="$(sed -n '2p' $data1)"
            cpu="$(sed -n '3p' $data1)"
            cpu_parallel="$(sed -n '4p' $data1)"
            ext="$(sed -n '5p' $data1)"
            threads="$(sed -n '6p' $data1)"
            num_poses="$(sed -n '7p' $data1)"
            min_rmsd="$(sed -n '8p' $data1)"
            energy_range="$(sed -n '9p' $data1)"
            spacing="$(sed -n '10p' $data1)"
            s_x="$(sed -n '11p' $data1)"
            s_y="$(sed -n '12p' $data1)"
            s_z="$(sed -n '13p' $data1)"
            export sf split cpu cpu_parallel ext threads num_poses min_rmsd energy_range spacing s_x s_y s_z
            echo "Hidden file Form_data1.txt saved in $CODOC_DIR"
            show_main_menu
            ;;
        1)  # Main Menu button
            show_main_menu
            ;;
    esac
}

#################################################################################################################################
#                               FUNCTION TO CONFIGURE LIGAND PREPARE VARIABLES:                                                 #
#################################################################################################################################
ligands_setting_form() {
    form_data2=$(
    yad --form --center --title="LIGAND PREPARE CONFIGURATION PARAMETERS" \
        --text="Change the fields below if necessary :" \
        --width=500 --height=500 --borders=10 --on-top \
        --separator="\n" \
        --image="$CODOC_DIR/icons/configP.png" \
        --button="LIGANDS MENU":1 --button="OK":0 --buttons-layout=edge \
        --field="Minimum File Size (Bytes) :":NUM "$file_size" \
        --field="pH :":NUM "$pH"\!0..100\!0.1\!2 \
        --field="Máx. ligands/folder :":NUM "$max_lig" \
        --field="Rejected elements :" "$reject" \
        --field="Speed of gen3D 1ª attempt :":CB "!fastest!fast!med!slow!slowest!dist" \
        --field="Speed of gen3D 2ª attempt :":CB "!fastest!fast!med!slow!slowest!dist" \
        --field="Timeout 1ª attempt(s) :":NUM "$time_limit" \
        --field="Timeout 2ª attempt(s) :":NUM "$time_limit2" \
        --field="Energy minimization steps:":NUM "$steps" \
        )

    # Check if the user selected an option or pressed a button
    case $? in
        0)  # OK button
            touch .form_data2.txt
            echo -n > .form_data2.txt
            echo "$form_data2" > .form_data2.txt
            sed -i 's/,/./g' .form_data2.txt
            data2="$CODOC_DIR"/.form_data2.txt
            file_size="$(sed -n '1p' $data2)"
            pH="$(sed -n '2p' $data2)"
            max_lig="$(sed -n '3p' $data2)"
            reject="$(sed -n '4p' $data2)"
            vel="$(sed -n '5p' $data2)"
            vel2="$(sed -n '6p' $data2)"
            time_limit="$(sed -n '7p' $data2)"
            time_limit2="$(sed -n '8p' $data2)"
            steps="$(sed -n '9p' $data2)"
            export file_size pH max_lig reject vel vel2 time_limit time_limit2 steps
            echo "Hidden file Form_data2.txt saved in $CODOC_DIR"
            show_ligand_menu
            ;;
        1)  # Ligand Prepare Menu button
            show_ligand_menu
            ;;
    esac
}

#################################################################################################################################
#                            FUNCTION TO DISPLAY THE LIGANDS PREPARE MENU:                                                      #
#################################################################################################################################
show_ligand_menu() {
    opcao=$(
    yad --list --center --title="LIGANDS PREPARE MENU" \
        --text=" Select an option:" --text-align=center \
        --width=600 --height=500 --borders=10 --on-top \
        --separator="\n" \
        --image="$CODOC_DIR/icons/ligandP.png" \
        --button="MAIN MENU":1 --button="RUN ALL":2 --button="OK":0 --buttons-layout=edge \
        --column=" Option:" \
        "						CODOC Tools       " \
        "	1. Ligand prepare settings" \
        "	2. Split multimodel files to directories" \
        "	3. Split large folders (Memory Optimization)" \
        "	4. Generate ligands SMI/CSV with Lipinski Parameter" \
        "	5. Druggability filter" \
        "	6. Move empty files" \
        "	7. Run Ligands Conversion for PDBQT" \
        "	8. Reject .pdbqt ligands files with errors" \
        "	9. Attempt to recover lost ligands" \
        "	10. Move empty files" \
        "" \
        "						CoGen3D       " \
        "	1. CoGen3D settings" \
        "	2. Run CoGen3D" \
        "	3. Rigid macrocycles for Vina-GPU(Without G0,G1...)" \
        "" 
        )

    # Check if the user selected an option
    case $? in
        0) # OK button
            case "$opcao" in
                "	1. Ligand prepare settings") ligands_setting_form ;;
                "	2. Split multimodel files to directories") run_ligands_split ;;
                "	3. Split large folders (Memory Optimization)") run_split_folder ;;
                "	4. Generate ligands SMI/CSV with Lipinski Parameter") run_lipinski_parameters ;;
                "	5. Druggability filter") run_druggability_filter ;;
                "	6. Move empty files") run_empty ;;
                "	7. Run Ligands Conversion for PDBQT") run_ligands_conversion ;;
                "	8. Reject .pdbqt ligands files with errors") run_pdbqt_rejected ;;
                "	9. Attempt to recover lost ligands") run_pdbqt_recovery ;;
                "	10. Move empty files") run_empty ;;
                "	1. CoGen3D settings") cogen3d_settings_form ;;
                "	2. Run CoGen3D") run_cogen3d_conversion ;;
                "	3. Rigid macrocycles for Vina-GPU(Without G0,G1...)") run_macrocyclic ;;
                *) show_ligand_menu ;;
            esac
            ;;
        1) # Main Menu button
            show_main_menu
            ;;
        2) # RUN ALL button
            ligands_setting_form
            run_ligands_split
            run_split_folder
            run_lipinski_parameters
            run_druggability_filter
            run_empty
            run_ligands_conversion
            run_pdbqt_rejected
            run_pdbqt_recovery
            run_empty
            ;;
    esac
}

#################################################################################################################################
#                            FUNCTION TO DISPLAY THE TAGETS PREPARE MENU:                                                      #
#################################################################################################################################
run_target_prepare() {

target_file=$(yad --file --center --title="CHOOSE TARGET FILE" \
                --image="$CODOC_DIR/icons/targetP.png" \
                --separator="\n" \
                --width=900 --height=600 --borders=10 --on-top \
                --button="MAIN MENU":1 --button="OK":0 --buttons-layout=edge )

# Checking if the user selected an option
case $? in
    0) # OK Button
        # Creating .form_data4.txt and directories:
        touch .form_data4.txt
        EXT="${target_file##*.}"
        target_base=$(basename "$target_file" ."$EXT")
        target_dir="$targets"/"$target_base"
        mkdir -p "$target_dir"
        cp "$target_file" "$target_dir"
        target_in="$target_dir"/"$target_base"."$EXT"
        target_out="$target_dir"/protein.pdbqt

        # Grid configuration with yad interface:
        grid_config=$(
        yad --form --center --title "Grid Settings" \
            --text "    Change the fields below if necessary:" \
            --field="   Grid Spacing :":FLT "$spacing" \
            --field="   Grid x size :":NUM "$s_x" \
            --field="   Grid y size :":NUM "$s_y" \
            --field="   Grid z size :":NUM "$s_z" \
            --field="   Grid x center :":FLT "$c_x" \
            --field="   Grid y center :":FLT "$c_y" \
            --field="   Grid z center :":FLT "$c_z" \
            --text-align=center \
            --width=500 --height=500 --borders=10 --on-top \
            --separator="\n" \
            --image="$CODOC_DIR/icons/configP.png" \
            --button="RESTART":1 --button="OK":0 --buttons-layout=edge )

        # Checking the user's choice in grid configuration
        case $? in
            0)  # OK Button
                echo -n > .form_data4.txt
                echo "$grid_config" > .form_data4.txt
                # Updating docking parameters according to the user's choices:
                data4="$CODOC_DIR/.form_data4.txt"
                spacing="$(sed -n '1p' $data4)"
                s_x="$(sed -n '2p' $data4)"
                s_y="$(sed -n '3p' $data4)"
                s_z="$(sed -n '4p' $data4)"
                c_x="$(sed -n '5p' $data4)"
                c_y="$(sed -n '6p' $data4)"
                c_z="$(sed -n '7p' $data4)"
                export spacing s_x s_y s_z c_x c_y c_z
                echo "Hidden file Form_data4.txt saved in $CODOC_DIR"
                ;;
            1)  # Main Menu Button
                rm -rf "$target_dir"
                run_target_prepare
                ;;
        esac

        # Creating grid.txt file
        touch "$target_dir"/grid.txt
        grid_file="$target_dir"/grid.txt

        # Creating grid.txt file for each target:
        cat <<EOL > "$grid_file"
$target_base
spacing	$spacing
npts    $s_x	$s_y	$s_z
center	$c_x	$c_y	$c_z
EOL

        # Keeping lines that start with ATOM or TER
        cd "$target_dir"
        sed -i '/^ATOM\|^TER/!d' "$target_in"
        $HOME/ADFRsuite-1.0/bin/prepare_receptor -r "$target_in" -o "$target_out"
        rm "$target_in"
        cd ../
        yad --info --center \
            --title="CODOC - QUESTION !" \
            --text="DO YOU WANT TO PREPARE ANOTHER TARGET?" \
            --text-align=center \
            --button="NO":1 --button="YES":0 --buttons-layout=center \
            --width=500 --borders=10 --on-top \
            --image=$CODOC_DIR/icons/questionP.png

        case $? in
            0)  # YES Button
                run_target_prepare
                ;;
            1)  # NO Button
                cd $CODOC_DIR
                show_main_menu
                ;;
        esac
        ;;
    1) # Main Menu Button
        show_main_menu
        ;;
esac
}

#################################################################################################################################
#                                       FUNCTION TO DISPLAY THE DOCKING MENU:                                                   #
#################################################################################################################################
show_docking_menu() {
opcao=$(
    yad --form --center --title="DOCKING MENU" \
        --text="Select the following options :" \
        --width=500 --borders=10 --on-top \
        --separator="\n" \
        --image="$CODOC_DIR/icons/docP.png" \
        --field="Docking Type :":CB "!Rigid!Flexible" \
        --field="Processing Type :":CB "!CPU!GPU" \
        --field="Run Type :":CB "!NEW!RESTART" \
        --button="MAIN MENU":1 --button="RUN":0 --buttons-layout=edge )

# Check if the user selected an option or pressed a button
case $? in
    0)  # OK button
        doc_type=$(echo "$opcao" | sed -n '1p')
        proc_type=$(echo "$opcao" | sed -n '2p')
        run_type=$(echo "$opcao" | sed -n '3p')
        if [[ "$doc_type" == "Rigid" && "$proc_type" == "CPU" && "$run_type" == "NEW" ]]; then
            list_new_cpu
            run_rigid_docking_cpu
        elif [[ "$doc_type" == "Rigid" && "$proc_type" == "GPU" && "$run_type" == "NEW" ]]; then
            list_new_gpu
            run_rigid_docking_gpu
        elif [[ "$doc_type" == "Flexible" && "$proc_type" == "CPU" && "$run_type" == "NEW" ]]; then
            list_new_cpu
            run_flexible_docking_cpu
        elif [[ "$doc_type" == "Flexible" && "$proc_type" == "GPU" && "$run_type" == "NEW" ]]; then
            list_new_gpu
            run_flexible_docking_gpu
        elif [[ "$doc_type" == "Rigid" && "$proc_type" == "CPU" && "$run_type" == "RESTART" ]]; then
            list_restart_cpu
            run_rigid_docking_cpu
        elif [[ "$doc_type" == "Rigid" && "$proc_type" == "GPU" && "$run_type" == "RESTART" ]]; then
            list_restart_gpu
            run_rigid_docking_gpu
        elif [[ "$doc_type" == "Flexible" && "$proc_type" == "CPU" && "$run_type" == "RESTART" ]]; then
            list_restart_cpu
            run_flexible_docking_cpu
        elif [[ "$doc_type" == "Flexible" && "$proc_type" == "GPU" && "$run_type" == "RESTART" ]]; then
            list_restart_gpu
            run_flexible_docking_gpu
        fi
        ;;
    1)  # MAIN MENU button
        show_main_menu
        ;;
esac
}

################################################################################################################################
#                               FUNCTION FOR VIEW RESULTS:                                                   #
################################################################################################################################
show_docking_result() {

    opcao=$(yad --form --center --title="CODOC - VIEW RESULTS" \
            --text="SELECT RESULT PARAMETERS:" --text-align=center \
            --width=500 --borders=10 --on-top \
            --separator="\n" \
            --image="$CODOC_DIR/icons/graphP.png" \
            --field="Máx. Number os ligands :":NUM "$n_result" \
            --field="RMSD threshold value :":NUM "$rmsd_limit" \
            --button="MAIN MENU":1 --button="OK":0 --buttons-layout=edge )

    # Check if the user selected an option or pressed a button
    case $? in
        0)  # OK button
            n_result=$(echo "$opcao" | sed -n '1p')
            rmsd_limit=$(echo "$opcao" | sed -n '2p')
            export n_result rmsd_limit
            ;;
        1)  # MAIN MENU button
            show_main_menu
            ;;
    esac

    list_results="$results_doc"/.list_results.txt
    echo -n > "$list_results"
    
    # List the result directories and save them to the file
    for dir in "$results_doc"/*/; do
        result_dir=$(basename "$dir")
        echo "$result_dir" >> "$list_results"
    done

    # Display the list of results in checklist format
    selected_result=$(yad --list --radiolist --title="CODOC - VIEW RESULTS" --margins=10 \
        --text="Select a result to view:" --center --text-align=center \
        --width=600 --height=500 --borders=10 --on-top \
        --column="Select" --column="Results" $(awk '{print "FALSE", $0}' "$list_results") --separator="\n" \
        --button="MAIN MENU":1 --button="VIEW":0 --buttons-layout=edge \
        --image="$CODOC_DIR/icons/graphP.png" --print-column=2 
    )        
   
        if [[ $? -eq 0 && -n "$selected_result" ]]; then
            echo "Selected result: $selected_result"
            # Display the list of targets for the selected result:
            list_target="$results_doc"/"$selected_result"/.list_targets.txt
            echo -n > "$list_target"
            touch "$list_target"
            for target in "$results_doc"/"$selected_result"/*/; do
                result_target=$(basename "$target")
                echo "$result_target" >> "$list_target"
            done
            selected_target=$(yad --list --radiolist --title="CODOC - VIEW RESULTS" --margins=10 \
                    --text="Select a target in $selected_result to view:" --center --text-align=center \
                    --width=600 --height=500 --borders=10 --on-top \
                    --column="Select" --column="Targets" $(awk '{print "FALSE", $0}' "$list_target") --separator="\n" \
                    --button="BACK":1 --button="VIEW":0 --buttons-layout=edge \
                    --image="$CODOC_DIR/icons/targetP.png" --print-column=2              
            )
            
            if [[ $? -eq 0 && -n "$selected_target" ]]; then
                echo "Selected result: $selected_target"
                input_file="$results_doc"/"$selected_result"/"$selected_target"/"$selected_result"_"$selected_target".csv
                output_file="$results_doc"/"$selected_result"/"$selected_target"/"$selected_target"_top"$n_result".csv
                echo -n > "$output_file"
                touch "$output_file"
                # Process the CSV file, filtering lines with RMSD < 2 and sorting by binding energy
                awk -F'\t' -v rmsd="$rmsd_limit" '$4 < rmsd' "$input_file" | sort -t$'\t' -k3,3n | head -n "$n_result" | tr -d ' ' | tr -d '-' > "$output_file"
                echo "The "$n_result" ligands with RMSD < "$rmsd_limit" and the lowest binding energy were saved to $output_file"
                selected_view=$(
                yad --form --center --title="RESULT VIEW SELECTION" \
                    --text="Choose how to view the result :" \
                    --width=500 --borders=10 --on-top \
                    --separator="\n" \
                    --image="$CODOC_DIR/icons/graphP.png" \
                    --field="Display format :":CB "!Graph!Table" \
                    --button="BACK":1 --button="OK":0 --buttons-layout=edge )

                    # Check if the user selected an option or pressed a button
                    case $? in
                        0)  # OK button
                            view=$(echo "$selected_view" | sed -n '1p')
                            if [[ "$view" == "Graph" ]]; then
                                csv_file="$output_file"
                                temp_data=temp_$(basename "$output_file").txt
                                awk -F'\t' '{print $2, $3, $4}' "$csv_file" > "$temp_data"
#                                export selected_target
gnuplot -persist <<-EOFMarker
    set title "Top Ligands for $selected_target"
    set xlabel " "
    set ylabel "Binding Energy (Kcal/mol) \n RMSD (Angstroms)"
    set style data histograms
    set style fill solid 2.0 border -1
    set boxwidth 2
    set xtics rotate by -45
    set key outside
    plot "$temp_data" using 2:xtic(1) title "Binding Energy" with histograms linecolor rgb "#006680", \
         "$temp_data" using 3:xtic(1) title "RMSD" with histograms linecolor rgb "orange"
EOFMarker

                                rm "$temp_data"                                
                            elif [[ "$view" == "Table" ]]; then
                            yad --list --ellipsize=END --title="CODOC - VIEW RESULTS" --margins=10 --on-top \
                                --width=800 --height=500 --center --text-align=center \
                                --text="Results of $n_result TOP ligands for $selected_target:" \
                                --column="SMILES" \
                                --column="LIGAND NAME" \
                                --column="BINDING ENERGY" \
                                --column="RMSD" \
                                --separator="\t" $(cat "$output_file") \
                                --image="$CODOC_DIR/icons/graphP.png" \
                                --button="BACK TO START":1 --button="MAIN MENU":0 --buttons-layout=edge
                                case $? in
                                    1) # BACK TO START
                                        show_docking_result ;;
                                    0) # BACK TO MAIN MENU
                                        show_main_menu ;;
                                esac           
                            fi
                            ;;
                        1) # BACK TO START
                            show_docking_result
                            ;;
                    esac
                    show_docking_result
            elif [[ $? -eq 1 ]]; then
                show_docking_result
            else
                echo "No target selected or cancelled"
            fi
        elif [[ $? -eq 1 ]]; then
            show_main_menu
        else
            echo "No result selected or cancelled"
        fi
}

#################################################################################################################################
#                                       FUNCTION OF SPLIT MULTI-MODEL LIGANDS FOR DOCKING:                                      #
#################################################################################################################################
run_ligands_split() {

# CHECK IF THERE ARE MULTI-MODEL FILES IN THE "LIGANDS" FOLDER:
quantity_files=$(find "$ligands" -mindepth 1 -maxdepth 1 -type f ! -path "$ligands" | wc -l)
if [ "$quantity_files" -eq 0 ]; then
    yad --info --center \
        --title="CODOC - NOTICE !" \
        --text="THERE ARE NO MULTI-MODEL LIGANDS FILES IN THE \"LIGANDS\" FOLDER" \
        --text-align=center \
        --button="OK":0 --buttons-layout=center \
        --width=500 --borders=10 --on-top \
        --image=$CODOC_DIR/icons/attentionP.png
    if [ $? -eq 0 ]; then
        show_ligand_menu
    fi

elif [ "$quantity_files" -gt 0 ]; then
    for multi in "$ligands"/*; do        
        if [ -f "$multi" ]; then        
            if [[ "$multi" == *.sdf ]]; then
                LIG=$(basename "$multi" .sdf)
                total=$(grep -o '\$\$\$\$' "$multi" | wc -l)
                mkdir "$ligands/$LIG"
                mv $multi "$ligands"/"$LIG"
                obabel "$ligands"/"$LIG"/"$LIG".sdf -O "$ligands"/"$LIG"/"$LIG"*.sdf --split --unique &
                obabel_pid=$!
                ( 
                  while [ -e "$ligands"/"$LIG"/"$LIG".sdf ]; do                   
                    rest=$(find "$ligands"/$LIG -maxdepth 1 -type f | wc -l)        
                    progress=$(( rest * 100 / total  ))
                    echo $progress
                    sleep 0.1
                  done
                 ) | yad --splash --progress --text="Fragmenting \"$LIG\" files…" \
                  --image=$CODOC_DIR/icons/progressP.png \
                  --auto-close \
                  --skip-taskbar \
                  --center --width=400 --borders=10 --on-top \
                  --no-buttons &
                wait $obabel_pid
                rm "$ligands"/"$LIG"/"$LIG".sdf

                yad --info --center \
                    --title="CODOC - CONFIRMATION !" \
                    --text="Please wait for it to finish..." \
                    --text-align=center --auto-close \
                    --width=300 --borders=10 --no-buttons \
                    --image=$CODOC_DIR/icons/progressP.png &
                YAD_PID=$!

                # Converts the chemical names generated after splitting into .sdf files into the database id code and remove spaces:
                for file in "$ligands/$LIG"/*.sdf; do
                    f=$(basename "$file" .sdf)
                    # Checks if the file exists
                    if [ -f "$file" ]; then
                        # Extract database id code from file using awk
                        id_cod=$(awk '/>  <id>/ {getline; print}' "$file")
                        zinc=$(awk '/>  <zinc_id>/ {getline; print}' "$file")
                        compound=$(awk '/>  <COMPOUND_ID>/ {getline; print}' "$file")
                        coconut=$(awk '/>  <coconut_id>/ {getline; print}' "$file")
                        chembl=$(awk '/>  <chembl_id>/ {getline; print}' "$file")
                        
                        if [ -n "$id_cod" ]; then
                            # Checks whether the file with the new name already exists to avoid conflict
                            if [ ! -f "$ligands/$LIG/"$LIG""$id_cod".sdf" ]; then
                                mv "$file" "$ligands/$LIG/"$LIG""$id_cod".sdf"
                            fi
                        fi
                        if [ -n "$zinc" ]; then
                            # Checks whether the file with the new name already exists to avoid conflict
                            if [ ! -f "$ligands/$LIG/$zinc.sdf" ]; then
                                mv "$file" "$ligands/$LIG/$zinc.sdf"                                
                            fi
                        fi
                        if [ -n "$compound" ]; then
                            # Checks whether the file with the new name already exists to avoid conflict
                            if [ ! -f "$ligands/$LIG/$compound.sdf" ]; then
                                mv "$file" "$ligands/$LIG/$compound.sdf"                                
                            fi
                        fi
                        if [ -n "$coconut" ]; then
                            # Checks whether the file with the new name already exists to avoid conflict
                            if [ ! -f "$ligands/$LIG/$coconut.sdf" ]; then
                                mv "$file" "$ligands/$LIG/$coconut.sdf"                                
                            fi
                        fi
                        if [ -n "$chembl" ]; then
                            # Checks whether the file with the new name already exists to avoid conflict
                            if [ ! -f "$ligands/$LIG/$coconut.sdf" ]; then
                                mv "$file" "$ligands/$LIG/$chembl.sdf"                                
                            fi
                        fi
                        # Check if the file name contains spaces
                        if [[ "$file" =~ \  ]]; then
                            # Remove spaces from the file name
                            new_file=$(echo "$file" | tr -d ' ')
                            mv "$file" "$new_file"
                        fi
                    fi
                done
                kill $YAD_PID
            elif [[ "$multi" == *.mol2 ]]; then
                LIG=$(basename "$multi" .mol2)
                total=$(wc -l < "$multi")
                mkdir "$ligands"/$LIG
                mv $multi "$ligands"/$LIG
                obabel "$ligands"/$LIG/*.mol2 -O "$ligands"/"$LIG"/.mol2 --split --unique cansmi &
                obabel_pid=$!
                ( 
                  while [ -e "$ligands"/"$LIG"/"$LIG".smi ]; do                   
                    rest=$(find "$ligands"/$LIG -maxdepth 1 -type f | wc -l)        
                    progress=$(( rest * 100 / total  ))
                    echo $progress
                    sleep 0.1
                  done
                 ) | yad --splash --progress --text="Fragmenting \"$LIG\" files…" \
                  --image=$CODOC_DIR/icons/progressP.png \
                  --auto-close \
                  --skip-taskbar \
                  --center --width=400 --borders=10 --on-top \
                  --no-buttons &
                wait $obabel_pid
                rm "$ligands"/"$LIG"/"$LIG".mol2

            elif [[ "$multi" == *.smi ]]; then
                LIG=$(basename "$multi" .smi)
                total=$(wc -l < "$multi")
                mkdir "$ligands"/$LIG
                mv $multi "$ligands"/$LIG
                if grep -q "^ " "$ligands"/"$LIG"/"$LIG".smi; then
                    echo "Removendo espaços no início das linhas..."
                    sed -i 's/^ *//' "$ligands"/"$LIG"/"$LIG".smi
                fi                            
                obabel "$ligands"/"$LIG"/"$LIG".smi -O "$ligands"/"$LIG"/.smi --split --unique cansmi &
                obabel_pid=$!
                ( 
                  while [ -e "$ligands"/"$LIG"/"$LIG".smi ]; do                   
                    rest=$(find "$ligands"/$LIG -maxdepth 1 -type f | wc -l)        
                    progress=$(( rest * 100 / total  ))
                    echo $progress
                    sleep 0.1
                  done
                 ) | yad --splash --progress --text="Fragmenting \"$LIG\" files…" \
                  --image=$CODOC_DIR/icons/progressP.png \
                  --auto-close \
                  --skip-taskbar \
                  --center --width=400 --borders=10 --on-top \
                  --no-buttons &
                wait $obabel_pid
                rm "$ligands"/"$LIG"/"$LIG".smi

            elif [[ "$multi" == *.pdb ]]; then
                # Multi-model .pdb files are not common. 
                LIG=$(basename "$multi" .pdb)
                total=$(wc -l < "$multi")
                mkdir "$ligands"/$LIG
                mv $multi "$ligands"/$LIG
                obabel "$ligands"/$LIG/*.pdb -O "$ligands"/"$LIG"/.pdb --split --unique cansmi &
                obabel_pid=$!
                ( 
                  while [ -e "$ligands"/"$LIG"/"$LIG".smi ]; do                   
                    rest=$(find "$ligands"/$LIG -maxdepth 1 -type f | wc -l)        
                    progress=$(( rest * 100 / total  ))
                    echo $progress
                    sleep 0.1
                  done
                 ) | yad --splash --progress --text="Fragmenting \"$LIG\" files…" \
                  --image=$CODOC_DIR/icons/progressP.png \
                  --auto-close \
                  --skip-taskbar \
                  --center --width=400 --borders=10 --on-top \
                  --no-buttons &
                wait $obabel_pid
                rm "$ligands"/"$LIG"/"$LIG".pdb

            elif [[ "$multi" == *.pdbqt ]]; then
                # Multi-model .pdbqt files are not common. 
                LIG=$(basename "$multi" .pdbqt)
                mkdir "$ligands"/$LIG
                mv $multi "$ligands"/$LIG
                obabel "$ligands"/$LIG/*.pdbqt -O "$ligands"/"$LIG"/.pdbqt --split --unique cansmi
                for file in $ligands/$LIG/*.pdbqt; do
                    sed -i '1{/^MODEL/d};${/^ENDMDL/d}' "$file"
                done
                rm "$ligands"/"$LIG"/"$LIG".pdbqt
            else
                if yad  --question --center --title="CODOC - QUESTION ?" \
                        --width=500 --height=200 \
                        --text="FILE FORMAT NOT RECOGNIZED. DO YOU WANT TO DELETE THE FILE \"$multi\"?" \
                        --text-align=center \
                        --button="NO":1 --button="YES":0 --buttons-layout=edge \
                        --borders=10 --on-top \
                        --image="$HOME"/MGLTools-1.5.7/doc/icons/questionP.png; then
                    rm "$multi"
                else
                    mkdir "$results_ligands/NOT_RECOGNIZED_LIGANDS/"
                    mv "$multi" "$results_ligands/NOT_RECOGNIZED_LIGANDS/"
                fi          
            fi
        fi
    done
fi

yad --info --center \
    --title="CODOC - CONFIRMATION !" \
    --text="THE SPLIT OF THE LIGANDS IS FINISHED! \nCHECK THE LIGANDS FOLDER" \
    --text-align=center \
    --button="OK":0 --buttons-layout=center \
    --width=500 --borders=10 --on-top \
    --image=$CODOC_DIR/icons/okP.png

show_ligand_menu
}

#################################################################################################################################
#                                       FRAGMENTATION FOR BIG DIRECTORIES FUNCTION:                                             #
#################################################################################################################################
run_split_folder() {

yad --info --center --title="CODOC - DIRECTORIES FRAGMENTATION !" \
    --text="MEMORY OTIMIZATION WITH BIG DIRECTORIES SPLIT...  \nPlease wait for completion !" \
    --text-align=center --button="CANCEL":1 --buttons-layout=center --width=500 --borders=10 --on-top \
    --image=$CODOC_DIR/icons/01P.png &
YAD_PID=$!
case $? in
    1) # CANCEL BUTTON
        break
        kill $YAD_PID
        show_ligand_menu
        return
        ;;
esac

# Iterate over all subfolders in the main directory
for SUBFOLDER in "$ligands"/*; do
    if [ -d "$SUBFOLDER" ]; then
        # Count the number of files in the subfolder
        FILE_COUNT=$(find "$SUBFOLDER" -type f | wc -l)

        if [ "$FILE_COUNT" -gt "$max_lig" ]; then
            echo "Subfolder $SUBFOLDER contains $FILE_COUNT files. Fragmenting..."

            # Create a new subfolder with the original name and a sequential number
            COUNTER=1
            NEW_FOLDER="$SUBFOLDER"_"$COUNTER"
            mkdir -p "$NEW_FOLDER"

            # Initialize the file counter
            FILES_IN_NEW_FOLDER=0

            # Move files to the new subfolders
            for FILE in "$SUBFOLDER"/*; do
                mv "$FILE" "$NEW_FOLDER"/
                FILES_IN_NEW_FOLDER=$((FILES_IN_NEW_FOLDER + 1))

                # Check if the new subfolder has reached $max_lig files
                if [ "$FILES_IN_NEW_FOLDER" -ge "$max_lig" ]; then
                    COUNTER=$((COUNTER + 1))
                    NEW_FOLDER="$SUBFOLDER"_"$COUNTER"
                    mkdir -p "$NEW_FOLDER"
                    FILES_IN_NEW_FOLDER=0
                fi
            done

            echo "Fragmentation completed for subfolder $SUBFOLDER with max $max_lig ligands."
        else
            echo "Subfolder $SUBFOLDER contains less than $max_lig files. It will not be fragmented."
        fi
    fi
done
# Remove all empty subfolders
find "$ligands" -type d -empty -delete
echo "All empty subfolders have been removed."
kill $YAD_PID 

yad --info --center \
    --title="CODOC - CONFIRMATION !" \
    --text="FOLDERS OVER \"$max_lig\" LIGANDS WERE FRAGMENTED INTO SUBFOLDERS OF UP TO \"$max_lig\" LIGANDS. CHECK THE SUBFOLDERS!" \
    --text-align=center \
    --button="OK":0 --buttons-layout=center \
    --width=500 --height=100 \
    --image=$CODOC_DIR/icons/okP.png

show_ligand_menu
}

#################################################################################################################################
#                           GENERATING LIPINSKI PARAMETERS FOR THE DATABASE (CSV DATASET):                                      #
#################################################################################################################################
run_lipinski_parameters() {
    LIPINSKI_DIR="$results_ligands/DATAFRAMES"
    mkdir -p "$LIPINSKI_DIR"  # Create directory if it doesn't exist

    yad --info --center --title="CODOC - LIPINSKI PARAMETERS !" \
        --text="GENERATING LIPINSKI PARAMETERS ! ... \nFOR THE DATABASE (SMI AND CSV DATASET) \nPlease wait for completion !" \
        --text-align=center --button="CANCEL":1 --buttons-layout=center --width=500 --borders=10 --on-top \
        --image=$CODOC_DIR/icons/01P.png &
    YAD_PID=$!
    case $? in
        1) # CANCEL BUTTON
            break
            kill $YAD_PID
            show_ligand_menu
            return
            ;;
    esac

    # Function to generate Lipinski parameters
    convert_to_lipinski() {
        local input_L="$1"
        local input_ext="$2"
        local output_smi="$3"
        local output_csv="$4"
        local output_lip="$5"
        for file in "$L"/*."$input_ext"; do
            LIG=$(basename "$file" ."$input_ext")
            obabel "$file" -O "$LIG".smi --title "$LIG" --addtotitle " $DIR" --append "MW logP HBA2 HBD rotors TPSA" -n
            if [[ "$input_ext" == "pdbqt" ]]; then
                smi=$(awk 'NR==2 {print $3}' "$file")
                sed -i "1s/^[^[:space:]]*/$smi/" "$LIG".smi
            fi
            cat "$LIG".smi >> "$output_lip"            
            echo -e "$LIG\t$smi" >> "$output_smi"
            echo -e "$LIG\t$smi" >> "$output_csv"
            rm "$LIG".smi
        done
    }

    # CONVERTING LIGANDS TO SMILES FILES WITH LIPINSKI PARAMETERS:
    for L in "$ligands"/*/; do
        DIR=$(basename "$L")
        mkdir -p "$LIPINSKI_DIR/$DIR"        
        first_file=$(find "$L" -maxdepth 1 -type f | head -n 1)
        if [[ -n "$first_file" ]]; then  # Check if there is at least one file in the subfolder
            extension="${first_file##*.}"
            output_smi="$L""$DIR".smi
            output_csv="$L""$DIR".csv
            output_lip="$L""$DIR"_lip.csv
            
            echo "Name Smiles DB MW logP HBA2 HBD rotors TPSA" >> "$output_lip"

            echo -e "name\tsmiles" >> "$output_csv"

            convert_to_lipinski "$L" "$extension" "$output_smi" "$output_csv" "$output_lip"

            echo "Converted $DIR.smi >>> $DIR.csv"
            mv "$output_lip" "$LIPINSKI_DIR/$DIR"
            mv "$output_smi" "$LIPINSKI_DIR/$DIR"
            mv "$output_csv" "$LIPINSKI_DIR/$DIR"
        else
            echo "No files found in the subfolder $L"
        fi
    done
    kill $YAD_PID
    yad --info --center \
        --title="CODOC - CONFIRMATION !" \
        --text="The .smi and .csv files have been generated for $DIR." \
        --text-align=center \
        --button="OK":0 --buttons-layout=center \
        --width=500 --borders=10 --on-top \
        --image=$CODOC_DIR/icons/okP.png

show_ligand_menu
}

#################################################################################################################################
#                               FUNCTION TO RUN DRUGGABILITY FILTER:                                                            #
#################################################################################################################################
run_druggability_filter() {
form_data5=$(
yad --form --center --title="DRUGGABILITY RULES FILTER" \
    --text="Change the fields below if necessary:" \
    --image="$CODOC_DIR/icons/configP.png" \
    --width=600 --height=400 \
    --separator="\n" \
    --button="LIGAND MENU":1 --button="RUN FILTER":0 --buttons-layout=edge \
    --field="Min. Molecular Weight:":NUM "$mw_1" \
    --field="Max. Molecular Weight:":NUM "$mw_2" \
    --field="Log P range:":NUM "$lp_2" \
    --field="Max. Rotatable Bonds:":NUM "$rb" \
    --field="Max. H Donor:":NUM "$hd" \
    --field="Max. H Acceptor:":NUM "$ha" \
    --field="Max. TPSA:":NUM "$tpsa" \
)

# Check if the user selected an option or pressed a button
case $? in
    0)  # RUN FILTER button pressed
        yad --info --center --title="CODOC - DRUGGABILITY RULES FILTER!" \
            --text="APPLYING DRUGGABILITY FILTER...  \nPlease wait for completion !" \
            --text-align=center --button="CANCEL":1 --buttons-layout=center --width=500 --borders=10 --on-top \
            --image=$CODOC_DIR/icons/01P.png &
        YAD_PID=$!
        mkdir -p $drug_dir
        touch .form_data5.txt
        echo -n > .form_data5.txt        
        echo "$form_data5" > .form_data5.txt
        # Replace commas with dots and read values into variables
        sed -i 's/,/./g' .form_data5.txt
        data5="$CODOC_DIR"/.form_data5.txt
        mw_1="$(sed -n '1p' $data5)"
        mw_2="$(sed -n '2p' $data5)"
        lp_2="$(sed -n '3p' $data5)"
        rb="$(sed -n '4p' $data5)"
        hd="$(sed -n '5p' $data5)"
        ha="$(sed -n '6p' $data5)"
        tpsa="$(sed -n '7p' $data5)"
        
        # Ensure the variables are exported so they are available later
        export mw_1 mw_2 lp_2 rb hd ha tpsa
        druggability_filter() {
            local file="$1"
            local dir_nL="$2"
            nl=$(basename "$file")
            obabel "$file" -O "$dir_nL"/"$nl" --filter "MW>$mw_1 & MW<$mw_2 & logP<$lp_2 & rotors<$rb & HBA2<$ha & HBD<$hd & TPSA<$tpsa"
            # Check if the conversion was successful by checking the return code of obabel
            if [ ! -s ""$dir_nL"/"$nl"" ]; then
                mv "$file" "$dir_nL"/"$nl"
            else
                rm "$dir_nL"/"$nl"
            fi
        }
        # Iterate through directories and process files
        for L in "$ligands"/*/; do
            nL=$(basename "$L")
            mkdir -p "$drug_dir"/"$nL"
            dir_nL="$drug_dir"/"$nL"
            list=$(mktemp)
            # Iterate through files in each directory
            for file in "$L"*; do
                echo "$file $dir_nL" >> "$list"
            done
            export -f druggability_filter
            parallel -j "$cpu" --colsep ' ' druggability_filter :::: "$list"
        done
        kill $YAD_PID
        show_ligand_menu
        ;;

    1)  # LIGAND MENU button pressed
        show_ligand_menu
        ;;
esac
}

#################################################################################################################################
#                                       LIGAND CONVERSION FUNCTION FOR PDBQT:                                                   #
#################################################################################################################################
run_ligands_conversion() {

    process_sdf2D() {
        local FILE="$1"
            nl=$(basename "$FILE" .sdf)
            echo ""$nl"_2D.sdf >>>> "$nl"_3D.pdbqt"
            smiles=$(obabel "$nl".sdf -osmi | awk '{print $1}' | sed 's/\[C\]/C/g; s/\[O\]/O/g')
            obabel "$nl".sdf -O "$nl".smi
            obabel "$nl".smi -O "$nl".mol2 -p "$pH" --gen3d --minimize --sd --steps "$steps" --ff GAFF -r
            obabel "$nl".mol2 -O "$nl".pdbqt
            sed -i '/^REMARK  Name/d' "$nl".pdbqt
            sed -i "1iREMARK  Name = "$nl"\nREMARK SMILES $smiles" "$nl".pdbqt
            rm "$FILE"
    }

    process_smi1D() {
        local FILE="$1"
        nl=$(basename "$FILE" .smi)
        smiles=$(awk '{print $1}' "$nl".smi | sed 's/\[C\]/C/g; s/\[O\]/O/g')
        obabel "$nl".smi -O "$nl".mol2 --gen3d -r
        obabel "$nl".mol2 -O "$nl".pdbqt -p
#        prepare_ligand -l "$nl".mol2
        sed -i '/^REMARK  Name/d' "$nl".pdbqt
        sed -i "1iREMARK  Name = "$nl"\nREMARK SMILES $smiles" "$nl".pdbqt
        rm "$FILE" && rm "$nl".mol2
    }

    process_files3D() {
        local FILE="$1"
        local EXT="${FILE##*.}"
            nl=$(basename "$FILE" ."$EXT")
            echo  ""$nl"_3D."$EXT" >>>> "$nl"_3D.pdbqt"
            obabel "$nl"."$EXT" -O "$nl".pdbqt -p "$pH" --partialcharge gasteiger --minimize --sd --steps $steps --ff GAFF -r
            smiles=$(obabel "$nl"."$EXT" -osmi | awk '{print $1}' | sed 's/\[C\]/C/g; s/\[O\]/O/g')
            sed -i '/^REMARK  Name/d' "$nl".pdbqt
            sed -i "1iREMARK  Name = "$nl"\nREMARK SMILES $smiles" "$nl".pdbqt
            rm "$FILE"
    }

    process_pdbqt() {
        local FILE="$1"
            nl=$(basename "$FILE" .pdbqt)
            echo  ""$nl".pdbqt >>>> "$nl"_smiles.pdbqt"
            smiles=$(obabel "$nl".pdbqt -osmi | awk '{print $1}' | sed 's/\[C\]/C/g; s/\[O\]/O/g')
            obabel "$nl".pdbqt -O "$nl".pdbqt -p "$pH" --minimize --sd --steps $steps --ff GAFF -r
            sed -i '/^REMARK  Name/d' "$nl".pdbqt
            sed -i "1iREMARK  Name = "$nl"\nREMARK SMILES $smiles" "$nl".pdbqt
    }
    process_mol() {
        local FILE="$1"
            nl=$(basename "$FILE" .mol2)
            echo  ""$nl".mol2 >>>> "$nl"_smiles.pdbqt"
            smiles=$(obabel "$nl".mol2 -osmi | awk '{print $1}' | sed 's/\[C\]/C/g; s/\[O\]/O/g')
            obabel "$nl".mol2 -O "$nl".pdbqt -p "$pH" --partialcharge gasteiger --minimize --sd --steps $steps --ff GAFF -r
            sed -i '/^REMARK  Name/d' "$nl".pdbqt
            sed -i "1iREMARK  Name = "$nl"\nREMARK SMILES $smiles" "$nl".pdbqt
            rm "$FILE"
    }

for L in "$ligands"/*/; do
    cd "$L"
    nL=$(basename "$L")
    # Failure directory
    failure="$failure_dir/$nL"
    mkdir -p "$failure"  # Create the directory only if it doesn't exist

    # Create the list of files in the directory
    list="$ligands/list_$nL.txt"
    touch "$list"
    echo -n > "$list"
    for FILE in "$L"*; do
        echo "$FILE" >> "$list"
    done

    # Check the first file:
    first_file=$(find "$L" -maxdepth 1 -type f | head -n 1)
    case "${first_file##*.}" in
        sdf)
            # Performing conversion with gnu parallel and OpenBabel for 2D sdf:
            # Check the third element of the sixth line in the first file:
            count=$(awk '$3 == "0.0000"' "$first_file" | wc -l)
            if [[ $count -gt 1 ]]; then               
                # Performing conversion with gnu parallel and OpenBabel for 2D sdf:
                export -f process_sdf2D
                total=$(wc -l < "$list")
                echo "SDF_2D $total"
                parallel -j "$cpu" --timeout "${time_limit}" -a "$list" process_sdf2D {} &
                parallel_pid=$!
                (
                  while kill -0 $parallel_pid 2>/dev/null; do
                    rest=$(ls "$L"/*.pdbqt 2>/dev/null | wc -l)
                    progress=$(( rest * 100 / total ))
                    echo $progress
                    sleep 0.2
                  done
                ) | yad --splash --progress --text="Converting \"$nL\" files…" \
                  --image=$CODOC_DIR/icons/progressP.png \
                  --auto-close \
                  --skip-taskbar \
                  --center --width=400 --borders=10 --on-top \
                  --button="CANCEL":1 --buttons-layout=center &
                yad_pid=$!

                wait $yad_pid
                yad_exit_code=$?

                if [ $yad_exit_code -eq 1 ]; then
                    kill $parallel_pid
                    mkdir "$canceled/$nL"
                    mv "$ligands/$nL" "$canceled/$nL"
                    echo "Conversion cancelled by user."
                    show_ligand_menu
                fi

                wait $parallel_pid
                                    
            else
                # Performing conversion with gnu parallel and OpenBabel for 3D sdf:
                export -f process_files3D
                total=$(wc -l < "$list")
                echo "SDF 3D $total"
                parallel -j "$cpu" --timeout "${time_limit}" -a "$list" process_files3D {} &
                parallel_pid=$!

                (
                  while kill -0 $parallel_pid 2>/dev/null; do
                    rest=$(ls "$L"/*.pdbqt 2>/dev/null | wc -l)
                    progress=$(( rest * 100 / total ))
                    echo $progress
                    sleep 0.2
                  done
                ) | yad --splash --progress --text="Converting \"$nL\" files…" \
                  --image=$CODOC_DIR/icons/progressP.png \
                  --auto-close \
                  --skip-taskbar \
                  --center --width=400 --borders=10 --on-top \
                  --button="CANCEL":1 --buttons-layout=center &
                yad_pid=$!

                wait $yad_pid
                yad_exit_code=$?

                if [ $yad_exit_code -eq 1 ]; then
                    kill $parallel_pid
                    echo "Conversion cancelled by user."
                    show_ligand_menu
                fi

                wait $parallel_pid
            fi
            # Move not converted .sdf files to the failure directory
            for FILE in "$L"*.sdf; do
                [ -e "$FILE" ] && mv "$FILE" "$failure" && echo "Moving $FILE to $failure"
            done
            ;;                       
        smi)
            # Performing conversion with gnu parallel and OpenBabel:
            export -f process_smi1D
            total=$(wc -l < "$list")
            parallel -j "$cpu" --timeout "${time_limit}" -a "$list" process_smi1D {} &
            parallel_pid=$!                
            (
              while kill -0 $parallel_pid 2>/dev/null; do
                rest=$(find "$L" -maxdepth 1 -type f -name "*.pdbqt" | wc -l)
                progress=$(( rest * 100 / total ))
                echo $progress
                sleep 0.2
              done
            ) | yad --splash --progress --text="Converting \"$nL\" files…" \
              --image=$CODOC_DIR/icons/progressP.png \
              --auto-close \
              --skip-taskbar \
              --center --width=400 --borders=10 --on-top \
              --button="CANCEL":1 --buttons-layout=center &
            if [ $? -eq 1 ]; then
                kill $parallel_pid
                show_ligand_menu
            fi
            wait $parallel_pid
        
            # Move not converted .smi files to the failure directory
            for FILE in "$L"*.{smi,mol2}; do
                [ -e "$FILE" ] && mv "$FILE" "$failure" && echo "Moving $FILE to $failure"
            done
            ;;
        pdb)
            # Performing conversion with gnu parallel and OpenBabel:
            export -f process_files3D
            total=$(wc -l < "$list")
            parallel -j "$cpu" --timeout "${time_limit}" -a "$list" process_files3D {} &
            parallel_pid=$!                
            (
              while kill -0 $parallel_pid 2>/dev/null; do
                rest=$(find "$L" -maxdepth 1 -type f -name "*.pdbqt" | wc -l)
                progress=$(( rest * 100 / total ))
                echo $progress
                sleep 0.2
              done
            ) | yad --splash --progress --text="Converting \"$nL\" files…" \
              --image=$CODOC_DIR/icons/progressP.png \
              --auto-close \
              --skip-taskbar \
              --center --width=400 --borders=10 --on-top \
              --button="CANCEL":1 --buttons-layout=center &
                if [ $? -eq 1 ]; then
                    kill $parallel_pid
                    show_ligand_menu
                fi
            wait $parallel_pid
        
            # Move not converted .pdb files to the failure directory
            for FILE in "$L"*.pdb; do
                [ -e "$FILE" ] && mv "$FILE" "$failure" && echo "Moving $FILE to $failure"
            done
            ;;
        mol2)
            # Performing conversion with gnu parallel and OpenBabel:
            export -f process_mol
            total=$(wc -l < "$list")
            parallel -j "$cpu" --timeout "${time_limit}" -a "$list" process_mol {} &
            parallel_pid=$!                
            (
              while kill -0 $parallel_pid 2>/dev/null; do
                rest=$(ls "$L"/*.pdbqt 2>/dev/null | wc -l)
                progress=$(( rest * 100 / total ))
                echo $progress
                sleep 0.2
              done
            ) | yad --splash --progress --text="Converting \"$nL\" files…" \
              --image=$CODOC_DIR/icons/progressP.png \
              --auto-close \
              --skip-taskbar \
              --center --width=400 --borders=10 --on-top \
              --no-buttons &
            wait $parallel_pid
        
            # Move not converted .mol2 files to the failure directory
            for FILE in "$L"*.mol2; do
                [ -e "$FILE" ] && mv "$FILE" "$failure" && echo "Moving $FILE to $failure"
            done
            ;;
        pdbqt)
            if yad --question --center --title="CODOC - QUESTION ?" \
                --width=500 --borders=10 --on-top \
                --text="THE FILES IN THE \"$nL\" FOLDER ARE ALREADY OF THE .PDBQT TYPE! DO YOU WANT TO RECONVERT THEM EVEN SO AS TO GENERATE THE HEADERS WITH SMILES AND NAME?" \
                --text-align=center \
                --button="NO":1 --button="YES":0 --buttons-layout=edge \
                --image=$CODOC_DIR/icons/questionP.png; then

                # Performing conversion with gnu parallel and OpenBabel:
                export -f process_pdbqt
                parallel -j "$cpu" --timeout "${time_limit}" -a "$list" process_pdbqt {} &
                parallel_pid=$!                
                yad --info --center \
                    --title="CODOC - CONFIRMATION !" \
                    --text="Please wait for it to finish..." \
                    --text-align=center \
                    --width=300 --borders=10 --no-buttons \
                    --image=$CODOC_DIR/icons/progressP.png &
                YAD_PID=$!
                wait $parallel_pid
                kill $YAD_PID
            fi
            ;;
        *)
            yad --info --center \
                --title="CODOC - WARNING !" \
                --text="FILES IN $L FOLDER ARE NOT RECOGNIZED !" \
                --text-align=center \
                --button="OK":0 --buttons-layout=center \
                --width=500 --borders=10 --on-top \
                --image=$CODOC_DIR/icons/warningP.png
            ;;
    esac
    rm "$list"            
    cd ../    
done

# Removes all files with extensions other than .pdbqt, i.e. remaining files that were not converted or moved:
find "$ligands" -type f ! -name "*.pdbqt" -exec rm {} +
cd $CODOC_DIR
yad --info --center \
    --title="CODOC - CONFIRMATION !" \
    --text="THE CONVERSION OF THE LIGANDS IS FINISHED! CHECK THE LIGANDS FOLDER" \
    --text-align=center \
    --button="OK":0 --buttons-layout=center \
    --width=500 --borders=10 --on-top \
    --image=$CODOC_DIR/icons/okP.png

show_ligand_menu
}


#################################################################################################################################
#                                       LIGAND REJECTED FUNCTION FOR PDBQT:                                                     #
#################################################################################################################################
run_pdbqt_rejected() {
    
    process_rejected() {
        local FILE="$1"
        local failure="$2"
        local nL="$3"
        local nl=$(basename "$FILE" .pdbqt)

        # Count occurrences of 0.000 or -0.000 in ATOM lines in x, y, z columns:
        count_ZEROS=$(awk '/^ATOM/ {count=0; for (i=6; i<=8; i++) if ($i == "0.000" || $i == "-0.000") count++; if (count == 2 || count == 3) print}' "$FILE" | wc -l)

        # Count occurrences of TORSDOF:
        count_TORSDOF=$(grep -c "^TORSDOF" "$FILE")

        # Check for repeated coordinates:
        repeated_coords=$(awk '
        BEGIN { x = ""; y = ""; z = ""; count = 0; }
        /^ATOM/ {
            matches = 0;
            if ($6 == x) { matches++; }
            if ($7 == y) { matches++; }
            if ($8 == z) { matches++; }

            if (matches > 2) {
                count++;
            } else {
                count = 1;
            }
            
            x = $6; y = $7; z = $8;

            if (count >= 2) {
                print "repetition"; exit 1;
            }
        }' "$FILE")

        if [[ $? -eq 1 ]]; then
            mv "$FILE" "$failure/$nl.pdbqt"
            echo "# - File: "$nl" with repeated atom coordinates has been moved to failure folder!"
        elif [[ $count_ZEROS -gt 1 ]]; then
            mv "$FILE" "$failure/$nl.pdbqt"
            echo "# - File: "$nl" with multiple 0.000 coordinates has been moved to failure folder!"
        elif [[ $count_TORSDOF -gt 1 ]]; then
            mv "$FILE" "$failure/$nl.pdbqt"
            echo "# - File: "$nl" with error TORSDOF found!"
        elif grep -q -E "^ATOM.*\b($reject)\b" "$FILE"; then
            mv "$FILE" "$failure/$nl.pdbqt"
            echo "# - File: "$nl" with atoms not recognized by Vina-GPU has been moved to failure folder!"
        elif grep -q -E "ATOM.*[0-9]{6,}" "$FILE"; then
            mv "$FILE" "$failure/$nl.pdbqt"
            echo "# - File: "$nl" with error BIG NUMBER found!"
        fi
        echo 1 >> "$failure"/."$nL"_count.txt
    }

    # Iterate over subdirectories in $ligands
    for L in "$ligands"/*/; do
        nL=$(basename "$L")
        failure="$failure_dir/$nL"
        mkdir -p "$failure"  # Create the directory if it doesn't exist
        list="$failure"/."$nL"_rejected.txt
        count_file="$failure"/."$nL"_count.txt
        touch "$list"
        echo -n > "$list"
        echo -n > "$count_file"
        (
        echo "# Generating "$nL" rejected list ..."

        # List .pdbqt files for progress tracking
        for FILE in "$L"*.pdbqt; do
            nl=$(basename "$FILE" .pdbqt)
            echo "$FILE" >> "$list"
        done     

        # Calculate total files for progress tracking
        total=$(wc -l < "$list")
        temp_count_file=$(mktemp)
        echo "# Total files to process: $total"
        echo "# Evaluating "$nL":"

        export -f process_rejected
        parallel -j "$cpu" process_rejected {} "$failure" "$nL" :::: "$list" &
        parallel_pid=$!
        while kill -0 "$parallel_pid" 2>/dev/null; do
            count=$(wc -l < "$count_file")
            progress=$((count * 100 / total))
            echo $progress  # Update progress
            sleep 0.5
        done
        ) | yad --progress --text="Progress:" \
              --title="CODOC - REJECTED LIGANDS" \
              --image="$CODOC_DIR/icons/progressP.png" \
              --center --height=500 --width=800 --borders=10 --on-top \
              --enable-log="Status:" --log-expanded --log-height=450 --auto-close \
              --button="CANCEL CURRENT":1 & 
        YAD_PID=$!
        wait
        exit_status=$?        
        if [ $exit_status -eq 1 ]; then
            # "CANCEL CURRENT" button pressed
            kill $parallel_pid
            kill $YAD_PID
        fi
        rm "$list" 
        rm "$count_file"
    done

    # YAD notification
    yad --info --center \
        --title="CODOC - CONFIRMATION!" \
        --text="THE LIGANDS REJECTION HAS BEEN FINALIZED! CHECK IN THE FAILURE FOLDER!" \
        --text-align=center \
        --button="OK":0 --buttons-layout=center \
        --width=500 --borders=10 --on-top \
        --image=$CODOC_DIR/icons/okP.png

    show_ligand_menu
}



#################################################################################################################################
#                                       LIGAND RECOVERY FUNCTION:                                                               #
#################################################################################################################################
run_pdbqt_recovery() {
    process_recovery() {
        local FILE="$1"
            nl=$(basename "$FILE" .pdbqt)
            echo  "# recovering ... "$nl".pdbqt"
            smiles=$(awk 'NR==2 && /^REMARK SMILES/ {print $3}' | sed 's/\[C\]/C/g; s/\[O\]/O/g' | tr 'C' 'c')
            obabel "$smiles" -O "$nl".mol2 -h --gen3d "$vel" --partialcharge gasteiger
            obabel "$nl".mol2 -O "$nl".pdbqt -p "$pH" --minimize --sd --steps "$steps" --ff GAFF -r
            sed -i '/^REMARK  Name/d' "$nl".pdbqt
            sed -i "1iREMARK  Name = "$nl"\nREMARK SMILES $smiles" "$nl".pdbqt
            rm "$nl".mol2
    }

    for L in "$ligands"/*/; do
        nL=$(basename "$F")
        list="$failure_dir"/."$nL"_recovery.txt
        failure="$failure_dir/$nL"
        touch "$list"
        for FILE in "$failure"*.pdbqt; do
            echo "$FILE" >> "$list"
        done
        # Performing conversion with gnu parallel and OpenBabel:
        export -f process_recovery
        total=$(wc -l < "$list")
        parallel -j "$cpu" --timeout "${time_limit2}" -a $list process_recovery {} &
        parallel_pid=$!                
        (
          while kill -0 $parallel_pid 2>/dev/null; do
            rest=$(find "$failure" -maxdepth 1 -type f -name "*.pdbqt" | wc -l)
            progress=$(( (total - rest) * 100 / total ))
            echo $progress
            sleep 0.5
          done
        ) | yad --splash --progress --text="Recovering \"$nF\" files…" \
          --image=$CODOC_DIR/icons/helpP.png \
          --auto-close --center --width=400 --borders=10 --on-top \
          --enable-log="Log:" --log-expanded --log-height=450 \
          --no-buttons &
        YAD_PID1=$!
        wait $parallel_pid
        kill $YAD_PID1
        (
        # Restore successfully converted .pdbqt files
        for lig in "$failure"*.pdbqt; do
            FILE=$(basename $lig .pdbqt)
            # Count occurrences of 0.000 or -0.000 in ATOM lines in x, y, z columns:
            count_ZEROS=$(awk '/^ATOM/ {count=0; for (i=6; i<=8; i++) if ($i == "0.000" || $i == "-0.000") count++; if (count == 2 || count == 3) print}' "$FILE" | wc -l)

            # Count occurrences of TORSDOF:
            count_TORSDOF=$(grep -c "^TORSDOF" "$FILE")

            # Check for repeated coordinates:
            repeated_coords=$(awk '
            BEGIN { x = ""; y = ""; z = ""; count = 0; }
            /^ATOM/ {
                matches = 0;
                if ($6 == x) { matches++; }
                if ($7 == y) { matches++; }
                if ($8 == z) { matches++; }

                if (matches > 2) {
                    count++;
                } else {
                    count = 1;
                }
                
                x = $6; y = $7; z = $8;

                if (count >= 2) {
                    print "repetition"; exit 1;
                }
            }' "$FILE")

            if [[ $? -eq 1 ]]; then
                # Kept file to the failure folder
                echo "# File: $FILE in $nF with repeated coordinates was kept in the failure folder"
            elif [[ $count_ZEROS -gt 1 ]]; then
                # Kept file to the failure folder
                echo "# File: $FILE in $nF with multiple coordinates 0.000 was kept in the failure folder"
            elif [[ $count_TORSDOF -gt 1 ]]; then
                # Kept file to the failure folder
                echo "# File: $FILE in $nF with multiple TORSDOF was kept in the failure folder"
            elif grep -q -E "^ATOM.*\b($reject)\b" "$FILE"; then
                # Kept file to the failure folder
                echo "# File: "$FILE" with atoms not recognized by Vina-GPU was kept in the failure folder"
            elif grep -q -E "ATOM.*[0-9]{6,}" "$FILE"; then
                # Kept file to the failure folder
                echo "# File: "$FILE" with BIG NUMBER was kept in the failure folder"
            else
                mkdir -p "$ligands/RECOVERED/$nL"
                mv "$lig" "$ligands/RECOVERED/$nL" && echo "# Moving $FILE to "$ligands/RECOVERED/$nL""
            fi
        done ) | yad --text-info --text="Recovering \"$nF\" files…" \
                      --image=$CODOC_DIR/icons/helpP.png \
                      --auto-close --center --width=400 --borders=10 --on-top \
                      --enable-log="Log:" --log-expanded --log-height=450 \
                      --no-buttons &
        YAD_PID2=$!
        wait $parallel_pid
        kill $YAD_PID2
    done   

yad --info --center \
    --title="CODOC - CONFIRMATION !" \
    --text="THE LIGANDS RECOVERY HAVE BEEN FINALIZED! CHECK IN THE FOLDER!" \
    --text-align=center \
    --button="OK":0 --buttons-layout=center \
    --width=500 --borders=10 --on-top \
    --image=$CODOC_DIR/icons/okP.png

show_ligand_menu
}

#################################################################################################################################
#                                       EMPTY LIGAND FUNCTION:                                                        #
#################################################################################################################################
run_empty() {
    # Create empty folder
    empty_dir="$results_ligands"/EMPTY_LIGANDS
    mkdir -p "$empty_dir"

    # YAD information dialog
    yad --info --center --title="CODOC - REMOVE EMPTY FILE !" \
        --text="Removing ligands files with sizes smaller than $file_size bytes ! ... Please wait for completion !" \
        --text-align=center --button="CANCEL":1 --buttons-layout=center --width=500 --borders=10 --on-top \
        --image="$CODOC_DIR/icons/01P.png" &
    YAD_PID=$!

    # Check if the cancel button is clicked
    if [ $? -eq 1 ]; then
        kill "$YAD_PID"
        show_ligand_menu
        return
    fi

    # Iterate through all directories
    for L in "$ligands"/*/; do
        nL=$(basename "$L")
        mkdir -p "$empty_dir/$nL"
        find "$L" -type f -size -"$file_size"c -exec mv {} "$empty_dir/$nL" \;
    done

    # Remove all empty subfolders
    find "$ligands" -type d -empty -delete
    echo "All empty subfolders have been removed."
    
    # Kill YAD process
    kill "$YAD_PID"

    # YAD confirmation dialog
    yad --info --center \
        --title="CODOC - CONFIRMATION !" \
        --text="THE LIGANDS EMPTY HAVE BEEN MOVED! CHECK EMPTY_LIST IN THE \"$empty\" FOLDER!" \
        --text-align=center \
        --button="OK":0 --buttons-layout=center --on-top \
        --width=500 --borders=10 \
        --image="$CODOC_DIR/icons/okP.png"

    show_ligand_menu
}


#################################################################################################################################
#                               FUNCTION TO CONFIGURE COGEN3D PARAMETERS:                                                       #
#################################################################################################################################
cogen3d_settings_form() {
form_data3=$(
yad --form --center --title="COGEN3D CONFIGURATION PARAMETERS" \
    --text="Change the fields below if necessary:" \
    --image="$CODOC_DIR/icons/configP.png" \
    --width=600 --height=600 \
    --separator="\n" \
    --button="LIGAND MENU":1 --button="OK":0 --buttons-layout=edge \
    --field="Min. Molecular Weight:":NUM "$mw_1" \
    --field="Max. Molecular Weight:":NUM "$mw_2" \
    --field="Min. Log P:":CBE "0"\!"-6"!"-5"!"-4"\!"-3"\!"-2"\!"-1"\!"0" \
    --field="Max. Log P:":CBE "$lp_2" \
    --field="Max. Rotatable Bonds:":NUM "$rb" \
    --field="Max. H Donor:":NUM "$hd" \
    --field="Max. H Acceptor:":NUM "$ha" \
    --field="Max. TPSA:":NUM "$tpsa" \
    --field="pH:":NUM $pH\!0..100\!0.1\!2 \
)

# Check if the user selected an option or pressed a button
case $? in
    0)  # OK button
        touch .form_data3.txt
        echo -n > .form_data3.txt
        echo "$form_data3" > .form_data3.txt
        sed -i 's/,/./g' .form_data3.txt
        # Updating docking parameters according to user choices:
        data3="$CODOC_DIR/.form_data3.txt"
        mw_1="$(sed -n '1p' $data3)"
        mw_2="$(sed -n '2p' $data3)"
        lp_1="$(sed -n '3p' $data3)"
        lp_2="$(sed -n '4p' $data3)"
        rb="$(sed -n '5p' $data3)"
        hd="$(sed -n '6p' $data3)"
        ha="$(sed -n '7p' $data3)"
        tpsa="$(sed -n '8p' $data3)"
        pH="$(sed -n '9p' $data3)"
        export mw_1 mw_2 lp_1 lp_2 rb hd ha tpsa pH
        show_ligand_menu
        ;;
    1)  # Main Menu button
        show_ligand_menu
        ;;
esac
}

#################################################################################################################################
#                               FUNCTION TO CONVERT WITH COGEN3D:                                                               #
#################################################################################################################################
run_cogen3d_conversion() {
# Run CoGen3D:
if [ -f "$CODOC_DIR/bin/CoGen3D.py" ]; then
    echo "Runing CoGen3D!"
        python3 $CODOC_DIR/bin/CoGen3D.py inp --codoc --ph "$pH" --mw_min "$mw_1" --mw_max "$mw_2" --logp_min "$lp_1" --logp_max "$lp_2" --rotB_max "$rb" --hbd_max "$hd" --hba_max "$ha" --tpsa_max "$tpsa"
        mkdir -p "$COGEN3D_DIR"
        mv "$CODOC_DIR/ERRORS" "$COGEN3D_DIR"
        mv "$CODOC_DIR/CSV" "$COGEN3D_DIR"
        mv "$CODOC_DIR/SDF" "$COGEN3D_DIR"
        mv "$CODOC_DIR/PERFORMANCE_METRICS.txt" "$COGEN3D_DIR"

    else
        yad --info --center \
            --title="CODOC - INFORMATION !" \
            --text="THE COGEN3D.PY SCRIPT IS MISSING. COPY THE SCRIPT FILE TO THE CURRENT DIRECTORY: \"$CODOC_DIR\"!" \
            --text-align=center \
            --button="OK":0 --buttons-layout=center \
            --width=500 --borders=10 --on-top \
            --image=$CODOC_DIR/icons/attentionP.png
fi
show_ligand_menu
}

#################################################################################################################################
#                                       FUNCTION FOR REMOVE BOND BREAKS IN MACROCYCLIC RINGS:                                   #
#################################################################################################################################
run_macrocyclic() {
    MACROCYCLES_DIR="$results_ligands/MACROCYCLES"
    mkdir -p "$MACROCYCLES_DIR"    
    
    yad --info --center --title="CODOC - MACROCYCLIC RINGS !" \
        --text="REMOVING BOND BREAKS IN MACROCYCLIC RINGS ! ... Please wait for completion !" \
        --text-align=center --button="CANCEL":1 --buttons-layout=center --width=500 --borders=10 --on-top \
        --image=$CODOC_DIR/icons/01P.png &
    YAD_PID=$!
    case $? in
        1) # CANCEL BUTTON
            break
            kill $YAD_PID
            show_ligand_menu
            return
            ;;
    esac

    # Search for .pdbqt files within subfolders
    for L in "$ligands"/*/; do
        nL=$(basename "$L")
        mkdir -p "$MACROCYCLES_DIR/$nL"

        for FILE in "$L"/*.pdbqt; do
            if grep -q '^ATOM.*\bG\b' "$FILE"; then
                # Copy the file to the Macrocycles directory
                cp "$FILE" "$MACROCYCLES_DIR/$nL"
                
                # Replace words only in lines that start with 'ATOM' and maintain character spacing
                sed -i '/^ATOM/ {
                    s/\bCG\b/C /g
                    s/\bCG0/C  /g
                    s/\bCG1/C  /g
                    s/\bCG2/C  /g
                    s/\bCG3/C  /g
                    s/\bG0/C /g
                    s/\bG1/C /g
                    s/\bG2/C /g
                    s/\bG3/C /g
                    s/\bCG/C /g
                    s/\bG\b/C/g
                }' "$FILE"
                
                echo "$FILE fixed"
            fi
        done
    done

    # Remove any empty directories in the Macrocycles directory
    find "$MACROCYCLES_DIR" -type d -empty -delete
    kill $YAD_PID
    yad --info --center \
        --title="CODOC - CONFIRMATION!" \
        --text="REMOVED BOND BREAKS IN MACROCYCLIC RINGS! CHECK IN THE FOLDER!" \
        --text-align=center \
        --button="OK":0 --buttons-layout=center \
        --width=500 --borders=10 --on-top \
        --image="$CODOC_DIR/icons/okP.png"

    show_ligand_menu
}

#################################################################################################################################
#                                       FUNCTION TO GENERATE LIST OF NEW EXECUTIONS IN CPU:                                            #
#################################################################################################################################

list_new_cpu() {
yad --info --text="Generating lists of ligands and targets for NEW CPU processing…" \
  --image=$CODOC_DIR/icons/progressP.png \
  --center --width=400 --borders=10 --on-top \
  --no-buttons &
    yad_pid=$!

    P_list="$targets"/.P_list.txt
    selected_result="$results_doc"/.selected_result.txt
    echo -n > "$P_list"
    echo -n > "$selected_result"
    for P in "$targets"/*/; do
        nP=$(basename "$P")
        echo $P >> $P_list
    done
    L_list="$ligands"/.L_list.txt
    echo -n > "$L_list"
    for L in "$ligands"/*/; do
        nL=$(basename "$L")
        echo $L >> $L_list
    done
    for L in "$ligands"/*/; do
        nL=$(basename "$L")
        l_list="$ligands"/."$nL"_list.txt
        echo -n > "$l_list"
        for l in "$L"/*.pdbqt; do
            nl=$(basename "$l")
            echo $l >> $l_list
        done
    done
    kill $yad_pid
}

#################################################################################################################################
#                                FUNCTION TO GENERATE LIST OF RESTARTED EXECUTIONS IN CPU:                                      #
#################################################################################################################################

list_restart_cpu() {
    # List the result directories and save them to the file
    list_results="$results_doc"/.list_results.txt
    echo -n > "$list_results"
    for dir in "$results_doc"/*/; do
        result_dir=$(basename "$dir")
        echo "$result_dir" >> "$list_results"
    done

    # Display the list of results in checklist format
    selected_result=$(yad --list --radiolist --title="CODOC - RESTART CPU DOCKING" --margins=10 \
        --text="Select a result to restart:" --center --text-align=center \
        --width=600 --height=500 --borders=10 --on-top \
        --column="Select" --column="Results" $(awk '{print "FALSE", $0}' "$list_results") --separator="\n" \
        --button="DOCKING MENU":1 --button="RUN":0 --buttons-layout=edge \
        --image="$CODOC_DIR/icons/docP.png" --print-column=2 
    )
    if [[ $? -eq 0 && -n "$selected_result" ]]; then
        echo "$selected_result" >> "$results_doc"/.selected_result.txt
        L_list="$ligands"/.L_list.txt
        echo -n > "$L_list"
        P_list="$targets"/.P_list.txt
        echo -n > "$P_list"
        for P in "$results_doc"/"$selected_result"/*/; do
            nP=$(basename "$P")
            for L in "$ligands"/*/; do
                nL=$(basename "$L")
                mkdir -p "$results_doc"/"$selected_result"/"$nP"/"$nL"
            done
            for L in "$P"*/; do
                nL=$(basename "$L")
                count_Lp=$(find "$L" -mindepth 1 -maxdepth 1 -type d | wc -l)
                count_Lt=$(find "$ligands/$nL" -maxdepth 1 -type f -name "*.pdbqt" | wc -l)
                difference=$(( count_Lt - count_Lp ))
                if (( difference > 4 )); then
                    echo "$ligands"/"$nL" >> $L_list
                    if ! grep -Fxq "$targets/$nP" "$P_list"; then
                        echo "$targets/$nP" >> "$P_list"
                    fi
                fi
                l_list="$ligands"/."$nL"_list.txt
                echo -n > "$l_list"
                count_lp=$(find "$L" -maxdepth 1 -type f -name "*.pdbqt" | wc -l)
                    if (( difference > 4 )); then
                        for l in $L/*.pdbqt; do
                            nl=$(basename "$l")
                            echo "$ligands"/"$nL"/"$nl" >> $l_list
                        done
                    fi
            done
        done
    elif [[ $? -eq 1 ]]; then
        show_docking_menu
    fi
}

#################################################################################################################################
#                                       FUNCTION TO GENERATE LIST OF NEW EXECUTIONS IN GPU:                                            #
#################################################################################################################################

list_new_gpu() {
yad --info --text="Generating lists of ligands and targets for NEW GPU processing…" \
  --image=$CODOC_DIR/icons/progressP.png \
  --center --width=400 --borders=10 --on-top \
  --no-buttons &
    yad_pid=$!

    P_list="$targets"/.P_list.txt
    selected_result="$results_doc"/.selected_result.txt
    echo -n > "$P_list"
    echo -n > "$selected_result"
    for P in "$targets"/*/; do
        nP=$(basename "$P")
        echo $P >> $P_list
    done
    L_list="$ligands"/.L_list.txt
    echo -n > "$L_list"
    for L in "$ligands"/*/; do
        nL=$(basename "$L")
        echo $L >> $L_list
    done
    kill $yad_pid
}

#################################################################################################################################
#                                       FUNCTION TO GENERATE LIST OF RESTARTED EXECUTIONS IN GPU:                                      #
#################################################################################################################################

list_restart_gpu() {
    # List the result directories and save them to the file
    list_results="$results_doc"/.list_results.txt
    echo -n > "$list_results"
    for dir in "$results_doc"/*/; do
        result_dir=$(basename "$dir")
        echo "$result_dir" >> "$list_results"
    done

    # Display the list of results in checklist format
    selected_result=$(yad --list --radiolist --title="CODOC - RESTART GPU DOCKING" --margins=10 \
        --text="Select a result to restart:" --center --text-align=center \
        --width=600 --height=500 --borders=10 --on-top \
        --column="Select" --column="Results" $(awk '{print "FALSE", $0}' "$list_results") --separator="\n" \
        --button="DOCKING MENU":1 --button="RUN":0 --buttons-layout=edge \
        --image="$CODOC_DIR/icons/docP.png" --print-column=2 
    )
    if [[ $? -eq 0 && -n "$selected_result" ]]; then
        echo "$selected_result" >> "$results_doc"/.selected_result.txt
        L_list="$ligands"/.L_list.txt
        echo -n > "$L_list"
        P_list="$targets"/.P_list.txt
        echo -n > "$P_list"
        for P in "$results_doc"/"$selected_result"/*/; do
            nP=$(basename "$P")
            for L in "$ligands"/*/; do
                nL=$(basename "$L")
                mkdir -p "$results_doc"/"$selected_result"/"$nP"/"$nL"
            done
            for L in "$P"/*/; do
                nL=$(basename "$L")
                count_Lp=$(find "$L" -mindepth 1 -maxdepth 1 -type d | wc -l)
                count_Lt=$(find "$ligands/$nL" -maxdepth 1 -type f -name "*.pdbqt" | wc -l)
                difference=$(( count_Lt - count_Lp ))
                if (( difference > 4 )); then
                    echo "$ligands"/"$nL" >> $L_list
                    if ! grep -Fxq "$targets/$nP" "$P_list"; then
                        echo "$targets/$nP" >> "$P_list"
                    fi
                fi
            done
        done
    elif [[ $? -eq 1 ]]; then
        show_docking_menu
    fi
}

#################################################################################################################################
#                                       FUNCTION TO PERFORM RIGID DOCKING (WITH CPU):                                           #
#################################################################################################################################
run_rigid_docking_cpu() {

missing_files=""

# Verificar se existe pelo menos um arquivo .pdbqt em $ligands
for dir_L in "$ligands"/*/; do
  if [ -z "$(find "$dir_L" -maxdepth 1 -name "*.pdbqt" -print -quit)" ]; then
    missing_files+="$dir_L: arquivos pdbqt ausentes\n"
  fi
done

# Verificar a existência de grid.txt e protein.pdbqt em $targets
for dir_T in "$targets"/*/; do
  if [ ! -f "$dir_T/grid.txt" ] || [ ! -f "$dir_T/protein.pdbqt" ]; then
    missing_files+="$dir_T: grid.txt ou protein.pdbqt ausente(s)\n"
  fi
done

# Exibir uma mensagem se arquivos estiverem ausentes
if [ -n "$missing_files" ]; then
    yad --center --title="CODOC - AVISO!" \
        --width=500 --borders=10 --on-top \
        --text="\nARQUIVOS AUSENTES: \n$missing_files\n\nPor favor! Adicione os arquivos correspondentes à pasta!" \
        --text-align=center \
        --button="OK":0 --buttons-layout=edge \
        --image="$CODOC_DIR/icons/attentionP.png"
    if [ $? -eq 0 ]; then
        clear
        exit 0
    fi
fi

# Start of the total time counter, total ligands count and targets count:
start_time_total=$(date +%s)
target_account=0
crossings=0
    
# Path to the hidden file
selected_result="$results_doc/.selected_result.txt"

# Check if the file is empty
if [ ! -s "$selected_result" ]; then
    # The file is empty, execute the commands
    result_folder="${current_date}_RIGID_DOCKING_RESULT_CPU"
    RR="$results_doc"/"$result_folder"
    mkdir -p "$RR"
    rsync -av --include=*/ --exclude=* $targets/* $RR
else
    # The file contains an address, assign the value to the RR variable
    result_folder=$(cat "$selected_result")
    RR="$results_doc"/"$result_folder"
fi

# 1st FOR Loop enters each protein folder present in the TARGETS folder, assigns the GridBox parameters, and copies the ligand group directories to the RIGID_DOCKING_RESULT_"$current_date" folder:
while IFS= read -r P; do
    nP=$(basename "$P")
    p="$targets/$nP/protein.pdbqt"

    # Check if the file is empty
    if [ ! -s "$selected_result" ]; then
        # The file is empty, execute the commands
        rsync -av --include=*/ --exclude=* "$ligands"/* "$RR"/"$nP"
        rp=$RR/"$nP"/"$result_folder"_"$nP".csv && touch "$rp"
        dp=$RR/"$nP"/"$result_folder"_PERFORMANCE_"$nP".txt && touch "$dp"
    else
        # The file contains an address, assign the value to the RR variable
        rp=$RR/"$nP"/"$result_folder"_"$nP".csv
        dp=$RR/"$nP"/"$result_folder"_PERFORMANCE_"$nP".txt
    fi
    
    # Checks if the grid.txt file exists in the $targets/$nP folder
    if [ -f "$targets/$nP/grid.txt" ]; then
        # If the file exists, it updates the Grid Box parameters:
        grid=/$targets/$nP/grid.txt
        # Extract the line containing "center/size" and get the values:
        center_line=$(grep 'center' "$grid")
        c_x=$(echo "$center_line" | awk '{print $2}')
        c_y=$(echo "$center_line" | awk '{print $3}')
        c_z=$(echo "$center_line" | awk '{print $4}')
        size_line=$(grep 'npts' "$grid")
        s_x=$(echo "$size_line" | awk '{print $2}')
        s_y=$(echo "$size_line" | awk '{print $3}')
        s_z=$(echo "$size_line" | awk '{print $4}')
    else
        yad --info --center --title="CODOC - WARNING !" \
            --text="The grid.txt file was not found in the $targets/$nP folder. Generate the text file named as grid.txt in ADT, save it in the $targets/$nP folder, and restart CODOC." \
            --text-align=center \
            --button="OK":0 --buttons-layout=center \
            --width=500 --borders=10 --on-top \
            --image=$CODOC_DIR/icons/warningP.png
            if [ $? -eq 0 ]; then
                show_docking_menu
            fi
    fi

    #  Generates the headers where PARTIAL PERFORMANCES will be recorded in each of the targets:
    echo "########################################################################################" >> "$dp"
    echo "#                                 CODOC VERSION 2024.1:                                #" >> "$dp"
    echo "#                         			15/07/2025					                     #" >> "$dp"
    echo "########################################################################################" >> "$dp"
    echo "                                                                                        " >> "$dp"
    echo "########################################################################################" >> "$dp"
    echo "#                                 FROM TARGET: $nP                                     #" >> "$dp"
    echo "########################################################################################" >> "$dp"
    echo "                                                                                        " >> "$dp"

    # Generates the headers where the PARTIAL RESULTS will be recorded in each of the targets:
    echo "" >> "$rp"
    echo "TARGET	$nP" >> "$rp"

    ((target_account++)) # Adds 1 more to the target account
    
    # 2nd FOR Loop goes through each subfolder, with the ligand database, within the LIGANTES folder:
    while IFS= read -r L; do
        nL=$(basename "$L")
        total=$(ls -1 $L | wc -l)
        # Start of time counter and ligands account for the ligand databank:
        start_time_P=$(date +%s)
        account_ligands=0

        # Create a configuration file for each protein:
        touch $RR/$nP/$nL/config.txt
        config_file="$RR/$nP/$nL/config.txt"

        # Generates the headers where the LIGAND GROUPS will be recorded in the performance file:       
        echo "                                                                                        " >> "$dp"
        echo "----------------------------------------------------------------------------------------" >> "$dp"
        echo "/////////////////////////////FROM LIGAND DATABANK: $nL /////////////////////////////////" >> "$dp"
        echo "----------------------------------------------------------------------------------------" >> "$dp"
        echo "                                                                                        " >> "$dp"

        # Generates the headers where the LIGAND GROUPS will be recorded in the partial results file:
        echo "" >> "$rp"
        echo "LIGAND_DATABANK	$nL" >> "$rp"
        echo "SMILES	LIGAND	BINDING_ENERGY(Kcal/mol)	RMSD(mean)" >> "$rp"

        counter=0            
        (
        # 3rd FOR Loop executes docking on each .pdbqt ligand present in the subfolder:
        while IFS= read -r l; do
            nl=$(basename "$l" .pdbqt)
            ((counter++))
            mkdir -p "$RR/$nP/$nL/$nl"
            # Create a config file for each proteins and ligand database:   
            cat <<EOL > "$config_file"
receptor = $p
ligand = $l
scoring = $sf
center_x = $c_x
center_y = $c_y
center_z = $c_z
size_x = $s_x
size_y = $s_y
size_z = $s_z	
out = $RR/$nP/$nL/$nl/$nl.pdbqt
cpu = $cpu
exhaustiveness = $ext
num_modes = $num_poses
min_rmsd = $min_rmsd
energy_range = $energy_range
spacing = $spacing
EOL

            # YAD Progress Bar Update:
            ((crossings+=1))
            ((account_ligands+=1))
            progress=$(( account_ligands * 100 / total ))
            echo "$progress"
            echo "#\n Total Ligands: $total\n Ligands Processed: $account_ligands\n Last Ligand Processed: $nl\n Ligand Base: $nL\n Target: $nP\n"

            echo "////////////////////////////////////////////////////////////"
            echo "/Running the docking ... // Ligand: $nl // Protein: $nP     "
            echo "////////////////////////////////////////////////////////////"
            # Running the docking calculation
            $vina --config $config_file > /dev/null 1>&2 &
            if ((counter % "$cpu_parallel" == 0)); then
                wait
                counter=0
            fi
        done < "$ligands/."$nL"_list.txt"
        )  | yad --progress --text="Docking progress ..." --center --on-top \
                --image=$CODOC_DIR/icons/rigidP.png \
                --auto-close\
                --title="CODOC - CPU Rigid Docking" --button="NEXT BASE":1 --button="NEXT TARGET":2 --button="CANCEL ALL":3 \
                --width=600 --borders=10 &
        YAD_PID=$!
        wait $YAD_PID
        exit_status=$?
        if [ $exit_status -eq 1 ]; then
            # CANCEL CURRENT button pressed
            pkill vina_1.2.5_linux_x86_64
            continue
        elif [ $exit_status -eq 2 ]; then
            # NEXT TARGET button pressed
            pkill vina_1.2.5_linux_x86_64
            break
        elif [ $exit_status -eq 3 ]; then
            # CANCEL ALL button pressed
            pkill vina_1.2.5_linux_x86_64
            return
        fi

        yad --info --text="\n Spliting \"$nL\" files…\n Wait for the end ! " --text-align=center \
              --image=$CODOC_DIR/icons/progressP.png \
              --skip-taskbar \
              --center --width=400 --borders=10 --on-top \
              --no-buttons &
        SPLIT_PID=$!
        for s in "$RR/$nP/$nL/"*/; do
            b=$(basename "$s")
            echo "////////////////////////////////////////////////////////////"
            echo "/Running the Vina Split // Ligand: $b                      /"
            echo "////////////////////////////////////////////////////////////"
            if [ "$split" = "yes" ]; then
                # Decomposes each $nl.pdbqt output result into the pose files:           
                $vina_split --input $s/$b.pdbqt # Running the vina split
            fi

            # Extracts binding energy and RMSD of the out.pdbqt multimodel file:
            energy_md1=$(awk '/MODEL 1/ {getline; if ($0 ~ /REMARK VINA RESULT:/) print; exit}' "$s/$b.pdbqt")
            results_rmsd=$(grep 'REMARK VINA RESULT:' "$s/$b.pdbqt")
            results_smiles=$(grep 'REMARK SMILES' "$s/$b.pdbqt" | head -n 1)                
            e=$(echo "$energy_md1" | awk '{print $4}')
            rmsd=$(echo "$results_rmsd" | awk '{print $5}')
            smi=$(echo "$results_smiles" | awk '{print $3}')
            
            # Calculating the average RMSD of extracted values:
                r=$(echo $rmsd | awk '{ 
                    sum = 0; 
                    for (i = 1; i <= NF; i++) { 
                        sum += $i; 
                    } 
                    print sum / NF  
                }')                                
            # Saves the ligand name, binding energy and rmsd to the result file:
            echo "$smi	$b	$e	$r" >> "$rp"
        done
        cp "$p" "$RR/$nP/$nL/"
        kill $SPLIT_PID
        # Calculation of partial elapsed time and partial performance information for each binder group:
        end_time_P=$(date +%s)
        parcial_time=$((end_time_P - start_time_P))
        days=$((parcial_time / 86400))
        hours=$(( (parcial_time % 86400) / 3600 ))
        minutes=$(( (parcial_time % 3600) / 60 ))
        seconds=$((parcial_time % 60))

        echo "                                                                                        " >> "$dp"
        echo "              $account_ligands LIGANDS WERE PROCESSED                             	  " >> "$dp"
        echo "                                                                                        " >> "$dp"
        echo "                                                                                        " >> "$dp"
        echo "	    Elapsed time: $parcial_time seconds												  " >> "$dp"
        echo "		Elapsed time: $days days : $hours hours : $minutes minutes : $seconds seconds     " >> "$dp"
        echo "                                                                                        " >> "$dp"
        echo "----------------------------------------------------------------------------------------" >> "$dp"
    done < "$ligands/.L_list.txt"    
done < "$targets/.P_list.txt"

yad --info --center \
    --title="CODOC - CONFIRMATION !" \
    --text="RIGID DOCKING WITH CPU IS OVER! CHECK THE $result_folder FOLDER." \
    --text-align=center \
    --button="OK":0 --buttons-layout=center \
    --width=500 --borders=10 --on-top \
    --image=$CODOC_DIR/icons/okP.png

show_docking_menu
}

#################################################################################################################################
#                                       FUNCTION TO PERFORM RIGID DOCKING (WITH GPU):                                           #
#################################################################################################################################
run_rigid_docking_gpu() {

missing_files=""

# Verificar se existe pelo menos um arquivo .pdbqt em $ligands
for dir_L in "$ligands"/*/; do
  if [ -z "$(find "$dir_L" -maxdepth 1 -name "*.pdbqt" -print -quit)" ]; then
    missing_files+="$dir_L: arquivos pdbqt ausentes\n"
  fi
done

# Verificar a existência de grid.txt e protein.pdbqt em $targets
for dir_T in "$targets"/*/; do
  if [ ! -f "$dir_T/grid.txt" ] || [ ! -f "$dir_T/protein.pdbqt" ]; then
    missing_files+="$dir_T: grid.txt ou protein.pdbqt ausente(s)\n"
  fi
done

# Exibir uma mensagem se arquivos estiverem ausentes
if [ -n "$missing_files" ]; then
    yad --center --title="CODOC - AVISO!" \
        --width=500 --borders=10 --on-top \
        --text="\nARQUIVOS AUSENTES: \n$missing_files\n\nPor favor! Adicione os arquivos correspondentes à pasta!" \
        --text-align=center \
        --button="OK":0 --buttons-layout=edge \
        --image="$CODOC_DIR/icons/attentionP.png"
    if [ $? -eq 0 ]; then
        clear
        exit 0
    fi
fi

# Start of the total time counter, total ligands count and targets count:
start_time_total=$(date +%s)
target_account=0
crossings=0

# Path to the hidden file
selected_result="$results_doc/.selected_result.txt"

# Check if the file is empty
if [ ! -s "$selected_result" ]; then
    # The file is empty, execute the commands
    result_folder="${current_date}_RIGID_DOCKING_RESULT_GPU"
    RR="$results_doc"/"$result_folder"
    mkdir -p "$RR"
    rsync -av --include=*/ --exclude=* $targets/* $RR
else
    # The file contains an address, assign the value to the RR variable
    result_folder=$(cat "$selected_result")
    RR="$results_doc"/"$result_folder"
fi

# 1st FOR Loop enters each protein folder present in the TARGETS folder, assigns the GridBox parameters, and copies the ligand group directories to the RIGID_DOCKING_RESULT_"$current_date" folder:
while IFS= read -r P; do
    nP=$(basename "$P")
    p="$targets/$nP/protein.pdbqt"

    # Check if the file is empty
    if [ ! -s "$selected_result" ]; then
        # The file is empty, execute the commands
        rsync -av --include=*/ --exclude=* "$ligands"/* "$RR"/"$nP"
        rp=$RR/"$nP"/"$result_folder"_"$nP".csv && touch "$rp"
        dp=$RR/"$nP"/"$result_folder"_PERFORMANCE_"$nP".txt && touch "$dp"
    else
        # The file contains an address, assign the value to the RR variable
        rp=$RR/"$nP"/"$result_folder"_"$nP".csv
        dp=$RR/"$nP"/"$result_folder"_PERFORMANCE_"$nP".txt
    fi

    # Checks if the grid.txt file exists in the $targets/$nP folder
    if [ -f "$targets/$nP/grid.txt" ]; then
        # If the file exists, it updates the Grid Box parameters:
        grid=/$targets/$nP/grid.txt
        # Extract the line containing "center/size" and get the values:
        center_line=$(grep 'center' "$grid")
        c_x=$(echo "$center_line" | awk '{print $2}')
        c_y=$(echo "$center_line" | awk '{print $3}')
        c_z=$(echo "$center_line" | awk '{print $4}')
        size_line=$(grep 'npts' "$grid")
        s_x=$(echo "$size_line" | awk '{print $2}')
        s_y=$(echo "$size_line" | awk '{print $3}')
        s_z=$(echo "$size_line" | awk '{print $4}')
    else
        yad --info --center --title="CODOC - WARNING !" \
            --text="The grid.txt file was not found in the $targets/$nP folder. Generate the text file named as grid.txt in ADT, save it in the $targets/$nP folder, and restart CODOC." \
            --text-align=center \
            --button="OK":0 --buttons-layout=center \
            --width=500 --borders=10 --on-top \
            --image=$CODOC_DIR/icons/warningP.png

            show_docking_menu
    fi

    #  Generates the headers where PARTIAL PERFORMANCES will be recorded in each of the targets:
    echo "########################################################################################" >> "$dp"
    echo "#                                 CODOC VERSION 2024.1 :                               #" >> "$dp"
    echo "#                         			15/07/2025					                     #" >> "$dp"
    echo "########################################################################################" >> "$dp"
    echo "                                                                                        " >> "$dp"
    echo "########################################################################################" >> "$dp"
    echo "                                  FROM TARGET: $nP                                      " >> "$dp"
    echo "########################################################################################" >> "$dp"
    echo "                                                                                        " >> "$dp"

    # Generates the headers where the PARTIAL RESULTS will be recorded in each of the targets:
    echo "" >> "$rp"
    echo "TARGET	$nP" >> "$rp"

    ((target_account++)) # Adds 1 more to the target count
    
    # 2nd FOR Loop goes through each subfolder, with the ligand database, within the LIGANTES folder:
    while IFS= read -r L; do
        nL=$(basename "$L")
        total=$(find "$L" -maxdepth 1 -type f -name "*.pdbqt" | wc -l)

        # Start of the split time counter for the ligand group:
        parcial_time=0
        start_time_P=$(date +%s)
        account_ligands=0

        # Create a configuration file for each protein:
        touch $RR/$nP/$nL/config.txt
        config_file="$RR/$nP/$nL/config.txt"
        
        # Generates the headers where the LIGAND GROUPS will be recorded in the performance file:       
        echo "                                                                                        " >> "$dp"
        echo "----------------------------------------------------------------------------------------" >> "$dp"
        echo "                             FROM LIGAND DATABANK: $nL:                                 " >> "$dp"
        echo "----------------------------------------------------------------------------------------" >> "$dp"
        echo "                                                                                        " >> "$dp"

        # Generates the headers where the LIGAND GROUPS will be recorded in the partial results file:
        echo "" >> "$rp"
        echo "LIGAND_DATABANK	$nL" >> "$rp"
        echo "SMILES	LIGAND	BINDING_ENERGY(Kcal/mol)	RMSD(mean)" >> "$rp"

        # Create a config file for each proteins and ligand database:   
        cat <<EOL > "$config_file"
receptor = $p
ligand_directory = $L
output_directory = $RR/$nP/$nL/
opencl_binary_path = $VINAGPU_DIR
center_x = $c_x
center_y = $c_y
center_z = $c_z
size_x = $s_x
size_y = $s_y
size_z = $s_z
thread = $threads
EOL
        echo "////////////////////////////////////////////////////////////"
        echo "/Running the docking calculation in ligands database: "$L"  "
        echo "////////////////////////////////////////////////////////////"
        echo -n > $track_progress
        cat <<EOL > "$track_progress"
0 ligands docked
0 total ligands
0.00% complete
00:00:00 ETA
00:00:00 running time
0000-00-00 00:00:00 (Estim. completion)
EOL
        # Running the docking calculation
        $vina_GPU --config "$config_file" &
        VINA_PID=$!
        while kill -0 $VINA_PID > /dev/null 1>&2; do
            ligands_docked=$(awk 'NR==1 {print $1}' "$track_progress")
            ligands_total=$(awk 'NR==2 {print $1}' "$track_progress")
            progress=$(awk 'NR==3 {print $1}' "$track_progress" | sed 's/%//')
            eta=$(awk 'NR==4 {print $1}' "$track_progress")
            completion=$(awk 'NR==6 {print $1, $2}' "$track_progress")
            echo $progress
            echo "#\n Target: $nP\n Ligand Base: $nL\n Total Ligands: $ligands_total\n Ligands Docked: "$ligands_docked"\n Elapsed Time: "$eta"\n Estimated Completion: "$completion"\n"
            sleep 1
        done | yad --progress --text="Docking progress ..." \
                --image=$CODOC_DIR/icons/rigidP.png \
                --title="CODOC - GPU Rigid Docking" --button="CANCEL CURRENT":1 --button="NEXT TARGET":2 --button="CANCEL ALL":3 --buttons-layout=edge --on-top \
                --center --width=500 --borders=10 --auto-close &
                YAD_PID=$!
                wait $YAD_PID
                exit_status=$?
                if [ $exit_status -eq 1 ]; then
                    # CANCEL CURRENT button pressed
                    kill $VINA_PID
                    kill $YAD_PID
                    continue
                elif [ $exit_status -eq 2 ]; then
                    # NEXT TARGET button pressed
                    kill $VINA_PID
                    kill $YAD_PID
                    break
                elif [ $exit_status -eq 3 ]; then
                    # CANCEL ALL button pressed
                    kill $VINA_PID
                    kill $YAD_PID
                    return
                fi

        yad --info --text="\n Spliting \"$nL\" files…\n Wait for the end ! " --text-align=center \
              --image=$CODOC_DIR/icons/progressP.png \
              --skip-taskbar \
              --center --width=400 --borders=10 --on-top \
              --no-buttons &
        SPLIT_PID=$!
        wait $VINA_PID
        # 3rd FOR Loop create a directory for each .pdbqt ligand present in the subfolder and move _out.pdbqt file:
        for out in "$RR/$nP/$nL/"*.pdbqt; do
            [ -e "$out" ] || continue
            nl=$(basename "$out" .pdbqt | sed "s/_out//")
            mkdir "$RR/$nP/$nL/$nl"
            mv "$out" "$RR/$nP/$nL/$nl/$nl.pdbqt"
            ((account_ligands++))
            ((crossings++))    
        done
        echo "////////////////////////////////////////////////////////////"
        echo "/Running the Vina Split // Ligand: $l                       "
        echo "////////////////////////////////////////////////////////////"
        for s in "$RR/$nP/$nL/"*/; do
            b=$(basename "$s")
            if [ "$split" = "yes" ]; then
                # Decomposes each $nl.pdbqt output result into the pose files:           
                $vina_split --input $s/$b.pdbqt # Running the vina split
            fi
            # Extracts binding energy and RMSD of the out.pdbqt multimodel file:
            energy_md1=$(awk '/MODEL 1/ {getline; if ($0 ~ /REMARK VINA RESULT:/) print; exit}' "$s/$b.pdbqt")
            results_rmsd=$(grep 'REMARK VINA RESULT:' "$s/$b.pdbqt")
            results_smiles=$(grep 'REMARK SMILES' "$s/$b.pdbqt" | head -n 1)                
            e=$(echo "$energy_md1" | awk '{print $4}')
            rmsd=$(echo "$results_rmsd" | awk '{print $5}')
            smi=$(echo "$results_smiles" | awk '{print $3}')
            
            # Calculating the average RMSD of extracted values:
                r=$(echo $rmsd | awk '{ 
                    sum = 0; 
                    for (i = 1; i <= NF; i++) { 
                        sum += $i; 
                    } 
                    print sum / NF  
                }')
                        
            # Saves the ligand name, binding energy and rmsd to the result file:
            echo "$smi	$b	$e	$r" >> "$rp"
        done
        cp "$p" "$RR/$nP/$nL/"
        # Calculation of partial elapsed time and partial performance information for each binder group:
        end_time_P=$(date +%s)
        parcial_time=$((end_time_P - start_time_P))
        days=$((parcial_time / 86400))
        hours=$(( (parcial_time % 86400) / 3600 ))
        minutes=$(( (parcial_time % 3600) / 60 ))
        seconds=$((parcial_time % 60))

        echo "                                                                                        " >> "$dp"
        echo "              $account_ligands LIGANDS WERE PROCESSED                             	  " >> "$dp"
        echo "                                                                                        " >> "$dp"
        echo "                                                                                        " >> "$dp"
        echo "	    Elapsed time: $parcial_time seconds												  " >> "$dp"
        echo "		Elapsed time: $days days : $hours hours : $minutes minutes : $seconds seconds     " >> "$dp"
        echo "                                                                                        " >> "$dp"
        echo "----------------------------------------------------------------------------------------" >> "$dp"
        kill $SPLIT_PID
    done < "$ligands/.L_list.txt" 
done < "$targets/.P_list.txt"

yad --info --center \
    --title="CODOC - CONFIRMATION !" \
    --text="RIGID DOCKING WITH GPU IS OVER! CHECK THE $result_folder FOLDER." \
    --text-align=center \
    --button="OK":0 --buttons-layout=center \
    --width=500 --borders=10 --on-top \
    --image=$CODOC_DIR/icons/okP.png

show_docking_menu
}

#################################################################################################################################
#                                       FUNCTION TO PERFORM FLEXIBLE DOCKING (WITH CPU):                                        #
#################################################################################################################################
run_flexible_docking_cpu() {
missing_files=""

# Check subfolders and files in $ligands
for dir_L in "$ligands"/*/; do
  if [ -z "$(find "$dir_L" -maxdepth 1 -name "*.pdbqt" -print -quit)" ]; then
    missing_files+="$dir_L: arquivos pdbqt ausentes\n"
  fi
done

# Check subfolders and files in $targets
for dir_T in "$targets"/*/; do
  if [ ! -f "$dir_T/grid.txt" ] || [ ! -f "$dir_T/protein_rigid.pdbqt" ] || [ ! -f "$dir_T/protein_flex.pdbqt" ]; then
    missing_files+="$dir_T: grid.txt or protein_rigid.pdbqt or protein_flex.pdbqt missing\n"
  fi
done

# Display a message if files are missing
if [ -n "$missing_files" ]; then
    yad --center --title="CODOC - NOTICE !" \
        --width=500 --borders=10 --on-top \
        --text="\nMISSING FILES: \n$missing_files\n \nPlease! Add the corresponding files to the folder!" \
        --text-align=center \
        --button="OK":0 --buttons-layout=edge \
        --image=$CODOC_DIR/icons/attentionP.png
    if [ $? -eq 0 ]; then
        show_docking_menu
    fi
fi

# Start of the total time counter, total ligands count and targets count:
start_time_total=$(date +%s)
target_account=0
crossings=0

# Path to the hidden file
selected_result="$results_doc/.selected_result.txt"

# Check if the file is empty
if [ ! -s "$selected_result" ]; then
    # The file is empty, execute the commands
    result_folder="${current_date}_FLEXIBLE_DOCKING_RESULT_CPU"
    RF="$results_doc"/"$result_folder"
    mkdir -p "$RR"
    rsync -av --include=*/ --exclude=* $targets/* $RF
else
    # The file contains an address, assign the value to the RR variable
    result_folder=$(cat "$selected_result")
    RR="$results_doc"/"$result_folder"
fi

# 1st FOR Loop enters each protein folder present in the TARGETS folder, assigns the GridBox parameters, and copies the ligand group directories to the RIGID_DOCKING_RESULT_"$current_date" folder:
while IFS= read -r P; do
    nP=$(basename "$P")
    pR="$targets/$nP/protein_rigid.pdbqt"
    pF="$targets/$nP/protein_flex.pdbqt"

    # Check if the file is empty
    if [ ! -s "$selected_result" ]; then
        # The file is empty, execute the commands
        rsync -av --include=*/ --exclude=* "$ligands"/* "$RF"/"$nP"
        rp=$RF/"$nP"/"$result_folder"_"$nP".csv && touch "$rp"
        dp=$RF/"$nP"/"$result_folder"_PERFORMANCE_"$nP".txt && touch "$dp"
    else
        # The file contains an address, assign the value to the RR variable
        rp=$RF/"$nP"/"$result_folder"_"$nP".csv
        dp=$RF/"$nP"/"$result_folder"_PERFORMANCE_"$nP".txt
    fi
    
    # Checks if the grid.txt file exists in the $targets/$nP folder
    if [ -f "$targets/$nP/grid.txt" ]; then
        # If the file exists, it updates the Grid Box parameters:
        grid=/$targets/$nP/grid.txt
        # Extract the line containing "center/size" and get the values:
        center_line=$(grep 'center' "$grid")
        c_x=$(echo "$center_line" | awk '{print $2}')
        c_y=$(echo "$center_line" | awk '{print $3}')
        c_z=$(echo "$center_line" | awk '{print $4}')
        size_line=$(grep 'npts' "$grid")
        s_x=$(echo "$size_line" | awk '{print $2}')
        s_y=$(echo "$size_line" | awk '{print $3}')
        s_z=$(echo "$size_line" | awk '{print $4}')
    else
        yad --info --center --title="CODOC - WARNING !" \
            --text="The grid.txt file was not found in the $targets/$nP folder. Generate the text file named as grid.txt in ADT, save it in the $targets/$nP folder, and restart CODOC." \
            --text-align=center \
            --button="OK":0 --buttons-layout=center \
            --width=500 --borders=10 --on-top \
            --image=$CODOC_DIR/icons/warningP.png

            show_docking_menu
    fi

    #  Generates the headers where PARTIAL PERFORMANCES will be recorded in each of the targets:
    echo "########################################################################################" >> "$dp"
    echo "#                                 CODOC VERSION 2024.1:                                #" >> "$dp"
    echo "#                         			15/07/2025					                     #" >> "$dp"
    echo "########################################################################################" >> "$dp"
    echo "                                                                                        " >> "$dp"
    echo "########################################################################################" >> "$dp"
    echo "#                                 FROM TARGET: $nP                                     #" >> "$dp"
    echo "########################################################################################" >> "$dp"
    echo "                                                                                        " >> "$dp"

    # Generates the headers where the PARTIAL RESULTS will be recorded in each of the targets:
    echo "" >> "$rp"
    echo "TARGET	$nP" >> "$rp"

    ((target_account++)) # Adds 1 more to the target account
    
    # 2nd FOR Loop goes through each subfolder, with the ligand database, within the LIGANTES folder:
    while IFS= read -r L; do
        nL=$(basename "$L")
        total=$(ls -1 $L | wc -l)
        # Start of time counter and ligands account for the ligand databank:
        start_time_P=$(date +%s)
        account_ligands=0

        # Create a configuration file for each protein:
        touch $RF/$nP/$nL/config.txt
        config_file="$RF/$nP/$nL/config.txt"
             
        # Generates the headers where the LIGAND GROUPS will be recorded in the performance file:       
        echo "                                                                                        " >> "$dp"
        echo "----------------------------------------------------------------------------------------" >> "$dp"
        echo "/////////////////////////////FROM LIGAND DATABANK: $nL://///////////////////////////////" >> "$dp"
        echo "----------------------------------------------------------------------------------------" >> "$dp"
        echo "                                                                                        " >> "$dp"

        # Generates the headers where the LIGAND GROUPS will be recorded in the partial results file:
        echo "" >> "$rp"
        echo "LIGAND_DATABANK	$nL" >> "$rp"
        echo "SMILES	LIGAND	BINDING_ENERGY(Kcal/mol)	RMSD(mean)" >> "$rp"

        counter=0
        (
        # 3rd FOR Loop executes docking on each .pdbqt ligand present in the subfolder:
        while IFS= read -r l; do
            nl=$(basename "$l" .pdbqt)
            echo "////////////////////////////////////////////////////////////"
            echo "/Running the docking calculation // Ligand: $nl             "
            echo "////////////////////////////////////////////////////////////"
            mkdir "$RF/$nP/$nL/$nl"

            # Create a config file for each proteins and ligand database:   
            cat <<EOL > "$config_file"
receptor = $pR
flex = $pF
ligand = $l
scoring = $sf
center_x = $c_x
center_y = $c_y
center_z = $c_z
size_x = $s_x
size_y = $s_y
size_z = $s_z
out = $RF/$nP/$nL/$nl/$nl.pdbqt
cpu = $cpu
exhaustiveness = $ext
num_modes = $num_poses
min_rmsd = $min_rmsd
energy_range = $energy_range
spacing = $spacing
EOL
            # YAD Progress Bar Update:
            ((crossings+=1))
            ((account_ligands+=1))
            progress=$(( account_ligands * 100 / total ))
            echo "$progress"
            echo "# Docking Ligand $nl from Base $nL to Target $nP"

            echo "////////////////////////////////////////////////////////////"
            echo "/Running the docking calculation // Ligand: $nl             "
            echo "////////////////////////////////////////////////////////////"
            # Running the docking calculation
            $vina --config $config_file > /dev/null 1>&2 &
            if ((counter % "$cpu_parallel" == 0)); then
                wait
                counter=0
            fi

        done < "$ligands/."$nL"_list.txt"
        ) | yad --progress --text="Docking progress ..." \
                --image=$CODOC_DIR/icons/rigidP.png \
                --auto-close \
                --title="CODOC - CPU Flexible Docking" --button="NEXT BASE":1 --button="NEXT TARGET":2 --button="CANCEL ALL":3 --on-top \
                --center --width=600 --borders=10 &
                YAD_PID=$!
                wait $YAD_PID
                exit_status=$?
                if [ $exit_status -eq 1 ]; then
                    # CANCEL CURRENT button pressed
                    pkill vina_1.2.5_linux_x86_64
                    continue
                elif [ $exit_status -eq 2 ]; then
                    # NEXT TARGET button pressed
                    pkill vina_1.2.5_linux_x86_64
                    break
                elif [ $exit_status -eq 3 ]; then
                    # CANCEL ALL button pressed
                    pkill vina_1.2.5_linux_x86_64
                    return
                fi 
        yad --info --text="\n Spliting \"$nL\" files…\n Wait for the end ! " --text-align=center \
              --image=$CODOC_DIR/icons/progressP.png \
              --skip-taskbar \
              --center --width=400 --borders=10 --on-top \
              --no-buttons &
        SPLIT_PID=$!
        for s in "$RF/$nP/$nL/"*/; do
            b=$(basename "$s")
            echo "////////////////////////////////////////////////////////////"
            echo "/Running the Vina Split // Ligand: $b                       "
            echo "////////////////////////////////////////////////////////////"
            if [ "$split" = "yes" ]; then
                # Decomposes each $nl.pdbqt output result into the pose files:           
                $vina_split --input $s/$b.pdbqt # Running the vina split
            fi

            # Extracts binding energy and RMSD of the out.pdbqt multimodel file:
            energy_md1=$(awk '/MODEL 1/ {getline; if ($0 ~ /REMARK VINA RESULT:/) print; exit}' "$s/$b.pdbqt")
            results_rmsd=$(grep 'REMARK VINA RESULT:' "$s/$b.pdbqt")
            results_smiles=$(grep 'REMARK SMILES' "$s/$b.pdbqt" | head -n 1)                
            e=$(echo "$energy_md1" | awk '{print $4}')
            rmsd=$(echo "$results_rmsd" | awk '{print $5}')
            smi=$(echo "$results_smiles" | awk '{print $3}')
            
            # Calculating the average RMSD of extracted values:
                r=$(echo $rmsd | awk '{ 
                    sum = 0; 
                    for (i = 1; i <= NF; i++) { 
                        sum += $i; 
                    } 
                    print sum / NF  
                }')
                        
            # Saves the ligand name, binding energy and rmsd to the result file:
            echo "$smi	$b	$e	$r" >> "$rp"
        done
        cp "$pR" "$RF/$nP/$nL/"
        cp "$pF" "$RF/$nP/$nL/"
        kill $SPLIT_PID
        # Calculation of partial elapsed time and partial performance information for each binder group:
        end_time_P=$(date +%s)
        parcial_time=$((end_time_P - start_time_P))
        days=$((parcial_time / 86400))
        hours=$(( (parcial_time % 86400) / 3600 ))
        minutes=$(( (parcial_time % 3600) / 60 ))
        seconds=$((parcial_time % 60))

        echo "                                                                                          " >> "$dp"
        echo "                      $account_ligands LIGANDS WERE PROCESSED                             " >> "$dp"
        echo "                                                                                          " >> "$dp"
        echo "                                                                                          " >> "$dp"
        echo "                        Elapsed time: $parcial_time seconds                               " >> "$dp"
        echo "      Elapsed time: $days days : $hours hours : $minutes minutes : $seconds seconds       " >> "$dp"
        echo "                                                                                          " >> "$dp"
        echo "------------------------------------------------------------------------------------------" >> "$dp"
    done < "$ligands/.L_list.txt" 
done < "$targets/.P_list.txt"

yad --info --center \
    --title="CODOC - CONFIRMATION !" \
    --text="FLEXIBLE DOCKING IS OVER! CHECK THE $result_folder FOLDER." \
    --text-align=center \
    --button="OK":0 --buttons-layout=center \
    --width=500 --borders=10 --on-top \
    --image=$CODOC_DIR/icons/okP.png

show_docking_menu
}

#################################################################################################################################
#                                       FUNCTION TO PERFORM FLEXIBLE DOCKING (WITH GPU):                                        #
#################################################################################################################################
run_flexible_docking_gpu() {

missing_files=""

# Check subfolders and files in $ligands
for dir_L in "$ligands"/*/; do
  if [ -z "$(find "$dir_L" -maxdepth 1 -name "*.pdbqt" -print -quit)" ]; then
    missing_files+="$dir_L: arquivos pdbqt ausentes\n"
  fi
done

# Check subfolders and files in $targets
for dir_T in "$targets"/*/; do
  if [ ! -f "$dir_T/grid.txt" ] || [ ! -f "$dir_T/protein_rigid.pdbqt" ] || [ ! -f "$dir_T/protein_flex.pdbqt" ]; then
    missing_files+="$dir_T: grid.txt or protein_rigid.pdbqt or protein_flex.pdbqt missing\n"
  fi
done

# Display a message if files are missing
if [ -n "$missing_files" ]; then
    yad --center --title="CODOC - NOTICE !" \
        --width=500 --borders=10 --on-top \
        --text="\nMISSING FILES: \n$missing_files\n \nPlease! Add the corresponding files to the folder!" \
        --text-align=center \
        --button="OK":0 --buttons-layout=edge \
        --image=$CODOC_DIR/icons/attentionP.png
    if [ $? -eq 0 ]; then
        show_docking_menu
    fi
fi

# Start of the total time counter, total ligands count and targets count:
start_time_total=$(date +%s)
target_account=0
crossings=0

# Path to the hidden file
selected_result="$results_doc/.selected_result.txt"

# Check if the file is empty
if [ ! -s "$selected_result" ]; then
    # The file is empty, execute the commands
    result_folder="${current_date}_FLEXIBLE_DOCKING_RESULT_GPU"
    RF="$results_doc"/"$result_folder"
    mkdir -p "$RF"
    rsync -av --include=*/ --exclude=* $targets/* $RF
else
    # The file contains an address, assign the value to the RR variable
    result_folder=$(cat "$selected_result")
    RR="$results_doc"/"$result_folder"
fi

# 1st FOR Loop enters each protein folder present in the TARGETS folder, assigns the GridBox parameters, and copies the ligand group directories to the RIGID_DOCKING_RESULT_"$current_date" folder:
while IFS= read -r P; do
    nP=$(basename "$P")
    pR="$targets/$nP/protein_rigid.pdbqt"
    pF="$targets/$nP/protein_flex.pdbqt"

    # Check if the file is empty
    if [ ! -s "$selected_result" ]; then
        # The file is empty, execute the commands
        rsync -av --include=*/ --exclude=* "$ligands"/* "$RF"/"$nP"
        rp=$RF/"$result_folder"_"$nP".csv && touch "$rp"
        dp=$RF/"$result_folder"_PERFORMANCE_"$nP".txt && touch "$dp"
    else
        # The file contains an address, assign the value to the RR variable
        rp=$RF/"$nP"/"$result_folder"_"$nP".csv
        dp=$RF/"$nP"/"$result_folder"_PERFORMANCE_"$nP".txt
    fi

    # Checks if the grid.txt file exists in the $targets/$nP folder
    if [ -f "$targets/$nP/grid.txt" ]; then
        # If the file exists, it updates the Grid Box parameters:
        grid=/$targets/$nP/grid.txt
        # Extract the line containing "center/size" and get the values:
        center_line=$(grep 'center' "$grid")
        c_x=$(echo "$center_line" | awk '{print $2}')
        c_y=$(echo "$center_line" | awk '{print $3}')
        c_z=$(echo "$center_line" | awk '{print $4}')
        size_line=$(grep 'npts' "$grid")
        s_x=$(echo "$size_line" | awk '{print $2}')
        s_y=$(echo "$size_line" | awk '{print $3}')
        s_z=$(echo "$size_line" | awk '{print $4}')
    else
        yad --info --center --title="CODOC - WARNING !" \
            --text="The grid.txt file was not found in the $targets/$nP folder. Generate the text file named as grid.txt in ADT, save it in the $targets/$nP folder, and restart CODOC." \
            --text-align=center \
            --button="OK":0 --buttons-layout=center \
            --width=500 --borders=10 --on-top \
            --image=$CODOC_DIR/icons/warningP.png

            show_docking_menu
    fi

    #  Generates the headers where PARTIAL PERFORMANCES will be recorded in each of the targets:
    echo "########################################################################################" >> "$dp"
    echo "#                                 CODOC VERSION 2024.1:                                #" >> "$dp"
    echo "#                         			15/07/2025					                     #" >> "$dp"
    echo "########################################################################################" >> "$dp"
    echo "                                                                                        " >> "$dp"
    echo "########################################################################################" >> "$dp"
    echo "#                                 FROM TARGET: $nP                                     #" >> "$dp"
    echo "########################################################################################" >> "$dp"
    echo "                                                                                        " >> "$dp"

    # Generates the headers where the PARTIAL RESULTS will be recorded in each of the targets:
    echo "" >> "$rp"
    echo "TARGET	$nP" >> "$rp"

    ((target_account++)) # Adds 1 more to the target count

    # 2nd FOR Loop goes through each subfolder, with the ligand database, within the LIGANTES folder:
    while IFS= read -r L; do
        nL=$(basename "$L")

        total=$(find "$L" -maxdepth 1 -type f -name "*.pdbqt" | wc -l)

        # Start of the split time counter for the ligand group:
        parcial_time=0
        start_time_P=$(date +%s)
        account_ligands=0

        # Create a configuration file for each protein:
        touch $RF/$nP/$nL/config.txt
        config_file="$RF/$nP/$nL/config.txt"
        
        # Generates the headers where the LIGAND GROUPS will be recorded in the performance file:       
        echo "                                                                                        " >> "$dp"
        echo "----------------------------------------------------------------------------------------" >> "$dp"
        echo "                              FROM LIGAND DATABANK: $nL:                                " >> "$dp"
        echo "----------------------------------------------------------------------------------------" >> "$dp"
        echo "                                                                                        " >> "$dp"

        # Generates the headers where the LIGAND GROUPS will be recorded in the partial results file:
        echo "" >> "$rp"
        echo "LIGAND_DATABANK	$nL" >> "$rp"
        echo "SMILES	LIGAND	BINDING_ENERGY(Kcal/mol)	RMSD(mean)" >> "$rp"

        # Create a config file for each proteins and ligand database:   
        cat <<EOL > "$config_file"
receptor = $pR
flex = $pF
ligand_directory = $L
output_directory = $RF/$nP/$nL/
opencl_binary_path = $VINAGPU_DIR
center_x = $c_x
center_y = $c_y
center_z = $c_z
size_x = $s_x
size_y = $s_y
size_z = $s_z
thread = $threads
EOL

        echo "////////////////////////////////////////////////////////////"
        echo "/Running the docking calculation in ligands database: "$L"  "
        echo "////////////////////////////////////////////////////////////"
        # Running the docking calculation
        $vina_GPU --config "$config_file" &
        VINA_PID=$!
        echo -n > $track_progress
        while kill -0 $VINA_PID > /dev/null 1>&2; do
            source $track_progress
            ligands_docked=$(awk 'NR==1 {print $1}' "$track_progress")
            ligands_total=$(awk 'NR==2 {print $1}' "$track_progress")
            progress=$(awk 'NR==3 {print $1}' "$track_progress" | sed 's/%//')
            eta=$(awk 'NR==4 {print $1}' "$track_progress")
            completion=$(awk 'NR==6 {print $1, $2}' "$track_progress")
            echo $progress
            echo "#\n Target: $nP\n Ligand Base: $nL\n Total Ligands: $ligands_total\n Ligands Docked: "$ligands_docked"\n Elapsed Time: "$eta"\n Estimated Completion: "$completion"\n"
            sleep 1
        done | yad --progress --text="Docking progress ..." \
                --image=$CODOC_DIR/icons/rigidP.png \
                --title="CODOC - GPU Rigid Docking" --button="CANCEL CURRENT":1 --button="NEXT TARGET":2 --button="CANCEL ALL":3 --buttons-layout=edge --on-top \
                --center --width=500 --borders=10 --auto-close &
                YAD_PID=$!
                wait $YAD_PID
                exit_status=$?
                if [ $exit_status -eq 1 ]; then
                    # CANCEL CURRENT button pressed
                    kill $VINA_PID
                    kill $YAD_PID
                    continue
                elif [ $exit_status -eq 2 ]; then
                    # NEXT TARGET button pressed
                    kill $VINA_PID
                    kill $YAD_PID
                    break
                elif [ $exit_status -eq 3 ]; then
                    # CANCEL ALL button pressed
                    kill $VINA_PID
                    kill $YAD_PID
                    return
                fi

        wait $VINA_PID
        # 3rd FOR Loop create a directory for each .pdbqt ligand present in the subfolder and move _out.pdbqt file:
        for out in "$RF/$nP/$nL"/*.pdbqt; do
            nl=$(basename "$out" .pdbqt | sed "s/_out//")
            mkdir "$RF/$nP/$nL/$nl"
            mv "$out" "$RF/$nP/$nL/$nl/$nl.pdbqt"
            ((account_ligands++))
            ((crossings++))            
        done
        echo "////////////////////////////////////////////////////////////"
        echo "/Running the Vina Split // Ligand: $l                       "
        echo "////////////////////////////////////////////////////////////"
        for s in "$RF/$nP/$nL/"*/; do
            b=$(basename "$s")
            if [ "$split" = "yes" ]; then
                # Decomposes each $nl.pdbqt output result into the pose files:           
                $vina_split --input $s/$b.pdbqt # Running the vina split
            fi

            # Extracts binding energy and RMSD of the out.pdbqt multimodel file:
            energy_md1=$(awk '/MODEL 1/ {getline; if ($0 ~ /REMARK VINA RESULT:/) print; exit}' "$s/$b.pdbqt")
            results_rmsd=$(grep 'REMARK VINA RESULT:' "$s/$b.pdbqt")
            results_smiles=$(grep 'REMARK SMILES' "$s/$b.pdbqt" | head -n 1)                
            e=$(echo "$energy_md1" | awk '{print $4}')
            rmsd=$(echo "$results_rmsd" | awk '{print $5}')
            smi=$(echo "$results_smiles" | awk '{print $3}')
            
            # Calculating the average RMSD of extracted values:
                r=$(echo $rmsd | awk '{ 
                    sum = 0; 
                    for (i = 1; i <= NF; i++) { 
                        sum += $i; 
                    } 
                    print sum / NF  
                }')
                        
            # Saves the ligand name, binding energy and rmsd to the result file:
            echo "$smi	$b	$e	$r" >> "$rp"
        done
        cp "$pR" "$RF/$nP/$nL/"
        cp "$pF" "$RF/$nP/$nL/"
        # Calculation of partial elapsed time and partial performance information for each binder group:
        end_time_P=$(date +%s)
        parcial_time=$((end_time_P - start_time_P))
        days=$((parcial_time / 86400))
        hours=$(( (parcial_time % 86400) / 3600 ))
        minutes=$(( (parcial_time % 3600) / 60 ))
        seconds=$((parcial_time % 60))

        echo "                                                                                          " >> "$dp"
        echo "                      $account_ligands LIGANDS WERE PROCESSED                             " >> "$dp"
        echo "                                                                                          " >> "$dp"
        echo "                                                                                          " >> "$dp"
        echo "                        Elapsed time: $parcial_time seconds                               " >> "$dp"
        echo "      Elapsed time: $days days : $hours hours : $minutes minutes : $seconds seconds       " >> "$dp"
        echo "                                                                                          " >> "$dp"
        echo "------------------------------------------------------------------------------------------" >> "$dp"
    done < "$ligands/.L_list.txt" 
done < "$targets/.P_list.txt"

yad --info --center \
    --title="CODOC - CONFIRMATION !" \
    --text="FLEXIBLE DOCKING WITH GPU IS OVER! CHECK THE $result_folder FOLDER." \
    --text-align=center \
    --button="OK":0 --buttons-layout=center \
    --width=500 --borders=10 --on-top \
    --image=$CODOC_DIR/icons/okP.png

show_docking_menu
}

#################################################################################################################################
#                                       FUNCTION FOR REMOVING PARAMETER FILES:                                                  #
#################################################################################################################################

#Global access function for removing parameters:
remove_parameters() {
find "$CODOC_DIR" -type f -name ".*" -exec rm -f {} +
}

#################################################################################################################################
#                                                       START MAIN MENU:                                                        #
#################################################################################################################################
# On first access, if the menu shortcut is missing, it directs you to the prerequisite installation:
if [ ! -f "$MENU_FILE" ]; then
    run_CODOC_prerequisites
else
    echo "MENU ENTRY CHECK !"
fi
echo "COMPLETE INITIALIZATION!"
show_main_menu &
MENU_PID=$!

#---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# PLEASE CITE:
#---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# OUR PAPER:
#
#---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# FOR VINA 1.2.5:
# J. Eberhardt, D. Santos-Martins, A. F. Tillack, and S. Forli. (2021). AutoDock Vina 1.2.0: New Docking Methods, Expanded Force Field, and Python Bindings. Journal of Chemical Information and Modeling.
# O. Trott and A. J. Olson. (2010). AutoDock Vina: improving the speed and accuracy of docking with a new scoring function, efficient optimization, and multithreading. Journal of computational chemistry, 31(2), 455-461.
#---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# FOR OPENBABEL 3.0.0:
# N M O'Boyle, M Banck, C A James, C Morley, T Vandermeersch, and G R Hutchison. "Open Babel: An open chemical toolbox." J. Cheminf. (2011), 3, 33. DOI:10.1186/1758-2946-3-33
#---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
