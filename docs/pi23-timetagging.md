# PI23 time-tag recording

The recorder settings are under **Config → TimeTagging → PI-Timetagging**.
Choose the HDF5 or RAW executable, output format, endpoint, and destination
folder. An empty PI23 folder uses the MCS destination folder. Enable
**PI23 TTM (record with acquisition)** in the Time Tagging group.

PI23 imaging and PI23TTM are mutually exclusive: the image receiver's `CS`
command competes with the recorder's `SB` command. Use SPAD imaging when
PI23TTM is selected. Conflicting loaded configurations cannot start a scan.

For a normal acquisition, MCS prepares its workers, launches the recorder,
waits for its post-calibration `Press Ctrl+C to stop.` message and the configured
ready delay (default 0.5 s), then starts the FPGA scan. Preview does not launch
the recorder. Calibration/startup has a configurable timeout (default 120 s).
The ready message precedes the tool's SB command, so the ready delay provides
time for that command to be sent; it is not a device acknowledgement.

`--measurement-ms` includes pixel dwell time, image dimensions, frames,
repetitions, circular points/repetitions, laser startup waits, frame waits,
the ready delay, and the recording margin (default 2 s). Calibration itself
happens before the device starts this measurement timer, so it is awaited
separately rather than subtracted from the recording budget. Increase the
margin for external trigger delays or additional hardware overhead.

Files use the MCS acquisition stem, e.g. `data-…-tsraw.h5` or
`data-…-ts.raw`; collisions receive a numeric suffix. Commands and recorder
stdout/stderr appear in the PI-Timetagging log. All settings persist in the
`cfg/plugins_cfg/pi23_timetagging.cfg` plug-in configuration, which is loaded
with the other plug-in configuration files at startup. Older main MCS
configurations containing top-level `pi23ttm_*` settings remain supported.

Natural MCS completion lets the recorder finish its timed measurement. New
acquisitions wait until it closes. Manual Stop, including during the recording
tail, immediately requests Ctrl+C. The Windows launcher uses a hidden isolated
console so the recorder can flush and close HDF5 safely. File flushing (or an
in-progress blocking vendor calibration request) may take additional time;
the recorder is not forcibly killed. Closing MCS also requests a clean stop.

**Adv2. → Time tagging / MCS saving → Do not save MCS data when TTM is active**
suppresses MCS HDF5/RAW output while continuing the finite scan and preview.
External TTM, automatic uTTM, and PI23TTM recording remain enabled. No empty
MCS metadata-only file is created in this mode.

## Register startup

Requested controls are replayed after the FPGA VI starts and after the scan
reset. Forced pulsing is explicitly applied on each acquisition; hardware
read-back no longer replaces requested settings. Register-write failures
propagate instead of silently leaving a cached value that was never written.
Physical first-run and repeated-run behavior still needs verification with
the connected FPGA and its firmware.

## Verification

`python -m pytest test/test_pi23_timetagging.py test/test_fpga_idle_control.py`
tests UI placement, exclusion, timing, stop behavior, saving suppression, and
register startup. When the supplied recorder builds are available, the tests
also run both real executables against a local fake TCP detector, including
calibration and clean interruption; no microscope hardware is contacted.

For UI changes, follow the central [Qt UI generation instructions](../CONTRIBUTING.md#editing-the-qt-ui).
