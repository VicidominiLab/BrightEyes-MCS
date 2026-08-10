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
    ("Main", "start_command", "Bool", "RW", "Start the scanning"),
    ("Main", "stop_command", "Bool", "RW", "Stop the scanning"),
    ("Main", "debug_scan_fsm_status", "I16", "R", "Status of the FSM"),
    ("Scan Settings", "time_bin_dwell_cycles", "I32", "RW", "Wait Cycles per bin in 40MHz clk units (default: 40)"),
    ("Scan Settings", "max_time_bins_per_pixel", "I32", "RW", "Number of timebins per pixel"),
    ("Scan Settings", "max_pixel", "I32", "RW", "Number of pixel (X)"),
    ("Scan Settings", "max_line", "I32", "RW", "Number of lines (Y)"),
    ("Scan Settings", "max_frame", "I32", "RW", "Number of frames (Z)"),
    ("Scan Settings", "max_repetition", "I32", "RW", "Number of repetition (REP)"),
    ("Scan Settings", "axis_start_offset_volts", "Fxp-Array", "RW", "Array [x,y,z] offset in V"),
    ("Scan Settings", "axis_calibration_volts_per_step", "Fxp-Array", "RW", "Array [x,y,z] calibration in V/step"),
    ("Scan Settings", "xy_snake_scan_enable", "Bool", "RW", "If enabled the scanning is performed as snake-scanning else use the normal raster scanning (default: False)"),
    ("Analog Output", "analog_output_7_volts", "Fxp", "R", "Current Voltage on AnalogOUT"),
    ("Analog Output", "analog_output_7_source_selector", "U8", "RW", "0 => X, 1 => Y, 2 => Z, else constant DC value"),
    ("Analog Output", "analog_output_7_dc_volts", "Fxp", "RW", "Constant value for Analog Output"),
    ("Scanning Status", "current_line_parity_flag", "Bool", "R", "Current Parity Line (for snake)"),
    ("Scanning Status", "current_cycle_index", "I32", "R", "Current Cycle"),
    ("Scanning Status", "current_time_bin_index", "I32", "R", "Current timebin"),
    ("Scanning Status", "current_x_index", "I32", "R", "Current X"),
    ("Scanning Status", "current_y_index", "I32", "R", "Current Y"),
    ("Scanning Status", "current_z_index", "I32", "R", "Current Z"),
    ("Scanning Status", "current_repetition_index", "I32", "R", "Current Rep"),
    ("Detection Configuration", "wait_initialization_time_in_us", "U32", "RW", "SPAD configuration - time to wait before start acquisition"),
    ("Detection Configuration", "spad_configuration_message", "U64", "RW", "SPAD configuration message cmd send"),
    ("Detection Configuration", "spad_configuration_message_length", "U8", "RW", "SPAD configuration message length"),
    ("Detection Configuration", "spad_sdata_invert_enable", "Bool", "RW", "SPAD configuration invert the cmd logic (useful for some SPAD prototype)"),
    ("Detection Configuration", "tag_clock_duration_cycles", "I64", "RW", "SPAD configuration - sync output duration (40 MHz units)"),
    ("Detection Configuration", "detector_fpga_holdoff_cycles", "U16", "RW", "holdOff time (FPGA based) in 120 MHz units"),
    ("Detection Configuration", "dummy_data_enable", "Bool", "RW", "If enable produces dummy data instead of using data from the detector"),
    ("Laser Control", "wait_laser_startup_cycles", "I64", "RW", "Wait after turning on laser (in 40 MHz units)"),
    ("Laser Control", "wait_post_frame_cycles", "I64", "RW", "Wait after frame completation (in 40 MHz units)"),
    ("Laser Control", "wait_laser_first_time_only_enable", "Bool", "RW", "Wait after turning on laser only the first time"),
    ("Laser Control", "laser_off_after_measurement_enable", "Bool", "RW", "If active turn off the laser after a measurement"),
    ("Circular Scanning Settings", "circular_scan_x_volts", "Fxp-Array", "RW", "Array of Voltages X for circular scanning"),
    ("Circular Scanning Settings", "circular_scan_y_volts", "Fxp-Array", "RW", "Array of Voltages Y for circular scanning"),
    ("Circular Scanning Settings", "circular_scan_z_volts", "Fxp-Array", "RW", "Array of Voltages Z for circular scanning"),
    ("Circular Scanning Settings", "circular_scan_enable", "Bool", "RW", "Use the circular scan voltages or positions supplied through stream_in instead of raster scanning"),
    ("Scanning Limits", "max_x_volts", "Fxp", "RW", "Set Voltages Limits Max X Voltage"),
    ("Scanning Limits", "max_y_volts", "Fxp", "RW", "Set Voltages Limits Max Y Voltage"),
    ("Scanning Limits", "max_z_volts", "Fxp", "RW", "Set Voltages Limits Max Z Voltage"),
    ("Scanning Limits", "min_x_volts", "Fxp", "RW", "Set Voltages Limits Min X Voltage"),
    ("Scanning Limits", "min_y_volts", "Fxp", "RW", "Set Voltages Limits Min Y Voltage"),
    ("Scanning Limits", "min_z_volts", "Fxp", "RW", "Set Voltages Limits Min Z Voltage"),
    ("FIFO Settings", "stream_out_aux_enable", "Bool", "RW", "Activate the FIFO Analog"),
    ("FIFO Settings", "stream_out_main_enable", "Bool", "RW", "Activate the FIFO Digital"),
    ("FIFO Settings", "internal_fifo_analog_overflow_flag", "Bool", "R", "True when the internal analog FIFO overflows during the scan"),
    ("FIFO Settings", "internal_fifo_spad_overflow_flag", "Bool", "R", "True when the internal SPAD FIFO overflows during the scan"),
    ("FIFO Settings", "stream_out_aux_overflow_cycle_counter", "U64", "R", "Counter of overflow cycles for stream_out_aux"),
    ("FIFO Settings", "stream_out_main_overflow_cycle_counter", "U64", "R", "Counter of overflow cycles for stream_out_main"),
    ("Laser Enable", "laser_1_enable", "Bool", "RW", "Laser Enable 1"),
    ("Laser Enable", "laser_2_enable", "Bool", "RW", "Laser Enable 2"),
    ("Laser Enable", "laser_3_enable", "Bool", "RW", "Laser Enable 3"),
    ("Laser Enable", "laser_4_enable", "Bool", "RW", "Laser Enable 4"),
    ("Analog Input", "analog_a_input_selector", "U8", "RW", "Select the Analog input for Analog A channel"),
    ("Analog Input", "analog_b_input_selector", "U8", "RW", "Select the Analog input for Analog B channel"),
    ("Analog Input", "analog_a_differential_mode_enable", "Bool", "RW", "True: signal derivative during within the timebin; False: signal direct"),
    ("Analog Input", "analog_b_differential_mode_enable", "Bool", "RW", "True: signal derivative during within the timebin; False: signal direct"),
    ("Analog Input", "analog_a_channel_7_invert_enable", "Bool", "RW", "True: signal inverted; False: signal not inverted"),
    ("Analog Input", "analog_a_channel_7_integrate_enable", "Bool", "RW", "True: signal integrated; False: signal not integrated. The integration is performed at the max ADC readout speed"),
    ("Analog Input", "analog_input_7_volts", "Fxp", "R", "Current Voltage on AnalogIN"),
    ("Digital Frequency Domain", "L1", "U8", "RW", "A state of laser sync for DFD - AAA_AAA_BBB_BBB"),
    ("Digital Frequency Domain", "L2", "U8", "RW", "B state of laser sync for DFD - AAA_000_BBB_000"),
    ("Digital Frequency Domain", "L3", "U8", "RW", "C state of laser sync for DFD - AA0_0BB_00C_C00"),
    ("Digital Frequency Domain", "L4", "U8", "RW", "D state of laser sync for DFD - A00_B00_C00_D00"),
    ("Digital Frequency Domain", "dfd_enable", "Bool", "RW", "Activate the DFD"),
    ("Digital Frequency Domain", "dfd_dwell_time_cycles_120mhz", "U32", "RW", "Time interval for the transmission of full histogram (in 120MHz units) (Default: 1e6) <= usually not used"),
    ("Digital Frequency Domain", "dfd_internal_dwell_time_enable", "Bool", "RW", "False: use the pixel index parity for triggering the transmission of the DFD histogram; True: use the Dwell time set (Default: False)"),
    ("Digital Frequency Domain", "dfd_laser_sync_debug_enable", "Bool", "RW", "True: the channel 26 become the laser time reference; False: channel 26 is connected to the channel_extra1"),
    ("Digital Frequency Domain", "dfd_current_position_index", "Fxp", "R", "Status of the DFD current pixel"),
    ("Digital Frequency Domain", "dfd_transmitted_position_index", "Fxp", "R", "Status of the DFD current pixel transmitted"),
    ("Digital Frequency Domain", "dfd_acquisition_active_status", "Bool", "R", "Status of the DFD module if activated or not"),
    ("Digital Frequency Domain", "internal_fifo_dfd_overflow_flag", "Bool", "R", "Status of the overflow of the internal DFD FIFO"),
    ("Custom Scanning Position", "custom_positions_last_pixelwise_address", "U32", "R", "Internal use / Debug"),
    ("Custom Scanning Position", "custom_positions_last_framewise_address", "U32", "R", "Internal use / Debug"),
    ("Custom Scanning Position", "custom_positions_stream_in_ready_flag", "Bool", "R", "Internal use / Debug"),
    ("Custom Scanning Position", "custom_positions_current_address", "U32", "R", "Internal use / Debug"),
    ("Custom Scanning Position", "custom_positions_x_volts", "Fxp", "R", "Internal use / Debug"),
    ("Custom Scanning Position", "custom_positions_y_volts", "Fxp", "R", "Internal use / Debug"),
    ("Custom Scanning Position", "custom_positions_z_volts", "Fxp", "R", "Internal use / Debug"),
    ("Custom Scanning Position", "custom_positions_tx_begin_flag", "Bool", "R", "Internal use / Debug"),
    ("Custom Scanning Position", "custom_positions_extra_flag", "Bool", "R", "Internal use / Debug"),
    ("Custom Scanning Position", "custom_positions_update_mode_flag", "Bool", "R", "Internal use / Debug"),
    ("Custom Scanning Position", "custom_positions_tx_end_flag", "Bool", "R", "Internal use / Debug"),
    ("Custom Scanning Position", "custom_positions_offset_current_address", "U32", "R", "Internal use / Debug"),
    ("Custom Scanning Position", "custom_positions_offset_x_volts", "Fxp", "R", "Internal use / Debug"),
    ("Custom Scanning Position", "custom_positions_offset_y_volts", "Fxp", "R", "Internal use / Debug"),
    ("Custom Scanning Position", "custom_positions_offset_z_volts", "Fxp", "R", "Internal use / Debug"),
    ("Custom Scanning Position", "custom_positions_offset_tx_begin_flag", "Bool", "R", "Internal use / Debug"),
    ("Custom Scanning Position", "custom_positions_offset_extra_flag", "Bool", "R", "Internal use / Debug"),
    ("Custom Scanning Position", "custom_positions_offset_update_mode_flag", "Bool", "R", "Internal use / Debug"),
    ("Custom Scanning Position", "custom_positions_offset_tx_end_flag", "Bool", "R", "Internal use / Debug"),
    ("Internal / Debug", "shutter_enable", "Bool-Array", "RW", "Internal use / Debug"),
    ("Internal / Debug", "debug_pixel_tag", "Bool", "RW", "Internal use / Debug"),
    ("Internal / Debug", "debug_line_tag", "Bool", "RW", "Internal use / Debug"),
    ("Internal / Debug", "debug_frame_tag", "Bool", "RW", "Internal use / Debug"),
    ("Internal / Debug", "debug_repetition_tag", "Bool", "RW", "Internal use / Debug"),
    ("Internal / Debug", "debug_end_of_frame_flag", "Bool", "RW", "Internal use / Debug"),
    ("Internal / Debug", "debug_line_counter", "I64", "RW", "Internal use / Debug"),
    ("Internal / Debug", "tag_turnoff_pixel_counter", "I64", "R", "Internal use / Debug"),
    ("Internal / Debug", "tag_turnoff_line_counter", "I64", "R", "Internal use / Debug"),
    ("Internal / Debug", "tag_turnoff_frame_counter", "I64", "R", "Internal use / Debug"),
    ("Internal / Debug", "debug_t", "I32", "RW", "Internal use / Debug"),
    ("Internal / Debug", "debug_x_index", "I32", "RW", "Internal use / Debug"),
    ("Internal / Debug", "debug_y_index", "I32", "RW", "Internal use / Debug"),
    ("Internal / Debug", "debug_z_index", "I32", "RW", "Internal use / Debug"),
    ("Internal / Debug", "debug_x_index_2", "I32", "RW", "Internal use / Debug"),
    ("Internal / Debug", "debug_y_index_2", "I32", "RW", "Internal use / Debug"),
    ("Internal / Debug", "debug_z_index_2", "I32", "RW", "Internal use / Debug"),
    ("Internal / Debug", "debug_repetition_index", "I32", "RW", "Internal use / Debug"),
)

_CHANNEL_EXPANSIONS = {
    "analog_output_7_volts": "analog_output_{channel}_volts",
    "analog_output_7_source_selector": "analog_output_{channel}_source_selector",
    "analog_output_7_dc_volts": "analog_output_{channel}_dc_volts",
    "analog_a_channel_7_invert_enable": "analog_a_channel_{channel}_invert_enable",
    "analog_a_channel_7_integrate_enable": "analog_a_channel_{channel}_integrate_enable",
    "analog_input_7_volts": "analog_input_{channel}_volts",
}

FIFO_SPECS = (
    FifoSpec("stream_in", "write", "U64", "Custom positions written from PC to FPGA"),
    FifoSpec("stream_out_main", "read", "U64", "Digital SPAD data read from FPGA to PC"),
    FifoSpec("stream_out_aux", "read", "U64", "Analog input data read from FPGA to PC"),
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
