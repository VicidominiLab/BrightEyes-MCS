"""PI23 adapter for the shared acquisition loop."""

import numpy as np

from brighteyes_mcs.acquisition.detectors.pi23.backend import (
    Pi23RawBunch,
    pi23_decode_raw_bunch_to_spad_preview_words,
)
from brighteyes_mcs.logging_setup import logger

from ...acquisition_loop import BaseAcquisitionLoopProcess


class Pi23AcquisitionLoopProcess(BaseAcquisitionLoopProcess):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("process_label", "PI23 acquisition loop")
        super().__init__(*args, **kwargs)

    def normalize_digital_payload(self, payload):
        """Convert native PI23 packets to normalized 25-channel FIFO words."""

        if isinstance(payload, Pi23RawBunch):
            logger.debug("%s %s %s %s", self.process_label, "decoded PI23 raw bunch", payload.sample_count, payload.payload.get("source"))
            return self._decode_raw_bunch(payload)

        if hasattr(payload, "payload") and hasattr(payload, "sample_count"):
            logger.debug("%s %s %s", self.process_label, "decoded PI23-compatible raw bunch", payload.sample_count)
            return self._decode_raw_bunch(payload)

        return np.asarray(payload, dtype=np.uint64)

    def _decode_raw_bunch(self, payload):
        return pi23_decode_raw_bunch_to_spad_preview_words(
            payload,
            digital_words_per_sample=self.DATA_WORDS_PER_SAMPLE_DIGITAL,
        ).astype(np.uint64, copy=False)


__all__ = ["Pi23AcquisitionLoopProcess"]
