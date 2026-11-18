"""Register browsing and edits, without a physical FPGA session."""

import os
from types import SimpleNamespace
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
from PySide6.QtCore import QPersistentModelIndex, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QCheckBox, QComboBox, QLineEdit, QSpinBox, QTreeView

from brighteyes_mcs.ui.controllers.registers import RegisterEditor
from brighteyes_mcs.ui.qt.register_browser import GROUP_ROLE, PATH_ROLE, VALUE_ROLE, RegisterBrowser, parse_value


pytestmark = pytest.mark.qt


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def browser(app):
    writer = MagicMock(side_effect=lambda path, value: value)
    widget = RegisterBrowser(QTreeView(), lambda path, value: (True, "Live"), writer, lambda: None)
    widget.update_data({"laser_enable": True, "array": [1, 2], "nested": {"gain": 3.5}, "counter": 2**64 - 1})
    yield widget, writer
    widget.close()
    widget.deleteLater()
    app.processEvents()


def test_filter_finds_nested_names_and_values_and_accepts_literal_text(browser):
    widget, _ = browser
    widget.search.setText("GAIN")
    assert widget.proxy.rowCount() == 1
    assert widget.proxy.index(0, 0).data() == "nested"
    assert widget.proxy.index(0, 0, widget.proxy.index(0, 0)).data() == "gain"
    widget.field.setCurrentIndex(2)
    widget.search.setText("3.5")
    assert widget.proxy.rowCount() == 1
    widget.search.setText("[")
    assert widget.proxy.rowCount() == 0
    widget.field.setCurrentIndex(1)
    assert widget.proxy.rowCount() == 1  # Array element names contain '['.
    widget.search.clear()
    assert widget.proxy.rowCount() == 4


def test_find_without_filter_visits_nested_matches(browser):
    widget, _ = browser
    widget.filter.setChecked(False)
    widget.search.setText("gain")
    assert widget.proxy.rowCount() == 4
    widget.find_next()
    assert widget.tree.currentIndex().data(PATH_ROLE) == ("nested", "gain")


def test_value_refresh_keeps_indexes_selection_and_expansion(browser):
    widget, _ = browser
    index = widget.proxy.mapFromSource(widget.model.rows[("array",)][0].index())
    widget.tree.expand(index)
    selected = widget.proxy.mapFromSource(widget.model.rows[("array", 1)][1].index())
    widget.tree.setCurrentIndex(selected)
    persistent = QPersistentModelIndex(selected)
    widget.update_data({"laser_enable": False, "array": [3, 4], "nested": {"gain": 9.0}, "counter": 0})
    assert persistent.isValid() and persistent.data() == "4"
    assert widget.tree.currentIndex() == selected
    assert widget.tree.isExpanded(index)


def test_structure_change_restores_selected_path_and_sorts_array_indexes_numerically(browser):
    widget, _ = browser
    widget.tree.setCurrentIndex(widget.proxy.mapFromSource(widget.model.rows[("array", 1)][1].index()))
    widget.update_data({"array": list(range(12)), "extra": "value"})
    assert widget.tree.currentIndex().data(PATH_ROLE) == ("array", 1)
    parent = widget.proxy.index(0, 0)
    assert [widget.proxy.index(i, 0, parent).data() for i in range(12)] == [f"[{i}]" for i in range(12)]


def test_u64_edits_preserve_precision_and_invalid_edits_report_error(browser):
    widget, writer = browser
    index = widget.model.rows[("counter",)][1].index()
    assert index.data() == str(2**64 - 1)
    assert widget.model.setData(index, "0xffffffffffffffff")
    writer.assert_called_once_with(("counter",), 2**64 - 1)
    assert not widget.model.setData(index, "1.5")
    assert index.data() == str(2**64 - 1)
    assert "Could not update" in widget.message.text()
    writer.side_effect = RuntimeError("write failed")
    assert not widget.model.setData(index, "7")
    assert "write failed" in widget.message.text()
    assert index.data() == str(2**64 - 1)


def test_automatic_refresh_does_not_replace_an_active_editor(browser, app):
    widget, writer = browser
    widget.resize(900, 500)
    widget.show()
    index = widget.proxy.mapFromSource(widget.model.rows[("counter",)][1].index())
    widget.tree.setCurrentIndex(index)
    widget.edit_current()
    app.processEvents()
    editor = widget.tree.findChild(QLineEdit)
    assert editor is not None
    editor.setText("12345678901234567890")
    widget.update_data({"counter": 8, "new": "sample"})
    assert editor.text() == "12345678901234567890"
    QTest.keyClick(editor, Qt.Key.Key_Return)
    app.processEvents()
    writer.assert_called_once_with(("counter",), 12345678901234567890)
    assert widget.model.rows[("counter",)][1].text() == "12345678901234567890"


