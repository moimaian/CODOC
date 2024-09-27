import argparse
import os
import sys
import re
import time
import rdkit.Chem as Chem
from pathlib import Path
import pandas as pd
from rdkit.Chem import PandasTools
from rdkit.Chem import Descriptors
from rdkit.Chem import rdMolDescriptors
from rdkit.Chem.SaltRemover import SaltRemover
import rdkit.Chem.Draw as Draw
import rdkit.Chem.AllChem as AllChem
from rdkit.Chem import rdDistGeom
from dimorphite_dl import DimorphiteDL
import numpy as np
import contextlib
import io
from tqdm import tqdm
from datetime import timedelta
import warnings
from meeko import MoleculePreparation
from meeko import PDBQTWriterLegacy
import concurrent.futures
pd.options.mode.copy_on_write = True
original_stderr = sys.stderr

 
parser = argparse.ArgumentParser(description='Preparation of ligands for docking',
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument("-c", "--codoc", action="store_true", help="For integrated use with CODOC")
#parser.add_argument("-v", "--verbose", action="store_true", help="increase verbosity")
#parser.add_argument("-B", "--block-size", help="checksum blocksize")
parser.add_argument("--overwrite", action="store_true", help="Overwrite existing files")
parser.add_argument('--ph', type=float, help="pH for protonation of molecules")
parser.add_argument('--mw_min', type=float, help="Minimum Molecular Weight (Filter)")
parser.add_argument('--mw_max', type=float, help="Maximum Molecular Weight (Filter)")
parser.add_argument('--logp_min', type=float, help="Minimum LogP (Filter)")
parser.add_argument('--logp_max', type=float, help="Maximum LogP (Filter)")
parser.add_argument('--rotB_min', type=float, help="Minimum Num. Rotatable Bonds (Filter)")
parser.add_argument('--rotB_max', type=float, help="Maximum Num. Rotatable Bonds (Filter)")
parser.add_argument('--hba_min', type=float, help="Minimum Lipinski H-bond acceptors (Filter)")
parser.add_argument('--hba_max', type=float, help="Maximum Lipinski H-bond acceptors (Filter)")
parser.add_argument('--hbd_min', type=float, help="Minimum Lipinski H-bond donors (Filter)")
parser.add_argument('--hbd_max', type=float, help="Maximum Lipinski H-bond donors (Filter)")
parser.add_argument('--tpsa_min', type=float, help="Minimum Topological Polar Surface Area (Filter)")
parser.add_argument('--tpsa_max', type=float, help="Maximum Topological Polar Surface Area (Filter)")
parser.add_argument("inp", help="Input dataset file (csv, smi, or sdf)")
args = parser.parse_args()
config = vars(args)

print(r"""
    *******************************************
    *  ____       ____            _____ ____  *
    * / ___|___  / ___| ___ _ __ |___ /|  _ \ *
    *| |   / _ \| |  _ / _ \ '_ \  |_ \| | | |*
    *| |__| (_) | |_| |  __/ | | |___) | |_| |*
    * \____\___/ \____|\___|_| |_|____/|____/ *
    *******************************************
""")

def main(dataset,parent_path):
    global performance
    global count_m
    global perf_pdbqt
    global perf_3d
    global start
    global stop

    start = time.time()
    dataset_path=Path(dataset).absolute()
    dataset_name=Path(dataset).absolute().stem
    fileType=Path(dataset).suffix.replace('.','')

    global df_mol_essential

    with open(dataset_path, 'r') as ln:
        if fileType=='sdf':
            countl=-1
            for line in ln:
                if re.search(r'\bEND\b', line):
                    countl+=1
        else:
            for countl, line in enumerate(ln):
                pass
    count_m.append(countl+1)
    print('Converting:', dataset_name, 'in', dataset_path, 'containing', countl+1,'entries')
    time.sleep(2)

    def detect_separator(dataset_path):
        # Read the first line of the file
        with open(dataset_path, 'r') as file:
            first_line = file.readline()
        
        # Define possible separators
        possible_separators = [';', '\t', ',', ' ']
        
        # Check for the presence of each separator
        for sep in possible_separators:
            if sep == ' ':
                # Check for one or more spaces
                if re.search(r'\s{2,}', first_line):
                    separator = ' ' * len(re.search(r'\s{2,}', first_line).group(0))
                    break
            elif sep in first_line:
                separator = sep
                break
        else:
            separator = None  # No separator found
        
        return separator
        
    separator = detect_separator(dataset_path)
    print(f"The detected separator is: '{separator}'")
    
    def importDataset(dataset):
        if fileType=='smi':
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', category=Warning)
                df_mol = pd.read_csv(dataset_path, sep=separator, names=['Smiles','Name'], index_col=False, engine='python')
        elif fileType=='csv':
            df_mol = pd.read_csv(dataset_path, sep=separator, usecols=['Smiles','Name'], engine='python')
        elif fileType=='sdf':
            df_mol = pd.DataFrame()
            sdName=[]
            sdSmiles=[]
            for msdf in Chem.SDMolSupplier(dataset, removeHs=True):
                sdName.append(msdf.GetProp('_Name'))
                sdSmiles.append(Chem.MolToSmiles(msdf))
            df_mol['Smiles']=sdSmiles
            df_mol['Name']=sdName
            
        else:
            df_mol = pd.read_csv(dataset_path, sep=separator, engine='python')
            
        print("=============================="+dataset_name+"==============================")
        print(df_mol.head())
        print('...')
        time.sleep(3)
        return df_mol
    
    df_mol=importDataset(dataset)
    if parent_path.joinpath('ERRORS').is_dir()==False:      				Path.mkdir(parent_path.joinpath('ERRORS'))    
    
    def datasetCleanup(df_mol,columnSmiles,columnName):
        df_mol_essential=df_mol[[columnSmiles,columnName]].copy(deep=False)
        df_mol_essential=df_mol_essential.drop(df_mol_essential[df_mol_essential['Smiles'].isnull()].index).reset_index(drop=True) #remove null values
        df_mol_essential=df_mol_essential[df_mol_essential['Smiles']!=''].reset_index(drop=True)
        df_mol_essential['Smiles']=df_mol_essential['Smiles'].astype(str)
        print('Null values removed: '+ str((len(df_mol)-len(df_mol_essential))))
        errorl_smi=[]
        errorl_idx=[]
        for idx, m in enumerate(df_mol_essential['Smiles']):
            if Chem.MolFromSmiles(m) is None:
                errorl_idx.append(idx)
                errorl_smi.append(m)
        if len(errorl_idx)>0:
            print('Could not read SMILES from '+str(len(errorl_idx))+' entries. Check '+dataset_name+'_log_error_smi.txt')
            df_mol_essential.drop(errorl_idx, axis=0, inplace=True)
            df_mol_essential=df_mol_essential.reset_index(drop=True)
            with open (parent_path.joinpath('ERRORS',dataset_name+'_log_error_smi.txt'),'w') as ersmi:
                ersmi.write("Following SMILES were dropped: \n")
                for er in errorl_smi:
                    ersmi.write(er+'\n')
        return df_mol_essential
        
    df_mol_essential=datasetCleanup(df_mol,'Smiles','Name')

    def duplRemoval():
        print("Removing duplicated SMILES...")
        global df_mol_essential
        df_mol_essential=df_mol_essential.drop(df_mol_essential[df_mol_essential.duplicated('Smiles', keep='first')].index)
        df_mol_essential=df_mol_essential.reset_index(drop=True)
        print("Duplicates removed!")
        time.sleep(0.5)

    duplRemoval()

    overwrite_op=config['overwrite']
    if overwrite_op==False:
        overwrite_op='n'
    else:
        print('Overwrite mode ON')
        overwrite_op='y'
    
    filenames = []
    
    if config['codoc']==True:
        directory = parent_path.joinpath('LIGANDS',dataset_dir)
    else:
        directory = parent_path.joinpath('pdbqt')
    if os.path.isdir(directory)==True:    
        for filename in os.listdir(directory):
            if filename.endswith(".pdbqt"):
                filenames.append(filename.replace('.pdbqt','').replace('/','').replace(':','x'))
                continue
            else:
                continue
        if len(filenames)!=0:
            print(len(filenames),'converted molecules in', directory,'skipping...')
        else:
            print(str(directory)+' is empty')

    df_mol_essential=df_mol_essential[~df_mol_essential['Name'].isin(filenames)]
    
    remover = SaltRemover()
    
    def remSalt(idx, smiles, name):
        error_message = []
        try:
            desalted_mol = remover.StripMol(Chem.MolFromSmiles(smiles))
            desalted = Chem.MolToSmiles(desalted_mol)
        except:
            desalted = "ERR"
            error_message.append('Error desalting: '+name+' '+smiles)
        return idx, desalted, error_message
    print()   
    print("Removing salts...")
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = []
        for idx, row in df_mol_essential.iterrows():
            futures.append(executor.submit(remSalt, idx, row['Smiles'], row['Name']))
    
        for future in tqdm(concurrent.futures.as_completed(futures), total=len(futures)):
            try:
                idx, desalted_molecule, error_message = future.result()
                df_mol_essential.loc[idx, 'Smiles'] = desalted_molecule
                if error_message:
                    print(error_message)
            except Exception as e:
                print(f"Error processing future: {e}")

    print('Salts removed!')
    time.sleep(1)

    duplRemoval()
    
    def descriptorCalc(idx,smiles,name):
        global df_mol_essential
    
        if Chem.MolFromSmiles(smiles)!=None:
            MW = Descriptors.MolWt(Chem.MolFromSmiles(smiles))
            LogP=Chem.Crippen.MolLogP(Chem.MolFromSmiles(smiles))
            numRot=rdMolDescriptors.CalcNumRotatableBonds(Chem.MolFromSmiles(smiles))
            numHAc=rdMolDescriptors.CalcNumLipinskiHBA(Chem.MolFromSmiles(smiles))
            numHDon=rdMolDescriptors.CalcNumLipinskiHBD(Chem.MolFromSmiles(smiles))
            TPSA=rdMolDescriptors.CalcTPSA(Chem.MolFromSmiles(smiles))
            error_idx=None
            error_smi=None
                
        else:
            MW=-1
            LogP=-1
            numRot=-1
            numHAc=-1
            numHDon=-1
            TPSA=-1
            error_idx=idx
            error_smi=smiles
    
        return idx, MW, LogP, numRot, numHAc, numHDon, TPSA, error_idx, error_smi
    
    print("Calculating molecular descriptors...")
    errorl_idx=[]
    errorl_smi=[]
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = []
        for idx, row in df_mol_essential.iterrows():
            futures.append(executor.submit(descriptorCalc, idx, row['Smiles'], row['Name']))
    
        for future in tqdm(concurrent.futures.as_completed(futures), total=len(futures)):
            try:
                idx, MW, LogP, numRot, numHAc, numHDon, TPSA, error_idx, error_smi = future.result()
                df_mol_essential.loc[idx, 'MW']=MW
                df_mol_essential.loc[idx, 'LogP']=LogP
                df_mol_essential.loc[idx, 'numRot']=numRot
                df_mol_essential.loc[idx, 'HBA']=numHAc
                df_mol_essential.loc[idx, 'HBD']=numHDon
                df_mol_essential.loc[idx, 'TPSA']=TPSA
    
                if error_idx is not None:
                    errorl_idx.append(error_idx)
                    errorl_smi.append(error_smi)
    
            except Exception as e:
                print(f"Error processing future: {e}")
                
        if len(errorl_idx)>0:
            print('Could not read SMILES from '+str(len(errorl_idx))+' entries. Check '+dataset_name+'_log_error_smi.txt')
            df_mol_essential.drop(errorl_idx, axis=0, inplace=True)
            df_mol_essential=df_mol_essential.reset_index(drop=True)
            with open (parent_path.joinpath(dataset_name+'_log_error_smi.txt'),'w') as ersmi:
                ersmi.write("Following SMILES were dropped: \n")
                for er in errorl_smi:
                    ersmi.write(er+'\n')
                    
    df_mol_essential['numRot']=df_mol_essential['numRot'].astype(int)
    df_mol_essential['HBA']=df_mol_essential['HBA'].astype(int)
    df_mol_essential['HBD']=df_mol_essential['HBD'].astype(int)

    def filter_MW(min_mw, max_mw):
        global df_mol_essential
        print('Dropping '+str(len(df_mol_essential[~df_mol_essential['MW'].between(min_mw,max_mw)]))+' molecules out of Mol. Weight range...')
        print(str(len(df_mol_essential[df_mol_essential['MW'].between(min_mw,max_mw)]))+' molecules remaining...')        
        time.sleep(2)
        df_mol_essential=df_mol_essential[df_mol_essential['MW'].between(min_mw,max_mw)].reset_index(drop=True)

    def filter_logp(min_logp, max_logp):
        global df_mol_essential
        print('Dropping '+str(len(df_mol_essential[~df_mol_essential['LogP'].between(min_logp, max_logp)]))+' molecules out of LogP range...')
        print(str(len(df_mol_essential[df_mol_essential['LogP'].between(min_logp, max_logp)]))+' molecules remaining...')
        time.sleep(2)
        df_mol_essential=df_mol_essential[df_mol_essential['LogP'].between(min_logp, max_logp)].reset_index(drop=True)

    def filter_rotB(min_rotB, max_rotB):
        global df_mol_essential
        print('Dropping '+str(len(df_mol_essential[~df_mol_essential['numRot'].between(min_rotB, max_rotB)]))+' molecules out of rotatable bonds range...')
        print(str(len(df_mol_essential[df_mol_essential['numRot'].between(min_rotB, max_rotB)]))+' molecules remaining...')
        time.sleep(2)
        df_mol_essential=df_mol_essential[df_mol_essential['numRot'].between(min_rotB, max_rotB)].reset_index(drop=True)

    def filter_HBA(min_hba, max_hba):
        global df_mol_essential
        print('Dropping '+str(len(df_mol_essential[~df_mol_essential['HBA'].between(min_hba, max_hba)]))+' molecules out of HBA range...')
        print(str(len(df_mol_essential[df_mol_essential['HBA'].between(min_hba, max_hba)]))+' molecules remaining...')
        time.sleep(2)
        df_mol_essential = df_mol_essential[df_mol_essential['HBA'].between(min_hba, max_hba)].reset_index(drop=True)
    
    def filter_HBD(min_hbd, max_hbd):
        global df_mol_essential
        print('Dropping '+str(len(df_mol_essential[~df_mol_essential['HBD'].between(min_hbd, max_hbd)]))+' molecules out of HBD range...')
        print(str(len(df_mol_essential[df_mol_essential['HBD'].between(min_hbd, max_hbd)]))+' molecules remaining...')
        time.sleep(2)
        df_mol_essential = df_mol_essential[df_mol_essential['HBD'].between(min_hbd, max_hbd)].reset_index(drop=True)

    def filter_TPSA(min_tpsa, max_tpsa):
        global df_mol_essential
        print('Dropping ' + str(len(df_mol_essential[~df_mol_essential['TPSA'].between(min_tpsa, max_tpsa)])) + ' molecules out of TPSA range...')
        print(str(len(df_mol_essential[df_mol_essential['TPSA'].between(min_tpsa, max_tpsa)]))+' molecules remaining...')
        time.sleep(2)
        df_mol_essential = df_mol_essential[df_mol_essential['TPSA'].between(min_tpsa, max_tpsa)].reset_index(drop=True)

    
    if config['mw_min'] is not None or config['mw_max'] is not None:
        if config['mw_max'] is None:
            config['mw_max'] = df_mol_essential['MW'].max()
        if config['mw_min'] is None:
            config['mw_min'] = df_mol_essential['MW'].min()
        filter_MW(config['mw_min'], config['mw_max'])
    
    if config['logp_min'] is not None or config['logp_max'] is not None:
        if config['logp_max'] is None:
            config['logp_max'] = df_mol_essential['LogP'].max()
        if config['logp_min'] is None:
            config['logp_min'] = df_mol_essential['LogP'].min()
        filter_logp(config['logp_min'], config['logp_max'])
    
    if config['rotB_min'] is not None or config['rotB_max'] is not None:
        if config['rotB_max'] is None:
            config['rotB_max'] = df_mol_essential['numRot'].max()
        if config['rotB_min'] is None:
            config['rotB_min'] = df_mol_essential['numRot'].min()
        filter_rotB(config['rotB_min'], config['rotB_max'])
    
    if config['hba_min'] is not None or config['hba_max'] is not None:
        if config['hba_max'] is None:
            config['hba_max'] = df_mol_essential['HBA'].max()
        if config['hba_min'] is None:
            config['hba_min'] = df_mol_essential['HBA'].min()
        filter_HBA(config['hba_min'], config['hba_max'])
    
    if config['hbd_min'] is not None or config['hbd_max'] is not None:
        if config['hbd_max'] is None:
            config['hbd_max'] = df_mol_essential['HBD'].max()
        if config['hbd_min'] is None:
            config['hbd_min'] = df_mol_essential['HBD'].min()
        filter_HBD(config['hbd_min'], config['hbd_max'])

    if config['tpsa_min'] is not None or config['tpsa_max'] is not None:
        if config['tpsa_max'] is None:
            config['tpsa_max'] = df_mol_essential['TPSA'].max()
        if config['tpsa_min'] is None:
            config['tpsa_min'] = df_mol_essential['TPSA'].min()
        filter_TPSA(config['tpsa_min'], config['tpsa_max'])
        
    time.sleep(1)
    
    df_mol_essential=df_mol_essential[df_mol_essential['Smiles']!=''].reset_index(drop=True)
    
    df_mol_essential['Name']=df_mol_essential['Name'].astype(str)
    
    duplRemoval()
    
    global max_ph

    def suppress_stderr():
        return contextlib.redirect_stderr(io.StringIO())

    def unsupress_stderr():
        sys.stderr = original_stderr
    def protMol(idx, smiles):
        with suppress_stderr():
            try:
                dimorphite_dl = DimorphiteDL(
                min_ph=max_ph,
                max_ph=max_ph,
                max_variants=1,
                label_states=False,
                pka_precision=0.1
                )
                protonated=dimorphite_dl.protonate(smiles)[0]
                unsupress_stderr()
            except:
                return None
        return idx, protonated

    print('Assigning protonation state at pH '+str(max_ph))
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = []
        for idx, row in df_mol_essential.iterrows():
            futures.append(executor.submit(protMol, idx, row['Smiles']))
            unsupress_stderr()
        for future in tqdm(concurrent.futures.as_completed(futures), total=len(futures)):
            try:
                idx, protonated_mol = future.result()
                df_mol_essential.loc[idx, 'Smiles'] = protonated_mol
            except Exception as e:
                print(f"Error processing future: {e}")
    
    print('Protonation completed!')
    time.sleep(1)

    unsupress_stderr()
    
    duplRemoval()
    
    def create_mol_col():
        global df_mol_essential
        PandasTools.AddMoleculeColumnToFrame(df_mol_essential,'Smiles','Molecule', includeFingerprints=True)
    
    create_mol_col()
    
    def rename_duplicates(df, column_name):
        # Create a dictionary to store the count of occurrences of each name
        name_count = {}
        
        # List to store the new names
        new_names = []
        names_replaced = 0
        
        for name in df[column_name]:
            if name in name_count:
                # Increment the count and rename the duplicate
                name_count[name] += 1
                new_name = f"{name}_{name_count[name]}"
                names_replaced += 1
            else:
                # Initialize the count for the new name
                name_count[name] = 0
                new_name = name
            
            # Add the new name to the list
            new_names.append(new_name)
        
        # Assign the new names to the column
        df[column_name] = new_names
        return print('Duplicated names replaced: '+str(names_replaced))
    
    rename_duplicates(df_mol_essential, 'Name')
    
    warnings.simplefilter("ignore")
    # Função que executa a otimização de uma molécula
    def optimize_molecule(idx, molecule, name):
        error_message = None
        molecule=Chem.AddHs(molecule)
        try:
            ps = rdDistGeom.ETKDGv3()
            ps.trackFailures = True
            ps.maxIterations=molecule.GetNumAtoms()*3
            ps.useRandomCoords = True
            rdDistGeom.EmbedMolecule(molecule,ps)
            AllChem.MMFFOptimizeMolecule(molecule, maxIters=100)
        except ValueError:
            try:
                print(f'Failed generating 3D conformer for {name}, trying distance geometry method (ETDG)...')
                ps = rdDistGeom.ETDG()
                ps.trackFailures = True
                ps.maxIterations=molecule.GetNumAtoms()*10
                ps.useRandomCoords = True
                rdDistGeom.EmbedMolecule(molecule,ps)
                AllChem.MMFFOptimizeMolecule(molecule, maxIters=10000)
            except ValueError as e:
                error_message = name
        return idx, molecule, error_message
    
    # Coleta de erros
    error_emb = []
    unsupress_stderr()
    # Usando ThreadPoolExecutor para paralelizar a otimização das moléculas
            
    print("Initializing 3D conformer generation...")
    time_start = time.time()
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = []
        for idx, row in df_mol_essential.iterrows():
            futures.append(executor.submit(optimize_molecule, idx, row['Molecule'], row['Name']))
                
        for future in tqdm(concurrent.futures.as_completed(futures), total=len(futures)):
            try:
                idx, optimized_molecule, error_message = future.result()
                df_mol_essential.loc[idx, 'Molecule'] = optimized_molecule
                if error_message:
                    error_emb.append(error_message)
            except Exception as e:
                print(f"Error processing future: {e}")
    if parent_path.joinpath('ERRORS').is_dir()==False:            
        Path.mkdir(parent_path.joinpath('ERRORS'))               
    erf=open(parent_path.joinpath('ERRORS',(dataset_name+'_log_error_3d_gen.txt')),'w')
    if len(error_emb)>0:
        erf.write('Unable to generate 3D conformations for the following '+str(len(error_emb))+' molecules:\n')
        with open(parent_path.joinpath('ERRORS',dataset_name+'_log_error_3d_gen.txt'),'a'):
            for er in error_emb:
                erf.write(er+'\n')
        erf.close()
    elif len(error_emb)==0:
        erf.write('No errors detected in 3D conformer generation')
        erf.close()
    time_stop = time.time()
    time_3d = (time_stop-time_start)
    perf_3d.append(time_3d)
    
    # remove unsuccesful molecules
    def save_csvs():
        global df_mol_error3d,df_mol_essential
        df_mol_error3d=df_mol_essential[df_mol_essential['Name'].isin(error_emb)]
        df_mol_essential=df_mol_essential[~df_mol_essential['Name'].isin(error_emb)]
        df_mol_error3d=df_mol_error3d.reset_index(drop=True)
        df_mol_essential=df_mol_essential.reset_index(drop=True)
        if parent_path.joinpath('CSV').is_dir()==False:
            Path.mkdir(parent_path.joinpath('CSV'))
        df_mol_essential.to_csv(parent_path.joinpath('CSV',(dataset_name+'_processed.csv')), columns=['Smiles','Name','MW','LogP','numRot','HBA','HBD','TPSA'], index=0, sep=';')
        if len(df_mol_error3d)>0:
            for idx, me in enumerate(df_mol_error3d['Molecule']):
                AllChem.Compute2DCoords(me)
                df_mol_error3d.loc[idx, 'Molecule']=Chem.RemoveHs(me)
            Chem.PandasTools.SaveXlsxFromFrame(df_mol_error3d, parent_path.joinpath('CSV',(dataset_name+'_error3Dgen.xlsx')), molCol='Molecule', size=(250,250), formats=None)
            df_mol_error3d.to_csv(parent_path.joinpath('CSV',(dataset_name+'_error3Dgen.csv')), columns=['Smiles','Name','MW','LogP','numRot','HBA','HBD','TPSA'], index=0,  sep=';')
    
    save_csvs()
    
    
    if parent_path.joinpath('SDF').is_dir()==False:
        Path.mkdir(parent_path.joinpath('SDF'), parents=True)
    PandasTools.WriteSDF(df_mol_essential, parent_path.joinpath('SDF', (dataset_name+'.sdf')), molColName='Molecule', idName='Name')
    print(len(df_mol_essential['Smiles']),"molecules were saved")
    
    filenames = []
    if config['codoc']==True:
        directory = parent_path.joinpath('LIGANDS',dataset_dir)
    else:
        directory = parent_path.joinpath('pdbqt')
    if os.path.isdir(directory)==True:    
        for filename in os.listdir(directory):
            if filename.endswith(".pdbqt"):
                filenames.append(filename.replace('.pdbqt',''))
                continue
            else:
                continue
        if len(filenames)!=0:
            print(len(filenames),'molecules in', directory)
        else:
            print(str(directory)+' is empty')
    if os.path.isdir(directory)==False:
        print('Target path does not exist, creating...')
        Path.mkdir(directory, parents=True)
        print('Created: '+str(directory))
    
    
    input_molecule_file = parent_path.joinpath('SDF', (dataset_name+'.sdf'))
    output_pdbqt_file = directory
    error_col=[]
    with open(parent_path.joinpath('ERRORS',(dataset_name+'_error_log_pdbqt.txt')), "w") as errorf:
        errorf.write("ERROR LOG:"+'\n')
    
    def pdbqtConv(mol, overwrite_op, filenames, error_col):
        try:
            title = mol.GetProp('_Name').replace('/', '')
            if overwrite_op == 'n' and title in filenames:
                return  # Skip already converted files
            preparator = MoleculePreparation()
            mol_setups = preparator.prepare(mol)
            for setup in mol_setups:
                pdbqt_string = PDBQTWriterLegacy.write_string(setup)
                pdbqt_string = 'REMARK  Name = ' + title + '\n' + pdbqt_string[0]
                output_file = output_pdbqt_file.joinpath(title.replace(':','x') + '.pdbqt')
                with open(output_file, "w") as f:
                    f.write(pdbqt_string)
        except Exception as e:
            with open(parent_path.joinpath('ERRORS', f'{dataset_name}_error_log_pdbqt.txt'), "a") as errorf:
                errorf.write(f"Error converting {title}\n")
                error_col.append(title)
    
    # Use ThreadPoolExecutor for multithreading
    print("Initializing conversion to pdbqt...")
    time_start = time.time()
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = []
        mol_num=len(Chem.SDMolSupplier(input_molecule_file, removeHs=False))
        for mol in tqdm(Chem.SDMolSupplier(input_molecule_file, removeHs=False)):
            if mol is None:
                continue
            futures.append(executor.submit(pdbqtConv, mol, overwrite_op, filenames, error_col))
    
        # Optionally, collect results or handle exceptions
        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"Error processing future: {e}")

    if len(error_col)==0:
        with open(parent_path.joinpath('ERRORS',(dataset_name+'_error_log_pdbqt.txt')), "a") as errorf:
            errorf.write('No errors in pdbqt conversion')
            
    time_stop = time.time()
    time_pdbqt = (time_stop-time_start)
    perf_pdbqt.append(time_pdbqt)
    
    def pdbqt_len(directory,output_pdbqt_file):
        filenames=[]
        for filename in os.listdir(directory):
            if filename.endswith(".pdbqt"):
                filenames.append(filename.replace('.pdbqt',''))
                continue
            else:
                continue
        print(len(filenames),'molecules successfully converted to pdbqt', str(directory))
        
        with open(parent_path.joinpath('ERRORS',(dataset_name+'_error_log_pdbqt.txt')), "r") as errorf:
            print(errorf.read())

    pdbqt_len(directory,output_pdbqt_file)
    
    stop = time.time()
    dif = timedelta(seconds=stop-start)
    
    print(f" Dataset ({dataset_name}) processing took {(dif.days*24+dif.seconds//3600):02d}:{(dif.seconds//60) % 60:02d}:{dif.seconds % 60:02d}")
    print('')
    performance.append(stop-start)

