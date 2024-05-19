#!/bin/bash
#################################################################################################################################
#                                               CODOC VERSION 1.0.0:                                                            #
#                                      Developed by Moisés Maia Neto - 05/2024                                                  #
#################################################################################################################################

# Predefined global access address variables:
current_date=$(date +"%d_%m_%Y")
doc="$HOME/MGLTools-1.5.7/doc"
ligands="$HOME/MGLTools-1.5.7/doc/LIGANDS"
targets="$HOME/MGLTools-1.5.7/doc/TARGETS"
data="$HOME/MGLTools-1.5.7/doc/.form_data.txt"
RR="$HOME/MGLTools-1.5.7/doc/RIGID_DOCKING_RESULT_$current_date"
RF="$HOME/MGLTools-1.5.7/doc/FLEXIBLE_DOCKING_RESULT_$current_date"

# Predefined global access parameter variables:
sf="vina"
cpu="16"
ext="32"
num_modes="9"
min_rmsd="1"
energy_range="3"
spacing="0.375"
pH="7.4"

#################################################################################################################################
#                                       FUNCTION TO DISPLAY THE MAIN MENU:                                                      #
#################################################################################################################################
title=("|||| C O D O C ||||  A AUTOMATIZED MULTI-TARGET DOCKING TOOL - with AutoDock Vina 1.2.5 and OpenBabel 3.1.1")
show_main_menu() {
    dialog --clear --backtitle "$title" \
    --title "MAIN MENU" \
    --menu "select an option:" 15 60 5 \
    1 "Docking Settings" \
    2 "Run Ligands Prepare" \
    3 "Run Rigid Docking" \
    4 "Run Flexible Docking" \
    5 "SAIR" \
    2> .menu_escolha.txt

    opcao=$(cat .menu_escolha.txt)
    case $opcao in
        1) show_form ;;
        2) run_ligands_prepare ;;
        3) run_rigid_docking ;;
        4) run_flexible_docking ;;
        5) remove_parameters; clear ; exit 0 ;;
        *) remove_parameters; clear ; exit 0 ;;
    esac
}

