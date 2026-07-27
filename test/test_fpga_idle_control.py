from types import SimpleNamespace
from unittest.mock import MagicMock, call

import numpy as np
import pytest

from brighteyes_mcs.acquisition.manager import McsManager
from brighteyes_mcs.hardware.fpga import FpgaHandle
from brighteyes_mcs.ui.qt.main_window import MainWindow


def bare_manager():
    manager = McsManager.__new__(McsManager)
    manager.is_connected = True
    manager.fpga_handle = MagicMock()
    manager.registers_configuration = {}
    return manager


def test_quick_reset_pulses_stop_and_waits_for_idle():
    manager = bare_manager()
    manager.wait_for_fpga_idle = MagicMock()

    manager.quick_reset_fpga(timeout=2.5)

    assert manager.fpga_handle.register_write_checked.call_args_list == [
        call("stop", True),
        call("stop", False),
    ]
    assert manager.registers_configuration["stop"] is False
    manager.wait_for_fpga_idle.assert_called_once_with(
        timeout=2.5, poll_interval=0.01
    )


def test_wait_for_fpga_idle_returns_on_status_zero():
    manager = bare_manager()
    manager.fpga_handle.register_read.side_effect = [
        {"FSM Status": 3},
        {"FSM Status": 0},
    ]

    manager.wait_for_fpga_idle(timeout=1, poll_interval=0)

    assert manager.registers_configuration["FSM Status"] == 0
    assert manager.fpga_handle.register_read.call_count == 2


def test_wait_for_fpga_idle_raises_after_timeout():
    manager = bare_manager()
    manager.fpga_handle.register_read.return_value = {"FSM Status": 4}

    with pytest.raises(TimeoutError, match="last status: 4"):
        manager.wait_for_fpga_idle(timeout=0.001, poll_interval=0)


def test_experimental_run_pulses_run_true_then_false():
    window = MainWindow.__new__(MainWindow)
    window.ui = SimpleNamespace(
        checkBox_loadFirmwareOnce=MagicMock(
            isChecked=MagicMock(return_value=True)
        )
    )
    window.setRegistersDict = MagicMock()

    window.sendCmdRun()

    assert window.setRegistersDict.call_args_list == [
        call({"stop": False, "Run": True}),
        call({"Run": False}),
    ]


def test_default_run_sequence_is_unchanged():
    window = MainWindow.__new__(MainWindow)
    window.ui = SimpleNamespace(
        checkBox_loadFirmwareOnce=MagicMock(
            isChecked=MagicMock(return_value=False)
        )
    )
    window.setRegistersDict = MagicMock()

    window.sendCmdRun()

    assert window.setRegistersDict.call_args_list == [
        call({"stop": False, "Run": False}),
        call({"Run": True}),
    ]


def acquisition_window(load_once):
    window = MainWindow.__new__(MainWindow)
    window.ui = SimpleNamespace(
        checkBox_loadFirmwareOnce=MagicMock(
            isChecked=MagicMock(return_value=load_once)
        )
    )
    window.mcs_manager = MagicMock()
    window.timerPreviewImg = MagicMock()
    window.sendCmdStop = MagicMock()
    return window


def test_experimental_stop_keeps_fpga_loaded_after_idle_reset():
    window = acquisition_window(load_once=True)

    window.stopAcquisition()

    window.mcs_manager.quick_reset_fpga.assert_called_once_with(timeout=5.0)
    window.mcs_manager.stopFPGA.assert_not_called()
    window.mcs_manager.stopAcquisition.assert_called_once_with(
        keep_fpga_loaded=True
    )


def test_default_stop_sequence_is_unchanged():
    window = acquisition_window(load_once=False)

    window.stopAcquisition()

    window.sendCmdStop.assert_called_once_with()
    window.mcs_manager.quick_reset_fpga.assert_not_called()
    window.mcs_manager.stopFPGA.assert_called_once_with()
    window.mcs_manager.stopAcquisition.assert_called_once_with(
        keep_fpga_loaded=False
    )


