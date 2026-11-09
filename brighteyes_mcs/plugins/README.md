# BrightEyes-MCS plug-ins

BrightEyes-MCS discovers plug-ins in two locations:

1. packaged implementations in `brighteyes_mcs/plugins/builtin/`;
2. the **Plug-ins folder** selected in the active microscope profile.

The two lists are combined. A profile plug-in with the same directory name as a
packaged plug-in overrides the packaged implementation. Only place trusted
Python code in a profile's plug-ins folder.

To add a profile plug-in, copy `_template` to
`<profile plug-ins folder>/<plugin_name>` and edit `plugin.py`. Its layout is:

```text
<plugin_name>/
├── plugin.py
├── helper.py       # optional
└── gui/            # optional
```

A plug-in needs only two declarations. Import the API by its absolute package
name so the same code works both inside and outside the BrightEyes-MCS source
tree:

```python
from brighteyes_mcs.plugins.api import PluginMetadata

PLUGIN = PluginMetadata(name="example", display_name="Example")

def setup(context):
    ...
```

Do not use a source-tree-relative import such as
`from ...api import PluginMetadata` in a profile plug-in. Imports within the
plug-in package can remain relative, for example `from .helper import VALUE`.

The plug-in framework itself is kept separate in `api.py`; acquisition,
storage, and GUI internals should not be copied into plug-ins.

Use `context.add_tab(widget, caption)` for UI, `context.on(event, callback)` for
application events, and `context.service(name)` for supported application
services. Per-instance state can be stored directly in `context` as a mapping.

Avoid reaching into `context.main_window` unless the plug-in needs a legacy Qt
control that is not yet exposed as a service.


## Preview / Acquisition hardware hooks (API 2.1)

Register `context.on_run(before, after)` in `setup(context)`. Both callbacks
receive a mode string, `"preview"` or `"acquisition"`. The synchronous `before`
callback runs before acquisition workers or recording start. Return only when
the hardware has confirmed readiness; raise an exception to abort startup.
Callbacks run on the GUI thread: use bounded waits that process Qt events for
asynchronous serial devices, rather than sleeping or waiting indefinitely.

The paired `after` callbacks run in reverse order on manual Stop, normal
completion, or startup failure, including the callback whose setup failed.
Cleanup must therefore tolerate partially completed setup. Cleanup errors are
logged and shown in the status bar, and other plug-ins still get their cleanup.
A continuous Flare preview uses one pair across all its finite frames.
The legacy `beforeRun` and `acquisitionDone` events remain available, but do not
provide this paired hardware preparation contract.

DAC_ino provides an idle voltage, an Enable checkbox, and a Preview / Acquisition
voltage (default 5 V) for each channel. Idle voltage applies when editing finishes
(Enter or leaving the field). Connect the DAC first, enable channels, then start
Preview or Acquisition. Each enabled output must acknowledge its run voltage
before startup; enabled outputs return to their idle voltages afterward.
Other channels stay at their manually configured idle voltages.
Selections and run voltages, plus enabled channels' idle voltages, are frozen
during a run. No output is changed just by loading the plug-in or selecting a
checkbox. If the serial link fails, software cannot confirm restoration of the
idle voltages; check the hardware and the debug log.


DAC settings use `cfg/plugins_cfg/DAC_ino.cfg` through the existing plug-in
configuration system, rather than QSettings. The file stores `serial_number`,
`port` (used when the serial number is empty), `auto_connect`, and four-element
`idle_voltages`, `run_voltages`, and `enabled` arrays. Use **Save configuration**
in the DAC tab or the application's plug-in CFG save controls to save changes.
The main microscope CFG records the DAC CFG path in `plugins.configs.DAC_ino`.

**Auto-connect** defaults to off. When enabled in the DAC CFG, loading the
plug-in or applying a microscope CFG first updates all DAC controls, then opens
the matching converter. Reloading a CFG keeps an existing connection open.
Connecting performs the normal handshake and readback; it does not apply idle
voltages automatically. To open DAC_ino at application startup, include
`"DAC_ino"` in the main CFG's `plugins.autoload` list.
