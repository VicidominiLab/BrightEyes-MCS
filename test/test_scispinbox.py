import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(1, os.getcwd())

from PySide6.QtGui import QValidator
from PySide6.QtCore import Qt, QLocale
from PySide6.QtTest import QTest, QSignalSpy
from PySide6.QtWidgets import QApplication, QDoubleSpinBox

from brighteyes_mcs.ui.qt.scispinbox import eng_string, sciSpinBox, value_eng_string
from brighteyes_mcs.ui.qt.qt_locale import install_scientific_locale


class TestSciSpinBox(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        install_scientific_locale()
        cls.app = QApplication.instance() or QApplication([])

    def test_eng_string_and_value_eng_string_support_common_formats(self):
        self.assertEqual(eng_string(123456, format_exp="e%d", si=True), "+123.456k")
        self.assertAlmostEqual(value_eng_string("1e3"), 1000.0)
        self.assertAlmostEqual(value_eng_string(" 1,5 k "), 1500.0)
        self.assertAlmostEqual(value_eng_string("1.2m"), 0.0012)

    def test_set_decimals_controls_display_and_api(self):
        box = sciSpinBox()
        box.setDecimals(4)
        box.setValue(200.0)

        self.assertEqual(box.decimals(), 4)
        self.assertEqual(box.decimal, 4)
        self.assertEqual(box.text(), "+200.0000")

    def test_validate_supports_partial_engineering_and_scientific_inputs(self):
        box = sciSpinBox()

        self.assertEqual(box.validate("", 0)[0], QValidator.Intermediate)
        self.assertEqual(box.validate("+", 1)[0], QValidator.Intermediate)
        self.assertEqual(box.validate("1.2", 3)[0], QValidator.Acceptable)
        self.assertEqual(box.validate("1e-3", 4)[0], QValidator.Acceptable)
        self.assertEqual(box.validate("1k", 2)[0], QValidator.Acceptable)
        self.assertEqual(box.validate("abc", 3)[0], QValidator.Invalid)

    def test_validate_returns_qt_compatible_tuple(self):
        box = sciSpinBox()

        state, text, pos = box.validate("1.2", 3)

        self.assertEqual(state, QValidator.Acceptable)
        self.assertEqual(text, "1.2")
        self.assertEqual(pos, 3)

    def test_validate_rejects_values_outside_range(self):
        box = sciSpinBox()
        box.setRange(-10.0, 10.0)

        self.assertEqual(box.validate("10", 2)[0], QValidator.Acceptable)
        self.assertEqual(box.validate("11", 2)[0], QValidator.Invalid)
        self.assertEqual(box.validate("-11", 3)[0], QValidator.Invalid)

    def test_value_from_text_falls_back_to_current_value_for_invalid_input(self):
        box = sciSpinBox()
        box.setValue(12.5)

        self.assertEqual(box.valueFromText("not-a-number"), 12.5)

    def test_step_by_tracks_integer_digit_at_cursor(self):
        box = sciSpinBox()
        box.setDecimals(3)
        box.setValue(200.0)
        box.lineEdit().setCursorPosition(1)

        box.stepBy(1)

        self.assertEqual(box.value(), 300.0)
        self.assertEqual(box.text(), "+300.000")

    def test_step_by_tracks_fractional_digit_at_cursor(self):
        box = sciSpinBox()
        box.setDecimals(3)
        box.setValue(12.345)
        box.lineEdit().setCursorPosition(box.text().find(".") + 1)

        box.stepBy(1)

        self.assertAlmostEqual(box.value(), 12.445, places=9)
        self.assertEqual(box.text(), "+12.445")

    def test_step_by_tracks_integer_digit_before_decimal_separator(self):
        box = sciSpinBox()
        box.setDecimals(3)
        box.setValue(12.345)
        box.lineEdit().setCursorPosition(box.text().find("."))

        box.stepBy(1)

        self.assertAlmostEqual(box.value(), 13.345, places=9)
        self.assertEqual(box.text(), "+13.345")

    def test_step_by_tracks_each_integer_digit_at_cursor(self):
        box = sciSpinBox()
        box.setDecimals(3)
        box.setValue(12.345)
        box.lineEdit().setCursorPosition(1)
        box.stepBy(1)
        self.assertAlmostEqual(box.value(), 22.345, places=9)

        box.setValue(12.345)
        box.lineEdit().setCursorPosition(2)
        box.stepBy(1)
        self.assertAlmostEqual(box.value(), 22.345, places=9)

        box.setValue(12.345)
        box.lineEdit().setCursorPosition(3)
        box.stepBy(1)
        self.assertAlmostEqual(box.value(), 13.345, places=9)

    def test_value_parsing_and_step_by_keep_suffix_compatibility(self):
        box = sciSpinBox()
        box.setSuffix(" ns")
        box.setDecimals(2)
        box.setValue(1.25)

        self.assertEqual(box.valueFromText("+1.25 ns"), 1.25)

        box.lineEdit().setCursorPosition(box.text().find(".") + 1)
        box.stepBy(1)

        self.assertAlmostEqual(box.value(), 1.35, places=9)
        self.assertEqual(box.text(), "+1.35 ns")

    def test_sci_spinbox_accepts_numpad_comma_but_formats_project_separator(self):
        box = sciSpinBox()
        box.setDecimals(2)

        self.assertEqual(box.validate("1,25", 4)[0], QValidator.Acceptable)
        self.assertAlmostEqual(box.valueFromText("1,25"), 1.25)
        self.assertEqual(box.fixup("1,25"), "1.25")

        box.setValue(box.valueFromText("1,25"))
        self.assertEqual(box.text(), "+1.25")

    def test_project_locale_formats_qdouble_spinbox_with_dot(self):
        box = QDoubleSpinBox()
        box.setDecimals(2)
        box.setValue(1.5)

        self.assertEqual(box.locale().decimalPoint(), ".")
        self.assertEqual(box.text(), "1.50")

    def test_sci_spinbox_uses_character_width_cursor(self):
        box = sciSpinBox()

        self.assertEqual(
            box.lineEdit().characterCursorWidth(),
            max(2, box.fontMetrics().horizontalAdvance("0")),
        )

    def test_formatting_signs_precision_and_engineering_boundaries(self):
        cases = [
            (0, {}, "+0.000"),
            (-12.5, {"format": "%.2f"}, "-12.50"),
            (1.25, {"decimal_sep": ","}, "+1,250"),
            (1e-6, {"format_exp": "e%d", "si": True}, "+1.000u"),
            (1e24, {"format_exp": "e%d", "si": True}, "+1.000Y"),
            (1e27, {"format_exp": "e%d", "si": True}, "+1.000e27"),
            (0.125, {"format_exp": "e%d"}, "+125.000e-3"),
            (1000, {"si": True}, "+1000.000"),
        ]
        for value, options, expected in cases:
            with self.subTest(value=value, options=options):
                self.assertEqual(eng_string(value, **options), expected)

    def test_smallest_float_and_all_si_prefixes(self):
        self.assertEqual(eng_string(5e-324, format_exp="e%d"), "+5.000e-324")
        for suffix, exponent in [("y", -24), ("z", -21), ("a", -18), ("f", -15),
                                 ("p", -12), ("n", -9), ("u", -6), ("m", -3),
                                 ("k", 3), ("M", 6), ("G", 9), ("T", 12),
                                 ("P", 15), ("E", 18), ("Z", 21), ("Y", 24)]:
            with self.subTest(suffix=suffix):
                self.assertEqual(value_eng_string("2" + suffix), 2 * 10.0**exponent)

    def test_prefix_cursor_and_carry_preserve_selected_place(self):
        box = sciSpinBox()
        box.setDecimals(2)
        box.setPrefix("Voltage: ")
        box.setSuffix(" V")
        box.setValue(9.95)
        box.lineEdit().setCursorPosition(box.text().find(".") + 1)
        box.stepBy(1)
        self.assertEqual(box.text(), "Voltage: +10.05 V")
        self.assertEqual(box.lineEdit().cursorPosition(), box.text().find(".") + 1)
        box.stepBy(-1)
        self.assertEqual(box.text(), "Voltage: +9.95 V")

    def test_negative_steps_limits_and_zero_decimal_display(self):
        box = sciSpinBox()
        box.setDecimals(0)
        box.setRange(-20, 20)
        box.setValue(-19)
        box.lineEdit().setCursorPosition(len(box.text()))
        box.stepBy(-5)
        self.assertEqual(box.value(), -20)
        box.stepBy(1)
        self.assertEqual(box.value(), -19)

    def test_nonfinite_values_are_not_accepted(self):
        box = sciSpinBox()
        for text in ("nan", "inf", "-inf", "1e999", "1kk"):
            with self.subTest(text=text):
                self.assertEqual(box.validate(text, len(text))[0], QValidator.Invalid)

    def test_keyboard_commit_and_arrow_step_with_units(self):
        box = sciSpinBox()
        box.setDecimals(2)
        box.setPrefix("Delay: ")
        box.setSuffix(" ns")
        box.show()
        box.setFocus()
        changes = QSignalSpy(box.valueChanged)
        box.lineEdit().selectAll()
        QTest.keyClicks(box.lineEdit(), "1,25")
        self.assertEqual(box.value(), 0.0)
        QTest.keyClick(box, Qt.Key_Return)
        self.assertEqual(box.value(), 1.25)
        self.assertGreater(changes.count(), 0)
        box.lineEdit().setCursorPosition(box.text().find(".") + 1)
        QTest.keyClick(box, Qt.Key_Up)
        self.assertEqual(box.value(), 1.35)
        box.close()

    def test_comma_locale_display_and_step(self):
        box = sciSpinBox()
        box.setLocale(QLocale(QLocale.Language.Italian))
        box.setDecimals(2)
        box.setValue(1.25)
        self.assertEqual(box.text(), "+1,25")
        box.lineEdit().setCursorPosition(box.text().find(",") + 1)
        box.stepBy(1)
        self.assertEqual(box.text(), "+1,35")


if __name__ == "__main__":
    unittest.main()
