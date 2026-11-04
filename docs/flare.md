# Kria Flare acquisition

Firmware 1.9 support and resume status: [integration status](flare-1.9-status.md).
The application discovers multi-DMA ABI 3 capabilities at every run. In this
release, normal mode enables **DMA1 intensity only** and DFD mode enables
**DMA2 DFD3 only**. PS-to-PL position streaming is deferred; positions come from
the PL raster and circular XYZ arrays.

With firmware 1.9, enable the existing Circular control and set radius, point
count (1–32), and repetitions, as with SPAD. MCS uses the same generated offsets,
converts their calibrated volts to signed native DAC counts, and sends the three
arrays with configuration before START. Circular dimensions are positive counts.
Intensity HDF5 data retains repetition/Z/Y/X/circular repetition/circular
point/ordinary time-bin/channel axes when circles expand the scan. Its preview
integrates all visits belonging to each raster pixel. These files use container
identifier `brighteyes-flare-circular-1`.

DFD3 uses ungrouped circular-point scope and 32-bit counts. HDF5 `data` has
window/phase/channel axes, with exposure ticks, coordinate ranges, scope,
grouping flags and run/trajectory identities in `dfd_windows`, under container
identifier `brighteyes-flare-dfd-3`. Channels are
physical detectors, extra, then laser reference. Counts and metadata survive
RAW conversion. General line/frame/grouped scopes are deferred; do not reshape
these files using the older six-axis DFD1/DFD2 assumptions. Existing analysis
tools may need explicit support for the window axis.

Firmware 1.9 freezes configuration while a run is active. Use Stop and a new
acquisition to change finite-run geometry. Preview reads geometry again between
finite runs; changes do not modify the active scan. Earlier service behavior
described below remains available on earlier firmware. No connected microscope
acceptance has yet been performed for this update.

Select **TCP/IP - FPGA Flare** in the detector combobox, then open **Config / FPGA / Kria Flare**. Existing FPGA settings are under **Config / FPGA / NI**. Existing detector selections keep their NI control and detector pipelines; they do not connect to Flare or require a reachable Flare board.

## Connection and modes

The default Flare host is `mmskria3`, with HTTP control on port **8081**. Master is the default mode: Flare owns the scan and detector stream, and no NI FPGA session is opened. Changing detector while an NI session is held closes that session before selecting Flare. Flare acquisition does not use NI bitfiles, FIFO settings or the second NI FPGA.

Slave mode can be selected and saved for future use. Register diagnostics remain available, but preview and acquisition are blocked until firmware implements synchronization to NI pixel/line/frame timing. The current inputs being readable does not establish that timing support.

Click **Connect** to read device identity, supported registers and status. Connecting never resets an existing acquisition. Master acquisition currently requires FLR4 board identity and register schema 3 or 4. DFD requires schema 4 and an advertised `dfd` acquisition mode (reference service revision `fc5f8a9`). Board firmware 1.0.2 with a 100 MHz clock was used for initial integration checks; the clock is discovered for each run. Firmware 1.0.4 from `brighteyes-flare` revision `2985e2f` (2026-10-21) supports live register writes. Board capability bit 4 advertises laser registers; bit 5 advertises acquisition-independent raw register writes. The catalog displays the server's access policies; the server decides whether to accept each write.

The board initiates a separate TCP connection to the GUI computer. The default **GUI receiver port is 9000**; it is independent of HTTP port 8081. Keep the advertised GUI address empty for automatic route selection, or enter an address the board can reach. The bind address controls the local listener. Port 0 requests an automatic ephemeral port, which needs corresponding network/firewall access. Integration checks on this workstation succeeded on 9000 after an ephemeral-port callback timed out.

If HTTP works but start reports a connection timeout, check the advertised address, receiver port and inbound TCP access on the GUI computer. No firewall changes are made by the application. Optional REST authentication reads `FLARE_API_TOKEN` from the environment; the token is not saved in profiles or acquisition metadata.

