# FLARE 1.9 integration status

Updated: 2026-11-03. Software implementation and verification complete.
Physical acceptance is pending. No software blocker remains.

## Requested scope

- Normal mode: DMA1 intensity only.
- DFD mode: DMA2 scoped DFD3 uint32 only.
- PL circular XYZ arrays, using the existing SPAD trajectory controls and explicit native DAC-count conversion.
- No PS-to-PL position stream, simultaneous outputs, or scan-only workflow.
- Preserve NI/SPAD and older FLARE service behavior where capabilities permit.

## Resume checklist

- [x] Read `BRIGHTEYES_MCS_1_9_MIGRATION.md`, `MULTI_DMA_V3_API.md`, the service implementation and reference decoder in the external repository `C:/Users/madonato/Documents/GitHub/tmp/brighteyes-flare` (documents under its docs directory).
- [x] Inspect existing acquisition, UI, decoder and storage boundaries.
- [x] Add capability-gated single-stream configuration and lifecycle handling.
- [x] Port DFD3 decoding, exposure metadata, uint32 storage and offline conversion.
- [x] Connect the existing circular controls to PL arrays; validate order and retain circular dimensions.
- [x] Run protocol/storage/UI and legacy regression tests and record results below.
- [ ] Physical normal/DFD 25/49-channel and circular scan acceptance on mmskria3.

## Workspace and resuming

The workspace already had uncommitted changes in FLARE config, DFD, acquisition,
worker, storage, UI/controller/generated UI, documentation and tests, plus
`test/test_flare_packet_sizing.py`. Preserve them. No commits or resets were made.
There were no applicable AGENTS.md files found in the two repositories.

Read this file and `docs/flare-integration-plan.md`, inspect
`git -c safe.directory=C:/BrightEyes-MCS status --short`, then continue unchecked
software items. Git requires the per-command safe.directory option under the
sandbox account; do not change the user's global git configuration.

## Implemented behavior and files

- `brighteyes_mcs/acquisition/detectors/flare/v19.py`: ABI-3 capability checks,
  exclusive DMA selection, PL array validation/conversion, accepted geometry,
  common START and per-stream completion validation. Normal intensity metadata
  also contains inactive DFD settings; stream selection uses the actual format.
- `brighteyes_mcs/acquisition/detectors/flare/config.py` and
  `brighteyes_mcs/acquisition/flare_worker.py`: discover capabilities for each run,
  build the corresponding request, size packets using the negotiated DFD3 layout.
  Older services receive no new configuration keys.
- `brighteyes_mcs/acquisition/detectors/flare/dfd_scope_format.py`: MIT reference
  SCP1/DFD3 parser port. Fragmented TCP, full run ID/ordinal/trajectory identity,
  scope/group flags, lengths and padding are validated.
- `brighteyes_mcs/acquisition/detectors/flare/dfd.py`: retain DFD1/DFD2 support;
  add uint32 DFD3 and exact point-window exposure/coordinate validation. Preview
  sums use uint64; circular intensity/RGB visits accumulate into raster pixels.
  DFD decay normalization uses decoded exposure ticks.
- `brighteyes_mcs/acquisition/flare.py` and
  `brighteyes_mcs/hardware/flare.py`: one selected listener, explicit
  `/streams/intensity` or `/streams/dfd`, one common START. Preserve the common
  run ID and accepted metadata. Scan completion, selected sender completion,
  exact byte counts and decoding must all pass. A V3 reader error aborts the
  owned common run and leaves the recording incomplete.
- `brighteyes_mcs/acquisition/detectors/flare/controls.py`: snapshot desired
  controls for atomic configuration. V3 masks/holdoff/laser requests are sent
  during configuration; post-configuration raw writes would invalidate START.
- `brighteyes_mcs/ui/controllers/flare.py` and
  `brighteyes_mcs/ui/qt/main_window.py`: use the existing SPAD-generated circular
  offsets, pass floating calibrated volts to the worker, then convert explicitly
  to native DAC counts. Bypass the NI array-upload path for FLARE. Freeze circular
  geometry during each run; finite preview reads settings again between runs.
  DFD3 extra/reference channels remain separate from physical detector channels.
- `brighteyes_mcs/storage/flare.py`: DFD3 uint32 window/phase/channel data with
  per-window coordinates, ticks, scope/group flags and identities. Container ID
  `brighteyes-flare-dfd-3`; circular intensity has explicit eight-dimensional
  data under `brighteyes-flare-circular-1`. Ordinary and expanded time-bin counts
  remain separate. RAW conversion retains counts, window metadata and completion
  state. Existing ordinary intensity and DFD1/DFD2 container IDs are unchanged.
- `test/test_flare_v19.py` and `test/test_flare_ui.py`: single DMA, 25/49 channels,
  fragmentation, uint32 values above 65535, header wrapping, circular bypass and
  repeated single points, HDF5 conversion, UI array handoff, atomic configuration
  and failed/truncated runs.

## Validation and blockers

No physical acquisition or board mutation has been attempted. No software
blocker is currently known.

The first full regression run reported 687 passed, 1 failed, 9 deselected and
44 subtests passed. The failure was a timeout in
`test_recorder_can_restart_after_failed_image_server_start` (PI SPAD23 vendor
recorder); rerunning that test alone passed. No PI recorder code was changed.
Lint, local documentation links and compileall passed after implementation.

Final verification on Windows using the existing `.venv` (Python 3.13):

- Full regression: `python -m pytest -q` with `QT_QPA_PLATFORM=offscreen`:
  **694 passed, 9 deselected, 44 subtests passed**. One existing NumPy matrix
  PendingDeprecationWarning in the main-window fingerprint test.
- After the final stream-discrimination/container-format adjustments,
  `python -m pytest test/test_flare_v19.py test/test_flare_dfd.py test/test_flare_ui.py -q`:
  **193 passed**. This includes all 42 firmware-1.9 protocol/storage tests.
- `python scripts/check_lint.py`: **0 new findings**, 332 baseline findings.
- `python scripts/check_docs.py`: **0 errors**.
- `python -m compileall -q brighteyes_mcs scripts`: passed.

The separate Qt-isolated console suite and channel-delay widget unittest were
not rerun in this increment; their code was not modified.

## Next work when resuming

1. Read the final validation results below, inspect the working diff, and retain
   the pre-existing changes listed above. If software verification was interrupted,
   rerun `.venv/Scripts/python.exe -m pytest -q` with `QT_QPA_PLATFORM=offscreen`.
2. On mmskria3, discover firmware capabilities and confirm ABI 3/DFD3. Exercise
   normal DMA1-only and DFD DMA2-only at 25 and 49 physical channels with laser
   requests off initially. Verify common run IDs, exact lengths and final status.
3. Repeat with circles disabled, one point/one repetition (array bypass), one
   point/multiple repetitions, and multiple points/repetitions. Verify the actual
   calibrated XYZ trajectory separately from transport; test long expanded
   intensity bin counts that wrap the eight-bit header fields.
4. Check preview responsiveness, Stop/error incomplete labels, reconnect/reconfigure,
   HDF5 window metadata and RAW conversion on real captures. Keep calibration/
   reference-alignment failures distinct from decoder/transport failures.
5. Perform the existing NI/SPAD and PI hardware regression gate from the original
   integration plan before releasing. Mock tests do not complete hardware acceptance.

PS position streams, simultaneous outputs, scan-only operation, grouped/coarse
DFD scopes and generic analysis-reader support for the new window axis remain
outside this requested increment.
