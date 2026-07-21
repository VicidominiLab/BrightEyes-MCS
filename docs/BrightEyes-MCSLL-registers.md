# BrightEyes-MCSLL
The BrightEyes Microscope Control Software Low-Level is a collections of firmwares for NI FPGA in order to be used with BrightEyes-MCS.
Documentation and usage you can find in [BrightEyes-MCS repository](https://github.com/VicidominiLab/BrightEyes-MCS).

**Copyright** (C) 2023 Istituto Italiano di Tecnologia

**Author:** Mattia Donato

**Credits to:** Marco Castello, Giorgio Tortarolo, Simonluca Piazza, Eli Slenders

**Closed-Source Firmware License Agreement:** This license grants you a non-exclusive, non-transferable permission to download and utilize our proprietary firmware free of charge. However, you are required to use this firmware exclusively in conjunction with open-source software, such as [BrightEyes-MCS](https://github.com/VicidominiLab/BrightEyes-MCS). Modifying, distributing, or employing it with closed-source software is strictly prohibited. We actively endorse and support the use of this firmware in educational institutions, including schools, universities, as well as in both public and private research organizations. All rights to the firmware are retained by us. The firmware is provided "as is" with absolutely no warranty. We disclaim all liability for any damages. This license may be terminated at your discretion or by us. Your use of the firmware signifies your agreement to this Agreement.

If you have bugs to report or you have requests for adding or modifying firmware functionalities, please feel free to contact us. We are open to collaborations!





# BrightEyes-MCS-LowLevel Firmwares

## I/O Table
|                                           | I/O    | USB-7856R<br>(Single-Board) | USB-7856R-OEM<br>(Single-Board) | PXIe-7856R<br>(Single-Board) | PCIe-7820R<br>(Single-Board) | PXIe-7856R<br>(Double-Board)<br>(Analog side) | PXIe-7822R<br>(Double-Board)<br>(Digital side) |
|-------------------------------------------|--------|-----------------------------|---------------------------------|------------------------------|:----------------------------:|:---------------------------------------------:|:----------------------------------------------:|
| SPAD CHANNEL 0                            | IN     | Connector0/DIO0             | Connector2/DIO0                 | Connector1/DIO0              | Connector1/DIO0              |                                               | Connector1/DIO0                                |
| ...                                       | ...    | ..                          | ..                              | ...                          | ...                          | ...                                           | ...                                            |
| SPAD CHANNEL 15                           | IN     | Connector0/DIO15            | Connector2/DIO15                | Connector1/DIO15             | Connector1/DIO15             |                                               | Connector1/DIO15                               |
| SPAD CHANNEL 16                           | IN     | Connector0/DIO16            | Connector3/DIO0                 | Connector1/DIO16             | Connector1/DIO16             |                                               | Connector1/DIO16                               |
| ...                                       | ...    | ...                         | ...                             | ...                          | ...                          | ...                                           | ...                                            |
| SPAD CHANNEL 24                           | IN     | Connector0/DIO24            | Connector3/DIO8                 | Connector1/DIO24             | Connector1/DIO24             |                                               | Connector1/DIO24                               |
|                                           |        |                             |                                 |                              |                              |                                               |                                                |
| SPAD ENABLE                               | OUT    | Connector0/DIO25            | Connector1/DIO12                | Connector1/DIO25             | Connector1/DIO25             |                                               | Connector1/DIO25                               |
| SPAD SCLK                                 | OUT    | Connector0/DIO26            | Connector1/DIO15                | Connector1/DIO26             | Connector2/DIO25             |                                               | Connector2/DIO25                               |
| SPAD SDATA                                | OUT    | Connector0/DIO27            | Connector1/DIO14                | Connector1/DIO27             | Connector2/DIO24             |                                               | Connector2/DIO24                               |
|                                           |        |                             |                                 |                              |                              |                                               |                                                |
| Laser 0                                   | OUT    | Connector0/DIO28            | Connector1/DIO0                 | Connector1/DIO28             | Connector1/DIO28             |                                               | Connector1/DIO28                               |
| Laser 1                                   | OUT    | Connector0/DIO29            | Connector1/DIO1                 | Connector1/DIO29             | Connector1/DIO29             |                                               | Connector1/DIO29                               |
| Laser 2                                   | OUT    | Connector0/DIO30            | Connector1/DIO2                 | Connector1/DIO30             | Connector1/DIO30             |                                               | Connector1/DIO30                               |
| Laser 3                                   | OUT    | Connector0/DIO31            | Connector1/DIO3                 | Connector1/DIO31             | Connector1/DIO31             |                                               | Connector1/DIO31                               |
|                                           |        |                             |                                 |                              |                              |                                               |                                                |
| AnalogINx                                 | IN     | Connector1/AIx              | Connector0/AIx                  | Connector0/AIx               |                              | Connector0/AIx                                |                                                |
| AnalogOUTx                                | OUT     | Connector1/AOx              | Connector0/AOx                  | Connector0/AOx               |                              | Connector0/AOx                                |                                                |
|                                           |        |                             |                                 |                              |                              |                                               |                                                |
| Pixel sync.                               | OUT    | Connector1/DIO5             | Connector1/DIO5                 | Connector0/DIO5              | Connector2/DIO29             |                                               | Connector2/DIO29                               |
| Line sync.                                | OUT    | Connector1/DIO6             | Connector1/DIO6                 | Connector0/DIO6              | Connector2/DIO30             |                                               | Connector2/DIO30                               |
| Frame sync.                               | OUT    | Connector1/DIO7             | Connector1/DIO7                 | Connector0/DIO7              | Connector2/DIO31             |                                               | Connector2/DIO31                               |
|                                           |        |                             |                                 |                              |                              |                                               |                                                |
| Debug OUT (Analog Output updated trigger) | OUT    | Connector1/DIO8             | Connector1/DI13                 | Connector0/DIO8              |                              | Connector0/DIO9                               |                                                |
|                                           |        |                             |                                 |                              |                              |                                               |                                                |
| Det_extra_0                               | IN     | Connector1/DIO0             | Connector3/DI9                  | Connector0/DIO0              | Connector1/DIO26             |                                               | Connector1/DIO26                               |
| Det_extra_1                               | IN     | Connector1/DIO1             | Connector3/DI10                 | Connector0/DIO1              | Connector1/DIO27             |                                               | Connector1/DIO27                               |
|                                           |        |                             |                                 |                              |                              |                                               |                                                |
| Laser Debug                               | OUT    | Connector1/DIO11            | Connector1/DIO9                 | Connector0/DIO11             |                              |                                               |                                                |
| Laser 0 (Duplicated)                      | OUT    | Connector1/DIO12            |                                 | Connector0/DIO12             |                              |                                               |                                                |
| Laser 1 (Duplicated)                      | OUT    | Connector1/DIO13            |                                 | Connector0/DIO13             |                              |                                               |                                                |
| Laser 2 (Duplicated)                      | OUT    | Connector1/DIO14            |                                 | Connector0/DIO14             |                              |                                               |                                                |
| Laser 3 (Duplicated)                      | OUT    | Connector1/DIO15            |                                 | Connector0/DIO15             |                              |                                               |                                                |
|                                           |        |                             |                                 |                              |                              |                                               |                                                |
| AD5764_SDATA                              | OUT    |                             |                                 |                              | Connector0/DIO26             |                                               | Connector0/DIO26                               |
| AD5764_SCLK                               | OUT    |                             |                                 |                              | Connector0/DIO27             |                                               | Connector0/DIO27                               |
| AD5764_SSYNC                              | OUT    |                             |                                 |                              | Connector0/DIO28             |                                               | Connector0/DIO28                               |
|                                           |        |                             |                                 |                              |                              |                                               |                                                |
| GI_DAC_ADC                                | IN/OUT |                             |                                 |                              | [Connector3]                 |                                               | [Connector3]                                   |


## Registers

| Name                           | Type       | Read/Write | Description                                                                                                                                      |
|--------------------------------|------------|------------|--------------------------------------------------------------------------------------------------------------------------------------------------|
| **Main**                       |            |            |                                                                                                                                                  |
| Run                            | Bool       | RW         | Start the scanning                                                                                                                               |
| stop                           | Bool       | RW         | Stop the scanning                                                                                                                                |
| FSM Status                     | I16        | R          | Status of the FSM                                                                                                                                |
|                                |            |            |                                                                                                                                                  |
| **Scan Settings**              |            |            |                                                                                                                                                  |
| Cx                             | I32        | RW         | Wait Cycles per bin in 40MHz clk units (default: 40)                                                                                             |
| #timebinsPerPixel              | I32        | RW         | Number of timebins per pixel                                                                                                                     |
| #pixels                        | I32        | RW         | Number of pixel (X)                                                                                                                              |
| #lines                         | I32        | RW         | Number of lines (Y)                                                                                                                              |
| #frames                        | I32        | RW         | Number of frames (Z)                                                                                                                             |
| #repetition                    | I32        | RW         | Number of repetition (REP)                                                                                                                       |
| Offset/StartValue (V)          | Fxp-Array  | RW         | Array [x,y,z] offset in V                                                                                                                        |
| CalibrationFactors(V/step)     | Fxp-Array  | RW         | Array [x,y,z] calibration in V/step                                                                                                              |
| snake                          | Bool       | RW         | If enabled the scanning is performed as "snake-scanning" else use the normal "raster scanning" (default: False)                                  |
|                                |            |            |                                                                                                                                                  |
| **Analog Output**              |            |            |                                                                                                                                                  |
| (for all channels from 0 to 7) |            |            |                                                                                                                                                  |
| AnalogOUT7                     | Fxp        | R          | Current Voltage on AnalogOUT                                                                                                                     |
| AnalogSelector_7               | U8         | RW         | 0 => X, 1 => Y, 2 => Z, else constant DC value                                                                                                   |
| AnalogOutDC_7                  | Fxp        | RW         | Constant value for Analog Output                                                                                                                 |
|                                |            |            |                                                                                                                                                  |
| **Scanning Status**            |            |            |                                                                                                                                                  |
| cur_parity                     | Bool       | R          | Current Parity Line (for snake)                                                                                                                  |
| cur_cycle                      | I32        | R          | Current Cycle                                                                                                                                    |
| cur_t                          | I32        | R          | Current timebin                                                                                                                                  |
| cur_x                          | I32        | R          | Current X                                                                                                                                        |
| cur_y                          | I32        | R          | Current Y                                                                                                                                        |
| cur_z                          | I32        | R          | Current Z                                                                                                                                        |
| cur_rep                        | I32        | R          | Current Rep                                                                                                                                      |
|                                |            |            |                                                                                                                                                  |
| **Detection Configuration**    |            |            |                                                                                                                                                  |
| initializationTime             | U32        | RW         | SPAD configuration - time to wait before start acquisition                                                                                       |
| msgOut                         | U64        | RW         | SPAD configuration message cmd send                                                                                                              |
| msgLen                         | U8         | RW         | SPAD configuration message length                                                                                                                |
| Invert SDATA                   | Bool       | RW         | SPAD configuration invert the cmd logic (useful for some SPAD prototype)                                                                         |
| ClockDur                       | I64        | RW         | SPAD configuration - sync output duration (40 MHz units)                                                                                         |
| holdOff                        | U16        | RW         | holdOff time (FPGA based) in 120 MHz units                                                                                                       |
| DummyData                      | Bool       | RW         | If enable produces dummy data instead of using data from the detector                                                                            |
|                                |            |            |                                                                                                                                                  |
| **Laser Control**              |            |            |                                                                                                                                                  |
| WaitForLaser                   | I64        | RW         | Wait after turning on laser (in 40 MHz units)                                                                                                    |
| WaitAfterFrame                 | I64        | RW         | Wait after frame completation (in 40 MHz units)                                                                                                  |
| WaitOnlyFirstTime              | Bool       | RW         | Wait after turning on laser only the first time                                                                                                  |
| LaserOffAfterMeasurement       | Bool       | RW         | If active turn off the laser after a measurement                                                                                                 |
|                                |            |            |                                                                                                                                                  |
| **Circular Scanning Settings** |            |            |                                                                                                                                                  |
| ScanXVoltages                  | Fxp-Array  | RW         | Array of Voltages X for circular scanning                                                                                                        |
| ScanYVoltages                  | Fxp-Array  | RW         | Array of Voltages Y for circular scanning                                                                                                        |
| ScanZVoltages                  | Fxp-Array  | RW         | Array of Voltages Z for circular scanning                                                                                                        |
| CircularMotionActivate         | Bool       | RW         | If activate instead of scanning will use the ScanXVoltages or the data as set via FIFOIn                                                         |
|                                |            |            |                                                                                                                                                  |
| **Scanning LImits**            |            |            |                                                                                                                                                  |
| MaxXVoltages                   | Fxp        | RW         | Set Voltages Limits Max X Voltage                                                                                                                |
| MaxYVoltages                   | Fxp        | RW         | Set Voltages Limits Max Y Voltage                                                                                                                |
| MaxZVoltages                   | Fxp        | RW         | Set Voltages Limits Max Z Voltage                                                                                                                |
| MinXVoltages                   | Fxp        | RW         | Set Voltages Limits Min X Voltage                                                                                                                |
| MinYVoltages                   | Fxp        | RW         | Set Voltages Limits Min Y Voltage                                                                                                                |
| MinZVoltages                   | Fxp        | RW         | Set Voltages Limits Min Z Voltage                                                                                                                |
|                                |            |            |                                                                                                                                                  |
| **FIFO Settings**              |            |            |                                                                                                                                                  |
| activateFIFOAnalog             | Bool       | RW         | Activate the FIFO Analog                                                                                                                         |
| activateFIFODigital            | Bool       | RW         | Activate the FIFO Digital                                                                                                                        |
| FIFOAnalog_Overflow            | Bool       | R          | True when at least once the FIFOAnalog failed during the scan                                                                                    |
| FIFO_Overflow                  | Bool       | R          | True when at least once the FIFO failed during the scan                                                                                          |
| FIFO Failed                    | U64        | R          | Counter of cycles when the FIFOAnalog failed during the scan                                                                                     |
| FIFOAnalog Failed              | U64        | R          | Counter of cycles when the FIFO failed during the scan                                                                                           |
|                                |            |            |                                                                                                                                                  |
| **Laser Enable**               |            |            |                                                                                                                                                  |
| LaserEnable0                   | Bool       | RW         | Laser Enable 1                                                                                                                                   |
| LaserEnable1                   | Bool       | RW         | Laser Enable 2                                                                                                                                   |
| LaserEnable2                   | Bool       | RW         | Laser Enable 3                                                                                                                                   |
| LaserEnable3                   | Bool       | RW         | Laser Enable 4                                                                                                                                   |
|                                |            |            |                                                                                                                                                  |
| **Analog Input**               |            |            |                                                                                                                                                  |
| AnalogInputA                   | U8         | RW         | Select the Analog input for Analog A channel                                                                                                     |
| AnalogInputB                   | U8         | RW         | Select the Analog input for Analog B channel                                                                                                     |
|                                |            |            |                                                                                                                                                  |
| AnalogA differential           | Bool       | RW         | True: signal derivative during within the timebin; False: signal direct                                                                          |
| AnalogB differential           | Bool       | RW         | True: signal derivative during within the timebin; False: signal direct                                                                          |
|                                |            |            |                                                                                                                                                  |
| (for all channels from 0 to 7) |            |            |                                                                                                                                                  |
| AnalogA7 invert                | Bool       | RW         | True: signal inverted; False: signal not inverted                                                                                                |
| AnalogA7 integrate             | Bool       | RW         | True: signal integrated; False: signal not integrated. The integration is performed at the max ADC readout speed                                 |
| AnalogIN7                      | Fxp        | R          | Current Voltage on AnalogIN                                                                                                                      |
|                                |            |            |                                                                                                                                                  |
| **Digital Frequency Domain**   |            |            |                                                                                                                                                  |
| L1                             | U8         | RW         | A state of laser sync for DFD - AAA_AAA_BBB_BBB                                                                                                  |
| L2                             | U8         | RW         | B state of laser sync for DFD - AAA_000_BBB_000                                                                                                  |
| L3                             | U8         | RW         | C state of laser sync for DFD - AA0_0BB_00C_C00                                                                                                  |
| L4                             | U8         | RW         | D state of laser sync for DFD - A00_B00_C00_D00                                                                                                  |
| DFD_Activate                   | Bool       | RW         | Activate the DFD                                                                                                                                 |
| DFD Dwell time (120MHz)        | U32        | RW         | Time interval for the transmission of full histogram (in 120MHz units) (Default: 1e6)  <= USUALLY NOT USED                                       |
| DFD_Uses_Own_Dwelltime         | Bool       | RW         | False: use the pixel index parity for triggering the transmission of the DFD histogram; True: use the Dwell time set (Default: False)            |
| DFD_LaserSyncDebug             | Bool       | RW         | True: the channel 26 become the laser time reference (needed for a proper phasor analysis); False: channel 26 is connected to the channel_extra1 |
| DFD_px_Current                 | Fxp        | R          | Status of the DFD current pixel                                                                                                                  |
| DFD_px_Transmitted             | Fxp        | R          | Status of the DFD current pixel transmitted                                                                                                      |
| DFD_FSM_Acquisition            | Bool       | R          | Status of the DFD module if activated or not                                                                                                     |
| DFD_FIFO_Overflow              | Bool       | R          | Status of the overflow of the internal DFD FIFO                                                                                                  |
|                                |            |            |                                                                                                                                                  |
| **Costum Scanning Position**   |            |            |                                                                                                                                                  |
| LastAddrPixelwise              | U32        | R          | Internal use / Debug                                                                                                                             |
| LastAddrFramewise              | U32        | R          | Internal use / Debug                                                                                                                             |
| FIFOPositionReady              | Bool       | R          | Internal use / Debug                                                                                                                             |
| position_curr_addr             | U32        | R          | Internal use / Debug                                                                                                                             |
| position_X                     | Fxp        | R          | Internal use / Debug                                                                                                                             |
| position_Y                     | Fxp        | R          | Internal use / Debug                                                                                                                             |
| position_Z                     | Fxp        | R          | Internal use / Debug                                                                                                                             |
| position_begin_tx              | Bool       | R          | Internal use / Debug                                                                                                                             |
| position_extra                 | Bool       | R          | Internal use / Debug                                                                                                                             |
| position_pixelwise-framewise   | Bool       | R          | Internal use / Debug                                                                                                                             |
| position_end_tx                | Bool       | R          | Internal use / Debug                                                                                                                             |
| offset_curr_addr               | U32        | R          | Internal use / Debug                                                                                                                             |
| offset_X                       | Fxp        | R          | Internal use / Debug                                                                                                                             |
| offset_Y                       | Fxp        | R          | Internal use / Debug                                                                                                                             |
| offset_Z                       | Fxp        | R          | Internal use / Debug                                                                                                                             |
| offset_begin_tx                | Bool       | R          | Internal use / Debug                                                                                                                             |
| offset_extra                   | Bool       | R          | Internal use / Debug                                                                                                                             |
| offset_pixelwise-framewise     | Bool       | R          | Internal use / Debug                                                                                                                             |
| offset_end_tx                  | Bool       | R          | Internal use / Debug                                                                                                                             |
|                                |            |            |                                                                                                                                                  |
| **Internal / Debug**           |            |            |                                                                                                                                                  |
| shutters                       | Bool-Array | RW         | Internal use / Debug                                                                                                                             |
| Pixel tag                      | Bool       | RW         | Internal use / Debug                                                                                                                             |
| Line tag                       | Bool       | RW         | Internal use / Debug                                                                                                                             |
| Frame tag                      | Bool       | RW         | Internal use / Debug                                                                                                                             |
| Repetition tag                 | Bool       | RW         | Internal use / Debug                                                                                                                             |
| End of frame                   | Bool       | RW         | Internal use / Debug                                                                                                                             |
| LC                             | I64        | RW         | Internal use / Debug                                                                                                                             |
| turnOffPC                      | I64        | R          | Internal use / Debug                                                                                                                             |
| turnOffLC                      | I64        | R          | Internal use / Debug                                                                                                                             |
| turnOffFC                      | I64        | R          | Internal use / Debug                                                                                                                             |
| t                              | I32        | RW         | Internal use / Debug                                                                                                                             |
| rx                             | I32        | RW         | Internal use / Debug                                                                                                                             |
| ry                             | I32        | RW         | Internal use / Debug                                                                                                                             |
| rz                             | I32        | RW         | Internal use / Debug                                                                                                                             |
| rx2                            | I32        | RW         | Internal use / Debug                                                                                                                             |
| ry2                            | I32        | RW         | Internal use / Debug                                                                                                                             |
| rz2                            | I32        | RW         | Internal use / Debug                                                                                                                             |
| rrep                           | I32        | RW         | Internal use / Debug                                                                                                                             |

## FIFOs:

| Type | Board      | Type | Read/Write | Tested                                             |
|------|------------|------|------------|----------------------------------------------------|
| 1    | FIFO In    | U64  | Write <br> \(from PC to FPGA\)      | Used only for the special case "custom positions"  |
| 2    | FIFO       | U64  | Read <br> \(from FPGA to PC\)      | Data from SPAD acquired from Digital Channels 25+2 |
| 3    | FIFOAnalog | U64  | Read <br> \(from FPGA to PC\)      | Data from selected Analog input A and B            |

### Data format:

#### Channels
Channels position on SPAD array 5x5.

|    |    |     |    |    |
|----|----|-----|----|----|
| 0  | 1  | 2   | 3  | 4  |
| 5  | 6  | 7   | 8  | 9  |
| 10 | 11  | 12  | 13  | 14  |
| 15 | 16  | 17   | 18  | 19  |
| 20 | 21  | 22   | 23  | 24  |

Moreover there are two extra channels called 25 and 26.

#### FIFO Digital
The micro-image is transmitted in a specific format made of two U64 words. 

Due to the physics of the system it has been assigned to the central elements more bits than the external ones. Here the table representing the number of bits for each channels.

Number of bit a channel:
|    |    |     |    |    |
|----|----|-----|----|----|
| 4  | 4  | 4   | 4  | 4  |
| 4  | 5  | 6   | 5  | 4  |
| 4  | 6  | 10  | 6  | 4  |
| 4  | 5  | 6   | 5  | 4  |
| 4  | 4  | 4   | 4  | 4  |

The micro-image is transmitted is trasmitted with the follwoing channels order:
- 1st word U64: 0, 1, 2, 3, 4, 5, 17, 18, 19, 20, 21, 22, 23, 24, 25. 
- 2nd word U64: 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 26.




#### FIFO Analog
A word of U64 the first U32 bits are corresponding to the Analog A, and the other U32 bits are corresponding to the Analog B.

