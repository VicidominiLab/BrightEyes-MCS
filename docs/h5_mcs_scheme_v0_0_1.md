# BrightEyes-MCS HDF5 Output Schema

This document describes the HDF5 files written by `brighteyes_mcs`.
It is based on the current writer implementation in `brighteyes_mcs/libs/h5manager.py`,
the acquisition loop in `brighteyes_mcs/libs/processes/acquisition_loop_process.py`,
the RAW converter in `brighteyes_mcs/libs/raw_acquisition_converter.py`, and the
sample tree printed by the last cell of `datah5.ipynb`.

## Top-Level Layout

Normal acquisition files have this structure when the digital FIFO is enabled:

```text
/
  attrs:
    default = "data"
    data_format_version = "0.0.1"
    comment = <user comment>

  data                         uint16, shape=(R, Z, Y, X, Td, C)
  data_channels_extra          uint8,  shape=(R, Z, Y, X, Td, 2)
  data_analog                  int32,  shape=(R, Z, Y, X, Ta, 2)   optional
  thumbnail                    vlen uint8 JPEG, shape=(1,)         optional

  configurationSpadFCSmanager/ attrs only
  configurationFPGA/            attrs only
  configurationGUI/             attrs only
  configurationGUI_beforeStart/ attrs only
  rawStreamAcquisition/         attrs only                         RAW mode only
```

Observed sample from `datah5.ipynb`:

```text
/data                shape=(1, 1, 512, 512, 91, 25) dtype=uint16
/data_channels_extra shape=(1, 1, 512, 512, 91, 2)  dtype=uint8
/thumbnail           shape=(1,) dtype=object
```

The file currently does not attach attributes to the data datasets themselves;
metadata are stored as root attributes and group attributes.

In this document, numeric metadata meanings start with a unit prefix when the
value has physical units, for example `[um]`, `[us]`, `[V]`, or `[40 MHz clock
cycles]`. No prefix means the value is dimensionless, a count, an index, a flag,
or an enumerated selector.

## Axis And Shape Conventions

Dataset axes are ordered as:

```text
(repetition, z_frame, y_line, x_pixel, time_bin, channel)
```

The dimension names are derived from FPGA register metadata:

| Symbol | Source attribute | Meaning |
| --- | --- | --- |
| `X` | `#pixels` | Number of pixels along x. |
| `Y` | `#lines` | Number of scan lines along y. |
| `Z` | `#frames` | Number of z frames. |
| `R` | `#repetition - 1` | Number of saved repetitions. The GUI writes FPGA `#repetition` as GUI repetitions plus one. |
| `Ta` | `#timebinsPerPixel * #circular_rep * #circular_points` | Effective analog time-bin count. |
| `Td` | `Ta // clk_multiplier` | Effective digital time-bin count. `clk_multiplier` is a runtime DFD decimation factor; in normal H5 files it is not a standard root/group attribute, so the dataset shape is authoritative. RAW metadata files store it in `/rawStreamAcquisition.attrs`. |
| `C` | `25` or `49` | Number of SPAD channels, selected by the GUI channel mode and related to `49_enable`. |

## Data Datasets

| Path | Required when | Dtype | Shape | Contents |
| --- | --- | --- | --- | --- |
| `/data` | Digital FIFO (`FIFO`) is active | `uint16` | `(R, Z, Y, X, Td, C)` | Photon counts decoded from the digital FIFO. The last axis is the 25- or 49-channel detector index. |
| `/data_channels_extra` | Digital FIFO (`FIFO`) is active | `uint8` | `(R, Z, Y, X, Td, 2)` | Two decoded auxiliary digital channels. For 25-channel decoding these are the low 5-bit fields of the two digital FIFO words; for 49-channel decoding they are the two auxiliary decoded indices after the 49 detector channels. The channel-delay-skew plugin may refer to this as `data_channel_extra`. |
| `/data_analog` | Analog FIFO (`FIFOAnalog`) is active | `int32` | `(R, Z, Y, X, Ta, 2)` | Two analog FIFO channels decoded from raw analog words. The analog path is not reduced by `clk_multiplier`. |
| `/thumbnail` | Normal, non-RAW acquisition with preview available | variable-length `uint8` | `(1,)` | JPEG bytes exported from the preview image at about 200 px width. Omitted in preview-less RAW metadata files. |

