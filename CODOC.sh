#!/bin/bash
#################################################################################################################################
#                                               CODOC VERSION 1.1.1:                                                            #
#                                      Developed by Moisés Maia Neto - 06/2024                                                  #
#################################################################################################################################
# Identifying the directory where the CODOC is located and checking the TARGETS and LIGANDS directories.
CURRENT_DIR=$(dirname "${BASH_SOURCE[0]}")
cd $CURRENT_DIR
CODOC_DIR=$(pwd)
if [ -d "LIGANDS" ]; then
    echo "LIGANDS FOLDER IS PRESENT!"
    else
        dialog --title "ATTENTION" --msgbox "THE DIRECTORY CONTAINING THE TARGETS IS MISSING. CREATE A DIRECTORY CALLED "TARGETS"!" 10 60 ;
    fi
if [ -d "TARGETS" ]; then
    echo "TARGETS FOLDER IS PRESENT!"
    else
        dialog --title "ATTENTION" --msgbox "THE DIRECTORY CONTAINING THE LIGANDS IS MISSING. CREATE A DIRECTORY CALLED "LIGANDS"!" 10 60 ;
fi

# Predefined global access address variables:
current_date=$(date +"%d_%m_%Y")
ligands="$CODOC_DIR/LIGANDS"
targets="$CODOC_DIR/TARGETS"
data="$CODOC_DIR/.form_data.txt"
vina="$CODOC_DIR/vina_1.2.5_linux_x86_64"
vina_split="$CODOC_DIR/vina_split_1.2.5_linux_x86_64"
vina_GPU_dir="$HOME/Vina-GPU-2.1/AutoDock-Vina-GPU-2.1/"
vina_GPU="$HOME/Vina-GPU-2.1/AutoDock-Vina-GPU-2.1/AutoDock-Vina-GPU-2-1"
opencl="/usr/local/cuda/lib64"

# Predefined global access parameter variables:
sf="vina" # Type of scoring function used
cpu="16" # Number of Threads used on the CPU
ext="32" # Exhaustiveness
threads="8192" # Number of Threads used on the GPU
num_modes="9" # Number of output poses to generate
min_rmsd="1" # Minimum RMSD between poses
energy_range="3" # Maximum energy interval between poses
spacing="0.375" # grid spacing (Angstrom)
pH="7.4" # pH of the medium that will determine the protonation state of the ligands
runs="10" # Parallel runs number

#################################################################################################################################
#                                       FUNCTION TO DISPLAY THE MAIN MENU:                                                      #
#################################################################################################################################
title="|||| C O D O C ||||  A AUTOMATIZED MULTI-TARGET DOCKING TOOL"

show_main_menu() {
    dialog --clear --backtitle "$title" \
    --title "MAIN MENU" \
    --menu "Select an option:" 15 60 7 \
    1 "Docking Settings" \
    2 "Run Ligands Prepare" \
    3 "Run Rigid Docking (with CPU)" \
    4 "Run Rigid Docking (with GPU)" \
    5 "Run Flexible Docking (with CPU)" \
    6 "Run Flexible Docking (with GPU)" \
    7 "Exit" \
    2> .menu_escolha.txt

    if [ $? -eq 0 ]; then
        opcao=$(cat .menu_escolha.txt)
        case $opcao in
            1) show_form ;;
            2) run_ligands_prepare ;;
            3) run_rigid_docking_cpu ;;
            4) run_rigid_docking_gpu ;;
            5) run_flexible_docking_cpu ;;
            6) run_flexible_docking_gpu ;;
            7) remove_parameters; clear; exit 0 ;;
            *) remove_parameters; clear; exit 0 ;;
        esac
    else
        remove_parameters
        clear
        exit 0
    fi
}

#################################################################################################################################
#                               FUNCTION TO CONFIGURE DOCKING PARAMETERS AND VARIABLES:                                         #
#################################################################################################################################
show_form() {
     form_data
     form_data=$(dialog --backtitle "$title" \
     --title "CONFIGURATION PARAMETERS" \
     --form "Change the fields below if necessary:" 26 65 0 \
     "Scoring function:" 1 4 "$sf" 1 35 20 0 \
     "vina / ad4 / vinardo" 2 4 "" 0 0 0 0 \
     "CPU Threads" 4 4 "$cpu" 4 35 20 0 \
     "Exhaustiveness" 6 4 "$ext" 6 35 20 0 \
     "GPU Threads" 8 4 "$threads" 8 35 20 0 \
     "Poses" 10 4 "$num_modes" 10 35 20 0 \
     "minimum RMSD" 12 4 "$min_rmsd" 12 35 20 0 \
     "Energy Range (Kcal/mol)" 14 4 "$energy_range" 14 35 20 0 \
     "Grid Spacing" 16 4 "$spacing" 16 35 20 0 \
     "pH" 18 4 "$pH" 18 35 20 0 \
     "Parallel runs" 20 4 "$runs" 20 35 20 0 \
      3>&1 1>&2 2>&3)

     # Check if the user canceled the form:
     if [ $? -eq 0 ]; then
         # Assign the entered data to variables:
         echo "$form_data" > .form_data.txt
         source .form_data.txt
         export $sf
         export $cpu
         export $ext
         export $threads
         export $num_modes
         export $min_rmsd
         export $energy_range
         export $spacing
         export $pH
         show_main_menu
     else
         show_main_menu
     fi
}

