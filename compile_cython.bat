@echo off
echo .venv\Scripts\activate.bat
call .venv\Scripts\activate.bat
cmd /C "python installer.py --no--install-requirements --do-not-upgrade-msys2"