## Root Attributes

| Attribute | Type | Meaning |
| --- | --- | --- |
| `default` | string | Always written as `"data"` by `H5Manager.metadata_add_initial()`. |
| `data_format_version` | string | Current writer value is `"0.0.1"`. |
| `comment` | string | User comment captured at acquisition finalization before the GUI comment field is cleared. This is the authoritative acquisition comment. |

## Metadata Storage Rules

Metadata groups are plain HDF5 groups; their metadata are stored in `.attrs`.
The helper `H5Manager.metadata_add_dict(group_name, mydict)` writes one attribute
per dictionary entry and skips values that are `None`.

Type conversion rules:

| Python value | HDF5 attribute representation |
| --- | --- |
| `list` | Converted to a NumPy `float64` array. |
| `decimal.Decimal` | Converted to `float`. |
| `dict` | Converted to `str(dict)`. This affects `/configurationGUI.attrs["plugins"]`. |
| Other non-`None` values | Written directly through h5py, commonly as string, NumPy bool, NumPy integer, NumPy float, or NumPy array. |

## `/configurationSpadFCSmanager.attrs`

This group is written from `spadfcsmanager_inst.registers_configuration`.
It is the live register/configuration dictionary held by the acquisition manager
after the FPGA registers have been read or set. The RAW converter uses this group
for dimensions and timing metadata.

Important attributes:

| Attribute | Meaning |
| --- | --- |
| `#pixels`, `#lines`, `#frames`, `#repetition` | Scan dimensions used to derive `(R, Z, Y, X)`. |
| `#timebinsPerPixel`, `#circular_rep`, `#circular_points` | Time-bin and circular scanning factors used to derive `Ta` and `Td`. |
| `Cx` | [40 MHz clock cycles] Time-resolution register. In the current GUI code, `Cx = time_resolution [us] * 40`; the manager's `time_resolution` is computed as `Cx / clock_base`. |
| `ClockDur` | [clock cycles] Pixel clock-duration register. In the current GUI code, `ClockDur = #timebinsPerPixel * time_resolution [us] * clock_base / 2`. |
| `49_enable` | Whether the 49-channel detector layout is selected. |
| `activateFIFODigital`, `activateFIFOAnalog`, `FIFO_Overflow`, `FIFOAnalog_Overflow`, `FIFO Failed`, `FIFOAnalog Failed` | FIFO enable/status registers and diagnostics. |
| `DFD_Activate`, `DFDnBins`, `DFD_Trig_Selector`, `DFD_LaserSyncDebug`, `DFD_Uses_Own_Dwelltime`, `DFD Dwell time (120MHz)` | DFD acquisition metadata. `DFDnBins` is a bin count; `DFD Dwell time (120MHz)` is in 120 MHz clock cycles. |
| `snake`, `snake_z` | Bidirectional scanning flags used when mapping FIFO samples to pixels. |
| `CalibrationFactors(V/step)`, `Offset/StartValue (V)`, `ScanXVoltages`, `ScanYVoltages`, `ScanZVoltages` | [V/step], [V], [V] Scan calibration factors, starting voltages, and scan waveform arrays. |
| `MinXVoltages`, `MinYVoltages`, `MinZVoltages`, `MaxXVoltages`, `MaxYVoltages`, `MaxZVoltages` | [V] Scanner voltage limits. |
| `WaitForLaser`, `WaitAfterFrame` | [40 MHz clock cycles] Laser-start delay and inter-frame/inter-repetition delay registers. The GUI stores the corresponding user-facing values in seconds as `/configurationGUI.attrs["waitForLaser"]` and `/configurationGUI.attrs["waitAfterFrame"]`. |
| `LaserEnable0` through `LaserEnable3`, `LaserOffAfterMeasurement`, `WaitOnlyFirstTime` | Laser enable and wait-control flags. |
| `cur_x`, `cur_y`, `cur_z`, `cur_t`, `cur_rep`, `cur_circ_point`, `cur_circ_rep`, `cur_cycle`, `cur_parity` | Runtime/current FPGA counters captured in the register dictionary. |