def test_escape_discards_edit_and_applies_pending_sample(browser, app):
    widget, writer = browser
    widget.show()
    widget.tree.setCurrentIndex(widget.proxy.mapFromSource(widget.model.rows[("counter",)][1].index()))
    widget.edit_current()
    app.processEvents()
    editor = widget.tree.findChild(QLineEdit)
    editor.setText("88")
    widget.update_data({"counter": 22})
    QTest.keyClick(editor, Qt.Key.Key_Escape)
    app.processEvents()
    assert widget.model.rows[("counter",)][1].text() == "22"
    writer.assert_not_called()


def test_f2_opens_value_editor_from_parameter_column(browser, app):
    widget, _ = browser
    widget.show()
    widget.activateWindow()
    widget.tree.setFocus()
    widget.tree.setCurrentIndex(widget.proxy.mapFromSource(widget.model.rows[("counter",)][0].index()))
    app.processEvents()
    QTest.keyClick(widget.tree, Qt.Key.Key_F2)
    app.processEvents()
    assert widget.tree.findChild(QLineEdit) is not None
    QTest.keyClick(widget.tree.findChild(QLineEdit), Qt.Key.Key_Escape)


@pytest.mark.parametrize("text,current,expected", [
    ("False", True, False), ("1", np.bool_(False), True),
    ("08", np.uint64(0), 8), ("-0x10", 0, -16),
    ("2.25", np.float64(0), 2.25), ("raw text", "old", "raw text"),
])
def test_typed_values(text, current, expected):
    assert parse_value(text, current) == expected


@pytest.mark.parametrize("text,current", [("maybe", True), ("NaN", 1.0), ("inf", 1.0), ("1.2", 1)])
def test_invalid_typed_values(text, current):
    with pytest.raises(ValueError):
        parse_value(text, current)


@pytest.fixture
def controller(app):
    trees = [QTreeView() for _ in range(3)]
    spin = QSpinBox()
    spin.setRange(1, 100)
    spin.setValue(5)
    combo = QComboBox()
    combo.addItems(["X", "Y"])
    checkbox = QCheckBox()
    configuration = {"gain": 5, "array": [1, 2, 3]}
    manager = SimpleNamespace(is_connected=True, fpga_handle=MagicMock(),
                              setRegistersDict=MagicMock(side_effect=configuration.update),
                              get_registers_configuration=lambda: configuration)
    window = SimpleNamespace(
        ui=SimpleNamespace(treeView=trees[0], treeView_2=trees[1], treeView_3=trees[2]),
        mcs_manager=manager, configurationFPGA_dict=dict(configuration),
        _latest_status_registers={"gain": 7, "array": [2, 4, 6], "status": 2},
        configurationGUI_dict={}, software_trigger=None, flare=None,
        configuration_helper={"nx": ("Pixels", int, spin, True),
                              "axis": ("Axis", str, combo, True),
                              "enabled": ("Enabled", bool, checkbox, True)},
        getGUI_data=lambda: {"nx": spin.value(), "axis": combo.currentText(), "enabled": checkbox.isChecked()},
    )
    window._status_tree_source = lambda tree: ("", window._latest_status_registers if tree is trees[0]
                                             else window.configurationFPGA_dict)
    editor = RegisterEditor(window)
    editor.metadata = lambda: {
        "gain": SimpleNamespace(is_indicator=False, datatype="U8", is_array=lambda: False),
        "array": SimpleNamespace(is_indicator=False, datatype="I16", is_array=lambda: True),
        "status": SimpleNamespace(is_indicator=True),
    }
    yield editor, window
    for widget in (*trees, spin, combo, checkbox):
        widget.deleteLater()
    app.processEvents()


def test_fpga_edits_use_checked_native_or_manager_configuration_writes(controller):
    editor, window = controller
    assert editor.write(window.ui.treeView, ("gain",), 9) == 9
    window.mcs_manager.fpga_handle.register_write_checked.assert_called_once_with("gain", 9)
    assert window._latest_status_registers["gain"] == 9
    assert window.configurationFPGA_dict["gain"] == 5
    assert editor.write(window.ui.treeView_2, ("array", 1), -4) == -4
    window.mcs_manager.setRegistersDict.assert_called_once_with({"array": [1, -4, 3]})
    assert window.configurationFPGA_dict["array"] == [1, -4, 3]


