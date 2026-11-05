# DAC_ino

Load `DAC_ino` from the BrightEyes-MCS plug-in selector. Select the USB-to-TTL
converter's serial port and press **Connect**, then enter 0–5 V and press **Set**
for each of DAC 0–3. No output commands are sent automatically on connection.

The port list displays the converter serial number reported by the USB driver.
Enter that value in **Converter S/N** to select its port automatically, including
after a COM number change. This preference is remembered locally. Matching is
exact and requires a unique match; no Arduino firmware serial number is used.
If the converter/driver does not expose a serial number, leave S/N empty and
select the port manually. Refresh after attaching a converter.

Uses PySide6 QtSerialPort (no additional Python dependency), 9600 baud, 8N1,
no flow control, newline-terminated commands. Connection waits for possible
Arduino startup and verifies `PING` / `READY`. Each voltage is rounded to the
nearest code using `voltage * 4095 / 5`, sent as `SET,ch,code`, and displayed as
acknowledged only after a matching `OK,ch,code`. Errors/timeouts close the
connection and invalidate displayed output state. Reconnect to retry explicitly.

The 5 V scale assumes a 5 V DAC supply/reference. Acknowledgments are not voltage
measurements: the supplied firmware cannot read back DAC codes or voltages.
Opening a USB serial port can reset the Arduino; the supplied sketch zeros all
four channels at boot. Disconnecting the plugin sends no output commands.
