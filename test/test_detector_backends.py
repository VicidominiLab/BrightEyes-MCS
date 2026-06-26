import unittest

import numpy as np

from brighteyes_mcs.libs.detector_backends import (
    DETECTOR_PI_23,
    DETECTOR_SPAD_ARRAY,
    Pi23RandomBunchSource,
    Pi23RawBunch,
    Pi23TcpBunchSource,
    detector_uses_nifpga_fifo,
    normalize_detector_model,
    pi23_decode_raw_bunch_to_spad_preview_words,
)


class Counter:
    def __init__(self, value):
        self.value = value


class TestDetectorBackends(unittest.TestCase):
    def make_pi23_tcp_source(self, scan_x=2, scan_y=2, scan_frames=1):
        return Pi23TcpBunchSource(
            fifo_chuck_size_digital=Counter(2),
            fifo_chuck_size_analog=Counter(0),
            expected_words_data_digital=Counter(scan_x * scan_y * scan_frames * 2),
            expected_words_data_analog=Counter(0),
            digital_words_per_sample=2,
            digital_output_channels=3,
            scan_x=scan_x,
            scan_y=scan_y,
            scan_frames=scan_frames,
            timebins_per_pixel=1,
            dwell_us=0.0,
            external_frame=1,
            detector_channels=3,
            command_scan_x_extra=1,
            command_scan_y_extra=1,
        )

    def test_detector_model_normalization(self):
        self.assertEqual(normalize_detector_model(DETECTOR_PI_23), DETECTOR_PI_23)
        self.assertEqual(normalize_detector_model("unknown"), DETECTOR_SPAD_ARRAY)
        self.assertTrue(detector_uses_nifpga_fifo(DETECTOR_SPAD_ARRAY))
        self.assertFalse(detector_uses_nifpga_fifo(DETECTOR_PI_23))

    def test_pi23_tcp_command_uses_compensated_scan_dimensions(self):
        source = self.make_pi23_tcp_source(scan_x=100, scan_y=200)

        self.assertEqual(source._format_cs_command(), "CS,0.0,1,101,201,1\n")

    def test_pi23_tcp_payload_crop_discards_compensation_row_and_column(self):
        source = self.make_pi23_tcp_source(scan_x=2, scan_y=2)
        command_planes = np.arange(1 * 3 * 3 * 3, dtype=np.uint8).reshape(1, 3, 3, 3)

        planes = source._payload_to_planes(command_planes.tobytes(order="C"))
        counts = source._planes_to_sample_counts(planes)

        np.testing.assert_array_equal(planes, command_planes[:, :, :2, :2])
        np.testing.assert_array_equal(
            counts,
            command_planes[:, :, :2, :2].transpose(0, 2, 3, 1).reshape(4, 3),
        )

    def test_pi23_tcp_payload_accepts_already_requested_dimensions(self):
        source = self.make_pi23_tcp_source(scan_x=2, scan_y=2)
        requested_planes = np.arange(1 * 3 * 2 * 2, dtype=np.uint8).reshape(1, 3, 2, 2)

        planes = source._payload_to_planes(requested_planes.tobytes(order="C"))

        np.testing.assert_array_equal(planes, requested_planes)

    def test_pi23_random_source_returns_raw_bunches_until_expected_words(self):
        source = Pi23RandomBunchSource(
            fifo_chuck_size_digital=Counter(4),
            fifo_chuck_size_analog=Counter(2),
            expected_words_data_digital=Counter(20),
            expected_words_data_analog=Counter(0),
            digital_words_per_sample=2,
            packet_chunk_multiplier=(1, 3),
            seed=1,
        )
        source.start()

        first_bunch = source.read_bunch("FIFO")
        self.assertIsInstance(first_bunch, Pi23RawBunch)
        self.assertIsInstance(first_bunch.payload, dict)
        self.assertIn("channel_counts", first_bunch.payload)
        self.assertNotIsInstance(first_bunch, np.ndarray)

        first_packet = pi23_decode_raw_bunch_to_spad_preview_words(
            first_bunch,
            digital_words_per_sample=2,
        )
        self.assertEqual(first_packet.dtype, np.uint64)
        self.assertGreater(first_packet.shape[0], 0)
        self.assertEqual(first_packet.shape[0] % 4, 0)

        received = first_packet.shape[0]
        while True:
            bunch = source.read_bunch("FIFO")
            if bunch is None:
                break
            packet = pi23_decode_raw_bunch_to_spad_preview_words(
                bunch,
                digital_words_per_sample=2,
            )
            received += packet.shape[0]

        self.assertEqual(received, 20)


if __name__ == "__main__":
    unittest.main()