#################################################################################################################################
#                                       FUNCTION TO PREPARE LINKS FOR DOCKING:                                                  #
#################################################################################################################################
run_ligands_prepare() {
# INITIAL USER GUIDELINES:
dialog --title "ATTENTION" --msgbox "MULTI-MODEL FILES MUST BE PLACED IN THE "LIGANDS" FOLDER AND SINGLE LIGAND FILES MUST BE PLACED IN "SUB FOLDERS" WITHIN LIGANDS FOLDER. NAME THESE SUB FOLDERS WITH ACRONYMS THAT IDENTIFY THE LIGAND DATABASE!" 10 60 ;
dialog --title "ATTENTION" --msgbox "ONLY SOME FILE FORMATS ARE ACCEPTED: .mol2/.sdf/.smi/.pdb" 10 60 ;

# Updating variables:
data="$CODOC_DIR/.form_data.txt"
pH="$(sed -n '9p' $data)"
cpu="$(sed -n '2p' $data)"

# CHECK IF THERE ARE MULTI-MODEL FILES IN THE "LIGANDS" FOLDER:
quantity_files=$(find "$ligands" -mindepth 1 -maxdepth 1 -type f ! -path "$ligands" | wc -l)
if [ "$quantity_files" -eq 0 ]; then
    dialog --title "ATTENTION" --msgbox "THERE ARE NO MULTI-MODEL LIGANDS FILES IN THE "LIGANDS" FOLDER" 10 60 ;
    
elif [ "$quantity_files" -gt 0 ]; then
    for multi in "$ligands"/*; do
        if [ -f "$multi" ]; then        
            if [[ "$multi" == *.sdf ]]; then
                LIG=$(basename $multi .sdf)
                mkdir "$ligands"/$LIG
                # Using grep and sed to delete lines that start with "M  CHG" because it generates an error in the conversion
                if grep -q "M  CHG" "$multi"; then
                    multi_temp="$ligands/multi_temp.sdf"
                    sed '/^M  CHG/d' "$multi" > "$multi_temp"
                    mv "$multi_temp" "$multi"
                    dialog --title "ATTENTION" --msgbox "FIXED MULTI-MODEL FILE WITH \"M  CHG\"" 10 60
                fi

                
                obabel "$multi" -O "$ligands/$LIG/$LIG.sdf" --split -h               
                 
                for file in "$ligands/$LIG"/*; do
                    f=$(basename $file .sdf)
                    # Verifica se o arquivo existe
                    if [ -f "$file" ]; then
                        # Extrai zinc_id do arquivo usando awk
                        zinc=$(awk '/>  <zinc_id>/ {getline; print}' "$file")
                        compound=$(awk '/>  <COMPOUND_ID>/ {getline; print}' "$file")
                        coconut=$(awk '/>  <coconut_id>/ {getline; print}' "$file")

                        # Renomeia o arquivo com o identificador apropriado
                        if [ -n "$zinc" ]; then
                            # Verifica se o arquivo com o novo nome já existe para evitar conflito
                            if [ ! -f "$ligands/$LIG/$zinc.sdf" ]; then
                                mv "$file" "$ligands/$LIG/$zinc.sdf"
                                continue
                            fi
                        fi
                        if [ -n "$compound" ]; then
                            # Verifica se o arquivo com o novo nome já existe para evitar conflito
                            if [ ! -f "$ligands/$LIG/$compound.sdf" ]; then
                                mv "$file" "$ligands/$LIG/$compound.sdf"
                                continue
                            fi
                        fi
                        if [ -n "$coconut" ]; then
                            # Verifica se o arquivo com o novo nome já existe para evitar conflito
                            if [ ! -f "$ligands/$LIG/$coconut.sdf" ]; then
                                mv "$file" "$ligands/$LIG/$coconut.sdf"
                                continue
                            fi
                        fi
                    fi
                done

                rm "$multi"
                # Due to a conversion error, the first line must be deleted so that it is no longer recognized as a multi-model file
#                    for file in "$ligands"/$LIG/*; do
#                        # Checks if the file exists
#                        if [[ -f "$file" ]]; then
#                            # Use sed to remove the first line and the last line
#                            sed '1d' "$file" > "${file}.tmp"
#                            # Replaces the original file with the temporary file
#                            mv "${file}.tmp" "$file"
#                        fi
#                    done
#                
            elif [[ "$multi" == *.mol2 ]]; then
                LIG=$(basename $multi .mol2)
                mkdir "$ligands"/$LIG
                obabel "$ligands"/*.mol2 -O "$ligands"/"$LIG"/.mol2 --split -h
                rm "$multi"
                # Due to a conversion error, the first and the last lines must be deleted so that it is no longer recognized as a multi-model file
#                for file in "$ligands"/$LIG/*; do
#                    # Checks if the file exists
#                    if [[ -f "$file" ]]; then
#                        # Counts the total number of lines in the file
#                        ENDMDL=$(wc -l < "$file")
#                        # Use sed to remove the first and last lines
#                        sed '1d;'"${ENDMDL}"'d' "$file" > "${file}.tmp"
#                        # Replaces the original file with the temporary file
#                        mv "${file}.tmp" "$file"
#                    fi
#                done

            elif [[ "$multi" == *.smi ]]; then
                LIG=$(basename $multi .smi)
                mkdir "$ligands"/$LIG
                obabel "$ligands"/*.smi -O "$ligands"/"$LIG"/.smi --split -h
                rm "$multi"
                # Due to a conversion error, the first and the last lines must be deleted so that it is no longer recognized as a multi-model file
            #            for file in "$ligands"/$LIG/*; do
            #                # Checks if the file exists
            #                if [[ -f "$file" ]]; then
            #                    # Counts the total number of lines in the file
            #                    ENDMDL=$(wc -l < "$file")
            #                    # Use sed to remove the first and last lines
            #                    sed '1d;'"${ENDMDL}"'d' "$file" > "${file}.tmp"
            #                    # Replaces the original file with the temporary file
            #                    mv "${file}.tmp" "$file"
            #                fi
            #            done

            elif [[ "$multi" == *.pdbqt ]]; then
                # There are no multi-model .pdbqt files so there is no need to split 
                LIG=$(basename $multi .smi)           
                mkdir "$ligands"/"$LIG"
                cp $multi "$ligands"/"$LIG"
                obabel "$ligands"/"$LIG"/*.pdbqt -O "$ligands"/"$LIG"/.pdbqt --split -h
                rm $multi

            else
                dialog --title "ATTENTION" --yesno "FILE FORMAT NOT RECOGNIZED. DO YOU WANT TO DELETE THE FILE "$multi"?" 10 60 ;
                    if [ $? -eq 0 ]; then
                        rm $multi
                    else
                        mkdir "$HOME/MGLTools-1.5.7/doc/NOT_RECOGNIZED_LIGANDS/"
                        mv $multi "$HOME/MGLTools-1.5.7/doc/NOT_RECOGNIZED_LIGANDS/"
                    fi                      
            fi
        fi
    done
fi

# CHECK IF THERE ARE SUBFOLDERS IN THE LIGANDS FOLDER:
quantity_subfolders=$(find "$ligands" -mindepth 1 -maxdepth 1 -type d ! -path "$ligands" | wc -l)

if [ "$quantity_subfolders" -eq 0 ]; then
    dialog --title "ATTENTION" --msgbox "THE LIGANDS FOLDER DOES NOT HAVE ANY SUB FOLDER!" 10 60
elif [ "$quantity_subfolders" -gt 0 ]; then
    for L in "$ligands/"*/; do
        quantity_files=$(find "$L" -maxdepth 1 -type f | wc -l)
        
        if [ "$quantity_files" -eq 0 ]; then
            dialog --title "ATTENTION" --msgbox "THERE ARE NO FILES IN THE $L SUBFOLDER. WAIT FOR THE FOLDER TO BE DELETED!" 10 60
            rm -r "$L" || continue
        elif [ "$quantity_files" -gt 0 ]; then
            export L pH cpu

            find "$L" -type f \( -name '*.sdf' -o -name '*.mol2' -o -name '*.smi' -o -name '*.pdb' \) | \
            parallel -j "$cpu" '
                file={};
                ext="${file##*.}";
                base=$(basename "$file" ".$ext");
                case "$ext" in
                    sdf)
                        obabel "$file" -O "$L/$base.pdbqt" --pH "$pH" --gen3d --partialcharge gasteiger --minimize --sd --ff GAFF --n 2000
                        rm "$file"
                        ;;
                    mol2)
                        obabel "$file" -O "$L/$base.pdbqt" --pH "$pH" --partialcharge gasteiger --minimize --sd --ff GAFF --n 2000
                        rm "$file"
                        ;;
                    smi)
                        obabel "$file" -O "$L/$base.pdbqt" --pH "$pH" --gen3d --partialcharge gasteiger --minimize --sd --ff GAFF --n 2000
                        rm "$file"
                        ;;
                    pdb)
                        obabel "$file" -O "$L/$base.pdbqt" --pH "$pH" --partialcharge gasteiger --minimize --sd --ff GAFF --n 2000
                        rm "$file"
                        ;;
                    pdbqt)
                        echo "Formato do arquivo em $L já é .pdbqt"
                        ;;
                    *)
                        dialog --title "ATTENTION" --yesno "FILE FORMAT NOT RECOGNIZED. DO YOU WANT TO DELETE THE FOLDER $L?" 10 60
                        if [ $? -eq 0 ]; then
                            rm -r "$L"
                        else
                            mkdir -p "$HOME/MGLTools-1.5.7/doc/NOT_RECOGNIZED_LIGANDS/"
                            mv "$L" "$HOME/MGLTools-1.5.7/doc/NOT_RECOGNIZED_LIGANDS/"
                        fi
                        ;;
                esac
            '
        fi
    done
