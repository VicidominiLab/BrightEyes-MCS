"""Process that streams FIFO payloads directly to raw files without conversion."""

import multiprocessing as mp
import os
import queue
import time
import traceback

import numpy as np

from ..print_debug import print_debug, set_debug


class RawStreamWriterProcess(mp.Process):
    def __init__(
        self,
        queue_in,
        active_fifos,
        raw_output_files,
        loc_acquired,
        loc_previewed,
        last_preprocessed_len,
        acquisition_done,
        acquisition_almost_done,
        shared_dict,
        debug=False,
    ):
        super().__init__()
        self.daemon = True
        set_debug(debug)

        self.queue_in = queue_in
        self.active_fifos = list(active_fifos)
        self.raw_output_files = dict(raw_output_files)
        self.loc_acquired = loc_acquired
        self.loc_previewed = loc_previewed
        self.last_preprocessed_len = last_preprocessed_len
        self.acquisition_done = acquisition_done
        self.acquisition_almost_done = acquisition_almost_done
        self.shared_dict = shared_dict

        self.stop_event = mp.Event()

        self.expected_words = {
            "FIFO": shared_dict["expected_words_data_digital"],
            "FIFOAnalog": shared_dict["expected_words_data_analog"],
        }
        self.expected_words_per_frame = {
            "FIFO": shared_dict["expected_words_data_per_frame_digital"],
            "FIFOAnalog": shared_dict["expected_words_data_per_frame_analog"],
        }
        self.shape = shared_dict["shape"]
        self.received_any_packet = {fifo_name: False for fifo_name in self.active_fifos}

    def _expected_bytes(self, fifo_name):
        return int(self.expected_words[fifo_name]) * np.dtype(np.uint64).itemsize

    def _update_progress(self, fifo_name, packet_words, packet_bytes):
        self.loc_acquired[fifo_name].value += packet_words
        self.loc_previewed[fifo_name].value = self.loc_acquired[fifo_name].value
        self.last_preprocessed_len[fifo_name].value = packet_words
        self.shared_dict["last_packet_size"] = packet_words

        bytes_key = f"{fifo_name}_bytes_written"
        self.shared_dict[bytes_key] = self.shared_dict.get(bytes_key, 0) + packet_bytes

        current_frame = 0
        expected_frame_words = self.expected_words_per_frame[fifo_name]
        if expected_frame_words > 0:
            current_frame = self.loc_acquired[fifo_name].value // expected_frame_words

        current_z = current_frame % self.shape[2] if self.shape[2] else 0
        current_rep = current_frame // self.shape[2] if self.shape[2] else 0

        if fifo_name == "FIFO":
            self.shared_dict["current_z_digital"] = current_z
            self.shared_dict["current_rep_digital"] = current_rep
        elif fifo_name == "FIFOAnalog":
            self.shared_dict["current_z_analog"] = current_z
            self.shared_dict["current_rep_analog"] = current_rep

    def run(self):
        print_debug("RawStreamWriterProcess RUN", os.getpid())
        self.acquisition_done.clear()
        self.acquisition_almost_done.clear()
        self.shared_dict["raw_writer_error"] = ""
        self.shared_dict["raw_writer_stop_reason"] = "running"

        handles = {}
        for fifo_name, filename in self.raw_output_files.items():
            folder = os.path.dirname(filename)
            if folder:
                os.makedirs(folder, exist_ok=True)
            handles[fifo_name] = open(filename, "wb", buffering=8 * 1024 * 1024)
            self.shared_dict[f"{fifo_name}_raw_filename"] = filename
            self.shared_dict[f"{fifo_name}_bytes_written"] = 0
            self.shared_dict[f"{fifo_name}_expected_words"] = int(self.expected_words[fifo_name])
            self.shared_dict[f"{fifo_name}_expected_bytes"] = self._expected_bytes(fifo_name)

        idle_after_stop = 0
        try:
            while True:
                try:
                    dict_from_queue = self.queue_in.get(timeout=0.1)
                    idle_after_stop = 0
                except queue.Empty:
                    dict_from_queue = None
                    if self.stop_event.is_set():
                        idle_after_stop += 1
                    else:
                        # Only auto-complete after the writer has observed valid data
                        # from every active FIFO. Otherwise a zero/invalid expected size
                        # at startup could mark the acquisition as done immediately.
                        completed = bool(self.active_fifos) and all(
                            self.expected_words[fifo_name] > 0
                            and self.received_any_packet[fifo_name]
                            and self.loc_acquired[fifo_name].value >= self.expected_words[fifo_name]
                            for fifo_name in self.active_fifos
                        )
                        if completed:
                            idle_after_stop += 1
                            self.shared_dict["raw_writer_stop_reason"] = "expected_words_reached"

                if dict_from_queue is not None:
                    for fifo_name, payload in dict_from_queue.items():
                        if fifo_name not in handles:
                            continue
                        data, packet_words = payload
                        array = np.asarray(data)
                        if packet_words <= 0 or array.size == 0:
                            continue
                        self.received_any_packet[fifo_name] = True
                        handles[fifo_name].write(array.tobytes(order="C"))
                        self._update_progress(fifo_name, packet_words, array.nbytes)

                try:
                    queue_depth = self.queue_in.qsize()
                except Exception:
                    queue_depth = 0
                self.shared_dict["FIFO_status"] = queue_depth if "FIFO" in self.active_fifos else 0
                self.shared_dict["FIFOAnalog_status"] = queue_depth if "FIFOAnalog" in self.active_fifos else 0

                if idle_after_stop >= 3:
                    if self.stop_event.is_set():
                        self.shared_dict["raw_writer_stop_reason"] = "stop_requested"
                    break

            for handle in handles.values():
                handle.flush()
                os.fsync(handle.fileno())
        except Exception:
            error_text = traceback.format_exc()
            self.shared_dict["raw_writer_error"] = error_text
            self.shared_dict["raw_writer_stop_reason"] = "error"
            print_debug("RawStreamWriterProcess ERROR", error_text)
        finally:
            for handle in handles.values():
                handle.close()

            for fifo_name, filename in self.raw_output_files.items():
                try:
                    self.shared_dict[f"{fifo_name}_actual_bytes_on_disk"] = os.path.getsize(filename)
                except OSError:
                    self.shared_dict[f"{fifo_name}_actual_bytes_on_disk"] = 0

        self.acquisition_almost_done.set()
        self.acquisition_done.set()
        print_debug("RawStreamWriterProcess DONE")

    def stop(self):
        print_debug("RawStreamWriterProcess STOP")
        self.stop_event.set()

