@REM VERSION WITH VISUAL STUDIO
@ECHO Compiling Cython code with Microsoft Visual Studio
@ECHO If fail modify the compile_cython.bat

python setup.py build_ext --inplace --force
