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
    "menu_step1": {"en": "Step 1 - Docking Settings", "pt": "Etapa 1 - Configurações de Docking"},
    "menu_step2": {"en": "Step 2 - Prepare Ligands", "pt": "Etapa 2 - Preparar Ligantes"},
    "menu_step3": {"en": "Step 3 - Prepare Targets", "pt": "Etapa 3 - Preparar Alvos"},
    "menu_step4": {"en": "Step 4 - Run Molecular Docking", "pt": "Etapa 4 - Executar Docking Molecular"},
    "menu_step5": {"en": "Step 5 - View Results", "pt": "Etapa 5 - Ver Resultados"},
    "menu_exit": {"en": "Exit", "pt": "Sair"},
    "menu_help": {"en": "Help", "pt": "Ajuda"},
    "menu_install_requirements": {"en": "Install Requirements", "pt": "Instalar Dependências"},
    "menu_github": {"en": "Code and Tutorials (Github)", "pt": "Código e Tutoriais (Github)"},
    "menu_about": {"en": "About Us", "pt": "Sobre Nós"},

    # ---------------------------------------------------------------- About dialog
    "msg_title_about": {"en": "ABOUT US", "pt": "SOBRE NÓS"},
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
              "   moimaian@gmail.com\n"
              "\n"
              "Version 1.0 (beta)",
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
              "   moimaian@gmail.com\n"
              "\n"
              "Versão 1.0 (beta)",
    },

    # ---------------------------------------------------------------- Tab names
    "tab_home": {"en": "HOME", "pt": "INÍCIO"},
    "tab_step1": {"en": "STEP 1", "pt": "ETAPA 1"},
    "tab_step2": {"en": "STEP 2", "pt": "ETAPA 2"},
    "tab_step3": {"en": "STEP 3", "pt": "ETAPA 3"},
    "tab_step4": {"en": "STEP 4", "pt": "ETAPA 4"},
    "tab_step5": {"en": "STEP 5", "pt": "ETAPA 5"},

    # ---------------------------------------------------------------- Section titles (_title)
    "title_step1": {"en": "Step 1. Docking Settings", "pt": "Etapa 1. Configurações de Docking"},
    "title_step2": {"en": "Step 2. Prepare Ligands", "pt": "Etapa 2. Preparar Ligantes"},
    "title_step3": {"en": "Step 3. Prepare Targets", "pt": "Etapa 3. Preparar Alvos"},
    "title_step4": {"en": "Step 4. Run Molecular Docking", "pt": "Etapa 4. Executar Docking Molecular"},
    "title_step5": {"en": "Step 5. View Results", "pt": "Etapa 5. Ver Resultados"},

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
    "home_grp_sw": {"en": "Software Specs", "pt": "Especificações de Software"},
    "home_grp_pipeline": {"en": "Pipeline - Steps", "pt": "Pipeline - Etapas"},
    "home_step1_name": {"en": "Step 1 - Docking Settings", "pt": "Etapa 1 - Configurações de Docking"},
    "home_step1_desc": {
        "en": "Configure directories, docking parameters and binary paths.",
        "pt": "Configure diretórios, parâmetros de docking e caminhos dos binários.",
    },
    "home_step2_name": {"en": "Step 2 - Prepare Ligands", "pt": "Etapa 2 - Preparar Ligantes"},
    "home_step2_desc": {
        "en": "Split inputs, calculate ligand descriptors, filter, convert to PDBQT and recover failures.",
        "pt": "Divida arquivos de entrada, calcule descritores dos ligantes, filtre, converta para PDBQT e recupere falhas.",
    },
    "home_step3_name": {"en": "Step 3 - Prepare Targets", "pt": "Etapa 3 - Preparar Alvos"},
    "home_step3_desc": {
        "en": "Prepare rigid or flexible receptors, build grid boxes and manage target folders.",
        "pt": "Prepare receptores rígidos ou flexíveis, construa grid boxes e gerencie as pastas de alvos.",
    },
    "home_step4_name": {"en": "Step 4 - Run Molecular Docking", "pt": "Etapa 4 - Executar Docking Molecular"},
    "home_step4_desc": {
        "en": "Launch rigid or flexible docking on CPU or GPU, including restart workflows.",
        "pt": "Execute docking rígido ou flexível em CPU ou GPU, incluindo fluxos de reinício.",
    },
    "home_step5_name": {"en": "Step 5 - View Results", "pt": "Etapa 5 - Ver Resultados"},
    "home_step5_desc": {
        "en": "Inspect docking tables, filter top ligands by RMSD and plot ranked hits.",
        "pt": "Inspecione as tabelas de docking, filtre os melhores ligantes por RMSD e plote os hits ranqueados.",
    },
    "home_btn_start": {"en": "START", "pt": "INICIAR"},
    "home_btn_install": {"en": "Install Requirements", "pt": "Instalar Dependências"},

    # ---------------------------------------------------------------- STEP 1 (Docking Settings)
    "s1_grp_docking_params": {"en": "Docking parameters", "pt": "Parâmetros de docking"},
    "s1_lbl_scoring_function": {"en": "Scoring function", "pt": "Função de pontuação"},
    "s1_lbl_split_results": {"en": "Split results", "pt": "Dividir resultados"},
    "s1_lbl_cpu_threads": {"en": "CPU threads", "pt": "Threads de CPU"},
    "s1_lbl_cpu_parallelism": {"en": "CPU parallelism", "pt": "Paralelismo de CPU"},
    "s1_lbl_exhaustiveness": {"en": "Exhaustiveness", "pt": "Exaustividade"},
    "s1_lbl_gpu_threads": {"en": "GPU threads", "pt": "Threads de GPU"},
    "s1_lbl_poses": {"en": "Poses", "pt": "Poses"},
    "s1_lbl_energy_range": {"en": "Energy range", "pt": "Intervalo de energia"},
    "s1_lbl_min_rmsd": {"en": "Minimum RMSD", "pt": "RMSD mínimo"},
    "s1_lbl_opencl_platform": {"en": "OpenCL platform", "pt": "Plataforma OpenCL"},
    "s1_lbl_docking_type": {"en": "Docking type", "pt": "Tipo de docking"},
    "s1_lbl_processing_type": {"en": "Processing type", "pt": "Tipo de processamento"},
    "s1_lbl_vina_mode": {"en": "Vina mode", "pt": "Modo do Vina"},
    "s1_lbl_run_type": {"en": "Run type", "pt": "Tipo de execução"},
    "s1_lbl_opencl_device": {"en": "OpenCL device", "pt": "Dispositivo OpenCL"},
    "s1_lbl_result_name": {"en": "Result name", "pt": "Nome do resultado"},
    "s1_lbl_ligands": {"en": "Ligands", "pt": "Ligantes"},
    "s1_lbl_targets": {"en": "Targets", "pt": "Alvos"},
    "s1_lbl_jobs": {"en": "Jobs", "pt": "Jobs"},
    "s1_btn_save_settings": {"en": "Save settings", "pt": "Salvar configurações"},
    "s1_btn_reload_settings": {"en": "Reload settings", "pt": "Recarregar configurações"},

    # ---------------------------------------------------------------- STEP 2 (Prepare Ligands)
    "s2_grp_prep_settings": {"en": "Ligand preparation settings", "pt": "Configurações de preparação dos ligantes"},
    "s2_grp_druggability": {"en": "Druggability Filter", "pt": "Filtro de Drogabilidade"},
    "s2_grp_actions": {"en": "Ligand actions", "pt": "Ações dos ligantes"},
    "s2_lbl_conversion_engine": {"en": "Conversion engine", "pt": "Motor de conversão"},
    "s2_lbl_max_folder": {"en": "Max ligands/folder", "pt": "Máx. de ligantes/pasta"},
    "s2_lbl_min_file_size": {"en": "Minimum file size", "pt": "Tamanho mínimo do arquivo"},
    "s2_lbl_workers": {"en": "Conversion Workers (Parallelization)", "pt": "Workers de conversão (Paralelização)"},
    "s2_lbl_min_algorithm": {"en": "Minimization algorithm", "pt": "Algoritmo de minimização"},
    "s2_lbl_min_forcefield": {"en": "Minimization force field", "pt": "Campo de força de minimização"},
    "s2_lbl_min_steps": {"en": "Minimization steps", "pt": "Passos de minimização"},
    "s2_lbl_mw_min": {"en": "MW min.", "pt": "MW mín."},
    "s2_lbl_mw_max": {"en": "MW máx.", "pt": "MW máx."},
    "s2_lbl_logp_min": {"en": "LogP min.", "pt": "LogP mín."},
    "s2_lbl_logp_max": {"en": "LogP máx.", "pt": "LogP máx."},
    "s2_lbl_hdonor_max": {"en": "H Donor máx.", "pt": "Doador H máx."},
    "s2_lbl_hacceptor_max": {"en": "H Acceptor máx.", "pt": "Aceptor H máx."},
    "s2_lbl_rot_max": {"en": "Rotatable Bonds máx.", "pt": "Ligações Rotacionáveis máx."},
    "s2_lbl_tpsa_max": {"en": "TPSA máx.", "pt": "TPSA máx."},
    "s2_lbl_ph": {"en": "Protonation pH", "pt": "pH de protonação"},
    "s2_lbl_rejected": {"en": "Rejected Elements", "pt": "Elementos rejeitados"},
    "s2_btn_refresh_summary": {"en": "Refresh summary", "pt": "Atualizar resumo"},
    "s2_btn_open_ligands_folder": {"en": "Open ligands folder", "pt": "Abrir pasta de ligantes"},
    "s2_btn_save_lig_settings": {"en": "Save ligand settings", "pt": "Salvar configurações de ligantes"},
    "s2_act_split_multimodel": {"en": "Split multimodel files", "pt": "Dividir arquivos multimodelo"},
    "s2_act_split_large_folders": {"en": "Split large folders", "pt": "Dividir pastas grandes"},
    "s2_act_generate_lipinski": {"en": "Generate SMI/CSV + Lipinski", "pt": "Gerar SMI/CSV + Lipinski"},
    "s2_act_druggability_filter": {"en": "Apply druggability filter", "pt": "Aplicar filtro de drogabilidade"},
    "s2_act_move_empty": {"en": "Move empty files", "pt": "Mover arquivos vazios"},
    "s2_act_convert_pdbqt": {"en": "Convert ligands to PDBQT", "pt": "Converter ligantes para PDBQT"},
    "s2_act_reject_pdbqt": {"en": "Reject invalid PDBQT", "pt": "Rejeitar PDBQT inválidos"},
    "s2_act_recover_pdbqt": {"en": "Recover failed ligands", "pt": "Recuperar ligantes com falha"},
    "s2_act_fix_macrocycles": {"en": "Fix macrocycles for GPU", "pt": "Corrigir macrociclos para GPU"},

    # ---------------------------------------------------------------- STEP 3 (Prepare Targets)
    "s3_grp_prepare_target": {"en": "Prepare receptor target", "pt": "Preparar alvo receptor"},
    "s3_grp_prepared_targets": {"en": "Prepared targets", "pt": "Alvos preparados"},
    "s3_lbl_prep_mode": {"en": "Preparation mode", "pt": "Modo de preparação"},
    "s3_lbl_target_name": {"en": "Target name", "pt": "Nome do alvo"},
    "s3_ph_target_name": {"en": "Optional target folder name", "pt": "Nome opcional da pasta do alvo"},
    "s3_lbl_target_file": {"en": "Target file", "pt": "Arquivo do alvo"},
    "s3_lbl_protonation_ph": {"en": "Protonation pH", "pt": "pH de protonação"},
    "s3_lbl_rigid_receptor": {"en": "Rigid receptor", "pt": "Receptor rígido"},
    "s3_lbl_flex_receptor": {"en": "Flexible receptor", "pt": "Receptor flexível"},
    "s3_lbl_existing_grid": {"en": "Existing grid", "pt": "Grid existente"},
    "s3_lbl_grid_spacing": {"en": "Grid spacing", "pt": "Espaçamento do grid"},
    "s3_lbl_grid_center_x": {"en": "Grid center X", "pt": "Centro do grid X"},
    "s3_lbl_grid_center_y": {"en": "Grid center Y", "pt": "Centro do grid Y"},
    "s3_lbl_grid_center_z": {"en": "Grid center Z", "pt": "Centro do grid Z"},
    "s3_lbl_grid_x_size": {"en": "Grid x size", "pt": "Tamanho X do grid"},
    "s3_lbl_grid_y_size": {"en": "Grid y size", "pt": "Tamanho Y do grid"},
    "s3_lbl_grid_z_size": {"en": "Grid z size", "pt": "Tamanho Z do grid"},
    "s3_btn_choose_target": {"en": "Select target file", "pt": "Selecionar arquivo do alvo"},
    "s3_btn_choose_rigid": {"en": "Select protein_rigid.pdbqt", "pt": "Selecionar protein_rigid.pdbqt"},
    "s3_btn_choose_flex": {"en": "Select protein_flex.pdbqt", "pt": "Selecionar protein_flex.pdbqt"},
    "s3_btn_choose_grid": {"en": "Select existing grid.txt", "pt": "Selecionar grid.txt existente"},
    "s3_btn_detect_pocket": {"en": "Detect pocket (P2Rank)", "pt": "Detectar bolso (P2Rank)"},
    "s3_tooltip_detect_pocket": {
        "en": "Runs a heuristic pocket search with P2Rank on the selected target structure "
              "and fills the Grid center X/Y/Z fields with the top-ranked pocket's coordinates.",
        "pt": "Executa uma busca heurística de bolso com o P2Rank na estrutura do alvo "
              "selecionada e preenche os campos Grid center X/Y/Z com as coordenadas do "
              "bolso mais bem ranqueado.",
    },
    "s3_btn_prepare_target": {"en": "Prepare target", "pt": "Preparar alvo"},
    "s3_btn_refresh_targets": {"en": "Refresh target list", "pt": "Atualizar lista de alvos"},
    "s3_btn_open_target": {"en": "Open target folder", "pt": "Abrir pasta do alvo"},
    "s3_btn_remove_target": {"en": "Remove target", "pt": "Remover alvo"},

    # ---------------------------------------------------------------- STEP 4 (Run Molecular Docking)
    "s4_grp_monitor": {"en": "Docking monitor", "pt": "Monitor de docking"},
    "s4_lbl_update_interval": {"en": "Update interval", "pt": "Intervalo de atualização"},
    "s4_lbl_docked": {"en": "Ligands docked", "pt": "Ligantes dockados"},
    "s4_lbl_total": {"en": "Total ligands", "pt": "Total de ligantes"},
    "s4_lbl_percent": {"en": "Percent complete", "pt": "Percentual concluído"},
    "s4_lbl_eta": {"en": "ETA", "pt": "ETA"},
    "s4_lbl_running_time": {"en": "Running time", "pt": "Tempo de execução"},
    "s4_lbl_completion": {"en": "Estim. completion", "pt": "Conclusão estimada"},
    "s4_btn_run_docking": {"en": "Run docking", "pt": "Executar docking"},

    # ---------------------------------------------------------------- STEP 5 (View Results)
    "s5_grp_filters": {"en": "Result filters", "pt": "Filtros de resultados"},
    "s5_grp_controls": {"en": "Result controls", "pt": "Controles de resultados"},
    "s5_lbl_top_ligands": {"en": "Top ligands", "pt": "Melhores ligantes"},
    "s5_lbl_rmsd_threshold": {"en": "RMSD threshold", "pt": "Limiar de RMSD"},
    "s5_btn_refresh": {"en": "Refresh", "pt": "Atualizar"},
    "s5_btn_open_result_folder": {"en": "Open result folder", "pt": "Abrir pasta de resultados"},
    "s5_btn_load_raw_csv": {"en": "Load raw CSV", "pt": "Carregar CSV bruto"},
    "s5_btn_load_filtered": {"en": "Load filtered top results", "pt": "Carregar melhores resultados filtrados"},
    "s5_btn_export_csv": {"en": "Export CSV", "pt": "Exportar CSV"},
    "s5_btn_plot_filtered": {"en": "Plot filtered results", "pt": "Plotar resultados filtrados"},
    "s5_btn_generate_report": {"en": "Generate Final Report", "pt": "Gerar relatório final"},
}


def t(chave, idioma, **kwargs):
    valor = _TEXTOS.get(chave, {}).get(idioma)
    if valor is None:
        valor = _TEXTOS.get(chave, {}).get(IDIOMA_PADRAO, chave)
    return valor.format(**kwargs) if kwargs else valor
