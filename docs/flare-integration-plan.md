# Flare FPGA integration plan

Add `TCP/IP - FPGA Flare` as a detector and support two scan-control modes: **Master** (default), where Kria Flare owns control, scanning and streaming without an NI FPGA, and **Slave**, where NI owns scanning and Flare supplies detector data. Keep the existing NI detector workflows working throughout the integration.

Created: 2026-10-20. Branch: `flare`, created from `on_the_road_v2` at `c1ebc99a441a873b954eba43c7374e058457196f`. Master XY acquisition, preview, recording, diagnostics and NI isolation are implemented. Slave acquisition awaits firmware support. Physical microscope acceptance and sustained-rate checks remain open.

## Progress and resuming work

Check a task only when its acceptance condition passes. After each implementation session, update this file with completed task IDs, validation results, remaining blockers and the next task. Keep blocked tasks unchecked and record the dependency. Hardware checks require actual measurements; simulator results do not complete them.

- [x] P00 Create and switch to branch `flare`.
- [x] P01 Inspect the Flare documentation and the existing UI, detector, hardware, acquisition and storage boundaries.
- [x] P02 Save this implementation checklist in the repository and link it from the documentation index.
- [x] P03 Verify the saved plan with `python scripts/check_docs.py` (0 errors).

**Next task:** N06 and H03/H04 instrument acceptance. **External dependency:** slave acquisition needs future Flare firmware/API support; it does not block master integration. Live XYZ register staging and L1-L4 control are implemented; their physical calibration and timing remain instrument acceptance tasks.

To resume, inspect `git status --short`, switch to `flare` if necessary, read this file and start at the first incomplete task whose dependencies are met. Do not overwrite unrelated changes. If the external docs changed, reconcile their protocol changes before implementing the affected task.

## Sources and protocol baseline

Flare source directory: `C:\Users\madonato\tmp\brighteyes-flare\docs`.

| Source | Use |
| --- | --- |
| `REST_AND_STREAM_PROTOCOL.md` | Primary current HTTP, raw stream, register access and lifecycle contract; tested deployment described on 2026-10-20 |
| `HARDWARE.md` | DAC units, physical scan limitations, channel wiring and external timing limitations |
| `STREAM_TRANSPORT.md` | Internal FIFO/DMA behavior, overflow and drain semantics |
| `IMPLEMENTATION_BASELINE_20261015.md` | Historical bring-up context; later protocol documentation supersedes its transport status |
| `reference/BrightEyes-MCSLL-register-sizes.md` | Inherited register vocabulary; discover actual supported registers from the running device |

Source fingerprints at planning time, SHA256:

```text
REST_AND_STREAM_PROTOCOL.md
C15D06E58E0F0A9EB1C01746265B9E1A0A3D8E8FAED1A6005F9A7D18AA09562B
HARDWARE.md
0150B41A30F8FFBECA3A3D5B73F6139655D0CDFF3AF22FED96BFB3B4CD887AB5
STREAM_TRANSPORT.md
2B132817B61FCDC37AC119E479274E94146583F77188F2168E505B8053386AD7
IMPLEMENTATION_BASELINE_20261015.md
18A0035005CEEEDBB1653CAAB16EC294E2E78AE4B81258934F0B0FB7E8C049E9
```

These are local source references. The essential contract is recorded below so the checklist remains useful if the temporary directory moves. Refresh the baseline against the device before hardware acceptance.

### Required user behavior

| Selection | Scan control | Detector data | NI requirement |
| --- | --- | --- | --- |
| Existing FPGA SPAD and PI SPAD23 options | Existing NI behavior | Existing pipelines | Existing behavior preserved |
| Flare with Master selected | Flare REST and Kria scan engine | Flare raw TCP stream | No NI session, bitfile, driver or hardware required |
| Flare with Slave selected | NI FPGA | Flare detector stream synchronized to NI timing | NI required; acquisition unavailable until external timing support exists |

In Config, split the existing FPGA page into `Config/FPGA/NI` and `Config/FPGA/Kria Flare`. Move the complete existing FPGA configuration into NI. The Kria Flare page contains host `mmskria3`, HTTP port `8081`, GUI receiver port `9000`, Master/Slave selection, connection and status, receiver settings, a log view and register debugging. Selecting the NI subtab must not itself change the active backend.

### Compatibility when Flare is not selected

**Required invariant:** selecting any existing detector preserves its behavior from the branch base, including scan control, register values and command ordering, timing calculations, preview, recording, saved formats and supported features. The new nested FPGA tabs are a layout change; they must preserve the existing NI controls and their connections. Flare Master is the default mode only after Flare is selected; it must never become the default scan controller for an existing detector or profile.

Non-Flare startup and acquisition must work with the Flare board disconnected, its service unavailable and no Flare settings in the profile. They must not create a Flare client, resolve `mmskria3`, send Flare HTTP requests, bind a Flare receiver socket, start Flare workers/status timers or apply Flare capability restrictions. Opening the Kria Flare subtab alone must not activate Flare. Invalid or stale saved Flare settings must not prevent an existing detector from running.

## Compatibility checklist and release gate

These tasks apply throughout implementation. Capture N01 before changing shared acquisition behavior, run the relevant N02–N05 checks after each shared-code change, and complete N06 before declaring the integration ready.

