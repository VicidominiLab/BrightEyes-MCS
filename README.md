# BrightEyes-MCS

BrightEyes-MCS, a Microscope Control Software for image-scanning microscopy designed by the Molecular Microscopy and Spectroscopy group of the Italian Institute of Technology. 

For complete documentation, please visit our [Wiki page](https://github.com/VicidominiLab/BrightEyes-MCS/wiki).

[docs_video_brighteyes-mcs.webm](https://user-images.githubusercontent.com/61466143/202733339-2524c826-74d9-4ebc-8885-56855706200f.webm)

<!-- [![video session](docs/video/brighteyes-frame.png)](https://user-images.githubusercontent.com/61466143/202123174-e9019c5c-bc9c-403d-b710-0516af8346b9.webm) -->
**Click on the video**

## Quick Start

To get started, refer to the detailed instructions and guidelines available on the [Wiki](https://github.com/VicidominiLab/BrightEyes-MCS/wiki).

## Installer

BrightEyes-MCS now uses a single standalone stdlib installer:

```bat
python brighteyes_mcs_installer.py
```

Without arguments it opens the Tk GUI. The same file also works as a CLI:

```bat
python brighteyes_mcs_installer.py install
python brighteyes_mcs_installer.py install --source-branch main --source-commit <commit>
python brighteyes_mcs_installer.py update --stash-local
python brighteyes_mcs_installer.py update --branch main --commit <commit>
python brighteyes_mcs_installer.py firmware --firmware-branch main
python brighteyes_mcs_installer.py links
```

The installer finds local Python installations, requires Python 3.13 for the
project `.venv`, can download the Python 3.13.14 Windows installer from
python.org, suggests the Git for Windows download when git is missing, creates
shortcuts, downloads firmware from a selectable BrightEyes-MCSLL branch, and
installs or updates from a selected BrightEyes-MCS branch or commit. In the GUI,
the `BrightEyes-MCS source` group lists recent commits for the selected branch.
Updates preserve local `brighteyes_mcs/cfg` and `brighteyes_mcs/bitfiles`.

To build the small GUI executable:

```bat
build_installer_exe.bat
```

The build writes `brighteyes_mcs_installer.exe` in the repository root and
removes the temporary `dist/` folder. Install/update preserves that root exe if
it is already present.

## Compiled Extensions

The compiled extension modules are distributed separately as `brighteyes-mcs-cylibs`.
BrightEyes-MCS imports them from the installed pip package and no longer compiles
extensions from this repository during installation. The companion source package is
expected at `C:\Users\madonato\Documents\Git\BrightEyes-MCS-cylibs`.

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

## Development Notice

**Important:** This software is currently under active development and may contain bugs or incomplete features. Please use it with caution and report any issues you encounter to help us improve the application. 

For contribution guidelines, refer to the [contributing.md](CONTRIBUTING.md).

## License

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. This is free software, and you are welcome to redistribute it under certain conditions; this software code is licensed under the GNU General Public License version 3 (GPLv3), with the exception of certain parts where a different license is specified. Please refer to the individual source files for details on specific licensing exceptions. See LICENSE.md file for details.



## Referencing BrightEyes-MCS

If this software is part of your research, please acknowledge it by citing:

- BrightEyes-MCS: a control software for multichannel scanning microscopy. _Donato et al._, Journal of Open Source Software (2024), 9(103), 7125, doi: https://doi.org/10.21105/joss.07125
