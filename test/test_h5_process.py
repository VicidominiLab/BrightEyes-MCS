"""Standard frame writes preserve the existing asynchronous FPGA data path."""
import h5py
import numpy as np

from brighteyes_mcs.storage.h5 import H5ManagerProcessClient


def test_fpga_frame_writes_finish_before_the_file_is_closed(tmp_path, h5_writer):
    client = H5ManagerProcessClient(h5_writer.shared_objects["h5_command_queue"],
                                    h5_writer.shared_objects["h5_response_queue"])
    path = tmp_path / "fpga.h5"
    client.init(path)
    client.init_dataset("data", (3, 2, 1), 4, 25, np.uint16)
    first = np.arange(2 * 3 * 4 * 25, dtype=np.uint16).reshape(2, 3, 4, 25)
    client.add_to_dataset("data", first, 0, 0)
    client.add_to_dataset("data", first + 1000, 1, 0)
    client.close()
    client.shutdown()
    with h5py.File(path) as saved:
        assert saved["data"].shape == (2, 1, 2, 3, 4, 25)
        assert saved["data"].dtype == np.uint16
        np.testing.assert_array_equal(saved["data"][0, 0], first)
        np.testing.assert_array_equal(saved["data"][1, 0], first + 1000)
