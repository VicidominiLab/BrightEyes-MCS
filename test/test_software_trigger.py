"""Software frame triggering without a connected FPGA."""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import MagicMock, call

import pytest

from brighteyes_mcs.acquisition.manager import McsManager
from brighteyes_mcs.acquisition.software_trigger import SoftwareTriggerSession


def registers():
    return {
        "max_frame": 3, "max_repetition": 3, "max_pixel": 2, "max_line": 2,
        "max_time_bins_per_pixel": 2, "max_circular_point": 1, "max_circular_repetition": 1,
        "time_bin_dwell_cycles": 40, "axis_start_offset_volts": [1.0, 2.0, 3.0],
        "axis_calibration_volts_per_step": [0.1, 0.2, 0.5],
        "laser_1_enable": True, "laser_2_enable": False,
        "laser_3_enable": True, "laser_4_enable": False,
        "laser_force_pulsing_enable": True, "laser_off_after_measurement_enable": False,
        "wait_laser_first_time_only_enable": True, "z_snake_scan_enable": False,
        "slave_mode_enable": False,
    }


def manager_stub():
    manager = McsManager.__new__(McsManager)
    manager.registers_configuration = registers()
    manager.is_connected = True
    manager.detector_model = "SPAD Array"
    manager.clock_base = 40
    manager.spad_channels = 25
    manager.fpga_handle = MagicMock()
    manager.fpga_handle.register_read_all.return_value = {}
    manager.shared_dict = {"software_trigger_worker_ready": True}
    manager.activated_fifos_list = ["stream_out_main", "stream_out_aux"]
    manager.raw_stream_mode = False
    manager.quick_reset_fpga = MagicMock()
    manager.check_fpga_alive = MagicMock(return_value=0)
    manager.loc_acquired = {fifo: SimpleNamespace(value=0) for fifo in manager.activated_fifos_list}
    return manager


def make_session(**kwargs):
    manager = manager_stub()
    session = SoftwareTriggerSession(manager, **kwargs)
    manager.software_trigger_session = session
    session.prepare()
    manager.readRegistersDict()
    session.arm()
    return manager, session


def complete_frame(manager, session):
    for fifo in manager.activated_fifos_list:
        manager.shared_dict[f"software_trigger_frames_{fifo}"] = session.issued
    session.poll()


def test_single_frame_hardware_preserves_full_software_shape_and_counts():
    manager, session = make_session()
    assert manager.registers_configuration["max_frame"] == 1
    assert manager.registers_configuration["max_repetition"] == 2
    assert (manager.dim_z, manager.dim_rep) == (3, 2)
    assert manager.expected_words_data_digital == 96
    assert manager.expected_words_data_analog == 48
    assert session.state == "armed"
    assert call("start_command", True) not in manager.fpga_handle.register_write_checked.call_args_list


def test_unselected_mode_still_uses_hardware_dimensions():
    manager = manager_stub()
    manager.software_trigger_session = None
    manager.readRegistersDict()
    assert (manager.dim_z, manager.dim_rep) == (3, 2)
    assert manager.expected_words_data_digital == 96
    manager.fpga_handle.register_write_checked.assert_not_called()


def test_one_trigger_waits_for_both_streams_and_fpga_idle():
    manager, session = make_session()
    assert session.trigger()
    assert not session.trigger()
    manager.shared_dict["software_trigger_frames_stream_out_main"] = 1
    session.poll()
    assert session.state == "draining" and session.completed == 0
    manager.shared_dict["software_trigger_frames_stream_out_aux"] = 1
    manager.check_fpga_alive.return_value = 2
    session.poll()
    assert session.completed == 0
    manager.check_fpga_alive.return_value = 0
    session.poll()
    assert session.state == "armed" and session.completed == 1
    writes = manager.fpga_handle.register_write_checked.call_args_list
    assert writes.count(call("start_command", True)) == 1