def test_window_shutdown_closes_fpga_even_when_quick_reset_fails():
    window = MainWindow.__new__(MainWindow)
    window._shutdown_started = False
    window._shutdown_complete = False
    window.mcs_manager = MagicMock(is_connected=True)
    window.mcs_manager.quick_reset_fpga.side_effect = TimeoutError("not idle")
    window.timerPreviewImg = MagicMock()
    window.ttm_remote_manager = None

    window.shutdown()

    window.mcs_manager.quick_reset_fpga.assert_called_once_with(timeout=5.0)
    window.mcs_manager.stopPreview.assert_called_once_with()
    window.mcs_manager.stopAcquisition.assert_called_once_with()
    window.mcs_manager.stopFPGA.assert_called_once_with()
    assert window._shutdown_complete is True
    assert window.mcs_manager.is_connected is False


def test_window_shutdown_is_idempotent():
    window = MainWindow.__new__(MainWindow)
    window._shutdown_started = False
    window._shutdown_complete = False
    window.mcs_manager = MagicMock(is_connected=False)
    window.timerPreviewImg = MagicMock()
    window.ttm_remote_manager = None

    window.shutdown()
    window.shutdown()

    window.mcs_manager.stopFPGA.assert_called_once_with()


def test_fpga_handle_stop_closes_all_sessions_after_an_error():
    handle = FpgaHandle.__new__(FpgaHandle)
    handle.configuration = {"stop_event": MagicMock()}
    handle.fpga_handle_process = None
    handle.nifpga_obj = MagicMock()
    handle.nifpga_obj.abort.side_effect = RuntimeError("abort failed")
    handle.nifpga_obj2 = MagicMock()
    primary = handle.nifpga_obj
    secondary = handle.nifpga_obj2

    with pytest.raises(RuntimeError, match="shutdown completed with 1 error"):
        handle.stop()

    primary.abort.assert_called_once_with()
    primary.reset.assert_called_once_with()
    primary.close.assert_called_once_with()
    secondary.abort.assert_called_once_with()
    secondary.reset.assert_called_once_with()
    secondary.close.assert_called_once_with()
    assert handle.nifpga_obj is None
    assert handle.nifpga_obj2 is None


def test_circular_voltage_points_are_calibrated_offset_and_projected():
    x_points, y_points = MainWindow._circular_points_for_projection(
        registers={
            "ScanXVoltages": [1.0, 2.0, 99.0],
            "ScanYVoltages": [3.0, 4.0, 99.0],
            "ScanZVoltages": [1.0, 2.0, 99.0],
        },
        projection="xz",
        calibration=(2.0, 3.0, 4.0),
        offset=(10.0, 20.0, 30.0),
        point_count=2,
    )

    np.testing.assert_allclose(x_points, [12.0, 14.0])
    np.testing.assert_allclose(y_points, [34.0, 38.0])


def test_unit_lissajous_frequencies_generate_a_circle():
    x_offsets, y_offsets = MainWindow._lissajous_offsets(
        radius=2.0,
        point_count=4,
        omega_x=1,
        omega_y=1,
    )

    np.testing.assert_allclose(x_offsets, [2.0, 0.0, -2.0, 0.0], atol=1e-12)
    np.testing.assert_allclose(y_offsets, [0.0, 2.0, 0.0, -2.0], atol=1e-12)


def test_lissajous_frequencies_control_each_axis_independently():
    x_offsets, y_offsets = MainWindow._lissajous_offsets(
        radius=2.0,
        point_count=4,
        omega_x=2,
        omega_y=1,
    )

    np.testing.assert_allclose(x_offsets, [2.0, -2.0, 2.0, -2.0], atol=1e-12)
    np.testing.assert_allclose(y_offsets, [0.0, 2.0, 0.0, -2.0], atol=1e-12)


def test_lissajous_phase_rotates_the_generated_curve():
    x_offsets, y_offsets = MainWindow._lissajous_offsets(
        radius=2.0,
        point_count=4,
        omega_x=1,
        omega_y=1,
        phase_deg=90,
    )

    np.testing.assert_allclose(x_offsets, [0.0, -2.0, 0.0, 2.0], atol=1e-12)
    np.testing.assert_allclose(y_offsets, [2.0, 0.0, -2.0, 0.0], atol=1e-12)


