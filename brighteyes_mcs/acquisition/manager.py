"""Shared-memory orchestration for FPGA acquisition, preprocessing, and preview."""

import numpy as np
import multiprocessing as mp
import re
import time

# from PySide6.QtCore import QObject

from ..hardware.fpga import FpgaHandle
from brighteyes_mcs.logging_setup import logger
from ..acquisition.detectors.models import (
    DETECTOR_SPAD_ARRAY,
    detector_uses_nifpga_fifo,
    detector_uses_pi23_pipeline,
    normalize_detector_model,
)
from ..acquisition.detectors import create_detector_pipeline

from ..acquisition import (
    AcquisitionCoordinator,
    AcquisitionStorage,
    PreviewRepository,
    ProcessSupervisor,
    SharedMemoryRegistry,
)


PI23_NIFPGA_DIMENSION_OFFSETS = {
    "#pixels": 1,
    "#lines": 1,
    "#frames": 1,
}


def create_i64_counter(initial_value=0):
    return mp.Value("q", int(initial_value))


def _pi23_nifpga_dimension_registers(registers, detector_model, direction=1):
    registers = dict(registers)
    if not detector_uses_pi23_pipeline(detector_model):
        return registers

    for register, offset in PI23_NIFPGA_DIMENSION_OFFSETS.items():
        if register in registers and registers[register] is not None:
            registers[register] = max(1, int(registers[register]) + (direction * offset))
    return registers


