# BrightEyes-MCS refactoring architecture

The package is organized by responsibility. Python import compatibility is not
a design constraint; the legacy `.cfg` schema and HDF5/RAW formats are the
stable external contracts.

## Active boundaries

- `application`: service contracts, GUI gateway, bootstrap, and path policy.
- `acquisition`: acquisition settings and state, coordinator, worker processes,
  FIFO access, shared memory, and canonical SPAD/PI23 detector pipelines.
- `hardware`: NI-FPGA and TTM adapter surface.
- `storage`: the legacy `.cfg` codec and translation boundary, HDF5 schema, and
  RAW conversion.
- `api`: external control surfaces.
- `ui/controllers`: framework-independent configuration, lifecycle, and preview
  behavior.
- `ui/qt`: Qt widgets, generated Designer code, and the main-window adapter.
- `plugins/api.py`: the small API available to plug-in authors.
- `plugins/builtin`: isolated built-in plug-in implementations.
- `logging_setup.py`: standard-library logging configuration shared by the
  application and acquisition worker processes.

The former mixed-purpose `brighteyes_mcs.libs` and `brighteyes_mcs.gui`
packages have been removed. There are no compatibility import shims.

## Dependency direction

Acquisition settings and lifecycle state live next to the coordinator that owns
them. Application services coordinate acquisition, hardware, storage, and
plug-ins. Qt adapts those services for users; storage owns every serialized-format
mapping. Acquisition workers may depend on hardware transports and storage
clients but never on Qt.

The package deliberately has no generic `domain`, `models`, or `core` bucket.
New code is placed next to the capability that owns it. The legacy `.cfg`
translator is named explicitly in `storage/legacy_config.py`; it does not define
the in-memory acquisition settings.

## Logging

The application bootstrap configures Python's standard `logging` package and
writes logs to a user-writable location. `%LOCALAPPDATA%/BrightEyes-MCS/log` is
used on Windows, with `BRIGHTEYES_LOG_DIR` available as an explicit override.
The old `core.logging.print_debug` module and package have been removed.

## Plug-in contract

Every built-in plug-in is a package containing `plugin.py` with
`PLUGIN = PluginMetadata(...)` and `setup(context)`. The context exposes tabs,
events, named services, and per-instance state. `_template` is the starting
point for new plug-ins.

## GUI direction

`MainWindow` remains the legacy composition root, but new behavior belongs in a
controller or service. Continue extracting one user workflow at a time:

1. acquisition setup/start/stop into an acquisition presenter;
2. preview rendering into a preview presenter and focused Qt view;
3. configuration widget mapping into a form adapter;
4. TTM and HTTP panels into independent widgets;
5. generated Designer files remain data-only and are never edited manually.

This incremental presenter approach allows hardware validation after each slice
instead of replacing the full GUI in one untestable rewrite.

## Compatibility checks

Configuration tests round-trip every tracked `.cfg`, including unknown keys and
plugin payloads. HDF5 tests lock format version `0.0.1`, group names, dataset
shape and dtype, and legacy public GUI metadata keys. RAW tests lock `uint64`
counter and metadata behavior.

On Windows with Python 3.13, the channel-delay Qt widgets must run in a dedicated
interpreter because PySide finalizers can cause an access violation when followed
by multiprocessing primitive creation. The normal pytest run excludes the
`qt_isolated` marker; CI runs that module separately with `unittest`.

## Runtime paths

Immutable images and defaults are resolved relative to the installed package;
the process working directory is no longer changed. On first run, default and
plugin configuration files are copied to `%APPDATA%/BrightEyes-MCS`. An existing
package-local `cfg/current_system` selection is imported. Explicit legacy paths
remain valid and the copied JSON payload is not transformed.

## Hardware acceptance checklist

Automated tests do not replace validation on attached instruments. Before a
release, validate SPAD and PI23 connect, preview, normal acquisition, RAW
acquisition, stop, reconnect, HDF5 conversion, TTM, plugins, and REST startup.
