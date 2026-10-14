"""One persistent acquisition, driven by independent single-frame FPGA runs."""

from copy import deepcopy
import time

from .detectors.models import detector_uses_pispad23_pipeline


class SoftwareTriggerSession:
    def __init__(self, manager, *, preview=False, laser_off=False):
        self.manager = manager
        self.requested = deepcopy(manager.registers_configuration)
        self.frames = int(self.requested["max_frame"])
        self.repetitions = int(self.requested["max_repetition"]) - 1
        if self.frames < 1 or self.repetitions < 1:
            raise ValueError("Software triggering requires positive frame and repetition counts.")
        self.preview = preview
        self.laser_off = laser_off
        self.total = None if preview else self.frames * self.repetitions
        self.completed = 0
        self.issued = 0
        self.state = "preparing"
        self.timestamps = []
        self.preview_geometry = {
            "axis_start_offset_volts": list(self.requested["axis_start_offset_volts"]),
            "axis_calibration_volts_per_step": list(self.requested["axis_calibration_volts_per_step"]),
        }
        self.error = ""
        self.deadline = None
        self.started_at = None
        self.needs_receiver_ready = detector_uses_pispad23_pipeline(manager.detector_model)
        self.lasers = {
            f"laser_{i}_enable": bool(self.requested.get(f"laser_{i}_enable", False))
            for i in range(1, 5)
        }

    def prepare(self):
        # max_repetition includes the firmware's terminal repetition.
        registers = {"max_frame": 1, "max_repetition": 2,
                     "slave_mode_enable": False, "start_command": False,
                     "stop_command": False, "z_snake_scan_enable": False}
        if self.laser_off:
            registers.update(laser_off_after_measurement_enable=True,
                             wait_laser_first_time_only_enable=False)
        self.manager.setRegistersDict(registers)
        if self.laser_off:
            self.lasers_off()

    def lasers_off(self):
        # Disable forced pulsing before the individual laser enables.
        self.manager.setRegistersDict({"laser_force_pulsing_enable": False})
        self.manager.setRegistersDict(dict.fromkeys(self.lasers, False))

    def arm(self):
        if self.state != "preparing":
            return
        if not self.manager.shared_dict.get("software_trigger_worker_ready", False):
            return
        if (not self.needs_receiver_ready or
                self.manager.shared_dict.get("software_trigger_receiver_ready", 0) > self.issued):
            self.state = "armed"

    def frame_offsets(self):
        index = self.completed % self.frames
        repetition = self.completed // self.frames
        if self.requested.get("z_snake_scan_enable") and repetition % 2:
            index = self.frames - 1 - index
        geometry = self.preview_geometry if self.preview else self.requested
        offsets = list(geometry["axis_start_offset_volts"])
        offsets[2] += index * geometry["axis_calibration_volts_per_step"][2]
        return offsets

    def update_preview_geometry(self, registers):
        """Change preview range/position between frames without changing sample counts."""
        if not self.preview or self.state != "armed":
            return False
        allowed = {"axis_start_offset_volts", "axis_calibration_volts_per_step"} | {
            f"analog_output_{channel}_dc_volts" for channel in range(8)
        }
        if not registers or not set(registers).issubset(allowed):
            return False
        previous = deepcopy(self.preview_geometry)
        self.preview_geometry.update(deepcopy(registers))
        hardware = dict(registers)
        if set(hardware) & {"axis_start_offset_volts", "axis_calibration_volts_per_step"}:
            hardware["axis_start_offset_volts"] = self.frame_offsets()
        try:
            self.manager.setRegistersDict(hardware)
        except Exception:
            self.preview_geometry = previous
            raise
        return True

    def trigger(self):
        if self.state != "armed":
            return False
        self.state = "capturing"  # Reject repeated clicks before touching hardware.
        try:
            self.manager.quick_reset_fpga()
            offsets = self.frame_offsets()
            self.manager.setRegistersDict({"axis_start_offset_volts": offsets})
            if self.laser_off:
                self.manager.setRegistersDict(self.lasers)
                self.manager.setRegistersDict({"laser_force_pulsing_enable": bool(
                    self.requested.get("laser_force_pulsing_enable", False))})
            self.manager.setRegistersDict({"stop_command": False, "start_command": False})
            self.manager.setRegistersDict({"start_command": True})
            self.manager.setRegistersDict({"start_command": False})
            self.issued += 1
            self.timestamps.append(time.time())
            self.started_at = time.monotonic()
            r = self.requested
            samples = (r["max_pixel"] * r["max_line"] * r["max_time_bins_per_pixel"]
                       * r["max_circular_point"] * r["max_circular_repetition"])
            duration = (samples * r["time_bin_dwell_cycles"]
                        + r.get("wait_laser_startup_cycles", 0)
                        + r.get("wait_post_frame_cycles", 0)) / (self.manager.clock_base * 1e6)
            # The wait for a human trigger has no timeout. Only an issued frame does.
            self.deadline = self.started_at + max(30.0, duration * 3 + 10)
            return True
        except Exception as error:
            self.state = "error"
            self.error = str(error)
            raise

    def received_frames(self):
        counts = []
        for fifo in self.manager.activated_fifos_list:
            if self.manager.raw_stream_mode:
                counts.append(self.manager.loc_acquired[fifo].value //
                              self.manager.getExpectedFifoElementsPerFrame(fifo))
            else:
                counts.append(self.manager.shared_dict.get(f"software_trigger_frames_{fifo}", 0))
        return min(counts, default=0)

    def poll(self):
        if self.state == "preparing":
            self.arm()
            return
        if self.state not in ("capturing", "draining"):
            return
        idle = self.manager.check_fpga_alive() == 0
        if self.received_frames() > self.issued:
            self.state = "error"
            self.error = "The FPGA delivered more than one frame for a software trigger."
            raise RuntimeError(self.error)
        if idle and self.state == "capturing":
            self.state = "draining"
            if self.laser_off:
                self.lasers_off()
        if idle and self.received_frames() >= self.issued:
            self.completed = self.issued
            if self.total == self.completed:
                self.state = "complete"
            else:
                self.state = "preparing"
                self.arm()
        elif time.monotonic() > self.deadline:
            self.error = "Triggered frame did not finish on the FPGA and all enabled data streams."
            self.state = "error"
            raise TimeoutError(self.error)

    def metadata(self):
        completed = min(self.issued, self.received_frames())
        return {
            "enabled": True, "frames_requested": self.total or 0,
            "frames_triggered": self.issued, "frames_completed": completed,
            "complete": self.total == completed and not self.error,
            "laser_off_between_frames": self.laser_off,
            "trigger_timestamps_unix": self.timestamps, "error": self.error,
        }

    def restore(self):
        # Restore only controls overridden by this mode, never an old command edge.
        names = ("max_frame", "max_repetition", "slave_mode_enable", "z_snake_scan_enable",
                 "axis_start_offset_volts")
        if self.laser_off:
            names += ("laser_off_after_measurement_enable", "wait_laser_first_time_only_enable")
        registers = {name: self.requested.get(name, False) for name in names}
        if self.preview:
            registers.update(self.preview_geometry)
        self.manager.setRegistersDict(registers)
        # With inter-frame gating selected, leave outputs off after Stop as well.
        # The GUI retains the user's laser selection for the next session.
        if self.laser_off and self.manager.is_connected:
            self.lasers_off()