def test_failed_or_overflowing_fpga_edits_do_not_update_configuration(controller):
    editor, window = controller
    with pytest.raises(ValueError, match="between 0 and 255"):
        editor.write(window.ui.treeView, ("gain",), 256)
    window.mcs_manager.fpga_handle.register_write_checked.assert_not_called()
    window.mcs_manager.setRegistersDict.side_effect = RuntimeError("disconnected")
    with pytest.raises(RuntimeError, match="disconnected"):
        editor.write(window.ui.treeView_2, ("gain",), 9)
    assert window.configurationFPGA_dict["gain"] == 5


def test_numpy_array_edit_validates_before_casting_or_writing(controller):
    editor, window = controller
    window.configurationFPGA_dict["array"] = np.array([1, 2, 3], dtype=np.int16)
    with pytest.raises(ValueError, match="between -32768 and 32767"):
        editor.write(window.ui.treeView_2, ("array", 1), 32768)
    np.testing.assert_array_equal(window.configurationFPGA_dict["array"], [1, 2, 3])
    window.mcs_manager.setRegistersDict.assert_not_called()


def test_disconnected_configuration_edits_are_staged_and_status_is_read_only(controller):
    editor, window = controller
    window.mcs_manager.is_connected = False
    assert editor.access(window.ui.treeView_2, ("gain",), 5) == (True, "Staged FPGA")
    assert not editor.access(window.ui.treeView, ("gain",), 7)[0]
    assert not editor.access(window.ui.treeView_2, ("status",), 2)[0]
    assert editor.write(window.ui.treeView_2, ("gain",), 12) == 12
    assert window.configurationFPGA_dict["gain"] == 12


def test_gui_edits_emit_widget_signals_and_validate_controls(controller):
    editor, window = controller
    spin = window.configuration_helper["nx"][2]
    changed = MagicMock()
    spin.valueChanged.connect(changed)
    assert editor.write(window.ui.treeView_3, ("nx",), 42) == 42
    changed.assert_called_once_with(42)
    assert window.configurationGUI_dict["nx"] == 42
    with pytest.raises(ValueError, match="between"):
        editor.write(window.ui.treeView_3, ("nx",), 101)
    with pytest.raises(ValueError, match="Choose one of"):
        editor.write(window.ui.treeView_3, ("axis",), "Z")
    clicked = MagicMock()
    window.configuration_helper["enabled"][2].clicked.connect(lambda checked: clicked(checked))
    assert editor.write(window.ui.treeView_3, ("enabled",), True)
    clicked.assert_called_once_with(True)
    spin.setEnabled(False)
    with pytest.raises(ValueError, match="Read only"):
        editor.write(window.ui.treeView_3, ("nx",), 5)


def test_armed_acquisition_is_checked_again_at_commit(controller):
    editor, window = controller
    window.software_trigger = SimpleNamespace(active=True)
    for tree in (window.ui.treeView, window.ui.treeView_2, window.ui.treeView_3):
        with pytest.raises(ValueError, match="Acquisition armed"):
            editor.write(tree, ("gain",), 6)
    window.mcs_manager.setRegistersDict.assert_not_called()


def test_active_bitfile_metadata_is_cached_and_invalidated(app, tmp_path, monkeypatch):
    bitfile = tmp_path / "test.lvbitx"
    bitfile.write_text("first")
    line_edit = QLineEdit(str(bitfile))
    manager = SimpleNamespace(is_connected=False)
    editor = RegisterEditor(SimpleNamespace(mcs_manager=manager, ui=SimpleNamespace(lineEdit_fpgabitfile=line_edit)))
    reader = MagicMock(return_value=SimpleNamespace(registers={"gain": "metadata"}))
    monkeypatch.setattr("brighteyes_mcs.ui.controllers.registers.nifpga.Bitfile", reader)
    assert editor.metadata() == {"gain": "metadata"}
    editor.metadata()
    reader.assert_called_once()
    manager.is_connected = True
    manager.fpga_handle = SimpleNamespace(configuration={"bitfile": str(bitfile)})
    line_edit.setText("another-selection.lvbitx")
    assert editor.metadata() == {"gain": "metadata"}
    bitfile.unlink()
    assert editor.metadata() == {}
    line_edit.deleteLater()


