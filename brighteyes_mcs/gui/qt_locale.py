"""Qt locale policy for BrightEyes-MCS GUI numeric input."""

from PySide6.QtCore import QLocale


def scientific_locale():
    """
    Return the project GUI locale.

    BrightEyes-MCS is a scientific application, so numeric widgets use "." as
    decimal separator independent of the operating-system locale.
    """
    return QLocale(QLocale.Language.English, QLocale.Country.UnitedStates)


def install_scientific_locale():
    """
    Make "." the default decimal separator for Qt widgets created afterwards.
    """
    locale = scientific_locale()
    QLocale.setDefault(locale)
    return locale
