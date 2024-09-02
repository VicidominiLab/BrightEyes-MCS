# BrightEyes-MCS

BrightEyes-MCS, a Microscope Control Software for image-scanning microscopy designed by the Molecular Microscopy and Spectroscopy group of the Italian Institute of Technology.

[docs_video_brighteyes-mcs.webm](https://user-images.githubusercontent.com/61466143/202733339-2524c826-74d9-4ebc-8885-56855706200f.webm)

<!-- [![video session](docs/video/brighteyes-frame.png)](https://user-images.githubusercontent.com/61466143/202123174-e9019c5c-bc9c-403d-b710-0516af8346b9.webm) -->
**Click on the video**

Main Features
--------

- Realtime preview
- Support up 25 digital channels (SPAD array) + 2 "extra" channel
- Support up 2 analog channels (PMT)
- Pan & Zoom in realtime
- Scan along each axis and XYZ multi-stack
- Time lapse / Macro
- Data saved in HDF5 with metadata (current configurations, extra information, users comments etc etc).
  - The saved data can be analyzed with Napari (through Napari-ISM plugin) just by a few click
- The pixel is subdivided in temporal bins:
  - Normal acquisition down-to:
    - 0.5 us for USB hardware
    - 0.25 us for Chassis Thunderbolt configuration
  - Histogram TCSPC, via Digital Frequency Domain techniques
      - 0.4 ns for bins
- Integrated Jupyter Python Console for inspecting or acting on the running program
- Plugins / Scripting in Python
  - Automatic grid analysis for calibration
- Fluorescence correlation spectroscopy Preview
- Integrated with BrightEyes-Time Tagging Module



Moreover, it can be integrated with the
[BrightEyes Time-Tagging Module](https://github.com/VicidominiLab/BrightEyes-TTM). This module allow to perform 
single-photon time-tagging microscopy therefore fluorescence spectroscopy, fluorescence lifetime imaging microscopy
(FLIM), and fluorescence lifetime correlation spectroscopy (FLFS) experiments.

---

![image](docs/img/BrightEyes-NI.png)

---

# License

This program is distributed in the hope that it will be useful, 
but WITHOUT ANY WARRANTY; without even the implied warranty of 
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. 
This is free software, and you are welcome to redistribute it
under certain conditions; this software code is licensed under
the **GNU General Public License version 3** (GPLv3), with the 
exception of certain parts where a different license is specified.
Please refer to the individual source files for details on specific 
licensing exceptions.
See [LICENSE.md](LICENSE.md) file for details.


# Credits

**Author:** Mattia Donato

The authors are thanked for their valuable contributions. Below is a breakdown of the parts they have contributed to and the list of contributors.
- **BrightEyes-MCS-LowLevel**: Marco Castello, Giorgio Tortarolo, Simonluca Piazza, Mattia Donato, Eli Slenders
- **MemorySharedNumpyArray**: Sami Valtteri Koho 
- **FCS Live Preview**: Eli Slenders
- **Scripts examples (shift vectors, grid calibration, ffs analysis)**: Alessandro Zunino, Eli Slenders
- **Scientific QT Spinbox**: Luca Bega

**Scientific team**: 
[Molecular Microscopy and Spectroscopy](https://vicidominilab.github.io/), Istituto Italiano di Tecnologia:
  - **Giuseppe Vicidomini** _(Principal Investigator)_
  - Luca Bega
  - Andrea Bucci
  - Mattia Donato
  - Francesco Fersini
  - Giacomo Garre'
  - Marcus Held
  - Sanket Patil
  - Eleonora Perego
  - Marco Scotto
  - Eli Slenders
  - Sabrina Zappone
  - Alessandro Zunino



# Reference
- A robust and versatile platform for image scanning microscopy enabling super-resolution FLIM. _Castello, M., Tortarolo, G., Buttafava, M. et al._ Nature Methods 16, 175–178 (2019). doi: https://doi.org/10.1038/s41592-018-0291-9


- A Compact and Effective Photon-Resolved Image Scanning Microscope. _Giorgio Tortarolo, Alessandro Zunino, Simonluca Piazza, Mattia Donato, Sabrina Zappone, Agnieszka Pierzyńska-Mach, Marco Castello, Giuseppe Vicidomini_ 
bioRxiv 2023.07.28.549477; doi: https://doi.org/10.1101/2023.07.28.549477



---

# Requirements
## Hardware
BrightEyes-MCS supports only FPGA from NI. At the moment the bitfile are built for the following boards.

| Type | Board                                              | Extra req.                  | Tested                                      |
|------|----------------------------------------------------|-----------------------------|---------------------------------------------|
| 1    | NI FPGA PXIe-7856 (Single-board)                   | NI Chassis + NI Thunderbolt | Full supported, currently in use in our lab |
| 2    | NI FPGA USB-7856R (Single-board)                   | -                           | Full supported, currently in use in our lab |
| 3    | NI FPGA USB-7856R OEM (Single-board)               | -                           | Should work but not fully tested            |
| 4    | NI FPGA PXIe-7822 + NI FPGA PXIe-7856 (Dual-board) | NI Chassis + NI Thunderbolt | Full supported, currently in use in our lab |
| 4    | NI FPGA PXIe-7822 (Single-board)                   |  NI Chassis + NI Thunderbolt +  External DAC required       | Full supported, currently in use in our lab |
| 5    | NI FPGA PCIe-7820R                                 | External DAC required       | Full supported, currently in use in our lab |

**Warning!! To avoid any damage of your equipment, please verify that the pinout described in I/O Table are compatible with your actual system.**

## Software
- Python 3.10 ( https://www.python.org/downloads/ )
- Git ( https://desktop.github.com/ )
- NI FPGA drivers installed ( https://www.ni.com/en/support/downloads/software-products/download.labview-fpga-module.html )
- A C compiler:
  - [MSYS2](https://www.msys2.org/), we strongly suggest it as open-source project. Please install it in the default folder and after the installation remind to install `gcc` on MSYS2 terminal with the command `pacman -S mingw-w64-ucrt-x86_64-gcc`.
  - Otherwise you can use Microsoft Visual Studio (with development C++ build).


If you are a normal user jump to "Installation (for user)"

Otherwise if you are a developer, we strongly suggest to use PyCharm IDE Community editions ( https://www.jetbrains.com/pycharm/download ) for install and develop the BrightEyes-MCS.

PyCharm provides a easy graphical interfaces to donwload the source code, to create a virtual environment ("local interpreter") and to install automatically the requirements.txt. Note in any case you need to compile the Cython modules.



## Firmware
**IMPORTANT**
The firmwares needed for running the NI FPGA are not included in the BrightEyes-MCS tree.
It is present during the installation phase a graphical tool to download and extract them.
In case of issues it is possible download directly from the repository of [BrightEyes-MCSLL](https://github.com/VicidominiLab/BrightEyes-MCSLL).

## I/O table
The I/O table depeands by the firmware. The tables are available on the documentations of [BrightEyes-MCSLL](https://github.com/VicidominiLab/BrightEyes-MCSLL)

# Getting started


## Installation (for user)
Download the Zip from the repository. Extract it where you prefer.
Be sure to have Python 3.10 installed.

Then run the command 
```
install.bat
```
and following the instructions on the terminal.

Once installed you will have the link with icon of BrightEyes-MCS and on your Desktop.

---

## Installation (for developer / with PyCharm)

- Open PyCharm Community Edition
- Close if other project 
  - "Get from VCS"
    - URL: ```https://github.com/VicidominiLab/BrightEyes-MCS.git```
    - Clone
- File -> Settings -> Project: brighteyes-mcs -> Python Interpreter
  - gear button (setting) -> Add
    - Virtualenv Environment  -> New environment 
      - Base interpreter select Python 3.10
      - OK
    - OK
- Add configuration
  - Add new -> Python 
  - Module -> select ```brighteyes_mcs```
- Select ```brighteyes-mcs/brighteyes-mcs/__main__.py```
- It will appers "Package requirement '....'" -> Install requirements
- Wait the installation of the packages
- Terminal
    - ```python setup.py build_ext --inplace --force``` 
- Once the file are compiled 
- Click play button




### Installation (Manual) 

Get the source tree:

```git clone https://github.com/VicidominiLab/BrightEyes-MCS.git```



Create the virtual environment:

```cd brighteyes-mcs```

```python -m venv venv```

Activate the environment 

```venv\Scripts\activate.bat``` (if you use cmd.exe)

```.\venv\Scripts\activate.ps1``` (if you use powershell)

Install requirements:

```pip install -r requirements.txt ```

Compile the Cython modules:

```python setup.py build_ext --inplace --force```

Run BrightEyes-MCS:

```run-brighteys-mcs.bat```