fi

dialog --title "ATTENTION" --msgbox "THE PREPARATION OF THE LIGANDS IS FINISHED! CHECK THE LIGANDS FOLDER" 10 60 ;
show_main_menu
}

#################################################################################################################################
#                                       FUNCTION TO PERFORM RIGID DOCKING (WITH CPU):                                           #
#################################################################################################################################
run_rigid_docking_cpu() {
dialog --title "ATTENTION" --msgbox "CHECK THE FILES IN THE TARGETS FOLDER: protein.pdbqt and grid.txt." 10 60  ;

# Updating docking parameters according to user choices:
data="$CODOC_DIR/.form_data.txt"
sf="$(sed -n '1p' $data)"
cpu="$(sed -n '2p' $data)"
ext="$(sed -n '3p' $data)"
num_modes="$(sed -n '5p' $data)"
min_rmsd="$(sed -n '6p' $data)"
energy_range="$(sed -n '7p' $data)"
spacing="$(sed -n '8p' $data)"
runs="$(sed -n '10p' $data)"

# Creates the folder where all docking results and performance will be saved:
mkdir "$CODOC_DIR"/RIGID_DOCKING_RESULT_CPU_"$current_date"
RR="$CODOC_DIR/RIGID_DOCKING_RESULT_CPU_$current_date"

# Generates subfolders in the RIGID_DOCKING_RESULT_"$current_date" folder corresponding to the targets:
rsync -av --include=*/ --exclude=* $targets/* $RR

# Start of the total time counter, total ligands count and targets count:
start_time_total=$(date +%s)
target_account=0
crossings=0

# Creates files where all docking results and total performance will be saved:
rt=$RR/TOTAL_RESULT_RIGID_DOCKING_CPU_"$current_date".csv && touch "$rt"
dt=$RR/TOTAL_PERFORMANCE_RIGID_DOCKING_CPU_"$current_date".txt && touch "$dt"

# 1st FOR Loop enters each protein folder present in the TARGETS folder, assigns the GridBox parameters, and copies the ligand group directories to the RIGID_DOCKING_RESULT_"$current_date" folder:
for P in "$targets/"*/; do
    nP=$(basename "$P")
    p="$targets/$nP/protein.pdbqt"

    # Create subfolders for each group of ligands in the targets folder present in RESULTS:
    rsync -av --include=*/ --exclude=* "$ligands"/* "$RR"/"$nP"

    # Creates files where all partial docking results and performance for each target will be stargets:
    rp=$RR/"$nP"/RIGID_DOCKING_RESULT_CPU_"$nP"_"$current_date".csv && touch "$rp"
    dp=$RR/"$nP"/RIGID_DOCKING_PERFORMANCE_CPU_"$nP"_"$current_date".txt && touch "$dp"
    
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
        dialog --title "ATTENTION" --msgbox " The grid.txt file was not found in the $targets/$nP folder. Generate the text file named as grid.txt in ADT and save it in the $targets/$nP folder." 10 60  ;
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
            dialog --title "ATTENTION" --msgbox " The grid.txt file is STILL MISSING in the $targets/$nP folder. Correct and Restart the process" 10 60;
            break
        fi
    fi

    #  Generates the headers where PARTIAL PERFORMANCES will be recorded in each of the targets:
    echo "########################################################################################" >> "$dp"
    echo "#                                 CODOC VERSION 1.1.1:                                 #" >> "$dp"
    echo "#                         Developed by Moisés Maia Neto - 06/2024                      #" >> "$dp"
    echo "########################################################################################" >> "$dp"
    echo "                                                                                        " >> "$dp"
    echo "########################################################################################" >> "$dp"
    echo "#                                 FROM TARGET: $nP                                     #" >> "$dp"
    echo "########################################################################################" >> "$dp"
    echo "                                                                                        " >> "$dp"

    # Generates the headers where the PARTIAL RESULTS will be recorded in each of the targets:
    echo "" >> "$rp"
    echo "TARGET","$nP" >> "$rp"


    # Generates the headers where the TOTAL RESULTS for each of the targets will be recorded:
    echo "" >> "$rt"
    echo "TARGET","$nP" >> "$rt"
    echo "LIGAND,BINDING ENERGY(Kcal/mol), RMSD(mean)" >> "$rt"

    ((target_account++)) # Adds 1 more to the target account

    # 2nd FOR Loop goes through each subfolder, with the ligand database, within the LIGANTES folder:
    for L in "$ligands/"*/; do
        nL=$(basename "$L")

        # Start of time counter and ligands account for the ligand databank:
        start_time_P=$(date +%s)
        account_ligands=0
             
        # Generates the headers where the LIGAND GROUPS will be recorded in the performance file:       
        echo "                                                                                        " >> "$dp"
        echo "----------------------------------------------------------------------------------------" >> "$dp"
        echo "/////////////////////////////FROM LIGAND DATABANK: $nL://///////////////////////////////" >> "$dp"
        echo "----------------------------------------------------------------------------------------" >> "$dp"
        echo "                                                                                        " >> "$dp"

        # Generates the headers where the LIGAND GROUPS will be recorded in the partial results file:
        echo "" >> "$rp"
        echo "LIGAND DATABANK","$nL" >> "$rp"
        echo "LIGAND,BINDING ENERGY(Kcal/mol), RMSD(mean)" >> "$rp"

        # 3rd FOR Loop executes docking on each .pdbqt ligand present in the subfolder:
        for l in "$L"*.pdbqt; do
            nl=$(basename "$l" .pdbqt)
            echo "////////////////////////////////////////////////////////////"
            echo "/Running the docking calculation // Ligand: $nl             "
            echo "////////////////////////////////////////////////////////////"
            mkdir "$RR/$nP/$nL/$nl"
            
            # Running the docking calculation
            $vina --center_x $c_x --center_y $c_y --center_z $c_z --size_x $s_x --size_y $s_y --size_z $s_z --scoring "$sf" --cpu $cpu --exhaustiveness $ext --num_modes $num_modes --min_rmsd $min_rmsd --energy_range $energy_range --spacing $spacing --ligand "$l" --receptor $p --out "$RR/$nP/$nL/$nl/$nl.pdbqt" &

            ((account_ligands++))
            ((crossings++))  
            if ((account_ligands % $runs == 0)); then  # Check if "$runs" ligands have been processed
                wait  # Wait for all background processes to finish          
            fi
        done
        wait
        for s in "$RR/$nP/$nL/"*/; do
            b=$(basename "$s")
            echo "////////////////////////////////////////////////////////////"
            echo "/Running the Vina Split // Ligand: $b                       "
            echo "////////////////////////////////////////////////////////////"
#            if [ -f "$RR/$nP/$nL/$b/$b.pdbqt" ]; then
            if [ -f "$s/$b.pdbqt" ]; then
                # Decomposes each $nl.pdbqt output result into the pose files:           
                $vina_split --input "$s/$b.pdbqt" # Running the vina split

                # Extracts binding energy and RMSD of the out.pdbqt multimodel file:
                energy_md1=$(awk '/MODEL 1/ {getline; if ($0 ~ /REMARK VINA RESULT:/) print; exit}' "$s/$b.pdbqt")
                results_rmsd=$(grep 'REMARK VINA RESULT:' "$s/$b.pdbqt")
                e=$(echo "$energy_md1" | awk '{print $4}')
                rmsd=$(echo "$results_rmsd" | awk '{print $5}')
                
                # Calculating the average RMSD of extracted values:
                    r=$(echo $rmsd | awk '{ 
                        sum = 0; 
                        for (i = 1; i <= NF; i++) { 
                            sum += $i; 
                        } 
                        print sum / NF  
                    }')
                            
                # Saves the ligand name, binding energy and rmsd to the result file:
                echo "$b,$e,$r" >> "$rp"
                echo "$b,$e,$r" >> "$rt"
            fi
            cp "$p" "$RR/$nP/$nL/"
        done
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
    done
done

# Calculation of total elapsed time and total performance information for all ligands and proteins:
end_time_total=$(date +%s)
total_time=$((end_time_total - start_time_total))
days=$((total_time / 86400))
hours=$(( (total_time % 86400) / 3600 ))
minutes=$(( (total_time % 3600) / 60 ))
seconds=$((total_time % 60))
all_ligands=$((crossings / target_account))

echo "##################################################################################################" >> "$dt"
echo "#                                 CODOC VERSION 1.1.1:                                           #" >> "$dt"
echo "#                         Developed by Moisés Maia Neto - 06/2024                                #" >> "$dt"
echo "##################################################################################################" >> "$dt"
echo "                                                                                                  " >> "$dt"
echo "                                                                                                  " >> "$dt"
echo "                          PROCESSED: $target_account targets                                      " >> "$dt"
echo "                                     $all_ligands ligands                                         " >> "$dt"
echo "                                     $crossings Crossings                                         " >> "$dt"
echo "                                                                                                  " >> "$dt"
echo "                          TOTAL ELAPSED TIME: $total_time seconds                                 " >> "$dt"
echo "              $days days : $hours hours : $minutes minutes : $seconds seconds                     " >> "$dt"
echo "                                                                                                  " >> "$dt"
echo "°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°" >> "$dt"
dialog --title "ATTENTION" --msgbox "RIGID DOCKING IS OVER! CHECK THE RESULTADOS_RIGIDO_CPU_"$current_date" FOLDER" 10 60
show_main_menu
}

