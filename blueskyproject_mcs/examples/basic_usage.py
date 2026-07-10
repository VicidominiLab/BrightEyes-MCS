"""Small simulated usage example for the BrightEyes Bluesky device."""

from brighteyes_bluesky import BrightEyesMCSLLDevice, MappingRegisterIO


def main() -> None:
    register_io = MappingRegisterIO({"#pixels": 512, "#lines": 512, "Run": False})
    mcs = BrightEyesMCSLLDevice(name="mcs", register_io=register_io)

    mcs.reg_number_pixels.put(300)
    mcs.reg_number_lines.put(300)
    mcs.reg_run.put(True)

    print(mcs.read_registers("#pixels", "#lines", "Run"))
    print(mcs.describe_register("#timebinsPerPixel"))


if __name__ == "__main__":
    main()
