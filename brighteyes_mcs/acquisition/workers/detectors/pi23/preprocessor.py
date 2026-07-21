"""PI23 preprocessing scaffold."""

import multiprocessing as mp
import os
import queue

import numpy as np

from ....detectors.pi23.backend import (
    pi23_decode_raw_bunch_to_spad_preview_words,
    pi23_debug,
)
from brighteyes_mcs.logging_setup import logger, set_debug


class Pi23DataPreProcess(mp.Process):
    """
    Decode PI23-native raw bunches into the shared preview/acquisition stream.

    The output queue names intentionally remain ``FIFO`` and ``FIFOAnalog`` for
    now because the existing preview/H5 writer consumes those stream names.
    """

    def __init__(
        self,
        queue_in,
        dict_of_shared_loc,
        last_preprocessed_len,
        dict_of_queue_array_out,
        dict_of_dtype_queue_array_out,
        digital_words_per_sample=2,
        debug=False,
    ):
        super().__init__()
        self.daemon = True
        set_debug(debug)
        self.queue_in = queue_in
        self.dict_of_shared_loc = dict_of_shared_loc
        self.last_preprocessed_len = last_preprocessed_len
        self.dict_of_queue_array_out = dict_of_queue_array_out
        self.dict_of_dtype_queue_array_out = dict_of_dtype_queue_array_out
        self.digital_words_per_sample = digital_words_per_sample
        self.debug = bool(debug)
        self.stop_event = mp.Event()

    def run(self):
        logger.debug("%s %s", "Pi23DataPreProcess RUN - PID:", os.getpid())
        while not self.stop_event.is_set():
            try:
                dict_from_queue = self.queue_in.get(timeout=0.1)
            except queue.Empty:
                continue

            for fifo_name, payload in dict_from_queue.items():
                raw_bunch, _sample_count = payload
                try:
                    decoded = pi23_decode_raw_bunch_to_spad_preview_words(
                        raw_bunch,
                        digital_words_per_sample=self.digital_words_per_sample,
                    )
                except Exception as exc:
                    logger.debug("%s %s", "Pi23DataPreProcess decode error", repr(exc))
                    continue
                if decoded.size == 0:
                    continue
                logger.debug("%s %s %s %s %s %s", "Pi23DataPreProcess decoded", fifo_name, "samples", raw_bunch.sample_count, "words", decoded.size)
                pi23_debug(
                    "preprocess decoded",
                    fifo_name,
                    f"samples={raw_bunch.sample_count}",
                    f"words={decoded.size}",
                    enabled=self.debug,
                )
                decoded = np.asarray(
                    decoded,
                    dtype=self.dict_of_dtype_queue_array_out[fifo_name],
                )
                self.dict_of_queue_array_out[fifo_name].put(decoded)
                decoded_len = int(decoded.shape[0])
                self.dict_of_shared_loc[fifo_name].value += decoded_len
                self.last_preprocessed_len[fifo_name].value = decoded_len

    def stop(self):
        logger.debug("Pi23DataPreProcess STOP")
        self.stop_event.set()
        self.terminate()