- [x] N01 Record the existing regression results and representative deterministic acquisition fixtures at branch base `c1ebc99a441a873b954eba43c7374e058457196f`. Cover FPGA SPAD 25/49 channels, PI SPAD23 intensity and timestamp modes, and Disable according to their current behavior. Capture register writes/command order, geometry/dwell/repetition calculations, preview counts and saved data/metadata. Record existing failures and skips separately so they cannot conceal new regressions.
- [x] N02 Add isolation tests for every existing detector with Flare client construction, DNS resolution for the Flare host, HTTP calls, receiver creation and worker/timer startup instrumented to fail if invoked. Exercise startup, profile load, connect, preview, acquisition, stop, reset, reconnect and shutdown with the Flare service absent. Validate Flare-only fields only when Flare is selected; keep existing detector readiness checks and dependencies unchanged.
- [x] N03 Compare the deterministic fixtures against the branch base after introducing the scan-control interface and after subsequent shared manager/coordinator changes. Require unchanged NI register values and command order, clock/repetition conventions, FIFO selection/chunk sizes, image/trace/fingerprint counts, dataset shapes/dtypes/values and public metadata keys. Compare deterministic raw bytes and decoded HDF5 contents; account explicitly for timestamps and other run-specific metadata rather than requiring binary-identical HDF5 files.
- [x] N04 Verify old profiles without Flare keys retain their detector and settings, and round-trip unknown/plugin fields. Verify the existing NI widgets, signals, tab navigation, detector label mappings and saved selections after the UI move. Exercise existing supported analog, DFD/TTM, snake/circular scans, second FPGA, plugins, application REST commands, batch and software-trigger workflows; Flare limitations must never disable them for a non-Flare detector.
- [x] N05 Test switching from each existing detector to Flare and back while idle, including after a failed Flare connection or run. Finish explicit stop/disconnect cleanup before switching: close Flare sockets, stop its workers/timers and clear its run state without overwriting stored NI/PI settings. Restore the original detector pipeline, scan controller, capabilities and timing. Confirm subsequent legacy acquisition invokes no Flare operations and leaves no Flare resources active. Continue rejecting switches during acquisition.
- [ ] N06 Require passing non-Flare isolation/fixture tests and the existing regression suites, plus connected NI SPAD and PI SPAD23 smoke tests with Flare disconnected, before release. Compare representative acquisition timing and throughput with the recorded baseline to detect added polling or work in legacy paths. Record evidence and resolve regressions; if hardware is unavailable, leave hardware acceptance unchecked.

Acceptance: existing detector workflows retain their baseline behavior independently of Flare availability. Any failure of this gate blocks release of the integration, even if Flare master acquisition works.

## Flare protocol contract

- HTTP base: `http://mmskria3:8081/api/v1/devices/flare0`. Port 8081 is the control port. The GUI opens a separate listening socket and advertises its reachable host/port through POST `/streams`; the **board connects to the GUI** once per run. Allow bind address and advertised address to differ, with an explicit override for machines with multiple interfaces.
- Discover GET `/firmware`, `/system`, `/registers`, `/commands` and `/status`. Baseline identity is FLR4 (`board_id=0x464c5234`), schema `0x00030000`, board firmware 1.0.2 and nominal `clock_hz=100000000`; discover these instead of hardcoding the timing. Core firmware, board firmware and API version are separate identifiers.
- GET `/registers` supplies metadata. GET `/registers/{name}`, PUT `/registers/{name}` with `{"value":...}`, and GET `/registers_read_all` supply access. Names and `REG_` constants work; numeric address paths do not. Bulk reads are sequential, not atomic, and fail as a whole if any read fails.
- PUT `/configuration` resets and stages a finite acquisition; omitted fields return to defaults. Send complete settings and retain the accepted response because GET `/configuration` does not exist. Configuration is rejected while acquisition or transmission is active. Reapply custom staged registers after configuration resets them.
- POST `/streams` merges destination, buffer and timeout settings. POST `/commands/start`, `/commands/stop`, `/commands/reset` control the run. There is no resume, replay, stream reattachment, WebSocket or event subscription. A timed-out command may have executed; inspect status before deciding recovery.
- Stop aborts transmission, can discard pending data and holds the last DAC position. Reset also commands DAC zero. Save status before configuration, stop or reset removes retained stream results. Connecting or opening the debug panel must not reset another acquisition. The service has one device/run/destination and no controller leases.
- Raw records are little-endian: 8-byte header, 25 or 49 U32 counts, 4 zero padding bytes and 8-byte tail, totaling **120 or 216 bytes/bin**. Header marker is `0xA2` at byte offset 7; tail word is `0x465047415F454E44`. Neither is a checksum. FLR4 uses RPi channels 0..24, then PMOD channels 25..48; older FLR3 mapping differs.
- Acquisition order is time bin, X, Y, Z, repetition, fastest first. Header coordinates and FPGA run ID wrap modulo 256. Reconstruct full coordinates from configuration and bin index, then validate low eight bits. The FPGA run ID and service stream UUID are different identifiers.
- Success requires EOF at exactly the expected byte count, valid records, matching stream UUID with final `complete:true` and no stream/acquisition/DMA/PL errors, and successful local file finalization. PL DONE, EOF or board `bytes_sent` alone cannot establish success. A failed TCP stream can leave hardware running and draining into discard buffers.