def test_lissajous_first_position_rotates_the_output_array():
    x_offsets, y_offsets = MainWindow._lissajous_offsets(
        radius=1.0,
        point_count=4,
        omega_x=1,
        omega_y=1,
        first_position=1,
    )

    np.testing.assert_allclose(x_offsets, [0.0, -1.0, 0.0, 1.0], atol=1e-12)
    np.testing.assert_allclose(y_offsets, [1.0, 0.0, -1.0, 0.0], atol=1e-12)


def test_disabling_lissajous_restores_unit_frequencies():
    window = MainWindow.__new__(MainWindow)
    omega_x = MagicMock()
    omega_y = MagicMock()
    phase = MagicMock()
    first_position = MagicMock()
    omega_x.blockSignals.return_value = False
    omega_y.blockSignals.return_value = False
    phase.blockSignals.return_value = False
    first_position.blockSignals.return_value = False
    window.updateLissajousMiniPlot = MagicMock()
    window.ui = SimpleNamespace(
        spinBox_lissajous_omega_x=omega_x,
        spinBox_lissajous_omega_y=omega_y,
        spinBox_lissajous_phase_deg=phase,
        spinBox_lissajous_firstposition=first_position,
        checkBox_circular=MagicMock(
            isChecked=MagicMock(return_value=False)
        ),
    )

    window.lissajousModeChanged(False)

    omega_x.setEnabled.assert_called_once_with(False)
    omega_y.setEnabled.assert_called_once_with(False)
    omega_x.setValue.assert_called_once_with(1)
    omega_y.setValue.assert_called_once_with(1)
    phase.setEnabled.assert_called_once_with(False)
    phase.setValue.assert_called_once_with(0)
    first_position.setEnabled.assert_called_once_with(False)
    first_position.setValue.assert_called_once_with(0)


def test_lissajous_mini_plot_marks_selected_fpga_sample_points():
    window = MainWindow.__new__(MainWindow)
    window.ui = SimpleNamespace(
        checkBox_lissajous=MagicMock(
            isChecked=MagicMock(return_value=True)
        ),
        spinBox_lissajous_omega_x=MagicMock(
            value=MagicMock(return_value=1)
        ),
        spinBox_lissajous_omega_y=MagicMock(
            value=MagicMock(return_value=1)
        ),
        spinBox_lissajous_phase_deg=MagicMock(
            value=MagicMock(return_value=0)
        ),
        spinBox_lissajous_firstposition=MagicMock(
            value=MagicMock(return_value=0)
        ),
        spinBox_circular_points=MagicMock(
            value=MagicMock(return_value=4)
        ),
    )
    window.lissajous_mini_curve = MagicMock()
    window.lissajous_mini_points = MagicMock()
    window.lissajous_mini_first_point = MagicMock()
    window.lissajous_mini_plot = MagicMock()

    window.updateLissajousMiniPlot()

    point_data = window.lissajous_mini_points.setData.call_args.kwargs
    np.testing.assert_allclose(
        point_data["x"], [1.0, 0.0, -1.0, 0.0], atol=1e-12
    )
    np.testing.assert_allclose(
        point_data["y"], [0.0, 1.0, 0.0, -1.0], atol=1e-12
    )
    first_point = window.lissajous_mini_first_point.setData.call_args.kwargs
    np.testing.assert_allclose(first_point["x"], [1.0], atol=1e-12)
    np.testing.assert_allclose(first_point["y"], [0.0], atol=1e-12)


def test_only_finite_numeric_scalars_can_be_monitored():
    assert MainWindow._is_monitorable_value(3)
    assert MainWindow._is_monitorable_value(np.float64(2.5))
    assert not MainWindow._is_monitorable_value(True)
    assert not MainWindow._is_monitorable_value(np.nan)
    assert not MainWindow._is_monitorable_value([1, 2])


