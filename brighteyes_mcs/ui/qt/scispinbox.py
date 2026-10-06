"""Decimal editing and cursor-selected increments for microscope settings.

The public widget name is retained for Designer forms and plug-ins. Formatting
uses decimal scaling; stepping selects a displayed decimal place independently
of the widget's prefix and unit suffix.
"""

from decimal import Decimal, DecimalException, localcontext
import math
import re

from PySide6.QtCore import QEvent, Signal
from PySide6.QtGui import QPainter, QValidator
from PySide6.QtWidgets import QApplication, QDoubleSpinBox, QLineEdit

try:
    from .qt_locale import scientific_locale
except ImportError:  # Allow a standalone widget preview.
    from qt_locale import scientific_locale


_SI_BY_POWER = {
    -24: "y", -21: "z", -18: "a", -15: "f", -12: "p", -9: "n", -6: "u", -3: "m",
    3: "k", 6: "M", 9: "G", 12: "T", 15: "P", 18: "E", 21: "Z", 24: "Y",
}
ENGINEERING_EXPONENTS = {unit: power for power, unit in _SI_BY_POWER.items()}
_NUMBER = r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)"
_INPUT = re.compile(rf"({_NUMBER}(?:[eE][+-]?[0-9]+)?)([yzafpnumkMGTPEZY]?)")
_UNFINISHED_EXPONENT = re.compile(rf"{_NUMBER}[eE][+-]?")


def _normalize_decimal_separator(text, decimal_sep="."):
    compact = "".join(str(text).split())
    return compact.replace(decimal_sep or ".", ".").replace(",", ".")


