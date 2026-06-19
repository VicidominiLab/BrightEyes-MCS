@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
    echo Python launcher "py" was not found.
    echo Install Python 3.13, then run this script again.
    exit /b 1
)

py -3.13 -m pip install --upgrade pyinstaller
if errorlevel 1 exit /b 1

py -3.13 -m PyInstaller ^
    --onefile ^
    --windowed ^
    --name BrightEyes-MCS-Installer ^
    brighteyes_mcs_installer.py

if errorlevel 1 exit /b 1
echo.
echo Created dist\BrightEyes-MCS-Installer.exe
endlocal
