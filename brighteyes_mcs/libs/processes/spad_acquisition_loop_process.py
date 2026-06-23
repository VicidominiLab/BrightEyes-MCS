"""SPAD acquisition worker."""

from .acquisition_loop_process import (
    AcquisitionLoopProcess,
    accumulate_unordered_sum_4d,
    aggregate_samples_by_pixel,
    build_pointer_frame_lookup,
    circular_mean_from_positions,
    circular_mean_std,
    decode_pointer_list,
    flim_map_to_hcl,
    flim_parameters_from_3samples,
    flim_render_hcl,
    lch_to_srgb,
)


class SpadAcquisitionLoopProcess(AcquisitionLoopProcess):
    """SPAD-named wrapper around the legacy SPAD FIFO acquisition worker."""