def eng_string(x, format="%0.3f", format_exp=None, si=False, decimal_sep="."):
    """Format with an explicit sign and optional exponent in multiples of three.

    The two format parameters retain their percent-format interface.
    SI suffixes apply only when exponent formatting is requested.
    """
    number = Decimal(str(x))
    if not number.is_finite():
        raise ValueError("A finite number is required")
    magnitude = number.copy_abs()
    power = 0
    if magnitude and format_exp is not None:
        power = 3 * (magnitude.adjusted() // 3)
    with localcontext() as context:
        context.prec = max(28, len(number.as_tuple().digits))
        scaled = magnitude.scaleb(-power)
    unit = ""
    if power:
        unit = _SI_BY_POWER.get(power, "") if si else ""
        if not unit:
            unit = format_exp % power
    polarity = "-" if number < 0 else "+"
    return (polarity + (format % scaled) + unit).replace(".", decimal_sep)


def value_eng_string(value):
    """Parse decimal/scientific input with one optional SI suffix."""
    match = _INPUT.fullmatch(_normalize_decimal_separator(value))
    if match is None:
        raise ValueError("Expected a number with an optional SI suffix")
    digits, unit = match.groups()
    try:
        parsed = Decimal(digits).scaleb(ENGINEERING_EXPONENTS.get(unit, 0))
        result = float(parsed)
    except (DecimalException, OverflowError) as error:
        raise ValueError("Number is outside the supported range") from error
    if not math.isfinite(result):
        raise ValueError("A finite number is required")
    return result


class CharacterCursorLineEdit(QLineEdit):
    """Highlight the character at the insertion cursor while editing."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cursor_width = 2

    def characterCursorWidth(self):
        return self._cursor_width

    def setCharacterCursorWidth(self, width):
        self._cursor_width = max(2, int(width))
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.hasFocus() and not self.isReadOnly():
            area = self.cursorRect().adjusted(0, 1, 0, -1)
            area.setWidth(self._cursor_width)
            color = self.palette().highlight().color()
            painter = QPainter(self)
            painter.setPen(color)
            color.setAlpha(90)
            painter.fillRect(area, color)
            painter.drawRect(area.adjusted(0, 0, -1, -1))
            painter.end()


class sciSpinBox(QDoubleSpinBox):
    """Signed fixed-decimal display with SI input and digit-wise stepping."""

    sgn = Signal(float)  # Retained for existing Designer/plugin connections.

    def __init__(self, parent=None):
        self.decimal = 1
        super().__init__(parent)
        editor = CharacterCursorLineEdit(self)
        self.setLineEdit(editor)
        self.setLocale(scientific_locale())
        self.setRange(-1e99, 1e99)
        self.setDecimals(1)
        self.setSingleStep(1e-6)
        self.setKeyboardTracking(False)
        self.setObjectName("doubleSpinBox")
        self._resize_cursor()

    def _resize_cursor(self):
        self.lineEdit().setCharacterCursorWidth(self.fontMetrics().horizontalAdvance("0"))

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in {QEvent.Type.FontChange, QEvent.Type.ApplicationFontChange}:
            self._resize_cursor()

    def setDecimals(self, decimal):
        # Qt may call textFromValue while changing precision.
        self.decimal = min(323, max(0, int(decimal)))
        super().setDecimals(self.decimal)

    def _numeric_input(self, text):
        body = str(text).strip()
        for affix, at_start in ((self.prefix(), True), (self.suffix(), False)):
            if not affix:
                continue
            if at_start and body.startswith(affix):
                body = body[len(affix):]
            elif not at_start and body.endswith(affix):
                body = body[:-len(affix)]
        return _normalize_decimal_separator(body, self.locale().decimalPoint())

    def validate(self, string, pos):
        body = self._numeric_input(string)
        if body in {"", "+", "-", ".", "+.", "-."} or _UNFINISHED_EXPONENT.fullmatch(body):
            state = QValidator.Intermediate
        else:
            state = QValidator.Invalid
            try:
                candidate = value_eng_string(body)
                if self.minimum() <= candidate <= self.maximum():
                    state = QValidator.Acceptable
            except ValueError:
                pass
        return state, string, pos

    def valueFromText(self, text):
        try:
            return value_eng_string(self._numeric_input(text))
        except ValueError:
            return self.value()

    def textFromValue(self, value):
        # The display deliberately uses fixed decimals; SI suffixes are input only.
        return eng_string(value, format=f"%.{self.decimal}f",
                          decimal_sep=self.locale().decimalPoint())

    def fixup(self, text):
        return str(text).replace(",", ".").replace(".", self.locale().decimalPoint())

    def stepBy(self, steps):
        if not steps:
            return
        editor = self.lineEdit()
        # Commit pending typed input before selecting a place in the fixed display.
        cursor = editor.cursorPosition() - len(self.prefix())
        self.interpretText()
        display = self.textFromValue(self.value())
        point = display.find(self.locale().decimalPoint())
        if point == -1:
            point = len(display)
        digits = [index for index, char in enumerate(display) if char.isdigit()]
        # Prefer the digit just left of the cursor, then the next digit on the right.
        if cursor - 1 in digits:
            selected = cursor - 1
        else:
            selected = next((index for index in digits if index >= cursor), digits[-1])
        place = point - selected - (selected < point)
        with localcontext() as context:
            context.prec = 340
            increment = Decimal(int(steps)).scaleb(place)
            target = Decimal(str(self.value())) + increment
        self.setValue(float(min(Decimal(str(self.maximum())),
                                max(Decimal(str(self.minimum())), target))))
        updated = self.textFromValue(self.value())
        new_point = updated.find(self.locale().decimalPoint())
        if new_point == -1:
            new_point = len(updated)
        position = len(self.prefix()) + cursor + new_point - point
        editor.deselect()
        editor.setCursorPosition(max(len(self.prefix()),
                                     min(position, len(self.prefix()) + len(updated))))


if __name__ == "__main__":
    import sys

    application = QApplication(sys.argv)
    preview = sciSpinBox()
    preview.setDecimals(4)
    preview.setWindowTitle("BrightEyes-MCS numeric editor")
    preview.resize(350, 60)
    preview.show()
    sys.exit(application.exec())
