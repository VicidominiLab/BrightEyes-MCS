# BrightEyes-MCS

The BrightEyes Microscope Control Suite (BrightEyes-MCS) is a Python open-source software for controlling and operating your laser 
scanning microscope (LSM).
It provides a user-friendly interface to perform microscopy image or Fluorescence Correlation Spectroscopy (FCS) with a
25 channels detector array.

The software include a real-time preview and the possibility to pan the scanning area during the scouting phase; 
it allows to manage Z-stack imaging and time-lapsed imaging and to store the raw data in HDF5 format including also 
metadata (current configurations, extra information, users comments etc etc).

It provides a user-friendly interface to do microscopy with a 25 channels SPAD, 
the possibility to save the data in HDF5, moving the scanning area during the scouting, control the lasers, 
manage Z-stack imaging, time-lapsed imaging.      

Moreover, it can be integrated with the
[BrightEyes Time-Tagging Module](https://github.com/VicidominiLab/BrightEyes-TTM). This module allow to perform 
single-photon time-tagging microscopy therefore fluorescence spectroscopy, fluorescence lifetime imaging microscopy
(FLIM), and fluorescence lifetime correlation spectroscopy (FLFS) experiments.


[![video session](docs/video/brighteyes-frame.png)](docs/video/brighteyes-mcs.webm.mov)  
**Click on the video**

---

---

# Getting started

## Requirements
- Python 3.10
- Git
- NI FPGA drivers installed



We strongly suggest to use PyCharm IDE Community editions for install and develop the BrightEyes-MCS. PyCharm provides a easy graphical interfaces to donwload the source code, to create a virtual environment ("local interpreter") and to install automatically the requirements.txt. Note in any case you need to compile the Cython modules.

## Installation (with PyCharm)

- Open PyCharm Community Edition
- Close if other project 
  - "Get from VCS"
    - URL: ```https://gitlab.iit.it/mms/brighteyes-mcs.git```
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

```git clone https://gitlab.iit.it/mms/brighteyes-mcs.git```



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


# Hardware:
The hardware
## BrightEyes stand-alone
![image](docs/img/BrightEyes-NI.png)

## BrightEyes integrated with BrightEyes-TTM
![image](docs/img/BrightEyes-NI-with-TTM.png)





## Microscope:
Galvo, laser, etc etc...

## FPGA:
The microscope hardware is controlled by NI FPGA cards. BrightEyes-MCS is compatible either:

1. NI FPGA USB-7856
2. NI PXI-Chassis equipped with NI PXIE-7856R
3. NI PXI-Chassis equipped with NI PXIE-7856R + NI PXIE-7822R


The 1. and 2. system supports up-to 25 channels detector, the 3. support up-to 49 channels detector.
The low level code is released as LabView FPGA BitFile for each specific type of FPGA but with a common register / FIFOs interface in such way that for the software switching between FPGA is transparent. 

## I/O

The list below is for the NI USB-7856. 
In case of the NI PXIE-7856R `Connector0` correspond to `Connector1` and vice versa.

|                 | Connector        | I/O |
|-----------------|------------------|-----|
| SPAD CHANNEL 0  | `Connector0/DIO0`  | IN  |
| ...             | ...              | ... |
| SPAD CHANNEL 24 | `Connector0/DIO24` | IN  |
|                 |                  |     |
| SPAD ENABLE     | `Connector0/DIO25` | OUT |
| SPAD SCLK       | `Connector0/DIO26` | OUT |
| SPAD SDATA      | `Connector0/DIO27` | OUT |
|                 |                  |     |
| Vx              | `Connector1/AO0`   | OUT |
| Vy              | `Connector1/AO1`   | OUT |
| Vz              | `Connector1/AO2`   | OUT |
|                 |                  |     |
| PMT             | `Connector1/AI0`   | IN  |
| AnalogAI1       | `Connector1/AI1`   | IN  |
| AnalogAI2       | `Connector1/AI2`   | IN  |
| AnalogAI3       | `Connector1/AI3`   | IN  |
|                 |                  |     |
| Laser 0         | `Connector0/DIO28` | OUT |
| Laser 1         | `Connector0/DIO29` | OUT |
| Laser 2         | `Connector0/DIO30` | OUT |
| Laser 3         | `Connector0/DIO31` | OUT |
|                 |                  |     |
| Pixel sync.     | `Connector1/DIO5`  | OUT |
| Line sync.      | `Connector1/DIO6`  | OUT |
| Frame sync.     | `Connector1/DIO7`  | OUT |
|                 |                  |     |

 

# Software:
The software is complex as need to have a GUI interface, graphics, fast data processing and finally data saving.
Due to the high data-flux and the performace required the code uses multi process approach. This speeds up the data processing and data visualization but in the other hand is increase the complexity of the code.

The communication between process is not straightforward, but it is made by multiprocessing.Events, multiprocessing.Queue, multiprocessing.Dict and MemorySharedNumpyArray (multiprocessing.Array with some extra features).   
## Structure

The software is structured as follow:

- main.py:
   1. MainWindow.py
      - autocorrelator.pyx (Cython)
      - timeBinner (Cython)
   2. SpadFcsManager.py:
      - FpgaHandle.py:
         - FpgaHandleProcess.py (PROCESS)
      - DataPreProcess.py (PROCESS)
      - AcquisitionLoopProcess.py (PROCESS)
        - fastconverter.pyx (Cython)
        - autocorrelator.pyx (Cython)

### main.py
The main is simply the first part of the code. Here some detail some parameters are QT dark theme, application name and the MainWindow object is initialized.

### MainWindow.py
This is the core of the graphical user interface (GUI). Here object MainWindow is created and is populated by the graphical objects and the methods are "clicked", "moved" and many others are defined.
The GUI mainly designed actually with pyside2-designer and converted with pyside2-uic to Python script (guipyspadfcs.py) which is imported in this code.
The plots used in the GUI are from pyqtgraph libraries.

#### timeBinner.cpx
This is a Cython script to simply and faster the filling of a temporal plot.

### SpadFcsManager.py
This code provides the handle to control the acquisition. Ideally even without graphical interface this code would allows an used to control, acquire and save data.

### FpgaHandle.py and FpgaHandleProcess.py
The FpgaHandle is an interface to manage the FpgaHandelProcess. This last one is an interface to the NIFPGA library. Essentially there is an initialization part and the core is a "forever loop" where - if requested - FIFOs or written are read or written. The communication to this process is warranty by a Queue mechanism.

#### DataPreProcess.py
This module convert the data received from the FIFOs (through a Queue connected to FpgaHandleProcess) to an numpy array.

#### AcquisitionLoopProcess.py
It converts the data received from the DataPreProcess to an image by taking advantages the fastconverter.pyx. Moreover,  if requested. It is possible also to calculate the live correlation (FCS) throught the autocorrelator.pyx 

##### autocorrelator.pyx
It is a Cython code for calculating live the autocorrelation of a given data. The input samples can be added at anytime with any size. The result is an approximation of the autocorrelation curve.

##### fastconverter.pyx 
It is a Cython code used to convert the low level data format (defined in the NI FPGA code) to an numpy.array easier to manage with python.


