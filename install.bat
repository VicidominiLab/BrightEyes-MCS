@echo off
setlocal
cd /d "%~dp0"

echo BrightEyes-MCS installer
echo This opens the standalone stdlib GUI. For CLI usage run:
echo   python brighteyes_mcs_installer.py install --help
echo.

python brighteyes_mcs_installer.py gui
if errorlevel 1 (
    echo.
    echo If Python is not available, install Python 3.13 from:
    echo https://www.python.org/ftp/python/3.13.14/python-3.13.14-amd64.exe
    exit /b 1
)

endlocal