@pytest.mark.parametrize("snake, expected_z", [
    (False, [3, 3.5, 4, 3, 3.5, 4]), (True, [3, 3.5, 4, 4, 3.5, 3]),
])
def test_frame_positions_repetitions_and_automatic_completion(snake, expected_z):
    manager, session = make_session()
    session.requested["z_snake_scan_enable"] = snake
    actual_z = []
    for _ in range(6):
        assert session.trigger()
        actual_z.append(manager.registers_configuration["axis_start_offset_volts"][2])
        complete_frame(manager, session)
    assert actual_z == expected_z
    assert session.state == "complete" and not session.trigger()
    assert session.metadata()["frames_completed"] == 6
    assert session.metadata()["complete"]


def test_preview_does_not_finish_at_configured_frame_count(monkeypatch):
    manager, session = make_session(preview=True)
    for _ in range(8):
        assert session.trigger()
        complete_frame(manager, session)
    assert session.state == "armed"
    assert manager.expected_words_data_digital == (1 << 63) - 1
    monkeypatch.setattr("brighteyes_mcs.acquisition.software_trigger.time.monotonic", lambda: 1e20)
    session.poll()
    assert session.state == "armed"  # Human waits never time out.


def test_lasers_off_while_armed_restore_only_selected_lasers_then_off_at_idle():
    manager, session = make_session(laser_off=True)
    assert not any(manager.registers_configuration[f"laser_{i}_enable"] for i in range(1, 5))
    assert manager.registers_configuration["laser_off_after_measurement_enable"]
    assert not manager.registers_configuration["wait_laser_first_time_only_enable"]
    assert session.trigger()
    assert [manager.registers_configuration[f"laser_{i}_enable"] for i in range(1, 5)] == [True, False, True, False]
    session.poll()  # FPGA idle, data still draining.
    assert not manager.registers_configuration["laser_force_pulsing_enable"]
    assert not any(manager.registers_configuration[f"laser_{i}_enable"] for i in range(1, 5))
    session.restore()
    assert not manager.registers_configuration["laser_off_after_measurement_enable"]
    assert manager.registers_configuration["wait_laser_first_time_only_enable"]
    assert session.requested["laser_1_enable"]


def test_unchecked_laser_option_never_writes_laser_controls():
    manager, session = make_session()
    assert session.trigger()
    complete_frame(manager, session)
    assert not any(c.args[0].startswith("laser_") for c in manager.fpga_handle.register_write_checked.call_args_list)


def test_missing_frame_times_out_only_after_trigger(monkeypatch):
    manager, session = make_session()
    assert session.trigger()
    monkeypatch.setattr("brighteyes_mcs.acquisition.software_trigger.time.monotonic", lambda: session.deadline + 1)
    with pytest.raises(TimeoutError, match="all enabled data streams"):
        session.poll()
    assert session.state == "error"
    assert not session.metadata()["complete"]


def test_raw_progress_requires_complete_frame_on_each_stream():
    manager, session = make_session()
    manager.raw_stream_mode = True
    assert session.trigger()
    manager.loc_acquired["stream_out_main"].value = 16
    manager.loc_acquired["stream_out_aux"].value = 7
    session.poll()
    assert session.completed == 0
    manager.loc_acquired["stream_out_aux"].value = 8
    session.poll()
    assert session.completed == 1


def test_early_stop_metadata_and_restoration_preserve_requested_settings():
    manager, session = make_session()
    original = deepcopy(session.requested)
    assert session.trigger()
    complete_frame(manager, session)
    assert session.trigger()  # Stop during second frame.
    metadata = session.metadata()
    assert metadata["frames_requested"] == 6
    assert metadata["frames_triggered"] == 2
    assert metadata["frames_completed"] == 1
    assert not metadata["complete"]
    session.restore()
    assert manager.registers_configuration["max_frame"] == original["max_frame"]
    assert manager.registers_configuration["max_repetition"] == original["max_repetition"]
    assert manager.registers_configuration["axis_start_offset_volts"] == original["axis_start_offset_volts"]


def test_pispad23_waits_for_receiver_before_each_trigger():
    manager = manager_stub()
    manager.detector_model = "PISPAD23"
    session = SoftwareTriggerSession(manager)
    session.arm()
    assert session.state == "preparing" and not session.trigger()
    manager.shared_dict["software_trigger_receiver_ready"] = 1
    session.poll()
    assert session.trigger()
    complete_frame(manager, session)
    assert session.state == "preparing" and not session.trigger()
    manager.shared_dict["software_trigger_receiver_ready"] = 2
    session.poll()
    assert session.state == "armed"