Observed register attribute names in the sample file:

```text
#circular_points, #circular_rep, #frames, #lines, #pixels, #repetition,
#timebinsPerPixel, 49_enable, AnalogA differential, AnalogA0 integrate,
AnalogA0 invert, AnalogA1 integrate, AnalogA1 invert, AnalogA2 integrate,
AnalogA2 invert, AnalogA3 integrate, AnalogA3 invert, AnalogA4 integrate,
AnalogA4 invert, AnalogA5 integrate, AnalogA5 invert, AnalogA6 integrate,
AnalogA6 invert, AnalogA7 integrate, AnalogA7 invert, AnalogB differential,
AnalogIN0, AnalogIN1, AnalogIN2, AnalogIN3, AnalogIN4, AnalogIN5, AnalogIN6,
AnalogIN7, AnalogInputA, AnalogInputB, AnalogOUT0, AnalogOUT1, AnalogOUT2,
AnalogOUT3, AnalogOUT4, AnalogOUT5, AnalogOUT6, AnalogOUT7, AnalogOutDC_0,
AnalogOutDC_1, AnalogOutDC_2, AnalogOutDC_3, AnalogOutDC_4, AnalogOutDC_5,
AnalogOutDC_6, AnalogOutDC_7, AnalogSelector_0, AnalogSelector_1,
AnalogSelector_2, AnalogSelector_3, AnalogSelector_4, AnalogSelector_5,
AnalogSelector_6, AnalogSelector_7, CalibrationFactors(V/step),
Circular Repetition tag, CircularMotionActivate, ClockDur,
CustomPos_FIFOPositionReady, CustomPos_LastAddrFramewise,
CustomPos_LastAddrPixelwise, CustomPos_offset_X, CustomPos_offset_Y,
CustomPos_offset_Z, CustomPos_offset_begin_tx, CustomPos_offset_curr_addr,
CustomPos_offset_end_tx, CustomPos_offset_extra,
CustomPos_offset_pixelwise-framewise, CustomPos_position_X,
CustomPos_position_Y, CustomPos_position_Z, CustomPos_position_begin_tx,
CustomPos_position_curr_addr, CustomPos_position_end_tx,
CustomPos_position_extra, CustomPos_position_pixelwise-framewise, Cx,
DFD Dwell time (120MHz), DFD_Activate, DFD_FIFO_Overflow,
DFD_FSM_Acquisition, DFD_LaserSyncDebug, DFD_Trig_Selector,
DFD_Uses_Own_Dwelltime, DFD_px_Current, DFD_px_Transmitted, DFDnBins,
DummyData, End of frame, Ext_clk, FIFO Failed, FIFOAnalog Failed,
FIFOAnalog_Overflow, FIFO_Overflow, FLAG_ExtDAC, FLAG_Force25,
FLAG_GI_DAC_ADC, FSM Status, Frame tag, GI_DAC_ADC_ShortCableMode,
Invert SDATA, LC, LaserEnable0, LaserEnable1, LaserEnable2, LaserEnable3,
LaserNumberTimeBinCurrent, LaserOffAfterMeasurement, Line tag,
MaxXVoltages, MaxYVoltages, MaxZVoltages, MinXVoltages, MinYVoltages,
MinZVoltages, Offset/StartValue (V), Pixel tag,
Redirect_intensity_to_FIFOAnalog, Repetition tag, Run, ScanXVoltages,
ScanYVoltages, ScanZVoltages, SlaveMode, SlaveModeTestGen, SlaveMode_Count,
SlaveMode_CountMax, SlaveMode_PxEmulated, UseCustomPositions, VR0, VR1,
WaitAfterFrame, WaitForLaser, WaitOnlyFirstTime, activateFIFOAnalog,
activateFIFODigital, activateLaserTimeBin, circ_point, circ_rep,
cur_circ_point, cur_circ_rep, cur_cycle, cur_parity, cur_rep, cur_t, cur_x,
cur_y, cur_z, excitation sequence, ext_px_selector, holdOff,
initializationTime, maxLaserTimeBin, msgLen, msgOut,
ratio freq_fast/freq_exc, rrep, rx, rx2, ry, ry2, rz, rz2, shutters, snake,
snake_z, stop, t, turnOffFC, turnOffLC, turnOffPC
```

