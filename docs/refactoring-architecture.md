# BrightEyes-MCS refactoring architecture

The package is organized by responsibility. Internal imports may change during
a focused refactor; published REST and plug-in interfaces must remain compatible.
The legacy `.cfg` schema and HDF5/RAW formats are stable external contracts.

## Package boundaries

The [current architecture](current-architecture.md#package-ownership) lists the
implemented packages and their owners. Keep new code within those boundaries;
do not reintroduce the removed mixed-purpose `libs` or `gui` packages.

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

Pure scan-duration and ETA calculations already live in the statistics controller.
Timers and widget updates stay in `MainWindow`. Further extraction candidates are:

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

Use the existing application path helpers; do not change the working directory or
write into installed package resources. The [current architecture](current-architecture.md)
describes profile migration and user-writable paths.

## Hardware acceptance checklist

Automated tests do not replace validation on attached instruments. Before a
release, validate SPAD and PI23 connect, preview, normal acquisition, RAW
acquisition, stop, reconnect, HDF5 conversion, TTM, plugins, and REST startup.
