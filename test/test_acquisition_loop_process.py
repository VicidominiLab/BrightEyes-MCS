import unittest

import numpy as np

from brighteyes_mcs.libs.processes.acquisition_loop_process import (
    aggregate_samples_by_pixel,
    build_pointer_frame_lookup,
)


class TestAcquirePreviewAggregation(unittest.TestCase):
    def test_aggregate_samples_by_pixel_collapses_timebins(self):
        shape = (4, 3, 2)
        timebins_per_pixel = 4
        frame_lookup = build_pointer_frame_lookup(timebins_per_pixel, shape)
        values = np.arange(1, 11, dtype=np.uint16)

        list_x, list_y, list_z, list_rep, grouped = aggregate_samples_by_pixel(
            pointer_start=2,
            gap=values.shape[0],
            timebinsPerPixel=timebins_per_pixel,
            shape=shape,
            values=values,
            frame_lookup=frame_lookup,
            snake_walk_z=False,
            delay=0,
            need_z=True,
        )

        np.testing.assert_array_equal(grouped, np.array([3, 18, 34], dtype=np.uint16))
        np.testing.assert_array_equal(list_x, np.array([0, 1, 2], dtype=np.int32))
        np.testing.assert_array_equal(list_y, np.array([0, 0, 0], dtype=np.int32))
        np.testing.assert_array_equal(list_z, np.zeros(3, dtype=np.int32))
        np.testing.assert_array_equal(list_rep, np.zeros(3, dtype=np.int32))

    def test_aggregate_samples_by_pixel_supports_multichannel_values(self):
        shape = (2, 2, 2)
        timebins_per_pixel = 2
        frame_lookup = build_pointer_frame_lookup(timebins_per_pixel, shape)
        values = np.array(
            [
                [1, 10, 100],
                [2, 20, 200],
                [3, 30, 300],
                [4, 40, 400],
            ],
            dtype=np.uint16,
        )

        list_x, list_y, list_z, _, grouped = aggregate_samples_by_pixel(
            pointer_start=0,
            gap=values.shape[0],
            timebinsPerPixel=timebins_per_pixel,
            shape=shape,
            values=values,
            frame_lookup=frame_lookup,
            snake_walk_z=False,
            delay=0,
            need_z=True,
        )

        np.testing.assert_array_equal(list_x, np.array([0, 1], dtype=np.int32))
        np.testing.assert_array_equal(list_y, np.array([0, 0], dtype=np.int32))
        np.testing.assert_array_equal(list_z, np.array([0, 0], dtype=np.int32))
        np.testing.assert_array_equal(
            grouped,
            np.array([[3, 30, 300], [7, 70, 700]], dtype=np.uint16),
        )


if __name__ == "__main__":
    unittest.main()
