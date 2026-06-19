# BrightEyes-MCS Installer

Standalone Tk/Tcl GUI used to install or update BrightEyes-MCS on Windows.

The runtime installer uses only the Python standard library. It is designed to be
packaged into a single `.exe` with PyInstaller.

## What It Does

- Installs the latest BrightEyes-MCS source from GitHub.
- Updates an existing BrightEyes-MCS installation with the same GUI.
- Creates or reuses the project `.venv`.
- Runs the project `installer.py` to install requirements and build Cython code.
- Can create desktop links and download firmware using the project scripts.
- Offers either Visual Studio Build Tools or MSYS2 UCRT64 as the compiler path.

## Compiler Choices

### Visual Studio Build Tools

If Visual Studio C++ Build Tools are missing, the GUI downloads the official
`vs_BuildTools.exe` bootstrapper and opens the normal Microsoft installer GUI.
Complete that installer, then run this installer again.

### MSYS2

Before silent MSYS2 installation, the GUI requires explicit acceptance of the
MSYS2/package license notice. It then uses `winget` to install MSYS2 silently and
installs the UCRT64 GCC package with `pacman`.

## Build The EXE

From this folder:

```bat
build_exe.bat
```

The executable will be written to:

```text
dist\BrightEyes-MCS-Installer.exe
```

PyInstaller is only a build-time dependency. The installer source itself has no
third-party runtime dependency.

## Manual Run

```bat
py -3.13 brighteyes_mcs_installer.py
```

BrightEyes-MCS itself still expects Python 3.13 for the managed project virtual
environment.