## Integration boundaries

Current extension points are the [detector model predicates](../brighteyes_mcs/acquisition/detectors/models.py), [pipeline factory](../brighteyes_mcs/acquisition/detectors/factory.py), [manager](../brighteyes_mcs/acquisition/manager.py), [coordinator](../brighteyes_mcs/acquisition/coordinator.py), [NI handle](../brighteyes_mcs/hardware/fpga.py), [settings](../brighteyes_mcs/acquisition/settings.py), [configuration codec](../brighteyes_mcs/storage/legacy_config.py) and [main window](../brighteyes_mcs/ui/qt/main_window.py).

At the branch base, `McsManager.connect()` always constructed the NI handle, every normalized detector used NI control, and the main window checked NI bitfiles before connecting. The manager also calculates digital data as 2 or 8 U64 words per sample and derives repetitions through NI-specific conventions. Flare needs separate control selection, geometry mapping and stream accounting; adding a detector label alone would still initialize NI.

The implementation uses these package boundaries:

| Responsibility | Proposed location |
| --- | --- |
| Qt-independent REST control | `brighteyes_mcs/hardware/flare.py` |
| Flare settings, capabilities and lifecycle | `brighteyes_mcs/acquisition/flare.py` and `brighteyes_mcs/acquisition/detectors/flare/config.py` |
| Flare pipeline and binary decoder | New `flare` package under `brighteyes_mcs/acquisition/detectors/` |
| Dedicated receive thread and acquisition/file worker | `brighteyes_mcs/acquisition/flare.py` |
| Flare metadata and offline conversion | `brighteyes_mcs/storage/flare.py`, dispatched by `brighteyes_mcs/storage/raw.py` |
| Flare panel logic and Qt signals | New controller under `brighteyes_mcs/ui/controllers/` |

