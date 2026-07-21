# BrightEyes-MCS plug-ins

Built-in implementations live in `builtin/`. The plug-in framework itself is
kept separate in `api.py`; acquisition, storage, and GUI internals should not be
copied into plug-ins.

To add a plug-in, copy `_template` into `builtin/<plugin_name>` and edit
`plugin.py`. A plug-in needs only two declarations:

```python
PLUGIN = PluginMetadata(name="example", display_name="Example")

def setup(context):
    ...
```

Use `context.add_tab(widget, caption)` for UI, `context.on(event, callback)` for
application events, and `context.service(name)` for supported application
services. Per-instance state can be stored directly in `context` as a mapping.

Avoid reaching into `context.main_window` unless the plug-in needs a legacy Qt
control that is not yet exposed as a service.