The exact set can vary with FPGA bitfile/register availability.

## `/configurationFPGA.attrs`

This group is written from the GUI-side `configurationFPGA_dict`.
It records the FPGA configuration accumulated by the GUI and then updated with
the manager's register dictionary immediately before acquisition. In the sample
file, it has the same 178 attribute names as `/configurationSpadFCSmanager.attrs`.

Use this group to inspect what the GUI intended to program; use
`/configurationSpadFCSmanager.attrs` as the manager/live-register view used by
the conversion code.

## `/configurationGUI.attrs`

This group is written from `MainWindow.getGUI_data()` at finalization, after the
root `comment` is captured and the GUI comment field is cleared. Therefore,
`/configurationGUI.attrs["comment"]` may be empty even when `/.attrs["comment"]`
contains the acquisition comment.

| Attribute | Meaning |
| --- | --- |
| `fcs` | FCS preview checkbox state. |
| `circular_active` | Circular motion checkbox state. |
| `offset_x_um`, `offset_y_um`, `offset_z_um` | [um] GUI scan offsets. |
| `offset_x`, `offset_y`, `offset_z` | [V] GUI scan offsets converted to scanner voltage. |
| `range_x`, `range_y`, `range_z` | [um] GUI scan ranges. |
| `time_resolution` | [us] GUI time resolution per time bin. FPGA `Cx` is derived from this value and the 40 MHz GUI clock base. |
| `timebin_per_pixel` | GUI time bins per pixel. |
| `nx`, `ny`, `nframe`, `nrep` | GUI pixel, line, frame, and repetition counts. |
| `calib_x`, `calib_y`, `calib_z` | [um/V] GUI calibration values used to convert between micrometers and volts. The code converts `offset_*_um` to `offset_*` with `offset_V = offset_um / calib`. |
| `preview_autoscale`, `projection`, `preview_channel`, `ch_preview` | Preview display settings. |
| `fingerprint_visualization`, `fingerprint_autoscale` | Fingerprint display settings. |
| `ratio_xy_locked` | XY aspect-ratio lock state. |
| `waitForLaser`, `waitAfterFrame` | [s] Laser-start delay and inter-frame/inter-repetition delay as entered in the GUI. |
| `waitOnlyFirstTime`, `laserOffAfterMeas` | Laser/wait control flags as entered in the GUI. |
| `offsetExtra_x`, `offsetExtra_y`, `offsetExtra_z` | [V] Extra scanner voltage offsets. |
| `min_x_V`, `min_y_V`, `min_z_V`, `max_x_V`, `max_y_V`, `max_z_V` | [V] Scanner voltage limits. |
| `spad_vr0`, `spad_vr1` | SPAD VR checkboxes. |
| `default_offset_x_um`, `default_offset_y_um`, `default_offset_z_um` | [um] Default offset controls. |
| `default_range_x`, `default_range_y`, `default_range_z` | [um] Default range controls. |
| `LaserEnable0` through `LaserEnable3` | Laser enable checkboxes. |
| `defaultFolder` | GUI default destination folder. |
| `spad_number_of_channels` | GUI channel-count selector, normally `25` or `49`. |
| `comment` | GUI comment widget value at the moment the group is written. See root `comment`. |
| `bitFile`, `niAddr`, `bitFile2`, `niAddr2` | FPGA bitfile paths and NI addresses. |
| `bitFile_sign`, `bitFile2_sign` | Bitfile signatures displayed by the GUI. |
| `spadCmdLength`, `spadCmdData`, `spadCmdInvert` | SPAD command controls. |
| `DFDnbins` | DFD bin count. |
| `compensation_delay_for_snake` | [pixels] Snake-scan compensation delay. |
| `backendDataRecv` | FIFO backend selector. |
| `plugins` | String representation of the plugin configuration dictionary. |

