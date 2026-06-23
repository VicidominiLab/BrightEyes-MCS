"""PI23 raw-bunch stream writer scaffold."""

import multiprocessing as mp
import os
import pickle
import queue
import struct
import traceback

import numpy as np

from ...print_debug import print_debug, set_debug


class Pi23RawStreamWriterProcess(mp.Process):
    """Write PI23-native raw bunches without converting them to SPAD FIFO words."""

    FORMAT_VERSION = "pi23_pickle_bunch_v0"

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
        digital_words_per_sample=2,
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
        self.digital_words_per_sample = max(1, int(digital_words_per_sample))
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

    def _bunch_words(self, fifo_name, raw_bunch):
        if fifo_name == "FIFOAnalog":
            return int(raw_bunch.sample_count)
        return int(raw_bunch.sample_count) * self.digital_words_per_sample

    def _expected_bytes(self, fifo_name):
        return 0

    def _update_progress(self, fifo_name, packet_words, packet_bytes):
        self.loc_acquired[fifo_name].value += packet_words
        self.loc_previewed[fifo_name].value = self.loc_acquired[fifo_name].value
        self.last_preprocessed_len[fifo_name].value = packet_words
        self.shared_dict["last_packet_size"] = packet_words
        bytes_key = f"{fifo_name}_bytes_written"
        self.shared_dict[bytes_key] = self.shared_dict.get(bytes_key, 0) + packet_bytes

        expected_frame_words = self.expected_words_per_frame[fifo_name]
        current_frame = 0
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

    def _write_bunch(self, handle, raw_bunch):
        payload = pickle.dumps(raw_bunch, protocol=pickle.HIGHEST_PROTOCOL)
        handle.write(struct.pack("<Q", len(payload)))
        handle.write(payload)
        return len(payload) + 8

    def run(self):
        print_debug("Pi23RawStreamWriterProcess RUN", os.getpid())
        self.acquisition_done.clear()
        self.acquisition_almost_done.clear()
        self.shared_dict["raw_writer_error"] = ""
        self.shared_dict["raw_writer_stop_reason"] = "running"
        self.shared_dict["pi23_raw_stream_format"] = self.FORMAT_VERSION

        handles = {}
        for fifo_name, filename in self.raw_output_files.items():
            folder = os.path.dirname(filename)
            if folder:
                os.makedirs(folder, exist_ok=True)
            handles[fifo_name] = open(filename, "wb", buffering=8 * 1024 * 1024)
            self.shared_dict[f"{fifo_name}_raw_filename"] = filename
            self.shared_dict[f"{fifo_name}_bytes_written"] = 0
            self.shared_dict[f"{fifo_name}_expected_words"] = int(self.expected_words[fifo_name])
            self.shared_dict[f"{fifo_name}_expected_bytes"] = 0

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
                        raw_bunch, _sample_count = payload
                        packet_words = self._bunch_words(fifo_name, raw_bunch)
                        if packet_words <= 0:
                            continue
                        self.received_any_packet[fifo_name] = True
                        packet_bytes = self._write_bunch(handles[fifo_name], raw_bunch)
                        self._update_progress(fifo_name, packet_words, packet_bytes)

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
            print_debug("Pi23RawStreamWriterProcess ERROR", error_text)
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
        print_debug("Pi23RawStreamWriterProcess DONE")

    def stop(self):
        print_debug("Pi23RawStreamWriterProcess STOP")
        self.stop_event.set()

