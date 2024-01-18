import numpy as np
import multiprocessing as mp
#from UltraDict import UltraDict

from PySide2.QtCore import QObject

from ..libs.processes.data_pre_process import DataPreProcess
from ..libs.processes.acquisition_loop_process import AcquisitionLoopProcess
from ..libs.fpga_handle import FpgaHandle
from ..libs.print_dec import print_dec
from ..libs.mp_shared_array import MemorySharedNumpyArray


class SpadFcsManager(QObject):
    def __init__(self, filename="bitfiles/MyBitfileUSB.lvbitx", address="RIO0", channels=25):
        super().__init__()
        # def __init__(self, filename="C:/Users/madonato/PycharmProjects/pyspad-fcs/bitfiles/laser_wait4.lvbitx", address="RIO0"):
        self.channels = channels
        self.dim_detector = int(np.sqrt(self.channels))
        # self.activate_rgb = False

        self.niAddr = address
        self.bitfile = filename
        self.timeout_fifos = 0.5e6
        # self.fifo = None
        # self.nifpga_session = None
        self.fpga_handle = None
        self.shared_arrays_ready = False

        self.channels = 25

        self.mp_manager = mp.Manager()

        # self.ultra_dict_inst = UltraDict({}, shared_lock=True, full_dump_size=10000)
        # self.shared_dict = UltraDict(
        #     {}, shared_lock=True, full_dump_size=10000
        # )  # self.mp_manager.dict()

        self.ultra_dict_inst = self.mp_manager.dict()
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
            "#pixels": 512,
            "#lines": 512,
            "#frames": 1,
            "stop": False,
            "Run": False,
            "L1": 1,
            "L2": 2,
            "L3": 3,
            "L4": 4,
            # 'LaserOffAfterMeasurement' : False,
        }
        self.requested_depth = 100000
        self.actual_depth = 0

        self.timebins_per_pixel = 0
        self.time_resolution = 0

        self.dim_x = 0
        self.dim_y = 0
        self.dim_z = 0
        self.dim_rep = 0
        # self.acquisitionThread = Thread()
        self.previewProcess = None  # mp.Process()
        self.expected_raw_data = 0
        self.expected_raw_data_per_frame = 0
        # self.dataCounts = None
        self.registers_configuration = {}
        # self.raw_data_buffer = None
        # self.default_destination_folder = ""
        # self.previewEnabled = False

        self.shared_memory_buffer = None
        self.shared_image_xy = None
        self.shared_fingerprint = None
        self.shared_fingerprint_mask = None

        self.is_connected = False

        self.fifo_chuck_size = 10

        self.acquisition_done_event = mp.Event()
        self.acquisition_almost_done_event = mp.Event()
        self.acquisition_run_event = mp.Event()
        self.acquisition_stop_event = mp.Event()
        self.activate_preview_event = mp.Event()

        self.autocorrelation_maxx = 20

        self.trace_bins = 30000
        self.trace_sample_per_bins = 10000

        self.preview_buffer_size_in_words = 15000
        self.len_fifo_prebuffer = 0
        self.activated_fifos_list = []

        self.DFD_Activate = False
        self.snake_walk = False

        self.use_rust_fifo = True

        self.debug = False

    def __del__(self):
        print_dec("Destructor called.")

    def set_channels(self, ch):
        print_dec("Channels", ch)
        self.channels = ch
        self.dim_detector = int(np.sqrt(self.channels))

    def activateShowPreview(self, enable):
        print_dec("activate_show_preview", enable)
        self.activate_show_preview = enable

    def setActivatedFifo(self, fifos_list):
        print_dec("self.activated_fifos_list", fifos_list)
        self.activated_fifos_list = fifos_list

    def acquisition_stop(self):
        self.acquisition_stop_event.set()
        self.acquisition_run_event.clear()

    def acquisition_run(self):
        self.acquisition_stop_event.clear()
        self.acquisition_run_event.set()

    def acquisition_done_reset(self):
        self.acquisition_done_event.clear()

    def acquisition_almost_done_reset(self):
        self.acquisition_almost_done_event.clear()

    def acquisition_is_done(self):
        return self.acquisition_done_event.is_set()

    def acquisition_is_almost_done(self):
        return self.acquisition_almost_done_event.is_set()


    def set_activate_preview(self, active=True):
        if active:
            self.activate_preview_event.set()
            print_dec("self.activate_preview_event.set()")
        else:
            self.activate_preview_event.clear()
            print_dec("self.activate_preview_event.clear()")

    def set_activate_DFD(self, activate=True):
        print_dec("set_activate_DFD() set to ", activate)
        self.DFD_Activate = activate

    def set_activate_snake_walk(self, activate=True):
        print_dec("set_activate_snake_walk() set to ", activate)
        self.snake_walk = activate

    # def set_default_destination_folder(self, folder=""):
    #     self.default_destination_folder = folder

    def set_bit_file(self, bitfile=""):
        print_dec("set_bit_file", bitfile)
        self.bitfile = bitfile

    def set_ni_addr(self, niAddr=""):
        print_dec("set_ni_addr", niAddr)
        self.niAddr = niAddr

    def set_bit_file_second_fpga(self, bitfile=""):
        print_dec("set_bit_file 2nd FPGA", bitfile)
        self.bitfile2 = bitfile

    def set_ni_addr_second_fpga(self, niAddr=""):
        print_dec("set_ni_addr 2nd FPGA", niAddr)
        self.niAddr2 = niAddr


    def set_requested_depth(self, requested_depth):
        print_dec("requested_depth", requested_depth)
        self.requested_depth = requested_depth

    def set_preview_buffer_size_in_words(self, preview_buffer_size_in_words):
        print_dec("preview_buffer_size_in_words", preview_buffer_size_in_words)
        self.preview_buffer_size_in_words = preview_buffer_size_in_words

    def set_len_fifo_prebuffer(self, len_fifo_prebuffer):
        self.len_fifo_prebuffer = len_fifo_prebuffer

    def set_timeout_fifos(self, timeout):
        print_dec("set_timeout_fifos", timeout)
        self.timeout_fifos = timeout

    def connect(self, initial_registers={}, list_fifos=[]):
        print_dec("FPGA connect()")
        # self.nifpga_session = nifpga.Session(self.bitfile, self.niAddr)
        try:
            self.fpga_handle = FpgaHandle(
                bitfile=self.bitfile,
                ni_address=self.niAddr,
                mp_manager=self.mp_manager,
                requested_depth=self.requested_depth,
                list_fifos=["FIFO"],
                ultra_dict_inst=self.ultra_dict_inst,
                debug=self.debug,
                use_rust_fifo=self.use_rust_fifo,
                timeout_fifos=self.timeout_fifos,
                bitfile2=self.bitfile2,
                ni_address2=self.niAddr2,
            )
            self.is_connected = True
        except Exception as e:
            self.is_connected = False
            print_dec("connect ERROR", repr(e))
            raise ("ERROR")
        print_dec(".is_conneccted", self.is_connected)

        self.update_chuck()

        self.fpga_handle.run(initial_registers)
        print_dec("self.fpga_handle.run()")

    def set_filename_h5(self, filename):
        self.filenameh5 = filename

    def set_fingerprint_mask(self, fingerprint_mask):
        self.shared_fingerprint_mask.get_numpy_handle()[:] = np.copy(fingerprint_mask)

    def set_use_rust_fifo(self, value=True):
        self.use_rust_fifo = value

    def run(self):
        activate_preview = self.activate_preview_event.is_set()

        print_dec("spadfcsmanager.run()")

        print_dec("activate_preview", activate_preview)
        print_dec("fpga_process.runed from run")
        self.readRegistersDict()
        print_dec("spadfcsmanager.registers_configuration")
        print_dec("spadfcsmanager.expected_raw_data", self.expected_raw_data)

        ### ADD HERE

        self.fpga_handle.set_list_fifos_to_read_continously(self.activated_fifos_list)

        self.shared_autocorrelation = MemorySharedNumpyArray(
            dtype=float, shape=[2, self.autocorrelation_maxx], sampling=0, lock=True
        )

        self.shared_trace = MemorySharedNumpyArray(
            dtype=np.int64, shape=[2, self.trace_bins], sampling=0, lock=True
        )

        self.shared_image_xy_rgb = MemorySharedNumpyArray(
            dtype=np.int64, shape=[self.dim_y, self.dim_x, 3], sampling=0, lock=True
        )

        self.shared_image_xy = MemorySharedNumpyArray(
            dtype=np.int64, shape=[self.dim_y, self.dim_x], sampling=0, lock=True
        )

        self.shared_image_xz = MemorySharedNumpyArray(
            dtype=np.int64, shape=[self.dim_z, self.dim_x], sampling=0, lock=True
        )

        self.shared_image_zy = MemorySharedNumpyArray(
            dtype=np.int64, shape=[self.dim_y, self.dim_z], sampling=0, lock=True
        )

        self.shared_fingerprint = MemorySharedNumpyArray(
            dtype=np.uint64,
            shape=[
                6,
                self.dim_detector,
                self.dim_detector,
            ],  # [x,y,0] cumulative figerprint [x,y,1] last fingerprint
            sampling=0,
            lock=True,
        )

        self.shared_fingerprint_mask = MemorySharedNumpyArray(
            dtype=np.uint8,
            shape=[self.dim_detector * self.dim_detector],
            sampling=0,
            lock=True,
        )
        self.shared_fingerprint_mask.get_numpy_handle()[:] = np.ones(
            self.dim_detector * self.dim_detector, dtype=np.uint8
        )
        # self.shared_index = mp.Value("i",0)
        # , self.dim_z

        self.data_queue = {"FIFO": mp.Queue(), "FIFOAnalog": mp.Queue()}

        self.loc_acquired = {"FIFO": mp.Value("i", 0), "FIFOAnalog": mp.Value("i", 0)}

        self.last_preprocessed_len = {
            "FIFO": mp.Value("i", 0),
            "FIFOAnalog": mp.Value("i", 0),
        }

        self.loc_previewed = {"FIFO": mp.Value("i", 0), "FIFOAnalog": mp.Value("i", 0)}

        self.dtype_data_queue = {
            "FIFO": np.uint64,
            # "FIFO": np.uint64,
            "FIFOAnalog": np.uint64,
        }

        self.number_of_threads_h5 = mp.Value("i", 0)

        self.trace_pos = mp.Value("i", 0)
        # self.acquisitionThread = AcquireFIFOinBackground(self.queue,
        #                                                  self.fifo)

        self.dataProcess = DataPreProcess(
            self.fpga_handle.configuration["queueFifoRead"],
            # self.shared_memory_buffer,
            self.loc_acquired,
            self.last_preprocessed_len,
            self.data_queue,
            self.dtype_data_queue,
            len_buffer=self.len_fifo_prebuffer,
            debug=self.debug,
            use_rust_fifo=self.use_rust_fifo,
        )
        shared_objects = {
            "activated_fifos_list": self.activated_fifos_list,
            "loc_acquired": self.loc_acquired,
            "loc_previewed": self.loc_previewed,
            "shared_image_xy_rgb": self.shared_image_xy_rgb,
            "shared_image_xy": self.shared_image_xy,
            "shared_image_xz": self.shared_image_xz,
            "shared_image_zy": self.shared_image_zy,
            "shared_fingerprint": self.shared_fingerprint,
            "shared_autocorrelation": self.shared_autocorrelation,
            "shared_trace": self.shared_trace,
            "shared_fingerprint_mask": self.shared_fingerprint_mask,
            "number_of_threads_h5": self.number_of_threads_h5,
            "autocorrelation_maxx": self.autocorrelation_maxx,
            "trace_bins": self.trace_bins,
            "trace_sample_per_bins": self.trace_sample_per_bins,
            "trace_pos": self.trace_pos,
        }

        self.shared_dict["shape"] = [self.dim_x, self.dim_y, self.dim_z]
        self.shared_dict["channels"] = self.channels
        self.shared_dict["timebins_per_pixel"] = self.timebins_per_pixel
        self.shared_dict["time_resolution"] = self.time_resolution
        self.shared_dict["expected_raw_data"] = self.expected_raw_data
        self.shared_dict[
            "expected_raw_data_per_frame"
        ] = self.expected_raw_data_per_frame
        self.shared_dict["filenameh5"] = self.filenameh5

        print_dec("self.activate_show_preview", self.activate_show_preview)
        self.shared_dict.update(
            {
                "activate_show_preview": self.activate_show_preview,
                "current_z": 0,
                "current_rep": 0,
                "total_photon": 0,
                "FIFO_status": 0,
                "FIFOAnalog_status": 0,
                "preview_buffer_size_in_words": self.preview_buffer_size_in_words,
                "last_packet_size": 0,
                "DFD_Activate": self.DFD_Activate,
                "DFD_nBins": 81,
                "snake_walk": self.snake_walk,
            }
        )

        # if self.previewEnabled:
        print_dec("self.previewProcess()")
        self.previewProcess = AcquisitionLoopProcess(
            self.channels,
            shared_objects,
            activate_preview,
            self.data_queue,
            self.acquisition_done_event,
            self.acquisition_almost_done_event,
            self.shared_dict,
            debug=self.debug,
        )

        self.shared_arrays_ready = True
        print_dec("self.dataProcess.start()")
        self.dataProcess.start()
        # self.acquisitionThread.start()
        # if self.previewEnabled:
        self.previewProcess.start()
        # self.nifpga_session.run()
        self.fpga_handle.runfpga()

    def previewProcess_isAlive(self):
        try:
            return self.previewProcess.is_alive()
        except:
            return False

    def dataProcess_isAlive(self):
        try:
            return self.dataProcess.is_alive()
        except:
            return False

    def freeMemory(self):
        self.shared_image_xy = None

    def setRegistersDict(self, myconf):
        # print_dec("setRegistersDict")
        temp_dict = {}
        for i in myconf:
            if myconf[i] is not None:
                print_dec(i, myconf[i])
                # self.nifpga_session.registers[i].write(myconf[i])
                if self.is_connected:
                    self.fpga_handle.register_write(i, myconf[i])
                    temp_dict[i] = myconf[i]
            else:
                print_dec("myconf is None")
        # print(self.registers_configuration)
        self.registers_configuration.update(temp_dict)

    def readRegistersDict(self):
        print_dec("readRegistersDict()")
        if self.is_connected:
            self.registers_configuration.update(self.fpga_handle.register_read_all())
            print_dec(
                "readRegistersDict self.registers_configuration:",
                self.registers_configuration,
            )
        else:
            print_dec("register_read_all() not called due to FPGAhandle not connected")

        self.timebins_per_pixel = self.registers_configuration["#timebinsPerPixel"]
        self.time_resolution = self.registers_configuration["Cx"] / 40.0

        self.dim_x = self.registers_configuration["#pixels"]
        self.dim_y = self.registers_configuration["#lines"]
        self.dim_z = self.registers_configuration["#frames"]
        self.dim_rep = self.registers_configuration["#repetition"] - 1

        if self.channels == 25:
            self.expected_raw_data_per_frame = (
                2 * self.timebins_per_pixel * self.dim_x * self.dim_y
            )
            print_dec("self.expected_raw_data_per_frame calculated for 25 channels ",self.expected_raw_data_per_frame)
        elif self.channels == 49:
            self.expected_raw_data_per_frame = (
                    8 * self.timebins_per_pixel * self.dim_x * self.dim_y
            )
            print_dec("self.expected_raw_data_per_frame calculated for 49 channels", self.expected_raw_data_per_frame)

        else:
            print_dec("self.expected_raw_data_per_frame DISASTER")

        self.expected_raw_data = (
            self.expected_raw_data_per_frame * self.dim_z * self.dim_rep
        )

        self.update_chuck()

    def update_chuck(self):
        try:
            self.timebins_per_pixel = self.registers_configuration["#timebinsPerPixel"]
        except:
            self.timebins_per_pixel = self.default_configuration["#timebinsPerPixel"]

        if self.channels==25:
            self.fifo_chuck_size = 2 * self.timebins_per_pixel
            print_dec("update_chuck self.channels == 25")
        elif self.channels == 49:
            self.fifo_chuck_size = 8 * self.timebins_per_pixel
            print_dec("update_chuck self.channels == 49")

        # self.fifo_chuck_size = 2 * max(self.timebins_per_pixel, 100)

        self.fpga_handle.set_fifo_chuck_size(self.fifo_chuck_size)
        self.fpga_handle.set_expected_raw_data(self.expected_raw_data)
        # self.fpga_handle.set_expected_raw_data(self.expected_raw_data_per_frame)

        print_dec(
            "Updated expected_raw_data and fifo_chuck_size",
            self.expected_raw_data,
            self.fifo_chuck_size,
        )

    def getCurrentPreviewElement(self, fifo_name="FIFO"):
        return self.loc_previewed[fifo_name].value * 2

    def getCurrentAcquistionElement(self, fifo_name="FIFO"):
        return self.loc_acquired[fifo_name].value

    def getLastPreprocessedLen(self, fifo_name="FIFO"):
        return self.last_preprocessed_len[fifo_name]

    def getExpectedFifoElements(self):
        return self.expected_raw_data

    def getExpectedFifoElementsPerFrame(self):
        return self.expected_raw_data_per_frame

    # def getCurrentData(self):
    #     return self.acquisitionThread.data

    def stopFPGA(self):
        print_dec("stopAcquisition.stop()")
        self.fpga_handle.stop()

    def stopAcquisition(self):
        print_dec("stopAcquisition.stop()")
        self.dataProcess.stop()
        self.is_connected = False

    def stopPreview(self):
        print_dec("myfpga.stopPreview()")
        # if self.previewEnabled:
        self.previewProcess.stop()
        self.previewProcess.join()
        print_dec("self.previewThread.join() done")

    def get_current_z(self):
        return self.shared_dict["current_z"]

    def get_current_rep(self):
        return self.shared_dict["current_rep"]

    def get_total_photon(self):
        return self.shared_dict["total_photon"]

    def get_number_of_threads_h5(self):
        return self.number_of_threads_h5.value

    def reset(self):
        self.fpga_handle.reset()

    def getFingerprint(self):
        return self.shared_fingerprint.get_numpy_handle()[1, :, :]

    def getFingerprintCumulative(self):
        return self.shared_fingerprint.get_numpy_handle()[0, :, :]

    def getFingerprintCumulativeLast10000(self):
        return self.shared_fingerprint.get_numpy_handle()[2, :, :]

    def getFingerprintCumulativeLastFrame(self):
        return self.shared_fingerprint.get_numpy_handle()[3, :, :]

    def getFingerprintSaturation(self):
        return self.shared_fingerprint.get_numpy_handle()[4, :, :]

    def getImage(self):
        # self.dataCounts = np.zeros((self.dim_x*self.dim_y*self.dim_z*self.timebins_per_pixel, self.channels),
        #                           dtype = np.uint64)
        # #print(id(self.shared_memory_buffer))
        # #print(self.shared_memory_buffer.get_numpy_handle())
        # ddd = np.copy(self.shared_memory_buffer.get_numpy_handle())
        # print(ddd.shape, type(ddd), ddd.sum())
        # convertRawDataToCounts(ddd, self.dataCounts)
        # d = self.dataCounts.reshape(self.dim_z,
        #                             self.dim_y,
        #                             self.dim_x,
        #                             self.timebins_per_pixel,
        #                             self.channels)
        d = np.memmap(
            "test.raw",
            dtype="uint16",
            mode="r",
            shape=(
                self.dim_z,
                self.dim_y,
                self.dim_x,
                self.timebins_per_pixel,
                self.channels,
            ),
        )
        print_dec(d.shape, type(d))
        return d

    def setSelectedChannel(self, ch):
        self.update_shared_dict({"channel": ch})

    def set_autocorrelation_maxx(self, value=20):
        print("set_autocorrelation_maxx", value)
        self.autocorrelation_maxx = value

    def set_trace_bins(self, trace_bins=30000):
        self.trace_bins = trace_bins

    def set_trace_sample_per_bins(self, trace_sample_per_bins=10000):
        self.trace_sample_per_bins = trace_sample_per_bins

    def getAutocorrelation(self):
        return self.shared_autocorrelation.get_numpy_handle()

    def getTrace(self):
        if self.DFD_Activate:
            a = self.shared_trace.get_numpy_handle() * 1.0
            a[1, :] = a[1, :]
            a[0, :] = a[0, :]
            return a, self.trace_pos.value
        else:
            a = self.shared_trace.get_numpy_handle() * 1.0
            a[1, :] = a[1, :] / (
                self.trace_sample_per_bins * self.time_resolution * 1e-6
            )
            a[0, :] = a[0, :] * self.time_resolution * 1e-6 * self.trace_sample_per_bins
            return a, self.trace_pos.value

    def getPreviewImage(self, projection="xy", rgb=False):
        # print(self.previewThread.current_x,self.previewThread.current_y,self.previewThread.current_f, self.previewThread.data_len)
        if projection == "xy":
            shared_image = self.shared_image_xy
        elif projection == "zy":
            shared_image = self.shared_image_zy
        elif projection == "xz":
            shared_image = self.shared_image_xz
        elif projection == "yx":
            shared_image = self.shared_image_xy
        elif projection == "yz":
            shared_image = self.shared_image_zy
        elif projection == "zx":
            shared_image = self.shared_image_xz

        if rgb == True:
            shared_image = self.shared_image_xy_rgb

        shared_image.get_lock().acquire()
        array = np.copy(shared_image.get_numpy_handle()[:])
        shared_image.get_lock().release()
        return array

    def getPreviewFlatData(self, frame=0, channel=10):
        return self.shared_image_xy.get_numpy_handle()[:, :].flatten()

    def get_registers_configuration(self):
        return self.registers_configuration

    def update_shared_dict(self, ndict={}):
        self.shared_dict.update(ndict)

    def read_shared_dict(self):
        return dict(self.shared_dict)

    def get_FIFO_status(self):
        return self.shared_dict["FIFO_status"], self.shared_dict["FIFOAnalog_status"]

    def trace_reset(self):
        self.previewProcess.trace_reset()

    def FCS_reset(self):
        self.previewProcess.FCS_reset()