def test_unchanged_register_sample_emits_no_model_changes(browser):
    widget, _ = browser
    changed = MagicMock()
    widget.model.dataChanged.connect(changed)
    widget.update_data({"laser_enable": True, "array": [1, 2], "nested": {"gain": 3.5}, "counter": 2**64 - 1})
    changed.assert_not_called()
    widget.update_data({"laser_enable": False, "array": [1, 2], "nested": {"gain": 3.5}, "counter": 2**64 - 1})
    assert changed.call_count > 0
    assert widget.model.rows[("laser_enable",)][1].text() == "False"


def test_register_metadata_is_resolved_once_per_refresh_batch(controller):
    editor, window = controller
    registers = editor.metadata()
    editor.metadata = MagicMock(return_value=registers)
    with editor.refresh_snapshot():
        for _ in range(20):
            assert editor.access(window.ui.treeView_2, ("gain",), 5)[0]
    editor.metadata.assert_called_once()
    editor.access(window.ui.treeView_2, ("gain",), 5)
    assert editor.metadata.call_count == 2


@pytest.mark.parametrize("data,name,value", [
    ({"gain": 42}, "gain", 42.0),
    ({"laser_value": 3, "laser_limit": 4}, "laser_value", 3.0),
])
def test_register_context_menu_still_adds_numeric_values_to_monitor(browser, monkeypatch, data, name, value):
    from PySide6.QtCore import QPoint
    from brighteyes_mcs.ui.qt.main_window import MainWindow

    widget, _ = browser
    widget.update_data(data)
    index = widget.proxy.mapFromSource(widget.model.rows[(name,)][1].index())
    monkeypatch.setattr(widget.tree, "indexAt", lambda position: index)
    actions = [MagicMock() for _ in range(4)]
    menu = MagicMock()
    menu.addAction.side_effect = actions
    menu.exec.return_value = actions[-1]
    monkeypatch.setattr("brighteyes_mcs.ui.qt.main_window.QMenu", lambda parent: menu)
    window = SimpleNamespace(_status_tree_source=lambda tree: ("Conf. FPGA dict.", {}),
                             _monitored_registers={}, _coerce_monitor_value=MainWindow._coerce_monitor_value,
                             addRegisterToMonitor=MagicMock())
    MainWindow.statusRegisterContextMenu(window, widget.tree, QPoint())
    window.addRegisterToMonitor.assert_called_once_with(name, source_name="Conf. FPGA dict.", value=value)


@pytest.fixture
def grouped_browser(app):
    writer = MagicMock(side_effect=lambda path, value: value)
    widget = RegisterBrowser(QTreeView(), lambda path, value: (True, "Live"), writer, lambda: None)
    widget.update_data({
        "analog_output_0_volts": 1.5, "analog_output_0_source_selector": 0,
        "analog_output_2_volts": 2.5, "analog_output_2_source_selector": 1,
        "analog_output_10_volts": 3.5, "analog_output_10_source_selector": 2,
        "analog_input_0_volts": 4.5, "laser_1_enable": True, "laser_2_enable": False,
        "axis_start_offset_volts": [1.0, 2.0, 3.0], "isolated_value": 7,
    })
    yield widget, writer
    widget.close()
    widget.deleteLater()
    app.processEvents()


def test_underscore_groups_compress_chains_and_sort_channel_numbers(grouped_browser):
    widget, _ = grouped_browser
    assert ("analog",) in widget.model.groups
    assert ("analog", "output") in widget.model.groups
    assert ("isolated",) not in widget.model.groups
    assert widget.model.rows[("analog_output_0_volts",)][0].text() == "volts"
    assert widget.model.rows[("analog_output_0_volts",)][0].parent() is widget.model.groups[("analog", "output", "0")]
    assert "analog_output_0_volts" in widget.model.rows[("analog_output_0_volts",)][0].toolTip()
    parent = widget.proxy.mapFromSource(widget.model.groups[("analog", "output")].index())
    assert [widget.proxy.index(i, 0, parent).data() for i in range(3)] == ["0", "2", "10"]
    widget.update_data({"long_common_prefix_x": 1, "long_common_prefix_y": 2})
    assert set(widget.model.groups) == {("long", "common", "prefix")}
    assert widget.model.groups[("long", "common", "prefix")].text() == "long_common_prefix"


