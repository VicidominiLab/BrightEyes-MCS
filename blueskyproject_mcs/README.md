# BrightEyes Bluesky Device

This is a small standalone Bluesky/Ophyd project for the BrightEyes-MCS low-level FPGA register map documented in:

`../docs/BrightEyes-MCSLL-registers.md`

The project exposes an Ophyd `Device` named `BrightEyesMCSLLDevice`. Each FPGA register is represented as an Ophyd signal with a safe Python attribute name, while the original register name is preserved in the signal metadata.

The markdown documents some channel families with only channel 7 shown. Those families are expanded here for channels 0 through 7:

- `AnalogOUT{0..7}`
- `AnalogSelector_{0..7}`
- `AnalogOutDC_{0..7}`
- `AnalogA{0..7} invert`
- `AnalogA{0..7} integrate`
- `AnalogIN{0..7}`

## Install

From this folder:

```powershell
python -m pip install -e .
```

For NI FPGA hardware access, install the NI FPGA Python package in the same environment.

## Basic Usage

```python
from brighteyes_bluesky import BrightEyesMCSLLDevice, MappingRegisterIO

io = MappingRegisterIO({"max_pixel": 512, "max_line": 512, "start_command": False})
mcs = BrightEyesMCSLLDevice(name="mcs", register_io=io)

mcs.reg_max_pixel.put(300)
mcs.reg_max_line.put(300)
mcs.reg_start_command.put(True)

print(mcs.reg_max_pixel.get())
print(mcs.read_registers("max_pixel", "max_line", "start_command"))
```

With an existing `nifpga.Session`:

```python
from brighteyes_bluesky import BrightEyesMCSLLDevice, NifpgaRegisterIO

mcs = BrightEyesMCSLLDevice(
    name="mcs",
    register_io=NifpgaRegisterIO(session),
)

mcs.reg_start_command.put(True)
```

The original FPGA register names are available through:

```python
mcs.describe_register("max_time_bins_per_pixel")
mcs.get_signal("max_time_bins_per_pixel").put(10)
```

## Notes

This project maps registers and FIFO metadata. It does not implement BrightEyes acquisition orchestration; it gives Bluesky a clean device surface that can be used in plans and connected to the existing NI FPGA session layer.
