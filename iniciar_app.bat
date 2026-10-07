@echo off
title Inicio rapido - Comparacao de Apolices D^&O
REM Inicio rapido do aplicativo: dois cliques neste arquivo e o app abre no
REM navegador (UI demo com o modelo real via OpenRouter).
REM A chave NUNCA fica neste arquivo: ela mora na variavel de usuario
REM OPENROUTER_API_KEY (setx) do Windows.

cd /d "%~dp0"

if "%OPENROUTER_API_KEY%"=="" (
    echo [erro] Variavel OPENROUTER_API_KEY nao encontrada neste Windows.
    echo.
    echo Rode uma unica vez no terminal e depois abra este arquivo de novo:
    echo     setx OPENROUTER_API_KEY "sk-or-SEU_TOKEN"
    echo.
    pause
    exit /b 1
)

set LLM_REAL=1
REM Cadeia de LLMs: principal -> fallback (2 falhas) -> ultimo recurso (2 falhas).
set LLM_MODEL=z-ai/glm-5.3-flash
set LLM_FALLBACK_MODEL=deepseek/deepseek-v4.1-flash
set LLM_FALLBACK_MODEL_2=xiaomi/mimo-v2.6-pro
set PYTHONPATH=.tools\pylibs

echo Iniciando o app... o navegador abre sozinho em instantes.
echo Para encerrar, feche esta janela.
echo.

python -B -m streamlit run run_ui_demo.py --global.developmentMode false

pause
