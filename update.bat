@echo off
setlocal
cd /d "%~dp0"

if exist .venv\Scripts\python.exe (
    .venv\Scripts\python.exe brighteyes_mcs_installer.py update %*
) else (
    python brighteyes_mcs_installer.py update %*
)

endlocal