#################################################################################################################################
#                                       FUNCTION TO PERFORM RIGID DOCKING (WITH GPU):                                           #
#################################################################################################################################
run_rigid_docking_gpu() {
dialog --title "ATTENTION" --msgbox "CHECK THE FILES IN THE TARGETS FOLDER: protein.pdbqt and grid.txt." 10 60  ;

# Start of the total time counter, total ligands count and targets count:
start_time_total=$(date +%s)
target_account=0
crossings=0

# Updating docking parameters according to user choices:
data="$CODOC_DIR/.form_data.txt"
threads="$(sed -n '4p' $data)"
num_modes="$(sed -n '5p' $data)"
energy_range="$(sed -n '7p' $data)"

# Creates the folder where all docking results and performance will be saved:
mkdir "$CODOC_DIR"/RIGID_DOCKING_RESULT_GPU_"$current_date"
RR="$CODOC_DIR/RIGID_DOCKING_RESULT_GPU_$current_date"

# Generates subfolders in the RIGID_DOCKING_RESULT_"$current_date" folder corresponding to the targets:
rsync -av --include=*/ --exclude=* $targets/* $RR

# Creates files where all docking results and total performance will be saved:
rt=$RR/TOTAL_RESULT_RIGID_DOCKING_GPU_"$current_date".csv && touch "$rt"
dt=$RR/TOTAL_PERFORMANCE_RIGID_DOCKING_GPU_"$current_date".txt && touch "$dt"

# 1st FOR Loop enters each protein folder present in the TARGETS folder, assigns the GridBox parameters, and copies the ligand group directories to the RIGID_DOCKING_RESULT_"$current_date" folder:
for P in "$targets/"*/; do
    nP=$(basename "$P")
    p="$targets/$nP/"protein.pdbqt

    # Create subfolders for each group of ligands in the targets folder present in RESULTS:
    rsync -av --include=*/ --exclude=* "$ligands"/* "$RR"/"$nP"

    # Creates files where all partial docking results and performance for each target will be stargets:
    rp=$RR/"$nP"/RIGID_DOCKING_RESULT_GPU_"$nP"_"$current_date".csv && touch "$rp"
    dp=$RR/"$nP"/RIGID_DOCKING_PERFORMANCE_GPU_"$nP"_"$current_date".txt && touch "$dp"

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
        dialog --title "ATTENTION" --msgbox " The grid.txt file was not found in the $targets/$nP folder. Generate the text file named as grid.txt in ADT and save it in the $targets/$nP folder." 10 60  ;
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
            dialog --title "ATTENTION" --msgbox " The grid.txt file is STILL MISSING in the $targets/$nP folder. Correct and Restart the process" 10 60;
            break
        fi
    fi

    #  Generates the headers where PARTIAL PERFORMANCES will be recorded in each of the targets:
    echo "########################################################################################" >> "$dp"
    echo "#                                 CODOC VERSION 1.1.1:                                 #" >> "$dp"
    echo "#                         Developed by Moisés Maia Neto - 06/2024                      #" >> "$dp"
    echo "########################################################################################" >> "$dp"
    echo "                                                                                        " >> "$dp"
    echo "########################################################################################" >> "$dp"
    echo "#                                 FROM TARGET: $nP                                     #" >> "$dp"
    echo "########################################################################################" >> "$dp"
    echo "                                                                                        " >> "$dp"

    # Generates the headers where the PARTIAL RESULTS will be recorded in each of the targets:
    echo "" >> "$rp"
    echo "TARGET","$nP" >> "$rp"

    # Generates the headers where the TOTAL RESULTS for each of the targets will be recorded:
    echo "" >> "$rt"
    echo "TARGET","$nP" >> "$rt"
    echo "LIGAND,BINDING ENERGY(Kcal/mol), RMSD(mean)" >> "$rt"

    ((target_account++)) # Adds 1 more to the target count

    # 2nd FOR Loop goes through each subfolder, with the ligand database, within the LIGANTES folder:
    for L in "$ligands/"*/; do
        nL=$(basename "$L")

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
        echo "/////////////////////////////FROM LIGAND DATABANK: $nL://///////////////////////////////" >> "$dp"
        echo "----------------------------------------------------------------------------------------" >> "$dp"
        echo "                                                                                        " >> "$dp"

        # Generates the headers where the LIGAND GROUPS will be recorded in the partial results file:
        echo "" >> "$rp"
        echo "LIGAND DATABANK","$nL" >> "$rp"
        echo "LIGAND,BINDING ENERGY(Kcal/mol), RMSD(mean)" >> "$rp"

        # Create a config file for each proteins and ligand database:   
        cat <<EOL > "$config_file"
receptor = $p
ligand_directory = $L
output_directory = $RR/$nP/$nL
opencl_binary_path = $opencl
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
        cd "$vina_GPU_dir"
        $vina_GPU --config "$config_file"
        cd "$CODOC_DIR"

        # 3rd FOR Loop create a directory for each .pdbqt ligand present in the subfolder:
        for out in "$RR/$nP"/*_out.pdbqt; do
            l=$(echo "$out" | sed 's/_out//')
            mv "$out" "$l"
            nl=$(basename "$l" .pdbqt)
            mkdir "$RR/$nP/$nL/$nl"
            mv "$l" "$RR/$nP/$nL/$nl"
            ((account_ligands++))
            ((crossings++))            
        done

        echo "////////////////////////////////////////////////////////////"
        echo "/Running the Vina Split // Ligand: $l                       "
        echo "////////////////////////////////////////////////////////////"
        for s in "$RR/$nP/$nL/"*/; do
            b=$(basename "$s")
            if [ -f "$s/$b".pdbqt ]; then
                # Decomposes each $nl.pdbqt output result into the pose files:           
                $vina_split --input $s/$b.pdbqt # Running the vina split

                # Extracts binding energy and RMSD of the out.pdbqt multimodel file:
                energy_md1=$(awk '/MODEL 1/ {getline; if ($0 ~ /REMARK VINA RESULT:/) print; exit}' "$s/$b.pdbqt")
                results_rmsd=$(grep 'REMARK VINA RESULT:' "$s/$b.pdbqt")
                e=$(echo "$energy_md1" | awk '{print $4}')
                rmsd=$(echo "$results_rmsd" | awk '{print $5}')
                
                # Calculating the average RMSD of extracted values:
                    r=$(echo $rmsd | awk '{ 
                        sum = 0; 
                        for (i = 1; i <= NF; i++) { 
                            sum += $i; 
                        } 
                        print sum / NF  
                    }')
                            
                # Saves the ligand name, binding energy and rmsd to the result file:
                echo "$b,$e,$r" >> "$rp"
                echo "$b,$e,$r" >> "$rt"
            fi
            cp "$p" "$RR/$nP/$nL/"
        done
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
    done
done

# Calculation of total elapsed time and total performance information for all ligands and proteins:
end_time_total=$(date +%s)
total_time=$((end_time_total - start_time_total))
days=$((total_time / 86400))
hours=$(( (total_time % 86400) / 3600 ))
minutes=$(( (total_time % 3600) / 60 ))
seconds=$((total_time % 60))
all_ligands=$((crossings / target_account))

echo "##################################################################################################" >> "$dt"
echo "#                                 CODOC VERSION 1.1.1:                                           #" >> "$dt"
echo "#                         Developed by Moisés Maia Neto - 06/2024                                #" >> "$dt"
echo "##################################################################################################" >> "$dt"
echo "                                                                                                  " >> "$dt"
echo "                                                                                                  " >> "$dt"
echo "                          PROCESSED: $target_account targets                                      " >> "$dt"
echo "                                     $all_ligands ligands                                         " >> "$dt"
echo "                                     $crossings Crossings                                         " >> "$dt"
echo "                                                                                                  " >> "$dt"
echo "                          TOTAL ELAPSED TIME: $total_time seconds                                 " >> "$dt"
echo "              $days days : $hours hours : $minutes minutes : $seconds seconds                     " >> "$dt"
echo "                                                                                                  " >> "$dt"
echo "°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°" >> "$dt"
dialog --title "ATTENTION" --msgbox "RIGID DOCKING IS OVER! CHECK THE RESULTADOS_RIGIDO_GPU_"$current_date" FOLDER" 10 60
show_main_menu
}

