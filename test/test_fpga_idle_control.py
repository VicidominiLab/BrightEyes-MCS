from types import SimpleNamespace
from unittest.mock import MagicMock, call

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
