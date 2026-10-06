"""Save original PI23 dwell counts independently of rolling preview pixels."""

import h5py
import numpy as np

from .h5_schema import DATA_FORMAT_VERSION


class MicroimageH5Writer:
    def __init__(self, filename, width, height, frames, repetitions, dwell_seconds,
                 *, snake=False, snake_z=False):
        if min(width, height, frames, repetitions) < 1 or dwell_seconds <= 0:
            raise ValueError("Invalid PI23 HDF5 acquisition dimensions or dwell duration")
        self.width, self.height = width, height
        self.frames, self.repetitions = frames, repetitions
        self.snake, self.snake_z = snake, snake_z
        self.frame = None
        self.saved_dwells = self.complete_frames = 0
        self.counts = np.zeros((height, width, 1, 25), dtype=np.uint32)
        self.flags = np.zeros((height, width), dtype=np.uint8)
        # Never overwrite an existing acquisition if a filename collision occurs.
        self.file = h5py.File(filename, "x")
        try:
            self.file.attrs.update(default="data", data_format_version=DATA_FORMAT_VERSION)
            self.data = self.file.create_dataset(
                "data", (repetitions, frames, height, width, 1, 25), dtype="uint32",
                chunks=(1, 1, min(height, 32), min(width, 32), 1, 25), fillvalue=0,
            )
            self.data.attrs.update(axes="repetition,z,y,x,timebin,channel", units="photon counts",
                                   timebins_per_pixel=1, dwell_seconds=dwell_seconds,
                                   integration="one complete dwell per time bin")
            self.info = self.file.create_group("pi23_microimages")
            self.info.attrs.update(complete=False, stop_reason="recording", saved_dwells=0,
                                   dwell_seconds=dwell_seconds, expected_frames=frames * repetitions,
                                   detector_channels=25, snake_walk_xy=snake, snake_walk_z=snake_z)
            shape = (repetitions, frames, height, width)
            chunks = (1, 1, min(height, 64), min(width, 64))
            self.valid = self.info.create_dataset("valid", shape, dtype="bool", chunks=chunks)
            self.pixel_flags = self.info.create_dataset("flags", shape, dtype="uint8", chunks=chunks)
            self.pixel_flags.attrs["meaning"] = "bit 0 complete dwell; bit 1 valid; bit 2 saturated"
            self.frame_complete = self.info.create_dataset("frame_complete", shape[:2], dtype="bool")
            self.frame_id = self.info.create_dataset("frame_id", shape[:2], dtype="int64", fillvalue=-1)
        except Exception:
            self.file.close()
            raise

    def consume(self, snapshot):
        if snapshot.flags & 3 != 3:
            return
        if not (0 <= snapshot.x < self.width and 0 <= snapshot.y < self.height):
            return  # Trailing synchronization dwells are not scan pixels.
        if not 0 <= snapshot.frame < self.frames * self.repetitions:
            raise ValueError("PI23 HDF5 received a frame outside the configured acquisition")
        if self.frame is not None and snapshot.frame < self.frame:
            raise ValueError("PI23 HDF5 frame order reversed")
        if snapshot.frame != self.frame:
            self._flush_frame()
            self.frame = snapshot.frame
            self.counts.fill(0)
            self.flags.fill(0)
        x = self.width - 1 - snapshot.x if self.snake and snapshot.y % 2 else snapshot.x
        if self.flags[snapshot.y, x]:
            raise ValueError("Duplicate PI23 dwell coordinate in HDF5 acquisition")
        self.counts[snapshot.y, x, 0] = snapshot.counts
        self.flags[snapshot.y, x] = snapshot.flags
        self.saved_dwells += 1

    def _flush_frame(self):
        if self.frame is None:
            return
        rep, z = divmod(self.frame, self.frames)
        if self.snake_z and rep % 2:
            z = self.frames - 1 - z
        valid = self.flags & 3 == 3
        complete = bool(valid.all())
        self.data[rep, z] = self.counts
        self.valid[rep, z] = valid
        self.pixel_flags[rep, z] = self.flags
        self.frame_id[rep, z] = self.frame
        self.frame_complete[rep, z] = complete
        self.complete_frames += int(complete)
        self.info.attrs["saved_dwells"] = self.saved_dwells
        self.file.flush()
        self.frame = None

    def close(self, *, finished=False, error=""):
        try:
            self._flush_frame()
            complete = finished and not error and self.complete_frames == self.frames * self.repetitions
            self.info.attrs.update(complete=complete, saved_dwells=self.saved_dwells,
                                   stop_reason=("error" if error else "complete" if complete else
                                                "incomplete" if finished else "stopped"), error=error)
            return complete
        finally:
            self.file.close()
