# PI23 time-tag recording

This integration was built by the Molecular Microscopy and Spectroscopy group
at Istituto Italiano di Tecnologia for our own microscope workflows. It is our
own tool, not an official Pi Imaging tool, and is not presented as endorsed or
supported by Pi Imaging.

The device API source is the
[Pi Imaging Technology pSPAD system manual](https://piimaging.com/doc-pspad),
especially its Remote command interface and Command guide. Consult the vendor
manual for device commands and version compatibility. Vendor documentation and
examples retain their own copyright and terms; BrightEyes-MCS's license does
not grant rights to that material. The local image/microimage server protocol
described below belongs to our integration and is separate from the vendor API.

The recorder settings are under **Config → TimeTagging → PI23 (Timestamp mode)**.
Choose the HDF5 or RAW executable, output format, endpoint, and destination
folder. An empty PI23 folder uses the MCS destination folder. Enable
**PI23 TTM (record with acquisition)** in the Time Tagging group.

Select **TCP/IP - PI23 (TS mode - img)** for a live XY image from timestamp events.
Saved configurations using the previous **TCP/IP - PI23 (TS mode)** label
still select this full-image mode.
MCS launches the RAW executable with `--stream-image X Y`, using the scan's
pixel dimensions, and polls its `PREVIEW` TCP snapshots about five times per
second in a background thread. The image shows the sum of detector pixels.
Set **Stream image TCP/IP port** in the timestamp panel (default **19000**).
This is the local Rust image server port, separate from the device's TTM endpoint.
The executable must support `--stream-image` and `--no-output`; rebuild an older
`tdc_raw_acquire` executable from its current source if these options are missing.

Select **TCP/IP - PI23 (TS mode - uimg)** for per-channel scan imaging and the
detector fingerprint. Each microimage contains 25 photon counts, one per detector
channel, for one completed scan dwell. MCS launches `--stream-microimage` and
retrieves batches with `READ <sequence> <maximum-count>` on the configurable
local port (default **19000**). The uimg command omits `--stream-image-pixel`:
microimage mode always retains all 25 channels separately.

Rust retains completed dwells from acquisition start, independently of client
connections. The buffer and sequence numbers survive repeated SB measurements.
**Uimg buffer (dwells)** defaults to **1,048,576** (128 MiB of packed records when
full); **Uimg batch size (dwells)** defaults to **4,096**. Both settings persist in
the PI23 configuration. A request for 100 returns immediately with 0 through 100
available dwells. Reads are non-destructive: an interrupted transfer can be
retried at the same sequence. Session IDs prevent mixing data after a recorder
restart. If unread data is overwritten, MCS reports the missing dwell count and
stops instead of silently skipping pixels. Increase the buffer to absorb longer
delays; sustained processing must still keep up with acquisition.

A dedicated acquisition **process** performs image and fingerprint accumulation.
Its network **thread** retrieves batches into a bounded queue (32 MiB with the
default batch size). Qt only reads the normal shared preview buffers; delayed GUI
redraws do not stop reception or count processing. MCS waits for a successful
batch connection and the recorder's armed message before starting the FPGA.
**Preview delay [s]** estimates queued acquisition time from all unprocessed
dwells, both on the recorder and in the local processing queue, multiplied by
the configured dwell duration (including circular points/repetitions). The label
blinks red above **1 second** and returns to normal when the backlog falls below
that threshold. This estimate excludes scan waits and events Rust has not yet
decoded; it is not a measurement of end-to-end hardware latency.
Choose **Sum** or channel **0-24** for the scan image; Sum respects the detector
mask. XY/YX views, snake scanning, and accumulation across preview frames are
supported. The preview retains each pixel's latest counts across frame boundaries
until a new dwell replaces that pixel, including zero-photon dwells. The final
preview remains visible when acquisition ends. The existing fingerprint display shows the current frame, rolling
10,000 dwells, or previous frame, normalized by their actual dwell durations.
Microimages contain dwell counts, so sub-dwell time traces, lifetime channels,
and other projections are not produced by this mode.

At natural completion Rust allows up to 30 seconds for the primary batch client
to retrieve the buffered tail. MCS waits for its local worker to finish processing
before completing acquisition. Explicit Stop cancels this drain and retains the
bounded termination behavior described below. A dwell must be closed by a
subsequent scan boundary marker; DONE alone does not complete an active dwell.
Invalid dwells following device FIFO overflow are excluded until the next frame.
The old PREVIEW, LAST, and STREAM requests remain compatible with other clients;
BrightEyes uimg uses READ. Rebuild older Rust executables for the batch protocol.

TS Preview runs with `--no-output --repeat`. Its `--measurement-ms` budget is:

`one frame's pixel dwell time + laser wait + frame wait + ready delay + preview margin`

The frame includes circular points/repetitions. Frame count and scan repetitions
do not multiply this budget. **Preview margin** is configurable in the timestamp
panel (default **0.5 s**, minimum **0.001 s**) and is separate from **Recording
margin**. The result is rounded up to whole milliseconds. For example, a
200 x 200 frame at 10 microseconds/pixel, no laser/frame waits, a 0.5 s ready delay, and a
0.5 s preview margin uses `--measurement-ms 1400 --repeat`. Increase the preview
margin for communication, scheduling, or external trigger delays. **Stop** ends
the repeated preview cleanly. Repeated SB windows are time based, not locked to
FPGA frame boundaries; the margin provides additional capture time.
For a normal acquisition, enable **PI23 TTM** to save RAW timestamps while the
same Rust process serves the image. In **TS mode - uimg**, **Acquire** also saves
the normal MCS `.h5` file, including when PI23 TTM is unchecked. The existing
**Do not save MCS data when TTM is active** option can suppress this HDF5 output
when a timetagger is enabled. Preview never saves HDF5. **TS mode - img** still
provides preview and optional RAW timestamps only. Neither timestamp mode uses
the intensity/SPAD raw-stream saving option.

The uimg HDF5 `data` dataset has axes `(repetition, z, y, x, timebin, channel)`
and stores all 25 channels as uint32 counts, independent of display channel,
mask, or preview accumulation. There is **one integrated time bin per dwell**;
the stream cannot recover individual FPGA time bins. Dataset attributes specify
the dwell duration and integration, including circular points/repetitions.
Acquisition GUI/FPGA metadata retain their original hardware settings.
XY and Z snake coordinates are corrected when saving.

The acquisition process writes fresh frame buffers independently of the rolling
preview. `pi23_microimages/valid` distinguishes measured zero counts from missing
pixels; `flags` preserves saturation flags, and `frame_complete` and `frame_id`
describe each saved frame. Missing frames are not renumbered. The group's
`complete`, `stop_reason`, and `error` attributes record completion or interruption.
Natural completion waits for file closure before adding normal MCS metadata.
An incomplete natural acquisition reports an error; manual Stop preserves the
processed portion as incomplete. Forced termination can prevent file finalization.
Existing output files are never overwritten by this writer.
Normal TS acquisitions finish when the timed Rust measurement closes. Manual
Stop interrupts both preview and timestamp recording.

The **TCP/IP - PI23 (Intesity)** mode and PI23TTM remain mutually
exclusive: the intensity receiver's `CS` command competes with the recorder's
`SB` command. Use SPAD imaging or either PI23 timestamp mode with PI23TTM.
Conflicting loaded configurations cannot start a scan.
Older configurations using the label **TCP/IP - PI23** still select intensity
mode. Intensity keeps its existing `CS` receiver on the intensity panel's port
(default **9997**). TS mode never starts that receiver: only the Rust recorder
connects to the device's timestamp endpoint, while the MCS image client connects
to the separate local image port (default **19000**).

For RAW recording and both TS preview modes, MCS prepares its workers, launches
the recorder, and waits for `PI23_ARMED SB,<ms>`. Rust emits this only after the
SB command has been successfully written/flushed and its receive buffers are
ready. MCS then waits the configured **Delay after armed / ready** (default
0.5 s) before issuing FPGA `start_command`. Microimage mode also waits for its
first valid batch response. The earlier `Press Ctrl+C to stop.` banner
cannot trigger a RAW scan. `PI23_DISARMED` cancels a pending start if that SB
window finishes; a subsequent repeated SB must arm again. Later SB windows do
not issue additional FPGA start commands.

Rebuild older RAW executables: without the armed message MCS times out rather
than starting prematurely. The configured release executable has been rebuilt.
This message confirms host-side readiness and SB transmission; the device
protocol supplies no separate hardware-arm acknowledgement. The ready delay
allows device processing time and is included in the measurement budget.
HDF5 recording retains its existing post-calibration banner and ready-delay
sequence. Calibration/startup has a configurable timeout (default 120 s).

For recording acquisitions, `--measurement-ms` includes pixel dwell time, image dimensions, frames,
repetitions, circular points/repetitions, laser startup waits, frame waits,
the ready delay, and the recording margin (default 2 s). Calibration itself
happens before the device starts this measurement timer, so it is awaited
separately rather than subtracted from the recording budget. Increase the
margin for external trigger delays or additional hardware overhead.

Files use the MCS acquisition stem, e.g. `data-…-tsraw.h5` or
`data-…-ts.raw`; collisions receive a numeric suffix. Commands and recorder
stdout/stderr appear in the PI-Timetagging panel and the application log under
`%LOCALAPPDATA%/BrightEyes-MCS/log`. Recorder exits, image connection errors,
waiting for scan markers, and the first received image are logged even when
debug logging is disabled. All settings persist in the
`cfg/plugins_cfg/pi23_timetagging.cfg` plug-in configuration, which is loaded
with the other plug-in configuration files at startup. Older main MCS
configurations containing top-level `pi23ttm_*` settings remain supported.

Natural MCS completion lets the recorder finish its timed measurement. New
acquisitions wait until it closes. Manual Stop, including during the recording
tail, immediately requests Ctrl+C and cancels any pending FPGA start. In the
rebuilt RAW recorder, Ctrl+C closes the device socket to interrupt calibration,
setup, and acquisition reads/writes. The Windows launcher uses a hidden isolated
console so the recorder can normally flush and close its output safely.

Stopping is bounded: the launcher allows **2 seconds** for a clean exit, then
force-terminates an unresponsive recorder. An independent **5-second watchdog**
terminates the launcher and its recorder if the launcher or its command pipe is
stuck. On Windows a dedicated Job Object owns this process tree; no process-name
matching or `taskkill` is used. Closing the GUI also closes its job handle and
terminates remaining recorder processes. Stop remains available during the
recording tail and automatic MCS completion. New scans wait for recorder exit.

A forced termination is logged and may leave the last data incomplete or an
HDF5 file unfinalized. The fallback works during connection/startup, calibration,
streaming, and file closing, without depending on Qt timers.

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

`python -m pytest test/test_pi23_timetagging.py test/test_pi23_stream_image.py test/test_pi23_microimage_batches.py test/test_fpga_idle_control.py`
tests UI placement, exclusion, timing, stop behavior, saving suppression, and
register startup. When the supplied recorder builds are available, the tests
also run both real executables against a local fake TCP detector, including
calibration, timestamp image polling, complete microimage raster delivery,
channel selection, fingerprints, repeated frames, optional RAW recording, and clean
interruption; no microscope hardware is contacted. Batch tests also cover
fragmented responses, retries without duplication, session changes, buffer
overrun, and a 30,000-dwell worker run without GUI event processing.

For UI changes, follow the central [Qt UI generation instructions](../CONTRIBUTING.md#editing-the-qt-ui).