#################################################################################################################################
#                                       FUNCTION TO PERFORM FLEXIBLE DOCKING (WITH CPU):                                           #
#################################################################################################################################
run_flexible_docking_cpu() {
dialog --title "ATTENTION" --msgbox "CHECK THE FILES IN THE TARGETS FOLDER: protein_rigid.pdbqt, protein_flex.pdbqt e grid.txt." 10 60  ;

# Updating docking parameters according to user choices:
data="$CODOC_DIR/.form_data.txt"
sf="$(sed -n '1p' $data)"
cpu="$(sed -n '2p' $data)"
ext="$(sed -n '3p' $data)"
num_modes="$(sed -n '5p' $data)"
min_rmsd="$(sed -n '6p' $data)"
energy_range="$(sed -n '7p' $data)"
spacing="$(sed -n '8p' $data)"
runs="$(sed -n '10p' $data)"

# Creates the folder where all docking results and performance will be saved:
mkdir "$CODOC_DIR"/FLEXIBLE_DOCKING_RESULT_CPU_"$current_date"
RF="$CODOC_DIR/FLEXIBLE_DOCKING_RESULT_CPU_$current_date"

# Generates subfolders in the RIGID_DOCKING_RESULT_"$current_date" folder corresponding to the targets:
rsync -av --include=*/ --exclude=* $targets/* $RF

# Start of the total time counter, total ligands count and targets count:
start_time_total=$(date +%s)
target_account=0
crossings=0

# Creates files where all docking results and total performance will be saved:
rt=$RF/TOTAL_RESULT_FLEXIBLE_DOCKING_CPU_"$current_date".csv && touch "$rt"
dt=$RF/TOTAL_PERFORMANCE_FLEXIBLE_DOCKING_CPU_"$current_date".txt && touch "$dt"

# 1st FOR Loop enters each protein folder present in the TARGETS folder, assigns the GridBox parameters, and copies the ligand group directories to the RIGID_DOCKING_RESULT_"$current_date" folder:
for P in "$targets/"*/; do
    nP=$(basename "$P")
    pR="$targets/$nP/protein_rigid.pdbqt"
    pF="$targets/$nP/protein_flex.pdbqt"

    # Create subfolders for each group of ligands in the targets folder present in RESULTS:
    rsync -av --include=*/ --exclude=* "$ligands"/* "$RF"/"$nP"

    # Creates files where all partial docking results and performance for each target will be stargets:
    rp=$RF/"$nP"/FLEXIBLE_DOCKING_RESULT_CPU_"$nP"_"$current_date".csv && touch "$rp"
    dp=$RF/"$nP"/FLEXIBLE_DOCKING_PERFORMANCE_CPU_"$nP"_"$current_date".txt && touch "$dp"
    
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
        dialog --title "ATTENTION" --msgbox " The grid.txt file was not found in the $targets/$nP folder. Generate the text file named as grid.txt in ADT and save it in the $targets/$nP folder." 10 60  ;
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
            dialog --title "ATTENTION" --msgbox " The grid.txt file is STILL MISSING in the $targets/$nP folder. Correct and Restart the process" 10 60;
            break
        fi
    fi

    #  Generates the headers where PARTIAL PERFORMANCES will be recorded in each of the targets:
    echo "########################################################################################" >> "$dp"
    echo "#                                 CODOC VERSION 1.1.1:                                 #" >> "$dp"
    echo "#                         Developed by Moisés Maia Neto - 06/2024                      #" >> "$dp"
    echo "########################################################################################" >> "$dp"
    echo "                                                                                        " >> "$dp"
    echo "########################################################################################" >> "$dp"
    echo "#                                 FROM TARGET: $nP                                     #" >> "$dp"
    echo "########################################################################################" >> "$dp"
    echo "                                                                                        " >> "$dp"

    # Generates the headers where the PARTIAL RESULTS will be recorded in each of the targets:
    echo "" >> "$rp"
    echo "TARGET","$nP" >> "$rp"


    # Generates the headers where the TOTAL RESULTS for each of the targets will be recorded:
    echo "" >> "$rt"
    echo "TARGET","$nP" >> "$rt"
    echo "LIGAND,BINDING ENERGY(Kcal/mol), RMSD(mean)" >> "$rt"

    ((target_account++)) # Adds 1 more to the target account

    # 2nd FOR Loop goes through each subfolder, with the ligand database, within the LIGANTES folder:
    for L in "$ligands/"*/; do
        nL=$(basename "$L")

        # Start of time counter and ligands account for the ligand databank:
        start_time_P=$(date +%s)
        account_ligands=0
             
        # Generates the headers where the LIGAND GROUPS will be recorded in the performance file:       
        echo "                                                                                        " >> "$dp"
        echo "----------------------------------------------------------------------------------------" >> "$dp"
        echo "/////////////////////////////FROM LIGAND DATABANK: $nL://///////////////////////////////" >> "$dp"
        echo "----------------------------------------------------------------------------------------" >> "$dp"
        echo "                                                                                        " >> "$dp"

        # Generates the headers where the LIGAND GROUPS will be recorded in the partial results file:
        echo "" >> "$rp"
        echo "LIGAND DATABANK","$nL" >> "$rp"
        echo "LIGAND,BINDING ENERGY(Kcal/mol), RMSD(mean)" >> "$rp"

        # 3rd FOR Loop executes docking on each .pdbqt ligand present in the subfolder:
        for l in "$L"*.pdbqt; do
            nl=$(basename "$l" .pdbqt)
            echo "////////////////////////////////////////////////////////////"
            echo "/Running the docking calculation // Ligand: $nl             "
            echo "////////////////////////////////////////////////////////////"
            mkdir "$RF/$nP/$nL/$nl"
            
            # Running the docking calculation
            $vina --center_x $c_x --center_y $c_y --center_z $c_z --size_x $s_x --size_y $s_y --size_z $s_z --scoring "$sf" --cpu $cpu --exhaustiveness $ext --num_modes $num_modes --min_rmsd $min_rmsd --energy_range $energy_range --spacing $spacing --ligand "$l" --receptor $pR --flex $pF --out "$RF/$nP/$nL/$nl/$nl.pdbqt" &

            ((account_ligands++))
            ((crossings++))  
            if ((account_ligands % $runs == 0)); then  # Check if "$runs" ligands have been processed
                wait  # Wait for all background processes to finish          
            fi
        done
        wait
        for s in "$RF/$nP/$nL/"*/; do
            b=$(basename "$s")
            echo "////////////////////////////////////////////////////////////"
            echo "/Running the Vina Split // Ligand: $b                       "
            echo "////////////////////////////////////////////////////////////"
#            if [ -f "$RR/$nP/$nL/$b/$b.pdbqt" ]; then
            if [ -f "$s/$b.pdbqt" ]; then
                # Decomposes each $nl.pdbqt output result into the pose files:           
                $vina_split --input "$s/$b.pdbqt" # Running the vina split

                # Extracts binding energy and RMSD of the out.pdbqt multimodel file:
                energy_md1=$(awk '/MODEL 1/ {getline; if ($0 ~ /REMARK VINA RESULT:/) print; exit}' "$s/$b.pdbqt")
                results_rmsd=$(grep 'REMARK VINA RESULT:' "$s/$b.pdbqt")
                e=$(echo "$energy_md1" | awk '{print $4}')
                rmsd=$(echo "$results_rmsd" | awk '{print $5}')
                
                # Calculating the average RMSD of extracted values:
                    r=$(echo $rmsd | awk '{ 
                        sum = 0; 
                        for (i = 1; i <= NF; i++) { 
                            sum += $i; 
                        } 
                        print sum / NF  
                    }')
                            
                # Saves the ligand name, binding energy and rmsd to the result file:
                echo "$b,$e,$r" >> "$rp"
                echo "$b,$e,$r" >> "$rt"
            fi
            cp "$pR" "$RF/$nP/$nL/"
            cp "$pF" "$RF/$nP/$nL/"
        done
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
    done
done

# Calculation of total elapsed time and total performance information for all ligands and proteins:
end_time_total=$(date +%s)
total_time=$((end_time_total - start_time_total))
days=$((total_time / 86400))
hours=$(( (total_time % 86400) / 3600 ))
minutes=$(( (total_time % 3600) / 60 ))
seconds=$((total_time % 60))
all_ligands=$((crossings / target_account))

echo "##################################################################################################" >> "$dt"
echo "#                                 CODOC VERSION 1.1.1:                                           #" >> "$dt"
echo "#                         Developed by Moisés Maia Neto - 06/2024                                #" >> "$dt"
echo "##################################################################################################" >> "$dt"
echo "                                                                                                  " >> "$dt"
echo "                                                                                                  " >> "$dt"
echo "                          PROCESSED: $target_account targets                                      " >> "$dt"
echo "                                     $all_ligands ligands                                         " >> "$dt"
echo "                                     $crossings Crossings                                         " >> "$dt"
echo "                                                                                                  " >> "$dt"
echo "                          TOTAL ELAPSED TIME: $total_time seconds                                 " >> "$dt"
echo "              $days days : $hours hours : $minutes minutes : $seconds seconds                     " >> "$dt"
echo "                                                                                                  " >> "$dt"
echo "°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°" >> "$dt"
dialog --title "ATTENTION" --msgbox "FLEXIBLE DOCKING IS OVER! CHECK THE FLEXIBLE_DOCKING_RESULT_CPU_"$current_date" FOLDER" 10 60
show_main_menu
remove_parameters
}