**Bins per DMA packet** defaults to **Auto** (stored as `flare_packet_bins=0`). MCS estimates it before every run using the discovered fabric clock, exposure per record, record size, finite acquisition length and buffer duration. This also recalculates sizing when switching between normal and DFD acquisition. Auto targets 16 KiB packets, caps packet exposure at 2 ms (or one record for slower scans), and leaves room for two 32-descriptor DMA batches where possible. Hardware packet-count/byte limits and the existing buffer-capacity checks still apply. The selected count appears in the Flare log and acquisition status, and the accepted configuration saves the actual positive count in recording metadata.

Positive values select a manual override; DFD counts histogram records per packet rather than normal time bins. Existing profiles retain their saved manual values. To enable automatic sizing in an existing profile, select **Auto** at the minimum of the field and save the profile. Auto reduces overhead from tiny packets; it does not guarantee that every acquisition rate is sustainable by the board and network.

## Preview and recording

In normal intensity Flare mode, X/Y/Z offset (center), range and extra offset send live register updates when connected, including during preview and recording. Preview pan/zoom uses the same path. Rapid edits are coalesced for 80 ms and sent from a background worker. The application writes complete `axis_start_offset_volts` and `axis_calibration_volts_per_step` arrays in signed DAC counts, then writes 1 to `command` (COMMIT). It does not stop/reset the run or change its pixel counts, timing, calibration, channel count or stream framing. Edits made while disconnected are retained for connection/startup.

Like FPGA-SPAD mode, the displayed scan area follows position/range requests immediately. During the mouse event, Flare remaps the cached image with a lightweight transform; it does not wait for the 80 ms write timer, network response, COMMIT or next data frame, or recalculate image levels/histograms. Queued old frames and delayed confirmations do not undo the latest displayed area. The hardware updates remain asynchronous, and server errors still appear in the log.

Wheel zoom and pan retain the mouse-selected view when live writes complete or new preview frames arrive. Like FPGA-SPAD mode, navigation uses the smaller visible span for both X/Y scan ranges, so rectangular window padding does not stretch a square scan or its pixels. Navigation updates the spatial controls together, avoiding intermediate position/range callbacks. The existing Ctrl navigation preference still determines whether a gesture also changes microscope coordinates. Direct spatial-control edits fit the requested area immediately; ordinary image updates keep the current view. The cached pixels are progressively replaced by incoming measurements. A scan edited in progress can contain samples from more than one physical area. Recording metadata retains the initial configuration and timestamped live register requests/readbacks independently of the displayed area; the protocol does not identify the exact bin at which the hardware applies COMMIT.

Use the normal Preview and Acquire buttons. Master supports finite raster scans with 25 or 49 detector channels, multiple time bins, repetitions and frames. Z position/range is staged through the third axis-array element after the REST configuration resets it; frames advance that axis when its step is nonzero. With zero Z step, frames repeat XY. Physical calibration and direction remain instrument acceptance tasks. Preview repeats finite acquisitions with fresh connections; there are gaps between runs. Each pixel is cleared when its first new time bin arrives, then accumulates that pixel's remaining bins. Other pixels retain their previous values across frame boundaries and repeated preview runs until refreshed. The fingerprint uses Cumulative visualization, and the trace shows recent bin rates. Sum or individual channel selection and the fingerprint mask affect the displayed image; all detector counts are retained in the recording.

Range and offsets use the existing microscope calibration in micrometres per volt. Flare converts these to signed DAC counts, using the board's nominal `code * 10 / 32768` voltage mapping. Exceeding configured voltage limits logs a warning. Invalid coordinates/calibration cannot be converted, and initial X/Y scan endpoints outside the physical signed 16-bit DAC range still block acquisition. Live register values are submitted for server validation. Flare's internal coordinates can advance faster than the DAC settles; a valid photon bin does not establish the settled physical position.

Snake/circular/Lissajous scans, external/slave/software triggers, batch acquisition, FCS acquisition, ADC and TTM remain unavailable in this integration. The normal L1-L4 checkboxes control Flare's corresponding enable registers and may be selected before starting. Unsupported acquisition workflows remain separate from raw register access, where the server evaluates every request.

