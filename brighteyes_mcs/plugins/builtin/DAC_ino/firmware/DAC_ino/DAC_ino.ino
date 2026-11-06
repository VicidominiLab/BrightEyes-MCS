#include <Wire.h>
#include <Adafruit_MCP4725.h>
#include <string.h>
#include <stdlib.h>

/*
  ============================================================
  PROJECT OVERVIEW
  ============================================================

  This sketch controls 4 independent DAC outputs by using:
    - 4x MCP4725 DAC
    - 1x I2C multiplexer (TCA9546A-compatible, address 0x70)

  The Arduino receives serial commands from LabVIEW and:
    - selects the requested DAC channel through the I2C multiplexer
    - writes the requested DAC value
    - sends a short machine-readable reply back over serial
    - gives visual feedback using the onboard RGB LED

  ------------------------------------------------------------
  SERIAL COMMANDS
  ------------------------------------------------------------

  Supported incoming commands:

    PING
      -> reply: READY

    STATUS
      -> reply: STATUS,IDLE

    GET
      -> read all four MCP4725 DAC registers (does not change outputs)
      -> reply: VALS,code0,code1,code2,code3
      -> codes are 0..4095; ERR,I2C on any failed channel read

    SET,ch,val
      -> ch  = channel number, allowed values: 0..3
      -> val = DAC code, allowed values: 0..4095
      -> reply on success: OK,ch,val
      -> reply on error:
           ERR,FMT   malformed command
           ERR,CH    invalid channel
           ERR,VAL   invalid DAC value
           ERR,I2C   I2C / multiplexer communication error

  Example valid commands:
    SET,0,0
    SET,1,1024
    SET,3,4095

  ------------------------------------------------------------
  SERIAL WATCHDOG (protocol protection only)
  ------------------------------------------------------------

  1. Link timeout:
     If no recognized command (PING / STATUS / GET / SET,...) arrives
     for commTimeoutMs, the serial receive state is reset:
       - any partial command is discarded
       - pending input bytes are flushed
       - optionally the serial port is restarted
         (SERIAL_RESTART_ON_TIMEOUT)

     The DAC outputs are NOT touched: they stay at the last good
     value. Nothing is sent over serial on timeout, so LabVIEW's
     command/reply sequence is not disturbed.

     The host should send GET periodically (e.g. every 10 s) when it
     has nothing else to send, so the timeout only fires when the
     host is really gone.

  2. Partial-line timeout:
     If a line is started but no character arrives within
     rxIdleTimeoutMs, the partial line is discarded, so stray bytes
     never corrupt the next command.

  ------------------------------------------------------------
  LED FEEDBACK
  ------------------------------------------------------------

  Idle:
    - steady BLUE

  Successful SET command:
    - GREEN blinks twice (non-blocking)

  Error:
    - RED blinks twice (non-blocking)

  Important:
    The LED logic below assumes the onboard RGB LED is ACTIVE LOW:
      LOW  = LED ON
      HIGH = LED OFF

  ============================================================
*/


// ============================================================
// SERIAL WATCHDOG CONFIGURATION
// ============================================================

// 1 = call Serial.end() / Serial.begin() on link timeout
// 0 = only flush and reset the receive buffer
//
// NOTE: on boards with native USB serial, Serial.end() may make the
// COM port briefly disappear on the PC and break LabVIEW's VISA
// session. If that happens, set this to 0.
#define SERIAL_RESTART_ON_TIMEOUT 1

// Max time without a recognized command before the serial reset (ms)
const unsigned long commTimeoutMs = 30000;

// Max gap between characters of the same line (ms)
const unsigned long rxIdleTimeoutMs = 200;

// Serial baud rate
const unsigned long serialBaud = 9600;


// ============================================================
// HARDWARE OBJECTS
// ============================================================

// Adafruit driver object for the MCP4725 DAC
Adafruit_MCP4725 dac;


// ============================================================
// HARDWARE ADDRESSES
// ============================================================

