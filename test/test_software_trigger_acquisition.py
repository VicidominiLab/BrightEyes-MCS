"""Exercise real acquisition workers and storage across separately triggered frames."""

import multiprocessing as mp
import time
from unittest.mock import MagicMock, patch

import h5py
import numpy as np
import pytest

from brighteyes_mcs.acquisition.manager import McsManager
from brighteyes_mcs.acquisition.software_trigger import SoftwareTriggerSession
from test.test_software_trigger import registers


def wait_until(predicate, manager, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        for name in ("preview", "raw_writer"):
            worker = manager.process_supervisor.get(name)
            assert worker is None or worker.exitcode in (None, 0), (name, worker.exitcode)
        time.sleep(0.02)
    pytest.fail(f"Timed out waiting for frame; shared state: {dict(manager.shared_dict)}")


@pytest.mark.parametrize("preview,raw,channels", [(False, False, 25), (False, False, 49),
                                                (True, False, 25), (False, True, 25)])
def test_separate_triggers_share_workers_and_one_output(tmp_path, preview, raw, channels):
    manager = McsManager()
    incoming = mp.Queue()
    manager.fpga_handle = MagicMock()
    manager.fpga_handle.configuration = {"queueFifoRead": incoming}
    manager.fpga_handle.register_read_all.return_value = {}
    manager.is_connected = True
    manager.registers_configuration = registers()
    manager.registers_configuration.update(max_frame=2, max_repetition=3)
    manager.quick_reset_fpga = MagicMock()
    manager.check_fpga_alive = MagicMock(return_value=0)
    manager.set_spad_channels(channels)
    manager.set_DFD_nbins(81)
    manager.set_preview_buffer_capacity_samples(64)
    manager.setActivatedFifo(["stream_out_main", "stream_out_aux"])
    manager.activateShowPreview(True)
    manager.shared_dict.update(channel="Sum", activate_autocorrelation=False, activate_trace=False)
    manager.set_filename_h5(str(tmp_path / "triggered.h5"))
    manager.set_do_not_save(preview)
    manager.raw_stream_mode = raw
    manager.raw_output_files = {fifo: str(tmp_path / (fifo + ".raw"))
                                for fifo in manager.activated_fifos_list} if raw else {}
    session = SoftwareTriggerSession(manager, preview=preview)
    manager.software_trigger_session = session
    session.prepare()
    packets = {fifo: [] for fifo in manager.activated_fifos_list}
    try:
        # Inject preprocessed packets for HDF5, native packets for RAW. The
        # real processing/writer processes still run in separate interpreters.
        with patch("brighteyes_mcs.acquisition.detectors.spad.pipeline.SpadDetectorPipeline.make_data_preprocess",
                   return_value=None):
            manager.run()
        wait_until(lambda: manager.shared_dict.get("software_trigger_worker_ready"), manager)
        session.arm()
        worker = manager.raw_writer_process if raw else manager.previewProcess
        pid = worker.pid
        frame_count = 5 if preview else 4
        for frame in range(frame_count):
            assert session.trigger()
            assert not session.trigger()
            for fifo in manager.activated_fifos_list:
                size = manager.getExpectedFifoElementsPerFrame(fifo)
                packet = np.full(size, frame + 1 if raw else 0, dtype=np.uint64)
                packets[fifo].append(packet)
                if raw:
                    incoming.put({fifo: [packet, size]})
                else:
                    # FIFO chunks contain whole samples; split the last sample
                    # into a separate packet so completion cannot assume one chunk.
                    sample_words = (2 if channels == 25 else 8) if fifo == "stream_out_main" else 1
                    manager.data_queue[fifo].put(packet[:-sample_words])
                    manager.data_queue[fifo].put(packet[-sample_words:])
            wait_until(lambda frame=frame: session.received_frames() == frame + 1, manager)
            session.poll()
            assert session.completed == frame + 1
            assert worker.pid == pid
            if frame < frame_count - 1:
                assert session.state == "armed"
                assert not manager.acquisition_is_done()
                time.sleep(0.15)  # An idle gap must not close the writer.
        if preview:
            assert session.state == "armed" and worker.is_alive()
            assert not (tmp_path / "triggered.h5").exists()
        else:
            assert session.state == "complete"
            wait_until(manager.acquisition_is_done, manager)
            if raw:
                for fifo, filename in manager.raw_output_files.items():
                    np.testing.assert_array_equal(np.fromfile(filename, dtype=np.uint64),
                                                  np.concatenate(packets[fifo]))
            else:
                assert list(tmp_path.glob("*.h5")) == [tmp_path / "triggered.h5"]
                with h5py.File(manager.filenameh5) as output:
                    assert output["data"].shape == (2, 2, 2, 2, 2, channels)
                    assert output["data_analog"].shape == (2, 2, 2, 2, 2, 2)
    finally:
        manager.stopPreview()
        manager.stopAcquisition()
        incoming.close()
        manager.mp_manager.shutdown()