Observed GUI attribute names in the sample file:

```text
DFDnbins, LaserEnable0, LaserEnable1, LaserEnable2, LaserEnable3,
backendDataRecv, bitFile, bitFile2, bitFile2_sign, bitFile_sign, calib_x,
calib_y, calib_z, ch_preview, circular_active, comment,
compensation_delay_for_snake, defaultFolder, default_offset_x_um,
default_offset_y_um, default_offset_z_um, default_range_x, default_range_y,
default_range_z, fcs, fingerprint_autoscale, fingerprint_visualization,
laserOffAfterMeas, max_x_V, max_y_V, max_z_V, min_x_V, min_y_V, min_z_V,
nframe, niAddr, niAddr2, nrep, nx, ny, offsetExtra_x, offsetExtra_y,
offsetExtra_z, offset_x, offset_x_um, offset_y, offset_y_um, offset_z,
offset_z_um, plugins, preview_autoscale, preview_channel, projection, range_x,
range_y, range_z, ratio_xy_locked, spadCmdData, spadCmdInvert,
spadCmdLength, spad_number_of_channels, spad_vr0, spad_vr1, time_resolution,
timebin_per_pixel, waitAfterFrame, waitForLaser, waitOnlyFirstTime
```

## `/configurationGUI_beforeStart.attrs`

This group has the same schema as `/configurationGUI.attrs`, but it is captured
at acquisition start (`configurationGUI_dict_beforeStart = getGUI_data()`).
It is useful for comparing the GUI state at start and end of the acquisition.
The root `comment` usually corresponds to the comment entered before finalization;
`configurationGUI_beforeStart.comment` is the GUI comment value captured at start.

## `/rawStreamAcquisition.attrs`

This group exists only for preview-less RAW acquisition mode. In that mode the
H5 file is a small metadata file, usually named `*_only_metadata.h5`, and FIFO
payloads are streamed to sibling binary RAW files. The metadata H5 is opened
fresh at finalization and contains root attrs plus the metadata groups, but no
`/data`, `/data_channels_extra`, `/data_analog`, or `/thumbnail` datasets.

| Attribute | Type | Meaning |
| --- | --- | --- |
| `enabled` | bool | RAW stream mode enabled. |
| `digital_fifo_present` | bool | Digital FIFO was active. |
| `analog_fifo_present` | bool | Analog FIFO was active. |
| `digital_channels` | int | Digital detector channel count, usually 25 or 49. |
| `digital_words_per_sample` | int | Number of `uint64` raw words per digital sample: `2` for 25 channels, `8` for 49 channels. |
| `analog_words_per_sample` | int | Number of `uint64` raw words per analog sample, currently `1`. |
| `effective_timebins_per_pixel` | int | `#timebinsPerPixel * #circular_rep * #circular_points`. |
| `clock_base_mhz` | float/int | [MHz] GUI clock base, currently 40 MHz in the main window. |
| `clk_multiplier` | int | DFD decimation factor used when reconstructing digital time bins. |
| `dfd_shift` | int | [pixels] DFD shift/delay passed to the reconstruction mapping. |
| `snake_walk_xy`, `snake_walk_z` | bool | Bidirectional scan flags used by the RAW converter. |
| `dfd_activate` | bool | DFD active flag. |
| `digital_raw_file`, `analog_raw_file` | string | RAW FIFO file paths. Defaults are derived from the metadata filename when the attrs are empty. |
| `digital_raw_bytes`, `analog_raw_bytes` | int | [bytes] Bytes written to each RAW file. |
| `converted_to_standard_h5` | bool | Added by `convert_raw_acquisition()` after conversion. |
| `conversion_output_h5` | string | Added by `convert_raw_acquisition()` with the output H5 path. |

The RAW converter copies the metadata H5, adds reconstructed standard datasets,
and leaves the metadata groups in place.
