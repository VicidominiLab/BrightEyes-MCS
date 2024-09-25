@echo off
setlocal

:: Title and description
echo ================================================
echo            Cython Compilation Script
echo ================================================
echo.

:: Initialize variables
set "VS_INSTALLED="
set "MSYS2_INSTALLED="

:: Check if Visual C++ Build Tools are installed by looking for cl.exe or vcvarsall.bat
for %%v in (14.0 15.0 16.0 17.0) do (
    reg query "HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\VisualStudio\%%v" >nul 2>nul
    if !errorlevel! == 0 (
        echo [INFO] Visual Studio %%v detected.
        if exist "%ProgramFiles(x86)%\Microsoft Visual Studio\%%v\VC\Tools\MSVC\*\bin\Hostx64\x64\cl.exe" (
            echo [INFO] Visual C++ Build Tools detected for Visual Studio %%v.
            set "VS_INSTALLED=1"
            goto check_msys2
        ) else (
            echo [ERROR] Visual Studio %%v detected, but C++ Build Tools are missing.
        )
    )
)

:: Additional check using vswhere.exe for Visual C++ Build Tools
if exist "%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe" (
    for /f "tokens=* usebackq" %%i in (`"%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe" -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -find "VC\Auxiliary\Build\vcvarsall.bat"`) do (
        set "VS_INSTALLED=1"
        echo [INFO] Visual Studio C++ Toolchain found via vswhere.
        goto check_msys2
    )
)

:check_msys2
:: Check if MSYS2 is installed by checking for msys2.exe
if exist "C:\msys64\msys2.exe" (
    echo [INFO] MSYS2 detected.
    set "MSYS2_INSTALLED=1"
)

:: Determine the installation status and call the appropriate script
if defined VS_INSTALLED (
    call compile_cython_vs.bat
    goto end
) else if defined MSYS2_INSTALLED (
    call compile_cython_msys2.bat
    goto end
) else (
    echo [ERROR] Neither Visual Studio C++ Toolchain nor MSYS2 is installed.
    echo Please install one of them or set the PATH correctly.
    echo You can also choose to run one of the following manually:
    echo 1 - Compile with Visual Studio (if installed)
    echo 2 - Compile with MinGW/MSYS2 (if installed - NOTE: must be installed in the default folder C:\msys64\msys2.exe)
    echo 0 or CTRL+C exits
    echo If you do not have any compiler, please download and install MSYS2,
    echo and call compile_cython.bat FROM THE VENV ENVIRONMENT (enter_in_venv.bat).

    set /p CHOICE="Enter your choice (1 or 2) or press any other key to exit: "

    if "%CHOICE%"=="1" (
        echo You chose to compile with Visual Studio. Please ensure it's installed.
        call compile_cython_vs.bat
    ) else if "%CHOICE%"=="2" (
        echo You chose to compile with MinGW/MSYS2. Please ensure it's installed.
        call compile_cython_msys2.bat
    ) else (
        echo Exiting the script.
    )
)

:end
echo.
echo [INFO] Script execution complete.

:: Activate virtual environment
echo venv\Scripts\activate.bat
call venv\Scripts\activate.bat
python -c "import brighteyes_mcs.libs.cython.fastconverter as fc;  print ('\n=======================================================================\nCython BrightEyes-MCS library has been installed correctly!! \n=======================================================================\n' if fc.convertRawDataToCountsDirect.__name__ == 'convertRawDataToCountsDirect' else 'Something went wrong during compilation of BrightEyes-MCS cython libraries')"

pause
