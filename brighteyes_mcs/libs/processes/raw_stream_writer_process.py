"""Process that streams FIFO payloads directly to raw files without conversion."""

import multiprocessing as mp
import os
import queue
import time

import numpy as np

from ..print_dec import print_dec, set_debug


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
        print_dec("RawStreamWriterProcess RUN", os.getpid())
        self.acquisition_done.clear()
        self.acquisition_almost_done.clear()

        handles = {}
        for fifo_name, filename in self.raw_output_files.items():
            folder = os.path.dirname(filename)
            if folder:
                os.makedirs(folder, exist_ok=True)
            handles[fifo_name] = open(filename, "wb", buffering=8 * 1024 * 1024)
            self.shared_dict[f"{fifo_name}_raw_filename"] = filename
            self.shared_dict[f"{fifo_name}_bytes_written"] = 0

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
                    break

            for handle in handles.values():
                handle.flush()
                os.fsync(handle.fileno())
        finally:
            for handle in handles.values():
                handle.close()

        self.acquisition_almost_done.set()
        self.acquisition_done.set()
        print_dec("RawStreamWriterProcess DONE")

    def stop(self):
        print_dec("RawStreamWriterProcess STOP")
        self.stop_event.set()
