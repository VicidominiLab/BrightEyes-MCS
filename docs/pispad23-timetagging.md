# PI SPAD23R acquisition

This integration was developed at Istituto Italiano di Tecnologia for our
microscope workflows. It is our tool, not an official or endorsed Pi Imaging tool.

Both **TCP/IP - PI SPAD23R (Intensity)** and **TS mode - uimg** use
`brighteyes-pispad-libs>=0.3.0`. The library launches its packaged Rust worker
for TCP reception, buffering, decoding and recording. MCS pulls completed
microimages from the worker's memory-mapped FIFO.

## Install the local library

Choose the wheel matching the Python running MCS. For Python 3.12 on Windows x64:

```powershell
python -m pip install "C:\path\to\brighteyes_pispad_libs-0.3.0-cp312-cp312-win_amd64.whl"
```

Use the cp313 wheel for Python 3.13. These wheels contain native Rust and static
HDF5 code; another machine does not need Rust, maturin, MSYS2 or the source tree.
NumPy is a Python dependency. Install the local library before installing the
MCS `pispad` extra while the library remains unpublished.

## Shared configuration

Select the detector mode in the detector selector. Both modes use the single
**PI SPAD23R** configuration tab: endpoint, destination, RAW/HDF5 choice,
preview buffer/batch limits, readiness timeout, startup delay, status and log.
An internal intensity dwell overrides the rate denominator and saved dwell
duration; external dwell uses the FPGA timing settings.

Intensity additionally enables detector channel count (25 for SPAD23R, 23 for
SPAD23G), external frame clock, and dwell time in microseconds (0 = external).
Timestamp mode enables duration margins and Force Calibration.

**pSPAD TCP verbosity** controls the library independently of MCS `--log-level`:
Minimal logs lifecycle/errors; Normal (default) logs all commands and replies
plus receive byte counts without binary payloads; Full also stores every wire
byte in hex. The selection is saved with the PI configuration and applies to
both acquisition modes, preview, and Force Calibration. Each operation writes
`pispad-tcp-<id>.log` in the MCS log folder and displays its path in the tab.
Use **Load / Save Cfg → Open log folder** to find these files, including when
MCS application logging is off. Full mode creates large files and may slow
acquisition; reserve it for short diagnostic runs. Measurement RAW/HDF5
recording remains a separate setting.

**PI SPAD23R TDC recording** enables a Rust RAW or HDF5 event recording alongside
timestamp acquisition. Its format and destination controls apply only to TDC
mode. Intensity acquisition uses the normal MCS HDF5 destination, writer and
metadata flow. Preview does not create measurement files. Both modes provide
microimages independently of the TDC recording checkbox. The generic SPAD
raw-stream checkbox is unavailable for PI acquisition.

Settings are stored in `cfg/plugins_cfg/pispad23_timetagging.cfg`. Older top-level
PI settings still load. The former intensity IP/port migrate to the shared
endpoint for intensity configurations. Retired executable paths/backend/preview
port settings are ignored. They never reactivate the removed tools.

## Acquisition and preview

The MCS acquisition worker owns a separate Rust process. Rust receives and
buffers the TCP stream, optionally records TDC RAW/HDF5, decodes microimages, and publishes
them directly into a bounded memory-mapped FIFO. Python pulls available
25-channel dwell rows in batches, then processes the standard MCS preview and
saving arrays. Rust reception and decoding continue independently of Python's
GIL or polling. The library detects Rust worker crashes; on Windows its process
ownership prevents orphan workers after an MCS worker dies. Preview image,
fingerprints, masks, accumulation and saving use these same rows in both modes.
The Rust backend reports FIFO overflow instead of silently dropping rows.
MCS stops acquisition and marks the count file incomplete on delivery failure;
native TDC recording is independent of microimage delivery at the library level.

The MCS worker assembles original microimages into frames and sends them to
the same `H5ManagerProcess` used by FPGA SPAD acquisition. Acknowledged frame
writes preserve uint32 counts and report storage failures. Shared preview
arrays may retain old display pixels while the new frame arrives; the saved
frames are assembled separately from the ordered microimages.