Synthetic detector events are optional and default off. Enabling them does not disconnect physical detector inputs or suppress physical outputs.

**Stop** cancels the active Flare run and holds its last output. **Reset** also commands DAC zero and is available in the Flare panel when no local run is active. Transmission failure can leave hardware acquiring/draining: the panel reports hardware state, saves the partial result and leaves Stop/Reset as separate actions. Commands are not automatically retried after ambiguous HTTP errors. Check status before recovery.

Acquisition, device requests and RAW conversion run in persistent spawned worker processes; the Flare backend does not use `QThread`. Qt polls for results and renders the latest preview snapshot from a single-slot mailbox, so outdated display updates cannot accumulate. Live control values, cancellation and register-write ordering are shared across processes. Status polling uses an independent HTTP session inside the acquisition worker and cannot block decoding. A full data queue briefly applies TCP backpressure, bounded by the configured stream timeout, before reporting an incomplete capture.

Acquisition failures appear in the status bar and Flare log. After two preview or acquisition starts fail because Flare is busy within 30 seconds, a dialog offers **Reset** or **Cancel**. Reset is sent only after acceptance; wait for the reset-completed message, then start Preview or Acquisition again. An accepted reset waits for any ongoing control request. The panel retains the latest 1000 log lines; the session log file retains the complete diagnostics.

## Register debugging and logs

Select a register row or enter its canonical name, `REG_` name or displayed numeric address. Known numeric addresses are resolved against the discovered catalog. Use **Read**, **Write**, or **Read all**. Enter JSON values: arrays normally require a complete array, such as `[-10, 0, 10]`, and scalar values normally require integers. The client sends the value to the server and reads back after an accepted write.

The debug field sends writes regardless of the advertised `write_policy`, local acquisition state or whether a named register appears in the catalog. The server validates register existence, access, type/range and busy state. Its HTTP status, errno and message appear in the Flare log. Firmware 1.0.4 advertises all implemented writable registers as `live`; older servers can reject writes with HTTP 409 or 403. Errors are reported without retrying or silently stopping/resetting the device. Read all is sequential rather than an atomic snapshot.

Read, Write and Read all run in independent background workers and reuse connection discovery. A slow register request does not block Qt rendering/input, independent reads or acquisition data reception. Conflicting register writes and configuration/start/stop operations are ordered in their background workers; reads do not take that lock. The table updates returned values without rebuilding unchanged cells.

Raw writes retain their hardware semantics. Geometry, dwell, masks and axis arrays are staged; writing 1 to `command` commits them. Staging alone does not alter the active scan. Raw channel/packet writes and raw lifecycle commands do not update the application's expected geometry, receive buffers or recording metadata and can invalidate a capture. Use the normal acquisition controls and Stop/Reset for managed runs.

Reference alignment registers are discovered from the service, including `excitation_reference_capabilities` at `0x8120`. Firmware 1.6.0 adds bit 3 for the half-height estimator; internal reference capabilities are 13 (previously 5). The service reports `excitation_phase_registration` as `integer_reference_half_height_v2` when that bit is set, otherwise `integer_reference_aperture_v1`. These are metadata identifiers. Register addresses and DFD2 framing are unchanged. Reconnect after updating the firmware/service to refresh the register catalog.

`excitation_phase_offset_bins` at `0x8110` reports the integer offset already applied to payload bins. `excitation_reference_span` at `0x811c` reports the thresholded first-to-last aperture span with the new estimator. MCS preserves the service's estimator, offset, span, epoch and correction flag in JSON, preview metadata and HDF5 root/dataset and reader metadata attributes, including after RAW conversion. An unavailable fractional residual stays null in JSON and is omitted from HDF5 scalar attributes; its validity flag is retained.

For normal intensity scans, stream dimensions, channel mode and dummy generation are staged afresh for each run. Current detector enable masks and hold-off settings are reapplied after configuration resets them. The latest requested axis arrays and L1-L4 states are then reapplied and the axes committed before starting. GUI writes and configuration share a lock in their background workers; the GUI thread stays responsive. Saved metadata includes initial register readback and live register events.