// I2C address of the multiplexer board (TCA9546A / compatible)
#define MUX_ADDR 0x70

// I2C address of the MCP4725 DAC
#define DAC_ADDR 0x62


// ============================================================
// SERIAL RECEIVE BUFFER
// ============================================================

// Maximum length of a received command line, including terminating '\0'
const byte numChars = 48;

// Buffer used to store the incoming serial command
char receivedChars[numChars];

// End-of-command marker
// LabVIEW should send '\n' at the end of every command
const char endMarker = '\n';

// Flag set true when a full command line has been received
bool newData = false;

// Write position in receivedChars
// (global so the watchdog can reset it)
byte rxIndex = 0;


// ============================================================
// SERIAL WATCHDOG STATE
// ============================================================

// Time of the last recognized command
unsigned long lastCommandTime = 0;

// Time of the last received character
unsigned long lastRxCharTime = 0;


// ============================================================
// LED STATE MACHINE
// ============================================================

/*
  ledState determines the current LED mode:

    LED_IDLE
      - steady blue

    LED_BLINK_SUCCESS
      - blink green twice

    LED_BLINK_ERROR
      - blink red twice

  Blinking is implemented with millis(), so the program does NOT pause.
*/
enum LedState {
  LED_IDLE,
  LED_BLINK_SUCCESS,
  LED_BLINK_ERROR
};

LedState ledState = LED_IDLE;

// Timestamp used by the non-blocking blink state machine
unsigned long ledTimer = 0;

// True when we are in the "LED ON" part of a blink
bool blinkOnPhase = false;

// Counts how many ON/OFF transitions have happened
// Two blinks correspond to:
//   ON -> OFF -> ON -> OFF
// which means 4 transitions
uint8_t blinkTransitions = 0;

// Blink timing (milliseconds)
const unsigned long blinkOnTime  = 250;
const unsigned long blinkOffTime = 250;


// ============================================================
// SETUP
// ============================================================

void setup(void) {
  // Configure onboard RGB LED pins and built-in LED pin
  pinMode(LED_RED, OUTPUT);
  pinMode(LED_GREEN, OUTPUT);
  pinMode(LED_BLUE, OUTPUT);
  pinMode(LED_BUILTIN, OUTPUT);

  // Keep built-in LED in a known state
  // Depending on the board, HIGH may mean OFF
  digitalWrite(LED_BUILTIN, HIGH);

  // Start in idle visual state
  showIdleLed();

  // Start I2C bus
  Wire.begin();

  // Start DAC communication
  dac.begin(DAC_ADDR);

  // For safety, reset all 4 DAC channels to zero at power-up
  resetChannels();

  // Start serial communication for LabVIEW
  Serial.begin(serialBaud);

  // Short delay after boot so the serial interface is stable
  delay(300);

  // Optional startup message:
  // useful if LabVIEW opens the port after board reset
  Serial.println("READY");

  // Start the watchdog timers from now
  lastCommandTime = millis();
  lastRxCharTime  = lastCommandTime;
}


// ============================================================
// MAIN LOOP
// ============================================================

void loop(void) {
  // Try to receive one full line from serial
  recvWithEndMarker();

  // If a complete command has been received, process it
  if (newData) {
    if (processCommand()) {
      // Recognized command -> the host is alive
      lastCommandTime = millis();
    }
    newData = false;
  }

  // Serial / protocol watchdog
  checkSerialWatchdog();

  // Keep the LED state machine running continuously
  updateLedState();
}


// ============================================================
// SERIAL RECEIVE FUNCTIONS
// ============================================================

