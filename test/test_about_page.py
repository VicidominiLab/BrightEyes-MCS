from pathlib import Path


ABOUT_PAGE = (
    Path(__file__).parents[1]
    / "brighteyes_mcs"
    / "ui"
    / "qt"
    / "about.html"
)


def test_about_page_contains_credits_citation_and_both_licenses():
    page = ABOUT_PAGE.read_text(encoding="utf-8")

    assert "Credits and citation" in page
    assert "10.21105/joss.07125" in page
    assert "BrightEyes-MCS software license" in page
    assert "Full GNU General Public License" in page
    assert "BrightEyes-MCSLL firmware: separate license" in page
    assert "Closed-Source Firmware License Agreement" in page
    assert "BrightEyes-MCSLL/blob/main/LICENSE.md" in page


def test_designer_no_longer_contains_the_license_button():
    root = ABOUT_PAGE.parents[2]
    generated = (root / "ui/qt/main_window_design.py").read_text(encoding="utf-8")
    designer = (root / "ui/qt/main_window_design.ui").read_text(encoding="utf-8")

    assert "pushButton_about" not in generated
    assert "pushButton_about" not in designer
