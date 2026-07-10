"""Register metadata for the BrightEyes-MCS low-level FPGA firmware."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable


@dataclass(frozen=True)
class RegisterSpec:
    section: str
    name: str
    dtype: str
    access: str
    description: str
    attr: str

    @property
    def readable(self) -> bool:
        return "R" in self.access

    @property
    def writable(self) -> bool:
        return "W" in self.access


@dataclass(frozen=True)
class FifoSpec:
    name: str
    direction: str
    dtype: str
    description: str


_BASE_REGISTER_ROWS = (
    ("Main", "Run", "Bool", "RW", "Start the scanning"),
    ("Main", "stop", "Bool", "RW", "Stop the scanning"),
    ("Main", "FSM Status", "I16", "R", "Status of the FSM"),
    ("Scan Settings", "Cx", "I32", "RW", "Wait Cycles per bin in 40MHz clk units (default: 40)"),
    ("Scan Settings", "#timebinsPerPixel", "I32", "RW", "Number of timebins per pixel"),
    ("Scan Settings", "#pixels", "I32", "RW", "Number of pixel (X)"),
    ("Scan Settings", "#lines", "I32", "RW", "Number of lines (Y)"),
    ("Scan Settings", "#frames", "I32", "RW", "Number of frames (Z)"),
    ("Scan Settings", "#repetition", "I32", "RW", "Number of repetition (REP)"),
    ("Scan Settings", "Offset/StartValue (V)", "Fxp-Array", "RW", "Array [x,y,z] offset in V"),
    ("Scan Settings", "CalibrationFactors(V/step)", "Fxp-Array", "RW", "Array [x,y,z] calibration in V/step"),
    ("Scan Settings", "snake", "Bool", "RW", "If enabled the scanning is performed as snake-scanning else use the normal raster scanning (default: False)"),
    ("Analog Output", "AnalogOUT7", "Fxp", "R", "Current Voltage on AnalogOUT"),
    ("Analog Output", "AnalogSelector_7", "U8", "RW", "0 => X, 1 => Y, 2 => Z, else constant DC value"),
    ("Analog Output", "AnalogOutDC_7", "Fxp", "RW", "Constant value for Analog Output"),
    ("Scanning Status", "cur_parity", "Bool", "R", "Current Parity Line (for snake)"),
    ("Scanning Status", "cur_cycle", "I32", "R", "Current Cycle"),
    ("Scanning Status", "cur_t", "I32", "R", "Current timebin"),
    ("Scanning Status", "cur_x", "I32", "R", "Current X"),
    ("Scanning Status", "cur_y", "I32", "R", "Current Y"),
    ("Scanning Status", "cur_z", "I32", "R", "Current Z"),
    ("Scanning Status", "cur_rep", "I32", "R", "Current Rep"),
    ("Detection Configuration", "initializationTime", "U32", "RW", "SPAD configuration - time to wait before start acquisition"),
    ("Detection Configuration", "msgOut", "U64", "RW", "SPAD configuration message cmd send"),
    ("Detection Configuration", "msgLen", "U8", "RW", "SPAD configuration message length"),
    ("Detection Configuration", "Invert SDATA", "Bool", "RW", "SPAD configuration invert the cmd logic (useful for some SPAD prototype)"),
    ("Detection Configuration", "ClockDur", "I64", "RW", "SPAD configuration - sync output duration (40 MHz units)"),
    ("Detection Configuration", "holdOff", "U16", "RW", "holdOff time (FPGA based) in 120 MHz units"),
    ("Detection Configuration", "DummyData", "Bool", "RW", "If enable produces dummy data instead of using data from the detector"),
    ("Laser Control", "WaitForLaser", "I64", "RW", "Wait after turning on laser (in 40 MHz units)"),
    ("Laser Control", "WaitAfterFrame", "I64", "RW", "Wait after frame completation (in 40 MHz units)"),
    ("Laser Control", "WaitOnlyFirstTime", "Bool", "RW", "Wait after turning on laser only the first time"),
    ("Laser Control", "LaserOffAfterMeasurement", "Bool", "RW", "If active turn off the laser after a measurement"),
    ("Circular Scanning Settings", "ScanXVoltages", "Fxp-Array", "RW", "Array of Voltages X for circular scanning"),
    ("Circular Scanning Settings", "ScanYVoltages", "Fxp-Array", "RW", "Array of Voltages Y for circular scanning"),
    ("Circular Scanning Settings", "ScanZVoltages", "Fxp-Array", "RW", "Array of Voltages Z for circular scanning"),
    ("Circular Scanning Settings", "CircularMotionActivate", "Bool", "RW", "If activate instead of scanning will use the ScanXVoltages or the data as set via FIFOIn"),
    ("Scanning Limits", "MaxXVoltages", "Fxp", "RW", "Set Voltages Limits Max X Voltage"),
    ("Scanning Limits", "MaxYVoltages", "Fxp", "RW", "Set Voltages Limits Max Y Voltage"),
    ("Scanning Limits", "MaxZVoltages", "Fxp", "RW", "Set Voltages Limits Max Z Voltage"),
    ("Scanning Limits", "MinXVoltages", "Fxp", "RW", "Set Voltages Limits Min X Voltage"),
    ("Scanning Limits", "MinYVoltages", "Fxp", "RW", "Set Voltages Limits Min Y Voltage"),
    ("Scanning Limits", "MinZVoltages", "Fxp", "RW", "Set Voltages Limits Min Z Voltage"),
    ("FIFO Settings", "activateFIFOAnalog", "Bool", "RW", "Activate the FIFO Analog"),
    ("FIFO Settings", "activateFIFODigital", "Bool", "RW", "Activate the FIFO Digital"),
    ("FIFO Settings", "FIFOAnalog_Overflow", "Bool", "R", "True when at least once the FIFOAnalog failed during the scan"),
    ("FIFO Settings", "FIFO_Overflow", "Bool", "R", "True when at least once the FIFO failed during the scan"),
    ("FIFO Settings", "FIFO Failed", "U64", "R", "Counter of cycles when the FIFOAnalog failed during the scan"),
    ("FIFO Settings", "FIFOAnalog Failed", "U64", "R", "Counter of cycles when the FIFO failed during the scan"),
    ("Laser Enable", "LaserEnable0", "Bool", "RW", "Laser Enable 1"),
    ("Laser Enable", "LaserEnable1", "Bool", "RW", "Laser Enable 2"),
    ("Laser Enable", "LaserEnable2", "Bool", "RW", "Laser Enable 3"),
    ("Laser Enable", "LaserEnable3", "Bool", "RW", "Laser Enable 4"),
    ("Analog Input", "AnalogInputA", "U8", "RW", "Select the Analog input for Analog A channel"),
    ("Analog Input", "AnalogInputB", "U8", "RW", "Select the Analog input for Analog B channel"),
    ("Analog Input", "AnalogA differential", "Bool", "RW", "True: signal derivative during within the timebin; False: signal direct"),
    ("Analog Input", "AnalogB differential", "Bool", "RW", "True: signal derivative during within the timebin; False: signal direct"),
    ("Analog Input", "AnalogA7 invert", "Bool", "RW", "True: signal inverted; False: signal not inverted"),
    ("Analog Input", "AnalogA7 integrate", "Bool", "RW", "True: signal integrated; False: signal not integrated. The integration is performed at the max ADC readout speed"),
    ("Analog Input", "AnalogIN7", "Fxp", "R", "Current Voltage on AnalogIN"),
    ("Digital Frequency Domain", "L1", "U8", "RW", "A state of laser sync for DFD - AAA_AAA_BBB_BBB"),
    ("Digital Frequency Domain", "L2", "U8", "RW", "B state of laser sync for DFD - AAA_000_BBB_000"),
    ("Digital Frequency Domain", "L3", "U8", "RW", "C state of laser sync for DFD - AA0_0BB_00C_C00"),
    ("Digital Frequency Domain", "L4", "U8", "RW", "D state of laser sync for DFD - A00_B00_C00_D00"),
    ("Digital Frequency Domain", "DFD_Activate", "Bool", "RW", "Activate the DFD"),
    ("Digital Frequency Domain", "DFD Dwell time (120MHz)", "U32", "RW", "Time interval for the transmission of full histogram (in 120MHz units) (Default: 1e6) <= usually not used"),
    ("Digital Frequency Domain", "DFD_Uses_Own_Dwelltime", "Bool", "RW", "False: use the pixel index parity for triggering the transmission of the DFD histogram; True: use the Dwell time set (Default: False)"),
    ("Digital Frequency Domain", "DFD_LaserSyncDebug", "Bool", "RW", "True: the channel 26 become the laser time reference; False: channel 26 is connected to the channel_extra1"),
    ("Digital Frequency Domain", "DFD_px_Current", "Fxp", "R", "Status of the DFD current pixel"),
    ("Digital Frequency Domain", "DFD_px_Transmitted", "Fxp", "R", "Status of the DFD current pixel transmitted"),
    ("Digital Frequency Domain", "DFD_FSM_Acquisition", "Bool", "R", "Status of the DFD module if activated or not"),
    ("Digital Frequency Domain", "DFD_FIFO_Overflow", "Bool", "R", "Status of the overflow of the internal DFD FIFO"),
    ("Custom Scanning Position", "LastAddrPixelwise", "U32", "R", "Internal use / Debug"),
    ("Custom Scanning Position", "LastAddrFramewise", "U32", "R", "Internal use / Debug"),
    ("Custom Scanning Position", "FIFOPositionReady", "Bool", "R", "Internal use / Debug"),
    ("Custom Scanning Position", "position_curr_addr", "U32", "R", "Internal use / Debug"),
    ("Custom Scanning Position", "position_X", "Fxp", "R", "Internal use / Debug"),
    ("Custom Scanning Position", "position_Y", "Fxp", "R", "Internal use / Debug"),
    ("Custom Scanning Position", "position_Z", "Fxp", "R", "Internal use / Debug"),
    ("Custom Scanning Position", "position_begin_tx", "Bool", "R", "Internal use / Debug"),
    ("Custom Scanning Position", "position_extra", "Bool", "R", "Internal use / Debug"),
    ("Custom Scanning Position", "position_pixelwise-framewise", "Bool", "R", "Internal use / Debug"),
    ("Custom Scanning Position", "position_end_tx", "Bool", "R", "Internal use / Debug"),
    ("Custom Scanning Position", "offset_curr_addr", "U32", "R", "Internal use / Debug"),
    ("Custom Scanning Position", "offset_X", "Fxp", "R", "Internal use / Debug"),
    ("Custom Scanning Position", "offset_Y", "Fxp", "R", "Internal use / Debug"),
    ("Custom Scanning Position", "offset_Z", "Fxp", "R", "Internal use / Debug"),
    ("Custom Scanning Position", "offset_begin_tx", "Bool", "R", "Internal use / Debug"),
    ("Custom Scanning Position", "offset_extra", "Bool", "R", "Internal use / Debug"),
    ("Custom Scanning Position", "offset_pixelwise-framewise", "Bool", "R", "Internal use / Debug"),
    ("Custom Scanning Position", "offset_end_tx", "Bool", "R", "Internal use / Debug"),
    ("Internal / Debug", "shutters", "Bool-Array", "RW", "Internal use / Debug"),
    ("Internal / Debug", "Pixel tag", "Bool", "RW", "Internal use / Debug"),
    ("Internal / Debug", "Line tag", "Bool", "RW", "Internal use / Debug"),
    ("Internal / Debug", "Frame tag", "Bool", "RW", "Internal use / Debug"),
    ("Internal / Debug", "Repetition tag", "Bool", "RW", "Internal use / Debug"),
    ("Internal / Debug", "End of frame", "Bool", "RW", "Internal use / Debug"),
    ("Internal / Debug", "LC", "I64", "RW", "Internal use / Debug"),
    ("Internal / Debug", "turnOffPC", "I64", "R", "Internal use / Debug"),
    ("Internal / Debug", "turnOffLC", "I64", "R", "Internal use / Debug"),
    ("Internal / Debug", "turnOffFC", "I64", "R", "Internal use / Debug"),
    ("Internal / Debug", "t", "I32", "RW", "Internal use / Debug"),
    ("Internal / Debug", "rx", "I32", "RW", "Internal use / Debug"),
    ("Internal / Debug", "ry", "I32", "RW", "Internal use / Debug"),
    ("Internal / Debug", "rz", "I32", "RW", "Internal use / Debug"),
    ("Internal / Debug", "rx2", "I32", "RW", "Internal use / Debug"),
    ("Internal / Debug", "ry2", "I32", "RW", "Internal use / Debug"),
    ("Internal / Debug", "rz2", "I32", "RW", "Internal use / Debug"),
    ("Internal / Debug", "rrep", "I32", "RW", "Internal use / Debug"),
)

_CHANNEL_EXPANSIONS = {
    "AnalogOUT7": "AnalogOUT{channel}",
    "AnalogSelector_7": "AnalogSelector_{channel}",
    "AnalogOutDC_7": "AnalogOutDC_{channel}",
    "AnalogA7 invert": "AnalogA{channel} invert",
    "AnalogA7 integrate": "AnalogA{channel} integrate",
    "AnalogIN7": "AnalogIN{channel}",
}

FIFO_SPECS = (
    FifoSpec("FIFO In", "write", "U64", "Custom positions written from PC to FPGA"),
    FifoSpec("FIFO", "read", "U64", "Digital SPAD data read from FPGA to PC"),
    FifoSpec("FIFOAnalog", "read", "U64", "Analog input data read from FPGA to PC"),
)


def _iter_expanded_rows() -> Iterable[tuple[str, str, str, str, str]]:
    for section, name, dtype, access, description in _BASE_REGISTER_ROWS:
        template = _CHANNEL_EXPANSIONS.get(name)
        if template is None:
            yield section, name, dtype, access, description
            continue

        for channel in range(8):
            expanded_name = template.format(channel=channel)
            expanded_description = f"{description} channel {channel}"
            yield section, expanded_name, dtype, access, expanded_description


def _snake_case_register_name(name: str) -> str:
    text = name.replace("#", "number ")
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", text)
    text = re.sub(r"[^0-9A-Za-z]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_").lower()
    if not text:
        text = "unnamed"
    if text[0].isdigit():
        text = f"r_{text}"
    return f"reg_{text}"


def _make_register_specs() -> tuple[RegisterSpec, ...]:
    used_attrs: dict[str, int] = {}
    specs: list[RegisterSpec] = []
    for section, name, dtype, access, description in _iter_expanded_rows():
        base_attr = _snake_case_register_name(name)
        attr_index = used_attrs.get(base_attr, 0)
        used_attrs[base_attr] = attr_index + 1
        attr = base_attr if attr_index == 0 else f"{base_attr}_{attr_index + 1}"
        specs.append(RegisterSpec(section, name, dtype, access, description, attr))
    return tuple(specs)


REGISTER_SPECS = _make_register_specs()
REGISTER_SPECS_BY_NAME = {spec.name: spec for spec in REGISTER_SPECS}
REGISTER_SPECS_BY_ATTR = {spec.attr: spec for spec in REGISTER_SPECS}
REGISTER_ATTR_BY_NAME = {spec.name: spec.attr for spec in REGISTER_SPECS}
