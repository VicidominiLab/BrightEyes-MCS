@echo off
@REM this move to the batch folder
cd %~dp0
@REM activate env
echo venv\Scripts\activate.bat
call venv\Scripts\activate.bat
echo running python -m brighteyes_mcs
python -m brighteyes_mcs
echo:
echo:

echo main.py is closed
pause