#################################################################################################################################
#                                       FUNCTION TO PERFORM FLEXIBLE DOCKING (WITH GPU):                                        #
#################################################################################################################################
run_flexible_docking_gpu() {
dialog --title "ATTENTION" --msgbox "CHECK THE FILES IN THE TARGETS FOLDER: protein_rigid.pdbqt, protein_flex.pdbqt e grid.txt." 10 60  ;

# Start of the total time counter, total ligands count and targets count:
start_time_total=$(date +%s)
target_account=0
crossings=0

# Updating docking parameters according to user choices:
data="$CODOC_DIR/.form_data.txt"
threads="$(sed -n '4p' $data)"
num_modes="$(sed -n '5p' $data)"
energy_range="$(sed -n '7p' $data)"

# Creates the folder where all docking results and performance will be saved:
mkdir "$CODOC_DIR"/FLEXIBLE_DOCKING_RESULT_GPU_"$current_date"
RF="$CODOC_DIR/FLEXIBLE_DOCKING_RESULT_GPU_$current_date"

# Generates subfolders in the FLEXIBLE_DOCKING_RESULT_GPU_"$current_date" folder corresponding to the targets:
rsync -av --include=*/ --exclude=* $targets/* $RF

# Creates files where all docking results and total performance will be saved:
rt=$RF/TOTAL_RESULT_FLEXIBLE_DOCKING_GPU_"$current_date".csv && touch "$rt"
dt=$RF/TOTAL_PERFORMANCE_FLEXIBLE_DOCKING_GPU_"$current_date".txt && touch "$dt"

# 1st FOR Loop enters each protein folder present in the TARGETS folder, assigns the GridBox parameters, and copies the ligand group directories to the RIGID_DOCKING_RESULT_"$current_date" folder:
for P in "$targets/"*/; do
    nP=$(basename "$P")
    pR="$targets/$nP/protein_rigid.pdbqt"
    pF="$targets/$nP/protein_flex.pdbqt"

    # Create subfolders for each group of ligands in the targets folder present in RESULTS:
    rsync -av --include=*/ --exclude=* "$ligands"/* "$RF"/"$nP"

    # Creates files where all partial docking results and performance for each target will be stargets:
    rp=$RF/"$nP"/FLEXIBLE_DOCKING_RESULT_GPU_"$nP"_"$current_date".csv && touch "$rp"
    dp=$RF/"$nP"/FLEXIBLE_DOCKING_PERFORMANCE_GPU_"$nP"_"$current_date".txt && touch "$dp"

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
        dialog --title "ATTENTION" --msgbox " The grid.txt file was not found in the $targets/$nP folder. Generate the text file named as grid.txt in ADT and save it in the $targets/$nP folder." 10 60  ;
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
            dialog --title "ATTENTION" --msgbox " The grid.txt file is STILL MISSING in the $targets/$nP folder. Correct and Restart the process" 10 60;
            break
        fi
    fi

    #  Generates the headers where PARTIAL PERFORMANCES will be recorded in each of the targets:
    echo "########################################################################################" >> "$dp"
    echo "#                                 CODOC VERSION 1.1.1:                                 #" >> "$dp"
    echo "#                         Developed by Moisés Maia Neto - 06/2024                      #" >> "$dp"
    echo "########################################################################################" >> "$dp"
    echo "                                                                                        " >> "$dp"
    echo "########################################################################################" >> "$dp"
    echo "#                                 FROM TARGET: $nP                                     #" >> "$dp"
    echo "########################################################################################" >> "$dp"
    echo "                                                                                        " >> "$dp"

    # Generates the headers where the PARTIAL RESULTS will be recorded in each of the targets:
    echo "" >> "$rp"
    echo "TARGET","$nP" >> "$rp"

    # Generates the headers where the TOTAL RESULTS for each of the targets will be recorded:
    echo "" >> "$rt"
    echo "TARGET","$nP" >> "$rt"
    echo "LIGAND,BINDING ENERGY(Kcal/mol), RMSD(mean)" >> "$rt"

    ((target_account++)) # Adds 1 more to the target count

    # 2nd FOR Loop goes through each subfolder, with the ligand database, within the LIGANTES folder:
    for L in "$ligands/"*/; do
        nL=$(basename "$L")

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
        echo "/////////////////////////////FROM LIGAND DATABANK: $nL://///////////////////////////////" >> "$dp"
        echo "----------------------------------------------------------------------------------------" >> "$dp"
        echo "                                                                                        " >> "$dp"

        # Generates the headers where the LIGAND GROUPS will be recorded in the partial results file:
        echo "" >> "$rp"
        echo "LIGAND DATABANK","$nL" >> "$rp"
        echo "LIGAND,BINDING ENERGY(Kcal/mol), RMSD(mean)" >> "$rp"

        # Create a config file for each proteins and ligand database:   
        cat <<EOL > "$config_file"
receptor = $pR
flex = $pF
ligand_directory = $L
output_directory = $RF/$nP/$nL
opencl_binary_path = $opencl
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
        cd "$vina_GPU_dir"
        $vina_GPU --config "$config_file"
        cd "$CODOC_DIR"

        # 3rd FOR Loop create a directory for each .pdbqt ligand present in the subfolder:
        for out in "$RR/$nP"/*_out.pdbqt; do
            l=$(echo "$out" | sed 's/_out//')
            mv "$out" "$l"
            nl=$(basename "$l" .pdbqt)
            mkdir "$RF/$nP/$nL/$nl"
            mv "$l" "$RF/$nP/$nL/$nl"
            ((account_ligands++))
            ((crossings++))            
        done

        echo "////////////////////////////////////////////////////////////"
        echo "/Running the Vina Split // Ligand: $l                       "
        echo "////////////////////////////////////////////////////////////"
        for s in "$RF/$nP/$nL/"*/; do
            b=$(basename "$s")
            if [ -f "$s/$b".pdbqt ]; then
                # Decomposes each $nl.pdbqt output result into the pose files:           
                $vina_split --input $s/$b.pdbqt # Running the vina split

                # Extracts binding energy and RMSD of the out.pdbqt multimodel file:
                energy_md1=$(awk '/MODEL 1/ {getline; if ($0 ~ /REMARK VINA RESULT:/) print; exit}' "$s/$b.pdbqt")
                results_rmsd=$(grep 'REMARK VINA RESULT:' "$s/$b.pdbqt")
                e=$(echo "$energy_md1" | awk '{print $4}')
                rmsd=$(echo "$results_rmsd" | awk '{print $5}')
                
                # Calculating the average RMSD of extracted values:
                    r=$(echo $rmsd | awk '{ 
                        sum = 0; 
                        for (i = 1; i <= NF; i++) { 
                            sum += $i; 
                        } 
                        print sum / NF  
                    }')
                            
                # Saves the ligand name, binding energy and rmsd to the result file:
                echo "$b,$e,$r" >> "$rp"
                echo "$b,$e,$r" >> "$rt"
            fi
            cp "$pR" "$RF/$nP/$nL/"
            cp "$pF" "$RF/$nP/$nL/"
        done
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
    done
done

# Calculation of total elapsed time and total performance information for all ligands and proteins:
end_time_total=$(date +%s)
total_time=$((end_time_total - start_time_total))
days=$((total_time / 86400))
hours=$(( (total_time % 86400) / 3600 ))
minutes=$(( (total_time % 3600) / 60 ))
seconds=$((total_time % 60))
all_ligands=$((crossings / target_account))

echo "##################################################################################################" >> "$dt"
echo "#                                 CODOC VERSION 1.1.1:                                           #" >> "$dt"
echo "#                         Developed by Moisés Maia Neto - 06/2024                                #" >> "$dt"
echo "##################################################################################################" >> "$dt"
echo "                                                                                                  " >> "$dt"
echo "                                                                                                  " >> "$dt"
echo "                          PROCESSED: $target_account targets                                      " >> "$dt"
echo "                                     $all_ligands ligands                                         " >> "$dt"
echo "                                     $crossings Crossings                                         " >> "$dt"
echo "                                                                                                  " >> "$dt"
echo "                          TOTAL ELAPSED TIME: $total_time seconds                                 " >> "$dt"
echo "              $days days : $hours hours : $minutes minutes : $seconds seconds                     " >> "$dt"
echo "                                                                                                  " >> "$dt"
echo "°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°" >> "$dt"
dialog --title "ATTENTION" --msgbox "FLEXIBLE DOCKING IS OVER! CHECK THE FLEXIBLE_DOCKING_RESULT_GPU_"$current_date" FOLDER" 10 60
show_main_menu
remove_parameters
}

#################################################################################################################################
#                                       FUNCTION FOR REMOVING PARAMETER FILES:                                                  #
#################################################################################################################################

#Função de acesso global para remoção de parâmetros:
remove_parameters() {
rm /$CODOC_DIR/.form_data.txt
rm /$CODOC_DIR/.menu_escolha.txt
}

show_main_menu

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
# FOR OPENBABEL 3.1.1:
# N M O'Boyle, M Banck, C A James, C Morley, T Vandermeersch, and G R Hutchison. "Open Babel: An open chemical toolbox." J. Cheminf. (2011), 3, 33. DOI:10.1186/1758-2946-3-33
#---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
