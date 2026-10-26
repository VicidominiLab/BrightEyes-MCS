"""Compare existing detector routing/register behavior with the pre-Flare baseline."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from brighteyes_mcs.acquisition.detectors.factory import create_detector_pipeline
from brighteyes_mcs.acquisition.detectors.models import (
    detector_uses_nifpga_control,
    detector_uses_nifpga_fifo,
    normalize_detector_model,
)
from brighteyes_mcs.acquisition.manager import McsManager


def legacy_snapshot():
    results = []
    for detector in (
        "FPGA - SPAD",
        "SPAD_TTM",
        "TCP/IP - PI SPAD23R (Intensity)",
        "PISPAD23TT",
        "TCP/IP - PI SPAD23R (TS mode - uimg)",
        "Disable",
    ):
        for channels in (25, 49):
            model = normalize_detector_model(detector)
            handle = Mock()
            acquisition = SimpleNamespace(
                detector_model=model,
                is_connected=True,
                fpga_handle=handle,
                registers_configuration={},
            )
            McsManager.setRegistersDict(
                acquisition,
                {
                    "max_pixel": 3,
                    "max_line": 2,
                    "max_frame": 4,
                    "max_repetition": 3,
                    "time_bin_dwell_cycles": 2000,
                    "max_time_bins_per_pixel": 5,
                    "stream_out_main_enable": True,
                    "stream_out_aux_enable": True,
                    "dfd_enable": True,
                    "start_command": True,
                },
            )
            results.append(
                {
                    "detector": detector,
                    "channels": channels,
                    "model": model,
                    "pipeline": type(create_detector_pipeline(model)).__name__,
                    "ni_control": detector_uses_nifpga_control(model),
                    "ni_fifo": detector_uses_nifpga_fifo(model),
                    "writes": [
                        list(call.args) for call in handle.register_write_checked.call_args_list
                    ],
                    "registers": acquisition.registers_configuration,
                }
            )
    return results


def test_existing_detector_contract_matches_branch_base():
    fixture = Path(__file__).parent / "fixtures" / "flare_legacy_baseline.json"
    assert legacy_snapshot() == json.loads(fixture.read_text(encoding="utf-8"))
