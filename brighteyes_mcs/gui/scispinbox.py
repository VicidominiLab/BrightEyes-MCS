"""Scientific/engineering QDoubleSpinBox with project-wide decimal policy."""

import math
import re

from PySide6.QtCore import Signal, QRect, QMetaObject, QCoreApplication, QEvent
from PySide6.QtGui import QPainter, QValidator
from PySide6.QtWidgets import (
    QApplication,
    QDoubleSpinBox,
    QLineEdit,
    QMainWindow,
    QMenuBar,
    QStatusBar,
    QWidget,
)

try:
    from .qt_locale import scientific_locale
except ImportError:  # pragma: no cover - supports running this module directly.
    from qt_locale import scientific_locale


ENGINEERING_SUFFIXES = "yzafpnum kMGTPEZY"
ENGINEERING_EXPONENTS = {
    suffix: index * 3 - 24
    for index, suffix in enumerate(ENGINEERING_SUFFIXES)
    if suffix != " "
}


def _normalize_decimal_separator(text, decimal_sep="."):
    text = str(text).strip().replace(" ", "")
    if decimal_sep and decimal_sep != ".":
        text = text.replace(decimal_sep, ".")
    return text.replace(",", ".")


def eng_string(x, format="%0.3f", format_exp=None, si=False, decimal_sep="."):
    sign = "+"

    if x == 0:
        result = ("%s" + format) % (sign, x)
        return result if decimal_sep == "." else result.replace(".", decimal_sep)

    if x < 0:
        x = -x
        sign = "-"

    if format_exp is not None:
        exp = int(math.floor(math.log10(x)))
        exp3 = exp - (exp % 3)
        x3 = x / (10**exp3)
        if si and -24 <= exp3 <= 24 and exp3 != 0:
            exp3_text = ENGINEERING_SUFFIXES[(exp3 - (-24)) // 3]
        elif exp3 == 0:
            exp3_text = ""
        else:
            exp3_text = format_exp % exp3

        result = ("%s" + format + "%s") % (sign, x3, exp3_text)
        return result if decimal_sep == "." else result.replace(".", decimal_sep)

    result = ("%s" + format) % (sign, x)
    return result if decimal_sep == "." else result.replace(".", decimal_sep)


def value_eng_string(value):
    value = _normalize_decimal_separator(value)
    if value == "":
        raise ValueError("empty value")

    suffix = value[-1]
    if suffix in ENGINEERING_EXPONENTS:
        mantissa = value[:-1]
        if mantissa in ("", "+", "-"):
            raise ValueError("missing mantissa")
        return float(mantissa) * (10 ** ENGINEERING_EXPONENTS[suffix])

    return float(value)


class CharacterCursorLineEdit(QLineEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._character_cursor_width = 2

    def setCharacterCursorWidth(self, width):
        self._character_cursor_width = max(2, int(width))
        self.update()

    def characterCursorWidth(self):
        return self._character_cursor_width

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.hasFocus() or self.isReadOnly():
            return

        cursor_rect = self.cursorRect()
        cursor_rect.setWidth(self._character_cursor_width)
        cursor_rect.setHeight(max(1, cursor_rect.height() - 2))
        cursor_rect.moveTop(cursor_rect.top() + 1)

        painter = QPainter(self)
        fill = self.palette().highlight().color()
        fill.setAlpha(90)
        painter.fillRect(cursor_rect, fill)
        painter.setPen(self.palette().highlight().color())
        painter.drawRect(cursor_rect.adjusted(0, 0, -1, -1))


class sciSpinBox(QDoubleSpinBox):
    sgn = Signal(float)

    def __init__(self, parent=None):
        self.decimal = 1
        super().__init__(parent)
        self.setLineEdit(CharacterCursorLineEdit(self))
        self.setLocale(scientific_locale())
        super().setDecimals(self.decimal)
        self.setMaximum(1e99)
        self.setMinimum(-1e99)
        self.setSingleStep(1e-6)
        self.setValue(12.3)
        self.setObjectName("doubleSpinBox")
        self.setGeometry(QRect(125, 90, 122, 22))
        # With keyboard tracking disabled, valueChanged() is emitted on commit.
        self.setKeyboardTracking(False)
        self._set_character_cursor_width()

    def _set_character_cursor_width(self):
        cursor_width = max(2, self.fontMetrics().horizontalAdvance("0"))
        self.lineEdit().setCharacterCursorWidth(cursor_width)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (
            QEvent.Type.FontChange,
            QEvent.Type.ApplicationFontChange,
        ):
            self._set_character_cursor_width()

    def setDecimals(self, decimal):
        self.decimal = int(decimal)
        super().setDecimals(self.decimal)

    def _decimal_separator(self):
        return self.locale().decimalPoint()

    def _strip_affixes(self, text):
        text = str(text).strip()
        prefix = self.prefix()
        suffix = self.suffix()
        if prefix and text.startswith(prefix):
            text = text[len(prefix):]
        if suffix and text.endswith(suffix):
            text = text[: -len(suffix)]
        return text.strip()

    def _normalized_text(self, text):
        return _normalize_decimal_separator(
            self._strip_affixes(text),
            decimal_sep=self._decimal_separator(),
        )

    def _is_partial_number(self, text):
        text = self._normalized_text(text)
        if text in ("", "+", "-", ".", "+.", "-."):
            return True
        return re.fullmatch(r"[+-]?(\d+(\.\d*)?|\.\d+)[eE][+-]?", text) is not None

    def validate(self, string, pos):
        if self._is_partial_number(string):
            return QValidator.Intermediate, string, pos

        try:
            value = value_eng_string(self._normalized_text(string))
        except ValueError:
            return QValidator.Invalid, string, pos

        if self.minimum() <= value <= self.maximum():
            return QValidator.Acceptable, string, pos
        return QValidator.Invalid, string, pos

    def valueFromText(self, text):
        try:
            return value_eng_string(self._normalized_text(text))
        except ValueError:
            return self.value()

    def textFromValue(self, value):
        return eng_string(
            value,
            format="%%0.%df" % self.decimal,
            decimal_sep=self._decimal_separator(),
        )

    def fixup(self, text):
        decimal_sep = self._decimal_separator()
        if decimal_sep == ".":
            return str(text).replace(",", ".")
        return str(text).replace(".", decimal_sep)

    def _step_exponent_at_cursor(self, text, cursor_position):
        decimal_pos = text.find(self._decimal_separator())
        if decimal_pos < 0:
            decimal_pos = len(text)

        active_index = None
        if (
            cursor_position > 0
            and cursor_position <= len(text)
            and text[cursor_position - 1].isdigit()
        ):
            active_index = cursor_position - 1
        elif cursor_position < len(text) and text[cursor_position].isdigit():
            active_index = cursor_position
        else:
            for index in range(cursor_position + 1, len(text)):
                if text[index].isdigit():
                    active_index = index
                    break
            if active_index is None:
                for index in range(cursor_position - 1, -1, -1):
                    if text[index].isdigit():
                        active_index = index
                        break

        if active_index is None:
            return 0

        if active_index < decimal_pos:
            return decimal_pos - active_index - 1
        return decimal_pos - active_index

    def stepBy(self, steps):
        cursor_position = self.lineEdit().cursorPosition()
        value = self.value()
        str_value = self.textFromValue(value)
        decimal_pos = str_value.find(self._decimal_separator())
        if decimal_pos < 0:
            decimal_pos = len(str_value)

        exponent = self._step_exponent_at_cursor(str_value, cursor_position)

        value = value + (10**exponent) * steps
        value = min(max(value, self.minimum()), self.maximum())
        self.setValue(value)

        self.lineEdit().deselect()

        new_decimal_pos = self.textFromValue(self.value()).find(self._decimal_separator())
        if new_decimal_pos >= 0:
            cursor_position += new_decimal_pos - decimal_pos
        cursor_position = max(0, min(cursor_position, len(self.text())))
        self.lineEdit().setCursorPosition(cursor_position)


def fff(prova):
    return


class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName("MainWindow")
        MainWindow.resize(350, 200)
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        self.doubleSpinBox = sciSpinBox(self.centralwidget)
        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QMenuBar(MainWindow)
        self.menubar.setObjectName("menubar")
        self.menubar.setGeometry(QRect(0, 0, 800, 21))
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QStatusBar(MainWindow)
        self.statusbar.setObjectName("statusbar")
        MainWindow.setStatusBar(self.statusbar)

        self.doubleSpinBox.valueChanged.connect(fff)
        self.doubleSpinBox.setDecimals(4)

        self.retranslateUi(MainWindow)

        QMetaObject.connectSlotsByName(MainWindow)

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(
            QCoreApplication.translate("MainWindow", "MainWindow", None)
        )


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    window = QMainWindow()
    ui = Ui_MainWindow()
    ui.setupUi(window)
    window.show()
    sys.exit(app.exec())