/*
  recvWithEndMarker()

  Reads incoming serial data one character at a time until '\n' is found.

  When '\n' arrives:
    - terminate the received string with '\0'
    - trim optional '\r'
    - set newData = true

  This function is non-blocking:
    if no data is available, it immediately returns.
*/
void recvWithEndMarker() {
  char rc;

  while (Serial.available() > 0 && !newData) {
    rc = Serial.read();
    lastRxCharTime = millis();

    if (rc != endMarker) {
      receivedChars[rxIndex] = rc;
      rxIndex++;

      // Prevent buffer overflow:
      // if input is too long, keep last position reserved for '\0'
      if (rxIndex >= numChars) {
        rxIndex = numChars - 1;
      }
    } else {
      // End of command reached -> close the string
      receivedChars[rxIndex] = '\0';
      rxIndex = 0;

      // Remove '\r' if command came as "\r\n"
      trimTrailingCR(receivedChars);

      newData = true;
    }
  }
}


/*
  trimTrailingCR()

  Removes a trailing carriage return if present.

  This helps when the sender uses CR+LF line endings:
    "SET,1,2048\r\n"
*/
void trimTrailingCR(char *s) {
  int len = strlen(s);

  if (len > 0 && s[len - 1] == '\r') {
    s[len - 1] = '\0';
  }
}


// ============================================================
// SERIAL WATCHDOG
// ============================================================

/*
  checkSerialWatchdog()

  Called every loop iteration.

    1. Partial-line timeout:
       discard a started line if no character arrived recently.

    2. Link timeout:
       reset the serial receive state if no recognized command
       arrived for commTimeoutMs.

  DAC outputs and LED are never touched here.
  Unsigned subtraction keeps this correct across millis() rollover.
*/
void checkSerialWatchdog() {
  unsigned long now = millis();

  // 1. Stale partial line
  if (rxIndex > 0 && (now - lastRxCharTime >= rxIdleTimeoutMs)) {
    rxIndex = 0;
    receivedChars[0] = '\0';
  }

  // 2. No command for too long
  if (now - lastCommandTime >= commTimeoutMs) {
    resetSerialPort();

    // Restart the timer, so the reset repeats every commTimeoutMs
    // while the host stays silent (not on every loop)
    lastCommandTime = millis();
  }
}


/*
  resetSerialPort()

  Brings the serial receive side back to a clean state.
  No message is sent: LabVIEW would read it as the reply to its
  next command.
*/
void resetSerialPort() {
#if SERIAL_RESTART_ON_TIMEOUT
  Serial.end();
  delay(10);
  Serial.begin(serialBaud);
#endif

  // Discard any partial command
  rxIndex = 0;
  receivedChars[0] = '\0';
  newData = false;

  // Flush any bytes still waiting in the input buffer
  while (Serial.available() > 0) {
    Serial.read();
  }
}


// ============================================================
// COMMAND PARSER
// ============================================================

/*
  processCommand()

  Handles all supported commands:

    PING
    STATUS
    GET
    SET,ch,val

  Any unsupported format returns ERR,FMT

  Returns true if the line was a recognized command (PING, STATUS, GET,
  or anything starting with "SET,"), even if the SET arguments
  were invalid. Only recognized commands reset the watchdog, so
  line noise cannot keep the link "alive".
*/
bool processCommand() {
  // Handshake / presence check command
  if (strcmp(receivedChars, "PING") == 0) {
    Serial.println("READY");
    return true;
  }

  // Simple status query
  if (strcmp(receivedChars, "STATUS") == 0) {
    Serial.println("STATUS,IDLE");
    return true;
  }

  if (strcmp(receivedChars, "GET") == 0) {
    sendAllChannels();
    return true;
  }

  // All set-point commands must start with "SET,"
  if (strncmp(receivedChars, "SET,", 4) != 0) {
    sendError("FMT");
    triggerErrorBlink();
    return false;
  }

  // Parse the payload that follows "SET,"
  parseSetCommand(receivedChars + 4);
  return true;
}


