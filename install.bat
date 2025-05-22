@echo off
setlocal enabledelayedexpansion

:: Initialize global variable
set "SelectedPython="

echo Welcome to BrightEyes-MCS installation.
echo:
echo This script will install BrightEyes-MCS in a Virtual Environment in the current folder.
echo In order to proceed, you need to have installed in your system Python 3.10.
echo:
echo Found Python installation:

:: Use the "where" command to list available Python installations
set "Index=0"
for /f "tokens=* delims=" %%i in ('where python.exe') do (
    set /a Index+=1
    set "PythonExes[!Index!]=%%i"
    echo [!Index!] "%%i"
)

:: Prompt the user for input
echo:
echo Type the number of the Python 3.10 installation you want to use.
echo If you want to choose a different installation, please enter the full path to python.exe.
set /p "Choice=Then, press Enter (Default [1]):"
if "%Choice%"=="" set "Choice=1"

:: Check if the user entered a numeric choice
set /a NumericChoice=%Choice%
if defined PythonExes[%NumericChoice%] (
    set "SelectedPython=!PythonExes[%NumericChoice%]!"
) else (
    set "SelectedPython=%Choice%"
)

if not defined SelectedPython (
    echo Invalid choice or no Python installations found. Using the default.
    set "SelectedPython=!PythonExes[1]!"
)

:: Display the selected Python installation
echo:
echo Selected Python installation: %SelectedPython%
echo:
echo If it is correct, press Enter; otherwise, press Ctrl+C to exit.
echo:
pause
:: Save the selected Python installation path to the global variable
set "SelectedPython=!SelectedPython!"

:: Display the selected Python installation
echo Selected Python installation: %SelectedPython%

echo:
echo Generating the new venv environment in the folder venv\
echo:
"%SelectedPython%" -m venv venv
echo:
echo:
echo Activate the venv
echo:
call venv\Scripts\activate
echo:
echo Installing the pip requirements
echo:
pip install -r requirements.txt
echo:
echo Build Cython code
echo:
python compile_cython.py
echo:
python download_firmware.py
echo:
echo BrightEyes-MCS installation DONE!
echo:
pause
endlocal
