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

The default converter S/N is `3C8427C3B50C` (used when no nonempty preference is
saved). **Auto-connect by S/N** finds and connects to the converter specified in
the S/N field in one click, restoring the default if that field is empty.
It requires a unique driver S/N match and does not connect on plugin startup.

The **Debug output** panel shows timestamped port discovery, converter S/N
matches, connection events, transmitted bytes (`TX`), received bytes (`RX`),
acknowledgments, and errors. Escaped line endings and partial serial replies
are visible. The log retains the latest 1000 lines; **Clear log** empties it.

**Reset serial link** cancels any outstanding command, finds the converter
again using its S/N (or the selected manual port), and closes/reopens the port.
After the startup wait, a newline terminates any partial command in the Arduino;
replies are drained for 300 ms before a fresh PING / READY and GET exchange.
This synchronization also runs on ordinary connections. Stale replies during
the PING handshake are logged and discarded within the normal reply timeout.
An interrupted SET is never replayed automatically. Reopening the port may
reset the Arduino and zero its outputs; confirmed values remain unknown until
GET succeeds. This resets the serial session, not the USB driver or converter.

Uses PySide6 QtSerialPort (no additional Python dependency), 9600 baud, 8N1,
no flow control, newline-terminated commands.
Arduino USB CDC connections explicitly assert DTR then RTS after opening the
port; otherwise a COM port may open successfully while the board sends no replies.
This follows the host connection signals used by the
[ESP32 USB CDC implementation](https://github.com/espressif/arduino-esp32/blob/master/cores/esp32/USBCDC.cpp).
Connection waits for possible
Arduino startup and verifies `PING` / `READY`, then sends `GET`, expecting
`VALS,code0,code1,code2,code3` before enabling output controls. All four returned
codes must be integers in 0..4095. GET reads all channels every 10 seconds while
idle and updates the confirmed values; it leaves requested voltage inputs as
entered. Polls are skipped while another command is awaiting a reply. GET errors or
timeouts disconnect the device and are shown in the debug log.
PING is used only during connection and serial-link reset. The initial PING
handshake retries up to three times; SET commands are never retried automatically.
Each voltage is rounded to the
nearest code using `voltage * 4095 / 5`, sent as `SET,ch,code`, and displayed as
acknowledged only after a matching `OK,ch,code`. Errors/timeouts close the
connection and invalidate displayed output state. Reconnect to retry explicitly.

The 5 V scale assumes a 5 V DAC supply/reference. GET reads DAC registers over
I2C; these codes and SET acknowledgments are not measured output voltages.
Opening a USB serial port can reset the Arduino; the supplied sketch zeros all
four channels at boot. Disconnecting the plugin sends no output commands.

## Firmware compatibility

The user's latest attached sketch already supports GET / VALS and needs no
protocol change for this plugin. The earlier Desktop sketch supports STATUS
but has no GET command. For that older version, upload
[`firmware/DAC_ino/DAC_ino.ino`](firmware/DAC_ino/DAC_ino.ino) using the Arduino
IDE before using this plugin version. This copy adds GET register reads for
all four DACs through the multiplexer and preserves PING, STATUS, and SET.
On an I2C read error it returns ERR,I2C instead of a partial snapshot.
Register decoding follows the MCP4725 read format in section 6.2 of the
[Microchip datasheet](https://ww1.microchip.com/downloads/aemDocuments/documents/MSLD/ProductDocuments/DataSheets/MCP4725-Data-Sheet-20002039E.pdf).

The bundled firmware extends the serial watchdog from 5 to 30 seconds.
The original Desktop file
is unchanged. Firmware compilation/upload and hardware readback must be
verified on the target board.