def test_circular_points_replicate_at_each_raster_pixel_center():
    window = MainWindow.__new__(MainWindow)
    window._latest_status_registers = {
        "ScanXVoltages": [99.0],
        "ScanYVoltages": [99.0],
        "ScanZVoltages": [99.0],
    }
    window.configurationFPGA_dict = {
        "ScanXVoltages": [1.0, 2.0],
        "ScanYVoltages": [3.0, 4.0],
        "ScanZVoltages": [5.0, 6.0],
    }
    # The circular overlay must use the geometry of the displayed image, not
    # potentially newer values in the GUI controls.
    window.currentImage_pos = np.asarray([10.0, 20.0, 30.0])
    window.currentImage_size = np.asarray([4.0, 2.0, 0.0])
    window.currentImage_pixels = np.asarray([2, 1, 1])
    window._last_circular_debug_signature = None
    window.ui = SimpleNamespace(
        comboBox_view_projection=MagicMock(
            currentText=MagicMock(return_value="xy")
        ),
        spinBox_calib_x=MagicMock(value=MagicMock(return_value=2.0)),
        spinBox_calib_y=MagicMock(value=MagicMock(return_value=3.0)),
        spinBox_calib_z=MagicMock(value=MagicMock(return_value=4.0)),
        spinBox_off_x_um=MagicMock(value=MagicMock(return_value=-500.0)),
        spinBox_off_y_um=MagicMock(value=MagicMock(return_value=-500.0)),
        spinBox_off_z_um=MagicMock(value=MagicMock(return_value=-500.0)),
        spinBox_range_x=MagicMock(value=MagicMock(return_value=900.0)),
        spinBox_range_y=MagicMock(value=MagicMock(return_value=900.0)),
        spinBox_range_z=MagicMock(value=MagicMock(return_value=900.0)),
        spinBox_nx=MagicMock(value=MagicMock(return_value=9)),
        spinBox_ny=MagicMock(value=MagicMock(return_value=9)),
        spinBox_nframe=MagicMock(value=MagicMock(return_value=9)),
        spinBox_circular_points=MagicMock(value=MagicMock(return_value=2)),
        checkBox_lissajous=MagicMock(
            isChecked=MagicMock(return_value=False)
        ),
        spinBox_lissajous_omega_x=MagicMock(
            value=MagicMock(return_value=1)
        ),
        spinBox_lissajous_omega_y=MagicMock(
            value=MagicMock(return_value=1)
        ),
        spinBox_lissajous_phase_deg=MagicMock(
            value=MagicMock(return_value=0)
        ),
        spinBox_lissajous_firstposition=MagicMock(
            value=MagicMock(return_value=0)
        ),
    )
    window.circular_scan_points = MagicMock()
    window.circular_scan_first_points = MagicMock()
    window.circular_preview_plot_item = MagicMock()

    window.updateCircularPoints()

    call_kwargs = window.circular_scan_points.setData.call_args.kwargs
    np.testing.assert_allclose(call_kwargs["x"], [11.0, 13.0, 13.0, 15.0])
    np.testing.assert_allclose(call_kwargs["y"], [29.0, 32.0, 29.0, 32.0])
    first_points = window.circular_scan_first_points.setData.call_args.kwargs
    np.testing.assert_allclose(first_points["x"], [11.0, 13.0])
    np.testing.assert_allclose(first_points["y"], [29.0, 29.0])


def test_status_update_appends_one_point_to_each_monitored_register():
    window = MainWindow.__new__(MainWindow)
    first_curve = MagicMock()
    second_curve = MagicMock()
    window._monitored_registers = {
        ("Read Conf. FPGA", "FSM Status"): {
            "source_name": "Read Conf. FPGA",
            "register_name": "FSM Status",
            "times": [],
            "values": [],
            "curve": first_curve,
        },
        ("Conf. FPGA dict.", "cur_x"): {
            "source_name": "Conf. FPGA dict.",
            "register_name": "cur_x",
            "times": [],
            "values": [],
            "curve": second_curve,
        },
    }

    window._append_monitor_points(
        {
            "Read Conf. FPGA": {"FSM Status": 2},
            "Conf. FPGA dict.": {"cur_x": 17},
        },
        timestamp=1.25,
    )

    first_trace = window._monitored_registers[
        ("Read Conf. FPGA", "FSM Status")
    ]
    second_trace = window._monitored_registers[
        ("Conf. FPGA dict.", "cur_x")
    ]
    assert first_trace["times"] == [1.25]
    assert first_trace["values"] == [2.0]
    assert second_trace["times"] == [1.25]
    assert second_trace["values"] == [17.0]
    first_curve.setData.assert_called_once_with([1.25], [2.0])
    second_curve.setData.assert_called_once_with([1.25], [17.0])
