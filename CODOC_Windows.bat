@echo off
rem ============================================================================
rem  CODOC - instalador/lancador para Windows 10/11 (duplo clique)
rem
rem  Chama o Install-CODOC.ps1 (PowerShell) sem exigir que o usuario abra um
rem  terminal ou digite comandos: copia o programa para %USERPROFILE%\CODOC,
rem  instala o Python 3.10 se faltar (so para o usuario atual, sem administrador),
rem  cria o ambiente virtual e os atalhos CODOC na Area de Trabalho e no Menu
rem  Iniciar e abre o programa.
rem
rem  So e preciso na primeira vez: depois use o atalho CODOC.
rem  (Se o Windows mostrar "O Windows protegeu o computador": Mais informacoes >
rem  Executar assim mesmo.)
rem ============================================================================
setlocal EnableExtensions
title CODOC - Instalacao
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-CODOC.ps1" %*
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
    echo.
    echo [CODOC] A instalacao nao terminou ^(codigo %RC%^). Leia as mensagens acima.
    pause
)
exit /b %RC%