/*
  parseSetCommand()

  Expects payload in the form:
    ch,val

  Example:
    "2,2048"

  Validation steps:
    1. check comma exists
    2. check both fields are integer strings
    3. check channel range 0..3
    4. check DAC value range 0..4095
    5. select the mux channel
    6. write DAC value

  Replies:
    OK,ch,val
    ERR,FMT
    ERR,CH
    ERR,VAL
    ERR,I2C
*/
void parseSetCommand(char *payload) {
  // Look for the comma separating channel and value
  char *comma1 = strchr(payload, ',');
  if (comma1 == NULL) {
    sendError("FMT");
    triggerErrorBlink();
    return;
  }

  // Split the payload in-place into two C strings:
  // payload    -> channel string
  // comma1 + 1 -> value string
  *comma1 = '\0';
  char *chStr  = payload;
  char *valStr = comma1 + 1;

  // Verify both fields contain only digits
  if (!isIntegerString(chStr) || !isIntegerString(valStr)) {
    sendError("FMT");
    triggerErrorBlink();
    return;
  }

  // Convert ASCII strings to integers
  int channel = atoi(chStr);
  int value   = atoi(valStr);

  // Check channel bounds
  if (channel < 0 || channel > 3) {
    sendError("CH");
    triggerErrorBlink();
    return;
  }

  // Check DAC value bounds
  if (value < 0 || value > 4095) {
    sendError("VAL");
    triggerErrorBlink();
    return;
  }

  // Select the appropriate DAC path through the multiplexer
  if (!selectChannel(channel)) {
    sendError("I2C");
    triggerErrorBlink();
    return;
  }

  // Write value to DAC
  // false = fast mode, do not write to EEPROM each time
  dac.setVoltage(value, false);

  // Send positive acknowledgment to LabVIEW
  Serial.print("OK,");
  Serial.print(channel);
  Serial.print(",");
  Serial.println(value);

  // Blink green twice without pausing the program
  triggerSuccessBlink();
}


// ============================================================
// INPUT VALIDATION
// ============================================================

/*
  isIntegerString()

  Returns true only if the string is non-empty and contains digits only.

  Valid:
    "0"
    "123"
    "4095"

  Invalid:
    ""
    "-1"
    "12.3"
    "abc"
*/
bool isIntegerString(const char *s) {
  if (*s == '\0') return false;

  while (*s) {
    if (*s < '0' || *s > '9') return false;
    s++;
  }

  return true;
}


/*
  sendError()

  Sends a compact machine-readable error reply.

  Example:
    sendError("CH")  -> ERR,CH
*/
// Read all channels before emitting a reply, so an I2C error never produces
// a partial GET line. MCP4725 datasheet, section 6.2 / Figure 6-3:
// first received byte = status; next two bytes = DAC code, left-aligned.
void sendAllChannels() {
  uint16_t codes[4];
  for (uint8_t channel = 0; channel < 4; channel++) {
    if (!selectChannel(channel)) {
      sendError("I2C");
      triggerErrorBlink();
      return;
    }
    if (Wire.requestFrom((uint8_t)DAC_ADDR, (uint8_t)3) != 3) {
      while (Wire.available() > 0) Wire.read();
      sendError("I2C");
      triggerErrorBlink();
      return;
    }
    Wire.read();  // EEPROM ready and power-down status
    uint8_t highByte = Wire.read();
    uint8_t lowByte = Wire.read();
    codes[channel] = ((uint16_t)highByte << 4) | (lowByte >> 4);
  }
  Serial.print("VALS");
  for (uint8_t channel = 0; channel < 4; channel++) {
    Serial.print(',');
    Serial.print(codes[channel]);
  }
  Serial.println();
}

void sendError(const char *code) {
  Serial.print("ERR,");
  Serial.println(code);
}


// ============================================================
// DAC / MULTIPLEXER FUNCTIONS
// ============================================================

/*
  resetChannels()

  On startup, forces all 4 mux channels to DAC value 0.

  This is a safety measure so the outputs begin in a known state.
*/
void resetChannels() {
  for (int i = 0; i < 4; i++) {
    if (selectChannel(i)) {
      dac.setVoltage(0, true);
    }
  }
}


