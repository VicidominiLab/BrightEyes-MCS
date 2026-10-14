"""PISPAD23 adapter for the shared acquisition loop."""

import numpy as np

from brighteyes_mcs.acquisition.detectors.pispad23.backend import (
    PISPAD23RawBunch,
    pispad23_decode_raw_bunch_to_spad_preview_words,
)
from brighteyes_mcs.logging_setup import logger

from ...acquisition_loop import BaseAcquisitionLoopProcess


class PISPAD23AcquisitionLoopProcess(BaseAcquisitionLoopProcess):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("process_label", "PISPAD23 acquisition loop")
        super().__init__(*args, **kwargs)

    def normalize_digital_payload(self, payload):
        """Convert native PISPAD23 packets to normalized 25-channel FIFO words."""

        if isinstance(payload, PISPAD23RawBunch):
            logger.debug("%s %s %s %s", self.process_label, "decoded PISPAD23 raw bunch", payload.sample_count, payload.payload.get("source"))
            return self._decode_raw_bunch(payload)

        if hasattr(payload, "payload") and hasattr(payload, "sample_count"):
            logger.debug("%s %s %s", self.process_label, "decoded PISPAD23-compatible raw bunch", payload.sample_count)
            return self._decode_raw_bunch(payload)

        return np.asarray(payload, dtype=np.uint64)

    def _decode_raw_bunch(self, payload):
        return pispad23_decode_raw_bunch_to_spad_preview_words(
            payload,
            digital_words_per_sample=self.DATA_WORDS_PER_SAMPLE_DIGITAL,
        ).astype(np.uint64, copy=False)


__all__ = ["PISPAD23AcquisitionLoopProcess"]