### Laser registers

Use the normal L1-L4 checkboxes for Flare enable requests, or the register browser for direct control and clock programming. Checkbox values are sent as integer 0/1. Requests are attempted without a firmware/catalog veto; older servers report unsupported or busy controls through the normal error path. The same sequence selectors configure Flare through its REST service; see the DFD profile below.

| Address | Register | Meaning |
| --- | --- | --- |
| `0x0450` | `laser_1_enable` | 0 off, 1 enable; PMOD1 P0 / J2 pin 1 |
| `0x0454` / `0x0458` / `0x045c` | `laser_2_enable` / `laser_3_enable` / `laser_4_enable` | Independent internal requests; no external connections |
| `0x8070` | `master_laser_clk_multiplier` | Staged integer multiplier M |
| `0x8074` | `master_laser_clk_divider` | Staged integer divider D, 2..128 |
| `0x8078` | `master_laser_clk_apply` | Write 1 to apply M/D; reads back 0 |
| `0x807c` | `master_laser_clk_status` | Read-only bits: 0 ready, 1 busy, 2 fault |
| `0x8080` / `0x8084` | `master_laser_clk_active_multiplier` / `master_laser_clk_active_divider` | Submitted M/D; valid when ready |

At the current 100 MHz fabric clock, frequency is `100 MHz * M / D`, with M restricted to 8..12. Reset defaults are M=10, D=25 (40 MHz), with all lasers disabled. For 20 MHz, stage M=10 and D=50, write 1 to APPLY, then poll status until ready. APPLY pauses laser gates while the MMCM reprograms and relocks. On firmware 1.0.4, enable requests and clock staging are writable during scanning/draining; the driver serializes APPLY against an ongoing clock operation. Older firmware permits disabling during a stream but can return HTTP 409 when enabling or changing the clock.

Enable requests act immediately, without COMMIT. Start, stop and normal completion leave them unchanged. Reset, including the reset performed by `PUT /configuration` before every finite scan, disables lasers and restores 40 MHz. The application reapplies the latest checkbox requests after configuration, including between finite preview scans. A direct browser write does not change the checkbox state. Clock programming remains a register-browser operation and is not restored automatically after reset; the DFD profile configures sequencing as described below.

The bounded log shows client requests, returned errors and acquisition transitions, with clear/copy/export controls. It does not read the board's system journal. Device status is polled independently of rendering; network reception and disk writes run outside the GUI thread.

## DFD and laser sequencing

Use the existing **DFD** checkbox, laser sequence selectors, L1-L4 enables, reference checkbox and lifetime display controls for either FPGA-SPAD or Flare. Switching back to FPGA-SPAD restores its phase-bin and clock-multiplier settings. Flare currently fixes the profile to **40 MHz, 91 phase bins and six excitation slots**; the multiplier and phase-bin fields show these effective values.

Sequence selectors 1-6 map 0 to off and 1-4 to L1-L4. Slots 7-12 must be zero for this firmware. The six masks are sent in configuration and packed with slot 1 in the most significant nibble for direct `laser_excitation_sequence` register updates (`0x80c4`). L1-L4 remain independent enable gates. The current firmware selects the sequenced waveform in DFD mode; normal intensity mode retains its manual laser clock. Raw register requests still go to the server for validation.

DFD uses pixel-end timing: pixel integration is `dwell * bins_per_pixel / sys_hz`. These scan timing fields determine exposure, while the 91 histogram bins divide the 25 ns laser cycle. MCS supports negotiated DFD1 and DFD2 layouts. In DFD2 (firmware 1.4.0), zero-based channel 25 is **Extra (unconnected)** and channel 26 is **Laser reference** for 25 physical detectors; in 49-detector mode these indices are 49 and 50. Legacy DFD1 has only the reference at index 25/49. Select the numeric index in the preview channel selector; its tooltip and selection label show the role. Enable the reference checkbox to collect reference counts; disabling it leaves the reference slot present with zeros. The production extra input is unconnected and normally zero, but any injected counts are retained. Extra/reference selections bypass the fingerprint mask. Sum, the fingerprint and ordinary detector/lifetime sums include only physical detectors. Selecting a single extra/reference channel displays that channel's intensity and phase histogram. The existing RGBDFD, lifetime/quality images, histogram peak alignment, time axis and decay-fit controls are available. Histogram rates use the exposure per phase bin. Both backends share the lifetime estimator and histogram rendering. Firmware reference correction is already applied to payload bins and is not applied again by MCS.

