# BrightEyes-MCS

BrightEyes-MCS, a Microscope Control Software for image-scanning microscopy designed by the Molecular Microscopy and Spectroscopy group of the Italian Institute of Technology. 

For complete documentation, please visit our [Wiki page](https://github.com/VicidominiLab/BrightEyes-MCS/wiki).

[docs_video_brighteyes-mcs.webm](https://user-images.githubusercontent.com/61466143/202733339-2524c826-74d9-4ebc-8885-56855706200f.webm)

<!-- [![video session](docs/video/brighteyes-frame.png)](https://user-images.githubusercontent.com/61466143/202123174-e9019c5c-bc9c-403d-b710-0516af8346b9.webm) -->
**Click on the video**

## Quick Start

BrightEyes-MCS requires **Python 3.10 or newer**. Python **3.12 (64-bit)** is
recommended, although any compatible Python version from 3.10 onward should be
sufficient.

Use any environment manager you prefer, such as Python `venv`, Conda, uv, or
virtualenv. The following examples use the standard `venv` module.

### Install the `on_the_road_v2` version

To install the current `on_the_road_v2` branch directly from GitHub, make sure
Git is installed and use one of the following complete examples.

**PowerShell:**

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install "https://github.com/VicidominiLab/BrightEyes-MCS/archive/refs/heads/on_the_road_v2.zip"
python -m brighteyes_mcs
```

**Command Prompt (`cmd.exe`):**

```bat
py -3.12 -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install "https://github.com/VicidominiLab/BrightEyes-MCS/archive/refs/heads/on_the_road_v2.zip"
python -m brighteyes_mcs
```

### Install the PyPI release instead (AT MOMENT NOT AVAILABLE)

After creating and activating an environment as shown above, install the latest
published release with:

```console
python -m pip install brighteyes-mcs
python -m brighteyes_mcs
```

The remaining commands also work in either PowerShell or Command Prompt.

The first launch guides you through microscope-profile setup—including custom
plug-ins and scripts folders—optional firmware download, and Desktop shortcut
creation. To open the setup again later:

```console
python -m brighteyes_mcs --setup
```

Optional plug-in dependencies can be installed with:

```console
python -m pip install "brighteyes-mcs[ao]"    # serial-controlled AO hardware
python -m pip install "brighteyes-mcs[flim]"  # FLIM/DFD analysis
python -m pip install "brighteyes-mcs[all]"   # all optional plug-in dependencies
```

NI drivers and FPGA firmware are required for physical acquisition but are not
included in the Python package. See the
[Wiki](https://github.com/VicidominiLab/BrightEyes-MCS/wiki) for hardware setup
instructions.

## Compiled Extensions

The compiled extension modules are distributed separately as
`brighteyes-mcs-cylibs`. Pip installs a compatible wheel automatically as a
BrightEyes-MCS dependency; this repository does not compile them during
installation.

## Development

Project metadata and developer dependencies are defined in `pyproject.toml`:

```powershell
python -m pip install -e ".[dev]"
python -m pytest -q
python -m unittest test.test_channel_delay_skew_plugin -v
```

The second test command intentionally runs the PySide channel-delay widget tests
in a separate interpreter on Windows/Python 3.13. See
`docs/refactoring-architecture.md` for the package boundaries and compatibility
rules.

Maintainers can find the complete build, validation, TestPyPI, and Trusted
Publishing procedure in the
[PyPI release guide](https://github.com/VicidominiLab/BrightEyes-MCS/blob/main/docs/pypi-release.md).

## Development Notice

**Important:** This software is currently under active development and may contain bugs or incomplete features. Please use it with caution and report any issues you encounter to help us improve the application. 

For contribution guidelines, refer to
[CONTRIBUTING.md](https://github.com/VicidominiLab/BrightEyes-MCS/blob/main/CONTRIBUTING.md).

## License

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. This is free software, and you are welcome to redistribute it under certain conditions; this software code is licensed under the GNU General Public License version 3 or later (GPLv3+), with the exception of certain parts where a different license is specified. Please refer to the individual source files for details on specific licensing exceptions. See LICENSE.md file for details.



## Referencing BrightEyes-MCS

If this software is part of your research, please acknowledge it by citing:

- BrightEyes-MCS: a control software for multichannel scanning microscopy. _Donato et al._, Journal of Open Source Software (2024), 9(103), 7125, doi: https://doi.org/10.21105/joss.07125
