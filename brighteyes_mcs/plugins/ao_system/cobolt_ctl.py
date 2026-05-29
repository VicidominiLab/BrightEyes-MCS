import serial
from brighteyes_mcs.libs.print_debug import print_debug


def turn_on_laser(com, power):
    s = serial.Serial(port=com, baudrate=115200, timeout=1.0)
    s.write(bytes("gsn?\r\n", "ascii"))
    sn = s.read(1024)
    print_debug("Laser S/N", sn)
    s.write(bytes("ilk?\r\n", "ascii"))
    interlock = s.read(1024)
    print_debug("Laser interlock", interlock)
    s.write(bytes("cp\r\n", "ascii"))
    s.write(bytes("p %f\r\n" % power, "ascii"))
    s.write(bytes("l1\r\n", "ascii"))
    s.write(bytes("p?\r\n", "ascii"))
    actual_power = s.read(1024)
    print_debug("Laser actual_power", actual_power)


def turn_off_laser():
    s = serial.Serial(com=com, baudrate=115200, timeout=1.0)
    s.write(bytes("gsn?\r\n", "ascii"))
    sn = s.read(1024)
    print_debug("Laser S/N", sn)
    s.write(bytes("l0\r\n", "ascii"))
    print_debug("Laser off")