The current REST DFD configuration supports XY scanning with Z range and offsets at zero; frames repeat XY. DFD geometry, masks, hold-off, sequence, reference and laser enables are submitted together before START. START checks the accepted configuration against hardware, so live writes wait until configure/start completes. During DFD preview, XY range and position remain editable, including through preview navigation; changes send the axis arrays and COMMIT to Flare while preview runs and are also retained in the next finite frame configuration. Snapshot geometry follows the accepted live writes. Recording geometry stays fixed until acquisition/draining finishes. Z range and offsets remain locked because the DFD REST configuration requires zero. Normal intensity scans retain live position/range and laser controls. The register browser remains asynchronous and server-authoritative in either mode.

**Reference decimation (Flare)** in **Config / FPGA / Kria Flare** controls reference histogram counting on firmware advertising capability bit 10 (firmware 1.5.0). Set it before enabling DFD. Switching DFD on, or selecting Flare with DFD already enabled, immediately submits a background write to `dfd_reference_histogram_decimation_factor` and verifies readback. Unsupported firmware is discovered before accessing this register. This request shares the configure/START lock, so it cannot modify registers between accepted configuration and START. Each managed acquisition also explicitly includes the desired factor in configuration after any reset. The profile saves an integer factor from 1 to 65535; the GUI default is 101. Factor 1 retains every eligible reference edge; N retains the first edge and then every Nth edge. Default 101 preserves phase coverage for the current clock profile. Calibration, readiness and fault monitoring always remain full-rate; detector and extra counts are unaffected. The prescaler continues across pixels and resets at acquisition START. Longer pixel exposures can still saturate U16 counts and may require a larger factor.

The factor remains editable during preview and recording. An edit changes the next run's configuration, without writing the active acquisition's factor; the label distinguishes active and requested values and states when the change applies. Each finite preview run uses the latest request. On firmware without capability bit 10, the field is disabled, no unsupported configuration field/register is sent, and metadata identifies legacy reference counting at factor 1 with its original detector-holdoff behavior. The saved requested factor is retained for supporting firmware. Reference images, traces, histograms and HDF5/RAW conversion retain the measured decimated counts and rates without multiplying by N. Accepted configuration, JSON and HDF5 root/dataset attributes save `dfd_reference_histogram_decimation_factor`, `excitation_calibration_decimation_factor` (1), and `reference_histogram_counting`. DFD2 indices and byte framing are unchanged.

DFD reception validates the negotiated DFD1/DFD2 layout, channel roles, full 32-bit run ID, record ordinal/coordinates, flags, padding, tail and exact length across arbitrary TCP fragmentation. DFD2 has a different magic and channel count despite unchanged record byte sizes; layout selection never uses byte length alone. A partial pixel or nonzero `dfd_fault_flags` prevents a successful completion. No automatic switch to intensity decoding occurs on an invalid DFD stream.

## Files and offline conversion

A normal recording creates `name.h5`, `name.flare.raw` and `name.flare.json`. RAW-only mode creates the raw file and JSON sidecar. Existing files are not overwritten. Interrupted/failed recordings retain a partial result with error/status information. Partial HDF5 files retain the nominal dataset shape; the usable prefix is limited by both `validated_bins` and `stored_bins`. Check `complete` before interpreting unwritten positions as measured zeros.

