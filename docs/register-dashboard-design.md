# Register dashboard design archive

Status: **removed from the application on 18 November 2026**. This document
preserves the design for reference. The application retains the register editor;
there is no dashboard implementation, feature switch, animation, or benchmark
script to enable.

## Purpose and navigation

The dashboard was a visual presentation of the same three sources used by the
editor: **Read Conf. FPGA**, **Conf. FPGA dict.**, and **Conf. GUI dict.**. Status
had separate **Dashboard** and **Registry editor** activities, each with those
three source tabs. **Circular** and **Monitor** remained alongside them.

Cards displayed large values, type/access labels, boolean lights, and optional
register identifiers and descriptions. Search matched names, values, and
descriptions; category and access filters narrowed the display. Recently changed
values briefly highlighted. Position arrays used side-by-side X/Y/Z readouts.

The final design used the dashboard for inspection. Double-clicking an object
opened the matching editor source and selected its original register path or
array element. Navigation refreshed current GUI values without an additional
hardware poll and did not write a value or start editing automatically. The
editor retained responsibility for typed validation and access checks.

## Instrument pages

The instrument gallery used compact pages to avoid increasing dashboard height.

| Page | Representation | Registers combined |
| --- | --- | --- |
| Optics and scan | Four colored laser lamps | Laser enable bits; readable source labels |
| Optics and scan | Excitation sequencer tiles | FPGA excitation sequence array, or individual GUI sequence settings |
| Optics and scan | XY scan field | Scan dimensions and current X/Y indices, when available |
| Timing and volume | Bin/pixel/line/frame timing chain | Bin duration, bins per pixel, X/Y dimensions, circular point/repetition counts |
| Timing and volume | Z-plane stack | Frame count, current Z index, repetition limit and repetition counter |
| Timing and volume | Scan trajectory | X/Y voltage arrays, or a labeled GUI circular-radius schematic |
| Signals and streams | Eight-channel analog mixing desk | Output readbacks, set values, source selectors and selected-axis voltage limits |
| Signals and streams | Detector-to-host routing diagram | Digital/analog/DFD enable bits, overflow flags and historical overflow counters |

### Optical objects

Enabled laser controls had a colored round core and a gently pulsing halo.
Unknown bits were shown as unavailable. The halo represented an enable bit,
not measured optical emission. Sequence tiles showed configured step codes,
not simulated execution or actual pulse timing. A tile navigated to its exact
FPGA array element or individual GUI configuration key.

The XY field showed a current-pixel marker only when both coordinates and the
configured dimensions were known. Double-clicking the field or dimension labels
selected the relevant status or dimension register.

### Derived timing and volume

For ordinary raster scanning:

```text
pixel sample duration = bin duration × bins per pixel
line sample duration  = pixel sample duration × pixels along X
frame sample duration = line sample duration × lines along Y
```

When circular scanning was enabled, pixel duration also included the configured
circular point count and circular repetition count. Missing counts made the
derived duration unavailable. These estimates excluded startup and frame waits.

Native FPGA timing stayed in clock cycles rather than assuming a clock
frequency. GUI timing used microseconds. The volume display used the existing
native repetition convention, `max_repetition - 1`; GUI `nrep` was used directly.
Out-of-range Z indices were identified rather than presented as valid progress.

### Trajectory and analog outputs

The trajectory preview used at most 128 XY voltage samples, equal voltage scales
on both axes, and no fabricated playback position. A GUI-only circular radius
was explicitly schematic. A Lissajous configuration without voltage arrays was
not drawn as a measured circle.

Analog faders preferred readback values. Set values and stored DC constants were
labeled separately. Gauges used actual limits for the selected X/Y/Z source;
missing or invalid limits did not create an assumed range. A stored DC constant
was not treated as a live spatial output when another source was selected.
Double-clicking a fader or its source label selected the corresponding register.

### Stream state

Routes combined stream enables with overflow flags and counters. An active
overflow flag was distinct from a historical non-zero counter. Double-clicking
history selected the counter rather than the flag. Missing state remained
unknown. The diagram did not estimate throughput or FIFO occupancy.

## Presentation and performance design

The implementation used styled Qt widgets and QPainter vector drawings. It did
not require HTML, a browser engine, external image assets, or additional
dependencies. QWidget operations stayed on the main GUI thread.

Performance measures included:

- No card construction or rendering while a dashboard was hidden.
- Combining visible refresh requests through a 100 ms single-shot timer.
- Updating values and styles only when the corresponding data changed.
- Bounded trajectory sampling and retaining only the latest snapshot for hidden
  instrument pages.
- A separate 400 ms presentation timer for laser halos, active only while the
  laser panel was visible and an enabled bit was known. An Animate control could
  stop it; it never polled or wrote hardware.

Synthetic timings excluded driver I/O and were machine-dependent. They were not
acquisition timing guarantees. The editor's useful optimizations remain:
unchanged-row caching, preserved indexes during value refreshes, and firmware
metadata resolved once per batch of view updates.

## Current application

Only the searchable, editable register views remain under **Status → Registry
editor**, with the three original source tabs. Dashboard drawing code, extra
models, timers, configuration switches, catalogs, and dashboard-specific tests
and benchmarking tools have been removed. See the
[current register editor documentation](current-architecture.md#register-views-in-status)
for supported behavior.
