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
