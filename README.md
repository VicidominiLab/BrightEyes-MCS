# BrightEyes-MCS

BrightEyes-MCS is microscope control software for image-scanning microscopy,
developed by the Molecular Microscopy and Spectroscopy group at Istituto Italiano
di Tecnologia (Italian Institute of Technology).

[Documentation](docs/README.md) · [Report an issue](https://github.com/VicidominiLab/BrightEyes-MCS/issues) · [Watch the demo](https://user-images.githubusercontent.com/61466143/202733339-2524c826-74d9-4ebc-8885-56855706200f.webm)

## Contents

- [Quick Start](#quick-start)
- [First launch and configuration](#first-launch-and-configuration)
- [Detector support](#detector-support)
- [Logging and diagnostics](#logging-and-diagnostics)
- [Documentation and development](#development)
- [Referencing BrightEyes-MCS](#referencing-brighteyes-mcs)
- [License](#license)

## Quick Start

BrightEyes-MCS requires **Python 3.10 or newer**. Python **3.12 (64-bit)** is
recommended, although any compatible Python version from 3.10 onward should be
sufficient.

Use any environment manager you prefer, such as Python `venv`, Conda, uv, or
virtualenv. The following examples use the standard `venv` module.

NI drivers and FPGA firmware are required for physical acquisition but are not
included in the Python package. See the
[hardware reference](docs/BrightEyes-MCSLL-registers.md) for hardware setup
instructions.

### Temporary installation from the development branch

The current development branch is **`on_the_road_v2`**. Until this work is
released, install it directly from GitHub. Install Git and Python 3.12 (64-bit),
then run in PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install "git+https://github.com/VicidominiLab/BrightEyes-MCS.git@on_the_road_v2"
python -m brighteyes_mcs
```

In Command Prompt, activate with `.venv\Scripts\activate.bat` instead.
This installs the latest commit pushed to the branch.

To update, close BrightEyes-MCS, activate the same environment, and run:

```console
python -m pip install --upgrade --force-reinstall "git+https://github.com/VicidominiLab/BrightEyes-MCS.git@on_the_road_v2"
python -m brighteyes_mcs
```

`--force-reinstall` refreshes the installed code even when the branch's package
version has not changed. See the [pip installation options](https://pip.pypa.io/en/stable/cli/pip_install/#cmdoption-force-reinstall).

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

A published PyPI release has not been verified for this guide. Use the branch
or source installation above; the [release guide](docs/pypi-release.md) describes the
maintainer publishing procedure, which is currently disabled.

### Optional plug-in dependencies

From the source checkout, optional plug-in dependencies can be installed with:

```console
python -m pip install ".[ao]"    # serial-controlled AO hardware
python -m pip install ".[flim]"  # FLIM/DFD analysis
python -m pip install ".[all]"   # all optional plug-in dependencies
```

### Compiled Extensions

The compiled extension modules are distributed separately as
`brighteyes-mcs-cylibs`. Pip installs a compatible wheel automatically as a
BrightEyes-MCS dependency; this repository does not compile them during
installation.

## First launch and configuration

The first launch guides you through microscope-profile setup—including custom
plug-ins and scripts folders—optional firmware download, and Desktop shortcut
creation. To open the setup again later:

```console
python -m brighteyes_mcs --setup
```

## Detector support

BrightEyes-MCS was originally developed for SPAD arrays interfaced directly at the hardware level, with each pixel’s TTL output read by the BrightEyes-MCS FPGA. The Genoa Instruments PRISM-Light has been the most widely used detector in this configuration. Support for the Pi Imaging SPAD23R was added later through a high-level TCP/IP protocol that communicates with Pi Imaging’s pSPAD software.

Detector support was implemented for our own acquisition workflows and does not constitute a characterization or certification of any detector. Performance observed with BrightEyes-MCS depends on the complete experimental setup, including acquisition settings and firmware, and should not be interpreted as representative of a detector’s intrinsic or maximum achievable performance. For detector specifications, refer to the respective manufacturer’s documentation.

PRISM-Light, SPAD23R, and pSPAD are trademarks or product names of their respective owners.

## Logging and diagnostics

Logging defaults to level **2 (Verbose)**. Select the level at launch:

```console
python -m brighteyes_mcs --log-level 2
```

| Level | Log contents |
| --- | --- |
| 0 — No log | No application log files or crash dumps are written. |
| 1 — Normal | Normal application messages, warnings, errors and crash diagnostics. |
| 2 — Verbose (default) | Normal logs plus user input and the first action handler, with action IDs, completion and failure records. Includes buttons, settings and plot navigation. |
| 3 — Extremely Verbose | All of the above plus data-flow debug messages, PI SPAD23R receive/decode/batch details, and the RAW recorder's `--verbose` diagnostics. |

`--verbosity` is an alias for `--log-level`. The legacy `debug` argument still
selects the unstable window mode independently of log verbosity.

### Log files and location

Open **Load / Save Cfg → Open log folder** to see the logs. On Windows the default
folder is `%LOCALAPPDATA%\BrightEyes-MCS\log` (falling back to `%APPDATA%`, or
`./log` elsewhere); `BRIGHTEYES_LOG_DIR` can override it. The GUI, workers and
threads share **one `mcs-log-<session>.log` file**. Workers inherit the selected
level and session; each normal entry identifies its PID, process name, thread
and action. Existing logs keep their original names.

### Crash recovery and limitations

Complete records (including Python tracebacks) are serialized by an OS lock
that recovers when a writer dies. Acquisition processes and threads are unchanged;
there is no logging queue or collector that must survive to save the last records.
If another writer holds the lock for more than 100 ms, that record is skipped
with a bounded stderr notice so logging contention does not stall acquisition.
Storage/formatting failures also remain isolated from application actions.
Native fatal-crash stacks append directly to the same file without waiting for
the lock; during a crash, their lines can interleave with other process output.

Each normal record is flushed when written;
completed records survive an application crash or forced process exit, and log
files are not deleted at shutdown. Power loss, failed storage, or termination
during a write can still lose the last record. Level 0 does not write logs.
For PI SPAD23R failure analysis, keep the session log: it includes recorder
commands/output, exit codes, worker tracebacks and native-crash stacks when available.
Level 3 can generate large logs and affect acquisition performance.

## Development

Start with the [documentation index](docs/README.md) for user guides and technical
references. Versioned documentation in this repository is the source of truth.

See [CONTRIBUTING.md](CONTRIBUTING.md) for editable installation, test commands,
Qt UI generation, and documentation/lint checks. The [architecture guide](docs/current-architecture.md)
maps the code; [refactoring boundaries](docs/refactoring-architecture.md) describe
compatibility requirements.

Maintainers can find build validation and the proposed publishing procedure in
the [release guide](docs/pypi-release.md). Automatic publishing is disabled.

### Development Notice

**Important:** This software is currently under active development and may contain bugs or incomplete features. Please use it with caution and report any issues you encounter to help us improve the application. 

For contribution guidelines, refer to
[CONTRIBUTING.md](CONTRIBUTING.md).

## Referencing BrightEyes-MCS

If this software is part of your research, please acknowledge it by citing:

- BrightEyes-MCS: a control software for multichannel scanning microscopy. _Donato et al._, Journal of Open Source Software (2024), 9(103), 7125, doi: https://doi.org/10.21105/joss.07125

## License

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. This is free software, and you are welcome to redistribute it under certain conditions; this software code is licensed under the GNU General Public License version 3 or later (GPLv3+), with the exception of certain parts where a different license is specified. Please refer to the individual source files for details on specific licensing exceptions. See [LICENSE.md](LICENSE.md) for details.
