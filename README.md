# BrightEyes-MCS

BrightEyes-MCS, a Microscope Control Software for image-scanning microscopy designed by the Molecular Microscopy and Spectroscopy group of the Italian Institute of Technology. 

Start with the [documentation index](docs/README.md) for user guides, developer
instructions, and technical references. Versioned documentation in this repository
is the source of truth.

[docs_video_brighteyes-mcs.webm](https://user-images.githubusercontent.com/61466143/202733339-2524c826-74d9-4ebc-8885-56855706200f.webm)

<!-- [![video session](docs/video/brighteyes-frame.png)](https://user-images.githubusercontent.com/61466143/202123174-e9019c5c-bc9c-403d-b710-0516af8346b9.webm) -->
**Click on the video**

## Quick Start

BrightEyes-MCS requires **Python 3.10 or newer**. Python **3.12 (64-bit)** is
recommended, although any compatible Python version from 3.10 onward should be
sufficient.

Use any environment manager you prefer, such as Python `venv`, Conda, uv, or
virtualenv. The following examples use the standard `venv` module.

### Install from a source checkout

Install Git and Python 3.12 (64-bit), then run in PowerShell:

```powershell
git clone https://github.com/VicidominiLab/BrightEyes-MCS.git
cd BrightEyes-MCS
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install .
python -m brighteyes_mcs
```

In Command Prompt, activate with `.venv\Scripts\activate.bat` instead.
To use a particular development branch, check it out before installing.

A published PyPI release has not been verified for this guide. Use the source
installation above; the [release guide](docs/pypi-release.md) describes the
maintainer publishing procedure, which is currently disabled.

The remaining commands also work in either PowerShell or Command Prompt.

The first launch guides you through microscope-profile setup—including custom
plug-ins and scripts folders—optional firmware download, and Desktop shortcut
creation. To open the setup again later:

```console
python -m brighteyes_mcs --setup
```

From the source checkout, optional plug-in dependencies can be installed with:

```console
python -m pip install ".[ao]"    # serial-controlled AO hardware
python -m pip install ".[flim]"  # FLIM/DFD analysis
python -m pip install ".[all]"   # all optional plug-in dependencies
```

NI drivers and FPGA firmware are required for physical acquisition but are not
included in the Python package. See the
[hardware reference](docs/BrightEyes-MCSLL-registers.md) for hardware setup
instructions.

## Compiled Extensions

The compiled extension modules are distributed separately as
`brighteyes-mcs-cylibs`. Pip installs a compatible wheel automatically as a
BrightEyes-MCS dependency; this repository does not compile them during
installation.

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for editable installation, test commands,
Qt UI generation, and documentation/lint checks. The [architecture guide](docs/current-architecture.md)
maps the code; [refactoring boundaries](docs/refactoring-architecture.md) describe
compatibility requirements.

Maintainers can find build validation and the proposed publishing procedure in
the [release guide](docs/pypi-release.md). Automatic publishing is disabled.

## Development Notice

**Important:** This software is currently under active development and may contain bugs or incomplete features. Please use it with caution and report any issues you encounter to help us improve the application. 

For contribution guidelines, refer to
[CONTRIBUTING.md](CONTRIBUTING.md).

## License

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. This is free software, and you are welcome to redistribute it under certain conditions; this software code is licensed under the GNU General Public License version 3 or later (GPLv3+), with the exception of certain parts where a different license is specified. Please refer to the individual source files for details on specific licensing exceptions. See LICENSE.md file for details.



## Referencing BrightEyes-MCS

If this software is part of your research, please acknowledge it by citing:

- BrightEyes-MCS: a control software for multichannel scanning microscopy. _Donato et al._, Journal of Open Source Software (2024), 9(103), 7125, doi: https://doi.org/10.21105/joss.07125
