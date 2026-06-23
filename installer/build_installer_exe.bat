@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

where py >nul 2>nul
if not errorlevel 1 (
    set "PYTHON_CMD=py -3.13"
)

if not defined PYTHON_CMD (
    where python >nul 2>nul
    if not errorlevel 1 (
        for /f "tokens=*" %%v in ('python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2^>nul') do set "PYTHON_VERSION=%%v"
        if "!PYTHON_VERSION!"=="3.13" set "PYTHON_CMD=python"
    )
)

if not defined PYTHON_CMD (
    echo Python 3.13 was not found.
    echo Install Python 3.13, then run this script again:
    echo https://www.python.org/ftp/python/3.13.14/python-3.13.14-amd64.exe
    exit /b 1
)

echo Using: %PYTHON_CMD%

%PYTHON_CMD% -m pip install --upgrade pyinstaller
if errorlevel 1 exit /b 1

%PYTHON_CMD% -m PyInstaller ^
    --clean ^
    --noconfirm ^
    --onefile ^
    --windowed ^
    --name brighteyes_mcs_installer ^
    brighteyes_mcs_installer.py

if errorlevel 1 exit /b 1

if not exist "dist\brighteyes_mcs_installer.exe" (
    echo Expected output was not found: dist\brighteyes_mcs_installer.exe
    exit /b 1
)

move /Y "dist\brighteyes_mcs_installer.exe" "brighteyes_mcs_installer.exe"
if errorlevel 1 exit /b 1

if exist "dist" rmdir /S /Q "dist"

echo.
echo Created brighteyes_mcs_installer.exe
endlocal