Timestamp mode uses SB windows and includes zero-photon dwells. Preview repeats
windows without issuing another FPGA start. Intensity uses length-framed CS
channel planes, strips wire row padding to a multiple of four pixels, and
preserves full unsigned 8-bit counts. It does not clip counts to SPAD FIFO bit
fields. Intensity preview arrives after a complete frame's channel planes.
Set the microimage buffer to hold at least one full scan frame, with headroom
for consumer delays. Continuous intensity preview uses CS frames=0.

Software triggering supports SPAD and PI intensity. The worker arms CS for
one frame, waits indefinitely for the first data byte, and rearms after DONE.
Stop cancels the wait; stalls after a frame begins retain a timeout. The GUI
waits for receiver readiness before enabling the trigger and never starts the
FPGA automatically in this mode. Timestamp software triggering is unavailable.

## Files

The regular MCS HDF5 `data` array has axes
`(repetition, z, y, x, timebin, channel)`, uint32 counts and 25 channels.
There is one integrated time bin per dwell. XY/Z snake coordinates are corrected
when saving. Display selection and masks do not alter saved counts.
`pispad23_microimages/valid`, `flags`, `frame_complete` and `frame_id` preserve
missing-pixel and saturation information; group attributes record completion,
stop reason and errors. Natural completion waits for writer closure before MCS
adds metadata. Manual Stop preserves a partial acquisition as incomplete.

Optional timestamp recordings use `-ts.raw` or `-tsraw.h5` (schema-v3 events).
Intensity acquisition creates the standard MCS file, with regular configuration,
FPGA, GUI, comment and thumbnail metadata added by the normal finalizer. MCS
does not request a second native intensity file. The standalone library retains
its native intensity export/read/conversion APIs for use outside MCS.

**Do not save MCS data when TTM is active** can suppress the regular MCS file
while selected TDC event recording and preview continue. A saved PI TDC checkbox
does not suppress intensity saving. Live previews use shared
memory; read HDF5 recordings after the writer closes (no SWMR).

## FPGA startup

The primary FPGA session opens without automatically running the VI. Every acquisition first
resets the FSM, holding Stop until idle and clearing Run before releasing Stop.
Requested scan/laser/sequencer controls are replayed after VI startup/reset.
Run remains asserted until Stop/reset for both settings of Keep FPGA On. An
immediate host True/False pulse could previously be missed by the FPGA loop.
Startup readback is retained separately and does not overwrite requested controls.
Register-write failures propagate. Software triggers use the same held Run rule.

## Validation

The standard MCS storage integration passed 183 focused tests and 5 subtests:
PI acquisition/preview, HDF5 frame assembly and service writes, normal metadata
finalization, acquisition-manager storage allocation, FPGA frame writes/startup,
and software triggering. Checks cover large uint32 counts, partial/missing
frames, snake coordinates, existing-file protection, acknowledged write errors,
and intensity acquisition creating only the normal MCS file.

The 0.3 Rust process integration passed 45 focused PI worker/GUI/controller
tests on Windows, including a distinct Rust PID for timestamp/intensity
acquisition, readiness before FPGA start, preview and native recording,
configuration persistence, and independent protocol verbosity. The library
passed 21 Rust tests and 77 Python tests, including the installed CPython 3.12
wheel. Both cp312 and cp313 wheels contain the packaged Rust executable.

Earlier validation:

Tests exercise the native library and application worker against a local
simulator, including both modes, RAW/HDF5, fragmented transfers, partial frames,
preview-only acquisition, readiness before FPGA start, repeated preview,
software-trigger waits and clean cancellation. FPGA tests simulate delayed
sampling and repeated runs. Local validation passed 874 tests and 45 subtests in the full MCS suite,
with subsequent focused startup/GUI regressions also passing. All four isolated
channel-delay tests and all five console tests passed (console cases in fresh
interpreters). The native core passed 19 tests; installed CPython 3.12 and 3.13
library wheels each passed all 42 library tests. Documentation/lint, compilation,
package metadata and distribution-content checks passed.

No physical detector, vendor software or FPGA was
available; first/repeated-run hardware behavior and USB throughput still need
measurement on the instrument.

```powershell
python -m pytest -q test/test_pispad23_library.py test/test_pispad23_library_gui.py test/test_fpga_idle_control.py
```