#start script to check if codoc arg is set to true
performance=[]
count_m=[]
perf_pdbqt=[]
perf_3d=[]

if config['codoc']==True:
    if Path.cwd().joinpath('LIGANDS').is_dir()==False:
        print('Directory does not exist, exiting...')
        sys.exit()
    else:
        ligpath=Path.cwd().joinpath('LIGANDS')
        dir_p=Path(ligpath).glob('**/*')
        molfiles=[x for x in dir_p if x.suffix=='.smi' or x.suffix=='.csv' or x.suffix=='.sdf']

#dataset name
if config['ph'] is None:
    print('***** pH is not set, using 7.2 *****')
    print('')
    max_ph=7.2
    time.sleep(1)
    
if config['ph'] is not None:
    if config['ph'] > 0 and config['ph'] < 14:
        max_ph=config['ph']
    else:
        print('Invalid pH, exiting...')
        sys.exit()

if config['codoc']==False:
    print('Initializing...')
    print('')
    dataset=config['inp']
    parent_path=Path(dataset).parent.absolute()
    main(dataset,parent_path)

if config['codoc']==True:
    print(
        r"""                      
      ____ ___  ____   ___   ____  
     / ___/ _ \|  _ \ / _ \ / ___| 
    | |  | | | | | | | | | | |     
    | |__| |_| | |_| | |_| | |___  
     \____\___/|____/ \___/ \____| 
                             MODE       
        """
    )
    
    print(str(len(molfiles))+" datasets were found. Initializing...")
    print('')
    for idx, smi in enumerate(molfiles):
        print(str(idx+1)+'. '+str(Path(smi).name))
    print()
    time.sleep(1)
    for smi in molfiles:
        dataset=smi
        dataset_dir=Path(dataset).stem
        Path.mkdir(Path.cwd().joinpath('LIGANDS', dataset_dir), exist_ok=True)
        parent_path=Path(dataset.parent.absolute()).parent.absolute()
        main(dataset,parent_path)
    total_time=0.0
    for perf in performance:
        total_time=total_time+perf
    total_mol=0
    for ms in count_m:
        total_mol=total_mol+ms
    diftotal = timedelta(seconds=total_time)
    metrics = f"{len(molfiles)} datasets ({total_mol} mols.) processed in {(diftotal.days*24+diftotal.seconds//3600):02d}:{(diftotal.seconds//60) % 60:02d}:{diftotal.seconds % 60:02d} ({total_mol/total_time} mols/s)"
    for idx, perf in enumerate(performance):
        difset = timedelta(seconds=perf)
        dif3d = timedelta(seconds=perf_3d[idx])
        difpdbqt = timedelta(seconds=perf_pdbqt[idx])
        print(f'{Path(molfiles[idx]).name} in {(difset.days*24+difset.seconds//3600):02d}:{(difset.seconds//60) % 60:02d}:{difset.seconds % 60:02d} :: 3D generation in {(dif3d.days*24+dif3d.seconds//3600):02d}:{(dif3d.seconds//60) % 60:02d}:{dif3d.seconds % 60:02d} PDBQT conversion in {(difpdbqt.days*24+difpdbqt.seconds//3600):02d}:{(difpdbqt.seconds//60) % 60:02d}:{difpdbqt.seconds % 60:02d}')
    print(metrics)
    with open(parent_path.joinpath('PERFORMANCE_METRICS.txt'), 'w') as p:
        p.write(metrics + '\n')
        for idx, perf in enumerate(performance):
            difset = timedelta(seconds=perf)
            dif3d = timedelta(seconds=perf_3d[idx])
            difpdbqt = timedelta(seconds=perf_pdbqt[idx])
            p.write(
                f"{Path(molfiles[idx]).name} in {(difset.days*24+difset.seconds//3600):02d}:{(difset.seconds//60) % 60:02d}:{difset.seconds % 60:02d}"
                f" 3D generation in {(dif3d.days*24+dif3d.seconds//3600):02d}:{(dif3d.seconds//60) % 60:02d}:{dif3d.seconds % 60:02d} "
                f"PDBQT conversion in {(difpdbqt.days*24+difpdbqt.seconds//3600):60}:{(difpdbqt.seconds//60) % 60:02d}:{difpdbqt.seconds % 60:02d}\n"
            )

input("Press Enter to exit")



