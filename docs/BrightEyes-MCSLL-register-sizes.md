# BrightEyes MCSLL register sizes

The 151 documented registers require an estimated **822 bytes** when each element uses a whole-byte container. Their combined logical width is **4751 bits**, equivalent to **594 bytes** if all bits are packed together.

Source: [register definitions](BrightEyes-MCSLL-registers.md). Fixed-point widths and array lengths use the local reference firmware `brighteyes_mcs/bitfiles/MCSV2-USB7856R-3_3V-40M91.lvbitx`. The four `L1` through `L4` registers use the documented U8 type because those names are absent from that bitfile.

## Sizing assumptions

- Boolean values use one byte per element in the whole-byte estimate.
- Integer and fixed-point values use the smallest 1, 2, 4, 8 or 16 byte container that holds each element.
- Axis offset and calibration arrays contain three elements each; circular scanning arrays contain 32 elements each; the shutter array contains five elements.
- Channel definitions are expanded for channels 0 through 7.
- These totals describe register values. They exclude FIFO buffers, register address gaps, alignment, transport overhead and Python object overhead. Firmware variants may have different widths or array lengths.

## Register table

| Section | Register | Type | Access | Elements | Bits per element | Total bits | Estimated bytes |
|---|---|---|---|---:|---:|---:|---:|
| Main | `start_command` | Bool | RW | 1 | 1 | 1 | 1 |
| Main | `stop_command` | Bool | RW | 1 | 1 | 1 | 1 |
| Main | `debug_scan_fsm_status` | I16 | R | 1 | 16 | 16 | 2 |
| Scan Settings | `time_bin_dwell_cycles` | I32 | RW | 1 | 32 | 32 | 4 |
| Scan Settings | `max_time_bins_per_pixel` | I32 | RW | 1 | 32 | 32 | 4 |
| Scan Settings | `max_pixel` | I32 | RW | 1 | 32 | 32 | 4 |
| Scan Settings | `max_line` | I32 | RW | 1 | 32 | 32 | 4 |
| Scan Settings | `max_frame` | I32 | RW | 1 | 32 | 32 | 4 |
| Scan Settings | `max_repetition` | I32 | RW | 1 | 32 | 32 | 4 |
| Scan Settings | `axis_start_offset_volts` | Fxp-Array | RW | 3 | 32 | 96 | 12 |
| Scan Settings | `axis_calibration_volts_per_step` | Fxp-Array | RW | 3 | 32 | 96 | 12 |
| Scan Settings | `xy_snake_scan_enable` | Bool | RW | 1 | 1 | 1 | 1 |
| Analog Output | `analog_output_0_volts` | Fxp | R | 1 | 32 | 32 | 4 |
| Analog Output | `analog_output_1_volts` | Fxp | R | 1 | 32 | 32 | 4 |
| Analog Output | `analog_output_2_volts` | Fxp | R | 1 | 32 | 32 | 4 |
| Analog Output | `analog_output_3_volts` | Fxp | R | 1 | 32 | 32 | 4 |
| Analog Output | `analog_output_4_volts` | Fxp | R | 1 | 32 | 32 | 4 |
| Analog Output | `analog_output_5_volts` | Fxp | R | 1 | 32 | 32 | 4 |
| Analog Output | `analog_output_6_volts` | Fxp | R | 1 | 32 | 32 | 4 |
| Analog Output | `analog_output_7_volts` | Fxp | R | 1 | 32 | 32 | 4 |
| Analog Output | `analog_output_0_source_selector` | U8 | RW | 1 | 8 | 8 | 1 |
| Analog Output | `analog_output_1_source_selector` | U8 | RW | 1 | 8 | 8 | 1 |
| Analog Output | `analog_output_2_source_selector` | U8 | RW | 1 | 8 | 8 | 1 |
| Analog Output | `analog_output_3_source_selector` | U8 | RW | 1 | 8 | 8 | 1 |
| Analog Output | `analog_output_4_source_selector` | U8 | RW | 1 | 8 | 8 | 1 |
| Analog Output | `analog_output_5_source_selector` | U8 | RW | 1 | 8 | 8 | 1 |
| Analog Output | `analog_output_6_source_selector` | U8 | RW | 1 | 8 | 8 | 1 |
| Analog Output | `analog_output_7_source_selector` | U8 | RW | 1 | 8 | 8 | 1 |
| Analog Output | `analog_output_0_dc_volts` | Fxp | RW | 1 | 20 | 20 | 4 |
| Analog Output | `analog_output_1_dc_volts` | Fxp | RW | 1 | 20 | 20 | 4 |
| Analog Output | `analog_output_2_dc_volts` | Fxp | RW | 1 | 20 | 20 | 4 |
| Analog Output | `analog_output_3_dc_volts` | Fxp | RW | 1 | 20 | 20 | 4 |
| Analog Output | `analog_output_4_dc_volts` | Fxp | RW | 1 | 20 | 20 | 4 |
| Analog Output | `analog_output_5_dc_volts` | Fxp | RW | 1 | 20 | 20 | 4 |
| Analog Output | `analog_output_6_dc_volts` | Fxp | RW | 1 | 20 | 20 | 4 |
| Analog Output | `analog_output_7_dc_volts` | Fxp | RW | 1 | 20 | 20 | 4 |
| Scanning Status | `current_line_parity_flag` | Bool | R | 1 | 1 | 1 | 1 |
| Scanning Status | `current_cycle_index` | I32 | R | 1 | 32 | 32 | 4 |
| Scanning Status | `current_time_bin_index` | I32 | R | 1 | 32 | 32 | 4 |
| Scanning Status | `current_x_index` | I32 | R | 1 | 32 | 32 | 4 |
| Scanning Status | `current_y_index` | I32 | R | 1 | 32 | 32 | 4 |
| Scanning Status | `current_z_index` | I32 | R | 1 | 32 | 32 | 4 |
| Scanning Status | `current_repetition_index` | I32 | R | 1 | 32 | 32 | 4 |
| Detection Configuration | `wait_initialization_time_in_us` | U32 | RW | 1 | 32 | 32 | 4 |
| Detection Configuration | `spad_configuration_message` | U64 | RW | 1 | 64 | 64 | 8 |
| Detection Configuration | `spad_configuration_message_length` | U8 | RW | 1 | 8 | 8 | 1 |
| Detection Configuration | `spad_sdata_invert_enable` | Bool | RW | 1 | 1 | 1 | 1 |
| Detection Configuration | `tag_clock_duration_cycles` | I64 | RW | 1 | 64 | 64 | 8 |
| Detection Configuration | `detector_fpga_holdoff_cycles` | U16 | RW | 1 | 16 | 16 | 2 |
| Detection Configuration | `dummy_data_enable` | Bool | RW | 1 | 1 | 1 | 1 |
| Laser Control | `wait_laser_startup_cycles` | I64 | RW | 1 | 64 | 64 | 8 |
| Laser Control | `wait_post_frame_cycles` | I64 | RW | 1 | 64 | 64 | 8 |
| Laser Control | `wait_laser_first_time_only_enable` | Bool | RW | 1 | 1 | 1 | 1 |
| Laser Control | `laser_off_after_measurement_enable` | Bool | RW | 1 | 1 | 1 | 1 |
| Circular Scanning Settings | `circular_scan_x_volts` | Fxp-Array | RW | 32 | 20 | 640 | 128 |
| Circular Scanning Settings | `circular_scan_y_volts` | Fxp-Array | RW | 32 | 20 | 640 | 128 |
| Circular Scanning Settings | `circular_scan_z_volts` | Fxp-Array | RW | 32 | 20 | 640 | 128 |
| Circular Scanning Settings | `circular_scan_enable` | Bool | RW | 1 | 1 | 1 | 1 |
| Scanning LImits | `max_x_volts` | Fxp | RW | 1 | 20 | 20 | 4 |
| Scanning LImits | `max_y_volts` | Fxp | RW | 1 | 20 | 20 | 4 |
| Scanning LImits | `max_z_volts` | Fxp | RW | 1 | 20 | 20 | 4 |
| Scanning LImits | `min_x_volts` | Fxp | RW | 1 | 20 | 20 | 4 |
| Scanning LImits | `min_y_volts` | Fxp | RW | 1 | 20 | 20 | 4 |
| Scanning LImits | `min_z_volts` | Fxp | RW | 1 | 20 | 20 | 4 |
| FIFO Settings | `stream_out_aux_enable` | Bool | RW | 1 | 1 | 1 | 1 |
| FIFO Settings | `stream_out_main_enable` | Bool | RW | 1 | 1 | 1 | 1 |
| FIFO Settings | `internal_fifo_analog_overflow_flag` | Bool | R | 1 | 1 | 1 | 1 |
| FIFO Settings | `internal_fifo_spad_overflow_flag` | Bool | R | 1 | 1 | 1 | 1 |
| FIFO Settings | `stream_out_aux_overflow_cycle_counter` | U64 | R | 1 | 64 | 64 | 8 |
| FIFO Settings | `stream_out_main_overflow_cycle_counter` | U64 | R | 1 | 64 | 64 | 8 |
| Laser Enable | `laser_1_enable` | Bool | RW | 1 | 1 | 1 | 1 |
| Laser Enable | `laser_2_enable` | Bool | RW | 1 | 1 | 1 | 1 |
| Laser Enable | `laser_3_enable` | Bool | RW | 1 | 1 | 1 | 1 |
| Laser Enable | `laser_4_enable` | Bool | RW | 1 | 1 | 1 | 1 |
| Analog Input | `analog_a_input_selector` | U8 | RW | 1 | 8 | 8 | 1 |
| Analog Input | `analog_b_input_selector` | U8 | RW | 1 | 8 | 8 | 1 |
| Analog Input | `analog_a_differential_mode_enable` | Bool | RW | 1 | 1 | 1 | 1 |
| Analog Input | `analog_b_differential_mode_enable` | Bool | RW | 1 | 1 | 1 | 1 |
| Analog Input | `analog_a_channel_0_invert_enable` | Bool | RW | 1 | 1 | 1 | 1 |
| Analog Input | `analog_a_channel_1_invert_enable` | Bool | RW | 1 | 1 | 1 | 1 |
| Analog Input | `analog_a_channel_2_invert_enable` | Bool | RW | 1 | 1 | 1 | 1 |
| Analog Input | `analog_a_channel_3_invert_enable` | Bool | RW | 1 | 1 | 1 | 1 |
| Analog Input | `analog_a_channel_4_invert_enable` | Bool | RW | 1 | 1 | 1 | 1 |
| Analog Input | `analog_a_channel_5_invert_enable` | Bool | RW | 1 | 1 | 1 | 1 |
| Analog Input | `analog_a_channel_6_invert_enable` | Bool | RW | 1 | 1 | 1 | 1 |
| Analog Input | `analog_a_channel_7_invert_enable` | Bool | RW | 1 | 1 | 1 | 1 |
| Analog Input | `analog_a_channel_0_integrate_enable` | Bool | RW | 1 | 1 | 1 | 1 |
| Analog Input | `analog_a_channel_1_integrate_enable` | Bool | RW | 1 | 1 | 1 | 1 |
| Analog Input | `analog_a_channel_2_integrate_enable` | Bool | RW | 1 | 1 | 1 | 1 |
| Analog Input | `analog_a_channel_3_integrate_enable` | Bool | RW | 1 | 1 | 1 | 1 |
| Analog Input | `analog_a_channel_4_integrate_enable` | Bool | RW | 1 | 1 | 1 | 1 |
| Analog Input | `analog_a_channel_5_integrate_enable` | Bool | RW | 1 | 1 | 1 | 1 |
| Analog Input | `analog_a_channel_6_integrate_enable` | Bool | RW | 1 | 1 | 1 | 1 |
| Analog Input | `analog_a_channel_7_integrate_enable` | Bool | RW | 1 | 1 | 1 | 1 |
| Analog Input | `analog_input_0_volts` | Fxp | R | 1 | 32 | 32 | 4 |
| Analog Input | `analog_input_1_volts` | Fxp | R | 1 | 32 | 32 | 4 |
| Analog Input | `analog_input_2_volts` | Fxp | R | 1 | 32 | 32 | 4 |
| Analog Input | `analog_input_3_volts` | Fxp | R | 1 | 32 | 32 | 4 |
| Analog Input | `analog_input_4_volts` | Fxp | R | 1 | 32 | 32 | 4 |
| Analog Input | `analog_input_5_volts` | Fxp | R | 1 | 32 | 32 | 4 |
| Analog Input | `analog_input_6_volts` | Fxp | R | 1 | 32 | 32 | 4 |
| Analog Input | `analog_input_7_volts` | Fxp | R | 1 | 32 | 32 | 4 |
| Digital Frequency Domain | `L1` | U8 | RW | 1 | 8 | 8 | 1 |
| Digital Frequency Domain | `L2` | U8 | RW | 1 | 8 | 8 | 1 |
| Digital Frequency Domain | `L3` | U8 | RW | 1 | 8 | 8 | 1 |
| Digital Frequency Domain | `L4` | U8 | RW | 1 | 8 | 8 | 1 |
| Digital Frequency Domain | `dfd_enable` | Bool | RW | 1 | 1 | 1 | 1 |
| Digital Frequency Domain | `dfd_dwell_time_cycles_120mhz` | U32 | RW | 1 | 32 | 32 | 4 |
| Digital Frequency Domain | `dfd_internal_dwell_time_enable` | Bool | RW | 1 | 1 | 1 | 1 |
| Digital Frequency Domain | `dfd_laser_sync_debug_enable` | Bool | RW | 1 | 1 | 1 | 1 |
| Digital Frequency Domain | `dfd_current_position_index` | Fxp | R | 1 | 22 | 22 | 4 |
| Digital Frequency Domain | `dfd_transmitted_position_index` | Fxp | R | 1 | 22 | 22 | 4 |
| Digital Frequency Domain | `dfd_acquisition_active_status` | Bool | R | 1 | 1 | 1 | 1 |
| Digital Frequency Domain | `internal_fifo_dfd_overflow_flag` | Bool | R | 1 | 1 | 1 | 1 |
| Costum Scanning Position | `custom_positions_last_pixelwise_address` | U32 | R | 1 | 32 | 32 | 4 |
| Costum Scanning Position | `custom_positions_last_framewise_address` | U32 | R | 1 | 32 | 32 | 4 |
| Costum Scanning Position | `custom_positions_stream_in_ready_flag` | Bool | R | 1 | 1 | 1 | 1 |
| Costum Scanning Position | `custom_positions_current_address` | U32 | R | 1 | 32 | 32 | 4 |
| Costum Scanning Position | `custom_positions_x_volts` | Fxp | R | 1 | 20 | 20 | 4 |
| Costum Scanning Position | `custom_positions_y_volts` | Fxp | R | 1 | 20 | 20 | 4 |
| Costum Scanning Position | `custom_positions_z_volts` | Fxp | R | 1 | 20 | 20 | 4 |
| Costum Scanning Position | `custom_positions_tx_begin_flag` | Bool | R | 1 | 1 | 1 | 1 |
| Costum Scanning Position | `custom_positions_extra_flag` | Bool | R | 1 | 1 | 1 | 1 |
| Costum Scanning Position | `custom_positions_update_mode_flag` | Bool | R | 1 | 1 | 1 | 1 |
| Costum Scanning Position | `custom_positions_tx_end_flag` | Bool | R | 1 | 1 | 1 | 1 |
| Costum Scanning Position | `custom_positions_offset_current_address` | U32 | R | 1 | 32 | 32 | 4 |
| Costum Scanning Position | `custom_positions_offset_x_volts` | Fxp | R | 1 | 20 | 20 | 4 |
| Costum Scanning Position | `custom_positions_offset_y_volts` | Fxp | R | 1 | 20 | 20 | 4 |
| Costum Scanning Position | `custom_positions_offset_z_volts` | Fxp | R | 1 | 20 | 20 | 4 |
| Costum Scanning Position | `custom_positions_offset_tx_begin_flag` | Bool | R | 1 | 1 | 1 | 1 |
| Costum Scanning Position | `custom_positions_offset_extra_flag` | Bool | R | 1 | 1 | 1 | 1 |
| Costum Scanning Position | `custom_positions_offset_update_mode_flag` | Bool | R | 1 | 1 | 1 | 1 |
| Costum Scanning Position | `custom_positions_offset_tx_end_flag` | Bool | R | 1 | 1 | 1 | 1 |
| Internal / Debug | `shutter_enable` | Bool-Array | RW | 5 | 1 | 5 | 5 |
| Internal / Debug | `debug_pixel_tag` | Bool | RW | 1 | 1 | 1 | 1 |
| Internal / Debug | `debug_line_tag` | Bool | RW | 1 | 1 | 1 | 1 |
| Internal / Debug | `debug_frame_tag` | Bool | RW | 1 | 1 | 1 | 1 |
| Internal / Debug | `debug_repetition_tag` | Bool | RW | 1 | 1 | 1 | 1 |
| Internal / Debug | `debug_end_of_frame_flag` | Bool | RW | 1 | 1 | 1 | 1 |
| Internal / Debug | `debug_line_counter` | I64 | RW | 1 | 64 | 64 | 8 |
| Internal / Debug | `tag_turnoff_pixel_counter` | I64 | R | 1 | 64 | 64 | 8 |
| Internal / Debug | `tag_turnoff_line_counter` | I64 | R | 1 | 64 | 64 | 8 |
| Internal / Debug | `tag_turnoff_frame_counter` | I64 | R | 1 | 64 | 64 | 8 |
| Internal / Debug | `debug_t` | I32 | RW | 1 | 32 | 32 | 4 |
| Internal / Debug | `debug_x_index` | I32 | RW | 1 | 32 | 32 | 4 |
| Internal / Debug | `debug_y_index` | I32 | RW | 1 | 32 | 32 | 4 |
| Internal / Debug | `debug_z_index` | I32 | RW | 1 | 32 | 32 | 4 |
| Internal / Debug | `debug_x_index_2` | I32 | RW | 1 | 32 | 32 | 4 |
| Internal / Debug | `debug_y_index_2` | I32 | RW | 1 | 32 | 32 | 4 |
| Internal / Debug | `debug_z_index_2` | I32 | RW | 1 | 32 | 32 | 4 |
| Internal / Debug | `debug_repetition_index` | I32 | RW | 1 | 32 | 32 | 4 |
| **Total** | **151 registers** | | | | | **4751** | **822** |

## Sum

Estimated whole-byte storage: **822 bytes**.

Packed minimum: `ceil(4751 / 8) = 594` bytes.