class McsManager():
    """
    Manages BrightEyes-MCS detector control, data acquisition, and processing.

    Attributes:
        spad_channels (int): Number of SPAD channels.
        spad_detector_dim (int): Dimension of the SPAD detector.
        niAddr (str): NI address.
        bitfile (str): Path to the bitfile.
        timeout_fifos (float): Timeout for the FIFOs.
        fpga_handle (FpgaHandle): Handle for the FPGA.
        shared_arrays_ready (bool): Flag indicating if shared arrays are ready.
        mp_manager (multiprocessing.Manager): Manager for multiprocessing.
        initial_registers_dict (dict): Dictionary for ultra configuration.
        shared_dict (dict): Shared dictionary for multiprocessing.
        default_configuration (dict): Default configuration for the registers.
        requested_fifo_depth (int): Requested FPGA FIFO depth.
        actual_fifo_depth (int): Configured FPGA FIFO depth reported by the driver.
        timebins_per_pixel (int): Number of time bins per pixel.
        time_resolution (float): Time resolution.
        dim_x (int): Number of pixels in x dimension.
        dim_y (int): Number of pixels in y dimension.
        dim_z (int): Number of frames.
        dim_rep (int): Number of repetitions.
        previewProcess (AcquisitionLoopProcess): Process for previewing data.
        expected_words_data_digital (int): Expected raw data.
        expected_words_data_per_frame_digital (int): Expected raw data per frame.
        registers_configuration (dict): Configuration of the registers.
        shared_memory_buffer (MemorySharedNumpyArray): Shared memory buffer.
        shared_image_xy (MemorySharedNumpyArray): Shared image in xy plane.
        shared_fingerprint (MemorySharedNumpyArray): Shared fingerprint data.
        shared_fingerprint_mask (MemorySharedNumpyArray): Shared fingerprint mask.
        is_connected (bool): Flag indicating if connected to FPGA.
        fifo_chuck_size_digital (int): Size of the FIF O chuck.
        fifo_chuck_size_analog (int): Size of the FIFO chuck.
        acquisition_done_event (multiprocessing.Event): Event for acquisition done.
        acquisition_almost_done_event (multiprocessing.Event): Event for acquisition almost done.
        acquisition_run_event (multiprocessing.Event): Event for acquisition run.
        acquisition_stop_event (multiprocessing.Event): Event for acquisition stop.
        do_not_save_event (multiprocessing.Event): Event for activating preview.
        autocorrelation_maxx (int): Maximum value for autocorrelation.
        trace_bins (int): Number of time-trace bins.
        trace_sample_per_bins (int): Number of words per time-trace bin.
        preview_buffer_capacity_samples (int): Preview buffer capacity in samples.
        fifo_prebuffer_length (int): Number of FIFO values accumulated before dispatch.
        activated_fifos_list (list): List of activated FIFOs.
        DFD_Activate (bool): Flag for DFD activation.
        snake_walk_xy (bool): Flag for snake walk mode on xy.
        snake_walk_z (bool): Flag for snake walk mode on z.
        clk_multiplier (int): DFD Laser Clk multiplier = decimation on the time dimension
        dfd_shift (int): DFD bin to shift
        compensation_delay_for_snake (int): Pixel delay compensation used with snake walk.
        use_rust_fifo (bool): Flag for using Rust FIFO.
        debug (bool): Debug flag.
    """
    def __init__(self, filename="bitfiles/MyBitfileUSB.lvbitx", address="RIO0", spad_channels=25, clock_base=40):
        """
        Constructor of the class of McsManager
        """
        super().__init__()
        # def __init__(self, filename="C:/Users/madonato/PycharmProjects/pyspad-fcs/bitfiles/laser_wait4.lvbitx", address="RIO0"):
        self.spad_channels = spad_channels
        self.spad_detector_dim = int(np.sqrt(self.spad_channels))
        # self.activate_rgb = False

        self.niAddr = address
        self.bitfile = filename
        self.niAddr2 = ""
        self.bitfile2 = ""
        self.clock_base = clock_base
        self.timeout_fifos = 0.5e6
        # self.fifo = None
        # self.nifpga_session = None
        self.fpga_handle = None
        self.shared_arrays_ready = False

        self.mp_manager = mp.Manager()

        # self.initial_registers_dict = UltraDict({}, shared_lock=True, full_dump_size=10000)
        # self.shared_dict = UltraDict(
        #     {}, shared_lock=True, full_dump_size=10000
        # )  # self.mp_manager.dict()

        self.initial_registers_dict = self.mp_manager.dict()
        self.shared_dict = self.mp_manager.dict()

        self.default_configuration = {
            "shutters": None,
            # 'wait time': 5000000,
            # 'wait time': 1,
            "LC": None,
            "t": None,
            "rz": None,
            "ry": None,
            "rx": None,
            "Frame tag": None,
            "Line tag": None,
            "Pixel tag": None,
            "CalibrationFactors(V/step)": [0.00219727, 0.00219727, 0],
            "Offset/StartValue (V)": [-0.561798, -1.1236, 0],
            "msgLen": 29,
            "msgOut": 0,  # 33554431, #535822335,
            "initializationTime": 0,
            "holdOff": 11,
            "Cx": 40,
            "ClockDur": 20000,
            "turnOffFC": None,
            "turnOffLC": None,
            "turnOffPC": None,
            "rz2": None,
            "ry2": None,
            "rx2": None,
            "#timebinsPerPixel": 10,
            "#circular_points": 1,
            '#circular_rep': 1,
            "#pixels": 512,
            "#lines": 512,
            "#frames": 1,
            "stop": False,
            "Run": False,
            "L1": 1,
            "L2": 0,
            "L3": 0,
            "L4": 0,
            # 'LaserOffAfterMeasurement' : False,
        }
        self.requested_fifo_depth = 100000
        self.actual_fifo_depth = 0

        self.timebins_per_pixel = 0
        self.time_resolution = 0
        self.circ_repetition = 0
        self.circ_points = 0

        self.dim_x = 0
        self.dim_y = 0
        self.dim_z = 0
        self.dim_rep = 0
        # self.acquisitionThread = Thread()
        self.previewProcess = None  # mp.Process()
        self.expected_words_data_digital = 0
        self.expected_words_data_analog = 0
        self.expected_words_data_per_frame_digital = 0
        self.expected_words_data_per_frame_analog = 0
        # self.dataCounts = None
        self.registers_configuration = {}
        # self.raw_data_buffer = None
        # self.default_destination_folder = ""
        # self.previewEnabled = False

        self.shared_memory_buffer = None
        self.shared_image_xy = None
        self.shared_image_xy_hcl = None
        self.shared_fingerprint = None
        self.shared_fingerprint_mask = None
        self.shared_trace_dfd = None


        self.is_connected = False

        self.fifo_chuck_size_digital = 10
        self.fifo_chuck_size_analog = 10

        self.acquisition_done_event = mp.Event()
        self.acquisition_almost_done_event = mp.Event()
        self.acquisition_run_event = mp.Event()
        self.acquisition_stop_event = mp.Event()
        self.do_not_save_event = mp.Event()

        self.autocorrelation_maxx = 20

        self.trace_bins = 30000
        self.trace_sample_per_bins = 10000

        self.preview_buffer_capacity_samples = 15000
        self.fifo_prebuffer_length = 0
        self.activated_fifos_list = []
        self.activate_show_preview = False

        self.DFD_Activate = False
        self.DFD_nbins = 0
        self.dfd_cycle_mhz = 40

        self.snake_walk_xy = False
        self.snake_walk_z = False

        self.clk_multiplier = 1
        self.dfd_shift = 0
        self.compensation_delay_for_snake = 0
        self.compensation_delay_for_snake_shared = None

        self.use_rust_fifo = True
        self.detector_model = DETECTOR_SPAD_ARRAY
        self.pi23_host = "127.0.0.1"
        self.pi23_port = 9997

        self.debug = False
        self.h5_manager_process = None
        self.h5_command_queue = None
        self.h5_response_queue = None
        self.raw_stream_mode = False
        self.raw_output_files = {}
        self.raw_writer_process = None
        self.detector_pipeline = create_detector_pipeline(self.detector_model)
        self.detector_receiver_queue = None
        self.detector_receiver_process = None
        self.detector_receiver_start_event = None
        self.filenameh5 = ""
        self.shared_memory_registry = SharedMemoryRegistry()
        self.preview_repository = PreviewRepository()
        self.process_supervisor = ProcessSupervisor()
        self.acquisition_storage = AcquisitionStorage()
        self.acquisition_coordinator = AcquisitionCoordinator(self)



    def __del__(self):
        """
        Destructor of the class
        """
        logger.debug("Destructor called.")

    def set_DFD_nbins(self, DFD_nbins):
        """
        Set the number of DFD_nbins
        """
        logger.debug("%s %s", "DFD_nbins", DFD_nbins)
        self.DFD_nbins = DFD_nbins

    @staticmethod
    def parse_dfd_metadata_from_bitfile_name(bitfile="", default_cycle_mhz=40):
        """
        Infer DFD metadata from a bitfile name token like ``40M91``.

        Accept any ``xxxxxMyyyyyyy`` token found in the basename, provided:
        - 3 < xxxxx < 100
        - 3 < yyyyyyy < 1000
        """
        filename = str(bitfile).replace("\\", "/").split("/")[-1]
        match = re.search(r"(?P<cycle>\d+)M(?P<bins>\d+)", filename, re.IGNORECASE)
        if not match:
            return default_cycle_mhz, None

        parsed_cycle_mhz = int(match.group("cycle"))
        parsed_bins = int(match.group("bins"))
        if not (3 < parsed_cycle_mhz < 100 and 3 < parsed_bins < 1000):
            return default_cycle_mhz, None

        return parsed_cycle_mhz, parsed_bins

    def set_spad_channels(self, ch):
        """
        Set the number of SPAD channels
        """
        logger.debug("%s %s", "SPAD channels", ch)
        self.spad_channels = ch
        self.spad_detector_dim = int(np.sqrt(self.spad_channels))

        mydict = {}

        if ch == 49:
            mydict.update(
                {
                    "49_enable": True
                }
            )
        else:
            mydict.update(
                {
                    "49_enable": False
                }
            )

        self.default_configuration.update(mydict)

    def activateShowPreview(self, enable):
        """
        Activate the preview flag
        """
        logger.debug("%s %s", "activate_show_preview", enable)
        self.activate_show_preview = enable

    def setActivatedFifo(self, fifos_list):
        """
        Set the activated FIFOs
        """
        logger.debug("%s %s", "self.activated_fifos_list", fifos_list)
        self.activated_fifos_list = fifos_list

    def acquisition_stop(self):
        """
        Stop the acquisition
        """
        self.acquisition_stop_event.set()
        self.acquisition_run_event.clear()

    def acquisition_run(self):
        """
        Run the acquisition
        """
        self.acquisition_stop_event.clear()
        self.acquisition_run_event.set()

    def acquisition_done_reset(self):
        """
        Reset the acquisition done event
        """
        self.acquisition_done_event.clear()

    def acquisition_almost_done_reset(self):
        """
        Reset the acquisition almost done event
        """
        self.acquisition_almost_done_event.clear()

    def acquisition_is_done(self):
        """
        Check if the acquisition is done
        """
        return self.acquisition_done_event.is_set()

    def acquisition_is_almost_done(self):
        """
        Check if the acquisition is almost done
        """
        return self.acquisition_almost_done_event.is_set()


    def set_do_not_save(self, active=True):
        """
        Activate the preview
        """
        if active:
            self.do_not_save_event.set()
            logger.debug("self.do_not_save_event.set()")
        else:
            self.do_not_save_event.clear()
            logger.debug("self.do_not_save_event.clear()")

    def set_activate_DFD(self, activate=True):
        """
        Activate the DFD mode
        """
        logger.debug("%s %s", "set_activate_DFD() set to ", activate)
        self.DFD_Activate = activate

    def set_activate_snake_walk_xy(self, activate=True):
        """
        Set the snake walk (bidirectional scanning)
        """
        logger.debug("%s %s", "set_activate_snake_walk_xy() set to ", activate)
        self.snake_walk_xy = activate

    def set_activate_snake_walk_z(self, activate=True):
        """
        Set the snake walk (bidirectional scanning)
        """
        logger.debug("%s %s", "set_activate_snake_walk_z() set to ", activate)
        self.snake_walk_z = activate

    # def set_default_destination_folder(self, folder=""):
    #     self.default_destination_folder = folder

    def set_bit_file(self, bitfile=""):
        """
        Set the bit file for the 1st FPGA
        """
        logger.debug("%s %s", "set_bit_file", bitfile)
        self.bitfile = bitfile
        self.dfd_cycle_mhz, inferred_dfd_nbins = self.parse_dfd_metadata_from_bitfile_name(
            bitfile,
            default_cycle_mhz=self.dfd_cycle_mhz,
        )
        if inferred_dfd_nbins is not None:
            self.DFD_nbins = inferred_dfd_nbins

    def set_ni_addr(self, niAddr=""):
        """
        Set the NI address for the 1st FPGA
        """
        logger.debug("%s %s", "set_ni_addr", niAddr)
        self.niAddr = niAddr

    def set_bit_file_second_fpga(self, bitfile=""):
        """
        Set the bit file for the 2nd FPGA
        """
        logger.debug("%s %s", "set_bit_file 2nd FPGA", bitfile)
        self.bitfile2 = bitfile

    def set_ni_addr_second_fpga(self, niAddr=""):
        """
        Set the NI address for the 2nd FPGA
        """
        logger.debug("%s %s", "set_ni_addr 2nd FPGA", niAddr)
        self.niAddr2 = niAddr


    def set_requested_fifo_depth(self, requested_fifo_depth):
        logger.debug("%s %s", "requested_fifo_depth", requested_fifo_depth)
        self.requested_fifo_depth = requested_fifo_depth

    def set_requested_depth(self, requested_depth):
        self.set_requested_fifo_depth(requested_depth)

    def set_preview_buffer_capacity_samples(self, preview_buffer_capacity_samples):
        """
        Set the preview buffer capacity in samples.
        """
        logger.debug("%s %s", "preview_buffer_capacity_samples", preview_buffer_capacity_samples)
        self.preview_buffer_capacity_samples = preview_buffer_capacity_samples

    def set_preview_buffer_size_in_sample(self, preview_buffer_size_in_sample):
        self.set_preview_buffer_capacity_samples(preview_buffer_size_in_sample)

    def set_fifo_prebuffer_length(self, fifo_prebuffer_length):
        """
        Set the FIFO prebuffer length.
        """
        self.fifo_prebuffer_length = fifo_prebuffer_length

    def set_len_fifo_prebuffer(self, len_fifo_prebuffer):
        self.set_fifo_prebuffer_length(len_fifo_prebuffer)

    def set_timeout_fifos(self, timeout):
        """
        Set the timeout for the FIFOs
        """
        logger.debug("%s %s", "set_timeout_fifos", timeout)
        self.timeout_fifos = timeout

    def connect(self, initial_registers=None, list_fifos=None):
        if initial_registers is None:
            initial_registers = {}
        if list_fifos is None:
            list_fifos = []
        """
        Connect to the FPGA using FPGA handle class
        """
        logger.debug("FPGA connect()")
        initial_registers_for_detector = dict(initial_registers)
        if not detector_uses_nifpga_fifo(self.detector_model):
            initial_registers_for_detector = {
                **self.default_configuration,
                **initial_registers_for_detector,
                "#repetition": initial_registers_for_detector.get("#repetition", 2),
                "activateFIFOAnalog": False,
                "activateFIFODigital": False,
                "DFD_Activate": False,
            }
        nifpga_initial_registers = _pi23_nifpga_dimension_registers(
            initial_registers_for_detector,
            self.detector_model,
        )
        nifpga_fifos = list_fifos if detector_uses_nifpga_fifo(self.detector_model) else []
        # self.nifpga_session = nifpga.Session(self.bitfile, self.niAddr)
        try:
            self.fpga_handle = FpgaHandle(
                bitfile=self.bitfile,
                ni_address=self.niAddr,
                mp_manager=self.mp_manager,
                requested_fifo_depth=self.requested_fifo_depth,
                list_fifos=nifpga_fifos,
                initial_registers_dict=self.initial_registers_dict,
                debug=self.debug,
                use_rust_fifo=self.use_rust_fifo,
                timeout_fifos=self.timeout_fifos,
                bitfile2=self.bitfile2,
                ni_address2=self.niAddr2,
                detector_model=self.detector_model,
            )
            self.is_connected = True
            logger.debug("%s %s", ".is_conneccted", self.is_connected)

            self.update_chuck()

            self.fpga_handle.run(nifpga_initial_registers)
            logger.debug("self.fpga_handle.run()")
        except Exception as e:
            self.is_connected = False
            logger.debug("%s %s", "connect ERROR", repr(e))
            raise RuntimeError("ERROR") from e


    def set_filename_h5(self, filename):
        """
        Set the filename for the HDF5 file
        """
        self.filenameh5 = filename

    def set_fingerprint_mask(self, fingerprint_mask):
        """
        Set the fingerprint mask
        """
        self.shared_fingerprint_mask.get_numpy_handle()[:] = np.copy(fingerprint_mask)

    def set_use_rust_fifo(self, value=True):
        """
        Set the use of rust FIFO
        """
        self.use_rust_fifo = value

    def set_detector_model(self, detector_model=DETECTOR_SPAD_ARRAY):
        """
        Select which detector provides raw acquisition data.
        """
        self.detector_model = normalize_detector_model(detector_model)
        self.shared_dict["detector_model"] = self.detector_model
        self.detector_pipeline = create_detector_pipeline(self.detector_model)
        if self.fpga_handle is not None:
            self.fpga_handle.set_detector_model(self.detector_model)

    def set_pi23_connection(self, host="127.0.0.1", port=9997):
        self.pi23_host = str(host or "127.0.0.1")
        self.pi23_port = int(port or 9997)
        self.shared_dict["pi23_host"] = self.pi23_host
        self.shared_dict["pi23_port"] = self.pi23_port
        self.shared_dict["pi23_greeting_raw"] = ""
        self.shared_dict["pi23_greeting_decoded"] = ""

    def set_raw_stream_mode(self, enabled=False):
        """
        Enable direct FIFO-to-disk streaming without preview/conversion.
        """
        self.raw_stream_mode = enabled

    def set_raw_output_files(self, raw_output_files=None):
        """
        Set the per-FIFO destination files used by raw streaming mode.
        """
        self.raw_output_files = dict(raw_output_files or {})

    def run(self):
        """Start acquisition through the application coordinator."""
        return self.acquisition_coordinator.run()

    def _run_pipeline(self):
        """
        Run the FPGA, start the data process, the preview process and run the FPGA handle class
        """
        do_not_save = self.do_not_save_event.is_set()
        self.process_supervisor.clear()

        logger.debug("mcs_manager.run()")

        logger.debug("%s %s", "do_not_save", do_not_save)
        logger.debug("fpga_process.runed from run")
        self.readRegistersDict()
        logger.debug("mcs_manager.registers_configuration")
        logger.debug("%s %s", "mcs_manager.expected_words_data_digital", self.expected_words_data_digital)

        self.detector_pipeline = create_detector_pipeline(self.detector_model)
        nifpga_fifos = (
            self.activated_fifos_list
            if detector_uses_nifpga_fifo(self.detector_model)
            else []
        )
        self.fpga_handle.set_list_fifos_to_read_continously(nifpga_fifos)

        if not self.raw_stream_mode:
            preview_arrays = self.shared_memory_registry.allocate_preview(
                dim_x=self.dim_x,
                dim_y=self.dim_y,
                dim_z=self.dim_z,
                detector_dim=self.spad_detector_dim,
                autocorrelation_maxx=self.autocorrelation_maxx,
                trace_bins=self.trace_bins,
                dfd_bins=self.DFD_nbins,
            )
        else:
            preview_arrays = self.shared_memory_registry.disabled_preview()
        for name, value in preview_arrays.items():
            setattr(self, name, value)
        self.preview_repository.bind(preview_arrays)
        # self.shared_index = mp.Value("i",0)
        # , self.dim_z

        # self.data_queue = {"FIFO":       CircularSharedBuffer(size=1024*1024*128, dtype=np.uint64), # mp.Queue(),
        #                    "FIFOAnalog": CircularSharedBuffer(size=1024*1024*128, dtype=np.uint64), # mp.Queue()}
        #                   }

        self.data_queue = {"FIFO":  mp.Queue(),
                           "FIFOAnalog": mp.Queue()
                           }


        self.loc_acquired = {"FIFO": mp.Value("q"), "FIFOAnalog": mp.Value("q")}

        self.last_preprocessed_len = {
            "FIFO": mp.Value("q"),
            "FIFOAnalog": mp.Value("q"),
        }

        self.loc_previewed = {"FIFO": mp.Value("q"), "FIFOAnalog": mp.Value("q")}

        self.dtype_data_queue = {
            "FIFO": np.uint64,
            # "FIFO": np.uint64,
            "FIFOAnalog": np.uint64,
        }
        self.detector_receiver_start_event = mp.Event()
        self.detector_receiver_queue = self.detector_pipeline.make_receiver_queue(self)

        self.number_of_threads_h5 = mp.Value("i", 0)
        if not do_not_save and not self.raw_stream_mode:
            (
                self.h5_command_queue,
                self.h5_response_queue,
                self.h5_manager_process,
            ) = self.acquisition_storage.start(self.number_of_threads_h5)
        else:
            (
                self.h5_command_queue,
                self.h5_response_queue,
                self.h5_manager_process,
            ) = self.acquisition_storage.disabled()

        self.trace_pos = mp.Value("i", 0) if not self.raw_stream_mode else None

        # self.acquisitionThread = AcquireFIFOinBackground(self.queue,
        #                                                  self.fifo)

        self.compensation_delay_for_snake_shared = (
            mp.Value("i", int(self.compensation_delay_for_snake))
            if not self.raw_stream_mode
            else None
        )

        # The preprocessing worker repacks FIFO chunks into arrays that are
        # cheaper for the acquisition loop to consume repeatedly.
        if not self.raw_stream_mode:
            self.dataProcess = self.detector_pipeline.make_data_preprocess(
                self,
                self.detector_receiver_queue,
            )

            self.dataProcess.daemon = True
            self.process_supervisor.register("preprocess", self.dataProcess)
        else:
            self.dataProcess = None

        self.shared_objects = {
            "activated_fifos_list": self.activated_fifos_list,
            "loc_acquired": self.loc_acquired,
            "loc_previewed": self.loc_previewed,
            "shared_image_xy_rgb": self.shared_image_xy_rgb,
            "shared_image_xy_hcl": self.shared_image_xy_hcl,
            "shared_image_xy": self.shared_image_xy,
            "shared_image_xz": self.shared_image_xz,
            "shared_image_zy": self.shared_image_zy,
            "shared_fingerprint": self.shared_fingerprint,
            "shared_autocorrelation": self.shared_autocorrelation,
            "shared_trace": self.shared_trace,
            "shared_trace_dfd": self.shared_trace_dfd,
            "shared_fingerprint_mask": self.shared_fingerprint_mask,
            "number_of_threads_h5": self.number_of_threads_h5,
            "autocorrelation_maxx": self.autocorrelation_maxx,
            "trace_bins": self.trace_bins,
            "trace_sample_per_bins": self.trace_sample_per_bins,
            "trace_pos": self.trace_pos,
            "compensation_delay_for_snake": self.compensation_delay_for_snake_shared,
            "h5_command_queue": self.h5_command_queue,
            "h5_response_queue": self.h5_response_queue,
        }

        self.shared_dict["shape"] = [self.dim_x, self.dim_y, self.dim_z]
        self.shared_dict["spad_channels"] = self.spad_channels
        self.shared_dict["timebins_per_pixel"] = self.timebins_per_pixel
        self.shared_dict["circ_repetition"] = self.circ_repetition
        self.shared_dict["circ_points"] = self.circ_points
        self.shared_dict["time_resolution"] = self.time_resolution
        self.shared_dict["expected_words_data_digital"] = self.expected_words_data_digital
        self.shared_dict["expected_words_data_analog"] = self.expected_words_data_analog
        self.shared_dict["expected_words_data_per_frame_digital"] = self.expected_words_data_per_frame_digital
        self.shared_dict["expected_words_data_per_frame_analog"] = self.expected_words_data_per_frame_analog
        self.shared_dict["filenameh5"] = self.filenameh5
        self.shared_dict["DFD_nbins"] = self.DFD_nbins
        self.shared_dict["dfd_cycle_mhz"] = self.dfd_cycle_mhz
        self.shared_dict["raw_output_files"] = dict(self.raw_output_files)
        self.shared_dict["detector_model"] = self.detector_model

        logger.debug("%s %s", "self.activate_show_preview", self.activate_show_preview)
        self.shared_dict.update(
            {
                "activate_show_preview": self.activate_show_preview,
                "current_z_analog": 0,
                "current_rep_analog": 0,
                "current_z_digital": 0,
                "current_rep_digital": 0,
                "total_photon": 0,
                "FIFO_status": 0,
                "FIFOAnalog_status": 0,
                "preview_buffer_capacity_samples": self.preview_buffer_capacity_samples,
                "last_packet_size": 0,
                "DFD_Activate": self.DFD_Activate,
                "DFD_nBins": self.DFD_nbins,
                "dfd_peak_idx": -1,
                "snake_walk_xy": self.snake_walk_xy,
                "snake_walk_z": self.snake_walk_z,
                "clk_multiplier": self.clk_multiplier,
                "dfd_cycle_mhz": self.dfd_cycle_mhz,
                "dfd_shift": self.dfd_shift,
                "raw_stream_mode": self.raw_stream_mode,
            }
        )

        if self.raw_stream_mode:
            logger.debug("self.raw_writer_process()")
            self.raw_writer_process = self.detector_pipeline.make_raw_stream_writer(
                self,
                self.detector_receiver_queue,
            )
            self.raw_writer_process.daemon = True
            self.process_supervisor.register("raw_writer", self.raw_writer_process)
            self.previewProcess = None
        else:
            logger.debug("self.previewProcess()")
            self.previewProcess = self.detector_pipeline.make_acquisition_loop(
                self,
                do_not_save,
            )
            self.previewProcess.daemon = True
            self.process_supervisor.register("preview", self.previewProcess)

        self.detector_receiver_process = self.detector_pipeline.make_receiver_process(
            self,
            self.detector_receiver_queue,
            self.detector_receiver_start_event,
        )
        if self.detector_receiver_process is not None:
            self.detector_receiver_process.daemon = True
            self.process_supervisor.register("receiver", self.detector_receiver_process)

        self.shared_arrays_ready = not self.raw_stream_mode
        if self.detector_receiver_process is not None:
            logger.debug("self.detector_receiver_process.start()")
            self.process_supervisor.start("receiver")
        if self.dataProcess is not None:
            logger.debug("self.dataProcess.start()")
            self.process_supervisor.start("preprocess")
        if self.raw_stream_mode:
            self.process_supervisor.start("raw_writer")
        else:
            self.process_supervisor.start("preview")
        # self.nifpga_session.run()
        self.fpga_handle.runfpga()
        if self.detector_receiver_start_event is not None:
            self.detector_receiver_start_event.set()

    def previewProcess_isAlive(self):
        """
        Preview process is alive
        """
        try:
            return self.process_supervisor.is_alive("preview")
        except:
            return False

    def dataProcess_isAlive(self):
        """
        dataProcess is alive
        """
        try:
            return self.process_supervisor.is_alive("preprocess")
        except:
            return False

    def freeMemory(self):
        """
        Free the memory
        """
        self.shared_image_xy = None

    def setRegistersDict(self, myconf):
        """
        Set the registers dictionary
        """
        myconf = dict(myconf)
        if not detector_uses_nifpga_fifo(self.detector_model):
            for register in ("activateFIFOAnalog", "activateFIFODigital", "DFD_Activate"):
                if register in myconf:
                    myconf[register] = False
        nifpga_conf = _pi23_nifpga_dimension_registers(myconf, self.detector_model)
        # debug("setRegistersDict")
        register_set = "setRegistersDict: "
        temp_dict = {}
        for i in myconf:
            if myconf[i] is not None:
                # debug(i, myconf[i])
                register_set += "%s %s " % (i, myconf[i])
                # self.nifpga_session.registers[i].write(myconf[i])
                if self.is_connected:
                    self.fpga_handle.register_write(i, nifpga_conf[i])
                    temp_dict[i] = myconf[i]
            else:
                logger.debug("myconf is None")
        logger.debug(register_set)
        self.registers_configuration.update(temp_dict)

    def readRegistersDict(self):
        """
        Read the registers dictionary
        """
        logger.debug("readRegistersDict()")
        if self.is_connected:
            self.registers_configuration.update(
                _pi23_nifpga_dimension_registers(
                    self.fpga_handle.register_read_all(),
                    self.detector_model,
                    direction=-1,
                )
            )
            logger.debug("%s %s", "readRegistersDict self.registers_configuration:", self.registers_configuration)
        else:
            logger.debug("register_read_all() not called due to FPGAhandle not connected")

        self.timebins_per_pixel = self.registers_configuration["#timebinsPerPixel"]
        self.circ_repetition = self.registers_configuration["#circular_rep"]
        self.circ_points = self.registers_configuration["#circular_points"]

        self.time_resolution = self.registers_configuration["Cx"] / self.clock_base

        self.dim_x = self.registers_configuration["#pixels"]
        self.dim_y = self.registers_configuration["#lines"]
        self.dim_z = self.registers_configuration["#frames"]
        self.dim_rep = self.registers_configuration["#repetition"] - 1

        self.expected_words_data_per_frame_analog = (
                self.timebins_per_pixel * self.dim_x * self.dim_y * self.circ_repetition * self.circ_points
        )
        logger.debug("%s %s", "self.expected_words_data_per_frame_analog calculated ", self.expected_words_data_per_frame_analog)

        if self.spad_channels == 25:
            self.expected_words_data_per_frame_digital = (
                2 * self.timebins_per_pixel * self.dim_x * self.dim_y * self.circ_repetition * self.circ_points
            )
            logger.debug("%s %s", "self.expected_words_data_per_frame_digital calculated for 25 SPAD channels ", self.expected_words_data_per_frame_digital)
            logger.debug("%s %s %s %s %s %s %s %s %s %s %s %s %s %s", "timebins", self.timebins_per_pixel, "x", self.dim_x, "y", self.dim_y, "z", self.dim_z, "rep", self.dim_rep, "circ_rep", self.circ_repetition, "circ_points", self.circ_points)
        elif self.spad_channels == 49:
            self.expected_words_data_per_frame_digital = (
                    8 * self.timebins_per_pixel * self.dim_x * self.dim_y * self.circ_repetition * self.circ_points
            )
            logger.debug("%s %s", "self.expected_words_data_per_frame_digital calculated for 49 SPAD channels", self.expected_words_data_per_frame_digital)

        else:
            logger.debug("self.expected_words_data_per_frame_digital DISASTER")

        self.expected_words_data_digital = (
            self.expected_words_data_per_frame_digital * self.dim_z * self.dim_rep
        )

        self.expected_words_data_analog = (
                self.expected_words_data_per_frame_analog * self.dim_z * self.dim_rep
        )

        self.update_chuck()

    def update_chuck(self):
        """
        Update the chuck size
        """
        try:
            self.timebins_per_pixel = self.registers_configuration["#timebinsPerPixel"]
            self.circ_repetition = self.registers_configuration["#circular_rep"]
            self.circ_points = self.registers_configuration["#circular_points"]
        except:
            self.timebins_per_pixel = self.default_configuration["#timebinsPerPixel"]
            self.circ_repetition = self.default_configuration["#circular_rep"]
            self.circ_points = self.default_configuration["#circular_points"]


        self.fifo_chuck_size_analog = self.timebins_per_pixel * self.circ_repetition * self.circ_points
        if self.spad_channels==25:
            self.fifo_chuck_size_digital = 2 * self.timebins_per_pixel * self.circ_repetition * self.circ_points
            logger.debug("update_chuck self.spad_channels == 25")
        elif self.spad_channels == 49:
            self.fifo_chuck_size_digital = 8 * self.timebins_per_pixel * self.circ_repetition * self.circ_points
            logger.debug("update_chuck self.spad_channels == 49")


        self.fpga_handle.set_fifo_chuck_size_digital(self.fifo_chuck_size_digital)
        self.fpga_handle.set_fifo_chuck_size_analog(self.fifo_chuck_size_analog)
        self.fpga_handle.set_expected_words_data_digital(self.expected_words_data_digital)
        self.fpga_handle.set_expected_words_data_analog(self.expected_words_data_analog)

        # self.fpga_handle.set_expected_words_data_digital(self.expected_words_data_per_frame_digital)

        logger.debug("%s %s %s", "Updated expected_words_data_digital and fifo_chuck_size_digital", self.expected_words_data_digital, self.fifo_chuck_size_digital)

        logger.debug("%s %s %s", "Updated expected_words_data_analog and fifo_chuck_size_analog", self.expected_words_data_analog, self.fifo_chuck_size_analog)


    def getCurrentPreviewElement(self, fifo_name=None):
        """
        Get the current preview element
        """
        if fifo_name==None:
            logger.debug("BUG: getCurrentPreviewElement(None)")
        return self.loc_previewed[fifo_name].value * 2

    def getCurrentAcquistionElement(self, fifo_name=None):
        """
        Get the current acquisition element
        """
        if fifo_name==None:
            logger.debug("BUG: getCurrentAcquistionElement(None)")
        return self.loc_acquired[fifo_name].value

    def getLastPreprocessedLen(self, fifo_name=None):
        """
        Get the last preprocessed length
        """
        if fifo_name==None:
            logger.debug("BUG: getLastPreprocessedLen(None)")
        return self.last_preprocessed_len[fifo_name]

    def getExpectedFifoElements(self, fifo_name=None):
        """
        Get the expected FIFO elements
        """
        if fifo_name=="FIFO":
            return self.expected_words_data_digital
        elif fifo_name=="FIFOAnalog":
            return self.expected_words_data_analog
        else:
            logger.debug("BUG: getExpectedFifoElements WRONG CALL")
            return 0

    def getExpectedFifoElementsPerFrame(self, fifo_name=None):
        """
        Get the expected FIFO elements per frame
        """
        if fifo_name=="FIFO":
            return self.expected_words_data_per_frame_digital
        elif fifo_name=="FIFOAnalog":
            return self.expected_words_data_per_frame_analog
        else:
            logger.debug("BUG: getExpectedFifoElements WRONG CALL")
            return 0

    def stopFPGA(self):
        """
        stop the FPGA
        """
        logger.debug("stopAcquisition.stop()")
        if self.fpga_handle is not None:
            self.fpga_handle.stop()

    def wait_for_fpga_idle(self, timeout=5.0, poll_interval=0.01):
        """Wait until the scan state machine reports its idle state."""
        if not self.is_connected or self.fpga_handle is None:
            raise RuntimeError("The FPGA is not connected.")

        deadline = time.monotonic() + float(timeout)
        last_status = None
        while time.monotonic() < deadline:
            registers = self.fpga_handle.register_read(("FSM Status",))
            last_status = registers.get("FSM Status")
            self.registers_configuration["FSM Status"] = last_status
            if last_status == 0:
                return
            time.sleep(float(poll_interval))

        raise TimeoutError(
            "FPGA FSM did not reach idle state 0 within "
            f"{float(timeout):g} seconds (last status: {last_status!r})."
        )

    def quick_reset_fpga(self, timeout=5.0, poll_interval=0.01):
        """Pulse the stop register and verify that the scan FSM becomes idle."""
        if not self.is_connected or self.fpga_handle is None:
            raise RuntimeError("The FPGA is not connected.")

        self.fpga_handle.register_write_checked("stop", True)
        self.registers_configuration["stop"] = True
        self.fpga_handle.register_write_checked("stop", False)
        self.registers_configuration["stop"] = False
        self.wait_for_fpga_idle(timeout=timeout, poll_interval=poll_interval)

    def _stop_detector_receiver(self):
        if self.detector_receiver_process is None:
            return
        if self.process_supervisor.get("receiver") is None:
            self.process_supervisor.register("receiver", self.detector_receiver_process)
        self.process_supervisor.stop("receiver", timeout=5)
        self.detector_receiver_process = None

    def stopAcquisition(self, keep_fpga_loaded=False):
        """
        Stop the acquisition
        """
        logger.debug("stopAcquisition.stop()")
        self._stop_detector_receiver()
        if self.dataProcess is not None:
            self.dataProcess.stop()
        if not keep_fpga_loaded:
            self.is_connected = False

    def stopPreview(self):
        """Stop acquisition through the application coordinator."""
        return self.acquisition_coordinator.stop()

    def _stop_pipeline(self):
        """
        Stop the preview
        """
        logger.debug("myfpga.stopPreview()")
        if self.raw_stream_mode:
            if self.raw_writer_process is not None:
                if self.process_supervisor.get("raw_writer") is None:
                    self.process_supervisor.register("raw_writer", self.raw_writer_process)
                self.process_supervisor.stop("raw_writer", timeout=5)
                self.raw_writer_process = None
        elif self.previewProcess is not None:
            if self.process_supervisor.get("preview") is None:
                self.process_supervisor.register("preview", self.previewProcess)
            self.process_supervisor.stop("preview", timeout=5)
        self._stop_detector_receiver()
        self.acquisition_storage.stop(timeout=2)
        self.h5_manager_process = None
        self.h5_command_queue = None
        self.h5_response_queue = None
        logger.debug("self.previewThread.join() done")

    def get_current_z(self, fifo="FIFO"):
        """
        Get the current z
        """
        if fifo=="FIFO":
            return self.shared_dict["current_z_digital"]
        if fifo=="FIFOAnalog":
            return self.shared_dict["current_z_analog"]

    def get_current_rep(self, fifo="FIFO"):
        """
        Get the current repetition
        """
        if fifo=="FIFO":
            return self.shared_dict["current_rep_digital"]
        if fifo=="FIFOAnalog":
            return self.shared_dict["current_rep_analog"]


    def get_total_photon(self):
        """
        Get the number of total photon
        """
        return self.shared_dict["total_photon"]

    def get_number_of_threads_h5(self):
        """
        Get the number of threads
        """
        return self.number_of_threads_h5.value

    def reset(self):
        """
        Reset the FPGA
        """
        self.fpga_handle.reset()

    def getFingerprint(self):
        """
        Get the fingerprint
        """
        return self.preview_repository.get_fingerprint(1)

    def getFingerprintCumulative(self):
        """
        Get the fingerprint cumulative
        """
        return self.preview_repository.get_fingerprint(0)

    def getFingerprintCumulativeLast10000(self):
        """
        Get the fingerprint cumulative last 10000 data packets
        """
        return self.preview_repository.get_fingerprint(2)

    def getFingerprintCumulativeLastFrame(self):
        """
        Get the fingerprint cumulative last frame
        """
        return self.preview_repository.get_fingerprint(3)

    def getFingerprintSaturation(self):
        """
        Get the fingerprint saturation
        """
        return self.preview_repository.get_fingerprint(4)

    # def getImage(self):
    #     """
    #     Get the image
    #     """
    #     # self.dataCounts = np.zeros((self.dim_x*self.dim_y*self.dim_z*self.timebins_per_pixel, self.spad_channels),
    #     #                           dtype = np.uint64)
    #     # #print(id(self.shared_memory_buffer))
    #     # #print(self.shared_memory_buffer.get_numpy_handle())
    #     # ddd = np.copy(self.shared_memory_buffer.get_numpy_handle())
    #     # print(ddd.shape, type(ddd), ddd.sum())
    #     # convertRawDataToCounts(ddd, self.dataCounts)
    #     # d = self.dataCounts.reshape(self.dim_z,
    #     #                             self.dim_y,
    #     #                             self.dim_x,
    #     #                             self.timebins_per_pixel,
    #     #                             self.spad_channels)
    #     d = np.memmap(
    #         "test.raw",
    #         dtype="uint16",
    #         mode="r",
    #         shape=(
    #             self.dim_z,
    #             self.dim_y,
    #             self.dim_x,
    #             self.timebins_per_pixel,
    #             self.spad_channels,
    #         ),
    #     )
    #     debug(d.shape, type(d))
    #     return d

    def setSelectedChannel(self, ch):
        """
        Set the selected channel
        """
        self.update_shared_dict({"channel": ch})

    def set_autocorrelation_maxx(self, value=20):
        """
        Set the autocorrelation maxx
        """
        logger.debug("%s %s", "set_autocorrelation_maxx", value)
        self.autocorrelation_maxx = value

    def set_clk_multiplier(self, multiplier=1):
        logger.debug("%s %s", "set_clk_multiplier", multiplier)
        self.clk_multiplier = multiplier

    def set_dfd_shift(self, shift=0):
        self.dfd_shift = shift

    def set_compensation_delay_for_snake(self, delay=0):
        delay = int(delay)
        self.compensation_delay_for_snake = delay
        if self.compensation_delay_for_snake_shared is not None:
            self.compensation_delay_for_snake_shared.value = delay

    def set_trace_bins(self, trace_bins=30000):
        """
        Set the trace bins
        """
        self.trace_bins = trace_bins

    def set_trace_sample_per_bins(self, trace_sample_per_bins=10000):
        """
        Set the trace sample per bins
        """
        self.trace_sample_per_bins = trace_sample_per_bins

    def getAutocorrelation(self):
        """
        Get the autocorrelation
        """
        return self.shared_autocorrelation.get_numpy_handle()

    def getTrace(self):
        """
        Get the time trace
        """
        a = self.shared_trace.get_numpy_handle() * 1.0
        a[1, :] = a[1, :] / (
            self.trace_sample_per_bins * self.time_resolution * 1e-6
        )
        a[0, :] = a[0, :] * self.time_resolution * 1e-6 * self.trace_sample_per_bins
        return a, self.trace_pos.value

    def getDfdTrace(self):
        """
        Get the DFD trace curves.
        """
        a = self.shared_trace_dfd.get_numpy_handle() * 1.0
        dfd_bin_width_s = (
            self.time_resolution * 1e-6 * max(self.clk_multiplier, 1)
        )
        if dfd_bin_width_s > 0:
            a[1, :] = a[1, :] / dfd_bin_width_s

            bins_per_cycle = max(
                int(self.timebins_per_pixel // max(self.clk_multiplier, 1)),
                1,
            )
            samples_processed = int(self.loc_previewed["FIFO"].value)
            data_words_per_sample_digital = 8 if self.spad_channels == 49 else 2
            if self.expected_words_data_per_frame_digital > 0:
                samples_per_frame = max(
                    int(
                        self.expected_words_data_per_frame_digital
                        // data_words_per_sample_digital
                    ),
                    1,
                )
                samples_processed = samples_processed % samples_per_frame
            completed_cycles, partial_cycle_bins = divmod(
                samples_processed, bins_per_cycle
            )
            exposure_cycles = np.full(a.shape[1], completed_cycles, dtype=np.float64)
            exposure_cycles[: min(partial_cycle_bins, a.shape[1])] += 1.0
            exposure_time_s = exposure_cycles * dfd_bin_width_s
            np.divide(
                a[2, :],
                exposure_time_s,
                out=a[2, :],
                where=exposure_time_s > 0,
            )
            a[2, exposure_time_s <= 0] = 0
        return a

    def getPreviewImage(self, projection="xy", rgb=False):
        """
        Get the preview image with at selected projection
        """
        # print(self.previewThread.current_x,self.previewThread.current_y,self.previewThread.current_f, self.previewThread.data_len)
        self.preview_repository.bind(
            {
                "shared_image_xy": self.shared_image_xy,
                "shared_image_xz": getattr(self, "shared_image_xz", None),
                "shared_image_zy": getattr(self, "shared_image_zy", None),
                "shared_image_xy_rgb": getattr(self, "shared_image_xy_rgb", None),
                "shared_image_xy_hcl": self.shared_image_xy_hcl,
                "shared_fingerprint": self.shared_fingerprint,
            }
        )
        return self.preview_repository.get_preview_image(projection, rgb)

    def getPreviewHclImage(self):
        """
        Get the HCL preview image used by COLOR_LIFETIME rendering.
        """
        return self.preview_repository.get_hcl_image()

    def getPreviewFlatData(self, frame=0, channel=10):
        """
        Get the preview flat data
        """
        return self.shared_image_xy.get_numpy_handle()[:, :].flatten()

    def get_registers_configuration(self):
        """
        Get the registers configuration
        """
        return self.registers_configuration

    def update_shared_dict(self, ndict=None):
        """
        Update the shared dictionary
        """
        self.shared_dict.update({} if ndict is None else ndict)

    def read_shared_dict(self):
        """
        Read the shared dictionary
        """
        return dict(self.shared_dict)

    def get_FIFO_status(self):
        """
        Get the status of the FIFO
        """
        return self.shared_dict["FIFO_status"], self.shared_dict["FIFOAnalog_status"]

    def trace_reset(self):
        """
        Reset the trace process
        """
        self.previewProcess.trace_reset()

    def FCS_reset(self):
        """
        Reset the FCS process
        """
        self.previewProcess.FCS_reset()

