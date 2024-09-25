echo venv\Scripts\activate.bat
call venv\Scripts\activate.bat

@REM VERSION WITH MSYS2
@ECHO This is the script to compile the Cython part of the code
@ECHO "msys2" must be installed on your system in the default folder (C:\msys64)
@ECHO you can download it from https://www.msys2.org/
@ECHO and inside msys2 environment gcc must be installed
@ECHO (you can install it inside msys2 environment with the
@ECHO command 'pacman -S mingw-w64-ucrt-x86_64-gcc' inside msys2 env)

SET PATH=%PATH%;C:\msys64\usr\bin;C:\msys64\ucrt64\bin
python setup.py build_ext --inplace --force --compiler=mingw32 -DMS_WIN64
