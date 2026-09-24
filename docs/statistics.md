# Statistics and ETA

The Statistics dock shows FIFO progress, scan duration, preview delay, and an
estimated completion time. The grid fills the dock width while keeping labels
compact. Long raw-data counters wrap.

## Time displays

- Frame time and preview delay are in seconds.
- Total time uses **hours:seconds:minutes** (`hh:ss:mm`), retaining the existing
  display order. For example, 3,723 seconds is `01:03:02`. Hours can exceed 24.
- ETA uses local time in **YY/MM/DD hh:mm:ss**, for example `26/09/24 14:05:06`.

The configured scan duration is time-bin resolution (microseconds) multiplied by
time bins per pixel, X and Y pixels, frames, repetitions, circular points, and
circular repetitions, converted to seconds. Non-circular scans use a factor of
one for both circular settings. Displayed whole seconds are truncated; ETA
calculations retain the configured fractional seconds.

## Idle, preview, and acquisition

When neither preview nor acquisition is running, ETA means "completion if this
scan started now." A Qt timer refreshes it once per second using the current
configured duration and the local clock. Configuration changes appear on the next
tick. The idle timer does not overwrite preview or acquisition status.

Preview shows `--` rather than a finite completion estimate. During acquisition,
ETA uses the configured duration multiplied by the remaining FIFO fraction. With
multiple FIFOs, the least-complete valid FIFO determines that fraction. Progress
is clamped to 0?100%; FIFOs with non-positive expected counts are ignored. If no
valid expected counts exist, ETA shows `--`. Stopping returns to the idle estimate
on the next one-second tick.

This is a scan-data estimate, not a measured throughput prediction. It does not
budget laser startup waits, frame waits, external trigger delays, recorder startup
or tail time, or final disk flushing. These can make actual completion later.
Changing the system clock changes the displayed ETA. PI23 recorder duration is
calculated separately; see [time-tag recording](pi23-timetagging.md).
