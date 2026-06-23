"""PI23 detector receiver scaffold."""

import multiprocessing as mp
import os
from time import sleep

import psutil

from ..detector_backends import Pi23RandomBunchSource
from ..print_debug import print_debug, set_debug


class Pi23ReceiverProcess(mp.Process):
    """
    Receive PI23-native raw bunches.

    The simulator is intentionally isolated here. When the real PI23 detector
    arrives, replace the source hook without touching the SPAD FIFO reader.
    """

    def __init__(
        self,
        queue_out,
        active_fifos,
        start_event,
        fifo_chuck_size_digital,
        fifo_chuck_size_analog,
        expected_words_data_digital,
        expected_words_data_analog,
        digital_words_per_sample=2,
        digital_output_channels=25,
        debug=False,
    ):
        super().__init__()
        self.daemon = True
        set_debug(debug)
        self.queue_out = queue_out
        self.active_fifos = list(active_fifos)
        self.start_event = start_event
        self.stop_event = mp.Event()
        self.source = Pi23RandomBunchSource(
            fifo_chuck_size_digital=fifo_chuck_size_digital,
            fifo_chuck_size_analog=fifo_chuck_size_analog,
            expected_words_data_digital=expected_words_data_digital,
            expected_words_data_analog=expected_words_data_analog,
            digital_words_per_sample=digital_words_per_sample,
            digital_output_channels=digital_output_channels,
        )

    def run(self):
        print_debug("Pi23ReceiverProcess RUN - PID:", os.getpid())
        try:
            psutil.Process(os.getpid()).nice(psutil.HIGH_PRIORITY_CLASS)
        except Exception:
            pass

        self.source.start()
        while not self.stop_event.is_set():
            if not self.start_event.is_set():
                sleep(0.001)
                continue

            emitted_any = False
            for fifo_name in self.active_fifos:
                bunch = self.source.read_bunch(fifo_name)
                if bunch is None:
                    continue
                self.queue_out.put({fifo_name: [bunch, bunch.sample_count]})
                emitted_any = True

            if not emitted_any:
                sleep(0.001)

        self.source.stop()

    def stop(self):
        print_debug("Pi23ReceiverProcess STOP")
        self.stop_event.set()