def test_arm_waits_until_writer_is_ready():
    manager = manager_stub()
    manager.shared_dict["software_trigger_worker_ready"] = False
    session = SoftwareTriggerSession(manager)
    session.arm()
    assert session.state == "preparing" and not session.trigger()
    manager.shared_dict["software_trigger_worker_ready"] = True
    session.poll()
    assert session.state == "armed"


def test_preview_range_and_position_apply_to_next_frame_without_resetting_session():
    manager, session = make_session(preview=True, laser_off=True)
    assert session.trigger()
    complete_frame(manager, session)
    assert session.update_preview_geometry({"axis_start_offset_volts": [10.0, 20.0, 30.0],
                                            "axis_calibration_volts_per_step": [0.2, 0.4, 1.0],
                                            "analog_output_2_dc_volts": 1.25})
    assert manager.registers_configuration["axis_start_offset_volts"] == [10, 20, 31]
    assert manager.registers_configuration["max_frame"] == 1
    assert manager.expected_words_data_digital == (1 << 63) - 1
    assert session.completed == 1 and session.issued == 1
    assert not manager.registers_configuration["laser_1_enable"]
    assert session.trigger()
    assert manager.registers_configuration["axis_start_offset_volts"] == [10, 20, 31]
    assert manager.registers_configuration["analog_output_2_dc_volts"] == 1.25
    assert session.requested["axis_start_offset_volts"] == [1, 2, 3]
    session.restore()
    assert manager.registers_configuration["axis_start_offset_volts"] == [10, 20, 30]
    assert manager.registers_configuration["axis_calibration_volts_per_step"] == [0.2, 0.4, 1.0]


@pytest.mark.parametrize("state", ["preparing", "capturing", "draining", "complete", "error"])
def test_position_writes_are_rejected_outside_trigger_wait(state):
    manager, session = make_session(preview=True)
    session.state = state
    manager.fpga_handle.register_write_checked.reset_mock()
    assert not session.update_preview_geometry({"axis_start_offset_volts": [9, 8, 7]})
    assert session.preview_geometry["axis_start_offset_volts"] == [1, 2, 3]
    manager.fpga_handle.register_write_checked.assert_not_called()


def test_position_updates_cannot_change_dimensions_or_lasers():
    manager, session = make_session(preview=True)
    manager.fpga_handle.register_write_checked.reset_mock()
    assert not session.update_preview_geometry({"max_frame": 5, "laser_1_enable": True})
    manager.fpga_handle.register_write_checked.assert_not_called()


@pytest.mark.parametrize("state", ["preparing", "armed", "capturing", "draining", "complete"])
def test_acquisition_range_and_position_remain_locked(state):
    manager, session = make_session()
    session.state = state
    manager.fpga_handle.register_write_checked.reset_mock()
    assert not session.update_preview_geometry({"axis_start_offset_volts": [9, 8, 7],
                                                "axis_calibration_volts_per_step": [1, 2, 3],
                                                "analog_output_2_dc_volts": 1.25})
    assert session.frame_offsets() == [1, 2, 3]
    manager.fpga_handle.register_write_checked.assert_not_called()


def test_pispad23_human_wait_preserves_socket_and_normal_timeout_is_unchanged():
    import socket
    from unittest.mock import patch
    from brighteyes_mcs.acquisition.detectors.pispad23.backend import PISPAD23TcpBunchSource, DONE_SENTINEL

    for enabled in (False, True):
        shared = {"software_trigger_enabled": enabled}
        source = PISPAD23TcpBunchSource(2, 1, 20, 0, shared_dict=shared)
        connection = MagicMock()
        connection.recv.side_effect = [b"hello", socket.timeout(), b"payload" + DONE_SENTINEL]
        with patch("brighteyes_mcs.acquisition.detectors.pispad23.backend.socket.create_connection") as connect:
            connect.return_value.__enter__.return_value = connection
            if enabled:
                assert source._receive_cs_binary_payload() == b"payload"
                assert shared["software_trigger_receiver_ready"] == 1
                assert connect.call_count == 1
            else:
                with pytest.raises(socket.timeout):
                    source._receive_cs_binary_payload()
                assert "software_trigger_receiver_ready" not in shared