def test_full_register_names_are_searchable_and_find_skips_virtual_groups(grouped_browser):
    widget, _ = grouped_browser
    widget.search.setText("analog_output_10_volts")
    widget.find_next()
    assert widget.tree.currentIndex().data(PATH_ROLE) == ("analog_output_10_volts",)
    assert widget.count.text() == "1 / 11 parameters"
    widget.search.setText("laser")
    widget.find_next()
    assert widget.tree.currentIndex().data(PATH_ROLE) in (("laser_1_enable",), ("laser_2_enable",))
    assert widget.tree.currentIndex().data(GROUP_ROLE) is None
    widget.field.setCurrentIndex(2)
    widget.search.setText("registers")
    assert widget.proxy.rowCount() == 0  # Group counts are not register values.


def test_group_headers_are_read_only_and_cannot_collide_with_real_registers(grouped_browser):
    widget, writer = grouped_browser
    widget.update_data({"laser": 3, "laser_enable": True, "laser_power": 5})
    group = widget.model.groups[("laser",)]
    assert group.data(PATH_ROLE) is None
    assert not widget.model.setData(group.index().siblingAtColumn(1), "9")
    assert widget.model.rows[("laser",)][0].parent() is group
    assert widget.model.setData(widget.model.rows[("laser",)][1].index(), "8")
    writer.assert_called_once_with(("laser",), 8)


def test_grouped_registers_and_array_elements_write_original_paths(grouped_browser):
    widget, writer = grouped_browser
    assert widget.model.setData(widget.model.rows[("analog_output_0_volts",)][1].index(), "-2.125")
    writer.assert_called_with(("analog_output_0_volts",), -2.125)
    assert widget.model.setData(widget.model.rows[("axis_start_offset_volts", 1)][1].index(), "6.25")
    writer.assert_called_with(("axis_start_offset_volts", 1), 6.25)


def test_group_toggle_preserves_edits_selection_and_array_expansion(grouped_browser):
    widget, writer = grouped_browser
    array = widget.proxy.mapFromSource(widget.model.rows[("axis_start_offset_volts",)][0].index())
    widget.tree.expand(array)
    selected = widget.proxy.mapFromSource(widget.model.rows[("axis_start_offset_volts", 1)][1].index())
    widget.tree.setCurrentIndex(selected)
    assert widget.model.setData(widget.model.rows[("axis_start_offset_volts", 1)][1].index(), "6.25")
    for grouped in (False, True, False, True):
        widget.group_prefixes.setChecked(grouped)
        assert widget.tree.currentIndex().data(PATH_ROLE) == ("axis_start_offset_volts", 1)
        assert widget.tree.currentIndex().data() == "6.25"
        array = widget.proxy.mapFromSource(widget.model.rows[("axis_start_offset_volts",)][0].index())
        assert widget.tree.isExpanded(array)
    assert writer.call_count == 1
    widget.group_prefixes.setChecked(False)
    assert not widget.model.groups
    assert widget.model.rows[("analog_output_0_volts",)][0].text() == "analog_output_0_volts"


def test_grouped_value_refresh_keeps_indexes_and_collapsed_branches(grouped_browser):
    widget, _ = grouped_browser
    data = {path[0]: row[1].data(VALUE_ROLE).value for path, row in widget.model.rows.items() if len(path) == 1}
    group = widget.proxy.mapFromSource(widget.model.groups[("analog", "output")].index())
    widget.tree.collapse(group)
    index = QPersistentModelIndex(widget.model.rows[("analog_output_0_volts",)][1].index())
    data["analog_output_0_volts"] = 8.0
    widget.update_data(data)
    assert index.isValid() and index.data() == "8.0"
    assert not widget.tree.isExpanded(group)
    group_index = QPersistentModelIndex(widget.model.groups[("analog", "output")].index())
    widget.update_data(data)
    assert group_index.isValid()


def test_group_toggle_waits_for_active_editor(grouped_browser, app):
    widget, _ = grouped_browser
    widget.show()
    index = widget.proxy.mapFromSource(widget.model.rows[("analog_output_0_volts",)][1].index())
    widget.tree.setCurrentIndex(index)
    widget.edit_current()
    app.processEvents()
    editor = widget.tree.findChild(QLineEdit)
    editor.setText("7.25")
    widget.group_prefixes.setChecked(False)
    assert widget.group_prefixes.isChecked()
    assert editor.text() == "7.25"
    QTest.keyClick(editor, Qt.Key.Key_Escape)
