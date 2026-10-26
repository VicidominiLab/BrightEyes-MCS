"""Finite Flare acquisition with independent reception, control and rendering."""

import logging
from contextlib import nullcontext
import queue
import socket
import threading
import time

import numpy as np

from .detectors.flare.config import check_transport, total_bins, validate_configuration, stream_parameters
from .detectors.flare.decoder import FlareDecoder
from .detectors.flare.dfd import is_dfd, validate_accepted, FlareDfdDecoder, DfdPreview
from ..hardware.flare import FlareClient, FlareError
from ..storage.flare import FlareRecording


log = logging.getLogger(__name__)


def _update_preview_image(image, sums, start_bin, bins_per_pixel):
    """Replace visited pixels, retaining the preceding frame elsewhere."""
    indices = np.arange(start_bin, start_bin + len(sums), dtype=np.uint64)
    pixel = indices // bins_per_pixel
    frame_size = image.size
    frame = pixel // frame_size
    for frame_index in np.unique(frame):
        selected = frame == frame_index
        local = pixel[selected] % frame_size
        # A TCP batch can start midway through a pixel. Clear only when its
        # first timebin arrives, then accumulate all of that pixel's bins.
        fresh = local[indices[selected] % bins_per_pixel == 0]
        image[fresh // image.shape[1], fresh % image.shape[1]] = 0
        np.add.at(image, (local // image.shape[1], local % image.shape[1]), sums[selected])


def receiver_address(settings):
    if settings.receiver_host:
        return settings.receiver_host
    # Route lookup occurs only for an explicitly selected Flare acquisition.
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as route:
        route.connect((settings.host, settings.port))
        return route.getsockname()[0]


class FlareAcquisition:
    def __init__(
        self,
        settings,
        configuration,
        *,
        filename=None,
        raw_only=False,
        on_snapshot=None,
        initial_image=None,
        live_controls=None,
        client_factory=FlareClient,
    ):
        self.settings = settings.validate()
        if settings.mode != "master":
            raise FlareError(
                "Slave acquisition is unavailable until Flare firmware supports NI external timing"
            )
        self.configuration = validate_configuration(configuration)
        self.dfd = is_dfd(self.configuration)
        self.filename = filename
        self.raw_only = raw_only
        self.on_snapshot = on_snapshot or (lambda snapshot: None)
        self.client_factory = client_factory
        self.live_controls = live_controls
        self.cancel = threading.Event()
        self.received_bytes = 0
        self._receiver_error = None
        self._eof = threading.Event()
        self._stop_receiver = threading.Event()
        self.display_channels = None
        shape = (self.configuration["lines"], self.configuration["pixels"])
        self._image = (
            np.array(initial_image, dtype=np.uint64, copy=True)
            if initial_image is not None and initial_image.shape == shape
            else np.zeros(shape, dtype=np.uint64)
        )

    def stop(self):
        # The acquisition worker owns commands. UI cancellation never blocks Qt.
        self.cancel.set()

    def run(self):
        client = self.client_factory(self.settings)
        recording = None
        decoder = None
        listener = connection = thread = None
        metadata = {
            "complete": False,
            "result": "partial",
            "configurationGUI": getattr(self, "gui_metadata", {}),
        }
        started = False
        chunks = queue.Queue(maxsize=64)
        try:
            metadata["discovery"] = client.discover()
            if self.dfd:
                client.check_acquisition_support(dfd=True)
            else:
                client.check_acquisition_support()
            client.require_idle()
            check_transport(self.configuration, client.firmware["clock_hz"], self.settings)
            if self.cancel.is_set():
                raise InterruptedError("Flare acquisition cancelled before configuration")
            # GUI writes wait in their own worker while reset/configuration runs.
            # Restore the latest requests after reset, including laser enables.
            with self.live_controls.io_lock if self.live_controls else nullcontext():
                if self.live_controls:
                    self.live_controls.begin_run()
                initial_registers = client.read_all()
                requested = dict(self.configuration)
                if self.dfd:
                    if "detector_enable" in initial_registers:
                        requested["physical_mask"] = [
                            int(initial_registers["detector_enable"]) & (0x1ffffff if requested["channels"] == 25 else 0xffffffff),
                            int(initial_registers.get("detector_enable_high", 0)) & (0 if requested["channels"] == 25 else 0x1ffff),
                        ]
                    if "detector_fpga_holdoff_cycles" in initial_registers:
                        requested["detector_fpga_holdoff_cycles"] = int(initial_registers["detector_fpga_holdoff_cycles"])
                response = client.configure(requested)
                accepted = (validate_accepted(requested, response, client.firmware["clock_hz"])
                            if self.dfd else validate_configuration(response))
                if not self.dfd and accepted != self.configuration:
                    raise FlareError("Flare accepted settings differ from the requested scan")
                detector_settings = {}
                for name in ("detector_enable", "detector_enable_high", "detector_fpga_holdoff_cycles"):
                    if not self.dfd and name in initial_registers:
                        detector_settings[name] = client.write_register(name, initial_registers[name])["value"]
                if self.live_controls and not self.dfd:
                    self.live_controls.apply(client, restore=True)
                size, dwell, packet = stream_parameters(accepted)
                metadata.update(
                    configuration=accepted,
                    firmware=dict(client.firmware),
                    registers=client.read_all(),
                    mode=self.settings.mode,
                    detector_settings=detector_settings,
                    requested_configuration=requested,
                    bin_bytes=size,
                )
            if self.filename:
                recording = FlareRecording(self.filename, accepted, raw_only=self.raw_only)
            listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            listener.bind((self.settings.bind_host, self.settings.receiver_port))
            listener.listen(1)
            listener.settimeout(0.2)
            host = receiver_address(self.settings)
            metadata["stream_settings"] = client.stream_settings(
                {
                    "host": host,
                    "port": listener.getsockname()[1],
                    "buffer_seconds": self.settings.buffer_seconds,
                    "timeout_seconds": self.settings.timeout_seconds,
                }
            )
            clock_hz = client.firmware["clock_hz"]
            inactivity = max(
                10,
                5
                + 1.25
                * min(total_bins(accepted), 32 * packet)
                * dwell
                / clock_hz,
            )

            def receive():
                nonlocal connection
                raw = None
                pending = bytearray()
                last_dispatch = time.monotonic()

                def dispatch():
                    nonlocal last_dispatch
                    if not pending:
                        return
                    try:
                        chunks.put_nowait(bytes(pending))
                    except queue.Full as error:
                        raise FlareError(
                            "Flare processing queue filled; capture is incomplete"
                        ) from error
                    pending.clear()
                    last_dispatch = time.monotonic()

                try:
                    if recording:
                        raw = open(recording.raw_path, "xb")
                    deadline = (
                        time.monotonic()
                        + self.settings.http_timeout_seconds
                        + self.settings.timeout_seconds
                    )
                    while not self._stop_receiver.is_set():
                        try:
                            connection, _ = listener.accept()
                            break
                        except socket.timeout:
                            if time.monotonic() > deadline:
                                raise TimeoutError(
                                    "Flare did not connect to the GUI listener"
                                ) from None
                    if connection is None:
                        return
                    connection.settimeout(0.05)
                    last_data = time.monotonic()
                    while not self._stop_receiver.is_set():
                        try:
                            chunk = connection.recv(262144)
                        except socket.timeout:
                            dispatch()
                            if time.monotonic() - last_data > inactivity:
                                raise TimeoutError("Flare source inactivity timeout") from None
                            continue
                        if not chunk:
                            dispatch()
                            self._eof.set()
                            break
                        last_data = time.monotonic()
                        self.received_bytes += len(chunk)
                        if raw:
                            if raw.write(chunk) != len(chunk):
                                raise OSError("Short write to the Flare raw file")
                        pending.extend(chunk)
                        if len(pending) >= 262144 or time.monotonic() - last_dispatch >= 0.05:
                            dispatch()
                except Exception as error:
                    if not self._stop_receiver.is_set():
                        self._receiver_error = error
                finally:
                    if raw:
                        try:
                            raw.close()
                        except Exception as error:
                            self._receiver_error = error

            thread = threading.Thread(target=receive, name="Flare receiver", daemon=True)
            thread.start()
            if self.cancel.is_set():
                raise InterruptedError("Flare acquisition cancelled before start")
            # An ambiguous start failure must not be retried or silently reset.
            with self.live_controls.io_lock if self.live_controls else nullcontext():
                started = True
                stream = client.command("start")
            metadata["stream"] = stream
            metadata["stream_id"] = stream["id"]
            metadata["run_id"] = client.read_register("run_id")["value"]
            if self.dfd and any(stream.get(key) != accepted[key] for key in (
                "stream_format", "record_bytes", "stream_channels", "histogram_bins", "total_records", "total_bytes",
            )):
                raise FlareError("Started Flare DFD stream disagrees with its accepted layout")
            if recording:
                recording.checkpoint(metadata)
            decoder = (FlareDfdDecoder if self.dfd else FlareDecoder)(accepted, metadata["run_id"])
            image = self._image
            dfd_preview = DfdPreview(accepted, image) if self.dfd else None
            fingerprint = np.zeros(accepted["channels"], dtype=np.uint64)
            displayed_channels = self.display_channels
            trace = []
            expected_bytes = total_bins(accepted) * size
            last_snapshot = last_poll = 0.0
            status = {}
            while True:
                if self.cancel.is_set():
                    raise InterruptedError("Flare acquisition cancelled")
                if self._receiver_error:
                    raise self._receiver_error
                try:
                    chunk = chunks.get(timeout=0.05)
                except queue.Empty:
                    if not thread.is_alive() and chunks.empty():
                        break
                    chunk = b""
                index = decoder.index
                counts = decoder.feed(chunk)
                if recording:
                    recording.append(index, counts)
                if len(counts):
                    selection = self.display_channels
                    if selection != displayed_channels:
                        image.fill(0)
                        displayed_channels = selection
                    sums = dfd_preview.update(counts, index, selection) if self.dfd else (
                        counts.sum(axis=1, dtype=np.uint64)
                        if selection is None
                        else counts[:, selection].sum(axis=1, dtype=np.uint64)
                    )
                    if not self.dfd:
                        _update_preview_image(image, sums, index, accepted["bins_per_pixel"])
                    fingerprint += (counts[:, :, :accepted["channels"]].sum(axis=(0, 1), dtype=np.uint64)
                                    if self.dfd else counts.sum(axis=0, dtype=np.uint64))
                    trace.extend((sums.astype(float) * clock_hz / dwell).tolist())
                    trace = trace[-3000:]
                now = time.monotonic()
                if now - last_poll >= 0.2:
                    status = client.status()
                    last_poll = now
                    active = status.get("stream") or {}
                    if active.get("id") != stream["id"]:
                        raise FlareError("Flare stream identity changed during acquisition")
                    if any(active.get(key, 0) for key in ("stream_error", "acquisition_error")):
                        raise FlareError(f"Flare delivery failed: {active}")
                if now - last_snapshot >= 0.1:
                    self.on_snapshot(
                        {
                            "image": image.copy(),
                            "fingerprint": fingerprint.copy(),
                            "trace": np.asarray(trace),
                            "bins": decoder.index,
                            "total_bins": decoder.expected_bins,
                            "receiver_bytes": self.received_bytes,
                            "expected_bytes": expected_bytes,
                            "status": status,
                            "bin_seconds": dwell / clock_hz,
                            **(dfd_preview.snapshot() if self.dfd else {}),
                        }
                    )
                    last_snapshot = now
            if not self._eof.is_set() or self.received_bytes != expected_bytes:
                raise FlareError("Flare EOF/byte count validation failed")
            decoder.finish()
            deadline = time.monotonic() + self.settings.http_timeout_seconds
            while True:
                status = client.status()
                final = status.get("stream") or {}
                if (
                    final.get("complete")
                    or time.monotonic() >= deadline
                    or final.get("stream_error")
                    or final.get("acquisition_error")
                ):
                    break
                if self.cancel.wait(0.05):
                    raise InterruptedError("Flare acquisition cancelled")
            metadata["final_status"] = status
            if self.dfd:
                metadata["dfd_fault_flags"] = client.read_register("dfd_fault_flags")["value"]
                if metadata["dfd_fault_flags"]:
                    raise FlareError(f"Flare DFD fault flags: {metadata['dfd_fault_flags']}")
            if (
                final.get("id") != stream["id"]
                or final.get("complete") is not True
                or any(final.get(k, 0) for k in ("stream_error", "acquisition_error"))
                or any(status["dma"].get(k, 0) for k in ("error", "pl_error"))
            ):
                raise FlareError(
                    "Flare final service status does not confirm successful acquisition"
                )
            self.on_snapshot(
                {
                    "image": image.copy(),
                    "fingerprint": fingerprint.copy(),
                    "trace": np.asarray(trace),
                    "bins": decoder.index,
                    "total_bins": decoder.expected_bins,
                    "receiver_bytes": self.received_bytes,
                    "expected_bytes": expected_bytes,
                    "status": status,
                    "bin_seconds": dwell / clock_hz,
                    **(dfd_preview.snapshot() if self.dfd else {}),
                }
            )
            metadata.update(complete=True, result="complete", validated_bins=decoder.index)
        except Exception as error:
            metadata.update(
                error=str(error),
                result="cancelled" if isinstance(error, InterruptedError) else "partial",
            )
            if started:
                try:
                    # Save observable evidence before stop removes the retained stream object.
                    metadata["final_status"] = client.status()
                    current = metadata["final_status"].get("stream") or {}
                    if (
                        isinstance(error, InterruptedError)
                        and metadata.get("stream_id") == current.get("id")
                        and metadata.get("stream_id")
                    ):
                        with self.live_controls.io_lock if self.live_controls else nullcontext():
                            metadata["stop_result"] = client.command("stop")
                        metadata["after_stop_status"] = client.status()
                    elif current.get("id"):
                        metadata["recovery_required"] = True
                except Exception as recovery_error:
                    metadata["recovery_error"] = str(recovery_error)
            log.warning("Flare acquisition failed: %s", error)
        finally:
            self._stop_receiver.set()
            if connection:
                try:
                    connection.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                connection.close()
            if listener:
                listener.close()
            if thread:
                thread.join(timeout=2)
                if thread.is_alive():
                    metadata.update(
                        complete=False, result="partial", error="Flare receiver did not close"
                    )
            if self._receiver_error:
                metadata.update(complete=False, result="partial")
                metadata.setdefault("error", str(self._receiver_error))
            metadata["receiver_bytes"] = self.received_bytes
            if decoder is not None:
                metadata["validated_bins"] = decoder.index
                if self.dfd:
                    metadata["validated_records"] = decoder.index
                    metadata["partial_records"] = list(decoder.partial_records)
            if self.live_controls:
                with self.live_controls.io_lock:
                    metadata["live_register_updates"] = self.live_controls.events()
            if recording:
                try:
                    metadata["raw_bytes_on_disk"] = (
                        recording.raw_path.stat().st_size if recording.raw_path.exists() else 0
                    )
                    if metadata["raw_bytes_on_disk"] != self.received_bytes:
                        metadata.update(complete=False, result="partial")
                        metadata.setdefault(
                            "error", "Flare raw file size does not match received bytes"
                        )
                    recording.finish(metadata)
                    metadata["saved_filename"] = str(
                        recording.metadata_path if self.raw_only else recording.path
                    )
                except Exception as error:
                    metadata.update(
                        complete=False,
                        result="partial",
                        error=f"Flare file finalization failed: {error}",
                    )
            client.close()
        return metadata
