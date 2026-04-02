@echo off
cd /d %~dp0

if exist .venv\Scripts\activate.bat (
    echo Activating .venv
    call .venv\Scripts\activate.bat
) else (
    echo Warning: .venv\Scripts\activate.bat was not found. Using the current Python environment.
)

python upgrade_mcs.py %*
