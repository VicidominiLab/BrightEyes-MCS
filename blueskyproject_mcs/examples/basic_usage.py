"""Small simulated usage example for the BrightEyes Bluesky device."""

from brighteyes_bluesky import BrightEyesMCSLLDevice, MappingRegisterIO


def main() -> None:
    register_io = MappingRegisterIO({"max_pixel": 512, "max_line": 512, "start_command": False})
    mcs = BrightEyesMCSLLDevice(name="mcs", register_io=register_io)

    mcs.reg_max_pixel.put(300)
    mcs.reg_max_line.put(300)
    mcs.reg_start_command.put(True)

    print(mcs.read_registers("max_pixel", "max_line", "start_command"))
    print(mcs.describe_register("max_time_bins_per_pixel"))


if __name__ == "__main__":
    main()
