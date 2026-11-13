"""Assemble original PI dwell counts into frames for the standard MCS HDF5 writer."""

import numpy as np

from .h5 import H5Manager
from .h5_schema import DATA_FORMAT_VERSION


class MicroimageH5Writer:
    def __init__(self, filename, width, height, frames, repetitions, dwell_seconds,
                 *, snake=False, snake_z=False, manager=None):
        if min(width, height, frames, repetitions) < 1 or dwell_seconds <= 0:
            raise ValueError("Invalid PISPAD23 HDF5 acquisition dimensions or dwell duration")
        self.width, self.height = width, height
        self.frames, self.repetitions = frames, repetitions
        self.snake, self.snake_z = snake, snake_z
        self.frame = None
        self.saved_dwells = self.complete_frames = 0
        self.counts = np.zeros((height, width, 1, 25), dtype=np.uint32)
        self.flags = np.zeros((height, width), dtype=np.uint8)
        # MCS supplies its standard H5ManagerProcessClient. The direct manager
        # also supports the frame assembler outside an acquisition pipeline.
        self.manager = manager or H5Manager(filename, exclusive=True)
        try:
            if manager is not None:
                manager.init(filename, exclusive=True)
            self.manager.set_attributes("/", dict(default="data", data_format_version=DATA_FORMAT_VERSION))
            self.manager.init_dataset("data", (width, height, frames), 1, 25, np.uint32)
            self.manager.set_attributes("data", dict(
                axes="repetition,z,y,x,timebin,channel", units="photon counts",
                timebins_per_pixel=1, dwell_seconds=dwell_seconds,
                integration="one complete dwell per time bin"))
            self.manager.set_attributes("pispad23_microimages", dict(
                complete=False, stop_reason="recording", saved_dwells=0,
                dwell_seconds=dwell_seconds, expected_frames=frames * repetitions,
                detector_channels=25, snake_walk_xy=snake, snake_walk_z=snake_z))
            shape = (repetitions, frames, height, width)
            chunks = (1, 1, min(height, 64), min(width, 64))
            self.manager.create_dataset("pispad23_microimages/valid", shape, "bool", chunks=chunks)
            self.manager.create_dataset("pispad23_microimages/flags", shape, "uint8", chunks=chunks)
            self.manager.set_attributes("pispad23_microimages/flags", dict(
                meaning="bit 0 complete dwell; bit 1 valid; bit 2 saturated"))
            self.manager.create_dataset("pispad23_microimages/frame_complete", shape[:2], "bool")
            self.manager.create_dataset("pispad23_microimages/frame_id", shape[:2], "int64", fillvalue=-1)
        except Exception:
            self.manager.close()
            raise

    def consume(self, snapshot):
        if snapshot.flags & 3 != 3:
            return
        if not (0 <= snapshot.x < self.width and 0 <= snapshot.y < self.height):
            return  # Trailing synchronization dwells are not scan pixels.
        if not 0 <= snapshot.frame < self.frames * self.repetitions:
            raise ValueError("PISPAD23 HDF5 received a frame outside the configured acquisition")
        if self.frame is not None and snapshot.frame < self.frame:
            raise ValueError("PISPAD23 HDF5 frame order reversed")
        if snapshot.frame != self.frame:
            self._flush_frame()
            self.frame = snapshot.frame
            self.counts.fill(0)
            self.flags.fill(0)
        x = self.width - 1 - snapshot.x if self.snake and snapshot.y % 2 else snapshot.x
        if self.flags[snapshot.y, x]:
            raise ValueError("Duplicate PISPAD23 dwell coordinate in HDF5 acquisition")
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
        # Each acknowledged frame write is complete before its source buffer
        # is reused. Counts retain uint32 precision through the standard writer.
        self.manager.add_to_dataset("data", self.counts, rep, z, wait=True)
        for name, values in (("valid", valid), ("flags", self.flags),
                             ("frame_id", self.frame), ("frame_complete", complete)):
            self.manager.write_slice(f"pispad23_microimages/{name}", (rep, z), values)
        self.complete_frames += int(complete)
        self.manager.set_attributes("pispad23_microimages", dict(saved_dwells=self.saved_dwells))
        self.frame = None

    def close(self, *, finished=False, error=""):
        try:
            self._flush_frame()
            complete = finished and not error and self.complete_frames == self.frames * self.repetitions
            self.manager.set_attributes("pispad23_microimages", dict(complete=complete, saved_dwells=self.saved_dwells,
                                   stop_reason=("error" if error else "complete" if complete else
                                                "incomplete" if finished else "stopped"), error=error))
            return complete
        finally:
            self.manager.close()
