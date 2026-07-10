"""PI23 detector receiver."""

import multiprocessing as mp
import os
from time import sleep

import psutil

from ...detectors.pi23.backend import Pi23TcpBunchSource, pi23_debug
from ...print_debug import print_debug, set_debug


class Pi23ReceiverProcess(mp.Process):
    """
    Receive PI23-native raw bunches.

    The TCP detector source is intentionally isolated here so the rest of the
    acquisition stack can continue to consume detector-native bunches.
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
        scan_x=1,
        scan_y=1,
        scan_frames=1,
        timebins_per_pixel=1,
        dwell_us=2.0,
        external_frame=0,
        host=None,
        port=None,
        shared_dict=None,
        debug=False,
    ):
        super().__init__()
        self.daemon = True
        set_debug(debug)
        self.queue_out = queue_out
        self.active_fifos = list(active_fifos)
        self.start_event = start_event
        self.stop_event = mp.Event()
        self.source = Pi23TcpBunchSource(
            fifo_chuck_size_digital=fifo_chuck_size_digital,
            fifo_chuck_size_analog=fifo_chuck_size_analog,
            expected_words_data_digital=expected_words_data_digital,
            expected_words_data_analog=expected_words_data_analog,
            digital_words_per_sample=digital_words_per_sample,
            digital_output_channels=digital_output_channels,
            scan_x=scan_x,
            scan_y=scan_y,
            scan_frames=scan_frames,
            timebins_per_pixel=timebins_per_pixel,
            dwell_us=dwell_us,
            external_frame=external_frame,
            host=host,
            port=port,
            shared_dict=shared_dict,
            debug=debug,
        )
        self.debug = bool(debug)

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
                try:
                    bunch = self.source.read_bunch(fifo_name)
                except Exception as exc:
                    print_debug("Pi23ReceiverProcess read error", fifo_name, repr(exc))
                    self.stop_event.set()
                    break
                if bunch is None:
                    continue
                self.queue_out.put({fifo_name: [bunch, bunch.sample_count]})
                print_debug("Pi23ReceiverProcess queued", fifo_name, bunch.sample_count)
                pi23_debug("receiver queued", fifo_name, bunch.sample_count, enabled=self.debug)
                emitted_any = True

            if not emitted_any:
                sleep(0.001)

        self.source.stop()

    def stop(self):
        print_debug("Pi23ReceiverProcess STOP")
        self.stop_event.set()

