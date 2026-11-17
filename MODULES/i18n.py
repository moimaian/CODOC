# -*- coding: utf-8 -*-

# SPDX-License-Identifier: GPL-3.0-or-later
#
# CODOC - Python Molecular Docking Tool
# Copyright (C) 2024-2026 Moises Maia
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.

"""Interface texts in English / Brazilian Portuguese for CODOC.

Mirrors the pattern used by CODRUG's own MODULES/i18n.py (which in turn mirrors AgendaLab's):
a flat dict of {key: {"en": ..., "pt": ...}} plus a single t(key, idioma, **kwargs) lookup.
CODOC's UI was originally written entirely in English, so "en" values are always the original,
unmodified text (switching to English can never change existing behavior/wording) and "pt"
values are the added translation.

t() falls back to returning the key itself when a key has no entry yet (or no entry for the
requested language) - this lets the interface be translated incrementally, without ever
crashing or showing a blank string for text that hasn't been ported to i18n.t(...) yet.
"""

IDIOMA_PADRAO = "en"

_TEXTOS = {
    # ---------------------------------------------------------------- Main window chrome
    "app_titulo": {
        "en": "CODOC - Python Molecular Docking Tool",
        "pt": "CODOC - Ferramenta Python de Docking Molecular",
    },
    "tooltip_bandeira_pt": {"en": "Português", "pt": "Português"},
    "tooltip_bandeira_en": {"en": "English", "pt": "English"},

    # ---------------------------------------------------------------- Menu
    "menu_home": {"en": "Home", "pt": "Início"},
    "menu_config": {"en": "CONFIG - Project Settings", "pt": "CONFIG - Configurações do Projeto"},
    "menu_step1": {"en": "Step 1 - Prepare Ligands", "pt": "Etapa 1 - Preparar Ligantes"},
    "menu_step2": {"en": "Step 2 - Prepare Targets", "pt": "Etapa 2 - Preparar Alvos"},
    "menu_step3": {"en": "Step 3 - Run Molecular Docking", "pt": "Etapa 3 - Executar Docking Molecular"},
    "menu_step4": {"en": "Step 4 - View Results", "pt": "Etapa 4 - Ver Resultados"},
    "menu_exit": {"en": "Exit", "pt": "Sair"},
    "menu_help": {"en": "Help", "pt": "Ajuda"},
    "menu_install_requirements": {"en": "Install Requirements", "pt": "Instalar Dependências"},
    "menu_terminal": {"en": "Terminal", "pt": "Terminal"},
    "menu_github": {"en": "Code and Tutorials (Github)", "pt": "Código e Tutoriais (Github)"},
    "menu_about": {"en": "About Us", "pt": "Sobre Nós"},

    # ---------------------------------------------------------------- About dialog
    "msg_title_about": {"en": "ABOUT US", "pt": "SOBRE NÓS"},
    "msg_about_version": {"en": "Version", "pt": "Versão"},
    "msg_about_body": {
        "en": "CODOC\n"
              "Computational Molecular Docking Platform\n"
              "\n"
              "Developed by:\n"
              "   Allan Michael Junkert\n"
              "   Gustavo Henrique Scheiffer\n"
              "   Moises Maia Neto\n"
              "   Roberto Pontarolo\n"
              "   Universidade Federal do Parana (UFPR), Brazil\n"
              "\n"
              "Contact:\n"
              "   moimaian@gmail.com",
        "pt": "CODOC\n"
              "Plataforma Computacional de Docking Molecular\n"
              "\n"
              "Desenvolvido por:\n"
              "   Allan Michael Junkert\n"
              "   Gustavo Henrique Scheiffer\n"
              "   Moises Maia Neto\n"
              "   Roberto Pontarolo\n"
              "   Universidade Federal do Paraná (UFPR), Brasil\n"
              "\n"
              "Contato:\n"
              "   moimaian@gmail.com",
    },

    # ---------------------------------------------------------------- Tab names
    "tab_home": {"en": "HOME", "pt": "INÍCIO"},
    "tab_config": {"en": "CONFIG", "pt": "CONFIG"},
    "tab_step1": {"en": "STEP 1", "pt": "ETAPA 1"},
    "tab_step2": {"en": "STEP 2", "pt": "ETAPA 2"},
    "tab_step3": {"en": "STEP 3", "pt": "ETAPA 3"},
    "tab_step4": {"en": "STEP 4", "pt": "ETAPA 4"},

    # ---------------------------------------------------------------- Section titles (_title)
    "title_config": {"en": "Project Settings", "pt": "Configurações do Projeto"},
    "title_step1": {"en": "Prepare Ligands", "pt": "Preparar Ligantes"},
    "title_step2": {"en": "Prepare Targets", "pt": "Preparar Alvos"},
    "title_step3": {"en": "Run Molecular Docking", "pt": "Executar Docking Molecular"},
    "title_step4": {"en": "View Results", "pt": "Ver Resultados"},

    # ---------------------------------------------------------------- Shared nav buttons
    "btn_back": {"en": " << BACK ", "pt": " << VOLTAR "},
    "btn_next": {"en": " NEXT >> ", "pt": " AVANÇAR >> "},
    "btn_browse": {"en": "Browse", "pt": "Procurar"},

    # ---------------------------------------------------------------- HOME tab
    "home_title": {
        "en": "Computational Molecular Docking Plataform",
        "pt": "Plataforma Computacional de Docking Molecular",
    },
    "home_subtitle": {"en": "Multi-target docking with Vina", "pt": "Docking multi-alvo com Vina"},
    "home_grp_cpu": {"en": "Hardware Specs - CPU", "pt": "Especificações de Hardware - CPU"},
    "home_grp_gpu": {"en": "Hardware Specs - GPU", "pt": "Especificações de Hardware - GPU"},
    "home_grp_storage": {"en": "Hardware Specs - Storage", "pt": "Especificações de Hardware - Armazenamento"},
    "home_grp_sw": {"en": "Software Specs", "pt": "Especificações de Software"},
    "home_grp_pipeline": {"en": "Pipeline - Steps", "pt": "Pipeline - Etapas"},
    "home_config_name": {"en": "CONFIG - Project Settings", "pt": "CONFIG - Configurações do Projeto"},
    "home_config_desc": {
        "en": "Create a new project or resume a previous one, and set the performance options.",
        "pt": "Crie um projeto novo ou retome um anterior e defina as opções de desempenho.",
    },
    "home_step1_name": {"en": "Step 1 - Prepare Ligands", "pt": "Etapa 1 - Preparar Ligantes"},
    "home_step1_desc": {
        "en": "Import ligand files and folders, split inputs, calculate descriptors, filter, convert to PDBQT and recover failures.",
        "pt": "Importe arquivos e pastas de ligantes, divida entradas, calcule descritores, filtre, converta para PDBQT e recupere falhas.",
    },
    "home_step2_name": {"en": "Step 2 - Prepare Targets", "pt": "Etapa 2 - Preparar Alvos"},
    "home_step2_desc": {
        "en": "Prepare rigid or flexible receptors, build grid boxes and manage the targets of the project.",
        "pt": "Prepare receptores rígidos ou flexíveis, construa grid boxes e gerencie os alvos do projeto.",
    },
    "home_step3_name": {"en": "Step 3 - Run Molecular Docking", "pt": "Etapa 3 - Executar Docking Molecular"},
    "home_step3_desc": {
        "en": "Set the docking parameters and launch rigid or flexible docking on CPU or GPU; running it again resumes from the ligands still pending.",
        "pt": "Defina os parâmetros e execute docking rígido ou flexível em CPU ou GPU; executar de novo retoma pelos ligantes ainda pendentes.",
    },
    "home_step4_name": {"en": "Step 4 - View Results", "pt": "Etapa 4 - Ver Resultados"},
    "home_step4_desc": {
        "en": "Inspect docking tables, filter top ligands by RMSD and plot ranked hits.",
        "pt": "Inspecione as tabelas de docking, filtre os melhores ligantes por RMSD e plote os hits ranqueados.",
    },
    "home_btn_start": {"en": "START", "pt": "INICIAR"},
    "home_btn_install": {"en": "Install Requirements", "pt": "Instalar Dependências"},

    # ---------------------------------------------------------------- CONFIG (Projects + Settings)
    "msg_terminal_unavailable": {
        "en": "No terminal emulator was found (x-terminal-emulator, gnome-terminal, konsole, xfce4-terminal or xterm).",
        "pt": "Nenhum emulador de terminal foi encontrado (x-terminal-emulator, gnome-terminal, konsole, xfce4-terminal ou xterm).",
    },
    "msg_no_project": {
        "en": "Create or load a project first (CONFIG > Projects).",
        "pt": "Crie ou carregue um projeto antes (CONFIG > Projetos).",
    },
    "cfg_grp_projects": {"en": "Projects", "pt": "Projetos"},
    "cfg_proj_new": {"en": "New Project", "pt": "Novo Projeto"},
    "cfg_proj_load": {"en": "Load Previous Project", "pt": "Carregar Projeto Anterior"},
    "cfg_proj_date": {"en": "Date:", "pt": "Data:"},
    "cfg_proj_name": {"en": "Project name:", "pt": "Nome do projeto:"},
    "cfg_proj_prev": {"en": "Previous project:", "pt": "Projeto anterior:"},
    "cfg_proj_id": {"en": "Project ID:", "pt": "ID do projeto:"},
    "cfg_proj_ph_name": {"en": "e.g.: EGFR_inhibitors_01", "pt": "ex.: EGFR_inibidores_01"},
    "cfg_proj_prev_tip": {
        "en": "Reopens a project: its ligands, targets and docking results, and the settings saved in the .json file of each step.",
        "pt": "Reabre um projeto: seus ligantes, alvos e resultados de docking, e as configurações salvas no arquivo .json de cada etapa.",
    },
    "cfg_proj_btn": {"en": "Create / Load Project", "pt": "Criar / Carregar Projeto"},
    "cfg_proj_none": {
        "en": "No project open. Create a new one or load a previous one to use the steps.",
        "pt": "Nenhum projeto aberto. Crie um novo ou carregue um anterior para usar as etapas.",
    },
    "cfg_proj_name_required": {"en": "Type a name for the new project.", "pt": "Digite um nome para o novo projeto."},
    "cfg_proj_exists": {"en": "A project with this ID already exists.", "pt": "Já existe um projeto com este ID."},
    "cfg_proj_select_prev": {"en": "Select a previous project in the list.", "pt": "Selecione um projeto anterior na lista."},
    "cfg_proj_not_found": {"en": "Project folder not found:\n{path}", "pt": "Pasta do projeto não encontrada:\n{path}"},
    "cfg_grp_performance": {"en": "Performance Options", "pt": "Opções de Desempenho"},
    "cfg_lbl_processing_type": {"en": "Processing type", "pt": "Tipo de processamento"},
    "cfg_lbl_cpu_threads": {"en": "CPU threads", "pt": "Threads de CPU"},
    "cfg_lbl_gpu_threads": {"en": "GPU threads", "pt": "Threads de GPU"},
    "cfg_lbl_opencl_platform": {"en": "OpenCL platform", "pt": "Plataforma OpenCL"},
    "cfg_lbl_opencl_device": {"en": "OpenCL device", "pt": "Dispositivo OpenCL"},
    "cfg_btn_save_settings": {"en": "Save settings", "pt": "Salvar configurações"},
    "cfg_btn_reload_settings": {"en": "Reload settings", "pt": "Recarregar configurações"},

    # ---------------------------------------------------------------- STEP 1 (Prepare Ligands)
    "s1_grp_prep_settings": {"en": "Ligand preparation settings", "pt": "Configurações de preparação dos ligantes"},
    "s1_lbl_ligands": {"en": "Ligands", "pt": "Ligantes"},
    "s1_ph_ligands": {
        "en": "No ligands imported yet - click Browse (BASE folder)",
        "pt": "Nenhum ligante importado - clique em Procurar (pasta BASE)",
    },
    "s1_tip_ligands": {
        "en": "Opens the BASE folder: pick one or more multi-ligand files and/or one or more folders of individual ligands "
              "(Ctrl/Shift to select several). They are COPIED into CONVERSION/LIGANDS of this project; the originals stay where they are.",
        "pt": "Abre a pasta BASE: escolha um ou mais arquivos multiligante e/ou uma ou mais pastas de ligantes individuais "
              "(Ctrl/Shift para selecionar vários). Eles são COPIADOS para CONVERSION/LIGANDS deste projeto; os originais ficam onde estão.",
    },
    "s1_dlg_pick_ligands": {"en": "Select ligand files and/or folders", "pt": "Selecione arquivos e/ou pastas de ligantes"},
    "s1_grp_druggability": {"en": "Druggability Filter", "pt": "Filtro de Drogabilidade"},
    "s1_grp_actions": {"en": "Ligand actions", "pt": "Ações dos ligantes"},
    "s1_lbl_conversion_engine": {"en": "Conversion engine", "pt": "Motor de conversão"},
    "s1_lbl_max_folder": {"en": "Max ligands/folder", "pt": "Máx. de ligantes/pasta"},
    "s1_lbl_min_file_size": {"en": "Minimum file size", "pt": "Tamanho mínimo do arquivo"},
    "s1_lbl_workers": {"en": "Conversion Workers (Parallelization)", "pt": "Workers de conversão (Paralelização)"},
    "s1_lbl_min_algorithm": {"en": "Minimization algorithm", "pt": "Algoritmo de minimização"},
    "s1_lbl_min_forcefield": {"en": "Minimization force field", "pt": "Campo de força de minimização"},
    "s1_lbl_min_steps": {"en": "Minimization steps", "pt": "Passos de minimização"},
    "s1_lbl_mw_min": {"en": "MW min.", "pt": "MW mín."},
    "s1_lbl_mw_max": {"en": "MW max.", "pt": "MW máx."},
    "s1_lbl_logp_min": {"en": "LogP min.", "pt": "LogP mín."},
    "s1_lbl_logp_max": {"en": "LogP max.", "pt": "LogP máx."},
    "s1_lbl_hdonor_max": {"en": "H Donor max.", "pt": "Doador H máx."},
    "s1_lbl_hacceptor_max": {"en": "H Acceptor max.", "pt": "Aceptor H máx."},
    "s1_lbl_rot_max": {"en": "Rotatable Bonds max.", "pt": "Ligações Rotacionáveis máx."},
    "s1_lbl_tpsa_max": {"en": "TPSA max.", "pt": "TPSA máx."},
    "s1_lbl_ph": {"en": "Protonation pH", "pt": "pH de protonação"},
    "s1_lbl_rejected": {"en": "Rejected Elements", "pt": "Elementos rejeitados"},
    "s1_btn_refresh_monitor": {"en": "Refresh monitor", "pt": "Atualizar monitor"},
    "s1_grp_monitor": {"en": "Monitor", "pt": "Monitor"},
    "s1_mon_col_type": {"en": "Ligands Type", "pt": "Tipo de ligantes"},
    "s1_mon_col_count": {"en": "Quantity", "pt": "Quantidade"},
    "s1_mon_groups": {"en": "Groups", "pt": "Grupos"},
    "s1_mon_multimodels": {"en": "Multimodels", "pt": "Multimodelos"},
    "s1_mon_splitted": {"en": "Splitted", "pt": "Divididos"},
    "s1_mon_empty": {"en": "Empty", "pt": "Vazios"},
    "s1_mon_converted": {"en": "Converted", "pt": "Convertidos"},
    "s1_mon_rejected": {"en": "Rejected", "pt": "Rejeitados"},
    "s1_mon_recovered": {"en": "Recovered", "pt": "Recuperados"},
    "s1_btn_open_ligands_folder": {"en": "Open ligands folder", "pt": "Abrir pasta de ligantes"},
    "s1_btn_save_lig_settings": {"en": "Save ligand settings", "pt": "Salvar configurações de ligantes"},
    "s1_act_split_multimodel": {"en": "Split multimodel files", "pt": "Dividir arquivos multimodelo"},
    "s1_act_split_large_folders": {"en": "Split large folders", "pt": "Dividir pastas grandes"},
    "s1_act_generate_lipinski": {"en": "Generate SMI/CSV + Lipinski", "pt": "Gerar SMI/CSV + Lipinski"},
    "s1_act_druggability_filter": {"en": "Apply druggability filter", "pt": "Aplicar filtro de drogabilidade"},
    "s1_act_move_empty": {"en": "Move empty files", "pt": "Mover arquivos vazios"},
    "s1_act_convert_pdbqt": {"en": "Convert ligands to PDBQT", "pt": "Converter ligantes para PDBQT"},
    "s1_act_reject_pdbqt": {"en": "Reject invalid PDBQT", "pt": "Rejeitar PDBQT inválidos"},
    "s1_act_recover_pdbqt": {"en": "Recover failed ligands", "pt": "Recuperar ligantes com falha"},
    "s1_act_fix_macrocycles": {"en": "Fix macrocycles for GPU", "pt": "Corrigir macrociclos para GPU"},

    # ---------------------------------------------------------------- STEP 2 (Prepare Targets)
    "s2_grp_prepare_target": {"en": "Prepare receptor target", "pt": "Preparar alvo receptor"},
    "s2_grp_prepared_targets": {"en": "Prepared targets", "pt": "Alvos preparados"},
    "s2_lbl_prep_mode": {"en": "Preparation mode", "pt": "Modo de preparação"},
    "s2_lbl_target_name": {"en": "Target name", "pt": "Nome do alvo"},
    "s2_ph_target_name": {"en": "Optional target folder name", "pt": "Nome opcional da pasta do alvo"},
    "s2_lbl_target_file": {"en": "Target file", "pt": "Arquivo do alvo"},
    "s2_lbl_protonation_ph": {"en": "Protonation pH", "pt": "pH de protonação"},
    "s2_lbl_rigid_receptor": {"en": "Rigid receptor", "pt": "Receptor rígido"},
    "s2_lbl_flex_receptor": {"en": "Flexible receptor", "pt": "Receptor flexível"},
    "s2_lbl_existing_grid": {"en": "Existing grid", "pt": "Grid existente"},
    "s2_lbl_grid_spacing": {"en": "Grid spacing", "pt": "Espaçamento do grid"},
    "s2_lbl_grid_center_x": {"en": "Grid center X", "pt": "Centro do grid X"},
    "s2_lbl_grid_center_y": {"en": "Grid center Y", "pt": "Centro do grid Y"},
    "s2_lbl_grid_center_z": {"en": "Grid center Z", "pt": "Centro do grid Z"},
    "s2_lbl_grid_x_size": {"en": "Grid x size", "pt": "Tamanho X do grid"},
    "s2_lbl_grid_y_size": {"en": "Grid y size", "pt": "Tamanho Y do grid"},
    "s2_lbl_grid_z_size": {"en": "Grid z size", "pt": "Tamanho Z do grid"},
    "s2_btn_choose_target": {"en": "Select target file", "pt": "Selecionar arquivo do alvo"},
    "s2_btn_choose_rigid": {"en": "Select protein_rigid.pdbqt", "pt": "Selecionar protein_rigid.pdbqt"},
    "s2_btn_choose_flex": {"en": "Select protein_flex.pdbqt", "pt": "Selecionar protein_flex.pdbqt"},
    "s2_btn_choose_grid": {"en": "Select existing grid.txt", "pt": "Selecionar grid.txt existente"},
    "s2_btn_detect_pocket": {"en": "Detect pocket (P2Rank)", "pt": "Detectar bolso (P2Rank)"},
    "s2_tooltip_detect_pocket": {
        "en": "Runs a heuristic pocket search with P2Rank on the selected target structure "
              "and fills the Grid center X/Y/Z fields with the top-ranked pocket's coordinates.",
        "pt": "Executa uma busca heurística de bolso com o P2Rank na estrutura do alvo "
              "selecionada e preenche os campos Grid center X/Y/Z com as coordenadas do "
              "bolso mais bem ranqueado.",
    },
    "s2_lbl_cocrystal": {"en": "Co-crystal ligand", "pt": "Ligante cocristalizado"},
    "s2_btn_find_ligands": {"en": "Find co-crystal ligands", "pt": "Buscar ligantes cocristalizados"},
    "s2_tooltip_find_ligands": {
        "en": "Lists the ligands already complexed in the selected PDB file (HETATM groups that are not water, ions or modified residues).",
        "pt": "Lista os ligantes já complexados no arquivo PDB selecionado (grupos HETATM que não sejam água, íons ou resíduos modificados).",
    },
    "s2_btn_grid_from_ligand": {"en": "Grid from selected ligand", "pt": "Grid a partir do ligante"},
    "s2_tooltip_grid_from_ligand": {
        "en": "Centers the grid on the selected co-crystal ligand and sizes the box to enclose it (extent + 6 A per side, minimum 20 A).",
        "pt": "Centraliza o grid no ligante cocristalizado selecionado e dimensiona a caixa para envolvê-lo (extensão + 6 A por lado, mínimo 20 A).",
    },
    "s2_btn_export_redock": {"en": "Export ligand for redocking", "pt": "Exportar ligante p/ redocking"},
    "s2_tooltip_export_redock": {
        "en": "Writes the selected co-crystal ligand to the REDOCK group of this project's ligands (prepared in STEP 1 like any other ligand) and keeps its crystal pose as the reference for 'Redocking RMSD' in STEP 4.",
        "pt": "Grava o ligante cocristalizado selecionado no grupo REDOCK dos ligantes deste projeto (preparado na ETAPA 1 como qualquer outro ligante) e guarda a pose cristalográfica como referência para o 'RMSD do redocking' na ETAPA 4.",
    },
    "s2_btn_prepare_target": {"en": "Prepare target", "pt": "Preparar alvo"},
    "s2_btn_refresh_targets": {"en": "Refresh target list", "pt": "Atualizar lista de alvos"},
    "s2_btn_open_target": {"en": "Open target folder", "pt": "Abrir pasta do alvo"},
    "s2_btn_remove_target": {"en": "Remove target", "pt": "Remover alvo"},

    # ---------------------------------------------------------------- STEP 3 (Run Molecular Docking)
    "s3_grp_params": {"en": "Docking parameters", "pt": "Parâmetros de docking"},
    "s3_lbl_scoring_function": {"en": "Scoring function", "pt": "Função de pontuação"},
    "s3_lbl_split_results": {"en": "Split results", "pt": "Dividir resultados"},
    "s3_lbl_exhaustiveness": {"en": "Exhaustiveness", "pt": "Exaustividade"},
    "s3_lbl_poses": {"en": "Poses", "pt": "Poses"},
    "s3_lbl_energy_range": {"en": "Energy range", "pt": "Intervalo de energia"},
    "s3_lbl_min_rmsd": {"en": "Minimum RMSD", "pt": "RMSD mínimo"},
    "s3_lbl_docking_type": {"en": "Docking type", "pt": "Tipo de docking"},
    "s3_lbl_vina_mode": {"en": "Vina mode", "pt": "Modo do Vina"},
    "s3_grp_monitor": {"en": "Docking monitor", "pt": "Monitor de docking"},
    "s3_lbl_update_interval": {"en": "Update interval", "pt": "Intervalo de atualização"},
    "s3_lbl_docked": {"en": "Ligands docked", "pt": "Ligantes dockados"},
    "s3_lbl_total": {"en": "Total ligands", "pt": "Total de ligantes"},
    "s3_lbl_percent": {"en": "Percent complete", "pt": "Percentual concluído"},
    "s3_lbl_eta": {"en": "ETA", "pt": "ETA"},
    "s3_lbl_running_time": {"en": "Running time", "pt": "Tempo de execução"},
    "s3_lbl_completion": {"en": "Estim. completion", "pt": "Conclusão estimada"},
    "s3_btn_run_docking": {"en": "Run docking", "pt": "Executar docking"},

    # ---------------------------------------------------------------- STEP 4 (View Results)
    "s4_lbl_project": {"en": "Project: {name}", "pt": "Projeto: {name}"},
    "s4_grp_filters": {"en": "Result filters", "pt": "Filtros de resultados"},
    "s4_grp_controls": {"en": "Result controls", "pt": "Controles de resultados"},
    "s4_lbl_top_ligands": {"en": "Top ligands", "pt": "Melhores ligantes"},
    "s4_lbl_rmsd_threshold": {"en": "RMSD threshold", "pt": "Limiar de RMSD"},
    "s4_btn_refresh": {"en": "Refresh", "pt": "Atualizar"},
    "s4_btn_open_result_folder": {"en": "Open result folder", "pt": "Abrir pasta de resultados"},
    "s4_btn_load_raw_csv": {"en": "Load raw CSV", "pt": "Carregar CSV bruto"},
    "s4_btn_load_filtered": {"en": "Load filtered top results", "pt": "Carregar melhores resultados filtrados"},
    "s4_btn_export_csv": {"en": "Export CSV", "pt": "Exportar CSV"},
    "s4_btn_redock_rmsd": {"en": "Redocking RMSD", "pt": "RMSD do redocking"},
    "s4_tooltip_redock_rmsd": {
        "en": "Compares each docked REDOCK ligand with its crystal pose (heavy-atom, symmetry-aware RMSD, best pose and minimum over all poses). Success: <= 2.0 A.",
        "pt": "Compara cada ligante REDOCK dockado com sua pose cristalográfica (RMSD de átomos pesados, com simetria; melhor pose e mínimo entre todas as poses). Sucesso: <= 2,0 A.",
    },
    "s4_btn_plot_filtered": {"en": "Plot filtered results", "pt": "Plotar resultados filtrados"},
    "s4_btn_generate_report": {"en": "Generate Final Report", "pt": "Gerar relatório final"},
}


def t(chave, idioma, **kwargs):
    valor = _TEXTOS.get(chave, {}).get(idioma)
    if valor is None:
        valor = _TEXTOS.get(chave, {}).get(IDIOMA_PADRAO, chave)
    return valor.format(**kwargs) if kwargs else valor
