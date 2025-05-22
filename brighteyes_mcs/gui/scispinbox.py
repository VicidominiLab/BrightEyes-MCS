'''
Author: Luca Bega. Istituto Italiano di Tecnologia
'''

import sys
from PySide6.QtCore import QRegularExpression, Signal, QRect, Qt, QMetaObject, QCoreApplication
from PySide6.QtGui import QRegularExpressionValidator, QValidator
from PySide6.QtWidgets import (QDoubleSpinBox, QWidget, QMainWindow,
                              QMenuBar, QStatusBar, QApplication)


import math
from decimal import *


def eng_string(x, format="%0.3f", format_exp=None, si=False, decimal_sep="."):
    sign = "+"

    if x == 0:
        return ("%s" + format) % (sign, x)

    if x < 0:
        x = -x
        sign = "-"

    if format_exp != None:
        exp = int(math.floor(math.log10(x)))
        exp3 = exp - (exp % 3)
        x3 = x / (10**exp3)
        if si and -24 <= exp3 <= 24 and exp3 != 0:
            exp3_text = "yzafpnum kMGTPEZY"[(exp3 - (-24)) // 3]
        elif exp3 == 0:
            exp3_text = ""
        else:
            exp3_text = format_exp % exp3

        if decimal_sep == ".":
            return ("%s" + format + "%s") % (sign, x3, exp3_text)
        else:
            return (("%s" + format + "%s") % (sign, x3, exp3_text)).replace(
                ".", decimal_sep
            )

    if decimal_sep == ".":
        return ("%s" + format) % (sign, x)
    else:
        return (("%s" + format) % (sign, x)).replace(".", decimal_sep)


def value_eng_string(value):
    # delete whitespace to avoid mistakes
    oldvalue = value
    value = value.replace(" ", "")
    # search for "." or ",", add ".0" if it's not present and replace "," with "." if necessary
    if (value.find(",") == -1) and (value.find(".") == -1):
        if "yzafpnum kMGTPEZY".find(value[-1]) != -1:
            value = value[:-1] + ".0" + value[-1:]
        else:
            value = value + ".0"
    value = value.replace(",", ".")

    # check for the exponent
    tmp_find = "yzafpnum kMGTPEZY".find(value[-1])
    # case number without exponent
    if tmp_find == -1:
        result = float(value)
        return result
    else:
        result = float(value[:-1] + "e%d" % (tmp_find * 3 - 24))
        return result


class sciSpinBox(QDoubleSpinBox):
    sgn = Signal(float)

    def __init__(self, QDoubleSpinBox):
        self.decimal = 1
        super().__init__(QDoubleSpinBox)
        self.validator = QRegularExpressionValidator(
            QRegularExpression(r"\s*$[[\-\+]\d{1,9}a-zA-Z+-^,.]"), self
        )
        super().setDecimals(300)
        self.setMaximum(1e99)
        self.setMinimum(-1e99)
        self.setSingleStep(1e-6)
        self.setValue(12.3)
        self.setObjectName("doubleSpinBox")
        self.setGeometry(QRect(125, 90, 122, 22))
        # If keyboard tracking is disabled, the spinbox doesn’t emit the valueChanged() signal while typing.
        # It emits the signal later, when the return key is pressed
        self.setKeyboardTracking(False)

    def setDecimals(self, decimal):
        self.decimal = decimal
        # super().setDecimals(decimal)

    def validate(self, string, pos):
        try:
            # check if sign is present in the string
            if len(string) > 0:
                if not (("+" or "-") in string):
                    value = string[0:]
                else:
                    value = string[1:]

                if string[-1].isalpha():
                    value = value[0 : len(value) - 1]
                    valid = QValidator.Acceptable
                else:
                    valid = QValidator.Acceptable
            else:
                valid = QValidator.Intermediate
        # ERROR CHECK
        except Exception as E:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            valid = QValidator.Invalid
            print(repr(E), E.__traceback__)
            print(exc_type, exc_tb.tb_lineno)
        return valid, pos

    def valueFromText(self, text: str) -> float:
        return value_eng_string(text)

    def textFromValue(self, value):
        return eng_string(value)

    def stepBy(self, steps):
        cursor_position = self.lineEdit().cursorPosition()
        # number of characters before the decimal separator including +/- sign
        value = self.value()
        str_value = self.textFromValue(value)
        n_chars_before_sep = str_value.find(".")
        # set the cursor right of the +/- sign
        if cursor_position <= 1:
            if steps < 0:
                self.lineEdit().setCursorPosition(2)
                cursor_position = self.lineEdit().cursorPosition()
            else:
                self.lineEdit().setCursorPosition(1)
                cursor_position = self.lineEdit().cursorPosition()

        single_step = (10 ** (n_chars_before_sep - cursor_position)) * steps

        # Handle decimal separator. Step should be 0.1 if cursor is at `1.|23` or
        # `1.2|3`.
        if cursor_position >= n_chars_before_sep + 2:
            single_step = 10 * single_step

        if str_value[-1].isalpha():
            tmp_value = str(Decimal(str_value[:-1]) + Decimal(single_step))
            value = self.valueFromText(tmp_value + str_value[-1])
        elif "e" in str_value:
            exponent = str_value.find("e")
            tmp_value = str(Decimal(str_value[:exponent]) + Decimal(single_step))
            value = self.valueFromText(tmp_value + str_value[exponent:])
        else:
            value = value + single_step

        str_value_postop = self.textFromValue(value)
        dotPosPostOp = str_value_postop.find(".")
        print("pre:", n_chars_before_sep)
        print("post:", dotPosPostOp)

        if dotPosPostOp > n_chars_before_sep:
            cursor_position = cursor_position + 1
        elif dotPosPostOp < n_chars_before_sep:
            cursor_position = cursor_position - 1

        self.setValue(value)
        self.validate(str(self.value()), cursor_position)

        # self.sgn.emit(value)

        # Undo selection of the whole text.
        self.lineEdit().deselect()

        # Handle cases where the number of characters before the decimal separator
        # changes. Step size should remain the same.
        new_n_chars_before_sep = str_value.find(".")
        if new_n_chars_before_sep < n_chars_before_sep:
            cursor_position -= 1
        elif new_n_chars_before_sep > n_chars_before_sep:
            cursor_position += 1

        self.lineEdit().cursorPosition()

        self.lineEdit().setCursorPosition(cursor_position)


#
# @Slot()
# def valueChanged(p):
#     print(p)
def fff(prova):
    # print(prova)
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

    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(
            QCoreApplication.translate("MainWindow", "MainWindow", None)
        )

    # retranslateUi