/*
  selectChannel()

  Selects one channel on the I2C multiplexer.

  The multiplexer is controlled by writing a bit mask:
    channel 0 -> 0001
    channel 1 -> 0010
    channel 2 -> 0100
    channel 3 -> 1000

  Returns:
    true  if I2C transmission succeeded
    false if I2C transmission failed
*/
bool selectChannel(uint8_t channel) {
  Wire.beginTransmission(MUX_ADDR);
  Wire.write(1 << channel);

  uint8_t err = Wire.endTransmission();

  return (err == 0);
}


// ============================================================
// LED LOW-LEVEL CONTROL
// ============================================================

/*
  These helper functions control the onboard RGB LED.

  IMPORTANT:
  This code assumes ACTIVE LOW logic:
    LOW  -> LED ON
    HIGH -> LED OFF
*/

/*
  setLedOff()

  Turns off all RGB channels.
*/
void setLedOff() {
  digitalWrite(LED_RED, HIGH);
  digitalWrite(LED_GREEN, HIGH);
  digitalWrite(LED_BLUE, HIGH);
}


/*
  setLedColor(redOn, greenOn, blueOn)

  Example:
    setLedColor(false, false, true)  -> blue
    setLedColor(false, true, false)  -> green
    setLedColor(true, false, false)  -> red
*/
void setLedColor(bool redOn, bool greenOn, bool blueOn) {
  digitalWrite(LED_RED,   redOn   ? LOW : HIGH);
  digitalWrite(LED_GREEN, greenOn ? LOW : HIGH);
  digitalWrite(LED_BLUE,  blueOn  ? LOW : HIGH);
}


/*
  showIdleLed()

  Returns the LED to the normal idle state:
    steady blue
*/
void showIdleLed() {
  ledState = LED_IDLE;
  setLedColor(false, false, true);
}


/*
  triggerSuccessBlink()

  Starts the non-blocking "green blink twice" sequence.
*/
void triggerSuccessBlink() {
  ledState = LED_BLINK_SUCCESS;
  blinkOnPhase = true;
  blinkTransitions = 0;
  ledTimer = millis();

  // Start immediately with LED on
  setLedColor(false, true, false);
}


/*
  triggerErrorBlink()

  Starts the non-blocking "red blink twice" sequence.
*/
void triggerErrorBlink() {
  ledState = LED_BLINK_ERROR;
  blinkOnPhase = true;
  blinkTransitions = 0;
  ledTimer = millis();

  // Start immediately with LED on
  setLedColor(true, false, false);
}


// ============================================================
// LED STATE MACHINE
// ============================================================

/*
  updateLedState()

  Handles blink timing without using delay().

  This is called every loop iteration.

  For success and error:
    - LED turns on
    - waits blinkOnTime
    - turns off
    - waits blinkOffTime
    - repeats until 2 blinks are completed
    - returns to steady blue idle
*/
void updateLedState() {
  unsigned long now = millis();

  switch (ledState) {
    case LED_IDLE:
      // In idle mode the LED remains steady blue.
      // Nothing to update here.
      break;

    case LED_BLINK_SUCCESS:
    case LED_BLINK_ERROR:
      if (blinkOnPhase) {
        // We are currently in the ON part of the blink
        if (now - ledTimer >= blinkOnTime) {
          blinkOnPhase = false;
          ledTimer = now;
          setLedOff();
          blinkTransitions++;
        }
      } else {
        // We are currently in the OFF part of the blink
        if (now - ledTimer >= blinkOffTime) {
          // After 4 transitions we completed two blinks:
          // ON->OFF->ON->OFF
          if (blinkTransitions >= 4) {
            showIdleLed();
          } else {
            blinkOnPhase = true;
            ledTimer = now;

            if (ledState == LED_BLINK_SUCCESS) {
              setLedColor(false, true, false);  // green
            } else {
              setLedColor(true, false, false);  // red
            }

            blinkTransitions++;
          }
        }
      }
      break;
  }
}