#################################################################################################################################
#                               FUNÇÃO PARA CONFIGURAR PARÂMETROS E VARIÁVEIS DE DOCKING:                                       #
#################################################################################################################################
show_form() {
     form_data
     form_data=$(dialog --backtitle "$title" \
     --title "CONFIGURATION PARAMETERS" \
     --form "Change the fields below if necessary:" 22 65 0 \
     "Scoring function:" 1 4 "$sf" 1 35 20 0 \
     "vina / ad4 / vinardo" 2 4 "" 0 0 0 0 \
     "CPUs:" 4 4 "$cpu" 4 35 20 0 \
     "Exhaustiveness" 6 4 "$ext" 6 35 20 0 \
     "Poses" 8 4 "$num_modes" 8 35 20 0 \
     "minimum RMSD" 10 4 "$min_rmsd" 10 35 20 0 \
     "Energy Range (Kcal/mol)" 12 4 "$energy_range" 12 35 20 0 \
     "Grid Spacing" 14 4 "$spacing" 14 35 20 0 \
     "pH" 16 4 "$pH" 16 35 20 0 \
     3>&1 1>&2 2>&3)

     # Check if the user canceled the form:
     if [ $? -eq 0 ]; then
         # Assign the entered data to variables:
         echo "$form_data" > .form_data.txt
         source .form_data.txt
         export $sf
         export $cpu
         export $ext
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
#                           FUNÇÃO PARA PREPARAR OS LIGANTES PARA O DOCKING:                                                    #
#################################################################################################################################
run_ligands_prepare() {
# INITIAL USER GUIDELINES:
dialog --title "ATTENTION" --msgbox "FILES WITH MULTIPLE LIGANDS MUST BE PLACED IN THE "LIGANDS" FOLDER AND SINGLE LIGAND FILES MUST BE PLACED IN SUB FOLDERS WITHIN "LIGANDS" FOLDER. NAME THESE SUB FOLDERS WITH ACRONYMS THAT IDENTIFY THE LIGAND DATABASE!" 10 60 ;
dialog --title "ATTENTION" --msgbox "ONLY SOME FILE FORMATS ARE ACCEPTED: .mol2/.sdf/.smi/.pdb" 10 60 ;

# CHECK IF THERE ARE SUBFOLDERS IN THE LIGANDS FOLDER:
quantity_subfolders=$(find "$ligands" -mindepth 1 -maxdepth 1 -type d ! -path "$ligands" | wc -l)
if [ "$quantity_subfolders" -eq 0 ]; then
    echo 
    dialog --title "ATTENTION" --msgbox "THE LIGANDS FOLDER DOES NOT HAVE ANY SUB FOLDER!" 10 60 ;
    
elif [ "$quantity_subfolders" -gt 0 ]; then
    for L in "$ligands/"*/; do
        cd "$L"
        quantity_files=$(find "$L" -maxdepth 1 -type f | wc -l)
        if [ "$quantity_files" -eq 0 ]; then
            dialog --title "ATTENTION" --msgbox "THERE ARE NO FILES IN THE "$L" SUBFOLDER. WAIT FOR THE FOLDER TO BE DELETED!" 10 60 ;
            rm -r $L  || continue  
        elif [ "$quantity_files" -gt 0 ]; then
            for LIG in "$L"/*; do
                if [[ "$LIG" == *.sdf ]]; then
                    l=$(basename $LIG .sdf)
                    obabel -i sdf "$l".sdf -o pdbqt -O "$l".pdbqt -h --pH "$pH" --partialcharge gasteiger --minimize --sd --ff GAFF --n 1000
                    rm "$l".sdf
                elif [[ "$LIG" == *.mol2 ]]; then
                    l=$(basename $LIG .mol2)
                    obabel -i mol2 "$l".mol2 -o pdbqt -O "$l".pdbqt -h --pH "$pH" --partialcharge gasteiger --minimize --sd --ff GAFF --n 1000
                    rm "$l".mol2
                elif [[ "$LIG" == *.smi ]]; then
                    l=$(basename $LIG .smi)
                    obabel -i smi "$l".smi -o pdbqt -O "$l".pdbqt -h --pH "$pH" --gen3d --partialcharge gasteiger --minimize --sd --ff GAFF --n 1000
                    rm "$l".smi
                elif [[ "$LIG" == *.pdb ]]; then
                    l=$(basename $LIG .pdb)
                    obabel -i pdb "$l".pdb -o pdbqt -O "$l".pdbqt -h --pH "$pH" --partialcharge gasteiger --minimize --sd --ff GAFF --n 1000
                    rm "$l".pdb
                elif [[ "$LIG" == *.pdbqt ]]; then
                    echo "Formato do arquivo "$l" em "$L" já é .pdbqt"
                else
                    dialog --title "ATTENTION" --yesno "FILE FORMAT NOT RECOGNIZED. DO YOU WANT TO DELETE THE FILE $l ?" 10 60 ;
                        if [ $? -eq 0 ]; then
                            rm -r $LIG
                        else
                            mkdir "$HOME/MGLTools-1.5.7/doc/NOT_RECOGNIZED_LIGANDS/"
                            mv "$LIG" "$HOME/MGLTools-1.5.7/doc/NOT_RECOGNIZED_LIGANDS/"
                        fi                    
                fi
            done
        fi            
        cd ../
    done
fi

# CHECK IF THERE ARE MULTI-MODEL FILES IN THE "LIGANDS" FOLDER:
quantity_files=$(find "$ligands" -maxdepth 1 -type f | wc -l)
if [ "$quantity_files" -eq 0 ]; then
    dialog --title "ATTENTION" --msgbox "THERE ARE NO LIGANDS FILES IN THE "LIGANDS" FOLDER" 10 60 ;
    
elif [ "$quantity_files" -gt 0 ]; then
    cd $ligands
    for multi in "$ligands"/*; do
        if [ -f "$multi" ]; then
            if [[ "$multi" == *.sdf ]]; then
                LIG=$(basename $multi .sdf)
                mkdir "$ligands"/$LIG
                    obabel -i sdf "$ligands"/*.sdf -o sdf -O "$ligands"/$LIG/.sdf --split
                    for file in "$ligands"/$LIG/*; do
                        # Checks if the file exists
                        if [ -f "$file" ]; then
                            #f=$(basename "$file" )
                            # Extract zinc_id from file using awk
                            zinc=$(awk '/>  <zinc_id>/ {getline; print}' "$file")
                            # Checks if zinc_id was found
                            if [ -n "$zinc" ]; then
                                # Rename the file with zinc_id
                                mv $file $ligands/$LIG/"$zinc".sdf                  
                            else
                                echo "Unable to find zinc_id in "$file""
                            fi
                        fi
                    done        
                obabel -i sdf "$ligands"/"$LIG"/*.sdf -o pdbqt -O "$ligands"/"$LIG"/*.pdbqt -h --pH "$pH" --partialcharge gasteiger --minimize --sd --ff GAFF --n 1000
                rm "$multi"
                rm "$ligands"/"$LIG"/*.sdf
                # Due to a conversion error, the first line must be deleted so that it is no longer recognized as a multi-model file
                for file in "$ligands"/$LIG/*; do
                        # Checks if the file exists
                        if [[ -f "$file" ]]; then
                            # Use sed to remove the first line and the last line
                            sed '1d' "$file" > "${file}.tmp"
                        # Replaces the original file with the temporary file
                            mv "${file}.tmp" "$file"
                    fi
                done
                
            elif [[ "$multi" == *.mol2 ]]; then
                LIG=$(basename $multi .mol2)
                mkdir "$ligands"/$LIG
                obabel -i mol2 "$ligands"/*.mol2 -o pdbqt -O "$ligands"/"$LIG"/.pdbqt --split -h --pH "$pH" --partialcharge gasteiger --minimize --sd --ff GAFF --n 1000
                rm "$multi"
                # Due to a conversion error, the first and the last lines must be deleted so that it is no longer recognized as a multi-model file
                for file in "$ligands"/$LIG/*; do
                    # Checks if the file exists
                    if [[ -f "$file" ]]; then
                        # Counts the total number of lines in the file
                        ENDMDL=$(wc -l < "$file")
                        # Use sed to remove the first and last lines
                        sed '1d;'"${ENDMDL}"'d' "$file" > "${file}.tmp"
                        # Replaces the original file with the temporary file
                        mv "${file}.tmp" "$file"
                    fi
                done

            elif [[ "$multi" == *.smi ]]; then
                LIG=$(basename $multi .smi)
                mkdir "$ligands"/$LIG
                obabel -i smi "$ligands"/*.smi -o pdbqt -O "$ligands"/"$LIG"/.pdbqt --split -h --pH "$pH" --gen3d --partialcharge gasteiger --minimize --sd --ff GAFF --n 1000
                rm "$multi"
                # Due to a conversion error, the first and the last lines must be deleted so that it is no longer recognized as a multi-model file
                for file in "$ligands"/$LIG/*; do
                    # Checks if the file exists
                    if [[ -f "$file" ]]; then
                        # Counts the total number of lines in the file
                        ENDMDL=$(wc -l < "$file")
                        # Use sed to remove the first and last lines
                        sed '1d;'"${ENDMDL}"'d' "$file" > "${file}.tmp"
                        # Replaces the original file with the temporary file
                        mv "${file}.tmp" "$file"
                    fi
                done

            elif [[ "$multi" == *.pdbqt ]]; then
                # There are no multi-model .pdbqt files so there is no need to split                
                mkdir "$ligands"/LIG
                cp $multi "$ligands"/LIG
                rm $multi

            else
                dialog --title "ATTENTION" --yesno "FILE FORMAT NOT RECOGNIZED. DO YOU WANT TO DELETE THE FILE $multi ?" 10 60 ;
                    if [ $? -eq 0 ]; then
                        rm $multi
                    else
                        mkdir "$HOME/MGLTools-1.5.7/doc/NOT_RECOGNIZED_LIGANDS/"
                        mv $multi "$HOME/MGLTools-1.5.7/doc/NOT_RECOGNIZED_LIGANDS/"
                    fi                      
            fi
        else
            continue
        fi
    done
    cd ../
fi
dialog --title "ATTENTION" --msgbox "THE PREPARATION OF THE LIGANDS IS FINISHED! CHECK THE LIGANDS FOLDER" 10 60 ;
show_main_menu
}


#################################################################################################################################
#                                       FUNCTION TO PERFORM RIGID DOCKING:                                                       #
#################################################################################################################################
run_rigid_docking() {
dialog --title "ATTENTION" --msgbox "CHECK THE FILES IN THE TARGETS FOLDER: protein.pdbqt and grid.txt." 10 60  ;
# Updating docking parameters according to user choices:
data="$HOME/MGLTools-1.5.7/doc/.form_data.txt"
sf="$(sed -n '1p' $data)"
cpu="$(sed -n '2p' $data)"
ext="$(sed -n '3p' $data)"
num_modes="$(sed -n '4p' $data)"
min_rmsd="$(sed -n '5p' $data)"
energy_range="$(sed -n '6p' $data)"
spacing="$(sed -n '7p' $data)"
pH="$(sed -n '8p' $data)"

# Creates the folder where all docking results and performance will be saved:
mkdir "$doc"/RIGID_DOCKING_RESULT_"$current_date"

# Generates subfolders in the RIGID_DOCKING_RESULT_"$current_date" folder corresponding to the targets:
rsync -av --include=*/ --exclude=* $targets/* $RR

# Start of the total time counter and processed targets:
target_account=0 
start_time_total=$(date +%s)

# Creates files where all docking results and total performance will be saved:
rt=$RR/TOTAL_RESULT_RIGID_DOCKING_"$current_date".csv && touch "$rt"
dt=$RR/TOTAL_PERFORMANCE_RIGID_DOCKING_"$current_date".txt && touch "$dt"

# 1st FOR Loop enters each protein folder present in the TARGETS folder, assigns the GridBox parameters, and copies the ligand group directories to the RIGID_DOCKING_RESULT_"$current_date" folder:
for P in "$targets/"*/; do
    nP=$(basename "$P")
    p="$targets/$nP/protein.pdbqt"

    # Create subfolders for each group of ligands in the targets folder present in RESULTS:
    rsync -av --include=*/ --exclude=* "$ligands"/* "$RR"/"$nP"

    # Creates files where all partial docking results and performance for each target will be stargets:
    rp=$RR/"$nP"/RIGID_DOCKING_RESULT_"$nP"_"$current_date".csv && touch "$rp"
    dp=$RR/"$nP"/RIGID_DOCKING_PERFORMANCE_"$nP"_"$current_date".txt && touch "$dp"
    
    # Checks if the grid.txt file exists in the $targets/$nP folder
    if [ -f "$targets/$nP/grid.txt" ]; then
        # If the file exists, it updates the Grid Box parameters:
        grid=/$targets/$nP/grid.txt
        c_x=$(awk 'NR==4 {print substr($0, 11, 7)}' "$grid")
        c_y=$(awk 'NR==4 {print substr($0, 19, 7)}' "$grid")
        c_z=$(awk 'NR==4 {print substr($0, 27, 7)}' "$grid")
        s_x=$(awk 'NR==3 {print substr($0, 12, 2)}' "$grid")
        s_y=$(awk 'NR==3 {print substr($0, 15, 2)}' "$grid")
        s_z=$(awk 'NR==3 {print substr($0, 18, 2)}' "$grid")
    else
        dialog --title "ATTENTION" --msgbox " The grid.txt file was not found in the $targets/$nP folder. Generate the text file named as grid.txt in ADT and save it in the $targets/$nP folder." 10 60  ;
        if [ -f "$targets/$nP/grid.txt" ]; then
            # If the file exists, it updates the Grid Box parameters:
            grid=/$targets/$nP/grid.txt
            c_x=$(awk 'NR==4 {print substr($0, 11, 7)}' "$grid")
            c_y=$(awk 'NR==4 {print substr($0, 19, 7)}' "$grid")
            c_z=$(awk 'NR==4 {print substr($0, 27, 7)}' "$grid")
            s_x=$(awk 'NR==3 {print substr($0, 12, 2)}' "$grid")
            s_y=$(awk 'NR==3 {print substr($0, 15, 2)}' "$grid")
            s_z=$(awk 'NR==3 {print substr($0, 18, 2)}' "$grid")
        else
            dialog --title "ATTENTION" --msgbox " The grid.txt file is STILL MISSING in the $targets/$nP folder. Correct and Restart the process" 10 60;
            break
        fi
    fi

    #  Generates the headers where PARTIAL PERFORMANCES will be recorded in each of the targets:
    echo "########################################################################################" >> "$dp"
    echo "#                                 CODOC VERSION 1.0.0:                                 #" >> "$dp"
    echo "#                         Developed by Moisés Maia Neto - 05/2024                      #" >> "$dp"
    echo "########################################################################################" >> "$dp"
    echo "                                                                                        " >> "$dp"
    echo "########################################################################################" >> "$dp"
    echo "#                                 FROM TARGET: $nP                                     #" >> "$dp"
    echo "########################################################################################" >> "$dp"
    echo "                                                                                        " >> "$dp"

    # Generates the headers where the PARTIAL RESULTS will be recorded in each of the targets:
    echo "" >> "$rp"
    echo "TARGET","$nP" >> "$rp"
    echo "LIGAND,BINDING ENERGY(Kcal/mol)" >> "$rp"

    # Generates the headers where the TOTAL RESULTS for each of the targets will be recorded:
    echo "" >> "$rt"
    echo "TARGET","$nP" >> "$rt"
    echo "LIGAND,BINDING ENERGY(Kcal/mol)" >> "$rt"

    ((target_account++)) # Adds 1 more to the target count

    # 2nd FOR Loop goes through each subfolder, with the ligand database, within the LIGANTES folder:
    for L in "$ligands/"*/; do
        nL=$(basename "$L")

        # Start of the split time counter for the ligand group:
        start_time_P=$(date +%s)
              
        # Generates the headers where the LIGAND GROUPS will be recorded in the performance file:       
        echo "                                                                                        " >> "$dp"
        echo "----------------------------------------------------------------------------------------" >> "$dp"
        echo "/////////////////////////////FROM LIGAND DATABANK: $nL://///////////////////////////////" >> "$dp"
        echo "----------------------------------------------------------------------------------------" >> "$dp"
        echo "                                                                                        " >> "$dp"

        # Generates the headers where the LIGAND GROUPS will be recorded in the partial results file:
        echo "" >> "$rp"
        echo "LIGAND DATABANK","$nL" >> "$rp"
        account_ligands=0
        # 3rd FOR Loop executes docking on each .pdbqt ligand present in the subfolder:
        for l in "$L"*.pdbqt; do
            nl=$(basename "$l" .pdbqt)
            echo "//////////////////////////////////////////////////////////////////////////////////////"
            echo "/                          Performing the ligand docking $nl                         /"
            echo "//////////////////////////////////////////////////////////////////////////////////////"
            mkdir "$RR/$nP/$nL/$nl"
            vina_1.2.5_linux_x86_64 --center_x $c_x --center_y $c_y --center_z $c_z --size_x $s_x --size_y $s_y --size_z $s_z --scoring "$sf" --cpu $cpu --exhaustiveness $ext --num_modes $num_modes --min_rmsd $min_rmsd --energy_range $energy_range --spacing $spacing --ligand "$l" --receptor $p --out "$RR/$nP/$nL/$nl/$nl.pdbqt" &
            ((account_ligands++))
            if ((account_ligands % 10 == 0)); then  # Check if 10 ligands have been processed
                wait  # Wait for all background processes to finish          
            fi
        done
        wait
        for s in "$RR/$nP/$nL/"*/; do
            b=$(basename "$s")
            echo "//////////////////////////////////////////////////////////////////////////////////////"
            echo "/                             Performing the ligand split $b                         /"
            echo "//////////////////////////////////////////////////////////////////////////////////////"
            if [ -f "$RR/$nP/$nL/$b/$b.pdbqt" ]; then
                # Decomposes each $nl.pdbqt output result into the pose files:           
                vina_split_1.2.5_linux_x86_64 --input "$RR/$nP/$nL/$b/$b.pdbqt"
                # Extracts the numeric value from row 2 and columns 24 to 30 of the out.pdbqt file
                e=$(awk 'NR==2 {print substr($0, 24, 6)}' "$RR/$nP/$nL/$b/$b.pdbqt")
                # Saves the ligand name and binding energy to the result file:
                echo "$b","$e" >> "$rp"
                echo "$b","$e" >> "$rt"
            fi
            cp "$p" "$RR/$nP/$nL/$b"
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
        echo "                        Elapsed time: $partial_time seconds                               " >> "$dp"
        echo "      Elapsed time: $days Days : $hours hours : $minutes minutes : $seconds seconds       " >> "$dp"
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

echo "##################################################################################################" >> "$dt"
echo "#                                 CODOC VERSION 1.0.0:                                           #" >> "$dt"
echo "#                         Developed by Moisés Maia Neto - 05/2024                                #" >> "$dt"
echo "##################################################################################################" >> "$dt"
echo "                                                                                                  " >> "$dt"
echo "                                                                                                  " >> "$dt"
echo "                          WERE PROCESSED $target_account targets:                                 " >> "$dt"
echo "                                                                                                  " >> "$dt"
echo "                                                                                                  " >> "$dt"
echo "                          Total elapsed time: $total_time seconds                                 " >> "$dt"
echo "      Total elapsed time: $days Days : $hours hours : $minutes minutes : $seconds seconds         " >> "$dt"
echo "                                                                                                  " >> "$dt"
echo "°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°" >> "$dt"
dialog --title "ATTENTION" --msgbox "RIGID DOCKING IS OVER! CHECK THE RESULTADOS_RIGIDO_"$current_date" FOLDER" 10 60
show_main_menu
}


#################################################################################################################################
#                                       FUNÇÃO PARA EXECUTAR O DOCKING FLEXÍVEL:                                                #
#################################################################################################################################
run_flexible_docking() {
dialog --title "ATTENTION" --msgbox "ATENÇÃO! CONFIRA NA PASTA TARGETS OS ARQUIVOS: protein_rigid.pdbqt, protein_flex.pdbqt e grid.txt." 10 60  ;
# Updating docking parameters according to user choices:
data="$HOME/MGLTools-1.5.7/doc/.form_data.txt"
sf="$(sed -n '1p' $data)"
cpu="$(sed -n '2p' $data)"
ext="$(sed -n '3p' $data)"
num_modes="$(sed -n '4p' $data)"
min_rmsd="$(sed -n '5p' $data)"
energy_range="$(sed -n '6p' $data)"
spacing="$(sed -n '7p' $data)"
pH="$(sed -n '8p' $data)"

# Creates the folder where all docking results and performance will be saved:
mkdir "$doc"/FLEXIBLE_DOCKING_RESULT_"$current_date"

# Generates subfolders in the RIGID_DOCKING_RESULT_"$current_date" folder corresponding to the targets:
rsync -av --include=*/ --exclude=* $targets/* $RF

# Start of the total time counter and processed targets:
target_account=0 
start_time_total=$(date +%s)

# Creates files where all docking results and total performance will be saved:
rt=$RF/TOTAL_RESULT_FLEXIBLE_DOCKING_"$current_date".csv && touch "$rt"
dt=$RF/TOTAL_PERFORMANCE_FLEXIBLE_DOCKING_"$current_date".txt && touch "$dt"

# 1st FOR Loop enters each protein folder present in the TARGETS folder, assigns the GridBox parameters, and copies the ligand group directories to the RIGID_DOCKING_RESULT_"$current_date" folder:
for P in "$targets/"*/; do
    nP=$(basename "$P")
    pR="$targets/$nP/protein_rigid.pdbqt"
    pF="$targets/$nP/protein_flex.pdbqt"

    # Create subfolders for each group of ligands in the targets folder present in RESULTS:
    rsync -av --include=*/ --exclude=* "$ligands"/* "$RF"/"$nP"

    # Creates files where all partial docking results and performance for each target will be stargets:
    rp=$RF/"$nP"/FLEXIBLE_DOCKING_RESULT_"$nP"_"$current_date".csv && touch "$rp"
    dp=$RF/"$nP"/FLEXIBLE_DOCKING_PERFORMANCE_"$nP"_"$current_date".txt && touch "$dp"
    
    # Checks if the grid.txt file exists in the $targets/$nP folder
    if [ -f "$targets/$nP/grid.txt" ]; then
        # If the file exists, it updates the Grid Box parameters:
        grid=/$targets/$nP/grid.txt
        c_x=$(awk 'NR==4 {print substr($0, 11, 7)}' "$grid")
        c_y=$(awk 'NR==4 {print substr($0, 19, 7)}' "$grid")
        c_z=$(awk 'NR==4 {print substr($0, 27, 7)}' "$grid")
        s_x=$(awk 'NR==3 {print substr($0, 12, 2)}' "$grid")
        s_y=$(awk 'NR==3 {print substr($0, 15, 2)}' "$grid")
        s_z=$(awk 'NR==3 {print substr($0, 18, 2)}' "$grid")
    else
        dialog --title "ATTENTION" --msgbox " The grid.txt file was not found in the $targets/$nP folder. Generate the text file named as grid.txt in ADT and save it in the $targets/$nP folder." 10 60  ;
        if [ -f "$targets/$nP/grid.txt" ]; then
            # If the file exists, it updates the Grid Box parameters:
            grid=/$targets/$nP/grid.txt
            c_x=$(awk 'NR==4 {print substr($0, 11, 7)}' "$grid")
            c_y=$(awk 'NR==4 {print substr($0, 19, 7)}' "$grid")
            c_z=$(awk 'NR==4 {print substr($0, 27, 7)}' "$grid")
            s_x=$(awk 'NR==3 {print substr($0, 12, 2)}' "$grid")
            s_y=$(awk 'NR==3 {print substr($0, 15, 2)}' "$grid")
            s_z=$(awk 'NR==3 {print substr($0, 18, 2)}' "$grid")
        else
            dialog --title "ATTENTION" --msgbox " The grid.txt file is STILL MISSING in the $targets/$nP folder. Correct and Restart the process" 10 60;
            break
        fi
    fi

    #  Generates the headers where PARTIAL PERFORMANCES will be recorded in each of the targets:
    echo "########################################################################################" >> "$dp"
    echo "#                                 CODOC VERSION 1.0.0:                                 #" >> "$dp"
    echo "#                         Developed by Moisés Maia Neto - 05/2024                      #" >> "$dp"
    echo "########################################################################################" >> "$dp"
    echo "                                                                                        " >> "$dp"
    echo "########################################################################################" >> "$dp"
    echo "#                                 FROM TARGET: $nP                                     #" >> "$dp"
    echo "########################################################################################" >> "$dp"
    echo "                                                                                        " >> "$dp"

    # Generates the headers where the PARTIAL RESULTS will be recorded in each of the targets:
    echo "" >> "$rp"
    echo "TARGET","$nP" >> "$rp"
    echo "LIGAND,BINDING ENERGY(Kcal/mol)" >> "$rp"

    # Generates the headers where the TOTAL RESULTS for each of the targets will be recorded:
    echo "" >> "$rt"
    echo "TARGET","$nP" >> "$rt"
    echo "LIGAND,BINDING ENERGY(Kcal/mol)" >> "$rt"

    ((target_account++)) # Adds 1 more to the target count

    # 2nd FOR Loop goes through each subfolder, with the ligand database, within the LIGANTES folder:
    for L in "$ligands/"*/; do
        nL=$(basename "$L")

        # Start of the split time counter for the ligand group:
        start_time_P=$(date +%s)
              
        # Generates the headers where the LIGAND GROUPS will be recorded in the performance file:       
        echo "                                                                                        " >> "$dp"
        echo "----------------------------------------------------------------------------------------" >> "$dp"
        echo "/////////////////////////////FROM LIGAND DATABANK: $nL://///////////////////////////////" >> "$dp"
        echo "----------------------------------------------------------------------------------------" >> "$dp"
        echo "                                                                                        " >> "$dp"

        # Generates the headers where the LIGAND GROUPS will be recorded in the partial results file:
        echo "" >> "$rp"
        echo "LIGAND DATABANK","$nL" >> "$rp"
        account_ligands=0
        # 3rd FOR Loop executes docking on each .pdbqt ligand present in the subfolder:
        for l in "$L"*.pdbqt; do
            nl=$(basename "$l" .pdbqt)
            echo "//////////////////////////////////////////////////////////////////////////////////////"
            echo "/                          Performing the ligand docking $nl                         /"
            echo "//////////////////////////////////////////////////////////////////////////////////////"
            mkdir "$RF/$nP/$nL/$nl"
            vina_1.2.5_linux_x86_64 --center_x $c_x --center_y $c_y --center_z $c_z --size_x $s_x --size_y $s_y --size_z $s_z --scoring "$sf" --cpu $cpu --exhaustiveness $ext --num_modes $num_modes --min_rmsd $min_rmsd --energy_range $energy_range --spacing $spacing --ligand "$l" --receptor $pR --flex $pF --out "$RF/$nP/$nL/$nl/$nl.pdbqt" &
            ((account_ligands++))
            if ((account_ligands % 10 == 0)); then  # Check if 10 ligands have been processed
                wait  # Wait for all background processes to finish          
            fi
        done
        wait
        for s in "$RF/$nP/$nL/"*/; do
            b=$(basename "$s")
            echo "//////////////////////////////////////////////////////////////////////////////////////"
            echo "/                             Performing the ligand split $b                         /"
            echo "//////////////////////////////////////////////////////////////////////////////////////"
            if [ -f "$RF/$nP/$nL/$b/$b.pdbqt" ]; then
                # Decomposes each $nl.pdbqt output result into the pose files:           
                vina_split_1.2.5_linux_x86_64 --input "$RF/$nP/$nL/$b/$b.pdbqt"
                # Extracts the numeric value from row 2 and columns 24 to 30 of the out.pdbqt file
                e=$(awk 'NR==2 {print substr($0, 24, 6)}' "$RF/$nP/$nL/$b/$b.pdbqt")
                # Saves the ligand name and binding energy to the result file:
                echo "$b","$e" >> "$rp"
                echo "$b","$e" >> "$rt"
            fi
            cp "$pR" "$RF/$nP/$nL/$b"
            cp "$pF" "$RF/$nP/$nL/$b"
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
        echo "                        Elapsed time: $partial_time seconds                               " >> "$dp"
        echo "      Elapsed time: $days Days : $hours hours : $minutes minutes : $seconds seconds       " >> "$dp"
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

echo "##################################################################################################" >> "$dt"
echo "#                                 CODOC VERSION 1.0.0:                                           #" >> "$dt"
echo "#                         Developed by Moisés Maia Neto - 05/2024                                #" >> "$dt"
echo "##################################################################################################" >> "$dt"
echo "                                                                                                  " >> "$dt"
echo "                                                                                                  " >> "$dt"
echo "                          WERE PROCESSED $target_account targets:                                 " >> "$dt"
echo "                                                                                                  " >> "$dt"
echo "                                                                                                  " >> "$dt"
echo "                          Total elapsed time: $total_time seconds                                 " >> "$dt"
echo "      Total elapsed time: $days Days : $hours hours : $minutes minutes : $seconds seconds         " >> "$dt"
echo "                                                                                                  " >> "$dt"
echo "°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°" >> "$dt"
dialog --title "ATTENTION" --msgbox "FLEXIBLE DOCKING IS OVER! CHECK THE FLEXIBLE_DOCKING_RESULT_"$current_date" FOLDER" 10 60
show_main_menu
}

#################################################################################################################################
#                                       FUNCTION FOR REMOVING PARAMETER FILES:                                                  #
#################################################################################################################################

#Função de acesso global para remoção de parâmetros:
remove_parameters() {
rm /$HOME/MGLTools-1.5.7/doc/.form_data.txt
rm /$HOME/MGLTools-1.5.7/doc/.menu_escolha.txt
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