Flare publishes decoded count arrays to the existing image/fingerprint/trace widgets and uses its own U32 HDF5 writer. NI packed-word decoding and its existing writer remain on the legacy route. Follow [repository boundaries](refactoring-architecture.md) and [UI generation rules](../CONTRIBUTING.md#editing-the-qt-ui).

## Phase A Settings and capability contract

Dependencies: planning and N01 baseline capture complete. Finish this phase before routing acquisition to Flare.

- [x] A01 Add a stable internal Flare detector ID and exact UI label `TCP/IP - FPGA Flare`. Extend normalization and pipeline dispatch explicitly so Flare never falls through to SPAD. Model scan controller and Flare mode separately from detector identity. Test legacy labels and all three Flare/NI routing combinations.
- [x] A02 Extend typed settings, legacy translation, GUI configuration mapping and defaults with Flare host, HTTP port, mode (default `master`), receiver bind/advertised host and port, packet size, buffering and timeouts. Default missing Flare fields without changing the selected detector in old profiles. Preserve unknown keys and round-trip existing profiles and both modes. Support an optional runtime API token without writing it to logs or acquisition metadata.
- [x] A03 Define capabilities per mode and discovered firmware: raster scanning, 25/49 channels, physical axes, detector masks, preview, register access and supported commands. Audit circular/snake scans, analog inputs, DFD, TTM, laser/shutter sequencing, plugins, software triggers and batch workflows. Gate unsupported operations in services as well as widgets; a register appearing in the catalog does not establish an implemented feature.
- [x] A04 Provide explicit routing for connect/disconnect, configure, start, stop, reset, register access and status. Keep the existing NI manager route and delegate Flare to its own Qt-independent client/acquisition service. Keep NI FIFO tuning out of Flare. Specify lifecycle state and error propagation independently of Qt. This narrow routing preserves the captured NI behavior without a shared manager rewrite.

Acceptance: settings select the intended scan controller without connecting hardware; legacy profiles retain their behavior; unsupported settings fail before any scan starts.

## Phase B REST control and register debugging

Dependencies: A02 and A04. Can proceed alongside the UI and decoder after their shared contracts are fixed.

- [x] B01 Implement the Flare HTTP client using the existing HTTP dependency, with explicit request timeouts, JSON validation, optional bearer authentication and errors retaining method, endpoint, HTTP status, errno and message. Handle non-JSON failures and unknown metadata fields. Follow the documented literal paths and GET/PUT/POST methods.
- [x] B02 Implement discovery and status polling in a control worker. Show firmware/core/schema, board identity, clock, system and connection state. Reject unsupported format/schema for acquisition while keeping diagnostics usable. On connect, inspect a busy device and report it without issuing reset/configuration/start. Serialize lifecycle changes through one coordinator.
- [x] B03 Build register rows from `/registers`: name, address, type, signedness, width, array length, access, write policy and value. Allow selecting a register by name or its displayed address; resolve addresses locally to canonical names. Validate scalar ranges and full arrays before PUT. Read back after writing because PUT reports accepted input rather than hardware readback.
- [x] B04 Implement Read, Write and Read all using the documented endpoints. Display discovered policies, and submit writes for the server to validate without local policy/state/type/range vetoes. Preserve HTTP/errno errors without retrying or silently stopping a run. Resolve known addresses and `REG_` names while forwarding unknown named registers. Managed acquisition uses lifecycle endpoints. Bulk readbacks are non-atomic.
- [x] B05 Add a bounded, timestamped panel log fed from the normal application logging path: connection, register operations, commands, stream transitions and errors. Provide clear/copy/export. Redact tokens. Show client activity and returned device errors; the documented API has no remote journal/log endpoint.
- [x] B06 Test discovery, signed values, arrays, read all, readback, policy enforcement, malformed JSON, 400/401/403/404/409/503, unreachable host and timeout recovery with a fake HTTP service. Never automatically retry a state-changing request after an ambiguous timeout.

Acceptance: all requested debugging works against a fake service without freezing Qt, and connection alone changes no acquisition state.

## Phase C Detector selection and FPGA tabs

Dependencies: A01/A02/A03; wire live control after B01–B05.

- [x] C01 Edit [main_window_design.ui](../brighteyes_mcs/ui/qt/main_window_design.ui) to add the detector item and nested NI/Kria Flare tabs under Config/FPGA. Move the complete current FPGA page into NI, preserving widget names, connections and saved values. Regenerate the Python UI with `pyside6-uic`; never edit generated Python manually.
- [x] C02 Add the Kria Flare connection fields with `mmskria3:8081`, Master/Slave selector defaulting to Master, connect/disconnect, firmware/status, receiver settings, log and register browser. Explain that the receiver address belongs to the GUI computer. Make register arrays and populated values readable when resizing.
- [x] C03 Add a dedicated Flare controller for signals, worker requests and view updates. Keep network requests, bulk reads, file work and per-bin decoding outside the GUI event loop. Poll status at a moderate rate (proposed 5–10 Hz) and publish preview snapshots separately (proposed 10–30 Hz).
- [x] C04 Update detector selection, connect button, readiness checks, keep-connected behavior and mode switching. In master mode, remove NI address/bitfile/FIFO requirements. In slave mode, expose both NI scanning and Flare detector readiness. Reject detector/mode changes while busy. Preserve the selected mode across save/load; tab navigation does not change it.
- [x] C05 Show Slave as selectable with a clear firmware support message; prevent preview/acquisition until support is established by G01. Gate unsupported master controls from A03. Add UI checks for exact label, hierarchy, defaults, profile round-trip and responsive logs/register reads.

Acceptance: old NI fields retain values and behavior; Flare defaults are visible; a master connection never asks for an NI bitfile.

## Phase D TCP reception and lossless decoding

Dependencies: A01/A02 and protocol baseline. Can be tested without an actual board.

- [x] D01 Implement a worker-owned TCP listener and bounded receive path. Report listener readiness before start, accept one board connection per run and enforce startup/inactivity deadlines. Handle bind errors, advertised-address mistakes, cancellation and disconnect. Separate lossless receive/write work from replaceable preview snapshots.
- [x] D02 Implement incremental FLR4 decoding for arbitrary TCP fragmentation/coalescing. Validate 120/216-byte bins, channel count, header marker, zero padding, tail, run ID and modulo-256 coordinates against the full expected index. Buffer initial data until accepted settings and run ID arrive; bytes may precede the start HTTP response. Preserve malformed captures as partial rather than silently searching for a new marker.
- [x] D03 Keep channel counts as U32, with U64 accumulation where needed for summed pixels, traces and channels. Build a count-array path into preview/image/fingerprint services without the NI packed-word decoder. Preserve `(repetition, frame, line, pixel, timebin, channel)` ordering, masks and rate scaling from `dwell/clock_hz`. Do not invent NI auxiliary/laser channels.
- [x] D04 Give Flare its own expected bins/bytes and progress counters. Replace assumptions in `readRegistersDict()`, `update_chuck()`, FIFO counters and shared state for Flare runs; do not use 2/8 NI words/sample. Use counters wide enough for the maximum acquisition and test totals beyond 32 bits.
- [x] D05 Validate transport settings before starting: N is the product of five geometry counts and is at most 4294967295; expected bytes are N times bin size. Account for full-packet buffer rounding, at least one slot, 256 MiB service allocation cap, DMA completion bursts and socket versus DMA timeouts. Choose packet size from dwell and capacity; the protocol's 1 ms/bin example uses 4 bins/packet, rather than blindly accepting the 128-bin default.
- [x] D06 Add fixtures and a board simulator for both channel modes, U32 values above 65535, every-byte fragmentation, multiple bins/read, coordinate/run wrapping, short final DMA groups, truncated/extra bins, wrong markers/order, early EOF, slow receiver and cancellation. Check decoded values and exact raw bytes independently.

Acceptance: deterministic captures render the expected images and retain every count without truncation; receiver errors cannot produce a successful capture.

## Phase E Flare master acquisition

Dependencies: A–D. Master is the first usable Flare acquisition milestone.

- [x] E01 Route master mode from the main window to the Flare control/acquisition service; guard the legacy manager against accidentally initializing NI for a Flare model. Audit main-window connect/start/stop, register-monitor actions, health/idle/reset checks, second-FPGA settings, chunk calculation and shutdown. Bypass NI bitfile validation, session creation, NI control processes and FIFO tuning throughout this path. Make NI-specific imports lazy enough to launch and run Flare without NI drivers; inspect optional packaging of NI libraries separately without changing existing installation behavior accidentally.
- [x] E02 Map application geometry and dwell to the complete Flare configuration: `pixels`, `lines`, `frames`, `repetitions`, `bins_per_pixel`, `dwell`, `packet_bins`, `channels`, `dummy`, `x_start`, `x_step`, `y_start`, `y_step`. Validate integer types, limits, product and scan endpoints. Calculate ticks from discovered clock and report effective rounded timing. Use actual repetition counts, not the legacy NI `max_repetition - 1` convention; initially reject circular repetition/points other than one.
- [x] E03 Define voltage/calibration conversion for signed DAC counts. Inherited `*_volts` names represent DAC counts. After REST configuration, stage complete XYZ axis arrays and COMMIT using the implemented firmware semantics. Apply live position/range edits during preview and recording with fixed stream dimensions, and restore requested L1-L4 enables after configuration. Keep snake/circular trajectories and measurement-linked laser/shutter/ADC/DFD/TTM workflows gated. Physical calibration remains H03; internal bin coordinates do not prove settled physical positions.
- [x] E04 Implement ordered start: discover/check idle; PUT full configuration; apply supported custom stopped registers; prepare output and receive workers; wait for listener ready; POST stream destination/settings; POST start; associate stream UUID and FPGA run ID; poll status and receive. Handle a connected socket followed by start failure, and an HTTP timeout with an uncertain start result. Never issue a duplicate start automatically.
- [x] E05 Implement completion, Stop, Reset, disconnect and error cleanup with distinct hardware, delivery and saving state. Capture final status before any destructive lifecycle change. Require validated bytes, matching successful service status and writer completion. On transmission failure show whether hardware is still draining; cancellation remains explicit. Bound worker shutdown and preserve incomplete files and error metadata. Close each run's sockets and create fresh files/connections for the next run.
- [x] E06 Implement preview using supported finite runs, proposed as repeated short raster acquisitions with new connections. Do not present finite captures as a supported continuous stream. Specify stop latency, frame refresh and expected gaps, and keep preview cancellation responsive. Enable batch and software-trigger workflows only when their lifecycle semantics pass tests.
- [x] E07 Test master connect, preview, acquisition, read/write, read all, stop, reset, reconnect and shutdown with NI imports/session/process creation made to fail if invoked. Test receiver-before-HTTP-response, ambiguous HTTP completion, active remote run, stream failure with ongoing DMA drain, final status races and writer failures.

Acceptance: the complete master workflow works against a simulator without NI; connected-board acceptance remains H02/H03.

## Phase F Recording and conversion

Dependencies: D02/D03; lifecycle metadata integrates with E04/E05.

- [x] F01 Preserve original Flare bytes in a distinct, explicitly identified raw format. Define Flare filenames and versioned metadata through storage services. Never label 120/216-byte bins as legacy NI FIFO raw or send them to the NI converter. Preserve existing NI/PI filenames, metadata keys and decoding behavior.
- [x] F02 Save accepted configuration, custom registers/masks, master/slave mode, firmware/schema/board identity, FLR4 mapping, bin length, clock/effective dwell, calibration, UUID/run ID, requested/effective stream settings, receiver and disk counts, final status, validation and complete/partial/cancelled result. Record start/end times with timezone. Exclude credentials and retain diagnostic snapshots even when start fails.
- [x] F03 Define a Flare HDF5 schema/version before writing files. Existing NI conversion stores U16 counts, so use U32 per-bin Flare counts and sufficiently wide sums without silently changing the stable NI format 0.0.1. Reuse dataset ordering and metadata conventions where applicable; explicitly handle absent auxiliary/analog datasets. Verify analysis tools/readers against the Flare schema.
- [x] F04 Implement direct HDF5 recording and offline Flare raw-to-HDF5 conversion from the same decoded count batches. Add dispatch by explicit format identity; retain the existing converter entry points. Preserve partial captures and mark them incomplete instead of silently padding or truncating to nominal geometry.
- [x] F05 Compare raw conversion and direct HDF5 values, shapes and metadata for both channel modes, multiple repetitions/frames and high counts. Exercise disk full/write failures, interrupted files, absent metadata, invalid raw lengths and viewer loading. Run existing storage/metadata compatibility tests.

Acceptance: preview and saved counts agree; conversion is lossless; old files and converters retain their behavior.

## Phase G Flare slave mode

Dependencies: reusable Flare control, receiver, decoder and storage from B/D/F; future low-level external-timing support. Prepare the software boundaries now, then complete these tasks when that contract exists.

- [ ] G01 Agree and document the firmware/API contract for NI pixel/line/frame timing: electrical polarity and edges, arm/ready, clocks and bins, geometry, first/last bin, external trigger loss, stop/drain, DAC ownership and format identity. Determine how support is advertised by firmware/schema/capabilities. Current readable timing inputs do not mean external scanning is implemented; do not invent a REST mode field or capability bit.
- [ ] G02 Implement slave routing with NI scan control and Flare detector data, keeping NI detector FIFO reads off. Preserve NI scan register behavior while isolating Flare detector settings. Reuse the Flare decoder and recording path to provide image preview, traces, fingerprint and saving equivalent to the existing detector workflows.
- [ ] G03 Implement synchronization from the agreed contract: Flare receiver ready, detector armed, then NI scan start. Never let Flare drive scan outputs while NI owns scanning; require verified firmware behavior rather than relying on zero step settings. Define coordinated stop/reset ordering and record both devices' status and failures.
- [ ] G04 Test synthetic external triggers, readiness deadlines, dropped/missing triggers, count/geometry mismatches, stop/restart and recovery. Validate physical timing and saved channel counts with NI plus Flare. Remove the acquisition block only for an explicitly supported and tested firmware contract.

Acceptance: NI scans while Flare acts as the detector; preview and recordings align with NI geometry. Until then, Slave remains selectable for configuration/debugging and unavailable for acquisition, with an explicit reason.

## Phase H Regression and hardware acceptance

Dependencies: relevant implementation phases. Master release may finish while G remains blocked and clearly labelled.

- [x] H01 Run focused simulator/client/decoder/controller/storage tests, then the repository checks in CONTRIBUTING: normal pytest, separate channel-delay and Qt console suites, docs checker, lint checker and compileall. Inspect skips. Run a master-mode smoke test in an environment without NI drivers. If packaging changes, also run build/distribution checks.
- [x] H02 On `mmskria3:8081`, verify firmware/schema and an idle device, receiver reachability and supported registers. Test scratch write/readback, full register read, logs, 25/49-channel captures and concurrent supported live writes. Start with dummy acquisition and zero scan motion; dummy mode does not suppress physical detector events or disconnect outputs. Record device versions, settings and measured results.
- [ ] H03 Validate calibrated XY motion, axis orientation, timing, known pulse counts, image geometry, counts above U16 where feasible, saved metadata and offline conversion. Measure DAC behavior at intended scan speeds because internal timing can exceed physical DAC settling. Validate physical Z only if E03 enables it.
- [ ] H04 Exercise sustained recording at the intended rate, receiver stall/disconnect, service loss, overflow, stop versus reset, reconnect and file failure. Confirm failed delivery never reports success and hardware drain/hold/zero behavior is reported accurately. Repeat NI SPAD and PI SPAD23 connect/preview/HDF5/RAW/stop/reconnect smoke tests.
- [x] H05 Update the user/architecture/storage docs with supported firmware, Windows listener/firewall setup, calibration, mode limitations, log/debug instructions and recovery behavior. Record completed master acceptance independently of slave acceptance. Link the final verification evidence and leave incomplete capabilities unchecked.

Release acceptance also requires N06. Passing Flare tests does not complete the non-Flare compatibility gate.

## Implementation decisions and remaining acceptance

Flare uses a dedicated acquisition service and a receive thread, with explicit main-window routing. The legacy manager retains NI behavior and rejects accidental Flare connections/runs. Generated Designer code was regenerated from the UI source. Flare's own U32 HDF5 format is `brighteyes-flare-1`; legacy files keep their formats. [User instructions and protocol details](flare.md) describe the implemented controls and limitations.

The default receiver port is now 9000, matching successful live checks. An automatic ephemeral-port callback timed out on this workstation; HTTP control remains 8081. Port 0 remains an option when inbound access is configured.

E06 delivers repeated finite preview and explicitly gates unsupported batch/software-trigger workflows. E03 now delivers nominal XYZ DAC-array staging, live position/range writes and L1-L4 requests. Physical motion/calibration requires H03 acceptance; completing the software tasks does not establish settled positions or connector waveform quality.

Hardware acceptance remaining: N06 and H03/H04 require attached NI/PI instrument regression, measured calibration/direction and known pulse counts, throughput/endurance and network/disk failure exercises at the intended operating rate. No physical scan calibration or sustained-rate claim is made. G01–G04 remain blocked by future slave timing support. H01 software checks passed as recorded below.

## Preview refresh follow-up

- [x] Replace only newly visited pixels, keeping the previous frame visible elsewhere, including between finite preview runs. Preserve time-bin accumulation across TCP batches and initialize a fresh image for a new session or incompatible geometry.
- [x] Verify incremental refresh, frame/repetition boundaries, preview continuation and non-Flare compatibility: 48 focused tests passed. Lint reported 0 new findings; documentation and compilation checks passed. No hardware commands were needed for this visualization fix.

## Advisory validation follow-up

- [x] Report configured X/Y voltage-limit violations as warnings in the selected Flare panel and continue preview/acquisition with the requested coordinates. Keep invalid coordinates, physical DAC limits and acquisition/protocol failures blocking.
- [x] Verify both axes, lower/upper limits, preview/acquisition, warning visibility and legacy isolation: 60 focused tests passed. Lint: 0 new findings. Documentation and compilation checks passed. No hardware commands issued.

## Live preview geometry follow-up

- [x] Keep X/Y center and range editable during Flare preview and apply the latest control or pan/zoom values to the next finite scan. Keep recording geometry, pixel counts, timing, calibration and Z locked. The original firmware restricted axis writes to stopped hardware; applying GUI geometry between finite scans also preserves receiver consistency with firmware 1.0.4.
- [x] Render incoming data using its captured scan geometry while edits are pending. Fit the view when a new scan area takes effect and preserve manual navigation during other image updates. Route preview redraws through the Flare renderer and leave NI/PI behavior unchanged.
- [x] Verify XY/YX navigation, next-scan configuration, control restoration, image coordinates and an actual pyqtgraph view. All 65 focused Flare/compatibility checks passed within the full suite. Full run: 438 passed, 2 PI recorder timeouts, 9 isolated tests deselected and 44 subtests passed. Both timeouts passed on targeted rerun; the complete PI recorder module then passed all 56 tests. Lint: 0 new findings. Docs and compilation checks passed. No hardware commands issued.

## Firmware 1.0.4 live register follow-up

- [x] Review `brighteyes-flare` revision `2985e2f` (2026-10-21). Capability bit 4 advertises laser registers; bit 5 makes all implemented writable registers live, including raw commands. Follow discovered policies instead of inferring access from firmware version, and retain legacy restrictions and HTTP error reporting.
- [x] Resolve numeric register addresses consistently during local acquisitions. Restore detector masks and hold-off after configuration for both `stopped` and `live` policies. Preserve managed finite-run geometry and lifecycle behavior.
- [x] Document laser enables, MMCM clock registers, raw staging/COMMIT semantics and reset behavior. Laser settings remain explicit debug controls; no automatic measurement-linked sequencing or laser restoration is implemented.
- [x] Verify 95 focused Flare/compatibility tests and the latest source service catalog: 63 registers, all 28 live writable entries accepted by the mocked client and all 35 read-only entries blocked. Full suite: 470 passed, 9 isolated tests deselected, 44 subtests passed. Separate channel-delay suite: 4 passed; isolated console suite: 5 passed. Lint: 0 new findings; documentation, compilation and changed-file whitespace checks passed. No hardware commands issued.

## Server-authoritative writes and live GUI controls

- [x] Submit register writes to REST even when absent from the catalog or advertised as stopped, command or read-only. Let the server validate access and values; report its HTTP status/errno/message unchanged. Keep JSON parsing and coordinate conversion in the GUI.
- [x] Send X/Y/Z position/range and extra-offset edits through complete native DAC arrays followed by COMMIT. Coalesce edits for 80 ms off the GUI thread, including preview pan/zoom and normal recording. Keep stream dimensions, timing and calibration fixed during capture.
- [x] Route L1-L4 checkboxes to integer enable writes. Remove their acquisition veto and restore requested states after every configuration reset, including finite preview repeats. Retain server errors and avoid automatic retries after failed writes.
- [x] Serialize live writes, raw debug writes, scan configuration and start/stop against one shared I/O lock. Keep desired-state updates independent of that lock so Qt stays responsive while requests are in flight. Record timestamped values/readbacks/errors in acquisition metadata and update displayed geometry after accepted COMMIT.
- [x] Give Read, Write and Read all independent background workers and cached discovery. Test that Qt timers and independent reads continue while Read all or Write waits for a server response; serialize only conflicting writes/configuration/lifecycle operations.
- [x] Route Flare wheel/pan directly through batched spatial-widget updates, avoiding legacy callbacks and full-profile reads during a gesture. Preserve the manual view when COMMIT completes and finite preview frames advance. Verify real pyqtgraph wheel/pan events in XY and YX.
- [x] Final automated validation: 496 full-suite tests passed, 9 isolated tests deselected, 44 subtests passed. Separate channel-delay suite: 4 passed; isolated console suite: 5 passed. Final focused Flare/compatibility checks, lint (0 new findings), documentation, compilation and changed-source whitespace checks passed.
- [ ] Complete connected-board acceptance for these live controls, including physical XYZ calibration and laser waveforms. Final automated regression results are recorded in the session table.

Earlier follow-up sections above record the previous implementation and its validation. This section supersedes their client-side access gates, next-scan-only geometry and debug-only laser restrictions.

## Square preview pixels follow-up

- [x] Match FPGA-SPAD navigation by using the smaller visible span for both scan ranges, rather than stretching X/Y independently to fill a rectangular viewport. Keep the existing asynchronous register writes and manual-view preservation.
- [x] Verify real wheel and pan events in wide/tall previews and XY/YX projections. Check equal rendered pixel dimensions for square sampling after each live COMMIT, and compare resulting range/center controls directly with the FPGA-SPAD handler. Focused GUI/main-window/compatibility suite: 75 passed.
- [x] Full suite: 504 passed, 9 isolated tests deselected, 44 subtests passed. Separate channel-delay suite: 4 passed. Isolated console suite: 5 passed on a standalone rerun after the concurrent invocation stalled and was interrupted. Lint: 0 new findings; documentation and compilation checks passed.

## Immediate preview transform follow-up

- [x] Decouple displayed geometry from COMMIT confirmation. Remap the cached image synchronously inside the position/range or mouse event, before the 80 ms timer and HTTP requests. Change only the image transform during gestures, avoiding image processing and histogram/level recalculation.
- [x] Keep the latest requested display geometry when queued old frames or older COMMIT responses arrive. Preserve confirmed acquisition geometry and register-event metadata separately. New preview sessions reset the local display override.
- [x] Extend real wheel/pan checks to verify the requested image rectangle before any hardware write or new frame, then verify old frames and completed COMMITs do not change that transform. Test two in-flight area requests with server responses deliberately withheld.
- [x] Validation: 76 focused GUI/main-window/compatibility checks passed; full suite: 505 passed, 9 isolated tests deselected, 44 subtests passed. Separate suites: 4 channel-delay and 5 console checks passed. Lint: 0 new findings; documentation, compilation and changed-source whitespace checks passed.

## Session record

| Date | Completed work | Validation and blockers | Next task |
| --- | --- | --- | --- |
| 2026-10-20 | P00–P03; branch and integration plan | Documentation checker: 0 errors. Git diff whitespace check: passed. Planning only; no hardware commands issued. Slave acquisition awaits the external-timing contract. | A01 |
| 2026-10-20 | Added explicit non-Flare compatibility invariant and N01–N06 checklist | Requires baseline comparisons, inactive Flare isolation, old-profile/UI checks, switching cleanup and regression/hardware evidence before release. | N01, then A01 |
| 2026-10-20 | Implemented A–F, automated N01–N05, H02 diagnostics/captures and H05 documentation | Baseline: 375 tests plus 4 channel-delay and 5 isolated console checks passed. Intermediate full suite: 411 passed with Flare construction forbidden in existing workflows. Real window selection/restoration and no-NI-import smoke checks passed. Live board: firmware 1.0.2/schema 3, 53 registers, scratch restored to 0; 25/49-channel 257-bin captures (30840/55512 bytes), live read/write and read all passed on receiver port 9000; board reset/idle afterward. Final post-edit checks pending. | H01 final checks; N06 and H03/H04 physical acceptance; G01 when firmware supports slave timing |
| 2026-10-20 | H01 software verification complete | Full suite: 416 passed, 9 isolated tests deselected, 44 subtests passed. Separate channel-delay suite: 4 passed. Separate console suite: 5 passed after keeping the compatibility fixture out of the isolated Qt/Jupyter lifetime; an earlier invocation crashed and was cleaned up. Lint: 0 new findings. Docs: 0 errors. Compileall passed. Native service/main-window imports work with NI packages forbidden; real GUI startup, zero-range rendering, profile selection and legacy restoration passed without network access. Flare storage/reader/converter and disk-write failure checks passed. | N06 and H03/H04 attached-instrument acceptance; G01 when firmware supports slave timing |
| 2026-10-21 | Firmware 1.0.4 live register compatibility from source revision `2985e2f` | Numeric-address writes now work during local runs; detector masks/hold-off survive configuration with live policies. Updated laser/raw-register documentation. 95 focused and 470 full-suite tests passed; 4 channel-delay and 5 isolated console checks passed. Latest service catalog checked offline: 28 live writable and 35 read-only registers. Lint, docs, compilation and changed-file whitespace passed. No hardware commands issued. | Connected-board validation with firmware 1.0.4; N06 and H03/H04 physical acceptance; G01 when slave timing is supported |
| 2026-10-21 | Server-authoritative register writes, live XYZ/L1-L4 controls, independent diagnostics and smooth preview navigation | Removed local register policy vetoes. Reapply desired controls after reset and record live changes. Slow register operations leave Qt and independent reads responsive; real XY/YX wheel and pan preserve the view across COMMIT/data updates. Full suite: 496 passed, 44 subtests passed, 9 isolated tests deselected. Separate suites: 4 channel-delay and 5 console checks passed. Lint, docs, compilation and changed-source whitespace passed. | Connected-board validation of live XYZ/laser controls; N06 and H03/H04 acceptance |
| 2026-10-21 | Restore square Flare preview sampling during pan/zoom | Match FPGA-SPAD's common visible span while preserving the mouse view and asynchronous writes. Real wide/tall XY/YX tests check square rendered pixels and compare both handlers. Focused checks: 75 passed; full suite: 504 passed and 44 subtests passed. Separate suites: 4 channel-delay and 5 console checks passed (console rerun alone). Lint, docs and compilation passed. | Connected-instrument acceptance remains pending |
| 2026-10-21 | Immediate Flare image remapping during navigation | Cached-image transforms follow requests within the mouse event, independently of the write timer, COMMIT and incoming frames. Confirmed acquisition geometry remains separate. Real gesture tests check transforms before server writes, and a delayed-server test covers overlapping requests. Focused checks: 76 passed; full suite: 505 passed and 44 subtests passed. Separate suites: 4 channel-delay and 5 console checks passed. Lint, docs, compilation and changed-source whitespace passed. | Connected-instrument acceptance remains pending |
| 2026-10-26 | Schema-4 DFD1 and six-slot laser sequencer integration from Flare `fc5f8a9` | Existing DFD/laser/lifetime controls select backend-specific configuration and framing. U16 histograms/reference survive HDF5 and offline conversion; shared NI/Flare lifetime rendering, full run-ID validation and partial/fault handling covered. Full suite: 546 passed, 44 subtests passed; 4 channel-delay checks passed. All 5 console checks passed in separate processes; the combined isolated console invocation hit a Windows Qt/Jupyter access violation. Final DFD metadata checks: 34 passed. Lint: 0 new findings; docs and compilation passed. No hardware commands issued. | Connected-board DFD clock/sequence/reference validation, physical lifetime calibration and existing instrument acceptance remain pending |