For normal intensity scans, raw bytes preserve the original FLR4 stream: little-endian records of 120 bytes for 25 channels or 216 bytes for 49 channels. Counts are U32, not the NI packed FIFO encoding. Validation checks geometry/order modulo the header's eight-bit fields, run ID, markers, padding and exact length; these structural checks are not a payload checksum.

For normal intensity scans, the HDF5 format identifier is `brighteyes-flare-1`. Dataset `data` has shape `(repetition, frame, line, pixel, timebin, channel)` and U32 values. Root attributes contain completion state and JSON Flare metadata. Groups `configurationFlare`, `configurationGUI` and `raw/metadata` expose scan settings and common analysis metadata; `brighteyes_mcs_reader.load()` is tested for U32 values and effective timing. The JSON sidecar records accepted configuration, firmware, mode, detector registers, stream UUID/run ID, timing, buffer settings, received bytes, final status, timezone-aware times and completion/error state. `live_register_updates` records GUI and browser write values, request/finish times, readbacks and server errors during the run. Existing NI/PI files and the NI HDF5 0.0.1 schema keep their formats.

DFD recording writes contiguous pixel batches split at row boundaries, using HDF5 chunks that retain each pixel's full histogram and channel set. This avoids per-pixel writes and automatic multidimensional chunks that can make multi-frame recording fall behind the incoming stream.

DFD files retain the MCS container identifier `brighteyes-flare-dfd-1`; the separate `stream_format` attribute identifies DFD1 or DFD2. Both raw layouts use 5144/9512-byte records for 25/49 physical channels, with U16 counts. HDF5 `data` has shape `(repetition, frame, line, pixel, 91, stream_channels)`: DFD1 retains 26/50 meaningful channels and DFD2 retains 27/51, including extra and reference but excluding padding. Root/dataset attributes expose the channel indices, roles and padding layout; JSON metadata preserves the accepted layout and reference alignment provenance. The MCS six-dimensional container differs from the upstream capture tool's HDF5 container. Metadata also records the 40 MHz laser frequency, phase-bin width and pixel exposure. For incomplete DFD files inspect `validated_records`, `stored_records`, `partial_records` in metadata and `complete`; a structurally valid partial final pixel is retained but does not establish completion.

The existing RAW conversion action accepts a `.flare.json` sidecar and converts in a background worker. The Python entry point is also available:

```python
from brighteyes_mcs.storage.raw import convert_raw_acquisition

convert_raw_acquisition("scan.flare.json", "scan_converted.h5")
```

Flare conversion uses its own decoder and never routes the file through the NI decoder. It preserves the native U32 intensity or U16 DFD counts, reference channel and incomplete status. A capture without the required configuration/run identity cannot be reconstructed from raw bytes alone. Analysis tools should inspect the Flare format identifier and native count type; `h5py` can read the dataset directly.

## Validation and remaining acceptance

The [integration checklist](flare-integration-plan.md) records resumable work and release gates. Automated checks cover existing detector contracts with Flare construction forbidden, binary fragmentation/corruption, HTTP errors, ambiguous starts, Qt defaults/isolation, U32 intensity and U16 DFD recording/raw conversion, six-slot mapping, reference exclusion/preservation and lifetime GUI integration. DFD checks use independent binary fixtures and mocked service streams; connected-hardware DFD/sequencer acceptance is still pending.

Live checks on 2026-10-20 read firmware/status and all 53 advertised registers on `mmskria3:8081`, wrote/read/restored scratch, and completed zero-motion synthetic captures through GUI port 9000. Initial 12-bin captures received 1440/2592 bytes; final 257-bin captures received 30840/55512 bytes for 25/49 channels respectively. The final runs also checked coordinate wrapping, a short final DMA packet and concurrent scratch writes/readback plus reading all 53 registers during scanning. Raw framing, local HDF5 writing and final device completion passed. Scratch was restored to 0 and the board was reset/idle with no DMA/PL errors afterward. Local evidence is under the ignored `build/flare-live-checks/` directory.

These checks do not complete physical microscope calibration, known-pulse detector characterization, sustained throughput/endurance or attached NI/PI instrument regression acceptance. Those tasks remain unchecked before release.
