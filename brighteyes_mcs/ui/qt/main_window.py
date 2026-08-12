"""main_window.py: BrightEyes-MCS - MainWindow."""
__author__ = "Mattia Donato"
__copyright__ = "Copyright (C) 2023, Istituto Italiano di Tecnologia"
__license__ = "GPL"
from brighteyes_mcs import __version__
__email__ = ["mattia.donato@iit.it", "giuseppe.vicidomini@iit.it"]

# pyside6-uic main_design.ui -o main_design.py
#
# This module is the GUI/controller entry point: it wires the Designer UI to the
# acquisition manager, the live preview widgets, and the background processes.

from PySide6.QtWidgets import QMainWindow, QSplashScreen, QFileDialog
from PySide6.QtWidgets import QMessageBox, QTableWidgetItem, QLabel
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QComboBox,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QPushButton,
    QFrame,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QTextBrowser,
    QHeaderView,
    QProgressDialog,
    QMenu,
)
from PySide6.QtGui import QScreen  # Replaces QDesktopWidget

from PySide6.QtCore import (
    Slot,
    QTimer,
    Qt,
    QDir,
    QFile,
    QCoreApplication,
    QElapsedTimer,
    QIODevice,
    QBuffer
)
from PySide6.QtCore import QEvent, QRectF, QThread, QMutex, QMimeData, QUrl
from PySide6.QtGui import QPixmap, QIcon, QGuiApplication, QDesktopServices

from datetime import datetime

from .main_window_design import Ui_MainWindowDesign
from .flim_image_view import FlimImageView, ModifierGatedViewBox
from .qt_locale import install_scientific_locale
from .support import DoubleClickDoubleSpinBox, PluginSignals, RectROIWithoutHandles

from .console_widget import ConsoleWidget
from ...acquisition.manager import McsManager
from ..table_manager import TableManager

from brighteyes_mcs.logging_setup import logger
from .dict_to_tree import TreeModel
from ...hardware.ttm import TtmRemoteManager
from ...application.plugin_service import PluginManager
from ...api import FastAPIServerThread
from ...storage.raw import convert_raw_acquisition, metadata_filename, raw_output_files
from ...acquisition.detectors.models import (
    DETECTOR_SPAD_ARRAY,
    detector_uses_pi23_pipeline,
    normalize_detector_model,
)
from ...storage.legacy_config import LegacyConfigurationCodec, NumpyJSONEncoder
from ...storage.h5_schema import legacy_gui_metadata, legacy_raw_stream_metadata
from ...storage.legacy_names import LEGACY_H5_REGISTER_NAME_MAP
from ..controllers import ConfigurationController, LifecycleController, PreviewController
from ...application.paths import (
    ensure_user_configuration,
    resource_path,
    resolve_legacy_path,
    writable_config_path,
    write_default_pointer,
)

import numpy as np
import time

import psutil
import requests

import json
import h5py
import traceback
from ...storage.h5 import H5Manager

import os, sys

import socket
from pathlib import Path

import pyqtgraph as pg

try:
    import imageio as iio
except:
    print(
        "Warning: 'import imageio' failed. \n"
        + "This function is optional so the software will run but some functions  not work.\n"
    )


# ================== end of imports ====================================

pg.setConfigOption("background", "k")
pg.setConfigOption("foreground", "w")


class MainWindow(QMainWindow):
    """
    Main window class for the BrightEyes-MCS application.

    Attributes:
        http_server_thread (FastAPIServerThread): Thread for the HTTP server.
        guiReadyFlag (bool): Flag indicating if the GUI is ready.
        init_ready (bool): Flag indicating if the initialization is ready.
        splash (QSplashScreen): Splash screen for the application.
    """

    PROGRAM_STATE_IDLE = "idle"
    PROGRAM_STATE_ACQUISITION = "acquisition"
    PROGRAM_STATE_PREVIEW = "preview"
    PROGRAM_STATE_ACQUISITION_DONE = "acquisition_done"
    PROGRAM_STATES = (
        PROGRAM_STATE_IDLE,
        PROGRAM_STATE_ACQUISITION,
        PROGRAM_STATE_PREVIEW,
        PROGRAM_STATE_ACQUISITION_DONE,
    )
    FPGA_IDLE_TIMEOUT_SECONDS = 5.0
    FPGA_WATCHDOG_INTERVAL_MS = 500

    def __init__(self, args=None):
        install_scientific_locale()
        self.http_server_thread = None
        self.configuration_controller = ConfigurationController()
        self._loaded_configuration_payload = {}
        self.lifecycle_controller = LifecycleController()
        self.guiReadyFlag = False
        self.init_ready = False
        primary_screen = QGuiApplication.primaryScreen()
        splash_image = QPixmap(str(resource_path("images/splash.png"))).scaled(
            primary_screen.size().width() // 2,
            primary_screen.size().height() // 2,
            aspectMode=Qt.AspectRatioMode.KeepAspectRatio,
            mode=Qt.TransformationMode.SmoothTransformation
        )

        self.splash = QSplashScreen(splash_image)
        self.splash.setWindowFlags(Qt.WindowType.SplashScreen | Qt.WindowType.WindowStaysOnTopHint)

        LICENSE = (
                """BrightEyes-MCS (Version: %s)                  
        Author: Mattia Donato 
        License: General Public License version 3 (GPL v3)        
        Copyright © 2023 Istituto Italiano di Tecnologia
                        
        This program comes with ABSOLUTELY NO WARRANTY. 
        """
                % __version__
        )

        if "debug" in sys.argv:
            self.splash.showMessage(
                LICENSE + "\n" + "UNTESTED                                   \n" * 15,
                Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight,
                "white",
            )
        else:
            self.splash.showMessage(
                LICENSE,
                Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight,
                "white",
            )

        self.splash.show()

        super(MainWindow, self).__init__()

        qp = QPixmap(str(resource_path("images/icon.png")))
        appIcon = QIcon(qp)
        self.setWindowIcon(appIcon)

        self.preset_dict = {}

        self.spad_channels = 25
        self.spad_channels_x = 5
        self.spad_channels_y = 5
        self.started_preview = False
        self.started_normal = False
        self.program_state = self.PROGRAM_STATE_IDLE
        self.program_state_changed_at = self._make_status_timestamp()
        self.program_state_reason = "startup"
        self.last_requested_filename = None
        self.last_saved_filename = None
        self.last_completed_filename = None
        self.last_acquisition_started_at = None
        self.last_preview_started_at = None
        self.last_acquisition_completed_at = None
        self.acquisition_run_id = 0
        self.preview_run_id = 0
        self.completed_acquisition_count = 0
        self._pending_program_state_after_stop = None
        self._shutdown_started = False
        self._shutdown_complete = False
        self.raw_stream_mode = False
        self.raw_stream_output_files = {}
        self.console_widget = None
        self.selected_channel = None
        self.webcam_capture = None
        self.ui = Ui_MainWindowDesign()
        self.ui.setupUi(self)
        self._latest_status_registers = {}
        self._monitored_registers = {}
        self._monitor_started_at = time.monotonic()
        self._last_circular_debug_signature = None

        self.monitor_plot_widget = pg.PlotWidget(self)
        self.monitor_plot_widget.setLabel("bottom", "Time", units="s")
        self.monitor_plot_widget.setLabel("left", "Register value")
        self.monitor_plot_widget.showGrid(x=True, y=True, alpha=0.25)
        self.monitor_plot_widget.addLegend()
        self.ui.gridLayout_monitorPlot.addWidget(self.monitor_plot_widget, 0, 0)
        self.ui.pushButton_resetMonitor.clicked.connect(self.resetMonitor)

        self.circular_preview_plot_item = pg.PlotItem()
        self.circular_preview_plot_item.setLabel("bottom", "x", units="um")
        self.circular_preview_plot_item.setLabel("left", "y", units="um")
        self.circular_preview_widget = FlimImageView(
            self, view=self.circular_preview_plot_item
        )
        self.circular_scan_points = pg.PlotDataItem(
            pen=pg.mkPen("#fff176", width=1.5),
            symbol="o",
            symbolSize=4,
            symbolPen=pg.mkPen("#fffde7", width=1),
            symbolBrush=pg.mkBrush("#ff7043"),
        )
        self.circular_preview_widget.addItem(self.circular_scan_points)
        self.circular_scan_first_points = pg.ScatterPlotItem(
            pen=pg.mkPen("#ffffff", width=1.5),
            brush=pg.mkBrush("#00e676"),
            size=9,
            symbol="o",
        )
        self.circular_preview_widget.addItem(
            self.circular_scan_first_points
        )
        self.ui.gridLayout_circularPreview.addWidget(
            self.circular_preview_widget, 0, 0
        )
        self.ui.pushButton_updateCircularView.clicked.connect(
            self.updateCircularPreview
        )
        self.lissajous_mini_plot = pg.PlotWidget(self)
        self.lissajous_mini_plot.setFixedHeight(105)
        self.lissajous_mini_plot.hideAxis("bottom")
        self.lissajous_mini_plot.hideAxis("left")
        self.lissajous_mini_plot.setMouseEnabled(x=False, y=False)
        self.lissajous_mini_plot.setMenuEnabled(False)
        self.lissajous_mini_plot.setAspectLocked(True)
        self.lissajous_mini_curve = self.lissajous_mini_plot.plot(
            pen=pg.mkPen("#00d8ff", width=2)
        )
        self.lissajous_mini_points = pg.ScatterPlotItem(
            pen=pg.mkPen("#fff176", width=1),
            brush=pg.mkBrush("#ff7043"),
            size=7,
            symbol="o",
        )
        self.lissajous_mini_plot.addItem(self.lissajous_mini_points)
        self.lissajous_mini_first_point = pg.ScatterPlotItem(
            pen=pg.mkPen("#ffffff", width=1),
            brush=pg.mkBrush("#00e676"),
            size=10,
            symbol="o",
        )
        self.lissajous_mini_plot.addItem(
            self.lissajous_mini_first_point
        )
        self.ui.gridLayout_lissajousMiniPlot.setContentsMargins(0, 0, 0, 0)
        self.ui.gridLayout_lissajousMiniPlot.addWidget(
            self.lissajous_mini_plot, 0, 0
        )
        self.ui.checkBox_lissajous.toggled.connect(
            self.lissajousModeChanged
        )
        self.ui.checkBox_lissajous_opencurve.toggled.connect(
            self.lissajousFrequencyChanged
        )
        self.ui.spinBox_lissajous_omega_x.valueChanged.connect(
            self.lissajousFrequencyChanged
        )
        self.ui.spinBox_lissajous_omega_y.valueChanged.connect(
            self.lissajousFrequencyChanged
        )
        self.ui.spinBox_lissajous_phase_deg.valueChanged.connect(
            self.lissajousFrequencyChanged
        )
        self.ui.spinBox_lissajous_firstposition.valueChanged.connect(
            self.lissajousFrequencyChanged
        )
        self.lissajousModeChanged(
            self.ui.checkBox_lissajous.isChecked()
        )
        for status_tree in (
            self.ui.treeView,
            self.ui.treeView_2,
            self.ui.treeView_3,
        ):
            status_tree.setContextMenuPolicy(
                Qt.ContextMenuPolicy.CustomContextMenu
            )
            status_tree.customContextMenuRequested.connect(
                lambda position, tree=status_tree:
                    self.statusRegisterContextMenu(tree, position)
            )
        for special_channel in (
            "RGBDFD",
            "LIFETIME_HCL",
            "LIFETIME_HSV",
            "LIFETIME_HSL",
            "LIFETIME",
            "QUALITY",
        ):
            if self.ui.comboBox_plot_channel.findText(special_channel) < 0:
                self.ui.comboBox_plot_channel.addItem(special_channel)
        self.ui.label_delta_tau_ns = QLabel("Corr. delta_tau [ns]")
        self.ui.doubleSpinBox_delta_tau_ns = DoubleClickDoubleSpinBox(self)
        self.ui.doubleSpinBox_delta_tau_ns.setDecimals(4)
        self.ui.doubleSpinBox_delta_tau_ns.setRange(0.0, 1e6)
        self.ui.doubleSpinBox_delta_tau_ns.setSingleStep(0.1)
        self.ui.doubleSpinBox_delta_tau_ns.setSuffix(" ns")
        self.ui.pushButton_delta_tau_auto = QPushButton("A", self)
        self.ui.pushButton_delta_tau_auto.setToolTip("Automatic lifetime correction from the cumulative fit")
        self.ui.pushButton_delta_tau_auto.setFixedWidth(28)
        self.ui.gridLayout_4.addWidget(self.ui.label_delta_tau_ns, 2, 6, 1, 1)
        self.ui.gridLayout_4.addWidget(self.ui.doubleSpinBox_delta_tau_ns, 2, 7, 1, 1)
        self.ui.gridLayout_4.addWidget(self.ui.pushButton_delta_tau_auto, 2, 8, 1, 1)
        self.ui.doubleSpinBox_delta_tau_ns.valueChanged.connect(
            self.colorLifetimeDeltaTauChanged
        )
        self.ui.pushButton_delta_tau_auto.clicked.connect(
            self.colorLifetimeDeltaTauUseHistogramMean
        )
        self.ui.label_lifetime_hue_range = QLabel("Hue vis. [0..1]")
        self.ui.doubleSpinBox_lifetime_hue_min = QDoubleSpinBox(self)
        self.ui.doubleSpinBox_lifetime_hue_max = QDoubleSpinBox(self)
        self.ui.checkBox_lifetime_force_quality_full = QCheckBox("Force S/C=1", self)
        self.ui.checkBox_lifetime_force_quality_full.setChecked(True)
        for spinbox, value in (
            (self.ui.doubleSpinBox_lifetime_hue_min, 2.0 / 3.0),
            (self.ui.doubleSpinBox_lifetime_hue_max, 0.0),
        ):
            spinbox.setDecimals(4)
            spinbox.setRange(0.0, 1.0)
            spinbox.setSingleStep(0.01)
            spinbox.setValue(value)
        self.ui.widget_lifetime_hue_range = QWidget(self)
        self.ui.layout_lifetime_hue_range = QHBoxLayout(self.ui.widget_lifetime_hue_range)
        self.ui.layout_lifetime_hue_range.setContentsMargins(0, 0, 0, 0)
        self.ui.layout_lifetime_hue_range.setSpacing(4)
        self.ui.layout_lifetime_hue_range.addWidget(self.ui.label_lifetime_hue_range)
        self.ui.layout_lifetime_hue_range.addWidget(self.ui.doubleSpinBox_lifetime_hue_min)
        self.ui.layout_lifetime_hue_range.addWidget(QLabel("to"))
        self.ui.layout_lifetime_hue_range.addWidget(self.ui.doubleSpinBox_lifetime_hue_max)
        self.ui.layout_lifetime_hue_range.addWidget(self.ui.checkBox_lifetime_force_quality_full)
        self.ui.gridLayout_4.addWidget(self.ui.widget_lifetime_hue_range, 0, 6, 1, 4)
        self.ui.doubleSpinBox_lifetime_hue_min.valueChanged.connect(self.plotSettingsChanged)
        self.ui.doubleSpinBox_lifetime_hue_max.valueChanged.connect(self.plotSettingsChanged)
        self.ui.checkBox_lifetime_force_quality_full.toggled.connect(self.plotSettingsChanged)
        self.updateColorLifetimeShiftControls()
        self.updateImageInteractionHints()
        self.latest_dfd_tau_fit_ns = None
        self.ui.checkBox_trace_dfd_time_axis.toggled.connect(self.plotSettingsChanged)
        self.ui.checkBox_trace_dfd_align_peak.toggled.connect(self.plotSettingsChanged)
        self.ui.doubleSpinBox_trace_dfd_start_percent.valueChanged.connect(self.plotSettingsChanged)
        self.ui.doubleSpinBox_trace_dfd_end_percent.valueChanged.connect(self.plotSettingsChanged)

        self.configuration_helper = self.configuration_helper_init()

        self.ui.pushButton_loadCfg.clicked.connect(self.LoadConfigurationCmd)
        self.ui.pushButton_saveCfg.clicked.connect(self.SaveConfigurationCmd)
        self.ui.pushButton_convertRawAcquisition.clicked.connect(
            self.cmd_convertRawAcquisition
        )
        self.ui.pushButton_fpga_connection_cmd.clicked.connect(
            self.fpgaConnectionButtonClicked
        )

        # self.ui.listWidget.clicked.connect(self.listwidget_click)
        # self.thread_timerPreviewImg_tick = Runnable(self.timerPreviewImg_tick)
        # self.thread_timerConfigurationViewer_tick = Runnable(self.timerConfigurationViewer_tick)

        # The preview timer is the main GUI-side refresh loop for plots and images.
        self.timerPreviewImg = QTimer(None)
        self.timerPreviewImg_tick_mutex = QMutex()
        self.timerPreviewImg.timeout.connect(self.timerPreviewImg_tick)
        self.timerPreviewImg.setInterval(250)

        self.timerConfigurationViewer = QTimer(None)
        self.timerConfigurationViewer_tick_mutex = QMutex()
        self.timerConfigurationViewer.timeout.connect(
            self.timerConfigurationViewer_tick
        )
        self.timerConfigurationViewer.setInterval(500)
        self.timerConfigurationViewer.start()

        self.preview_view_box = ModifierGatedViewBox()
        self.im_widget_plot_item = pg.PlotItem(viewBox=self.preview_view_box)
        self.im_widget_plot_item.setLabel("left", "y (um)")
        self.im_widget_plot_item.setLabel("bottom", "x (um)")

        self.im_plugin_plot_item = pg.PlotItem()
        self.im_plugin_plot_item.setLabel("left", "y (nm)")
        self.im_plugin_plot_item.setLabel("bottom", "x (nm)")

        self.im_plugin = pg.ImageView(self, view=self.im_plugin_plot_item)
        self.ui.gridLayout_pluginImage.addWidget(self.im_plugin)

        # Main live preview view used by the xy/xz/zy projection widgets.
        self.im_widget = FlimImageView(self, view=self.im_widget_plot_item)

        self.ui.gridLayout_im.addWidget(self.im_widget, 0, 0, 1, 3)

        self.im_widget.show()
        self.im_widget.getView().showGrid(True, True)
        self.ui.checkBox_invertPreviewCtrl.toggled.connect(
            self.previewControlModeChanged
        )
        self.previewControlModeChanged(
            self.ui.checkBox_invertPreviewCtrl.isChecked()
        )

        im_widget_view_left_ax = self.im_widget.getView().getAxis("left")
        im_widget_view_bottom_ax = self.im_widget.getView().getAxis("bottom")

        im_widget_view_left_ax.setZValue(-1)
        im_widget_view_bottom_ax.setZValue(-1)

        self.im_panorama_widget_plot_item = pg.PlotItem()

        self.im_panorama_widget = pg.ImageView(
            self, view=self.im_panorama_widget_plot_item
        )
        self.ui.gridLayout_22.addWidget(self.im_panorama_widget)

        self.im_panorama_widget.show()

        # The trace/FCS widgets are updated from shared-memory data produced by the
        # acquisition loop process.
        self.trace_widget = pg.PlotWidget(self)
        self.trace_widget.setToolTip("Double-click for reset the trace")
        self.trace_widget.setLabel("left", "Freq.", "Hz")
        self.trace_widget.setLabel("bottom", "Time", "s")
        self.trace_widget.hideAxis("top")
        self.trace_widget.showAxis("bottom")
        self.ui.gridLayout_trace.setVerticalSpacing(0)
        self.ui.gridLayout_trace.setContentsMargins(0, 0, 0, 0)
        self.trace_separator = QFrame(self)
        self.trace_separator.setFrameShape(QFrame.Shape.HLine)
        self.trace_separator.setFrameShadow(QFrame.Shadow.Plain)
        self.trace_separator.setLineWidth(2)
        self.trace_separator.setMidLineWidth(0)
        self.trace_separator.setStyleSheet("color: rgb(90, 90, 90);")
        self.ui.gridLayout_trace.addWidget(self.trace_widget, 2, 0)
        self.ui.gridLayout_trace.addWidget(self.trace_separator, 1, 0)
        self.trace_widget.show()
        self.trace_widget.setDownsampling(1, True, "mean")
        self.trace_widget.setMinimumSize(100, 130)
        self.trace_dfd_widget = pg.PlotWidget(self)
        self.trace_dfd_widget.setToolTip("Double-click for reset the DFD trace")
        self.trace_dfd_widget.setLabel("left", "Freq.", "Hz")
        self.trace_dfd_widget.setLabel("top", "DFD bin")
        self.trace_dfd_widget.showAxis("top")
        self.trace_dfd_widget.hideAxis("bottom")
        self.ui.gridLayout_trace.addWidget(self.trace_dfd_widget, 0, 0)
        self.trace_dfd_widget.setDownsampling(1, True, "mean")
        self.trace_dfd_widget.setMinimumSize(100, 130)
        self.trace_dfd_widget.hide()
        self.fcs_widget = pg.PlotWidget(self)
        self.fcs_widget.setLabel("left", "Autocorr. (Norm.)")
        self.fcs_widget.setLabel("bottom", "Delay", "s")
        self.ui.gridLayout_FCS.addWidget(self.fcs_widget, 0, 0)
        self.fcs_widget.setLogMode(True, False)
        self.fcs_widget.show()

        self.webcam_widget = pg.ImageView(self)
        self.ui.tabWidget.addTab(self.webcam_widget, "Cam")
        self.ui.tabWidget.show()
        self.webcam_widget.setImage(np.zeros((15, 15)))

        self.ui.tabWidget.repaint()

        self.ui.tabWidget.setCurrentIndex(0)

        self.fingerprint_widget = pg.ImageView(self)
        self.fingerprint_widget.setToolTip("Double-click for select the channel\nCtrl+click for exclude a channel")
        self.ui.gridLayout_microimage.addWidget(self.fingerprint_widget)
        self.fingerprint_widget.show()
        self.fingerprint_mask = np.ones((5, 5), dtype=np.uint8)

        self.im_widget.setPredefinedGradient("thermal")
        self.fingerprint_widget.setPredefinedGradient("thermal")

        self.lock_parameters_changed_call = False
        logger.debug("self.lock_parameters_changed_call UNSET False")

        self.configurationFPGA_dict = {}
        self.configurationGUI_dict = {}

        self.mcs_manager = McsManager()
        self.preview_controller = PreviewController()
        logger.debug("McsManager()")
        self._laser_force_pulsing_previous = None
        self.ui.checkBox_pulsing_forced.toggled.connect(
            self.laserForcePulsingChanged
        )
        self.ui.checkBox_DFD.toggled.connect(
            self.updateLaserForcePulsingAvailability
        )
        self.updateLaserForcePulsingAvailability()
        self._fpga_watchdog_blink_on = False
        # This is a user preference, not a mirror of the live connection
        # state.  Acquisitions connect the FPGA automatically, but that must
        # not opt in to keeping the session alive after the run.
        self._keep_fpga_on_requested = False
        self.timerFPGAWatchdog = QTimer(self)
        self.timerFPGAWatchdog.setInterval(self.FPGA_WATCHDOG_INTERVAL_MS)
        self.timerFPGAWatchdog.timeout.connect(self._fpgaWatchdogTick)
        self.timerFPGAWatchdog.start()
        self._update_fpga_connection_button()
        if hasattr(self.ui, "comboBox_detector_model"):
            self.ui.comboBox_detector_model.currentTextChanged.connect(
                self.detectorModelChanged
            )
            self.detectorModelChanged(self._current_detector_model())
        self.ui.spinBox_compensation_delay.valueChanged.connect(
            self.compensationDelayForSnakeChanged
        )
        self.compensationDelayForSnakeChanged(
            self.ui.spinBox_compensation_delay.value()
        )
        self.apply_dfd_metadata_from_bitfile_name(self.ui.lineEdit_fpgabitfile.text())
        # self.qthread = QThread()
        # self.mcs_manager.moveToThread(self.qthread)
        # debug("mcs_manager.moveToThread()")

        self.ui.checkBoxLockRatio.setText("\U0001f512")

        self.ui.progressBar_frame.setValue(0)
        self.ui.progressBar_repetition.setValue(0)

        self.my_tick_counter = 0

        self.setAcceptDrops(True)
        self.activeFile = False

        self.fingerprint_widget.scene.sigMouseClicked.connect(self.fingerprintClicked)
        self.statusBar_cpu = QLabel("CPU .%%")
        self.statusBar_mem = QLabel("RAM .%%")
        self.statusBar_mousePosition = QLabel("Mouse Position")
        self.statusBar_currentPosition = QLabel("Current X,Y,Z")
        self.statusBar_processes = QLabel("P,D,F")
        self.statusBar_status = QLabel("Move mouse")

        self.ui.statusBar.addPermanentWidget(self.statusBar_cpu)
        self.ui.statusBar.addPermanentWidget(self.statusBar_mem)
        self.ui.statusBar.addPermanentWidget(self.statusBar_mousePosition)
        self.ui.statusBar.addPermanentWidget(self.statusBar_currentPosition)
        self.ui.statusBar.addPermanentWidget(self.statusBar_status)
        self.ui.statusBar.addPermanentWidget(self.statusBar_processes)

        self._update_program_state_label()
        self.ui.statusBar.showMessage("Ready", 5000)

        self.currentImage = np.zeros((512, 512))
        self.currentImage_pos = np.asarray((0, 0, 0))
        self.currentImage_size = np.asarray((2, 2, 2))
        self.currentImage_pixels = np.asarray((2, 2, 2))

        self.autoscale_image = self.ui.checkBox_autoscale_img.isChecked()
        self.autoscale_fingerprint = self.ui.checkBox_autoscale_fingerprint.isChecked()

        self.fingerprint_visualization = self.ui.comboBox_fingerprint.currentIndex()

        self.setSelectedChannel(10)

        self.rect_roi = pg.RectROI(0, 512, 0, 512)
        self.rect_roi_modified_lock = False

        self.im_widget.getView().addItem(self.rect_roi)
        self.im_widget.getView()

        self.rect_roi.hide()



        self.rect_roi_panorama_limit = RectROIWithoutHandles(
            0,
            512,
            0,
            512,
            movable=False,
            rotatable=False,
            resizable=False,
            removable=False,
        )

        self.rect_roi_panorama_limit.setPen(pg.mkPen(color=(50, 50, 50), width=2))

        self.rect_roi_panorama = RectROIWithoutHandles(
            0,
            512,
            0,
            512,
            movable=False,
            rotatable=False,
            resizable=False,
            removable=False,
        )

        self.rect_roi_panorama_modified_lock = False
        self.im_panorama_widget.getView().addItem(self.rect_roi_panorama)
        self.im_panorama_widget.getView().addItem(self.rect_roi_panorama_limit)

        self.im_widget.scene.sigMouseClicked.connect(self.imageClicked)
        self.im_widget.scene.sigMouseMoved.connect(self.imageMoved)

        self.trace_widget.scene().sigMouseClicked.connect(self.traceClicked)
        self.trace_dfd_widget.scene().sigMouseClicked.connect(self.traceClicked)

        self.rect_roi.sigRegionChanged.connect(self.roiModified)
        # self.rect_roi_panorama.sigRegionChanged.connect(self.roi_panoramaModified)

        self.ui.checkBoxLockRatio.setChecked(1)
        self.checkBoxLockRatioChanged()

        self.current_plot_size_x_um = 10
        self.current_plot_size_y_um = 10
        self.current_plot_size_z_um = 0

        self.current_number_px_x = 0
        self.current_number_px_y = 10
        self.current_number_px_z = 0


        self.configurationGUI_dict_beforeStart = {}

        self.im_widget_plot_item.sigRangeChanged.connect(self.axesRangeChanged)

        self.lockspatialSettingsChanged = False
        self.lock_range_changing = False
        self.configurationGUI_dict.update(self.getGUI_data())

        self.markers_list = []
        self.marker_plot = pg.ScatterPlotItem()

        self.marker_plot_circular_scan = pg.ScatterPlotItem()

        self.im_widget.addItem(self.marker_plot)
        self.im_widget.addItem(self.marker_plot_circular_scan)

        # self.fingerprint_ellipsoid = pg.QtGui.QGraphicsEllipseItem(0, 0, 10, 20)

        self.fingerprint_markers_centroid = pg.ScatterPlotItem()
        self.fingerprint_markers_mask = pg.ScatterPlotItem()
        self.fingerprint_saturation_mask = pg.ScatterPlotItem()

        self.fingerprint_widget.addItem(self.fingerprint_markers_centroid)
        self.fingerprint_widget.addItem(self.fingerprint_markers_mask)
        self.fingerprint_widget.addItem(self.fingerprint_saturation_mask)

        # self.tabifyDockWidget(self.ui.dockWidget_pos, self.ui.dockWidget_markers)
        self.tabifyDockWidget(self.ui.dockWidget_pos, self.ui.dockWidget_filename)
        self.tabifyDockWidget(self.ui.dockWidget_pos, self.ui.dockWidget_listfile)

        self.tabifyDockWidget(
            self.ui.dockWidget_preview, self.ui.dockWidget_activatefifo
        )
        # self.tabifyDockWidget(self.ui.dockWidget_preview, self.ui.dockWidget_PMT_adv)
        self.tabifyDockWidget(self.ui.dockWidget_preview, self.ui.dockWidget_laser)
        self.tabifyDockWidget(self.ui.dockWidget_preview, self.ui.dockWidget_adv2)

        # self.tabifyDockWidget(self.ui.dockWidget_preview, self.ui.dockWidget_TTM)

        self.tabifyDockWidget(
            self.ui.dockWidget_statistics, self.ui.dockWidget_AnalogCfg
        )
        self.tabifyDockWidget(
            self.ui.dockWidget_statistics, self.ui.dockWidget_analogOut
        )
        self.tabifyDockWidget(self.ui.dockWidget_statistics, self.ui.dockWidget_debug)
        self.tabifyDockWidget(self.ui.dockWidget_statistics, self.ui.dockWidget_plugins)

        self.tabifyDockWidget(self.ui.dockWidget_trace, self.ui.dockWidget_traceConf)

        self.tabifyDockWidget(
            self.ui.dockWidget_panorama, self.ui.dockWidget_pluginImage
        )

        self.ui.dockWidget_statistics.raise_()
        self.ui.dockWidget_preview.raise_()
        self.ui.dockWidget_pos.raise_()
        self.ui.dockWidget_trace.raise_()
        self.ui.dockWidget_panorama.raise_()

        self.ui.tabWidget.tabBarDoubleClicked.connect(self.tabDoubleClick)

        self.ui.tabWidget.setAcceptDrops(True)

        # PySide6 do not work anymore this
        # self.ui.tabWidget.connect(Signal("dragEnterEvent()"), self.prova)
        # FIXED WITH A VERY BAD HACK - WHICH NEEDS TO BE FIXED!!
        def drag_enter_event(event):
            self.ui.tabWidget.__class__.dragEnterEvent(self.ui.tabWidget, event)
            self.prova()

        self.ui.tabWidget.dragEnterEvent = drag_enter_event

        self.ui.tableWidget.keyPressEvent = self.table_keyPressEvent
        self.ui.tableWidget_markers.keyPressEvent = self.table_markers_keyPressEvent

        self.table_manager = TableManager(
            self.ui.tableWidget, self.configuration_helper
        )
        self.table_lock = True

        self.ttm_remote_manager = None

        self.selectedAutoscaleImg()
        self.selectedAutoscaleFingerprint()

        self.openConsoleWidget()
        if "debug" in sys.argv:
            self.setWindowTitle(
                QCoreApplication.translate(
                    "BrightEyes MCS UNSTABLE UNSTABLE UNSTABLE UNSTABLE UNSTABLE UNSTABLE",
                    "BrightEyes MCS UNSTABLE UNSTABLE UNSTABLE UNSTABLE UNSTABLE UNSTABLE",
                    None,
                )
            )
        else:
            self.setWindowTitle(
                QCoreApplication.translate("BrightEyes MCS", "BrightEyes MCS", None)
            )

        self.ui.progressBar_batch.setStyleSheet("height: 8px;")
        self.ui.progressBar_frame.setStyleSheet("height: 8px;")
        self.ui.progressBar_repetition.setStyleSheet("height: 8px;")

        self.ui.label_ttm_IP.setText(socket.gethostbyname(socket.gethostname()))

        self.plugin_signals = PluginSignals()
        self.plugin_manager = PluginManager(self)
        self.plugin_configuration = {}
        self.plugin_autoload = ["script_launcher", "channel_delay_skew"]
        self.plugin_configuration_files = {
            "channel_delay_skew": "cfg/plugins_cfg/channel_delay_skew.cfg",
            "dfd": "cfg/plugins_cfg/dfd.cfg",
        }
        self._loading_configuration_file = ""

        self.cmd_update_plugin_list()

        self.last_saved_filename = None

        self.clock_base = 40 #MHz
        self.dfd_cycle_mhz = 40

        self.dfd_enable = False
        self.DFD_nbins = 81
        self.snake_walk_Activate_XY = False
        self.snake_walk_Activate_Z = False

        self.setupAnalogOutputGUI()

        self.setStyleSheet(self.styleSheet() +
                           """
        QToolTip { 
        background-color: black; 
        color: white; 
        border: black solid 1px
        }\n"""
                           )
        if self.guiReadyFlag == True:
            QTimer.singleShot(10, self.guiReadyEvent)
            logger.debug("call guiReadyEvent from __init__")

        self.init_ready = True

    def _make_status_timestamp(self):
        """
        Return an ISO 8601 timestamp for status transitions and HTTP payloads.
        """
        return self.lifecycle_controller.timestamp()

    def _update_program_state_label(self):
        """
        Reflect the current runtime state in the GUI status bar when available.
        """
        if hasattr(self, "statusBar_status") and self.statusBar_status is not None:
            self.statusBar_status.setText("State: %s" % self.program_state)

    def _set_program_state(self, state, reason=""):
        """
        Update the main runtime state and keep the GUI label in sync.
        """
        self.lifecycle_controller.transition(self, state, reason)
        self._update_program_state_label()

    def get_state_payload(self):
        """
        Return only the current program state.
        """
        return self.lifecycle_controller.state_payload(self)

    def get_full_status_payload(self):
        """
        Return the extended status payload consumed by the HTTP server.
        """
        return self.lifecycle_controller.full_status_payload(self)

    # @staticmethod
    # def _add_padding_to_plot_widget(plot_widget, padding=0.1):
    #     """
    #     zooms out the view of a plot widget to show 'padding' around the contents of a PlotWidget
    #     :param plot_widget: The widget to add padding to
    #     :param padding: the percentage of padding expressed between 0.0 and 1.0
    #     :return:
    #     """
    #     debug("_add_padding_to_plot_widget")
    #     width = plot_widget.sceneRect().width() * (1.0 + padding)
    #     height = plot_widget.sceneRect().height() * (1.0 + padding)
    #     center = plot_widget.sceneRect().center()
    #     zoom_rect = QRectF(
    #         center.x() - width / 2.0, center.y() - height / 2.0, width, height
    #     )
    #
    #     plot_widget.fitInView(zoom_rect)


    @Slot()
    def httpServerCheckBoxChanged(self):
        """
        Slot for the HTTP server checkbox changed event
        """
        if self.ui.checkBox_httpServer.isChecked():
            self.httpApiServer_start()
        else:
            self.httpApiServer_stop()
    def httpApiServer_start(self):
        """
        Starts the FastAPI HTTP server
        """
        logger.debug("httpApiServer_start()")
        if self.http_server_thread is None:
            self.http_server_thread = FastAPIServerThread(self, self.ui.lineEdit_httpAddr.text(), int(self.ui.lineEdit_httpPort.text()))
            logger.debug("HTTP Server FastAPIServerThread Start")
            self.http_server_thread.start()
            self.ui.label_httpLink.setOpenExternalLinks(True)
            self.ui.label_httpLink.setText('<a href="http://%s:%s/docs">http://%s:%s/docs</a>' %
                                           (self.ui.lineEdit_httpAddr.text(), self.ui.lineEdit_httpPort.text(),
                                            self.ui.lineEdit_httpAddr.text(), self.ui.lineEdit_httpPort.text()))
        else:
            logger.debug("HTTP Server FastAPIServerThread ALREADY RUNNING")

    def httpApiServer_stop(self):
        """
        Stops the FastAPI HTTP server
        """
        logger.debug("htttApiServer_stop()")
        self.http_server_thread.stop()
        logger.debug("HTTP Server FastAPIServerThread Stop")
        self.http_server_thread.join()
        logger.debug("HTTP Server FastAPIServerThread Join")
        self.http_server_thread=None

    def configuration_helper_init(self):
        """
        Return a dictionary with the configuration helper for the GUI elements
        They are used both for configuration saving and loading, and macros.
        """
        configuration_helper = {}

        configuration_helper["fcs"] = (
            "FCS Preview",
            bool,
            self.ui.checkBox_fcs_preview,
            True,
        )
        configuration_helper["circular_active"] = (
            "Circular Motion",
            bool,
            self.ui.checkBox_circular,
            True,
        )
        configuration_helper["circular_radius_nm"] = (
            "Circular Radius (nm)",
            float,
            self.ui.spinBox_circular_radius_nm,
            True,
        )
        configuration_helper["circular_points"] = (
            "Circular Points",
            int,
            self.ui.spinBox_circular_points,
            True,
        )
        configuration_helper["circular_repetition"] = (
            "Circular Repetition",
            int,
            self.ui.spinBox_circular_repetition,
            True,
        )
        configuration_helper["lissajous_active"] = (
            "Lissajous Curve",
            bool,
            self.ui.checkBox_lissajous,
            True,
        )
        configuration_helper["lissajous_open_curve"] = (
            "Open Lissajous Curve",
            bool,
            self.ui.checkBox_lissajous_opencurve,
            True,
        )
        configuration_helper["lissajous_omega_x"] = (
            "Lissajous Omega X",
            int,
            self.ui.spinBox_lissajous_omega_x,
            True,
        )
        configuration_helper["lissajous_omega_y"] = (
            "Lissajous Omega Y",
            int,
            self.ui.spinBox_lissajous_omega_y,
            True,
        )
        configuration_helper["lissajous_phase_deg"] = (
            "Lissajous Rotation Phase (degree)",
            int,
            self.ui.spinBox_lissajous_phase_deg,
            True,
        )
        configuration_helper["lissajous_first_position"] = (
            "Lissajous First Array Position",
            int,
            self.ui.spinBox_lissajous_firstposition,
            True,
        )
        configuration_helper["slave_mode_enable"] = (
            "Slave Mode Enable",
            bool,
            self.ui.checkBox_slavemode_enable,
            False,
        )
        configuration_helper["slave_mode_type"] = (
            "Slave Mode Type",
            str,
            self.ui.comboBox_slavemode_type,
            False,
        )
        configuration_helper["offset_x_um"] = (
            "X Offset (um)",
            float,
            self.ui.spinBox_off_x_um,
            True,
        )
        configuration_helper["offset_y_um"] = (
            "Y Offset (um)",
            float,
            self.ui.spinBox_off_y_um,
            True,
        )
        configuration_helper["offset_z_um"] = (
            "Z Offset (um)",
            float,
            self.ui.spinBox_off_z_um,
            True,
        )

        configuration_helper["offset_x"] = (
            "X Range (V)",
            float,
            self.ui.spinBox_off_x_V,
            False,
        )
        configuration_helper["offset_y"] = (
            "Y Range (V)",
            float,
            self.ui.spinBox_off_y_V,
            False,
        )
        configuration_helper["offset_z"] = (
            "Z Range (V)",
            float,
            self.ui.spinBox_off_z_V,
            False,
        )

        configuration_helper["range_x"] = (
            "X Range (um)",
            float,
            self.ui.spinBox_range_x,
            True,
        )
        configuration_helper["range_y"] = (
            "Y Range (um)",
            float,
            self.ui.spinBox_range_y,
            True,
        )
        configuration_helper["range_z"] = (
            "Z Range (um)",
            float,
            self.ui.spinBox_range_z,
            True,
        )

        configuration_helper["time_resolution"] = (
            "Time Resolution (um)",
            float,
            self.ui.spinBox_timeresolution,
            True,
        )
        configuration_helper["timebin_per_pixel"] = (
            "Time Bin per Pixel",
            int,
            self.ui.spinBox_time_bin_per_px,
            True,
        )
        configuration_helper["nx"] = ("#x", int, self.ui.spinBox_nx, True)
        configuration_helper["ny"] = ("#y", int, self.ui.spinBox_ny, True)
        configuration_helper["nframe"] = ("#frame", int, self.ui.spinBox_nframe, True)
        configuration_helper["nrep"] = (
            "#repetition",
            int,
            self.ui.spinBox_nrepetition,
            True,
        )

        configuration_helper["calib_x"] = (
            "X Calib. (V/um)",
            float,
            self.ui.spinBox_calib_x,
            False,
        )
        configuration_helper["calib_y"] = (
            "Y Calib. (V/um)",
            float,
            self.ui.spinBox_calib_y,
            False,
        )
        configuration_helper["calib_z"] = (
            "Z Calib. (V/um)",
            float,
            self.ui.spinBox_calib_z,
            False,
        )

        configuration_helper["preview_autoscale"] = (
            "Preview Autoscale",
            bool,
            self.ui.checkBox_autoscale_img,
            False,
        )
        configuration_helper["preview_invert_ctrl"] = (
            "Invert Preview Ctrl Behavior",
            bool,
            self.ui.checkBox_invertPreviewCtrl,
            False,
        )
        configuration_helper["projection"] = (
            "Preview Projection",
            str,
            self.ui.comboBox_view_projection,
            True,
        )
        configuration_helper["preview_channel"] = (
            "Preview Ch.",
            str,
            self.ui.comboBox_plot_channel,
            True,
        )
        configuration_helper["fingerprint_visualization"] = (
            "FingerPrint Visual.",
            str,
            self.ui.comboBox_fingerprint,
            False,
        )
        configuration_helper["fingerprint_autoscale"] = (
            "FingerPrint Autoscale",
            bool,
            self.ui.checkBox_autoscale_fingerprint,
            False,
        )
        configuration_helper["ratio_xy_locked"] = (
            "Ratio XY locked",
            bool,
            self.ui.checkBoxLockRatio,
            False,
        )

        configuration_helper["waitOnlyFirstTime"] = (
            "Wait Only First Time",
            bool,
            self.ui.checkBox_waitOnlyFirstTime,
            True,
        )

        configuration_helper["waitAfterFrame"] = (
            "Wait After Laser",
            float,
            self.ui.spinBox_waitAfterFrame,
            True,
        )
        configuration_helper["laserOffAfterMeas"] = (
            "Turn OFF laser after meas.",
            bool,
            self.ui.checkBox_laserOffAfterMeas,
            True,
        )

        configuration_helper["offsetExtra_x"] = (
            "Offset ext. X (V)",
            float,
            self.ui.spinBox_offExtra_x_V,
            False,
        )
        configuration_helper["offsetExtra_y"] = (
            "Offset ext. Y (V)",
            float,
            self.ui.spinBox_offExtra_y_V,
            False,
        )
        configuration_helper["offsetExtra_z"] = (
            "Offset ext. Z (V)",
            float,
            self.ui.spinBox_offExtra_z_V,
            False,
        )

        configuration_helper["min_x_V"] = (
            "Min. X (V)",
            float,
            self.ui.spinBox_min_x_V,
            False,
        )
        configuration_helper["min_y_V"] = (
            "Min. Y (V)",
            float,
            self.ui.spinBox_min_y_V,
            False,
        )
        configuration_helper["min_z_V"] = (
            "Min. Z (V)",
            float,
            self.ui.spinBox_min_z_V,
            False,
        )

        configuration_helper["max_x_V"] = (
            "Max. X (V)",
            float,
            self.ui.spinBox_max_x_V,
            False,
        )
        configuration_helper["max_y_V"] = (
            "Max. Y (V)",
            float,
            self.ui.spinBox_max_y_V,
            False,
        )
        configuration_helper["max_z_V"] = (
            "Max. Z (V)",
            float,
            self.ui.spinBox_max_z_V,
            False,
        )

        # configuration_helper["PMT_Threshold"] = ("PMT Thr. (V)", float, self.ui.spinBox_PMT_Threshold, False)
        # configuration_helper["PMT_Threshold_Min"] = (
        #     "PMT Thr. Min (V)", float, self.ui.spinBox_PMT_Threshold_Min, False)
        # configuration_helper["PMT_Threshold_Max"] = (
        #     "PMT Thr. Max (V)", float, self.ui.spinBox_PMT_Threshold_Max, False)

        configuration_helper["spad_vr0"] = (
            "SPAD VR0",
            bool,
            self.ui.checkBox_SPAD_VR0,
            False,
        )

        configuration_helper["spad_vr1"] = (
            "SPAD VR1",
            bool,
            self.ui.checkBox_SPAD_VR1,
            False,
        )

        configuration_helper["default_offset_x_um"] = (
            "Default Offset X (um)",
            float,
            self.ui.spinBox_default_off_x_um,
            False,
        )
        configuration_helper["default_offset_y_um"] = (
            "Default Offset Y (um)",
            float,
            self.ui.spinBox_default_off_y_um,
            False,
        )
        configuration_helper["default_offset_z_um"] = (
            "Default Offset Z (um)",
            float,
            self.ui.spinBox_default_off_z_um,
            False,
        )

        configuration_helper["default_range_x"] = (
            "Default Range X (um)",
            float,
            self.ui.spinBox_default_range_x,
            False,
        )
        configuration_helper["default_range_y"] = (
            "Default Range Y (um)",
            float,
            self.ui.spinBox_default_range_y,
            False,
        )
        configuration_helper["default_range_z"] = (
            "Default Range Z (um)",
            float,
            self.ui.spinBox_default_range_z,
            False,
        )

        configuration_helper["laser_1_enable"] = (
            "Laser 0 En.",
            bool,
            self.ui.checkBox_laser0,
            True,
        )
        configuration_helper["laser_2_enable"] = (
            "Laser 1 En.",
            bool,
            self.ui.checkBox_laser1,
            True,
        )
        configuration_helper["laser_3_enable"] = (
            "Laser 2 En.",
            bool,
            self.ui.checkBox_laser2,
            True,
        )
        configuration_helper["laser_4_enable"] = (
            "Laser 3 En.",
            bool,
            self.ui.checkBox_laser3,
            True,
        )

        configuration_helper["ch_preview"] = (
            "Preview Channel",
            str,
            self.ui.comboBox_plot_channel,
            True,
        )

        configuration_helper["waitForLaser"] = (
            "Delay Laser (s)",
            float,
            self.ui.spinBox_waitForLaser,
            True,
        )
        configuration_helper["waitAfterFrame"] = (
            "Delay Between Rep (s)",
            float,
            self.ui.spinBox_waitAfterFrame,
            True,
        )

        configuration_helper["defaultFolder"] = (
            "Default Folder",
            str,
            self.ui.lineEdit_destinationfolder,
            False,
        )
        configuration_helper["filename"] = (
            "Filename",
            str,
            self.ui.lineEdit_filename,
            True,
        )

        configuration_helper["spad_channels"] = (
            "SPAD channels",
            str,
            self.ui.comboBox_spad_channels,
            False,
        )

        configuration_helper["detector_model"] = (
            "Detector",
            str,
            self.ui.comboBox_detector_model,
            False,
        )

        configuration_helper["pi23_ip_addr"] = (
            "PI23 IP addr.",
            str,
            self.ui.lineEdit_pi23_ip_addr,
            False,
        )

        configuration_helper["pi23_port"] = (
            "PI23 Port",
            int,
            self.ui.spinBox_pi23_port,
            False,
        )

        configuration_helper["comment"] = (
            "Comment",
            str,
            self.ui.lineEdit_comment,
            True,
        )

        configuration_helper["bitFile"] = (
            "Bit File",
            str,
            self.ui.lineEdit_fpgabitfile,
            False,
        )
        configuration_helper["niAddr"] = (
            "Ni Addr",
            str,
            self.ui.lineEdit_ni_addr,
            False,
        )

        configuration_helper["bitFile2"] = (
            "Bit File 2",
            str,
            self.ui.lineEdit_fpga2bitfile,
            False,
        )
        configuration_helper["niAddr2"] = (
            "Ni Addr 2",
            str,
            self.ui.lineEdit_ni2addr,
            False,
        )

        configuration_helper["spad_cmd_length"] = (
            "SPAD Command Length",
            str,
            self.ui.lineEdit_spad_length,
            False,
        )
        configuration_helper["spad_cmd_data"] = (
            "SPAD Command Data",
            str,
            self.ui.lineEdit_spad_data,
            False,
        )
        configuration_helper["spad_cmd_invert"] = (
            "SPAD Command Invert",
            bool,
            self.ui.checkBox_spad_invert,
            False,
        )

        configuration_helper["DFDnbins"] = (
            "DFDnbins",
            float,
            self.ui.spinBox_DFD_nbins,
            False,
        )
        configuration_helper["DFD_laser_debug"] = (
            "DFD Laser Debug",
            bool,
            self.ui.checkBox_DFD_LaserDebug,
            False,
        )
        configuration_helper["clk_base_multiplier"] = (
            "Clock Base Multiplier",
            int,
            self.ui.spinBox_clk_base_multiplier,
            False,
        )
        configuration_helper["analog_input_a"] = (
            "Analog Input A",
            str,
            self.ui.comboBox_analogSelect_A,
            False,
        )
        configuration_helper["analog_input_b"] = (
            "Analog Input B",
            str,
            self.ui.comboBox_analogSelect_B,
            False,
        )
        configuration_helper["analog_a_differentiate"] = (
            "Analog A Differentiate",
            bool,
            self.ui.checkBox_analog_in_differentiate_A,
            False,
        )
        configuration_helper["analog_b_differentiate"] = (
            "Analog B Differentiate",
            bool,
            self.ui.checkBox_analog_in_differentiate_B,
            False,
        )
        configuration_helper["analog_integrate_ai0"] = (
            "Analog Integrate AI0",
            bool,
            self.ui.checkBox_analog_in_integrate_AI0,
            False,
        )
        configuration_helper["analog_integrate_ai1"] = (
            "Analog Integrate AI1",
            bool,
            self.ui.checkBox_analog_in_integrate_AI1,
            False,
        )
        configuration_helper["analog_integrate_ai2"] = (
            "Analog Integrate AI2",
            bool,
            self.ui.checkBox_analog_in_integrate_AI2,
            False,
        )
        configuration_helper["analog_integrate_ai3"] = (
            "Analog Integrate AI3",
            bool,
            self.ui.checkBox_analog_in_integrate_AI3,
            False,
        )

        for laser_idx in range(1, 13):
            configuration_helper["laser_sequence_%d" % laser_idx] = (
                "Laser Sequence %d" % laser_idx,
                str,
                getattr(self.ui, "comboLaserSeq_%d" % laser_idx),
                False,
            )

        configuration_helper["backendDataRecv"] = (
            "backendDataRecv",
            str,
            self.ui.comboBox_fifobackend,
            False,
        )

        configuration_helper["bitFile_sign"] = (
            "bitFile_sign",
            str,
            self.ui.label_bitfile_signature,
            False,
        )

        configuration_helper["bitFile2_sign"] = (
            "bitFile2_sign",
            str,
            self.ui.label_bitfile_signature_2,
            False,
        )

        configuration_helper["plugins"] = ("Plugins", dict, None, False)

        return configuration_helper

    def configuration_helper_analog_output_init(self):
        """
        Return configuration helper entries for the dynamically built analog output widgets.
        """
        configuration_helper = {}
        for ch in range(0, 8):
            configuration_helper["analog_out_selector_%d" % ch] = (
                "Analog Out Selector %d" % ch,
                str,
                self.ui.comboBox_AnalogOut[ch],
                False,
            )
            configuration_helper["analog_out_value_%d" % ch] = (
                "Analog Out Value %d" % ch,
                float,
                self.ui.spinBox_AnalogOut[ch],
                False,
            )
            configuration_helper["analog_out_enabled_%d" % ch] = (
                "Analog Out Enabled %d" % ch,
                bool,
                self.ui.checkBox_AnalogOut[ch],
                False,
            )

        return configuration_helper

    @Slot(str)
    def detectorModelChanged(self, detector_model):
        detector_model = detector_model or DETECTOR_SPAD_ARRAY
        self.mcs_manager.set_detector_model(detector_model)
        if hasattr(self.ui, "comboBox_fifobackend"):
            self.ui.comboBox_fifobackend.setEnabled(
                not detector_uses_pi23_pipeline(detector_model)
            )

    def _current_detector_model(self):
        if getattr(self.ui, "comboBox_detector_model", None) is not None:
            return normalize_detector_model(self.ui.comboBox_detector_model.currentText())
        return DETECTOR_SPAD_ARRAY

    def _set_detector_model_combo(self, detector_model):
        detector_model = normalize_detector_model(detector_model)
        combo_text = "PI23" if detector_uses_pi23_pipeline(detector_model) else "SPAD"
        self.ui.comboBox_detector_model.blockSignals(True)
        self.ui.comboBox_detector_model.setCurrentText(combo_text)
        self.ui.comboBox_detector_model.blockSignals(False)
        self.detectorModelChanged(self._current_detector_model())

    def setupAnalogOutputGUI(self):
        """
        Build the Analog Output GUI menu
        """
        self.ui.spinBox_AnalogOut.deleteLater()
        self.ui.comboBox_AnalogOut.deleteLater()
        self.ui.label_AnalogOut.deleteLater()
        self.ui.checkBox_AnalogOut.deleteLater()
        self.ui.spinBox_AnalogOut = {}
        self.ui.comboBox_AnalogOut = {}
        self.ui.label_AnalogOut = {}
        self.ui.checkBox_AnalogOut = {}
        for ch in range(0, 8):
            self.ui.checkBox_AnalogOut[ch] = QCheckBox(self.ui.dockWidgetContents_18)
            self.ui.gridLayout_AO.addWidget(
                self.ui.checkBox_AnalogOut[ch], 1 + ch, 3, 1, 1
            )

            if ch > 2:
                self.ui.checkBox_AnalogOut[ch].setChecked(True)

            self.ui.spinBox_AnalogOut[ch] = QDoubleSpinBox(
                self.ui.dockWidgetContents_18
            )
            self.ui.spinBox_AnalogOut[ch].setDecimals(4)
            self.ui.spinBox_AnalogOut[ch].setMinimum(-10.00)
            self.ui.spinBox_AnalogOut[ch].setMaximum(10.00)

            self.ui.gridLayout_AO.addWidget(
                self.ui.spinBox_AnalogOut[ch], 1 + ch, 2, 1, 1
            )

            self.ui.comboBox_AnalogOut[ch] = QComboBox(self.ui.dockWidgetContents_18)
            self.ui.comboBox_AnalogOut[ch].addItem("X")
            self.ui.comboBox_AnalogOut[ch].addItem("Y")
            self.ui.comboBox_AnalogOut[ch].addItem("Z")
            self.ui.comboBox_AnalogOut[ch].addItem("Constant")
            self.ui.comboBox_AnalogOut[ch].addItem("Laser 1")
            self.ui.comboBox_AnalogOut[ch].addItem("Laser 2")
            self.ui.comboBox_AnalogOut[ch].addItem("Laser 3")
            self.ui.comboBox_AnalogOut[ch].addItem("Laser 4")


            if ch == 0:
                self.ui.comboBox_AnalogOut[ch].setCurrentIndex(0)
            elif ch == 1:
                self.ui.comboBox_AnalogOut[ch].setCurrentIndex(1)
            elif ch == 2:
                self.ui.comboBox_AnalogOut[ch].setCurrentIndex(2)
            else:
                self.ui.comboBox_AnalogOut[ch].setCurrentIndex(3)

            self.ui.gridLayout_AO.addWidget(
                self.ui.comboBox_AnalogOut[ch], 1 + ch, 1, 1, 1
            )

            self.ui.label_AnalogOut[ch] = QLabel(self.ui.dockWidgetContents_18)
            self.ui.label_AnalogOut[ch].setText("AO_%d" % ch)
            self.ui.gridLayout_AO.addWidget(
                self.ui.label_AnalogOut[ch], 1 + ch, 0, 1, 1
            )

            self.ui.comboBox_AnalogOut[ch].currentIndexChanged.connect(
                self.analogOutChanged
            )
            self.ui.spinBox_AnalogOut[ch].valueChanged.connect(self.analogOutChanged)

    @Slot()
    def analogOutChanged(self):
        """
        Slot for the Analog Output changed event
        """
        logger.debug("analogOutChanged()")

        mydict = {}
        for ch in range(0, 8):
            sel = self.ui.comboBox_AnalogOut[ch].currentIndex()
            if self.ui.comboBox_AnalogOut[ch].currentText() == "Constant":
                sel = 15

            mydict["analog_output_%d_source_selector" % ch] = sel
            mydict["analog_output_%d_dc_volts" % ch] = self.ui.spinBox_AnalogOut[ch].value()

        self.setRegistersDict(mydict)

    @Slot()
    def laserChanged(self):
        """
        Slot for the Laser changed event
        """
        logger.debug("laserChanged")
        self.setRegistersDict(
            {
                "laser_1_enable": self.ui.checkBox_laser0.isChecked(),
                "laser_2_enable": self.ui.checkBox_laser1.isChecked(),
                "laser_3_enable": self.ui.checkBox_laser2.isChecked(),
                "laser_4_enable": self.ui.checkBox_laser3.isChecked(),
            }
        )

    @Slot()
    def table_keyPressEvent(self, event):
        """
        Slot for the table key pressed
        """
        widget = self.ui.tableWidget
        logger.debug("%s %s %s %s", "Remove from", widget.selectedRanges()[0].leftColumn(), "to", widget.selectedRanges()[0].rightColumn())
        if event.key() == Qt.Key_Delete:
            a = widget.selectedRanges()[0].leftColumn()
            b = widget.selectedRanges()[0].rightColumn() + 1
            for column in range(a, b):
                widget.removeColumn(column)

    @Slot()
    def traceReset(self):
        """
        Slot for the trace reset event
        It resets the time trace
        """
        logger.debug("traceReset")
        self.mcs_manager.trace_reset()

    @Slot()
    def FCSReset(self):
        """
        Slot for the FCS reset event.
        """

        logger.debug("FCSReset")
        self.mcs_manager.FCS_reset()

    @Slot()
    def table_markers_keyPressEvent(self, event):
        """
        Slot for the table of the markers when a key pressed
        It handles the delete key
        """
        widget = self.ui.tableWidget_markers
        logger.debug("%s %s %s %s", "Remove from", widget.selectedRanges()[0].topRow(), "to", widget.selectedRanges()[0].bottomRow())
        if event.key() == Qt.Key_Delete:
            a = widget.selectedRanges()[0].topRow()
            b = widget.selectedRanges()[0].bottomRow() + 1
            logger.debug(len(self.markers_list))
            for n, row in enumerate(range(a, b)):
                logger.debug(row)
                self.markers_list.pop(row - n)
            self.markersViewTable()
            self.drawMarkers()

    @Slot()
    def traceClicked(self, event):
        """
        Slot for the time trace clicked event
        """
        mouse_event = event
        mouse_point = mouse_event.pos()
        projection = self.ui.comboBox_view_projection.currentText()

        if mouse_event.double():
            self.traceReset()

    @Slot()
    def cmd_path_ttm(self):
        """
        Slot for the TTM path command
        """
        logger.debug("cmd_path_ttm")

        dialog = QFileDialog(self)
        dialog.setWindowTitle("Select executable...")
        dialog.setViewMode(QFileDialog.Detail)
        dialog.setNameFilters([self.tr("Executable File (*.exe)")])
        dialog.setDefaultSuffix(".exe")

        if dialog.exec_():
            filepath = dialog.selectedFiles()[0]
            self.ui.lineEdit_ttm_executable_path.setText(filepath)

    @Slot()
    def cmd_path_destinationfolder(self):
        """
        Slot for the data destination folder command
        """
        logger.debug("cmd_path_destinationfolder")

        dialog = QFileDialog(self)
        dialog.setFileMode(QFileDialog.Directory)
        if dialog.exec_():
            self.ui.lineEdit_destinationfolder.setText(dialog.selectedFiles()[0])

    @Slot()
    def spadChannelsChanged(self):
        """
        Slot for the SPAD channel-count changed event.
        """
        ch = int(self.ui.comboBox_spad_channels.currentText())
        logger.debug("%s %s", "spadChannelsChanged to", self.ui.comboBox_spad_channels.currentText())
        self.spad_channels = ch
        self.spad_channels_x = int(np.sqrt(ch))
        self.spad_channels_y = self.spad_channels_x
        self.fingerprint_mask = np.ones((self.spad_channels_x, self.spad_channels_y), dtype=np.uint8)
        self.mcs_manager.set_spad_channels(int(self.ui.comboBox_spad_channels.currentText()))

    @Slot()
    def cmd_filename(self):
        """
        Slot for selecting the filename
        """
        logger.debug("cmd_filename")

        dialog = QFileDialog(self)
        dialog.setWindowTitle("Save as...")
        dialog.setViewMode(QFileDialog.Detail)
        dialog.setNameFilters([self.tr("HDF5 File (*.h5)")])
        dialog.setDefaultSuffix(".h5")

        if dialog.exec_():
            filepath = dialog.selectedFiles()[0]
            self.ui.lineEdit_filename.setText(filepath.split("/")[-1])
            self.ui.lineEdit_destinationfolder.setText(
                "/".join(filepath.split("/")[:-1])
            )

    @Slot()
    def cmd_convertRawAcquisition(self):
        """
        Convert a metadata-only RAW acquisition into a standard BrightEyes H5 file.
        """
        suggested_input = self.ui.lineEdit_destinationfolder.text()
        if self.last_saved_filename:
            last_saved_path = Path(self.last_saved_filename)
            if last_saved_path.exists():
                suggested_input = str(last_saved_path)

        metadata_filename, _ = QFileDialog.getOpenFileName(
            self,
            "Select RAW acquisition metadata",
            suggested_input,
            "HDF5 File (*.h5)",
        )
        if metadata_filename == "":
            return

        metadata_path = os.path.abspath(metadata_filename)
        metadata_stem = Path(metadata_path).stem
        if metadata_stem.endswith("_only_metadata"):
            default_output = str(Path(metadata_path).with_name(metadata_stem[: -len("_only_metadata")] + ".h5"))
        else:
            default_output = os.path.splitext(metadata_path)[0] + "_converted.h5"
        output_filename, _ = QFileDialog.getSaveFileName(
            self,
            "Save converted acquisition as",
            default_output,
            "HDF5 File (*.h5)",
        )
        if output_filename == "":
            return

        progress_dialog = QProgressDialog("Preparing RAW conversion...", None, 0, 100, self)
        progress_dialog.setWindowTitle("Converting RAW acquisition")
        progress_dialog.setMinimumDuration(0)
        progress_dialog.setAutoClose(True)
        progress_dialog.setAutoReset(True)
        progress_dialog.setValue(0)

        def progress_callback(value, message):
            progress_dialog.setLabelText(message)
            progress_dialog.setValue(value)
            QCoreApplication.processEvents()

        try:
            converted_path = convert_raw_acquisition(
                metadata_path,
                output_filename,
                progress_callback=progress_callback,
            )
        except Exception as ex:
            traceback.print_exc()
            progress_dialog.close()
            QMessageBox.critical(self, "RAW conversion failed", str(ex))
            return

        progress_dialog.setValue(100)
        self.last_saved_filename = str(converted_path)
        self._publish_filename_to_console(self.last_saved_filename)
        self.ui.pushButton_externalProgram.setEnabled(True)
        self.plugin_signals.signal.emit(
            "acquisitionDone %s" % self.last_saved_filename
        )
        self.ui.statusBar.showMessage(f"Converted RAW acquisition to {converted_path}", 10000)
        QMessageBox.information(
            self,
            "RAW conversion completed",
            f"Converted acquisition saved in:\n{converted_path}",
        )

    @Slot()
    def cmd_moveToSelectedRowMarker(self):
        """
        Slot for moving to the selected row marker
        """
        logger.debug("cmd_moveToSelectedRowMarker")
        if len(self.markers_list) > 0:
            self.setGUI_data(
                self.markers_list[
                    self.ui.tableWidget_markers.selectedIndexes()[0].row()
                ]
            )

    def moveToSelectedColumnFCS(self, k):
        """
        Set the GUI configuration to the selected column in the Macro/FCS table
        """
        logger.debug("moveToSelectedColumnFCS")
        widget = self.ui.tableWidget

        invrow = {
            caption: (name, mtype, ref_obj, visible)
            for name, (
                caption,
                mtype,
                ref_obj,
                visible,
            ) in self.configuration_helper.items()
        }
        configuration = {}
        for n in range(widget.rowCount()):
            logger.debug("%s %s", n, k)
            a = widget.verticalHeaderItem(n).text()
            if a in invrow:
                name, mtype, ref_obj, visible = invrow[a]
                if mtype is int:
                    value = int(widget.item(n, k).text())
                elif mtype is float:
                    value = float(widget.item(n, k).text())
                elif mtype is str:
                    value = str(widget.item(n, k).text())
                elif mtype is bool:
                    value = widget.item(n, k).checkState() == Qt.Checked

                configuration[name] = value
            self.setGUI_data(configuration)

    @Slot()
    def cmd_moveToSelectedColumnFCS(self, k=None):
        """
        Set the GUI configuration to the current column in the Macro/FCS table
        """
        logger.debug("cmd_moveToSelectedColumnFCS")
        widget = self.ui.tableWidget
        k = widget.currentColumn()
        if not k:
            return
        self.moveToSelectedColumnFCS(k)

    @Slot(name="copyPositionMarkers")
    def copyPositionMarkers_legacy(self):
        """
        Backward-compatible alias for the legacy Designer slot typo.
        """
        self.copyPositionsMarkers()

    @Slot()
    def prova(self, ev):
        """
        dummy button
        """
        logger.debug("%s %s", "prova", ev)

    @Slot()
    def getTabWinMinimization(self, widget, event):
        """
        Slot for the tab window minimization event
        """
        logger.debug("%s %s %s", widget, event, event.type())
        if event.type() is QEvent.Type.WindowStateChange:
            logger.debug("WindowStateChange")
            if widget.isMinimized():
                logger.debug("minimize")
                widget.setWindowFlags(Qt.Widget)
                self.ui.tabWidget.addTab(widget, widget.windowTitle())

    @Slot()
    def tabDoubleClick(self, number):
        """
        Slot for the tab double click event: it moves the tab to a new window
        """
        logger.debug("%s %s", "tabDoubleClick", number)
        w = self.ui.tabWidget.widget(number)
        pos = w.mapToGlobal(w.pos())
        size = w.frameSize()
        title = self.ui.tabWidget.tabText(number)
        self.ui.tabWidget.removeTab(number)
        w.setWindowTitle(title)
        # w.setWindowFlags(PySide6.QtCore.Qt.Window & ~PySide6.QtCore.Qt.WindowCloseButtonHint)
        w.setWindowFlags(
            Qt.Window
            | Qt.CustomizeWindowHint
            | Qt.WindowTitleHint
            | Qt.WindowMinMaxButtonsHint
        )
        w.showNormal()
        w.move(pos)
        w.resize(size)
        w.show()
        # This is an horrible choice but it works. We should use the signal and connect()
        w.changeEvent = lambda event: self.getTabWinMinimization(w, event)

    def guiReadyEvent(self):
        """
        Slot for the GUI ready event, normally called when the GUI is ready to be used
        """
        logger.debug("guiReadyEvent()")
        self.im_widget.show()
        default_cfg = self.checkDefaultCfg()
        self.ui.lineEdit_configurationfile.setText(default_cfg)        
        logger.debug("%s %s", "loading cfg", default_cfg)
        self.LoadConfiguration(default_cfg)
        self.panoramaButton()
        # self.splash.close()
        QTimer.singleShot(100, self.splash.close)

        current_conf = self.getGUI_data()
        self.ui.comboBox_preset.clear()
        for i in range(0, 26):
            self.preset_dict[chr(ord("A") + i)] = current_conf
            self.ui.comboBox_preset.addItem(chr(ord("A") + i))

        logger.debug("Launch the QTimer.singleShot")
        QTimer.singleShot(100, self.raise_)
        QTimer.singleShot(250, self.showMaximized)

    @Slot()
    def showEvent(self, event):
        """
        Overridden showEvent method for generating the GUI ready event
        """
        logger.debug("%s %s", "showEvent", event.spontaneous())
        super(MainWindow, self).showEvent(event)

        if not event.spontaneous():  # case when is the first paint
            self.guiReadyFlag = True
            if self.init_ready == True:
                logger.debug("call guiReadyEvent from showEvent")
                QTimer.singleShot(10, self.guiReadyEvent)

    # @Slot()
    # def mouseMovedOnImage(self, ev):
    #     debug("self.mouseMovedOnImage", ev)

    # @Slot()
    # def pmtThresholdChanged(self, value=0):
    #     debug("pmtThresholdChanged")
    #     self.setRegistersDict({"PMT_VThreshold": self.ui.spinBox_PMT_Threshold.value(),
    #                            "PMT_VThreshold_Min": self.ui.spinBox_PMT_Threshold_Min.value(),
    #                            "PMT_VThreshold_Max": self.ui.spinBox_PMT_Threshold_Max.value()})

    # @Slot()
    # def cfg_file_clicked(self):
    #     debug("cfg_file_clicked()")
    #
    #
    #     file_cfg = QFileDialog.getOpenFileName(self, caption="Save Configuration",
    #                                            filter="Config File (*.cfg)",
    #                                            dir=self.ui.lineEdit_configurationfile.text())[0]
    #
    #     current_folder = QDir.fromNativeSeparators(os.getcwd()) + "/"
    #     if file_cfg != "":
    #         debug(file_cfg)
    #         debug(current_folder)
    #         file_cfg_nicer = file_cfg.replace(current_folder, "")
    #         self.ui.lineEdit_configurationfile.setText(file_cfg_nicer)
    #
    #     self.ask_to_save_cfg_as_permanent(file_cfg_nicer)

    def ask_to_save_cfg_as_permanent(self, file_cfg_nicer):
        """
        Message box to ask if the configuration file should be saved as permanent
        """
        msgBox = QMessageBox()
        msgBox.setText("The file " + file_cfg_nicer + " was selected")
        msgBox.setInformativeText(
            "Do you want to save as PERMANENT default configuration?"
        )
        msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msgBox.setDefaultButton(QMessageBox.No)
        msgBox.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowTitleHint)
        ret = msgBox.exec_()

        if ret == QMessageBox.Yes:
            self.setNewDefaultCfg(file_cfg_nicer)
            self.ui.lineEdit_configurationfile.setText(file_cfg_nicer)
        if ret == QMessageBox.No:
            logger.debug("No")
    @Slot()
    def bitfile_changed(self):
        '''
        Slot for update and check the FPGA bitfiles
        '''
        import nifpga

        bitfile=self.ui.lineEdit_fpgabitfile.text()
        bitfile2=self.ui.lineEdit_fpga2bitfile.text()
        self.apply_dfd_metadata_from_bitfile_name(bitfile)
        resolved_bitfile = resolve_legacy_path(bitfile)
        if resolved_bitfile.is_file():
            try:
                bitfile_reader = nifpga.Bitfile(str(resolved_bitfile))
                bitfile_signature = bitfile_reader.signature
            except:
                bitfile_signature = ""
            self.ui.label_bitfile_signature.setText(bitfile_signature)
        resolved_bitfile2 = resolve_legacy_path(bitfile2) if bitfile2 else None
        if resolved_bitfile2 is not None and resolved_bitfile2.is_file():
            try:
                bitfile_reader = nifpga.Bitfile(str(resolved_bitfile2))
                bitfile_signature = bitfile_reader.signature
            except:
                bitfile_signature = ""
            self.ui.label_bitfile_signature_2.setText(bitfile_signature)

    def apply_dfd_metadata_from_bitfile_name(self, bitfile):
        """
        Update inferred DFD metadata from the primary FPGA bitfile name.
        """
        dfd_cycle_mhz, inferred_dfd_nbins = (
            self.mcs_manager.parse_dfd_metadata_from_bitfile_name(
                bitfile,
                default_cycle_mhz=40,
            )
        )
        self.dfd_cycle_mhz = dfd_cycle_mhz
        self.mcs_manager.dfd_cycle_mhz = dfd_cycle_mhz
        self.ui.label_120.setText(f"Clock Base {dfd_cycle_mhz}M x")
        if inferred_dfd_nbins is not None:
            self.ui.spinBox_DFD_nbins.setValue(inferred_dfd_nbins)



    @Slot()
    def bit_file_clicked(self):
        """
        Slot for the selecting the bitfile of the 1st FPGA
        """
        logger.debug("bit_file_clicked()")

        file_bit = QFileDialog.getOpenFileName(
            self,
            caption="FPGA Bit File",
            filter="FPGA Bit File (*.lvbitx)",
            dir=str(resource_path("bitfiles")),
        )[0]
        current_folder = QDir.fromNativeSeparators(os.getcwd()) + "/"
        if file_bit != "":
            logger.debug(file_bit)
            logger.debug(current_folder)
            file_bit_nicer = file_bit.replace(current_folder, "")
            self.ui.lineEdit_fpgabitfile.setText(file_bit_nicer)

    @Slot()
    def bit_file_clicked2(self):
        """
        Slot for the selecting the bitfile of the 2nd FPGA
        """
        logger.debug("bit_file_clicked2()")

        file_bit = QFileDialog.getOpenFileName(
            self,
            caption="FPGA Bit File",
            filter="FPGA Bit File (*.lvbitx)",
            dir=str(resource_path("bitfiles")),
        )[0]
        current_folder = QDir.fromNativeSeparators(os.getcwd()) + "/"
        if file_bit != "":
            logger.debug(file_bit)
            logger.debug(current_folder)
            file_bit_nicer = file_bit.replace(current_folder, "")
            self.ui.lineEdit_fpga2bitfile.setText(file_bit_nicer)

    def checkDefaultCfg(self, default_name=None):
        """
        Check if the default configuration file exists
        """
        if default_name is None:
            return str(ensure_user_configuration())
        if os.path.exists(default_name):
            with open(default_name, "r") as f:
                a = f.read().splitlines()
                logger.debug("%s %s", "current_system opened:", a[1])
                return a[1]
        else:
            file = self.setNewDefaultCfg(str(resource_path("cfg/default.cfg")), default_name)
            logger.debug("'current_system' file not found")
            return file
        raise ("Error in checkDefaultCfg")

    def setNewDefaultCfg(self, default_cfg, default_name=None):
        """
        Set a new default configuration file
        """
        if default_name is None:
            write_default_pointer(resolve_legacy_path(default_cfg))
            return default_cfg
        with open(default_name, "w") as f:
            f.write(
                "\n".join(
                    [
                        "# the line below provides the default configuration file",
                        default_cfg,
                    ]
                )
            )
            logger.debug("A new '"
                + default_name
                + "' generated in which '"
                + default_cfg
                + "' is selected.")
        return default_cfg

    def getGUI_data(self):
        """
        Get the GUI data and return it as a dictionary
        """
        configuration = {}
        for n, (name, (caption, mtype, ref_obj, visible)) in enumerate(
                self.configuration_helper.items()
        ):
            try:
                if name == "plugins":
                    configuration[name] = self._get_plugins_configuration_section()
                elif name == "detector_model":
                    configuration[name] = self._current_detector_model()
                else:
                    if (mtype is int) or (mtype is float):
                        configuration[name] = ref_obj.value()
                    elif mtype is str:
                        try:
                            configuration[name] = ref_obj.currentText()
                        except:
                            try:
                                configuration[name] = ref_obj.text()
                            except:
                                try:
                                    configuration[name] = ref_obj.toPlainText()
                                except:
                                    logger.debug("%s %s %s", "Wrong methods to read str", n, (name, (caption, mtype, ref_obj, visible)))
                    elif mtype is bool:
                        configuration[name] = ref_obj.isChecked()

            except Exception as e:
                logger.debug("ERROR getGUI_data")
                logger.debug("%s %s", n, (name, (caption, mtype, ref_obj, visible)))
                logger.debug(repr(e))

        return configuration

    def _default_plugin_config_path(self, plugin_name):
        return str(writable_config_path("cfg/plugins_cfg/%s.cfg" % plugin_name))

    def _get_plugins_configuration_section(self):
        """
        Return the lightweight plugin section stored in the main .cfg file.
        """
        return {
            "autoload": list(self.plugin_autoload),
            "configs": dict(self.plugin_configuration_files),
        }

    def _normalize_plugin_names(self, plugin_names):
        normalized = []
        for item in plugin_names:
            plugin_name = None
            if isinstance(item, str):
                plugin_name = item
            elif isinstance(item, dict):
                if item.get("enabled", True) is False:
                    continue
                plugin_name = item.get("name") or item.get("plugin")
                config_file = item.get("config") or item.get("cfg")
                if plugin_name and config_file:
                    self.plugin_configuration_files[plugin_name] = config_file

            if plugin_name and plugin_name not in normalized:
                normalized.append(plugin_name)
        return normalized

    def _resolve_plugin_config_path(self, config_file, base_cfg_file="", for_write=False):
        path = Path(str(config_file))
        if path.is_absolute():
            return path
        if for_write:
            if path.parts and path.parts[0].lower() == "cfg":
                return writable_config_path(path)
            if base_cfg_file:
                return Path(base_cfg_file).resolve().parent / path
            return writable_config_path(path)
        return resolve_legacy_path(path, base_file=base_cfg_file or None)

    def _load_plugin_config_file(self, plugin_name, config_file, base_cfg_file=""):
        path = self._resolve_plugin_config_path(config_file, base_cfg_file)
        try:
            with open(path, "r") as file:
                payload = json.loads(file.read().replace(", \n", ","))
        except FileNotFoundError:
            logger.debug("%s %s %s", "Plugin configuration file not found", plugin_name, str(path))
            return
        except Exception as error:
            logger.debug("%s %s %s %s", "Unable to load plugin configuration", plugin_name, str(path), repr(error))
            return

        if isinstance(payload, dict) and isinstance(payload.get(plugin_name), dict):
            payload = payload[plugin_name]

        if isinstance(payload, dict):
            self.plugin_configuration[plugin_name] = payload
            logger.debug("%s %s %s", "Loaded plugin configuration", plugin_name, str(path))

    def _save_plugin_configuration_files(self, plugin_names=None):
        if plugin_names is None:
            plugin_names = list(self.plugin_configuration_files)
        elif isinstance(plugin_names, str):
            plugin_names = [plugin_names]

        for plugin_name in plugin_names:
            config_file = self.plugin_configuration_files.get(
                plugin_name,
                self._default_plugin_config_path(plugin_name),
            )
            self.plugin_configuration_files[plugin_name] = config_file
            if plugin_name not in self.plugin_configuration:
                continue

            path = self._resolve_plugin_config_path(config_file, for_write=True)
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                text = json.dumps(
                    self.plugin_configuration[plugin_name],
                    cls=NumpyJSONEncoder,
                )
                with open(path, "w") as file:
                    file.write(text.replace(",", ",\n"))
                logger.debug("%s %s %s", "Saved plugin configuration", plugin_name, str(path))
            except Exception as error:
                logger.debug("%s %s %s %s", "Unable to save plugin configuration", plugin_name, str(path), repr(error))

    def _apply_plugins_configuration_section(self, plugins_section, base_cfg_file=""):
        if not isinstance(plugins_section, dict):
            return

        metadata_keys = {
            "autoload",
            "startup",
            "startup_plugins",
            "open_at_startup",
            "configs",
            "configuration_files",
            "configurations",
        }
        has_metadata = any(key in plugins_section for key in metadata_keys)

        if not has_metadata:
            self.plugin_configuration.update(plugins_section)
            for plugin_name in plugins_section:
                self.plugin_configuration_files.setdefault(
                    plugin_name,
                    self._default_plugin_config_path(plugin_name),
                )
            return

        for key in ("configs", "configuration_files", "configurations"):
            configs = plugins_section.get(key, {})
            if not isinstance(configs, dict):
                continue
            for plugin_name, config_file in configs.items():
                if isinstance(config_file, dict):
                    config_file = config_file.get("file") or config_file.get("path")
                if config_file:
                    self.plugin_configuration_files[plugin_name] = config_file

        for key in ("autoload", "startup", "startup_plugins", "open_at_startup"):
            if key in plugins_section:
                self.plugin_autoload = self._normalize_plugin_names(
                    plugins_section.get(key, [])
                )
                break

        embedded_config = plugins_section.get("configuration", {})
        if isinstance(embedded_config, dict):
            self.plugin_configuration.update(embedded_config)

        for plugin_name, config_file in self.plugin_configuration_files.items():
            self._load_plugin_config_file(plugin_name, config_file, base_cfg_file)

    def _load_startup_plugins(self):
        for plugin_name in self.plugin_autoload:
            try:
                self.plugin_manager.load_once(plugin_name)
            except Exception as error:
                logger.debug("%s %s %s", "Unable to autoload plugin", plugin_name, repr(error))

    def SavePluginConfiguration(self, plugin_names=None):
        if plugin_names is None:
            plugin_names = list(self.plugin_configuration_files)
        elif isinstance(plugin_names, str):
            plugin_names = [plugin_names]

        if len(plugin_names) == 0:
            QMessageBox.warning(self, "Save Plugin Configuration", "No plugin selected.")
            return

        self._save_plugin_configuration_files(plugin_names)
        self.ui.statusBar.showMessage("Plugin configuration saved.", 5000)

    def setGUI_data(self, configuration={}):
        """
        Set the GUI data from a dictionary (it can be also a partial configuration)
        """
        configuration = dict(configuration)
        # FPGA connection is live hardware state, not a saved GUI preference.
        configuration.pop("load_firmware_once", None)
        configuration.pop("keep_fpga_connected", None)

        # lock_old = self.lock_parameters_changed_call
        # self.lock_parameters_changed_call = True

        for name in configuration:
            try:
                caption, mtype, ref_obj, visible = self.configuration_helper[name]
                if name == "plugins":
                    self._apply_plugins_configuration_section(
                        configuration[name],
                        self._loading_configuration_file,
                    )
                    logger.debug("%s %s %s", "PLUGINS CONFIGURATION", type(configuration[name]), configuration[name])
                    logger.debug("%s %s %s", "PLUGINS CONFIGURATION", type(self.plugin_configuration), self.plugin_configuration)

                elif name == "detector_model":
                    self._set_detector_model_combo(configuration[name])

                else:
                    if (mtype is int) or (mtype is float):
                        ref_obj.setValue(configuration[name])
                    elif mtype is str:
                        try:
                            ref_obj.setCurrentText(configuration[name])
                        except:
                            ref_obj.setText(configuration[name])
                    elif mtype is bool:
                        ref_obj.setChecked(configuration[name])

            except Exception as e:
                logger.debug("ERROR setGUI_data")
                logger.debug("%s %s", name, (caption, mtype, ref_obj, visible))
                logger.debug(repr(e))
        self.plugin_signals.signal.emit("configurationLoaded")
        #
        # self.lock_parameters_changed_call = lock_old
        # self.positionSettingsChanged()
        # self.axesRangeChanged()

    # @Slot()
    # def testevent(self, ev):
    #     debug("testevent", ev)

    @Slot()
    def delete_list_file(self):
        """
        delete the selected files in the list
        """
        logger.debug("delete_list_file()")
        sel = []
        while len(self.ui.listWidget.selectedItems()) > 0:
            for i in range(self.ui.listWidget.count()):
                if self.ui.listWidget.item(i).isSelected():
                    self.ui.listWidget.takeItem(i)
                    break

    @Slot()
    def copy_list_file(self):
        '''
        Actually is "cut" the files ready to be "paste" in some folder
        '''
        logger.debug("copy_list_file()")
        list_urls = []
        for i in self.ui.listWidget.selectedItems():
            f = i.text()
            f = f.replace("TTM: ", "")
            list_urls.append(QUrl.fromLocalFile(f))
        print(list_urls)
        mime = QMimeData()
        mime.setUrls(list_urls)
        mime.setData("Preferred DropEffect", b"\x02\x00\x00\x00")
        QGuiApplication.clipboard().setMimeData(mime)

    @Slot()
    def cmd_load_plugin(self):
        """
        Load the selected plugin
        """
        item = self.ui.listWidget_plugins.currentItem()
        if item is not None:
            plugin_to_be_loaded = item.text()
            logger.debug(plugin_to_be_loaded)
            self.plugin_manager.load(plugin_to_be_loaded)

    @Slot()
    def cmd_close_plugin(self):
        """
        Close the selected plugin
        """
        pass

    @Slot()
    def cmd_update_plugin_list(self):
        """
        Update the plugin list
        """
        self.ui.listWidget_plugins.clear()
        l = self.plugin_manager.available_plugins()
        logger.debug("%s %s", "cmd_update_plugin_list()", l)
        for i in l:
            self.ui.listWidget_plugins.addItem(i)

    @Slot()
    def axesRangeChanged(self, ev=None):
        """
        Slot for the axes range changed event, when the range of the axes of the Image Preview is changed
        """
        logger.debug("axesRangeChanged(...)")
        if self.preview_view_box.navigation_event_active:
            proj = self.ui.comboBox_view_projection.currentText()
            old_lock_parameters_changed_call = self.lock_parameters_changed_call
            if not self.lock_range_changing:
                self.im_widget_plot_item.getAxis("bottom")
                bottom_range = self.im_widget_plot_item.getAxis("bottom").range
                left_range = self.im_widget_plot_item.getAxis("left").range

                bottom_offset = 0.5 * (bottom_range[0] + bottom_range[1])
                left_offset = 0.5 * (left_range[0] + left_range[1])

                bottom_gap = abs(bottom_range[1] - bottom_range[0])
                left_gap = abs(left_range[1] - left_range[0])

                logger.debug("%s %s", "bottom_range:", bottom_range)
                logger.debug("%s %s", "left_range:", left_range)
                logger.debug("%s %s %s %s %s %s", "R ", bottom_gap, left_gap, "    ", min(bottom_gap, left_gap), min(bottom_gap, left_gap))

                self.lock_parameters_changed_call = True
                logger.debug("axesRangeChanged self.lock_parameters_changed_call SET True")
                self.lock_range_changing = True

                self.currentImage_pixels = np.asarray(
                    (
                        self.ui.spinBox_nx.value(),
                        self.ui.spinBox_ny.value(),
                        self.ui.spinBox_nframe.value(),
                    )
                )

                if proj == "xy":
                    self.ui.spinBox_range_x.setValue(min(bottom_gap, left_gap))
                    self.ui.spinBox_range_y.setValue(min(bottom_gap, left_gap))

                    self.ui.spinBox_off_x_um.setValue(
                        bottom_offset
                    )  # + max(xr - yr, 0) / 2)
                    self.ui.spinBox_off_y_um.setValue(
                        left_offset
                    )  # + max(yr - xr, 0) / 2)

                    self.currentImage_pos = np.asarray(
                        (
                            bottom_offset,
                            left_offset,
                            self.ui.spinBox_off_z_um.value(),
                        )
                    )

                    self.currentImage_size = np.asarray(
                        (
                            min(bottom_gap, left_gap),
                            min(bottom_gap, left_gap),
                            self.ui.spinBox_range_z.value(),
                        )
                    )

                elif proj == "zy":
                    self.ui.spinBox_range_z.setValue(min(bottom_gap, left_gap))
                    self.ui.spinBox_range_y.setValue(min(bottom_gap, left_gap))

                    self.ui.spinBox_off_z_um.setValue(
                        bottom_offset
                    )  # + max(xr - yr, 0) / 2)
                    self.ui.spinBox_off_y_um.setValue(
                        left_offset
                    )  # + max(yr - xr, 0) / 2)

                    self.currentImage_pos = np.asarray(
                        (
                            self.ui.spinBox_off_x_um.value(),
                            left_offset,
                            bottom_offset,
                        )
                    )

                    self.currentImage_size = np.asarray(
                        (
                            self.ui.spinBox_range_x.value(),
                            min(bottom_gap, left_gap),
                            min(bottom_gap, left_gap),
                        )
                    )

                elif proj == "xz":
                    self.ui.spinBox_range_x.setValue(min(bottom_gap, left_gap))
                    self.ui.spinBox_range_z.setValue(min(bottom_gap, left_gap))

                    self.ui.spinBox_off_x_um.setValue(
                        bottom_offset
                    )  # + max(xr - yr, 0) / 2)
                    self.ui.spinBox_off_z_um.setValue(
                        left_offset
                    )  # + max(yr - xr, 0) / 2)

                    self.currentImage_pos = np.asarray(
                        (bottom_offset, self.ui.spinBox_off_y_um.value(), left_offset)
                    )

                    self.currentImage_size = np.asarray(
                        (
                            min(bottom_gap, left_gap),
                            self.ui.spinBox_range_y.value(),
                            min(bottom_gap, left_gap),
                        )
                    )
                elif proj == "yx":
                    self.ui.spinBox_range_y.setValue(min(bottom_gap, left_gap))
                    self.ui.spinBox_range_x.setValue(min(bottom_gap, left_gap))

                    self.ui.spinBox_off_y_um.setValue(
                        bottom_offset
                    )  # + max(xr - yr, 0) / 2)
                    self.ui.spinBox_off_x_um.setValue(
                        left_offset
                    )  # + max(yr - xr, 0) / 2)

                    self.currentImage_pos = np.asarray(
                        (
                            left_offset,
                            bottom_offset,
                            self.ui.spinBox_off_z_um.value(),
                        )
                    )

                    self.currentImage_size = np.asarray(
                        (
                            min(bottom_gap, left_gap),
                            min(bottom_gap, left_gap),
                            self.ui.spinBox_range_z.value(),
                        )
                    )

                elif proj == "yz":
                    self.ui.spinBox_range_y.setValue(min(bottom_gap, left_gap))
                    self.ui.spinBox_range_z.setValue(min(bottom_gap, left_gap))

                    self.ui.spinBox_off_y_um.setValue(
                        bottom_offset
                    )  # + max(xr - yr, 0) / 2)
                    self.ui.spinBox_off_z_um.setValue(
                        left_offset
                    )  # + max(yr - xr, 0) / 2)

                    self.currentImage_pos = np.asarray(
                        (self.ui.spinBox_off_x_um.value(), bottom_offset, left_offset)
                    )

                    self.currentImage_size = np.asarray(
                        (
                            self.ui.spinBox_range_x.value(),
                            min(bottom_gap, left_gap),
                            min(bottom_gap, left_gap),
                        )
                    )

                elif proj == "zx":
                    self.ui.spinBox_range_z.setValue(min(bottom_gap, left_gap))
                    self.ui.spinBox_range_x.setValue(min(bottom_gap, left_gap))

                    self.ui.spinBox_off_z_um.setValue(
                        bottom_offset
                    )  # + max(xr - yr, 0) / 2)
                    self.ui.spinBox_off_x_um.setValue(
                        left_offset
                    )  # + max(yr - xr, 0) / 2)

                    self.currentImage_pos = np.asarray(
                        (left_offset, self.ui.spinBox_off_y_um.value(), bottom_offset)
                    )

                    self.currentImage_size = np.asarray(
                        (
                            min(bottom_gap, left_gap),
                            self.ui.spinBox_range_y.value(),
                            min(bottom_gap, left_gap),
                        )
                    )

                # self.lock_parameters_changed_call = False
                self.lock_parameters_changed_call = old_lock_parameters_changed_call
                logger.debug("axesRangeChanged self.lock_parameters_changed_call UNSET False")

                self.updateLabelPixelSize()

                self.lock_range_changing = False

                if self.started_preview:
                    self.plotPreviewImage()
                if self.started_preview or self.started_normal:
                    self.positionSettingsChanged()

    @Slot()
    def shutdown(self):
        """Best-effort shutdown that always closes the NI FPGA sessions."""
        if self._shutdown_complete or self._shutdown_started:
            return
        self._shutdown_started = True

        logger.debug("=======================")
        logger.debug("   CLOSE EVERYTHING")
        logger.debug("=======================")

        if self.mcs_manager.is_connected:
            logger.debug("Quick-resetting FPGA before shutdown")
            try:
                self.mcs_manager.quick_reset_fpga(
                    timeout=self.FPGA_IDLE_TIMEOUT_SECONDS
                )
            except Exception:
                logger.exception(
                    "FPGA quick reset failed during shutdown; "
                    "continuing with forced session shutdown"
                )

        try:
            self.mcs_manager.stopPreview()
        except Exception:
            logger.exception("Could not stop acquisition/preview workers")

        try:
            self.timerPreviewImg.stop()
        except Exception:
            logger.exception("Could not stop the preview timer")

        try:
            self.timerFPGAWatchdog.stop()
        except (AttributeError, RuntimeError):
            logger.debug("FPGA watchdog timer was not active during shutdown")

        try:
            self.mcs_manager.stopAcquisition()
        except Exception:
            logger.exception("Could not stop acquisition processes")

        try:
            if self.ttm_remote_manager is not None:
                self.ttm_remote_manager.close()
                self.ttm_remote_manager = None
        except Exception:
            logger.exception("Could not close the TTM manager")

        try:
            self.mcs_manager.stopFPGA()
        except Exception:
            logger.exception("FPGA session shutdown reported errors")
        finally:
            self.mcs_manager.is_connected = False
            self._shutdown_complete = True
            self._shutdown_started = False

        logger.debug("Now every process should be closed.")

    @Slot()
    def closeEvent(self, event):
        """Shut down hardware and workers before accepting the close event."""
        self.shutdown()
        event.accept()

        logger.debug("Now every process should be closed,Really! \n=============\n=== CIAO! ===\n=============")

    def bitfile_check(self, path):
        """
        Check if the bitfile exists
        """
        resolved_path = resolve_legacy_path(path)
        if not resolved_path.is_file():
            msgBox = QMessageBox()
            msgBox.setText("The firmware file %s does not exist!\n"
                           "Please check if the path in the menu Config/Board Configuration/FPGA Bitfiles is correct.\n"
                           "IMPORTANT: the firmwares are not included in BrightEyes-MCS tree\n"
                           "you need to download them a part. Please find in the documentation the link.\n" % path
                           )
            msgBox.exec_()
            raise (ValueError("Firmware file not found!"))
        return str(resolved_path)

    def connectFPGA(self):
        """
        Connect to the FPGA(s)
        """
        logger.debug("ConnectFPGA")

        primary_bitfile = self.bitfile_check(self.ui.lineEdit_fpgabitfile.text())

        self.mcs_manager.set_bit_file(primary_bitfile)
        self.mcs_manager.set_ni_addr(self.ui.lineEdit_ni_addr.text())

        self.mcs_manager.set_bit_file_second_fpga(self.ui.lineEdit_fpga2bitfile.text())
        self.mcs_manager.set_ni_addr_second_fpga(self.ui.lineEdit_ni2addr.text())

        self.mcs_manager.set_timeout_fifos(
            self.ui.spinBox_fifo_timeout.value() * 1000
        )

        if self.mcs_manager.is_connected:
            logger.debug("Already connected")
        else:
            logger.debug("FPGA NOT CONNECTED NOW CONNECTING")
            mydict = {}
            mydict.update(self.mcs_manager.default_configuration)
            mydict.update(self.configurationFPGA_dict)
            # Opening the FPGA session must never start the scan FSM.  A stale
            # start value may remain in configurationFPGA_dict after a run.
            mydict["stop_command"] = False
            mydict["start_command"] = False

            invert_sdata = (self.ui.checkBox_spad_invert.isChecked(),)

            rust_fifo_active = self.ui.comboBox_fifobackend.currentText().startswith(
                "Rust"
            )
            logger.debug("%s %s", "rust_fifo_active", rust_fifo_active)
            self.mcs_manager.set_use_rust_fifo(rust_fifo_active)
            self.mcs_manager.set_detector_model(self._current_detector_model())

            msg_out = self.ui.lineEdit_spad_data.text()
            if msg_out.isdigit():
                msg_out = int(msg_out)
            else:
                msg_out = 0

            msg_len = self.ui.lineEdit_spad_length.text()
            if msg_len.isdigit():
                msg_len = int(msg_len)
            else:
                msg_len = 0

            mydict.update(
                {
                    "spad_sdata_invert_enable": self.ui.checkBox_spad_invert.isChecked(),
                    "spad_configuration_message": msg_out,
                    "spad_configuration_message_length": msg_len,
                }
            )

            if self.spad_channels == 49:
                mydict.update(
                    {
                        "detector_49_channel_mode_enable": True
                    }
                )
            else:
                mydict.update(
                    {
                        "detector_49_channel_mode_enable": False
                    }
                )

            # self.mcs_manager.set(self.ui.spinBox_requested_fifo_depth.value())
            self.mcs_manager.set_preview_buffer_capacity_samples(
                self.ui.spinBox_preview_buffer_samples.value()
            )
            self.ui.label_preview_buffer_capacity_samples.setText(
                "%d"
                % (
                        self.ui.spinBox_preview_buffer_samples.value()
                        * self.ui.spinBox_time_bin_per_px.value()
                )
            )

            fifo = []
            if self.ui.checkBox_fifo_analog.isChecked():
                fifo.append("stream_out_aux")
            if self.ui.checkBox_fifo_digital.isChecked():
                fifo.append("stream_out_main")

            self.mcs_manager.set_fifo_prebuffer_length(
                self.ui.spinBox_fifo_prebuffer_length.value()
            )
            self.mcs_manager.set_requested_fifo_depth(
                self.ui.spinBox_requested_fifo_depth.value()
            )

            try:
                self.mcs_manager.connect(mydict, list_fifos=fifo)
            except Exception as e:
                raise RuntimeError(str(e) or "FPGA initialization failed.") from e

            # self.mcs_manager.start()

        self._update_fpga_connection_button()

    def setRegistersDict(self, myconf):
        """
        Set the registers dictionary which is mapped to the FPGA
        """
        self.configurationFPGA_dict.update(myconf)
        # debug("setRegistersDict", self.configurationFPGA_dict)
        self.mcs_manager.setRegistersDict(myconf)
        # debug("Waiting setRegistersDict")

    @Slot()
    def panoramaButton(self):
        """
        Slot for the panorama button event
        It copy the current image to the panorama image place
        """
        xr = self.ui.spinBox_default_range_x.value()
        yr = self.ui.spinBox_default_range_y.value()
        xoff = self.ui.spinBox_default_off_x_um.value()
        yoff = self.ui.spinBox_default_off_y_um.value()

        self.ui.spinBox_range_x.setValue(xr)
        self.ui.spinBox_range_y.setValue(yr)
        self.ui.spinBox_range_z.setValue(self.ui.spinBox_default_range_z.value())

        self.ui.spinBox_off_x_um.setValue(xoff)
        self.ui.spinBox_off_y_um.setValue(yoff)
        self.ui.spinBox_off_z_um.setValue(self.ui.spinBox_default_off_z_um.value())

        self.currentImage_pos = np.asarray(
            (
                xoff + max(xr - yr, 0) / 2,
                yoff + max(yr - xr, 0) / 2,
                self.ui.spinBox_off_z_um.value(),
            )
        )

        self.currentImage_size = np.asarray(
            (min(xr, yr), min(xr, yr), self.ui.spinBox_range_z.value())
        )

        self.currentImage_pixels = np.asarray(
            (
                self.ui.spinBox_nx.value(),
                self.ui.spinBox_ny.value(),
                self.ui.spinBox_nframe.value(),
            )
        )

        if self.started_preview or self.started_normal:
            self.plotPreviewImage()
        else:
            self.plotPreviewImage(self.currentImage)
        self.AutoRange_im_widget()

    # def roi_panoramaModified(self, event):
    #     debug(event.pos().x(), event.pos().y(), event.size().x(), event.size().y())
    #     if not self.rect_roi_panorama_modified_lock:
    #         try:
    #             # print(event.pos().x(), event.pos().y(), event.size().x(), event.size().y())
    #
    #             xr = self.rect_roi_panorama.size().x()
    #             yr = self.rect_roi_panorama.size().y()
    #             xoff = self.rect_roi_panorama.pos().x()
    #             yoff = self.rect_roi_panorama.pos().y()
    #
    #             self.lock_range_changing = True
    #
    #             self.ui.spinBox_range_x.setValue(xr)
    #             self.ui.spinBox_range_y.setValue(yr)
    #
    #             self.ui.spinBox_off_x_um.setValue(xoff)
    #             self.ui.spinBox_off_y_um.setValue(yoff)
    #
    #             self.currentImage_pos = np.asarray(
    #                 (
    #                     xoff + max(xr - yr, 0) / 2,
    #                     yoff + max(yr - xr, 0) / 2,
    #                     self.ui.spinBox_off_z_um.value(),
    #                 )
    #             )
    #
    #             self.currentImage_size = np.asarray(
    #                 (min(xr, yr), min(xr, yr), self.ui.spinBox_range_z.value())
    #             )
    #
    #             self.currentImage_pixels = np.asarray(
    #                 (
    #                     self.ui.spinBox_nx.value(),
    #                     self.ui.spinBox_ny.value(),
    #                     self.ui.spinBox_nframe.value(),
    #                 )
    #             )
    #
    #             self.rect_roi_panorama_modified_lock = True
    #
    #             # v = self.im_panorama_widget.getView()
    #             # yR = v.getAxis("left").range
    #             # xR = v.getAxis("bottom").range
    #             # ratio = abs((yR[0] - yR[1]) / (xR[0] - xR[1]))
    #             # v.getAxis("left").setRange()
    #             # v.getAxis("bottom").setRange()
    #             self.im_widget.view.setRange(
    #                 xRange=[xr, xr + xoff], yRange=[yr, yr + yoff]
    #             )
    #
    #             self.plotPreviewImage()
    #
    #             self.AutoRange_im_widget()
    #
    #             self.rect_roi_panorama_modified_lock = False
    #             self.lock_range_changing = False
    #         except Exception as exc:
    #             self.rect_roi_panorama_modified_lock = False
    #             debug(exc)
    #
    #     else:
    #         debug("self.rect_roi_panorama_modified_lock")

    def AutoRange_im_widget(self):
        """
        Auto range the image widget
        """
        lock_range_changing = self.lock_range_changing
        roi_visible = self.rect_roi.isVisible()

        self.lock_range_changing = True
        self.rect_roi.hide()
        self.marker_plot.hide()
        self.marker_plot_circular_scan.hide()

        self.im_widget.getView().autoRange(padding=0)

        if roi_visible:
            self.rect_roi.show()

        self.marker_plot_circular_scan.show()
        self.marker_plot.show()
        self.lock_range_changing = lock_range_changing
        self.updateRoiPanaorama()

    def updateRoiPanaorama(self):
        """
        update the panorama ROI
        """
        logger.debug("updateRoiPanaorama")
        self.rect_roi_panorama_modified_lock = True

        pos = (
            self.currentImage_pos[0] - self.currentImage_size[0] / 2.0,
            self.currentImage_pos[1] - self.currentImage_size[1] / 2.0,
        )

        size = (self.currentImage_size[0], self.currentImage_size[1])

        self.rect_roi_panorama.setPos(pos)
        self.rect_roi_panorama.setSize(size)
        self.rect_roi_panorama_modified_lock = False

    def roiModified(self, event):
        """
        roiModified event - DUMMY
        """
        logger.debug("SKIP roiModified")
        return
        # self.rect_roi_panorama.setPos(self.rect_roi.pos())
        # self.rect_roi_panorama.setSize(self.rect_roi.size())
        # print(event)
        # debug(event.pos().x(), event.pos().y(), event.size().x(), event.size().y())
        # if not self.rect_roi_modified_lock:
        #     # print(event.pos().x(), event.pos().y(), event.size().x(), event.size().y())
        #
        #     self.lock_parameters_changed_call = True
        #     debug("roiModified self.lock_parameters_changed_call SET True")
        #
        #     self.ui.spinBox_off_x_um.setValue(self.rect_roi.pos().x())
        #     self.ui.spinBox_off_y_um.setValue(self.rect_roi.pos().y())
        #
        #     self.ui.spinBox_range_x.setValue(self.rect_roi.size().x())
        #     self.ui.spinBox_range_y.setValue(self.rect_roi.size().y())
        #     self.offset_um_Changed(force=True)
        #     self.lock_parameters_changed_call = False
        #     debug("roiModified self.lock_parameters_changed_call UNSET False")
        # else:
        #     debug("self.rect_roi_modified_lock")

    def setSelectedChannel(self, ch):
        """
        set the selected channel
        """
        self.selected_channel = ch
        logger.debug("%s %s", "setSelectedChannel", ch)
        i = self.ui.comboBox_plot_channel.findText("%d" % ch)
        logger.debug(i)
        if 0 <= i < self.spad_channels:
            self.ui.comboBox_plot_channel.setCurrentIndex(i)
        else:
            ii = self.ui.comboBox_plot_channel.findText("Sum")
            logger.debug(ii)
            self.ui.comboBox_plot_channel.setCurrentIndex(ii)

    @Slot()
    def about(self):
        """
        Show the about dialog box with license
        """

        self.textBrowser = QTextBrowser(None)
        self.textBrowser.setObjectName("textBrowser")
        self.textBrowser.setHtml(
            resource_path("ui/qt/about.html").read_text(encoding="utf-8")
        )
        # retranslateUi
        self.textBrowser.show()
        self.textBrowser.setWindowTitle("About")

        desktop = QDesktopWidget()
        half_desktop = desktop.size() / 2
        self.textBrowser.resize(half_desktop * 1.5)
        self.textBrowser.move(60, 60)

    def imageMoved(self, event):
        """
        image moved event
        """
        mouse_point = event
        pos = self.im_widget.view.vb.mapToView(mouse_point)
        self.statusBar_mousePosition.setText("x: %f   y: %f" % (pos.x(), pos.y()))

    def imageClicked(self, event):
        """
        Handle a double-click as either move-to or add-marker.

        Ctrl selects move-to by default.  The preview inversion control swaps
        the two actions.
        """
        mouse_event = event
        mouse_point = mouse_event.pos()
        projection = self.ui.comboBox_view_projection.currentText()

        if mouse_event.double():
            logger.debug("Double click")
            logger.debug(mouse_point)
            pos = self.im_widget.view.vb.mapToView(mouse_point)

            if projection == "xy":
                a = (pos.x(), pos.y(), self.ui.spinBox_off_z_um.value())
            elif projection == "zy":
                a = (self.ui.spinBox_off_x_um.value(), pos.y(), pos.x())
            elif projection == "xz":
                a = (pos.x(), self.ui.spinBox_off_y_um.value(), pos.y())
            elif projection == "yx":
                a = (pos.y(), pos.x(), self.ui.spinBox_off_z_um.value())
            elif projection == "yz":
                a = (self.ui.spinBox_off_x_um.value(), pos.x(), pos.y())
            elif projection == "zx":
                a = (pos.y(), self.ui.spinBox_off_y_um.value(), pos.x())

            logger.debug("%s %s", "event.modifiers()", event.modifiers())

            if self.preview_view_box.navigation_allowed(event.modifiers()):
                logger.debug("imageClicked(): move to position")
                self.ui.spinBox_off_x_um.setValue(a[0])
                self.ui.spinBox_off_y_um.setValue(a[1])
                self.ui.spinBox_off_z_um.setValue(a[2])
                self.offset_um_Changed()
            else:
                conf = self.getGUI_data()

                conf["offset_x_um"] = a[0]
                conf["offset_y_um"] = a[1]
                conf["offset_z_um"] = a[2]

                self.markers_list.append(conf)
                self.drawMarkers()
                self.markersViewTable()

    @Slot(bool)
    def previewControlModeChanged(self, inverted):
        """Apply and explain the selected Ctrl interaction mode."""
        inverted = bool(inverted)
        self.preview_view_box.set_control_inverted(inverted)
        if inverted:
            self.ui.label_106.setText(
                "Ctrl+Drag/Wheel: image only; Drag/Wheel/Double-Click: microscope"
            )
            self.ui.label_107.setText("Ctrl+Double-Click: set a Marker")
        else:
            self.ui.label_106.setText(
                "Drag/Wheel: image only; Ctrl+Drag/Wheel/Double-Click: microscope"
            )
            self.ui.label_107.setText("Double-Click: set a Marker")


    def drawMarkers(self):
        """
        draw the markers on the image
        """
        projection = self.ui.comboBox_view_projection.currentText()

        i = "offset_x_um"
        j = "offset_y_um"
        if projection == "xy":
            i = "offset_x_um"
            j = "offset_y_um"
        elif projection == "zy":
            i = "offset_z_um"
            j = "offset_y_um"
        elif projection == "xz":
            i = "offset_x_um"
            j = "offset_z_um"
        elif projection == "yx":
            i = "offset_y_um"
            j = "offset_x_um"
        elif projection == "yz":
            i = "offset_y_um"
            j = "offset_z_um"
        elif projection == "zx":
            i = "offset_z_um"
            j = "offset_x_um"
        else:
            i = "offset_x_um"
            j = "offset_y_um"
            logger.debug("NO PROJECTION IN DRAWMARKES")

        self.marker_plot.clear()

        for n, k in enumerate(self.markers_list):
            self.marker_plot.addPoints(
                x=[
                    k[i],
                ],
                y=[
                    k[j],
                ],
                pen="w",
                brush="b",
                size=10,
                symbol="+",
            )

    def fingerprintClicked(self, event):
        """
        fingerprint clicked event
        """
        mouse_point = event.pos()

        if event.double():
            logger.debug("Double click")

        self.fingerprint_widget.scene.itemsBoundingRect().contains(mouse_point)
        logger.debug("%s %s %s %s", "x=", mouse_point.x(), " y=", mouse_point.y())
        pos = self.fingerprint_widget.view.mapSceneToView(mouse_point)
        logger.debug(pos)
        logger.debug(event)
        selected_ch_x = int((pos.x()))
        selected_ch_y = int((pos.y()))
        logger.debug(event.modifiers())
        if event.modifiers() & Qt.ControlModifier:
            logger.debug("Qt.CTRL")
            if self.fingerprint_mask[selected_ch_y, selected_ch_x] == 1:
                self.fingerprint_mask[selected_ch_y, selected_ch_x] = 0
            else:
                self.fingerprint_mask[selected_ch_y, selected_ch_x] = 1
            self.update_fingerprint_mask()

        else:
            self.setSelectedChannel(selected_ch_x + 5 * selected_ch_y)
            logger.debug("%s %s %s %s %s %s %s", "You clicked on the channel ", self.selected_channel, "(x:", selected_ch_x, " y:", selected_ch_y, ")")
            # self.plotCurrentImage()

    def update_fingerprint_mask(self):
        """
        update the fingerprint mask
        """
        logger.debug("update_fingerprint_mask")
        self.fingerprint_markers_mask.clear()
        for xxx in range(self.spad_channels_x):
            for yyy in range(self.spad_channels_y):
                if self.fingerprint_mask[yyy, xxx] != 1:
                    self.fingerprint_markers_mask.addPoints(
                        x=[
                            xxx + 0.5,
                        ],
                        y=[
                            yyy + 0.5,
                        ],
                        pen="w",
                        brush="b",
                        size=5,
                        symbol="o",
                    )

        if self.mcs_manager.shared_arrays_ready:
            logger.debug("ready self.mcs_manager.shared_arrays_ready")
            self.mcs_manager.set_fingerprint_mask(
                np.ravel(self.fingerprint_mask)
            )
        else:
            logger.debug("not ready self.mcs_manager.shared_arrays_ready")

    # def dragEnterEvent(self, event):
    #     debug(event)
    #     if event.mimeData().hasUrls:
    #         event.accept()
    #     else:
    #         event.ignore()

    # def dragMoveEvent(self, event):
    #     debug(event)
    #     if event.mimeData().hasUrls:
    #         event.setDropAction(Qt.CopyAction)
    #         event.accept()
    #     else:
    #         event.ignore()

    # def dropEvent(self, event):
    #     if event.mimeData().hasUrls:
    #         event.setDropAction(Qt.CopyAction)
    #         event.accept()
    #         links = []
    #         for url in event.mimeData().urls():
    #             debug(url.toLocalFile())
    #             self.loadFile(url.toLocalFile())
    #     else:
    #         event.ignore()

    # def loadFile(self, file_name):
    #     self.activeFile = True
    #     hf = h5py.File(file_name, "r")
    #
    #     debug(hf)
    #
    #     if "default" in hf.attrs:
    #         debug("h5.attrs default", hf.attrs["default"])
    #     else:
    #         debug("h5.attrs default NOT FOUND")
    #
    #     if "data_format_version" in hf.attrs:
    #         debug("h5.attrs data_format_version", hf.attrs["data_format_version"])
    #     else:
    #         debug("h5.attrs data_format_version NOT FOUND")
    #
    #     self.currentImage = np.asarray(hf["data"])
    #     debug(self.currentImage.shape)
    #
    #     if 'configuration' in hf.attrs:
    #         for i in hf['configuration'].attrs:
    #             debug(i, hf['configuration'].attrs[i])
    #             self.configurationFPGA_dict.update({i: hf['configuration'].attrs[i]})
    #     else:
    #         debug("h5.attrs configuration NOT FOUND")
    #
    #     self.plotCurrentImage()
    #
    #     data_finger_print = self.currentImage.sum(axis=(0, 1, 2, 3, 4)).reshape(5, 5)
    #
    #     self.draw_fingerprint(data_finger_print)
    #
    #     self.ui.pushButton_napari.setEnabled(True)
    @Slot()
    def radioButton_ttm_type_ttm_toggle(self):
        self.ui.radioButton_ttm_type_uttm.setChecked(
            not self.ui.radioButton_ttm_type_ttm.isChecked()
        )

    @Slot()
    def radioButton_ttm_type_uttm_toggle(self):
        self.ui.radioButton_ttm_type_ttm.setChecked(
            not self.ui.radioButton_ttm_type_uttm.isChecked()
        )



    @Slot()
    def radio_ttm_local(self):
        """
        activate or disactivate the checkbox TTM in local mode
        """
        self.ui.radioButton_ttm_remote.setChecked(
            not self.ui.radioButton_ttm_local.isChecked()
        )
        self.ui.lineEdit_ttm_filename.setEnabled(True)
        self.ui.toolButton_ttm_filename.setEnabled(True)

    @Slot()
    def radio_ttm_remote(self):
        """
        activate or disactivate the checkbox TTM in remote mode
        """
        self.ui.radioButton_ttm_local.setChecked(
            not self.ui.radioButton_ttm_remote.isChecked()
        )
        self.ui.lineEdit_ttm_filename.setEnabled(False)
        self.ui.toolButton_ttm_filename.setEnabled(False)

    @Slot()
    def selectedAutoscaleImg(self):
        """
        Slot for the autoscale image checkbox
        """
        self.autoscale_image = self.ui.checkBox_autoscale_img.isChecked()
        logger.debug("%s %s", "selectedAutoscaleImg()", self.autoscale_image)

    @Slot()
    def selectedAutoscaleFingerprint(self):
        """
        Slot for the autoscale fingerprint checkbox
        """
        self.autoscale_fingerprint = self.ui.checkBox_autoscale_fingerprint.isChecked()
        logger.debug("%s %s", "selectedAutoscaleFingerprint", self.autoscale_fingerprint)

    # @Slot()
    # def selectedCumulativeFingerprint(self):
    #     self.cumulative_fingerprint = self.ui.checkBox_cumulative_fingerprint.isChecked()
    #     print("selectedCumulativeFingerprint", self.cumulative_fingerprint)

    @Slot()
    def microimageType(self, num):
        """
        Slot for the microimage type selection
        """
        logger.debug("%s %s", "microimageType ", num)
        self.fingerprint_visualization = num
        # if num == 0:    # cumulative
        # elif num == 1:  # 10000 bins
        # elif num == 2:  # fingerprint

    @Slot()
    def addToBatch(self):
        self.table_manager.add_dict(self.getGUI_data())

    def finalizeImage(self):
        logger.debug("finalizeImage()")
        self.plotCurrentImage()
        data_finger_print = self.mcs_manager.getFingerprint()
        if data_finger_print is None:
            pass
        else:
            if self.autoscale_fingerprint:
                self.fingerprint_widget.setImage(
                    data_finger_print.T,
                    autoLevels=True,
                    autoRange=True,
                    autoHistogramRange=True,
                )
            else:
                self.fingerprint_widget.setImage(
                    data_finger_print.T,
                    autoLevels=False,
                    autoRange=False,
                    autoHistogramRange=False,
                )

    def _status_tree_source(self, tree):
        if tree is self.ui.treeView_2:
            return "Conf. FPGA dict.", self.configurationFPGA_dict
        if tree is self.ui.treeView_3:
            return "Conf. GUI dict.", self.configurationGUI_dict
        return "Read Conf. FPGA", self._latest_status_registers

    def statusRegisterContextMenu(self, tree, position):
        """Offer monitoring for scalar numeric FPGA status registers."""
        index = tree.indexAt(position)
        if not index.isValid():
            return
        name_index = index.sibling(index.row(), 0)
        value_index = index.sibling(index.row(), 1)
        register_name = name_index.data(Qt.ItemDataRole.DisplayRole)
        source_name, source = self._status_tree_source(tree)
        value = source.get(register_name)
        numeric_value = self._coerce_monitor_value(value)

        # TEMP DEBUG: remove after the monitor context-menu behavior is verified.
        print(
            "[Monitor debug] right-click",
            {
                "tree": source_name,
                "register": register_name,
                "raw_value": repr(value),
                "display_value": value_index.data(Qt.ItemDataRole.DisplayRole),
                "numeric_value": numeric_value,
            },
        )

        menu = QMenu(self)
        action = menu.addAction("Add to Monitor")
        monitor_id = (source_name, register_name)
        action.setEnabled(
            numeric_value is not None
            and monitor_id not in self._monitored_registers
        )
        selected_action = menu.exec(
            tree.viewport().mapToGlobal(position)
        )
        if selected_action is action:
            self.addRegisterToMonitor(
                register_name,
                source_name=source_name,
                value=numeric_value,
            )

    @staticmethod
    def _coerce_monitor_value(value):
        if isinstance(value, (bool, np.bool_, str, bytes)):
            return None
        try:
            array = np.asarray(value)
            if array.ndim != 0:
                return None
            numeric_value = float(array.item())
        except (TypeError, ValueError, OverflowError):
            return None
        return numeric_value if np.isfinite(numeric_value) else None

    @classmethod
    def _is_monitorable_value(cls, value):
        return cls._coerce_monitor_value(value) is not None

    def addRegisterToMonitor(
        self,
        register_name,
        source_name="Read Conf. FPGA",
        value=None,
    ):
        """Add one FPGA register and its latest value to the time trace."""
        monitor_id = (source_name, register_name)
        if monitor_id in self._monitored_registers:
            return
        if value is None:
            _, source = self._status_tree_source(
                {
                    "Read Conf. FPGA": self.ui.treeView,
                    "Conf. FPGA dict.": self.ui.treeView_2,
                    "Conf. GUI dict.": self.ui.treeView_3,
                }[source_name]
            )
            value = self._coerce_monitor_value(source.get(register_name))
        if value is None:
            raise ValueError(
                f"Register {register_name!r} does not contain a numeric scalar."
            )

        # TEMP DEBUG: remove after monitor selection is verified.
        print(
            "[Monitor debug] adding",
            {
                "tree": source_name,
                "register": register_name,
                "value": value,
            },
        )

        color = pg.intColor(
            len(self._monitored_registers),
            hues=max(8, len(self._monitored_registers) + 1),
        )
        curve_name = f"{source_name} / {register_name}"
        curve = self.monitor_plot_widget.plot(
            pen=pg.mkPen(color, width=2),
            name=curve_name,
        )
        elapsed = time.monotonic() - self._monitor_started_at
        self._monitored_registers[monitor_id] = {
            "source_name": source_name,
            "register_name": register_name,
            "times": [elapsed],
            "values": [float(value)],
            "curve": curve,
        }
        curve.setData([elapsed], [float(value)])

    def _append_monitor_points(self, sources, timestamp=None):
        if not self._monitored_registers:
            return
        elapsed = (
            time.monotonic() - self._monitor_started_at
            if timestamp is None
            else float(timestamp)
        )
        for trace in self._monitored_registers.values():
            source = sources.get(trace["source_name"], {})
            value = self._coerce_monitor_value(
                source.get(trace["register_name"])
            )
            if value is None:
                continue
            trace["times"].append(elapsed)
            trace["values"].append(value)
            trace["curve"].setData(trace["times"], trace["values"])

    @Slot()
    def resetMonitor(self):
        """Remove all selected registers and their accumulated samples."""
        self._monitored_registers.clear()
        self.monitor_plot_widget.clear()
        legend = self.monitor_plot_widget.plotItem.legend
        if legend is not None:
            legend.clear()
        self._monitor_started_at = time.monotonic()

    @staticmethod
    def _circular_points_for_projection(
        registers,
        projection,
        calibration,
        offset,
        point_count,
        scan_range=None,
        pixel_counts=None,
    ):
        """Add calibrated circular displacements to raster-pixel centers."""
        arrays = []
        for register_name in (
            "circular_scan_x_volts",
            "circular_scan_y_volts",
            "circular_scan_z_volts",
        ):
            try:
                array = np.asarray(
                    registers.get(register_name, []), dtype=float
                ).reshape(-1)
            except (TypeError, ValueError):
                return np.asarray([]), np.asarray([])
            arrays.append(array)

        count = min(
            max(0, int(point_count)),
            *(len(array) for array in arrays),
        )
        if count == 0:
            return np.asarray([]), np.asarray([])

        circular_displacements = [
            arrays[axis][:count] * float(calibration[axis])
            for axis in range(3)
        ]
        axes = {
            "xy": (0, 1),
            "yx": (1, 0),
            "zy": (2, 1),
            "yz": (1, 2),
            "zx": (2, 0),
            "xz": (0, 2),
        }.get(projection, (0, 1))

        if scan_range is None or pixel_counts is None:
            raster_centers = [
                np.asarray([float(offset[axis])]) for axis in range(3)
            ]
        else:
            raster_centers = []
            for axis in range(3):
                axis_count = max(1, int(pixel_counts[axis]))
                axis_range = float(scan_range[axis])
                pixel_size = axis_range / axis_count
                raster_centers.append(
                    float(offset[axis])
                    - axis_range / 2.0
                    + (np.arange(axis_count, dtype=float) + 0.5)
                    * pixel_size
                )

        projected_center_x, projected_center_y = np.meshgrid(
            raster_centers[axes[0]],
            raster_centers[axes[1]],
            indexing="xy",
        )
        center_x = projected_center_x.reshape(-1, 1)
        center_y = projected_center_y.reshape(-1, 1)
        projected_x = (
            center_x + circular_displacements[axes[0]].reshape(1, -1)
        ).reshape(-1)
        projected_y = (
            center_y + circular_displacements[axes[1]].reshape(1, -1)
        ).reshape(-1)
        return projected_x, projected_y

    def updateCircularPoints(self):
        """Read, calibrate, offset, and display the circular voltage arrays."""
        registers = dict(self._latest_status_registers)
        # Prefer the values most recently configured by this application. The
        # live readback may still contain the previous point count briefly.
        registers.update(self.configurationFPGA_dict)
        projection = self.ui.comboBox_view_projection.currentText()
        calibration = (
            self.ui.spinBox_calib_x.value(),
            self.ui.spinBox_calib_y.value(),
            self.ui.spinBox_calib_z.value(),
        )
        # Use exactly the same geometry as getCurrentPreviewImage(). This keeps
        # the calibrated trajectory aligned with the image even when the live
        # GUI controls have changed since that image was acquired.
        offset = tuple(float(value) for value in self.currentImage_pos)
        scan_range = tuple(float(value) for value in self.currentImage_size)
        pixel_counts = tuple(
            max(1, int(value)) for value in self.currentImage_pixels
        )
        point_count = self.ui.spinBox_circular_points.value()
        x_points, y_points = self._circular_points_for_projection(
            registers=registers,
            projection=projection,
            calibration=calibration,
            offset=offset,
            point_count=point_count,
            scan_range=scan_range,
            pixel_counts=pixel_counts,
        )

        debug_payload = {
            "projection": projection,
            "point_count": point_count,
            "lissajous_active": self.ui.checkBox_lissajous.isChecked(),
            "lissajous_open_curve": (
                self.ui.checkBox_lissajous_opencurve.isChecked()
            ),
            "omega_x": self.ui.spinBox_lissajous_omega_x.value(),
            "omega_y": self.ui.spinBox_lissajous_omega_y.value(),
            "phase_deg": self.ui.spinBox_lissajous_phase_deg.value(),
            "first_position": (
                self.ui.spinBox_lissajous_firstposition.value()
            ),
            "circular_scan_x_volts": repr(registers.get("circular_scan_x_volts")),
            "circular_scan_y_volts": repr(registers.get("circular_scan_y_volts")),
            "circular_scan_z_volts": repr(registers.get("circular_scan_z_volts")),
            "calibration_um_per_v": calibration,
            "offset_um": offset,
            "scan_range_um": scan_range,
            "pixel_counts": pixel_counts,
            "replicated_points": len(x_points),
            "projected_x_um": x_points.tolist(),
            "projected_y_um": y_points.tolist(),
        }
        debug_signature = repr(debug_payload)
        if debug_signature != self._last_circular_debug_signature:
            # TEMP DEBUG: remove after the Circular overlay is verified.
            print("[Circular debug]", debug_payload)
            self._last_circular_debug_signature = debug_signature

        self.circular_scan_points.setData(x=x_points, y=y_points)
        try:
            trajectory_point_count = min(
                int(point_count),
                *(
                    np.asarray(registers.get(register_name, [])).size
                    for register_name in (
                        "circular_scan_x_volts",
                        "circular_scan_y_volts",
                        "circular_scan_z_volts",
                    )
                ),
            )
        except (TypeError, ValueError):
            trajectory_point_count = 0
        if trajectory_point_count > 0:
            self.circular_scan_first_points.setData(
                x=x_points[::trajectory_point_count],
                y=y_points[::trajectory_point_count],
            )
        else:
            self.circular_scan_first_points.setData(x=[], y=[])
        self.circular_preview_plot_item.setLabel(
            "bottom", projection[0], units="um"
        )
        self.circular_preview_plot_item.setLabel(
            "left", projection[1], units="um"
        )
        if len(x_points):
            self.circular_preview_plot_item.autoRange()

    def updateCircularPreview(self):
        """Mirror the central preview and overlay calibrated circular points."""
        self.updateCircularPoints()
        try:
            preview = self.getCurrentPreviewImage()
            if preview is None:
                return
            (
                preview_img,
                channel,
                auto_levels,
                _auto_range,
                position,
                scale,
            ) = preview

            if self.isLifetimeColorChannel(channel):
                tcycle_ns = 1e3 / (
                    max(float(self.dfd_cycle_mhz), 1e-12)
                    * max(int(self.mcs_manager.clk_multiplier), 1)
                )
                h_shift = 0.0
                if tcycle_ns > 0.0:
                    h_shift = (
                        self.ui.doubleSpinBox_delta_tau_ns.value() % tcycle_ns
                    ) / tcycle_ns
                self.circular_preview_widget.setFlimImage(
                    preview_img,
                    valid=preview_img[:, :, 2],
                    h_display_max=tcycle_ns,
                    h_shift=h_shift,
                    render_mode=self.getLifetimeColorRenderMode(channel),
                    hue_display_range=self.getLifetimeHueDisplayRange(),
                    force_quality_full=self.getLifetimeForceQualityFull(),
                    autoLevels=auto_levels,
                    autoRange=True,
                    pos=position,
                    scale=scale,
                )
            else:
                level_mode = "rgba" if channel.startswith("RGB") else "mono"
                self.circular_preview_widget.setImage(
                    preview_img,
                    levelMode=level_mode,
                    autoLevels=auto_levels,
                    autoRange=True,
                    pos=position,
                    scale=scale,
                )
        except Exception:
            logger.exception("Could not update the Circular status preview")

    @Slot()
    def updateTables(self):
        """
        Update the Status tables
        """
        if self.mcs_manager.is_connected == True:
            fff = self.mcs_manager.fpga_handle.register_read_all()
        else:
            fff = self.mcs_manager.get_registers_configuration()
        self._latest_status_registers = dict(fff)

        try:
            t = [
                str(fff[i])
                for i in (
                    "current_time_bin_index",
                    "current_x_index",
                    "current_y_index",
                    "current_z_index",
                    "current_repetition_index",
                    # "current_cycle",
                )
            ]
        except:
            t = ["na"] * 5

        self.statusBar_currentPosition.setText(
            "B:%s X:%s Y:%s Z:%s R:%s" % (t[0], t[1], t[2], t[3], t[4])
        )



        if self.ui.treeView.model() is None:  # first time only
            model = TreeModel(["Parameter", "Data"], fff, sort_first_column=True, view=self.ui.treeView)
            self.ui.treeView.setModel(model)
            self.ui.treeView.expandAll()
            self.ui.treeView.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            self.ui.treeView.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        else:
            self.ui.treeView.model().updateData(fff)


        fff = self.configurationFPGA_dict

        if self.ui.treeView_2.model() is None:  # first time only
            model = TreeModel(["Parameter", "Data"], fff, sort_first_column=True, view=self.ui.treeView_2)
            self.ui.treeView_2.setModel(model)
            self.ui.treeView_2.expandAll()
            self.ui.treeView_2.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            self.ui.treeView_2.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        else:
            self.ui.treeView_2.model().updateData(fff)


        fff = self.configurationGUI_dict

        if self.ui.treeView_3.model() is None:  # first time only
            model = TreeModel(["Parameter", "Data"], fff, sort_first_column=True, view=self.ui.treeView_3)
            self.ui.treeView_3.setModel(model)
            self.ui.treeView_3.expandAll()
            self.ui.treeView_3.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            self.ui.treeView_3.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        else:
            self.ui.treeView_3.model().updateData(fff)

        self._append_monitor_points(
            {
                "Read Conf. FPGA": self._latest_status_registers,
                "Conf. FPGA dict.": self.configurationFPGA_dict,
                "Conf. GUI dict.": self.configurationGUI_dict,
            }
        )


    @Slot()
    def test1(self):
        """
        dummy button clicked event for test
        """
        logger.debug("test1()")
        self.finalizeImage()

    @Slot()
    def test2(self):
        """
        dummy button clicked event for test
        """
        logger.debug("test2()")
        self.webcam_capture = iio.get_reader("<video0>")

    @Slot()
    def test3(self):
        """
        dummy button clicked event for test
        """
        frame = self.webcam_capture.get_next_data()
        logger.debug(frame.shape)
        self.webcam_widget.setImage(np.moveaxis(frame, [0, 1, 2], [1, 0, 2]))
        logger.debug("test3()")

    @Slot()
    def test4(self):
        """
        dummy button clicked event for test
        """
        pass
        # self.openConsoleWidget()

    @Slot()
    def test5(self):
        """
        dummy button clicked event for test
        """
        logger.debug("test5()")
        import ipykernel.kernelbase

        class a(ipykernel.kernelbase.Kernel):
            pass

        from ipykernel.kernelapp import IPKernelApp

        IPKernelApp.launch_instance(kernel_class=a)

        fff = a()

    @Slot()
    def test6(self):
        """
        dummy button clicked event for test
        """
        self.updateTables()

    @Slot()
    def test7(self):
        """
        dummy button clicked event for test
        """
        logger.debug("test7() as start but no run")

        if self.ui.checkBox_ttmActivate.isChecked():
            self.ttm_activate_change_state()

        # self.myfpgainst.acquisitionThread.reset_data()
        self.ui.pushButton_acquisitionStart.setEnabled(False)
        self.ui.pushButton_externalProgram.setEnabled(False)
        self.ui.pushButton_stop.setEnabled(True)

        if not self.mcs_manager.is_connected:
            logger.debug("not self.mcs_manager.is_connected")
            self.connectFPGA()
        else:
            logger.debug("FPGA Already connected!")

        self.updatePreviewConfiguration()

        self.currentImage = None
        self.activeFile = False

        self.started_normal = True
        self.started_preview = False

        self.rect_roi.hide()

        self.ui.progressBar_repetition.setValue(0)
        self.ui.progressBar_frame.setMaximum(0)
        self.ui.progressBar_fifo_digital.setMaximum(5)
        self.ui.progressBar_fifo_analog.setMaximum(5)
        self.ui.progressBar_saving.setMaximum(5)

        self.configurationGUI_dict_beforeStart = self.getGUI_data()
        # self.configurationGUI_dict_beforeStart = self.configurationGUI_dict.copy()

        self.initializeAcquisition(do_not_save=True, do_run=False)
        self.last_acquisition_started_at = self._make_status_timestamp()
        self._set_program_state(self.PROGRAM_STATE_ACQUISITION, "test_mode_started")

    @Slot()
    def test8(self):
        """
        dummy button clicked event for test
        """
        pass
        # self.define_circular()

    @Slot(bool)
    def lissajousModeChanged(self, enabled):
        """Enable Lissajous controls or restore the standard unit circle."""
        self.ui.checkBox_lissajous_opencurve.setEnabled(enabled)
        self.ui.spinBox_lissajous_omega_x.setEnabled(enabled)
        self.ui.spinBox_lissajous_omega_y.setEnabled(enabled)
        self.ui.spinBox_lissajous_phase_deg.setEnabled(enabled)
        self.ui.spinBox_lissajous_firstposition.setEnabled(enabled)
        if not enabled:
            for spinbox in (
                self.ui.spinBox_lissajous_omega_x,
                self.ui.spinBox_lissajous_omega_y,
            ):
                signals_were_blocked = spinbox.blockSignals(True)
                spinbox.setValue(1)
                spinbox.blockSignals(signals_were_blocked)
            signals_were_blocked = (
                self.ui.spinBox_lissajous_phase_deg.blockSignals(True)
            )
            self.ui.spinBox_lissajous_phase_deg.setValue(0)
            self.ui.spinBox_lissajous_phase_deg.blockSignals(
                signals_were_blocked
            )
            signals_were_blocked = (
                self.ui.spinBox_lissajous_firstposition.blockSignals(True)
            )
            self.ui.spinBox_lissajous_firstposition.setValue(0)
            self.ui.spinBox_lissajous_firstposition.blockSignals(
                signals_were_blocked
            )

        self.updateLissajousMiniPlot()
        if (
            hasattr(self, "mcs_manager")
            and self.ui.checkBox_circular.isChecked()
        ):
            self.circularMotionActivateChanged()

    @Slot(bool)
    @Slot(int)
    def lissajousFrequencyChanged(self, _value):
        """Regenerate the active trajectory after an omega change."""
        if not self.ui.checkBox_lissajous.isChecked():
            self.lissajousModeChanged(False)
            return
        self.updateLissajousMiniPlot()
        if (
            hasattr(self, "mcs_manager")
            and self.ui.checkBox_circular.isChecked()
        ):
            self.circularMotionActivateChanged()

    @staticmethod
    def _lissajous_offsets(
        radius,
        point_count,
        omega_x=1,
        omega_y=1,
        phase_deg=0,
        first_position=0,
        open_curve=False,
    ):
        """Return a rotated trajectory with the selected point at index zero."""
        point_count = int(point_count)
        if point_count <= 0:
            return np.asarray([], dtype=float), np.asarray([], dtype=float)

        if open_curve:
            # The odd x frequency gives opposite x coordinates at the two
            # endpoints, while the integer y frequency returns y to zero.
            t = np.linspace(0.0, 1.0, point_count)
            x_unrotated = (
                -np.cos((2 * int(omega_x) + 1) * np.pi * t)
                * float(radius)
            )
            y_unrotated = (
                np.sin(int(omega_y) * np.pi * t) * float(radius)
            )
        else:
            t = np.linspace(0, 2 * np.pi, point_count + 1)[:-1]
            x_unrotated = np.cos(int(omega_x) * t) * float(radius)
            y_unrotated = np.sin(int(omega_y) * t) * float(radius)
        phase_rad = np.deg2rad(float(phase_deg))
        cos_phase = np.cos(phase_rad)
        sin_phase = np.sin(phase_rad)
        x_values = (
            x_unrotated * cos_phase - y_unrotated * sin_phase,
            x_unrotated * sin_phase + y_unrotated * cos_phase,
        )
        first_index = int(first_position) % point_count
        return (
            np.roll(x_values[0], -first_index),
            np.roll(x_values[1], -first_index),
        )

    def updateLissajousMiniPlot(self):
        """Draw a normalized dense preview of the selected trajectory."""
        if self.ui.checkBox_lissajous.isChecked():
            open_curve = self.ui.checkBox_lissajous_opencurve.isChecked()
            omega_x = self.ui.spinBox_lissajous_omega_x.value()
            omega_y = self.ui.spinBox_lissajous_omega_y.value()
            phase_deg = self.ui.spinBox_lissajous_phase_deg.value()
            first_position = (
                self.ui.spinBox_lissajous_firstposition.value()
            )
        else:
            open_curve = False
            omega_x = 1
            omega_y = 1
            phase_deg = 0
            first_position = 0
        selected_point_count = self.ui.spinBox_circular_points.value()
        maximum_first_position = max(0, selected_point_count - 1)
        signals_were_blocked = (
            self.ui.spinBox_lissajous_firstposition.blockSignals(True)
        )
        self.ui.spinBox_lissajous_firstposition.setMaximum(
            maximum_first_position
        )
        if first_position > maximum_first_position:
            first_position %= selected_point_count
            self.ui.spinBox_lissajous_firstposition.setValue(
                first_position
            )
        self.ui.spinBox_lissajous_firstposition.blockSignals(
            signals_were_blocked
        )
        x_values, y_values = self._lissajous_offsets(
            radius=1.0,
            point_count=512,
            omega_x=omega_x,
            omega_y=omega_y,
            phase_deg=phase_deg,
            open_curve=open_curve,
        )
        if open_curve:
            self.lissajous_mini_curve.setData(x_values, y_values)
        else:
            self.lissajous_mini_curve.setData(
                np.append(x_values, x_values[0]),
                np.append(y_values, y_values[0]),
            )
        sampled_x, sampled_y = self._lissajous_offsets(
            radius=1.0,
            point_count=selected_point_count,
            omega_x=omega_x,
            omega_y=omega_y,
            phase_deg=phase_deg,
            first_position=first_position,
            open_curve=open_curve,
        )
        self.lissajous_mini_points.setData(x=sampled_x, y=sampled_y)
        self.lissajous_mini_first_point.setData(
            x=sampled_x[:1],
            y=sampled_y[:1],
        )
        self.lissajous_mini_plot.autoRange(padding=0.08)

    def define_circular(self, circular_points):
        """
        Define the points for the circular or Lissajous scan.
        """
        radius = self.ui.spinBox_circular_radius_nm.value() / 1000.

        calib_xx = self.ui.spinBox_calib_x.value()
        calib_yy = self.ui.spinBox_calib_y.value()
        calib_zz = self.ui.spinBox_calib_z.value()

        if self.ui.checkBox_lissajous.isChecked():
            open_curve = self.ui.checkBox_lissajous_opencurve.isChecked()
            omega_x = self.ui.spinBox_lissajous_omega_x.value()
            omega_y = self.ui.spinBox_lissajous_omega_y.value()
            phase_deg = self.ui.spinBox_lissajous_phase_deg.value()
            first_position = (
                self.ui.spinBox_lissajous_firstposition.value()
            )
        else:
            open_curve = False
            omega_x = 1
            omega_y = 1
            phase_deg = 0
            first_position = 0
        self.X_array_um, self.Y_array_um = self._lissajous_offsets(
            radius,
            circular_points,
            omega_x,
            omega_y,
            phase_deg,
            first_position,
            open_curve=open_curve,
        )
        self.Z_array_um = np.zeros(circular_points)

        self.X_array = self.X_array_um / calib_xx
        self.Y_array = self.Y_array_um / calib_yy
        self.Z_array = self.Z_array_um / calib_zz

        self.marker_plot_circular_scan.clear()

        self.markers_list_circular = []
        #
        # for i in range(circular_points):
        #     conf = {}
        #     # conf["offset_x_um"] = (self.X_array[i] - (offExtra_x_V + offset_xx))/calib_xx
        #     # conf["offset_y_um"] = (self.Y_array[i] - (offExtra_y_V + offset_yy))/calib_yy
        #     # conf["offset_z_um"] = (self.Z_array[i] - (offExtra_z_V + offset_zz))/calib_zz
        #
        #     conf["offset_x_um"] = self.X_array[i] * calib_xx
        #     conf["offset_y_um"] = self.Y_array[i] * calib_yy
        #     conf["offset_z_um"] = self.Z_array[i] * calib_zz
        #
        #     self.markers_list_circular.append(conf)
        #
        # projection = self.ui.comboBox_view_projection.currentText()
        #
        # i = "offset_x_um"
        # j = "offset_y_um"
        # if projection == "xy":
        #     i = "offset_x_um"
        #     j = "offset_y_um"
        # elif projection == "zy":
        #     i = "offset_z_um"
        #     j = "offset_y_um"
        # elif projection == "xz":
        #     i = "offset_x_um"
        #     j = "offset_z_um"
        # elif projection == "yx":
        #     i = "offset_y_um"
        #     j = "offset_x_um"
        # elif projection == "yz":
        #     i = "offset_y_um"
        #     j = "offset_z_um"
        # elif projection == "zx":
        #     j = "offset_x_um"
        #     i = "offset_z_um"
        # else:
        #     i = "offset_x_um"
        #     j = "offset_y_um"
        #     debug("NO PROJECTION IN DRAWMARKES")
        #
        # for n, k in enumerate(self.markers_list_circular):
        #     self.marker_plot_circular_scan.addPoints(
        #         x=[
        #             k[i],
        #         ],
        #         y=[
        #             k[j],
        #         ],
        #         pen="w",
        #         brush="r",
        #         size=10,
        #         symbol="x",
        #     )

    @Slot()
    def test9(self):
        """
        dummy button clicked event for test
        """
        self.load_circular()

    @Slot()
    def circularMotionActivateChanged(self):
        """
        activate or disactivate the circular motion
        """
        self.updateLissajousMiniPlot()
        if self.ui.checkBox_circular.isChecked():
            circular_points = self.ui.spinBox_circular_points.value()
            self.define_circular(circular_points)
            # self.ui.spinBox_time_bin_per_px.setValue(32)
            # self.ui.spinBox_nx.setValue(circular_points)
            # self.ui.spinBox_ny.setValue(100)
            # self.ui.spinBox_time_bin_per_px.setValue(32)
            self.load_circular()
            self.temporalSettingsChanged()
        else:
            self.markers_list_circular = []
            self.marker_plot_circular_scan.clear()
            self.temporalSettingsChanged()

    def load_circular(self, ARRAY_SIZE=32):
        """
        load the circular scan position to the FPGA registers
        """
        # CIRCULAR MODE
        # ScanXVoltages <==== self.X_array
        # ScanYVoltages <==== self.Y_array
        # ScanZVoltages <==== self.Z_array

        # self.ui.spinBox_time_bin_per_px.setValue(31)

        # debug("previewLoop CIRCULAR <======================================================")
        #
        # self.nrepetition_before_run_preview = self.ui.spinBox_nrepetition.value()
        #
        # # self.myfpgainst.acquisitionThread.reset_data()
        # if not self.mcs_manager.is_connected:
        #     debug("not self.mcs_manager.is_connected")
        #     self.connectFPGA()
        #
        # self.positionSettingsChanged_apply()
        # self.temporalSettingsChanged()
        # self.plotSettingsChanged()

        X_arr = self.X_array
        Y_arr = self.Y_array
        Z_arr = self.Z_array

        if X_arr.shape[0] < 32:
            X_arr = np.pad(X_arr, (0, 32 - X_arr.shape[0]), mode="edge")

        if Y_arr.shape[0] < 32:
            Y_arr = np.pad(Y_arr, (0, 32 - Y_arr.shape[0]), mode="edge")

        if Z_arr.shape[0] < 32:
            Z_arr = np.pad(Z_arr, (0, 32 - Z_arr.shape[0]), mode="edge")

        self.setRegistersDict(
            {
                "circular_scan_x_volts": X_arr,
                "circular_scan_y_volts": Y_arr,
                "circular_scan_z_volts": Z_arr,
            }
        )

        # debug("Start")
        # self.currentImage = None
        # self.activeFile = False
        #
        # self.ui.pushButton_previewStart.setEnabled(False)
        # self.ui.pushButton_acquisitionStart.setEnabled(False)
        # self.ui.pushButton_stop.setEnabled(True)
        #
        # self.started_normal = False
        # self.started_preview = True
        #
        # self.rect_roi.hide()
        #
        # self.ui.progressBar_repetition.setValue(0)
        # self.ui.progressBar_frame.setMaximum(0)
        #
        # self.startAcquisition(do_not_save=True)
    @Slot()
    def addcurrentconfmacro(self):
        """
        Slot for the add current configuration to the table for macros
        """
        logger.debug("addcurrentconfmacro")
        conf = self.getGUI_data()
        self.table_manager.add_dict(conf)
    @Slot()
    def addcurrentconfmacrofcs(self):
        """
        Slot for the add current configuration to the table for macros
        activating FCS preview and forcing to zero the range
        """
        logger.debug("addcurrentconfmacrofcs")
        conf = self.getGUI_data()
        conf["range_x"] = 0.
        conf["range_y"] = 0.
        conf["range_z"] = 0.
        conf["fcs"] = True
        print(conf)
        self.table_manager.add_dict(conf)
    @Slot()
    def copyPositionsMarkers(self):
        """
        copy the markers to the table for macros
        """
        logger.debug("copyPositionMarkers")
        self.table_manager.add_list_of_dict(self.markers_list)

    @Slot()
    def copyPositionsMarkersFCS(self):
        """
        copy the markers to the table for macros
        activating FCS preview and forcing to zero the range
        """
        logger.debug("copyPositionMarkersFCS")
        self.table_manager.add_list_of_dict(self.markers_list,  fcs=True)

    @Slot()
    def startBatchFCS(self):
        """
        start the batch event
        """
        self.runBatchFCS = True
        self.batchFCS()

    @Slot()
    def batchFCS(self):
        """
        the actual loop for the batch event
        """
        logger.debug("startBatchFCS started")
        column = self.ui.tableWidget.columnCount()
        self.ui.label_batch.setText("Starting...")
        self.ui.progressBar_batch.setValue(0)
        self.ui.progressBar_batch.setMaximum(column)
        self.ui.progressBar_batch.setEnabled(True)
        self.ui.tableWidget.setEnabled(True)
        for i in range(column):
            self.ui.label_batch.setText("Running column %d..." % (i + 1))

            try:
                delay_software = float(
                    self.table_manager.get_value("Delay Software (s)", i)
                )
            except:
                delay_software = 0.0

            active = self.ui.tableWidget.item(0, i).checkState() == Qt.Checked
            if not active:
                continue

            QCoreApplication.processEvents()

            self.moveToSelectedColumnFCS(i)
            self.start()
            self.ui.progressBar_batch.setValue(i)

            QCoreApplication.processEvents()
            time.sleep(0.1)

            while not self.ui.pushButton_acquisitionStart.isEnabled():
                QCoreApplication.processEvents()
                if not self.runBatchFCS:
                    break

            t = QElapsedTimer()
            t.start()
            while t.elapsed() < delay_software * 1000:
                QCoreApplication.processEvents()
                self.ui.label_batch.setText(
                    "Column %d done! Waiting %.3f s... "
                    % (i + 1, delay_software - t.elapsed() / 1000.0)
                )
                if not self.runBatchFCS:
                    break
            # except Exception as e:
            #     print("ERROR", e)
            #     self.ui.label_batch.setText("Error.")

        self.ui.progressBar_batch.setValue(column)
        self.ui.label_batch.setText("Done!")

        self.ui.progressBar_batch.setEnabled(False)
        self.ui.tableWidget.setEnabled(True)
        self.ui.checkBox_fcs_preview.setChecked(False)
        logger.debug("startedBatch FCS ended")

    @Slot()
    def stopBatchFCS(self):
        """
        stop the batch event
        """
        self.runBatchFCS = False
        logger.debug("stopBatchFCS")

    @Slot()
    def timerConfigurationViewer_tick(self):
        """
        timer tick event for the configuration viewer
        it set the status bar with the CPU and RAM usage
        """
        self.timerConfigurationViewer_tick_mutex.lock()
        if self.ui.checkBox_updateStatus.isChecked():
            self.updateTables()

        P = "⏹"
        D = "⏹"
        F = "⏹"
        try:
            if self.mcs_manager.previewProcess_isAlive():
                P = "⏩"
        except:
            pass

        try:
            if self.mcs_manager.dataProcess_isAlive():
                D = "⏩"
        except:
            pass

        try:
            if self.mcs_manager.fpga_handle.fpga_handle_process_isAlive():
                F = "⏩"
        except:
            pass
        self.updatePi23GreetingStatus()
        self.statusBar_cpu.setText("CPU: %d%%" % psutil.cpu_percent())
        self.statusBar_mem.setText("RAM: %d%%" % psutil.virtual_memory().percent)

        self.statusBar_processes.setText(P + D + F)
        self.timerConfigurationViewer_tick_mutex.unlock()

    def updatePi23GreetingStatus(self):
        if not hasattr(self.ui, "textEdit_pi23_greeting_raw"):
            return
        try:
            raw_greeting = self.mcs_manager.shared_dict.get("pi23_greeting_raw", "")
            decoded_greeting = self.mcs_manager.shared_dict.get(
                "pi23_greeting_decoded",
                "",
            )
        except Exception:
            return
        if raw_greeting != self.ui.textEdit_pi23_greeting_raw.toPlainText():
            self.ui.textEdit_pi23_greeting_raw.setPlainText(raw_greeting)
        if decoded_greeting != self.ui.textEdit_pi23_greeting_decoded.toPlainText():
            self.ui.textEdit_pi23_greeting_decoded.setPlainText(decoded_greeting)

    @Slot()
    def cmd_call_external(self):
        import subprocess

        line = self.ui.lineEdit_externalProgram.text()
        line = line.replace("%python", sys.executable)
        line = line.replace("%lastfilename", self.last_saved_filename)
        cmds = line.split(" ")
        logger.debug("%s %s", "cmd_call_external", cmds)
        logger.debug(sys.platform)
        if "win" in sys.platform:
            subprocess.Popen(
                cmds,
                creationflags=subprocess.DETACHED_PROCESS
                              | subprocess.CREATE_NEW_PROCESS_GROUP,
            )
        else:
            subprocess.Popen(cmds, start_new_session=True)

    @Slot()
    def markersViewTable(self):
        """
        update the markers table
        """
        self.ui.tableWidget_markers.setRowCount(len(self.markers_list))
        self.ui.tableWidget_markers.setColumnCount(4)

        for k, v in enumerate(self.markers_list):
            # print(k, type(k), v, type(v))
            for n, i in enumerate(
                    ["offset_x_um", "offset_y_um", "offset_z_um"]
            ):  # assumed to be length 3
                # print(n, type(n), i, type(i))
                self.ui.tableWidget_markers.setItem(k, n, QTableWidgetItem(str(v[i])))

    @Slot()
    def timerPreviewImg_tick(self):
        """
        timer tick event for the preview image
        continuosly update the preview image
        """
        # This method runs frequently, so extra copies or full redraws here
        # directly affect UI responsiveness during acquisition.
        if not self.timerPreviewImg_tick_mutex.tryLock():
            logger.debug("self.timerPreviewImg_tick_lock called but busy")
            return

        time_res = self.ui.spinBox_timeresolution.value()
        time_bin = self.ui.spinBox_time_bin_per_px.value()
        frames = self.ui.spinBox_nframe.value()
        repetition = self.ui.spinBox_nrepetition.value()

        fifo_activated = []
        if self.ui.checkBox_fifo_analog.isChecked():
            fifo_name = "stream_out_aux"
            fifo_activated.append(fifo_name)
        if self.ui.checkBox_fifo_digital.isChecked():
            fifo_name = "stream_out_main"
            fifo_activated.append(fifo_name)
        if not (self.ui.checkBox_fifo_analog.isChecked() or self.ui.checkBox_fifo_digital.isChecked()):
            logger.debug("Bug: No FIFO Selected")

        #debug("fifo_activated", fifo_activated)
        #fifo_name is the "priority" fifo when two are activated
        
        fifo_elements = { fifo : self.mcs_manager.getCurrentAcquistionElement(fifo) for fifo in fifo_activated}
        expected_fifo_elements = { fifo : self.mcs_manager.getExpectedFifoElements(fifo) for fifo in fifo_activated}
        expected_fifo_elements_per_frame = { fifo : self.mcs_manager.getExpectedFifoElementsPerFrame(fifo) for fifo in fifo_activated}
        current_preview_element = { fifo : self.mcs_manager.getCurrentPreviewElement(fifo) for fifo in fifo_activated}
        number_of_threads_h5 = self.mcs_manager.get_number_of_threads_h5()

        data_point_str = ""

        for fifo in fifo_activated:
            data_point_str = data_point_str + fifo + " %d %% (%d / %d)\n" % (
                100 * fifo_elements[fifo] / expected_fifo_elements[fifo],
                fifo_elements[fifo],
                expected_fifo_elements[fifo],
            )

        self.ui.label_tot_num_dat_point_val.setText(data_point_str)

        self.ui.progressBar_repetition.setMaximum(100.0)

        if self.raw_stream_mode:
            label_frame = ""
            label_repetition = ""
            for fifo in fifo_activated:
                label_frame += "%d " % self.mcs_manager.get_current_z(fifo)
                label_repetition += "%d " % self.mcs_manager.get_current_rep(fifo)

            self.ui.label_current_time_val.setText("RAW")
            self.ui.label_current_frame_val.setText(label_frame)
            self.ui.label_current_repetition_val.setText(label_repetition)

            if expected_fifo_elements[fifo_name] != 0:
                self.ui.progressBar_repetition.setValue(
                    100.0 * fifo_elements[fifo_name] / expected_fifo_elements[fifo_name]
                )
            else:
                self.ui.progressBar_repetition.setValue(0)

            if fifo_elements[fifo_name] != 0:
                self.ui.progressBar_frame.setMaximum(100.0)
            else:
                self.ui.progressBar_frame.setMaximum(0)
            self.ui.progressBar_frame.setValue(
                100.0
                * (fifo_elements[fifo_name] % expected_fifo_elements_per_frame[fifo_name])
                / expected_fifo_elements_per_frame[fifo_name]
            )

            if self.mcs_manager.acquisition_is_almost_done():
                self.ui.pushButton_stop.setEnabled(False)
                self.ui.pushButton_acquisitionStart.setEnabled(False)

            if self.mcs_manager.acquisition_is_done():
                self.my_tick_counter += self.timerPreviewImg.interval()
                self.mcs_manager.acquisition_done_reset()
                self.finalizeAcquisition()

            fifo1, fifo2 = self.mcs_manager.get_stream_status()
            self.ui.progressBar_fifo_digital.setValue(fifo1)
            self.ui.progressBar_fifo_analog.setValue(fifo2)
            self.ui.progressBar_saving.setValue(0)
            self.ui.label_preview_delay.setText("RAW")

            try:
                self.ui.label_fifo_last_pkt_size.setText(
                    "%d" % self.mcs_manager.shared_dict["last_packet_size"]
                )
            except:
                logger.debug("self.ui.last_packet_size FAIL")

            try:
                self.ui.label_last_preprocessed_size.setText(
                    "%d" % self.mcs_manager.last_preprocessed_len["stream_out_aux"].value
                )
            except:
                pass

            try:
                self.ui.label_last_preprocessed_size.setText(
                    "%d" % self.mcs_manager.last_preprocessed_len["stream_out_main"].value
                )
            except:
                pass

            self.timerPreviewImg_tick_mutex.unlock()
            return

        current_time = {}
        current_frame = {}
        current_rep = {}

        label_time = ""
        label_frame = ""
        label_repetition = ""

        for fifo in fifo_activated:
            current_time[fifo] = current_preview_element[fifo] * (time_res * time_bin * 1e-6) / self.spad_channels
            current_frame[fifo] = self.mcs_manager.get_current_z(fifo)
            current_rep[fifo] = self.mcs_manager.get_current_rep(fifo)
            label_time += "%0.2f " % current_time[fifo]
            label_frame += "%d " % current_frame[fifo]
            label_repetition += "%d " % current_rep[fifo]


        self.ui.label_current_time_val.setText(label_time)
        self.ui.label_current_frame_val.setText(label_frame)
        self.ui.label_current_repetition_val.setText(label_repetition)


        if expected_fifo_elements[fifo_name] != 0:
            self.ui.progressBar_repetition.setValue(
                100.0 * fifo_elements[fifo_name] / expected_fifo_elements[fifo_name]
            )
        else:
            self.ui.progressBar_repetition.setValue(0)

        if fifo_elements[fifo_name] != 0:
            self.ui.progressBar_frame.setMaximum(100.0)
        else:
            self.ui.progressBar_frame.setMaximum(0)
        self.ui.progressBar_frame.setValue(
            100.0
            * (fifo_elements[fifo_name] % expected_fifo_elements_per_frame[fifo_name])
            / expected_fifo_elements_per_frame[fifo_name]
        )

        corralation = self.mcs_manager.getAutocorrelation()
        self.fcs_widget.plot(
            corralation[0, :] * time_res * 1e-6,
            corralation[1, :],
            clear=True,
            symbol="o",
        )

        clk_multiplier = self.ui.spinBox_clk_base_multiplier.value()

        trace, trace_pos = self.mcs_manager.getTrace()
        self.trace_widget.setLabel("bottom", "Time", "s")
        trace_x = trace[0, :trace_pos]
        trace_y = trace[1, :trace_pos]

        if clk_multiplier > 1 and not self.dfd_enable:
            size = trace_x.shape[0]
            idx = np.arange(size)
            trace_x_n = trace_x[:size//clk_multiplier]
            trace_y_n = np.zeros(size//clk_multiplier)

            #trace_x_n =
            # np.add.at(
            #     trace_x_n,
            #     idx % clk_multiplier,
            #     trace_x,
            # )

            np.add.at(
                trace_y_n,
                idx % (size//clk_multiplier),
                trace_y,
            )

            trace_x = trace_x_n
            trace_y = trace_y_n

        if ( "Analog" in self.ui.comboBox_plot_channel.currentText() and not self.dfd_enable):
            self.trace_widget.setLabel("left", "Mean", "V")
            trace_bin = int(
                self.ui.doubleSpinBox_binsize.value()
                * 1e3
                / (self.ui.spinBox_timeresolution.value())
            )
            coeff = 1.0 / (2 ** 27) / trace_bin
        else:
            self.trace_widget.setLabel("left", "Freq.", "Hz")
            coeff = 1

        if self.ui.checkBox_trace_autorange.isChecked():
            self.trace_widget.plot(
                trace_x, trace_y * coeff, clear=True
            )
        else:
            self.trace_widget.plot(trace_x, trace_y, clear=True)

        self.trace_dfd_widget.setVisible(self.dfd_enable)
        if self.dfd_enable:
            dfd_trace = self.mcs_manager.getDfdTrace()
            trace_dfd_x = dfd_trace[0, :]
            trace_live = dfd_trace[1, :]
            trace_sum = dfd_trace[2, :]
            peak_idx = int(np.argmax(trace_sum))
            self.mcs_manager.update_shared_dict({"dfd_peak_idx": peak_idx})
            trace_dfd_x_bins = np.asarray(trace_dfd_x, dtype=float)
            tcycle_s = 1.0 / (
                max(float(self.dfd_cycle_mhz), 1e-12) * 1e6 * max(clk_multiplier, 1)
            )
            trace_dfd_x_seconds = trace_dfd_x_bins / max(int(self.DFD_nbins), 1) * tcycle_s
            axis_name = "DFD bin"
            if self.ui.checkBox_trace_dfd_time_axis.isChecked():
                trace_dfd_x = trace_dfd_x_seconds
                axis_name = "Time"
            else:
                trace_dfd_x = trace_dfd_x_bins
            bin_width_ns = tcycle_s * 1e9 / max(int(self.DFD_nbins), 1)
            live_max = np.max(trace_live)
            sum_max = np.max(trace_sum)

            if live_max > 0 and sum_max > 0:
                trace_live = (trace_live / live_max) * sum_max
            elif live_max > 0 and sum_max <= 0:
                trace_live = trace_live / live_max

            if self.ui.checkBox_trace_dfd_align_peak.isChecked():
                trace_live = np.roll(trace_live, -peak_idx)
                trace_sum = np.roll(trace_sum, -peak_idx)
                trace_dfd_x_plot = (
                    np.roll(
                        np.mod(trace_dfd_x_seconds - trace_dfd_x_seconds[peak_idx], tcycle_s),
                        -peak_idx,
                    )
                    if self.ui.checkBox_trace_dfd_time_axis.isChecked()
                    else np.roll(
                        np.mod(
                            trace_dfd_x_bins - trace_dfd_x_bins[peak_idx],
                            float(max(int(self.DFD_nbins), 1)),
                        ),
                        -peak_idx,
                    )
                )
            else:
                trace_dfd_x_plot = trace_dfd_x

            self.trace_dfd_widget.plot(
                trace_dfd_x_plot,
                trace_live,
                clear=True,
                pen=pg.mkPen(color=(255, 255, 255), width=1),
            )
            self.trace_dfd_widget.plot(
                trace_dfd_x_plot,
                trace_sum,
                pen=pg.mkPen(color=(180, 180, 180), width=2),
            )
            tau_ns, fit_curve, peak_idx, trace_sum_peak0, trace_dfd_x_peak0_seconds = self.estimateDfdDecayLifetimeNs(
                trace_sum,
                trace_dfd_x_seconds,
                bin_width_ns,
                max(int(self.DFD_nbins), 1),
                tcycle_s,
                start_level=self.ui.doubleSpinBox_trace_dfd_start_percent.value() / 100.0,
                end_level=self.ui.doubleSpinBox_trace_dfd_end_percent.value() / 100.0,
            )
            self.latest_dfd_tau_fit_ns = tau_ns
            if tau_ns is not None:
                self.trace_dfd_widget.setLabel("top", f"tau_fit={tau_ns:.3f} ns - {axis_name}", "s" if axis_name == "Time" else None)
            else:
                self.trace_dfd_widget.setLabel("top", axis_name, "s" if axis_name == "Time" else None)

            if fit_curve is not None:
                if self.ui.checkBox_trace_dfd_time_axis.isChecked():
                    fit_x = fit_curve["x_fit_seconds"]
                else:
                    fit_x = fit_curve["x_fit_bins"]
                fit_y = fit_curve["y_fit"]
                order = np.argsort(fit_x)
                fit_x = fit_x[order]
                fit_y = fit_y[order]
                self.trace_dfd_widget.plot(
                    fit_x,
                    fit_y,
                    pen=None,
                    symbol="o",
                    symbolSize=3,
                    symbolBrush=(255, 200, 0),
                    symbolPen=pg.mkPen(color=(255, 200, 0), width=1),
                )
        else:
            self.latest_dfd_tau_fit_ns = None
            self.mcs_manager.update_shared_dict({"dfd_peak_idx": -1})
            self.trace_dfd_widget.clear()
            self.trace_dfd_widget.setLabel("top", "DFD bin")

        # numpy random.rand also much faster than list comprehension
        # img = np.random.rand(512, 512)
        # if self.previewEnabled:
        # print(self.ui.comboBox_view_projection.currentText())
        self.plotPreviewImage()

        # result = self.calculateAutoCorrelation(self.getPreviewFlatData())
        # self.fcs_widget.plot(result, clear=True)
        time_res = self.ui.spinBox_timeresolution.value()
        time_bin = self.ui.spinBox_time_bin_per_px.value()
        data_finger_print = None

        # if num == 0:    # cumulative
        # elif num == 1:  # 10000 bins
        # elif num == 2:  # fingerprint
        if self.fingerprint_visualization == 0:
            if ( fifo_elements[fifo_name] % expected_fifo_elements_per_frame[fifo_name] ) != 0:
                data_finger_print = (
                        self.mcs_manager.getFingerprintCumulative()
                        / (
                                (
                                        (
                                                fifo_elements[fifo_name]
                                                % expected_fifo_elements_per_frame[fifo_name]
                                        )
                                        / 2
                                )
                                * time_res
                                * time_bin
                                * 1e-6
                        )
                )
        elif self.fingerprint_visualization == 1:
            data_finger_print = (
                    self.mcs_manager.getFingerprintCumulativeLast10000()
                    / (10000 * time_res * 1e-6)
            )
        elif self.fingerprint_visualization == 2:
            data_finger_print = (
                    self.mcs_manager.getFingerprintCumulativeLastFrame()
                    / (expected_fifo_elements_per_frame[fifo_name] / 2 * time_res * 1e-6)
            )

        saturation_data = self.mcs_manager.getFingerprintSaturation()

        if data_finger_print is not None:
            data_finger_print = data_finger_print * self.fingerprint_mask

            if self.ui.checkBox_correlationMatrix.isChecked():
                self.microimage_analysis(data_finger_print)

            self.draw_fingerprint(data_finger_print, saturation_data)

        if self.mcs_manager.acquisition_is_almost_done():
            logger.debug("%s %s", "self.mcs_manager.acquisition_is_almost_done()", number_of_threads_h5)
            self.ui.pushButton_stop.setEnabled(False)
            self.ui.pushButton_acquisitionStart.setEnabled(False)

        if self.mcs_manager.acquisition_is_done():
            logger.debug("%s %s", "self.mcs_manager.acquisition_is_done()", self.mcs_manager.acquisition_is_done())
            self.my_tick_counter += self.timerPreviewImg.interval()


            for fifo in fifo_activated:
                if (self.my_tick_counter > 5000) or (
                        current_preview_element[fifo] >= expected_fifo_elements[fifo]
                ):
                    logger.debug("get_fifo_elements >= get_expected_fifo_elements and 1s passed")
                    self.mcs_manager.acquisition_done_reset()
                    self.finalizeAcquisition()

        fifo1, fifo2 = self.mcs_manager.get_stream_status()

        if fifo1 > 0.9 * self.ui.progressBar_fifo_digital.maximum():
            self.ui.progressBar_fifo_digital.setMaximum(fifo1 * 1.2)

        if fifo2 > 0.9 * self.ui.progressBar_fifo_analog.maximum():
            self.ui.progressBar_fifo_analog.setMaximum(fifo2 * 1.2)

        self.ui.progressBar_fifo_digital.setValue(fifo1)
        self.ui.progressBar_fifo_analog.setValue(fifo2)

        self.ui.label_preview_delay.setText(
            "%0.3f"
            % (
                    fifo1
                    * self.mcs_manager.shared_dict["last_packet_size"]
                    * self.ui.spinBox_timeresolution.value()
                    / 2e6
            )
        )

        if number_of_threads_h5 > 0.9 * self.ui.progressBar_saving.maximum():
            self.ui.progressBar_saving.setMaximum(number_of_threads_h5 * 1.2)
        self.ui.progressBar_saving.setValue(number_of_threads_h5)

        # print("Digital: %d\nAnalog: %d" % (fifo1, fifo2))
        # self.ui.label_FIFOqueue.setText("Digital: %d\nAnalog: %d" % (, ))

        if fifo1 > 300:
            self.ui.progressBar_fifo_digital.setStyleSheet(
                "border: 1px solid red; height: 8px;"
            )
            self.ui.label_preview_delay.setStyleSheet(
                "border: 1px solid red; height: 8px; background: rgb(255,128,128);"
            )
        else:
            self.ui.progressBar_fifo_digital.setStyleSheet("height: 8px;")
            self.ui.label_preview_delay.setStyleSheet("height: 8px; background: None;")

        if fifo2 > 300:
            self.ui.progressBar_fifo_analog.setStyleSheet(
                "border: 1px solid red; height: 8px;"
            )
        else:
            self.ui.progressBar_fifo_analog.setStyleSheet("height: 8px;")

        try:
            self.ui.label_fifo_last_pkt_size.setText(
                "%d" % self.mcs_manager.shared_dict["last_packet_size"]
            )
        except:
            logger.debug("self.ui.last_packet_size FAIL")

        try:
            # print(self.mcs_manager.last_preprocessed_len)
            # print(self.mcs_manager.last_preprocessed_len["stream_out_main"].value)
            self.ui.label_last_preprocessed_size.setText(
                "%d"
                % self.mcs_manager.last_preprocessed_len["stream_out_aux"].value
            )
        except:
            logger.debug("self.ui.last_preprocessed_len stream_out_aux FAIL")

        try:
            # print(self.mcs_manager.last_preprocessed_len)
            # print(self.mcs_manager.last_preprocessed_len["stream_out_main"].value)
            self.ui.label_last_preprocessed_size.setText(
                "%d" % self.mcs_manager.last_preprocessed_len["stream_out_main"].value
            )

        except:
            logger.debug("self.ui.last_preprocessed_len stream_out_main FAIL")

        self.timerPreviewImg_tick_mutex.unlock()

    def draw_fingerprint(self, data_finger_print, saturation_data):
        """

        """
        # TEST data_finger_printdata_finger_printdata_finger_printdata_finger_printdata_finger_printdata_finger_printdata_finger_printdata_finger_printdata_finger_print

        # data_finger_print = log(copy(data_finger_print)+1)
        # #print(data_finger_print.shape)

        # data_finger_print = data_finger_print * self.fingerprint_mask

        if np.sum(data_finger_print) > 0:
            if self.autoscale_fingerprint:
                self.fingerprint_widget.setImage(
                    data_finger_print.T,
                    autoLevels=False,
                    autoRange=False,
                    autoHistogramRange=False,
                )

                self.fingerprint_widget.setLevels(np.min(data_finger_print[self.fingerprint_mask == 1]),
                                                  np.max(data_finger_print[self.fingerprint_mask == 1]))
            else:
                self.fingerprint_widget.setImage(
                    data_finger_print.T,
                    autoLevels=False,
                    autoRange=False,
                    autoHistogramRange=False,
                )
        else:
            self.fingerprint_widget.setImage(
                data_finger_print.T,
                autoLevels=False,
                autoRange=False,
                autoHistogramRange=False,
            )

        self.fingerprint_saturation_mask.clear()

        coeff = 25. / self.spad_channels

        for xxx in range(self.spad_channels_x):
            for yyy in range(self.spad_channels_y):
                if saturation_data[yyy, xxx] > 0:
                    v = self.mcs_manager.getFingerprintCumulative() * 1.
                    ratio = saturation_data[yyy, xxx] / v[yyy, xxx]
                    # print(ratio)
                    size = 1 + min(ratio * 8 * 100, 8)

                    self.fingerprint_saturation_mask.addPoints(
                        x=[
                            xxx + 0.5,
                        ],
                        y=[
                            yyy + 0.5,
                        ],
                        pen="b",
                        brush="b",
                        size=size * coeff,
                        symbol="s",
                    )

    def openConsoleWidget(self):
        """
        open the console widget
        """
        logger.debug("Start QTConsole")
        namespace = {
            "np": np,
            "h5py": h5py,
            "pg": pg,
            "main_window": self,
            "mcs_manager": self.mcs_manager,
            "filename": None
            # 'list_plugins': plugin_list,
            # 'load_plugin': lambda x: plugin_loader(x, self)
        }

        banner = """
Welcome to BrightEyes-MCS console.
            
It is an instance of Jupyter Qt Console "InProcess".
In the current namespace to the following objects:            

'np' for numpy
'h5py' for h5py
'pg' for pyqtgraph
'plt' includes matplotlib.pyplot (i.e. plt.plot(x,y), plt.imshow(img) etc etc... )\n

'main_window' for the current QT window instantiation
'mcs_manager' for the current mcs_manager instantiation\n\n
'filename' contains the last h5 file saved or the last file selected

Have fun!


"""

        # "- 'list_plugins()' to list the plugins\n" + \
        # "- 'load_plugin(plugin_name)' to load a plugin \n" + \

        self.console_widget = ConsoleWidget(customBanner=banner)
        self.console_widget.set_default_style(colors="linux")
        # self.ui.tabWidget.addTab(self.console_widget, "Terminal")
        self.ui.gridLayout_Terminal.addWidget(self.console_widget)
        self.console_widget.show()
        self.console_widget.kernel_manager.kernel.shell.user_ns.update(namespace)

    def _publish_filename_to_console(self, filename):
        """Expose the latest completed file in the embedded Python console."""
        console = getattr(self, "console_widget", None)
        if console is None or not filename:
            return
        try:
            # Keep this in the core lifecycle instead of relying on the optional
            # Script Launcher plug-in.  The plug-in may be removed or disabled,
            # but ``filename`` is part of the console's documented namespace.
            console.push_vars({"filename": os.path.abspath(filename)})
        except Exception:
            logger.exception("Unable to publish filename to Python console")

    def microimage_analysis(self, data_finger_print):
        """
        microimage analysis in live, useful for alligment
        """
        data_finger_print = data_finger_print.astype(float)
        n = np.sum(data_finger_print)
        if n > 0:
            X, Y = np.meshgrid(np.arange(5), np.arange(5))
            x0 = np.sum(data_finger_print / n * X)
            y0 = np.sum(data_finger_print / n * Y)

            self.fingerprint_markers_centroid.clear()
            self.fingerprint_markers_centroid.addPoints(
                x=[
                    x0 + 0.5,
                ],
                y=[
                    y0 + 0.5,
                ],
                pen="w",
                brush="b",
                size=10,
                symbol="x",
            )

            sigma_XX = np.sum(data_finger_print / n * ((X - x0) * (X - x0)))
            sigma_YY = np.sum(data_finger_print / n * ((Y - y0) * (Y - y0)))
            sigma_XY = np.sum(data_finger_print / n * ((X - x0) * (Y - y0)))

            try:
                eigenvalues, eigenvectors = np.linalg.eig(
                    np.matrix([[sigma_XX, sigma_XY], [sigma_XY, sigma_YY]])
                )
            except:
                pass

            theta = np.arctan2(eigenvectors[0, 1], eigenvectors[0, 0])
            self.ui.label_dummy.setText(
                "%0.3f\t%0.3f\n\n%0.3f\t%0.3f\n%0.3f\t%0.3f\n\n%0.3f\t%0.3f\n%0.3f\t%0.3f\n\n%0.3f\n%0.3f\n\n%0.3f"
                % (
                    x0 - 2,
                    y0 - 2,
                    sigma_XX,
                    sigma_XY,
                    sigma_XY,
                    sigma_YY,
                    eigenvectors[0, 0],
                    eigenvectors[0, 1],
                    eigenvectors[1, 0],
                    eigenvectors[1, 1],
                    eigenvalues[0],
                    eigenvalues[1],
                    theta,
                )
            )

    @Slot()
    def temporalSettingsChanged(self):
        """

        """
        time_res = self.ui.spinBox_timeresolution.value()
        time_bin = self.ui.spinBox_time_bin_per_px.value()

        if self.ui.checkBox_circular.isChecked():
            circ_repetition = self.ui.spinBox_circular_repetition.value()
            circ_points = self.ui.spinBox_circular_points.value()
        else:
            circ_repetition = 1
            circ_points = 1

        clock_duration = time_bin * time_res * 20
        Cx = time_res * self.clock_base
        logger.debug("temporalSettingsChanged")

        waitForLaserInCycle = self.ui.spinBox_waitForLaser.value() * 40e6
        waitAfterFrame = self.ui.spinBox_waitAfterFrame.value() * 40e6
        waitOnlyFirstTime = self.ui.checkBox_waitOnlyFirstTime.isChecked()

        logger.debug("temporalSettingsChanged")

        self.setRegistersDict(
            {
                "time_bin_dwell_cycles": int(Cx),
                "max_time_bins_per_pixel": int(time_bin),
                "tag_clock_duration_cycles": int(clock_duration),
                "wait_laser_startup_cycles": int(waitForLaserInCycle),
                "wait_post_frame_cycles": int(waitAfterFrame),
                "wait_laser_first_time_only_enable": waitOnlyFirstTime,
                "max_circular_point": circ_points,
                "max_circular_repetition": circ_repetition
            }
        )

        numbers_xx = self.ui.spinBox_nx.value()
        numbers_yy = self.ui.spinBox_ny.value()
        numbers_ff = self.ui.spinBox_nframe.value()
        rep = self.ui.spinBox_nrepetition.value()

        self.ui.label_dwell_time_val.setText("%0.3f" % (time_res * time_bin))
        self.ui.label_frame_time_val.setText(
            "%0.3f" % (time_res * time_bin * circ_points * circ_repetition * numbers_xx * numbers_yy * 1e-6)
        )
        self.ui.label_expected_dur_val.setText(
            "%0.3f"
            % (time_res * time_bin * circ_points * circ_repetition * numbers_xx * numbers_yy * numbers_ff * rep * 1e-6)
        )

        self.checkAlerts()

    @Slot()
    def checkBoxLockRatioChanged(self):
        """
        lock the ratio of the ROI
        """
        self.ui.spinBox_range_y.setEnabled(not self.ui.checkBoxLockRatio.isChecked())
        self.rect_roi.aspectLocked = self.ui.checkBoxLockRatio.isChecked()
        self.rect_roi_panorama.aspectLocked = self.ui.checkBoxLockRatio.isChecked()

    @Slot()
    def loadPreset(self):
        """
        load the preset configuration
        """
        logger.debug("loadPreset")
        combo_str = self.ui.comboBox_preset.currentText()
        self.setGUI_data(self.preset_dict[combo_str])
        logger.debug("preset %d loaded" % combo_str)

    @Slot()
    def savePreset(self):
        """
        save the preset configuration
        """
        logger.debug("savePreset")
        combo_str = self.ui.comboBox_preset.currentText()
        self.preset_dict[combo_str] = self.getGUI_data()
        logger.debug("preset %d saved" % combo_str)

    # @Slot()
    # def removeMarkerCmd(self):
    #     if len(self.markers_list) == 0:
    #         return
    #     self.markers_list.pop(max(self.markers_list), None)
    #     self.drawMarkers()

    @Slot()
    def calibrationFactorChanged(self):
        """
        calibration factor changed event
        """
        self.positionSettingsChanged_apply()

    @Slot()
    def offset_V_Changed(self):
        """
        offset in Volts changed event
        """
        self.positionSettingsChanged_apply()

    @Slot()
    def offset_um_Changed(self, force=False):
        """
        offset in um changed event
        """

        self.offset_um_update(force)
        self.rangeValueChanged()

    @Slot()
    def updatePixelValueChanged(self, number=None):
        """
        update the number of pixel, line, frame changed event
        """
        logger.debug("updatePixelValueChanged")

        if self.ui.spinBox_nx.value() == 1:
            self.ui.comboBox_view_projection.setCurrentIndex(
                self.ui.comboBox_view_projection.findText("zy")
            )
        if self.ui.spinBox_ny.value() == 1:
            self.ui.comboBox_view_projection.setCurrentIndex(
                self.ui.comboBox_view_projection.findText("xz")
            )
        if self.ui.spinBox_nframe.value() == 1:
            self.ui.comboBox_view_projection.setCurrentIndex(
                self.ui.comboBox_view_projection.findText("xy")
            )

        self.ui.pushButton_18.setStyleSheet("")

        proj = self.ui.comboBox_view_projection.currentText()

        self.currentImage_pos = np.asarray(
            (
                self.ui.spinBox_off_x_um.value(),  # - self.ui.spinBox_range_x.value()/2,
                self.ui.spinBox_off_y_um.value(),  # - self.ui.spinBox_range_y.value()/2,
                self.ui.spinBox_off_z_um.value(),
            )
        )  # - self.ui.spinBox_range_z.value()/2,))

        self.currentImage_size = np.asarray(
            (
                self.ui.spinBox_range_x.value(),
                self.ui.spinBox_range_y.value(),
                self.ui.spinBox_range_z.value(),
            )
        )

        self.currentImage_pixels = np.asarray(
            (
                self.ui.spinBox_nx.value(),
                self.ui.spinBox_ny.value(),
                self.ui.spinBox_nframe.value(),
            )
        )

        xxx = self.currentImage_pixels[0]
        yyy = self.currentImage_pixels[1]
        zzz = self.currentImage_pixels[2]

        if proj == "xy":
            a = xxx
            b = yyy
        elif proj == "zy":
            a = zzz
            b = yyy
        elif proj == "xz":
            a = xxx
            b = zzz
        elif proj == "yx":
            a = yyy
            b = xxx
        elif proj == "yz":
            a = yyy
            b = zzz
        elif proj == "zx":
            a = zzz
            b = xxx

        self.current_plot_size_x_um = self.ui.spinBox_range_x.value()
        self.current_plot_size_y_um = self.ui.spinBox_range_y.value()
        self.current_plot_size_z_um = self.ui.spinBox_range_z.value()

        self.current_number_px_x = self.ui.spinBox_nx.value()
        self.current_number_px_y = self.ui.spinBox_ny.value()
        self.current_number_px_z = self.ui.spinBox_nframe.value()

        xx = self.ui.spinBox_range_x.value()
        yy = self.ui.spinBox_range_y.value()
        zz = self.ui.spinBox_range_z.value()

        calib_xx = self.ui.spinBox_calib_x.value()
        calib_yy = self.ui.spinBox_calib_y.value()
        calib_zz = self.ui.spinBox_calib_z.value()

        offset_xx_um = self.ui.spinBox_off_x_um.value()
        offset_yy_um = self.ui.spinBox_off_y_um.value()
        offset_zz_um = self.ui.spinBox_off_z_um.value()

        self.ui.spinBox_off_x_V.setValue(offset_xx_um / calib_xx)
        self.ui.spinBox_off_y_V.setValue(offset_yy_um / calib_yy)
        self.ui.spinBox_off_z_V.setValue(offset_zz_um / calib_zz)

        offset_xx = self.ui.spinBox_off_x_V.value()
        offset_yy = self.ui.spinBox_off_y_V.value()
        offset_zz = self.ui.spinBox_off_z_V.value()

        numbers_xx = self.ui.spinBox_nx.value()
        numbers_yy = self.ui.spinBox_ny.value()
        numbers_ff = self.ui.spinBox_nframe.value()
        numbers_repetition = self.ui.spinBox_nrepetition.value()

        calibration_v_step = (
                np.asarray([xx, yy, zz])
                / np.asarray([calib_xx, calib_yy, calib_zz])
                / np.asarray([numbers_xx, numbers_yy, numbers_ff])
        )

        offExtra_x_V = self.ui.spinBox_offExtra_x_V.value()
        offExtra_y_V = self.ui.spinBox_offExtra_y_V.value()
        offExtra_z_V = self.ui.spinBox_offExtra_z_V.value()

        laserEnable0 = self.ui.checkBox_laser0.isChecked()
        laserEnable1 = self.ui.checkBox_laser1.isChecked()
        laserEnable2 = self.ui.checkBox_laser2.isChecked()
        laserEnable3 = self.ui.checkBox_laser3.isChecked()

        start_offset = np.asarray(
            [
                offset_xx - (0.5 * xx / calib_xx) + offExtra_x_V,
                offset_yy - (0.5 * yy / calib_yy) + offExtra_y_V,
                offset_zz - (0.5 * zz / calib_zz) + offExtra_z_V,
            ]
        )

        #

        #
        #
        #

        dummy_img = np.zeros((a, b))
        self.currentImage = dummy_img
        self.plotPreviewImage(dummy_img)
        self.AutoRange_im_widget()

        self.current_plot_size_x_um = self.ui.spinBox_range_x.value()
        self.current_plot_size_y_um = self.ui.spinBox_range_y.value()
        self.current_plot_size_z_um = self.ui.spinBox_range_z.value()

        self.current_number_px_x = self.ui.spinBox_nx.value()
        self.current_number_px_y = self.ui.spinBox_ny.value()
        self.current_number_px_z = self.ui.spinBox_nframe.value()

        # self.rect_roi_modified_lock = True

        self.rect_roi.setSize(
            self.ui.spinBox_range_x.value(), self.ui.spinBox_range_y.value()
        )
        # self.rect_roi.setPos(-self.ui.spinBox_range_x.value() / 2 + self.ui.spinBox_off_x_um.value(),
        #                      -self.ui.spinBox_range_y.value() / 2 + self.ui.spinBox_off_y_um.value())
        self.rect_roi.setPos(
            self.ui.spinBox_off_x_um.value(), self.ui.spinBox_off_y_um.value()
        )
        # self.rect_roi.setSize(self.ui.spinBox_nx.value(), self.ui.spinBox_ny.value())
        # self.rect_roi.setPos(0., 0.) # for some bug this must be after setSize
        self.rect_roi.update()

        logger.debug(self.rect_roi.state)
        # self.rect_roi_modified_lock = False

        self.rect_roi.hide()

        self.positionSettingsChanged_apply()
        self.temporalSettingsChanged()
        self.plotSettingsChanged()

        #
        self.axesRangeChanged()
        # self.positionSettingsChanged()

        # pass
        logger.debug("self.im_widget.autoRange()")
        self.im_widget.autoRange()

    def updateLabelPixelSize(self):
        if self.ui.spinBox_nx.value() != 1:
            self.ui.label_pixelsize_x.setText(
                "%.3f nm" % (1000 * self.ui.spinBox_range_x.value() / (self.ui.spinBox_nx.value() - 1.)))
        else:
            self.ui.label_pixelsize_x.setText(
                "∞")

        if self.ui.spinBox_ny.value() != 1:
            self.ui.label_pixelsize_y.setText(
                "%.3f nm" % (1000 * self.ui.spinBox_range_y.value() / (self.ui.spinBox_ny.value() - 1.)))
        else:
            self.ui.label_pixelsize_y.setText(
                "∞")

        if self.ui.spinBox_nframe.value() != 1:
            self.ui.label_pixelsize_z.setText(
                "%.3f nm" % (1000 * self.ui.spinBox_range_z.value() / (self.ui.spinBox_nframe.value() - 1.)))
        else:
            self.ui.label_pixelsize_z.setText(
                "∞")

    @Slot()
    def rangeValueChanged(self, number=None):
        """
        the range in um is changed event
        """

        lock = self.lock_range_changing
        self.lock_range_changing = False
        self.positionSettingsChanged_apply(force=True)
        self.offset_um_update()

        self.updateLabelPixelSize()

        self.lock_range_changing = lock

    @Slot()
    def offset_um_update(self, force=False):
        """
        called when the offset in um is changed
        """
        oldlock_range_changing = self.lock_range_changing
        oldlock_parameters_changed_call = self.lock_parameters_changed_call
        if not self.lock_parameters_changed_call or force:
            self.lock_parameters_changed_call = True
            logger.debug("offset_um_update self.lock_parameters_changed_call SET True")
            self.lock_range_changing = True
            calib_xx = self.ui.spinBox_calib_x.value()
            calib_yy = self.ui.spinBox_calib_y.value()
            calib_zz = self.ui.spinBox_calib_z.value()

            offset_xx_um = self.ui.spinBox_off_x_um.value()
            offset_yy_um = self.ui.spinBox_off_y_um.value()
            offset_zz_um = self.ui.spinBox_off_z_um.value()

            self.ui.spinBox_off_x_V.setValue(offset_xx_um / calib_xx)
            self.ui.spinBox_off_y_V.setValue(offset_yy_um / calib_yy)
            self.ui.spinBox_off_z_V.setValue(offset_zz_um / calib_zz)

            self.offset_V_Changed()
            logger.debug("%s %s", self.started_normal, self.started_preview)
            self.currentImage_pos = np.asarray(
                (
                    self.ui.spinBox_off_x_um.value(),  # - self.ui.spinBox_range_x.value()/2,
                    self.ui.spinBox_off_y_um.value(),  # - self.ui.spinBox_range_y.value()/2,
                    self.ui.spinBox_off_z_um.value(),
                )
            )  # - self.ui.spinBox_range_z.value()/2,))

            self.currentImage_size = np.asarray(
                (
                    self.ui.spinBox_range_x.value(),
                    self.ui.spinBox_range_y.value(),
                    self.ui.spinBox_range_z.value(),
                )
            )

            self.currentImage_pixels = np.asarray(
                (
                    self.ui.spinBox_nx.value(),
                    self.ui.spinBox_ny.value(),
                    self.ui.spinBox_nframe.value(),
                )
            )

            # self.im_widget.setImage(self.im_widget.image,
            #                         autoLevels=self.autoscale_image,
            #                         pos=(self.ui.spinBox_off_x_um.value()-self.ui.spinBox_range_x.value()/2.,
            #                              self.ui.spinBox_off_y_um.value()-self.ui.spinBox_range_y.value()/2.),
            #                         scale=(self.ui.spinBox_range_x.value() / self.ui.spinBox_nx.value(),
            #                                self.ui.spinBox_range_y.value() / self.ui.spinBox_ny.value()))

            if self.started_normal or self.started_preview:
                self.plotPreviewImage()
            else:
                self.plotPreviewImage(self.currentImage)

            self.AutoRange_im_widget()
            if self.started_normal or self.started_preview:
                self.axesRangeChanged()
        else:
            logger.debug("offset_um_update lock_parameters_changed_call is True")

        self.lock_parameters_changed_call = oldlock_parameters_changed_call
        self.lock_range_changing = oldlock_range_changing

    @Slot()
    def spatialSettingsChanged(self, force=False):
        """
        spatial settings changed event
        """
        if self.lockspatialSettingsChanged == False:
            # Update only the statistics the configuration will be updated during the start acquisition

            time_res = self.ui.spinBox_timeresolution.value()
            time_bin = self.ui.spinBox_time_bin_per_px.value()

            if self.ui.checkBox_circular.isChecked():
                circ_repetition = self.ui.spinBox_circular_repetition.value()
                circ_points = self.ui.spinBox_circular_points.value()
            else:
                circ_repetition = 1
                circ_points = 1

            clock_duration = time_bin * time_res * self.clock_base/2
            Cx = time_res * self.clock_base

            numbers_xx = self.ui.spinBox_nx.value()
            numbers_yy = self.ui.spinBox_ny.value()
            numbers_ff = self.ui.spinBox_nframe.value()
            rep = self.ui.spinBox_nrepetition.value()

            self.ui.label_dwell_time_val.setText("%0.3f" % (time_res * time_bin))
            self.ui.label_frame_time_val.setText(
                "%0.3f" % (time_res * time_bin * numbers_xx * numbers_yy * 1e-6)
            )
            self.ui.label_expected_dur_val.setText(
                "%0.3f"
                % (
                        time_res
                        * time_bin
                        * numbers_xx
                        * numbers_yy
                        * numbers_ff
                        * rep
                        * 1e-6
                )
            )

            self.checkAlerts()

            self.ui.pushButton_18.setStyleSheet("border: 1px solid red;")

        self.updateLabelPixelSize()


    @Slot()
    def positionSettingsChanged(self, force=False):
        """
        position settings changed event
        """
        self.offset_um_update(force)
        self.positionSettingsChanged_apply(force)

    def positionSettingsChanged_apply(self, force=False):
        """
        actuation of the position settings changed event
        """
        if not self.lock_parameters_changed_call or force:
            logger.debug("positionSettingsChanged_apply")
            xx = self.ui.spinBox_range_x.value()
            if self.ui.checkBoxLockRatio.isChecked():
                self.ui.spinBox_range_y.setValue(self.ui.spinBox_range_x.value())
            yy = self.ui.spinBox_range_y.value()
            zz = self.ui.spinBox_range_z.value()

            calib_xx = self.ui.spinBox_calib_x.value()
            calib_yy = self.ui.spinBox_calib_y.value()
            calib_zz = self.ui.spinBox_calib_z.value()

            offset_xx_um = self.ui.spinBox_off_x_um.value()
            offset_yy_um = self.ui.spinBox_off_y_um.value()
            offset_zz_um = self.ui.spinBox_off_z_um.value()

            self.ui.spinBox_off_x_V.setValue(offset_xx_um / calib_xx)
            self.ui.spinBox_off_y_V.setValue(offset_yy_um / calib_yy)
            self.ui.spinBox_off_z_V.setValue(offset_zz_um / calib_zz)

            offset_xx = self.ui.spinBox_off_x_V.value()
            offset_yy = self.ui.spinBox_off_y_V.value()
            offset_zz = self.ui.spinBox_off_z_V.value()

            numbers_xx = self.ui.spinBox_nx.value()
            numbers_yy = self.ui.spinBox_ny.value()
            numbers_ff = self.ui.spinBox_nframe.value()
            numbers_repetition = self.ui.spinBox_nrepetition.value()

            calibration_v_step = (
                    np.asarray([xx, yy, zz])
                    / np.asarray([calib_xx, calib_yy, calib_zz])
                    / np.asarray([numbers_xx, numbers_yy, numbers_ff])
            )

            offExtra_x_V = self.ui.spinBox_offExtra_x_V.value()
            offExtra_y_V = self.ui.spinBox_offExtra_y_V.value()
            offExtra_z_V = self.ui.spinBox_offExtra_z_V.value()

            start_offset = np.asarray(
                [
                    offset_xx - (0.5 * xx / calib_xx) + offExtra_x_V,
                    offset_yy - (0.5 * yy / calib_yy) + offExtra_y_V,
                    offset_zz - (0.5 * zz / calib_zz) + offExtra_z_V,
                ]
            )

            self.setRegistersDict(
                {
                    "axis_calibration_volts_per_step": calibration_v_step,
                    "axis_start_offset_volts": start_offset,
                    "max_pixel": numbers_xx,
                    "max_line": numbers_yy,
                    "max_frame": numbers_ff,
                    "max_repetition": numbers_repetition + 1,
                }
            )

            # self.rect_roi_modified_lock = True

            self.rect_roi.setSize(
                self.ui.spinBox_range_x.value(), self.ui.spinBox_range_y.value()
            )

            self.rect_roi.setPos(
                self.ui.spinBox_off_x_um.value(), self.ui.spinBox_off_y_um.value()
            )

            # for some bug this must be after setSize
            self.rect_roi.update()
            logger.debug(self.rect_roi.state)
            # self.rect_roi_modified_lock = False

            self.updateRectLimit() #update the rectangle in the panaorma

        else:
            logger.debug("positionSettingsChanged_apply lock_parameters_changed_call is True")

        self.checkAlerts()

    @Slot()
    def DFD_clicked(self):
        """
        activate the DFD mode
        """
        self.DFD_nbins = self.ui.spinBox_DFD_nbins.value()
        self.trace_dfd_widget.setVisible(self.ui.checkBox_DFD.isChecked())
        if self.ui.checkBox_DFD.isChecked():
            self.ui.spinBox_time_bin_per_px.setValue(self.DFD_nbins)
            self.ui.spinBox_timeresolution.setValue(2.0)
        self.updateLaserForcePulsingAvailability()

    def _currentLaserRegisterValue(self, register_name):
        """Return the latest configured value for a laser register, if known."""
        for configuration in (
            self.configurationFPGA_dict,
            self.mcs_manager.registers_configuration,
            self.mcs_manager.default_configuration,
        ):
            if register_name in configuration and configuration[register_name] is not None:
                return True, configuration[register_name]
        return False, None

    @Slot(bool)
    def laserForcePulsingChanged(self, enabled):
        """Apply force-pulsing registers and restore their prior values."""
        if enabled and self.ui.checkBox_DFD.isChecked():
            self.ui.checkBox_pulsing_forced.setChecked(False)
            return

        restored_registers = ("laser_time_bin_mode_enable", "max_laser_time_bin")
        if enabled:
            previous = {}
            for register_name in restored_registers:
                found, value = self._currentLaserRegisterValue(register_name)
                if found:
                    previous[register_name] = value
            self._laser_force_pulsing_previous = previous
            self.setRegistersDict(
                {
                    "laser_time_bin_mode_enable": True,
                    "max_laser_time_bin": 1,
                    "laser_force_pulsing_enable": True,
                }
            )
            return

        previous = self._laser_force_pulsing_previous
        if previous is None:
            # The unchecked initial UI state must not emit a hardware write.
            return

        restore = dict(previous)
        restore["laser_force_pulsing_enable"] = False
        for register_name in restored_registers:
            if register_name not in previous:
                # No value was configured before activation (normally this only
                # occurs before connecting); stop carrying the temporary forced
                # value into a later FPGA connection.
                self.configurationFPGA_dict.pop(register_name, None)
        self._laser_force_pulsing_previous = None
        self.setRegistersDict(restore)

    def updateLaserForcePulsingAvailability(self, _checked=None):
        """Force pulsing and DFD are mutually exclusive."""
        dfd_enabled = self.ui.checkBox_DFD.isChecked()
        if dfd_enabled and self.ui.checkBox_pulsing_forced.isChecked():
            self.ui.checkBox_pulsing_forced.setChecked(False)
        self.ui.checkBox_pulsing_forced.setEnabled(not dfd_enabled)

    @Slot(int)
    def compensationDelayForSnakeChanged(self, value):
        """
        Keep the snake-walk compensation delay synced with the runtime manager.
        """
        if hasattr(self, "mcs_manager") and self.mcs_manager is not None:
            self.mcs_manager.set_compensation_delay_for_snake(value)

    @Slot()
    def updateMaxMinVoltages(self):
        """
        event when the max and min voltages are changed
        """
        logger.debug("updateMaxMinVoltages")
        min_x_V = self.ui.spinBox_min_x_V.value()
        min_y_V = self.ui.spinBox_min_y_V.value()
        min_z_V = self.ui.spinBox_min_z_V.value()

        max_x_V = self.ui.spinBox_max_x_V.value()
        max_y_V = self.ui.spinBox_max_y_V.value()
        max_z_V = self.ui.spinBox_max_z_V.value()

        self.setRegistersDict(
            {
                "min_x_volts": min_x_V,
                "min_y_volts": min_y_V,
                "min_z_volts": min_z_V,
                "max_x_volts": max_x_V,
                "max_y_volts": max_y_V,
                "max_z_volts": max_z_V,
            }
        )

    @Slot()
    def plotSettingsChanged(self):
        """

        """
        logger.debug("plotSettingsChanged")
        self.updateColorLifetimeShiftControls()
        self.updatePreviewConfiguration()
        self.checkAlerts()

    def estimateDfdDecayLifetimeNs(
        self,
        trace_sum,
        trace_x_seconds,
        bin_width_ns,
        nbins,
        tcycle_s,
        start_level=0.95,
        end_level=0.25,
    ):
        trace_sum = np.asarray(trace_sum, dtype=float)
        trace_x_seconds = np.asarray(trace_x_seconds, dtype=float)
        if (
            trace_sum.size < 4
            or trace_x_seconds.size != trace_sum.size
            or not np.isfinite(bin_width_ns)
            or bin_width_ns <= 0
            or nbins <= 0
            or not np.isfinite(tcycle_s)
            or tcycle_s <= 0
            or not np.isfinite(start_level)
            or not np.isfinite(end_level)
            or not (0.0 < end_level < start_level < 1.0)
        ):
            logger.debug("FIT: invalid input parameters")
            return None, None, None, None, None

        peak_idx = int(np.argmax(trace_sum))
        trace_sum_peak0 = np.roll(trace_sum, -peak_idx)
        trace_x_peak0_seconds = np.roll(
            np.mod(trace_x_seconds - trace_x_seconds[peak_idx], tcycle_s),
            -peak_idx,
        )

        peak_value = float(trace_sum_peak0[0])
        if not np.isfinite(peak_value) or peak_value <= 0:
            #debug("FIT: invalid peak value")
            return None, None, peak_idx, trace_sum_peak0, trace_x_peak0_seconds

        y_start = start_level * peak_value
        idx_start_candidates = np.flatnonzero(trace_sum_peak0 <= y_start)
        fallback_levels = [end_level, 0.30, 0.40]
        fallback_levels = [level for level in fallback_levels if 0.0 < level < start_level]
        fallback_levels = list(dict.fromkeys(fallback_levels))
        selected_end_level = None
        idx_end_candidates = np.asarray([], dtype=int)
        y_end = None
        for candidate_end_level in fallback_levels:
            y_end_candidate = candidate_end_level * peak_value
            idx_end_candidate = np.flatnonzero(trace_sum_peak0 <= y_end_candidate)
            if idx_start_candidates.size != 0 and idx_end_candidate.size != 0:
                selected_end_level = candidate_end_level
                idx_end_candidates = idx_end_candidate
                y_end = y_end_candidate
                break

        if idx_start_candidates.size == 0 or idx_end_candidates.size == 0:
            #debug("FIT: y_start, y_end, idx_start_candidates, idx_end_candidates", y_start, y_end, idx_start_candidates, idx_end_candidates)
            #debug("FIT: no candidates for start or end indices")
            return None, None, peak_idx, trace_sum_peak0, trace_x_peak0_seconds

        #debug("FIT: start_level, selected_end_level", start_level, selected_end_level)

        start_idx = int(idx_start_candidates[0])
        end_idx = int(idx_end_candidates[0])
        if end_idx <= start_idx:
            #debug("FIT: end_idx <= start_idx")
            return None, None, peak_idx, trace_sum_peak0, trace_x_peak0_seconds

        y_section = trace_sum_peak0[start_idx : end_idx + 1]
        x_section_seconds = trace_x_peak0_seconds[start_idx : end_idx + 1]
        positive = y_section > 0
        if np.count_nonzero(positive) < 4:
            #debug("FIT: np.count_nonzero(positive) < 4")
            return None, None, peak_idx, trace_sum_peak0, trace_x_peak0_seconds

        x_fit_bins = np.arange(start_idx, end_idx + 1, dtype=float)[positive]
        x_fit_seconds = x_section_seconds[positive]
        y_fit_input = y_section[positive]
        slope, intercept = np.polyfit(x_fit_bins, np.log(y_fit_input), 1)
        #debug("FIT: slope and intercept", slope, intercept)
        if not np.isfinite(slope) or slope >= 0:
            return None, None, peak_idx, trace_sum_peak0, trace_x_peak0_seconds

        tau_ns = -float(bin_width_ns) / slope
        if not np.isfinite(tau_ns) or tau_ns <= 0:
            return None, None, peak_idx, trace_sum_peak0, trace_x_peak0_seconds

        y_fit = np.exp(intercept + slope * x_fit_bins)
        x_fit_bins_plot = np.mod(x_fit_bins + int(peak_idx), int(nbins))
        x_fit_seconds_plot = np.mod(x_fit_seconds + int(peak_idx) * bin_width_ns * 1e-9, tcycle_s)

        fit_curve = {
            "fit_len": int(end_idx - start_idx + 1),
            "x_fit_bins": x_fit_bins_plot,
            "x_fit_seconds": x_fit_seconds_plot,
            "y_fit": y_fit,
        }
        return float(tau_ns), fit_curve, peak_idx, trace_sum_peak0, trace_x_peak0_seconds

    def updateColorLifetimeShiftControls(self):
        current_channel = self.ui.comboBox_plot_channel.currentText()
        visible = self.isLifetimeColorChannel(current_channel)
        self.ui.label_delta_tau_ns.setVisible(visible)
        self.ui.doubleSpinBox_delta_tau_ns.setVisible(visible)
        self.ui.pushButton_delta_tau_auto.setVisible(visible)
        self.ui.widget_lifetime_hue_range.setVisible(visible)
        self.updateImageInteractionHints()

        clk_multiplier = 1
        if hasattr(self, "mcs_manager") and self.mcs_manager is not None:
            clk_multiplier = max(int(self.mcs_manager.clk_multiplier), 1)
        dfd_cycle_mhz = max(float(getattr(self, "dfd_cycle_mhz", 40.0)), 1e-12)
        tcycle_ns = 1e3 / (dfd_cycle_mhz * clk_multiplier)
        self.ui.label_delta_tau_ns.setText(f"Corr. delta_tau [ns] (T={tcycle_ns:.4f})")

        self.ui.doubleSpinBox_delta_tau_ns.blockSignals(True)
        self.ui.doubleSpinBox_delta_tau_ns.setRange(0.0, max(tcycle_ns, 1e-12))
        self.ui.doubleSpinBox_delta_tau_ns.setSingleStep(max(tcycle_ns / 100.0, 1e-4))
        if tcycle_ns > 0.0:
            wrapped_value = self.ui.doubleSpinBox_delta_tau_ns.value() % tcycle_ns
            self.ui.doubleSpinBox_delta_tau_ns.setValue(wrapped_value)
        self.ui.doubleSpinBox_delta_tau_ns.blockSignals(False)

    @Slot()
    def colorLifetimeDeltaTauChanged(self):
        self.updateColorLifetimeShiftControls()
        if self.isLifetimeColorChannel():
            self.plotPreviewImage()

    @Slot()
    def colorLifetimeDeltaTauUseHistogramMean(self):
        if not self.isLifetimeColorChannel():
            return

        tcycle_ns = 1e3 / (
            max(float(self.dfd_cycle_mhz), 1e-12)
            * max(int(self.mcs_manager.clk_multiplier), 1)
        )
        h_mean = self.im_widget.getDisplayedHMean()
        tau_fit_ns = self.latest_dfd_tau_fit_ns
        if h_mean is None or tau_fit_ns is None:
            return

        current_mean_ns = float(h_mean) * tcycle_ns
        corrected_value = (
            self.ui.doubleSpinBox_delta_tau_ns.value()
            + current_mean_ns
            - float(tau_fit_ns)
        ) % tcycle_ns

        self.ui.doubleSpinBox_delta_tau_ns.blockSignals(True)
        self.ui.doubleSpinBox_delta_tau_ns.setValue(corrected_value)
        self.ui.doubleSpinBox_delta_tau_ns.blockSignals(False)
        self.plotPreviewImage()

    def getLifetimeColorRenderMode(self, channel_name=None):
        if channel_name is None:
            channel_name = self.ui.comboBox_plot_channel.currentText()
        render_modes = {
            "COLOR_LIFETIME": "hcl",
            "LIFETIME_HCL": "hcl",
            "LIFETIME_HSV": "hsv",
            "LIFETIME_HSL": "hsl",
        }
        return render_modes.get(channel_name)

    def isLifetimeColorChannel(self, channel_name=None):
        return self.getLifetimeColorRenderMode(channel_name) is not None

    def getLifetimeHueDisplayRange(self):
        return (
            float(self.ui.doubleSpinBox_lifetime_hue_min.value()),
            float(self.ui.doubleSpinBox_lifetime_hue_max.value()),
        )

    def getLifetimeForceQualityFull(self):
        return bool(self.ui.checkBox_lifetime_force_quality_full.isChecked())

    def updateImageInteractionHints(self):
        visible = not self.isLifetimeColorChannel()
        for label_name in ("label_106", "label_107"):
            label = getattr(self.ui, label_name, None)
            if label is not None:
                label.setVisible(visible)

    @Slot()
    def previewButtonClicked(self):
        """
        preview button clicked event
        """
        self.previewLoop()

    @Slot()
    def startButtonClicked(self):
        """
        start button clicked event
        """
        self.start()

    @Slot()
    def stopButtonClicked(self):
        """
        stop button clicked event
        """
        self.stop()

    def _update_fpga_connection_button(self):
        """Reflect whether FPGA firmware is currently loaded."""
        connected = bool(self.mcs_manager.is_connected)
        keep_requested = bool(
            getattr(self, "_keep_fpga_on_requested", False)
        )
        button = self.ui.pushButton_fpga_connection_cmd
        button.setChecked(connected and keep_requested)
        button.setText(
            "Disconnect FPGA"
            if connected and keep_requested
            else "Keep FPGA On"
        )
        button.setToolTip(
            "Stop any active acquisition, reset, and disconnect the FPGA"
            if connected
            else "Load the FPGA firmware and keep it connected"
        )
        if not connected:
            self._fpga_watchdog_blink_on = False
            self.ui.label_FPGA_status.setText("● FPGA disconnected")
            self.ui.label_FPGA_status.setStyleSheet("color: #808080;")
            self.ui.label_FPGA_status.setToolTip("Waiting for a Preview / Acquisition or the Keep FPGA On button.")

    @Slot()
    def _fpgaWatchdogTick(self):
        """Poll the FPGA and blink its status label after successful reads."""
        if not self.mcs_manager.is_connected:
            self._update_fpga_connection_button()
            return

        try:
            status = self.mcs_manager.check_fpga_alive()
        except Exception as error:
            self._fpga_watchdog_blink_on = False
            self.ui.label_FPGA_status.setText("● FPGA not responding")
            self.ui.label_FPGA_status.setStyleSheet("color: #d32f2f;")
            self.ui.label_FPGA_status.setToolTip(str(error))
            logger.warning("FPGA watchdog read failed: %s", error)
            return

        self._fpga_watchdog_blink_on = not self._fpga_watchdog_blink_on
        color = "#00e676" if self._fpga_watchdog_blink_on else "#006b3c"
        self.ui.label_FPGA_status.setText("● FPGA connected")
        self.ui.label_FPGA_status.setStyleSheet(f"color: {color};")
        self.ui.label_FPGA_status.setToolTip(
            f"Watchdog OK — debug_scan_fsm_status: {status}"
        )

    def _show_fpga_initialization_error(self, error):
        """Show an actionable hardware or firmware connection error."""
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.setWindowTitle("FPGA initialization failed")
        msg.setText("The FPGA could not be initialized.\n"
                    "Probably the firmware selected is not compatible with the hardware, " \
                    "or the hardware is not connected. Check that the firmware is correct" \
                    "and the FPGA is powered on and connected.")
        msg.setInformativeText(str(error))
        msg.setDetailedText(
            "Check that:\n"
            "- the FPGA is powered on and connected;\n"
            "- FPGA BitFile matches the FPGA model and BrightEyes-MCS;\n"
            "- FPGA Addr is correct (usually RIO0)."
        )
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()

    def disconnectFPGA(self):
        """Stop FPGA activity and close the hardware session."""
        self._keep_fpga_on_requested = False
        if not self.mcs_manager.is_connected:
            self._update_fpga_connection_button()
            return

        reset_error = None
        try:
            self.mcs_manager.quick_reset_fpga(
                timeout=self.FPGA_IDLE_TIMEOUT_SECONDS
            )
        except Exception as error:
            reset_error = error
            logger.exception(
                "FPGA quick reset failed; forcing the session to close"
            )

        try:
            self.mcs_manager.stopPreview()
            self.timerPreviewImg.stop()
            self.mcs_manager.stopFPGA()
        finally:
            self.mcs_manager.stopAcquisition(keep_fpga_loaded=False)
            self.mcs_manager.is_connected = False
            self._update_fpga_connection_button()

        if reset_error is not None:
            raise reset_error

    @Slot(bool)
    def fpgaConnectionButtonClicked(self, checked):
        """Connect when checked; stop, reset, and disconnect when unchecked."""
        self._keep_fpga_on_requested = bool(checked)
        try:
            if not checked:
                if self.started_normal or self.started_preview:
                    self.stop()
                if self.mcs_manager.is_connected:
                    self.disconnectFPGA()
                self.ui.statusBar.showMessage("FPGA disconnected.", 5000)
            elif not self.mcs_manager.is_connected:
                self.connectFPGA()
                self._fpgaWatchdogTick()
                self.ui.statusBar.showMessage("FPGA connected and idle.", 5000)
        except Exception as error:
            logger.exception("Could not change the FPGA connection state")
            self._keep_fpga_on_requested = False
            self.ui.pushButton_fpga_connection_cmd.setChecked(False)
            self._show_fpga_initialization_error(error)
        finally:
            self._update_fpga_connection_button()

    # @Slot()
    # def connectButtonClicked(self):
    #     self.connectCmd()

    # def afterFpgaRun(self):
    #     pass

    def initializeAcquisition(self, do_not_save=False, do_run=True, raw_stream_mode=False):
        """
        Initialize and configure acquisition parameters (registers, calibration, trace settings, etc.).
        This method does NOT start the acquisition - it only prepares the system.
        """
        self.do_not_save = do_not_save
        self.raw_stream_mode = raw_stream_mode

        # Initialize DFD settings BEFORE circular motion to ensure correct state
        self.dfd_enable = self.ui.checkBox_DFD.isChecked()
        self.DFD_nbins = self.ui.spinBox_DFD_nbins.value()

        # Now initialize circular motion with correct DFD state
        self.circularMotionActivateChanged()

        self.spadChannelsChanged()
        self.mcs_manager.set_spad_channels(int(self.ui.comboBox_spad_channels.currentText()))
        self.mcs_manager.set_pi23_connection(
            self.ui.lineEdit_pi23_ip_addr.text(),
            self.ui.spinBox_pi23_port.value(),
        )

        self.mcs_manager.set_dfd_enable(self.dfd_enable)
        self.mcs_manager.set_DFD_nbins(self.DFD_nbins)

        self.ui.progressBar_fifo_digital.setMaximum(5)
        self.ui.progressBar_fifo_analog.setMaximum(5)
        self.ui.progressBar_saving.setMaximum(5)

        self.currentImage_pos = np.asarray(
            (
                self.ui.spinBox_off_x_um.value(),  # - self.ui.spinBox_range_x.value()/2,
                self.ui.spinBox_off_y_um.value(),  # - self.ui.spinBox_range_y.value()/2,
                self.ui.spinBox_off_z_um.value(),
            )
        )  # - self.ui.spinBox_range_z.value()/2,))

        self.currentImage_size = np.asarray(
            (
                self.ui.spinBox_range_x.value(),
                self.ui.spinBox_range_y.value(),
                self.ui.spinBox_range_z.value(),
            )
        )

        self.currentImage_pixels = np.asarray(
            (
                self.ui.spinBox_nx.value(),
                self.ui.spinBox_ny.value(),
                self.ui.spinBox_nframe.value(),
            )
        )

        time_res = self.ui.spinBox_timeresolution.value()
        time_bin = self.ui.spinBox_time_bin_per_px.value()

        if self.ui.checkBox_circular.isChecked():
            circ_repetition = self.ui.spinBox_circular_repetition.value()
            circ_points = self.ui.spinBox_circular_points.value()
        else:
            circ_repetition = 1
            circ_points = 1

        clock_duration = time_bin * time_res * self.clock_base/2
        Cx = time_res * self.clock_base

        waitForLaserInCycle = self.ui.spinBox_waitForLaser.value() * 40e6
        waitAfterFrame = self.ui.spinBox_waitAfterFrame.value() * 40e6
        waitOnlyFirstTime = self.ui.checkBox_waitOnlyFirstTime.isChecked()

        logger.debug("temporalSettingsChanged")

        circular_motion = self.ui.checkBox_circular.isChecked()
        dummy_data = self.ui.checkBox_DummyData.isChecked()

        laser_seq_gui = [int(self.ui.comboLaserSeq_1.currentText()),
                        int(self.ui.comboLaserSeq_2.currentText()),
                        int(self.ui.comboLaserSeq_3.currentText()),
                        int(self.ui.comboLaserSeq_4.currentText()),
                        int(self.ui.comboLaserSeq_5.currentText()),
                        int(self.ui.comboLaserSeq_6.currentText()),
                        int(self.ui.comboLaserSeq_7.currentText()),
                        int(self.ui.comboLaserSeq_8.currentText()),
                        int(self.ui.comboLaserSeq_9.currentText()),
                        int(self.ui.comboLaserSeq_10.currentText()),
                        int(self.ui.comboLaserSeq_11.currentText()),
                        int(self.ui.comboLaserSeq_12.currentText())
                         ]

        laser_sequence =  [laser_seq_gui[0],
                           laser_seq_gui[1],
                           laser_seq_gui[2],
                           laser_seq_gui[3],
                           laser_seq_gui[4],
                           laser_seq_gui[5],
                           laser_seq_gui[6],
                           laser_seq_gui[7],
                           laser_seq_gui[8],
                           laser_seq_gui[9],
                           laser_seq_gui[10],
                           laser_seq_gui[11],
                           0,0,0,0,0,0,0,0,0,0,0,0,
                           ]

        slave_mode = self.ui.checkBox_slavemode_enable.isChecked()
        slave_type = self.ui.comboBox_slavemode_type.currentIndex()

        vr0 = self.ui.checkBox_SPAD_VR0.isChecked()
        vr1 = self.ui.checkBox_SPAD_VR0.isChecked()

        xx = self.ui.spinBox_range_x.value()
        yy = self.ui.spinBox_range_y.value()
        zz = self.ui.spinBox_range_z.value()

        calib_xx = self.ui.spinBox_calib_x.value()
        calib_yy = self.ui.spinBox_calib_y.value()
        calib_zz = self.ui.spinBox_calib_z.value()

        if self.spad_channels == 49:
            self.setRegistersDict(
                {
                    "detector_49_channel_mode_enable": True
                }
            )
        else:
            self.setRegistersDict(
                {
                    "detector_49_channel_mode_enable": False
                }
            )

        offset_xx_um = self.ui.spinBox_off_x_um.value()
        offset_yy_um = self.ui.spinBox_off_y_um.value()
        offset_zz_um = self.ui.spinBox_off_z_um.value()

        self.ui.spinBox_off_x_V.setValue(offset_xx_um / calib_xx)
        self.ui.spinBox_off_y_V.setValue(offset_yy_um / calib_yy)
        self.ui.spinBox_off_z_V.setValue(offset_zz_um / calib_zz)

        offset_xx = self.ui.spinBox_off_x_V.value()
        offset_yy = self.ui.spinBox_off_y_V.value()
        offset_zz = self.ui.spinBox_off_z_V.value()

        numbers_xx = self.ui.spinBox_nx.value()
        numbers_yy = self.ui.spinBox_ny.value()
        numbers_ff = self.ui.spinBox_nframe.value()
        numbers_repetition = self.ui.spinBox_nrepetition.value()

        calibration_v_step = (
                np.asarray([xx, yy, zz])
                / np.asarray([calib_xx, calib_yy, calib_zz])
                / np.asarray([numbers_xx, numbers_yy, numbers_ff])
        )

        offExtra_x_V = self.ui.spinBox_offExtra_x_V.value()
        offExtra_y_V = self.ui.spinBox_offExtra_y_V.value()
        offExtra_z_V = self.ui.spinBox_offExtra_z_V.value()

        laserEnable0 = self.ui.checkBox_laser0.isChecked()
        laserEnable1 = self.ui.checkBox_laser1.isChecked()
        laserEnable2 = self.ui.checkBox_laser2.isChecked()
        laserEnable3 = self.ui.checkBox_laser3.isChecked()
        self.snake_walk_Activate_XY = self.ui.checkBox_snake.isChecked()
        self.snake_walk_Activate_Z = self.ui.checkBox_snake_z.isChecked()
        self.mcs_manager.set_activate_snake_walk_xy(self.snake_walk_Activate_XY)
        self.mcs_manager.set_activate_snake_walk_z(self.snake_walk_Activate_Z)
        self.compensationDelayForSnakeChanged(
            self.ui.spinBox_compensation_delay.value()
        )

        start_offset = np.asarray(
            [
                offset_xx - (0.5 * xx / calib_xx) + offExtra_x_V,
                offset_yy - (0.5 * yy / calib_yy) + offExtra_y_V,
                offset_zz - (0.5 * zz / calib_zz) + offExtra_z_V,
            ]
        )

        laser_debug = self.ui.checkBox_DFD_LaserDebug.isChecked()

        self.setRegistersDict(
            {
                "time_bin_dwell_cycles": int(Cx),
                "max_time_bins_per_pixel": int(time_bin),
                "tag_clock_duration_cycles": int(clock_duration),
                "wait_laser_startup_cycles": int(waitForLaserInCycle),
                "wait_post_frame_cycles": int(waitAfterFrame),
                "wait_laser_first_time_only_enable": waitOnlyFirstTime,
                "max_circular_point": circ_points,
                "max_circular_repetition": circ_repetition,
                "circular_scan_enable": circular_motion,
                "dummy_data_enable": dummy_data,
                "laser_excitation_sequence": laser_sequence,
                "slave_mode_external_source_selector": slave_type,
                "slave_mode_enable": slave_mode,
                "spad_vr0_enable": vr0,
                "spad_vr1_enable": vr1,
                "xy_snake_scan_enable": self.snake_walk_Activate_XY,
                "z_snake_scan_enable": self.snake_walk_Activate_Z,
                "dfd_laser_sync_debug_enable": laser_debug,
                # "AD5764_MaxBit": 1,
                "axis_calibration_volts_per_step": calibration_v_step,
                "axis_start_offset_volts": start_offset,
                "max_pixel": numbers_xx,
                "max_line": numbers_yy,
                "max_frame": numbers_ff,
                "max_repetition": numbers_repetition + 1,
                "laser_1_enable": laserEnable0,
                "laser_2_enable": laserEnable1,
                "laser_3_enable": laserEnable2,
                "laser_4_enable": laserEnable3,
                "dfd_trigger_selector": 5, #IT MEANS GET DFD EVERY CIRCULAR SCANNING POINT THIS SHOULD NOT HARD-CODE
            }
        )

        # self.pmtThresholdChanged()

        self.configurationFPGA_dict.update(
            self.mcs_manager.registers_configuration
        )
        self.current_plot_size_x_um = self.ui.spinBox_range_x.value()
        self.current_plot_size_y_um = self.ui.spinBox_range_y.value()
        self.current_plot_size_z_um = self.ui.spinBox_range_z.value()

        self.current_number_px_x = self.ui.spinBox_nx.value()
        self.current_number_px_y = self.ui.spinBox_ny.value()
        self.current_number_px_z = self.ui.spinBox_nframe.value()

        # self.rect_roi_modified_lock = True
        self.rect_roi.setSize(
            self.ui.spinBox_range_x.value(), self.ui.spinBox_range_y.value()
        )
        # self.rect_roi.setPos(-self.ui.spinBox_range_x.value() / 2 + self.ui.spinBox_off_x_um.value(),
        #                      -self.ui.spinBox_range_y.value() / 2 + self.ui.spinBox_off_y_um.value())
        self.rect_roi.setPos(
            self.ui.spinBox_off_x_um.value(), self.ui.spinBox_off_y_um.value()
        )
        # self.rect_roi.setSize(self.ui.spinBox_nx.value(), self.ui.spinBox_ny.value())
        # self.rect_roi.setPos(0., 0.) # for some bug this must be after setSize
        self.rect_roi.update()

        logger.debug(self.rect_roi.state)

        # self.rect_roi_modified_lock = False
        self.timerPreviewImg.start()

        logger.debug(self.rect_roi.state)
        self.updateMaxMinVoltages()

        self.analogOutChanged()
        self.configure_analog()

        if do_run:
            self.configure_stream_enables()
        self.activateShowPreview(self.ui.checkBox_showPreview.isChecked() and not raw_stream_mode)


        self.mcs_manager.set_do_not_save(do_not_save)
        self.mcs_manager.set_raw_stream_mode(raw_stream_mode)

        filename_for_ttm = self.defineFilename(with_folder=False)
        if self.ttm_remote_is_up() and not do_not_save:
            self.ttm_remote_manager.set_folder_name_remote(
                self.ui.lineEdit_ttm_filename.text()
            )
            self.ttm_remote_manager.set_file_name_remote(
                filename_for_ttm.replace(".h5", ".ttr")
            )

        filename = (
            self.defineMetadataFilename(with_folder=True)
            if raw_stream_mode
            else self.defineFilename(with_folder=True)
        )
        self.last_requested_filename = filename
        self.mcs_manager.set_filename_h5(filename)
        if raw_stream_mode:
            self.raw_stream_output_files = self.defineRawOutputFiles(filename)
            self.mcs_manager.set_raw_output_files(self.raw_stream_output_files)
        else:
            self.raw_stream_output_files = {}
        self.mcs_manager.set_autocorrelation_maxx(
            self.ui.spinBox_FCSbins.value()
        )

        trace_bins = int(
            self.ui.doubleSpinBox_binsize.value()
            * 1e3
            / (self.ui.spinBox_timeresolution.value())
        )

        trace_length = (
                self.ui.doubleSpinBox_maxlength.value()
                * 1e6
                / (self.ui.spinBox_timeresolution.value())
        )

        trace_sample_per_bins = int(trace_length // trace_bins)

        logger.debug("%s %s", "trace_bins", trace_bins)
        logger.debug("%s %s", "trace_length", trace_length)
        logger.debug("%s %s", "trace_sample_per_bins", trace_sample_per_bins)

        self.mcs_manager.set_trace_bins(trace_bins=trace_bins)
        self.mcs_manager.set_trace_sample_per_bins(
            trace_sample_per_bins=trace_sample_per_bins
        )

        self.ui.label_trace_total_bins.setText("%s" % trace_sample_per_bins)
        self.ui.label_configured_fifo_depth.setText(
            "%d" % self.mcs_manager.fpga_handle.get_actual_fifo_depth()
        )
        if self.dfd_enable:
            self.mcs_manager.set_clk_multiplier(
                self.ui.spinBox_clk_base_multiplier.value()
            )
        else:
            self.mcs_manager.set_clk_multiplier(1)

        # self.mcs_manager.acquistion_run()
        if self.ttm_remote_is_up() and not do_not_save:
            self.ttm_remote_manager.start_ttm_recv()

        if self.ui.checkBox_uttmActivate.isChecked() and \
           self.ui.checkBox_uttm_auto.isChecked() and \
           not do_not_save :
               self.pushButton_uttm_start_clicked()

        self.mcs_manager.run()

        self.plugin_signals.signal.emit("beforeRun")

        if do_run:
            self.sendCmdRun()

        self.update_fingerprint_mask()

    @Slot()
    def test_analog_digital(self):
        """experimental mixed analog and digital mode"""
        logger.debug("test_analog_digital()")
        self.ui.checkBox_fifo_analog.setAutoExclusive(False)
        self.ui.checkBox_fifo_digital.setAutoExclusive(False)
        logger.debug("now the ratioButton can be on at the same time")

    @Slot()
    def trace_parameters_changed(self):
        """trace parameters changed event"""
        trace_bins = int(
            self.ui.doubleSpinBox_binsize.value()
            * 1e3
            / (self.ui.spinBox_timeresolution.value())
        )
        trace_length = (
                self.ui.doubleSpinBox_maxlength.value()
                * 1e6
                / (self.ui.spinBox_timeresolution.value())
        )
        trace_sample_per_bins = int(trace_length // trace_bins)
        self.ui.label_trace_total_bins.setText("%s" % trace_sample_per_bins)
        if trace_sample_per_bins > 100000:
            self.ui.label_trace_total_bins.setStyleSheet("border: 1px solid red;")
        else:
            self.ui.label_trace_total_bins.setStyleSheet("")

    def configure_analog(self):
        """
        configure the dictionary for the analog input
        """
        logger.debug("Configure Analog")
        # ANALOG CONFIGURATION
        # self.ui.checkBox_analog_in_integrate_AI0
        # self.ui.checkBox_analog_in_integrate_AI1
        # self.ui.checkBox_analog_in_integrate_AI2
        # self.ui.checkBox_analog_in_integrate_AI3
        #
        # self.ui.checkBox_analog_in_invert_AI0
        # self.ui.checkBox_analog_in_invert_AI1
        # self.ui.checkBox_analog_in_invert_AI2
        # self.ui.checkBox_analog_in_invert_AI3
        #
        # self.ui.checkBox_analog_in_differentiate_A
        # self.ui.checkBox_analog_in_differentiate_B
        #
        # self.ui.comboBox_analogSelect_A
        # self.ui.comboBox_analogSelect_B

        self.setRegistersDict(
            {
                "analog_a_channel_0_integrate_enable": self.ui.checkBox_analog_in_integrate_AI0.isChecked(),
                "analog_a_channel_0_invert_enable": self.ui.checkBox_analog_in_invert_AI0.isChecked(),
                "analog_a_channel_1_integrate_enable": self.ui.checkBox_analog_in_integrate_AI1.isChecked(),
                "analog_a_channel_1_invert_enable": self.ui.checkBox_analog_in_invert_AI1.isChecked(),
                "analog_a_channel_2_integrate_enable": self.ui.checkBox_analog_in_integrate_AI2.isChecked(),
                "analog_a_channel_2_invert_enable": self.ui.checkBox_analog_in_invert_AI2.isChecked(),
                "analog_a_channel_3_integrate_enable": self.ui.checkBox_analog_in_integrate_AI3.isChecked(),
                "analog_a_channel_3_invert_enable": self.ui.checkBox_analog_in_invert_AI3.isChecked(),
                "analog_a_input_selector": self.ui.comboBox_analogSelect_A.currentIndex(),
                "analog_b_input_selector": self.ui.comboBox_analogSelect_B.currentIndex(),
                "analog_a_differential_mode_enable": self.ui.checkBox_analog_in_differentiate_A.isChecked(),
                "analog_b_differential_mode_enable": self.ui.checkBox_analog_in_differentiate_B.isChecked(),
            }
        )

    def activateShowPreview(self, enable):
        """
        activate the preview mode
        """
        self.mcs_manager.activateShowPreview(enable)

    def configure_stream_enables(self):
        """
        Configure the firmware output-stream enable registers.
        """

        logger.debug("configure_stream_enables")
        logger.debug("%s %s", "DFD", self.dfd_enable)

        fifo = []
        if self.ui.checkBox_fifo_digital.isChecked():
            fifo.append("stream_out_main")
        if self.ui.checkBox_fifo_analog.isChecked():
            fifo.append("stream_out_aux")

        self.mcs_manager.setActivatedFifo(fifo)

        if self.dfd_enable:
            self.setRegistersDict(
                {
                    "dfd_enable": True,
                    "stream_out_aux_enable": self.ui.checkBox_fifo_analog.isChecked(),
                    "stream_out_main_enable": self.ui.checkBox_fifo_digital.isChecked(),
                }
            )
        else:
            self.setRegistersDict(
                {
                    "dfd_enable": False,
                    "stream_out_aux_enable": self.ui.checkBox_fifo_analog.isChecked(),
                    "stream_out_main_enable": self.ui.checkBox_fifo_digital.isChecked(),
                }
            )

    def updateRectLimit(self):
        """
        init the panorama image
        """

        lim_x = (self.ui.spinBox_max_x_V.value() - self.ui.spinBox_min_x_V.value()) * self.ui.spinBox_calib_x.value()
        lim_y = (self.ui.spinBox_max_y_V.value() - self.ui.spinBox_min_y_V.value()) * self.ui.spinBox_calib_y.value()

        self.rect_roi_panorama_limit.setSize(lim_x, lim_y)

        self.rect_roi_panorama_limit.setPos(-lim_x/2., -lim_y/2.)

        # debug("Panorama")
        #
        # pos_x = 0.
        # pos_y = 0.
        # size_x = (self.ui.spinBox_max_x_V.value() - self.ui.spinBox_min_x_V.value()) * self.ui.spinBox_calib_x.value()
        # size_y = (self.ui.spinBox_max_y_V.value() - self.ui.spinBox_min_y_V.value()) * self.ui.spinBox_calib_y.value()
        # img = np.zeros((101, 101))
        # img[0, :] = 1
        # img[:, 0] = 1
        # img[100, :] = 1
        # img[:, 100] = 1
        #
        # self.im_panorama_widget.setImage(
        #     img=img,
        #     pos=(
        #         -size_x / 2.,
        #         -size_y / 2.,
        #     ),
        #     scale=(
        #         size_x / img.shape[0],
        #         size_y / img.shape[1],
        #     ),
        # )
        # debug(pos_x, pos_y, size_x, size_y)
        # self.im_widget_panorama.setItem(img)


    @Slot()
    def grabPanorama(self):
        """
        grab the panorama image
        """
        logger.debug("Panorama")

        pos_x = self.im_widget.getImageItem().x()
        pos_y = self.im_widget.getImageItem().y()
        size_x = self.im_widget.getImageItem().width()
        size_y = self.im_widget.getImageItem().height()
        img = self.im_widget.getImageItem().image

        self.im_panorama_widget.setImage(
            img=img,
            pos=(
                self.currentImage_pos[0] - self.currentImage_size[0] / 2.0,
                self.currentImage_pos[1] - self.currentImage_size[1] / 2.0,
            ),
            scale=(
                self.currentImage_size[0] / self.currentImage_pixels[0],
                self.currentImage_size[1] / self.currentImage_pixels[1],
            ),
        )
        self.im_panorama_widget.show()
        logger.debug("%s %s %s %s", pos_x, pos_y, size_x, size_y)
        # self.im_widget_panorama.setItem(img)

    def updatePreviewConfiguration(self):
        """
        update the preview configuration - channel selection
        """
        logger.debug("updatePreviewConfiguration")

        t = self.ui.comboBox_plot_channel.currentText()
        self.ui.label_plot_channel.setText("Ch. selected: %s" % t.upper())

        if t.isnumeric():
            self.selected_channel = int(t)
        else:
            self.selected_channel = t

        self.mcs_manager.update_shared_dict(
            {
                "proj": self.ui.comboBox_view_projection.currentText(),
                "channel": self.selected_channel,
                "activate_autocorrelation": self.ui.checkBox_fcs_preview.isChecked(),
                "activate_trace": self.ui.checkBox_trace_on.isChecked(),
            }
        )
        logger.debug(self.mcs_manager.read_shared_dict())

    def defineFilename(self, with_folder=True):
        """
        helper for define the filename of the data output
        """
        folder = self.ui.lineEdit_destinationfolder.text()
        filename = self.ui.lineEdit_filename.text()
        if not ".h5" in filename:
            filename = filename + ".h5"

        if folder != "":
            folder = folder + "/"

        if filename == "DEFAULT.h5":
            filename = "data-" + datetime.now().strftime("%d-%m-%Y-%H-%M-%S") + ".h5"
        else:
            if QFile(folder + filename).exists():
                filename = (
                        filename.replace(".h5", "")
                        + datetime.now().strftime("%d-%m-%Y-%H-%M-%S")
                        + ".h5"
                )
                logger.debug("FILE EXISTS")
        logger.debug(filename)
        if with_folder:
            return folder + filename
        else:
            return filename

    def defineMetadataFilename(self, with_folder=True):
        """
        Derive the metadata-only H5 filename used by preview-less RAW acquisitions.
        """
        return metadata_filename(self.defineFilename(with_folder=with_folder))

    def defineRawOutputFiles(self, metadata_filename):
        """
        Derive raw FIFO output paths from the metadata H5 filename.
        """
        return raw_output_files(
            metadata_filename,
            digital=self.ui.checkBox_fifo_digital.isChecked(),
            analog=self.ui.checkBox_fifo_analog.isChecked(),
        )

    @Slot()
    def start(self):
        """
        Start acquisition in normal mode (full duration, with saving).
        Wrapper for backward compatibility.
        """
        self.beginAcquisition(is_preview=False)

    def _prepare_fpga_for_acquisition(self):
        """Connect when necessary and reset the scan FSM before each run."""
        if not self.mcs_manager.is_connected:
            logger.debug("FPGA not connected, connecting now...")
            self.connectFPGA()
        else:
            logger.debug("FPGA already connected")

        # A freshly loaded firmware is not guaranteed to have observed a stop
        # command.  Without this pulse the first start can be ignored, while a
        # later run succeeds only because stopping the first one reset the FSM.
        self.mcs_manager.quick_reset_fpga(
            timeout=self.FPGA_IDLE_TIMEOUT_SECONDS
        )

    @Slot()
    def beginAcquisition(self, is_preview=False):
        """
        Start the acquisition with unified initialization for both normal and preview modes.
        
        Args:
            is_preview (bool): If True, run in preview mode (limited repetitions, no saving).
                             If False, run in normal acquisition mode.
        """
        logger.debug("beginAcquisition(is_preview=%s)" % is_preview)

        # Enable TTM if requested
        if self.ui.checkBox_ttmActivate.isChecked():
            self.ttm_activate_change_state()

        # Update UI button states
        self.ui.pushButton_previewStart.setEnabled(False)
        self.ui.pushButton_acquisitionStart.setEnabled(False)
        self.ui.pushButton_stop.setEnabled(True)

        # Validate and start the FPGA before allocating acquisition workers or
        # activating any FIFO readers.
        try:
            self._prepare_fpga_for_acquisition()
        except Exception as error:
            logger.exception("FPGA preparation failed; acquisition not started")
            if self.mcs_manager.is_connected:
                try:
                    self.disconnectFPGA()
                except Exception:
                    logger.exception(
                        "Could not fully close the failed FPGA connection"
                    )
            self.ui.pushButton_previewStart.setEnabled(True)
            self.ui.pushButton_acquisitionStart.setEnabled(True)
            self.ui.pushButton_stop.setEnabled(False)
            self.ui.pushButton_fpga_connection_cmd.setEnabled(True)
            self._update_fpga_connection_button()
            self.ui.statusBar.showMessage("FPGA initialization failed.", 5000)
            self._show_fpga_initialization_error(error)
            return

        # Configure preview settings
        self.updatePreviewConfiguration()

        # Reset current image state
        self.currentImage = None
        self.activeFile = False
        self.mcs_manager.acquisition_done_reset()
        self.mcs_manager.acquisition_almost_done_reset()

        # Set acquisition mode flags
        self.started_normal = not is_preview
        self.started_preview = is_preview
        self._pending_program_state_after_stop = None
        raw_stream_mode = (not is_preview) and self.ui.checkBox_rawStreamAcquisition.isChecked()
        self.raw_stream_mode = raw_stream_mode

        # Hide ROI and reset progress bars
        self.rect_roi.hide()
        self.ui.progressBar_repetition.setValue(0)
        self.ui.progressBar_frame.setMaximum(0)
        self.ui.progressBar_fifo_digital.setMaximum(5)
        self.ui.progressBar_fifo_analog.setMaximum(5)
        self.ui.progressBar_saving.setMaximum(5)

        # Save current GUI configuration for later comparison
        self.configurationGUI_dict_beforeStart = self.getGUI_data()

        # If preview mode, adjust repetitions and disable certain controls
        if is_preview:
            self.nrepetition_before_run_preview = self.ui.spinBox_nrepetition.value()
            old_lock = self.lockspatialSettingsChanged
            self.lockspatialSettingsChanged = True
            self.ui.spinBox_nrepetition.setValue(30000)
            self.ui.spinBox_nx.setEnabled(0)
            self.ui.spinBox_ny.setEnabled(0)
            self.ui.spinBox_nframe.setEnabled(0)
            self.ui.spinBox_nrepetition.setEnabled(0)
            self.lockspatialSettingsChanged = old_lock

            # Apply preview-specific settings
            self.positionSettingsChanged_apply()
            self.temporalSettingsChanged()
            self.plotSettingsChanged()

            # Disable additional UI elements for preview
            self.ui.checkBox_fifo_digital.setEnabled(False)
            self.ui.checkBox_fifo_analog.setEnabled(False)
            self.ui.checkBox_DFD.setEnabled(False)
            self.ui.checkBox_uttmActivate.setEnabled(False)
            self.ui.checkBox_ttmActivate.setEnabled(False)
            self.ui.pushButton_externalProgram.setEnabled(False)

        # Initialize acquisition with appropriate mode flag
        self.initializeAcquisition(
            do_not_save=is_preview,
            do_run=True,
            raw_stream_mode=raw_stream_mode,
        )

        if is_preview:
            self.preview_run_id += 1
            self.last_preview_started_at = self._make_status_timestamp()
            self._set_program_state(
                self.PROGRAM_STATE_PREVIEW, "preview_started"
            )
        else:
            self.acquisition_run_id += 1
            self.last_acquisition_started_at = self._make_status_timestamp()
            self._set_program_state(
                self.PROGRAM_STATE_ACQUISITION, "acquisition_started"
            )

    @Slot()
    def ttm_activate_change_state(self):
        """
        activate or deactivate the TTM
        """

        if self.ui.checkBox_ttmActivate.isChecked():
            if self.ttm_remote_manager is None:
                ip = self.ui.label_ttm_IP.text()
                port = int(self.ui.lineEdit_ttmPort.text())

                self.ui.radioButton_ttm_remote.setEnabled(False)
                self.ui.radioButton_ttm_local.setEnabled(False)
                self.ui.lineEdit_ttmPort.setEnabled(False)
                self.ui.label_ttm_IP.setEnabled(False)

                if self.ui.radioButton_ttm_remote.isChecked():
                    logger.debug("self.ui.radioButton_ttm_local.isChecked()==True")
                    local_executable = ""
                else:
                    local_executable = self.ui.lineEdit_ttm_executable_path.text()
                    ip = "127.0.0.1"

                self.ttm_remote_manager = TtmRemoteManager(
                    ip, port, local_executable=local_executable
                )
        else:
            self.ui.radioButton_ttm_remote.setEnabled(True)
            self.ui.radioButton_ttm_local.setEnabled(True)
            self.ui.lineEdit_ttmPort.setEnabled(True)
            self.ui.label_ttm_IP.setEnabled(True)

            if self.ttm_remote_manager is not None:
                self.ttm_remote_manager.close()
                self.ttm_remote_manager = None

    def ttm_remote_is_up(self):
        """
        check if the TTM is up
        """
        logger.debug("check if ttm_remote_is_up")
        if self.ttm_remote_manager is not None:
            if self.ttm_remote_manager.is_ready():
                return True
        return False

    @Slot()
    def pushButton_uttm_start_clicked(self):
        logger.debug("pushButton_uttm_start")
        ip, port = self.ui.lineEdit_uttm_addr.text().split(":")
        self.ui.label_uttm_ip.setText(ip)
        url =  "http://"+self.ui.lineEdit_uttm_addr.text()
        data = {}
        try:
            r = requests.post(url+"/start", data=data)
            self.ui.textEdit_uttm_status.setText(json.dumps(r.json(), indent=4))
            if not self.ui.checkBox_uttm_watchdog.isChecked():
                self.ui.checkBox_uttm_watchdog.setChecked(True)
                self.checkBox_uttm_watchdog_clicked()
        except:
            logger.debug("Impossible to connect: " + url+"/start")

    @Slot()
    def pushButton_uttm_stop_clicked(self):
        logger.debug("pushButton_uttm_stop_clicked")
        ip, port = self.ui.lineEdit_uttm_addr.text().split(":")
        self.ui.label_uttm_ip.setText(ip)
        url =  "http://"+self.ui.lineEdit_uttm_addr.text()
        data = {}
        try:
            r = requests.post(url+"/stop", data=data)
            self.ui.textEdit_uttm_status.setText(json.dumps(r.json(), indent=4))
        except:
            logger.debug("Impossible to connect: " + url+"/stop")

    def sizeof_fmt(self, num, suffix="B"):
        #num = float(num)
        for unit in ["", "K", "M", "G", "T"]:
            if abs(num) < 1024.0:
                return f"{num:3.1f} {unit}{suffix}"
            num /= 1024.0
        return f"{num:.1f} P{suffix}"

    def pretty_html(self, data) -> str:
        uploader = data["uploader"]

        # Disk usage percentages
        total = data["disk_usage"][0]
        used = data["disk_usage"][1]
        free = data["disk_usage"][2]
        free_percent = free / total * 100 if total > 0 else 0
        used_percent = used / total * 100 if total > 0 else 0

        html = f"""
        <h2 style="color:#00aaff">📡 Acquisition Status</h2>
        <p><b>Acquisition running:</b> {data['acquisition_running']}</p>
        <p><b>Upload running:</b> {data['upload_running']}</p>
        <p><b>PID:</b> {data['pid']}</p>
        <p><b>Remote file:</b> {data['remote_filename']}</p>
        <p><b>Local file:</b> {data['local_filename']}</p>
        <p><b>Free RAM:</b> {self.sizeof_fmt(data['free_ram'])}</p>
        <p><b>File size:</b> {self.sizeof_fmt(data['file_size'])}</p>

        <h3 style="color:#ffaa00">💾 Disk usage</h3>
        <p><b>Total:</b> {self.sizeof_fmt(total)} | <b>Used:</b> {self.sizeof_fmt(used)} | <b>Free:</b> {self.sizeof_fmt(free)}</p>
        {self.progress_bar_html(used_percent, "#ff5555")}
        <p style="font-size:11px; color:#666;">Free space: {free_percent:.1f}%</p>

        <h3 style="color:#00cc66">🚀 Uploader</h3>
        <p><b>Bytes sent:</b> {self.sizeof_fmt(uploader['bytes_sent'])} / {self.sizeof_fmt(uploader['total_bytes'])}</p>
        {self.progress_bar_html(uploader['percent'], "#00cc66")}
        <p><b>Elapsed:</b> {uploader['elapsed']} s | <b>ETA:</b> {uploader['eta']} s</p>
        <p><b>Speed:</b> {self.sizeof_fmt(int(uploader['speed']))}/s</p>
        <p><b>Completed:</b> {"✅ Yes" if uploader['completed'] else "❌ No"}</p>
        """
        return html

    def progress_bar_html(self, percent: float, color="#00cc66") -> str:
        """Return a simple HTML progress bar"""
        return f"""
        <div style="border:1px solid #ccc; width:100%; height:18px; border-radius:4px; background:#f0f0f0;">
          <div style="width:{percent:.1f}%; height:100%; background:{color}; border-radius:4px;"></div>
        </div>
        <p style="font-size:11px; color:#555;">{percent:.1f}%</p>
        """

    @Slot()
    def pushButton_uttm_status_clicked(self):
        logger.debug("pushButton_uttm_status")

        ip, port = self.ui.lineEdit_uttm_addr.text().split(":")
        self.ui.label_uttm_ip.setText(ip)
        url =  "http://"+self.ui.lineEdit_uttm_addr.text()

        try:
            r = requests.get(url+"/status", timeout=0.5)

            data = r.json()
            try:
                self.ui.textEdit_uttm_status.setHtml(self.pretty_html(data))
            except:
                self.ui.textEdit_uttm_status.setText(json.dumps(r.json(), indent=4))
        except:
            self.timerUttmWatchDog = None
            logger.debug("%s %s", "Failed ", url+"/status")
            self.ui.checkBox_uttm_watchdog.setChecked(False)

        try:
            r = requests.get(url+"/log_last", timeout=0.5)
            #print(r.text)
            self.ui.textEdit_uttm_log.setText(r.text)
        except:
            self.timerUttmWatchDog = None
            logger.debug("%s %s", "Failed ", url + "/log_last")
            self.ui.checkBox_uttm_watchdog.setChecked(False)

    def pushButton_uttm_test_clicked(self):
        logger.debug("pushButton_uttm_test_clicked")

    def pushButton_uttm_check_laser_clicked(self):
        logger.debug("pushButton_uttm_check_laser_clicked")

        ip, port = self.ui.lineEdit_uttm_addr.text().split(":")
        self.ui.label_uttm_ip.setText(ip)
        url = "http://" + self.ui.lineEdit_uttm_addr.text()

        self.uttm_laser_widget = pg.PlotWidget(self)
        #self.uttm_laser_widget.setToolTip("Double-click for reset the trace")
        self.uttm_laser_widget.setLabel("left", "count", "")
        self.uttm_laser_widget.setLabel("bottom", "Time", "s")
        self.ui.gridLayout_uttm_preview.addWidget(self.uttm_laser_widget, 0, 0)
        self.uttm_laser_widget.show()
        self.uttm_laser_widget.setDownsampling(1, True, "mean")
        self.uttm_laser_widget.setMinimumSize(100, 130)
        try:
            r = requests.get(url + "/show_preview", timeout=1.1)
            j = r.json()
            #self.ui.textEdit_uttm_status.setText(json.dumps(j, indent=4))
        except:
            logger.debug("%s %s", "Failed ", url + "/show_preview")

        self.ui.label_uttm_laser_freq.setText("Laser freq. found: %s MHz" % j["laser_frequency"])

        x=[]
        y=[]
        for i in j["histogram"]:
            x_pos = i["end"]
            if isinstance(x_pos, (int, float, complex)):
                x.append(x_pos)
            else:
                x.append(2*x[-1]-x[-2])
            y.append(i["count"])

        self.uttm_laser_widget.plot(np.asarray(x)*1.0e-12, np.asarray(y), clear=True)

    @Slot()
    def checkBox_uttm_watchdog_clicked(self):
        logger.debug("checkBox_uttm_watchdog_clicked")
        if self.ui.checkBox_uttm_watchdog.isChecked():
            self.timerUttmWatchDog = QTimer(None)
            self.timerUttmWatchDog_mutex = QMutex()
            self.timerUttmWatchDog.timeout.connect(self.uttm_watchdog_trigger)
            self.timerUttmWatchDog.setInterval(1500)
            self.timerUttmWatchDog.start()
        else:
            if self.timerUttmWatchDog is not None:
                self.timerUttmWatchDog.stop()
            self.timerUttmWatchDog = None

    def uttm_watchdog_trigger(self):
        self.timerUttmWatchDog_mutex.lock()
        self.pushButton_uttm_status_clicked()
        self.timerUttmWatchDog_mutex.unlock()

    @Slot()
    def checkAlerts(self):
        """
        check the GUI alerts i.e. potential wrong parameters
        """
        logger.debug("checkAlerts")

        current_plot_size_x_um = self.ui.spinBox_range_x.value()
        current_plot_size_y_um = self.ui.spinBox_range_y.value()
        current_plot_size_z_um = self.ui.spinBox_range_z.value()

        current_number_px_x = self.ui.spinBox_nx.value()
        current_number_px_y = self.ui.spinBox_ny.value()
        current_number_px_z = self.ui.spinBox_nframe.value()

        self.ui.spinBox_range_x.setStyleSheet("")
        self.ui.spinBox_range_y.setStyleSheet("")
        self.ui.spinBox_range_z.setStyleSheet("")

        self.ui.spinBox_nx.setStyleSheet("")
        self.ui.spinBox_ny.setStyleSheet("")
        self.ui.spinBox_nframe.setStyleSheet("")

        self.ui.comboBox_view_projection.setStyleSheet("")
        self.ui.comboBox_view_projection.setStyleSheet("")
        self.ui.comboBox_view_projection.setStyleSheet("")

        self.ui.comboBox_plot_channel.setStyleSheet("")
        self.ui.checkBox_fifo_analog.setStyleSheet("")
        self.ui.checkBox_fifo_digital.setStyleSheet("")

        # x
        if ((current_plot_size_x_um == 0.0) and (current_number_px_x > 1)) or (
                (current_plot_size_x_um > 0.0) and (current_number_px_x == 1)
        ):
            self.ui.spinBox_range_x.setStyleSheet("border: 1px solid red;")
            self.ui.spinBox_nx.setStyleSheet("border: 1px solid red;")
        # y
        if ((current_plot_size_y_um == 0.0) and (current_number_px_y > 1)) or (
                (current_plot_size_y_um > 0.0) and (current_number_px_y == 1)
        ):
            self.ui.spinBox_range_y.setStyleSheet("border: 1px solid red;")
            self.ui.spinBox_ny.setStyleSheet("border: 1px solid red;")
        # z
        if ((current_plot_size_z_um == 0.0) and (current_number_px_z > 1)) or (
                (current_plot_size_z_um > 0.0) and (current_number_px_z == 1)
        ):
            self.ui.spinBox_range_z.setStyleSheet("border: 1px solid red;")
            self.ui.spinBox_nframe.setStyleSheet("border: 1px solid red;")

        # x
        if (self.ui.comboBox_view_projection.currentText().find("x") != -1) and (
                current_number_px_x == 1
        ):
            self.ui.comboBox_view_projection.setStyleSheet("border: 1px solid red;")
            self.ui.spinBox_nx.setStyleSheet("border: 1px solid red;")
        # y
        if (self.ui.comboBox_view_projection.currentText().find("y") != -1) and (
                current_number_px_y == 1
        ):
            self.ui.comboBox_view_projection.setStyleSheet("border: 1px solid red;")
            self.ui.spinBox_nx.setStyleSheet("border: 1px solid red;")
        # z
        if (self.ui.comboBox_view_projection.currentText().find("z") != -1) and (
                current_number_px_z == 1
        ):
            self.ui.comboBox_view_projection.setStyleSheet("border: 1px solid red;")
            self.ui.spinBox_nframe.setStyleSheet("border: 1px solid red;")

        if "analog" in (self.ui.comboBox_plot_channel.currentText().lower()) and (
                not self.ui.checkBox_fifo_analog.isChecked()
        ):
            self.ui.comboBox_plot_channel.setStyleSheet("border: 1px solid red;")
            self.ui.checkBox_fifo_analog.setStyleSheet("border: 1px solid red;")

        if not ("analog" in (self.ui.comboBox_plot_channel.currentText().lower())) and (
                not self.ui.checkBox_fifo_digital.isChecked()
        ):
            self.ui.comboBox_plot_channel.setStyleSheet("border: 1px solid red;")
            self.ui.checkBox_fifo_digital.setStyleSheet("border: 1px solid red;")



    @Slot()
    def previewLoop(self):
        """
        Start acquisition in preview mode (limited repetitions, no saving).
        This is now a wrapper around beginAcquisition for backward compatibility.
        """
        logger.debug("previewLoop() - starting preview acquisition")
        self.beginAcquisition(is_preview=True)

    @Slot()
    def projChanged(self):
        logger.debug("projChanged()")
        self.plotPreviewImage()

        logger.debug("self.im_widget.autoRange()")
        self.im_widget.autoRange()

        self.drawMarkers()
        self.checkAlerts()

        proj = self.ui.comboBox_view_projection.currentText()
        if len(proj) == 2:
            self.im_widget_plot_item.setLabel("bottom", "%s (um)" % proj[0])
            self.im_widget_plot_item.setLabel("left", "%s (um)" % proj[1])

    def finalizeAcquisition(self):
        """
        finalize the acquisition: save the data, add metadata, etc.
        """

        # self.rect_roi.show()
        logger.debug("finalizeAcquisition")

        if self.started_normal:

            if self.ui.checkBox_uttmActivate.isChecked() and \
            self.ui.checkBox_uttm_auto.isChecked():
                    self.pushButton_uttm_stop_clicked()

            logger.debug(self.mcs_manager.shared_dict)
            self.last_saved_filename = self.mcs_manager.shared_dict["filenameh5"]
            self.last_completed_filename = self.last_saved_filename
            self.completed_acquisition_count += 1
            self.last_acquisition_completed_at = self._make_status_timestamp()

            h5mgr = H5Manager(self.last_saved_filename, new_file=self.raw_stream_mode)

            comment = self.ui.lineEdit_comment.toPlainText()
            self.ui.lineEdit_comment.setText("")
            self.ui.listWidget.addItem(self.last_saved_filename + "   " + comment)
            logger.debug("saveHDF()")

            h5mgr.metadata_add_initial(comment)

            h5mgr.metadata_add_dict(
                "configurationSpadFCSmanager",
                self.mcs_manager.registers_configuration,
                legacy_name_map=LEGACY_H5_REGISTER_NAME_MAP,
            )

            h5mgr.metadata_add_dict(
                "configurationFPGA",
                self.configurationFPGA_dict,
                legacy_name_map=LEGACY_H5_REGISTER_NAME_MAP,
            )

            h5mgr.metadata_add_dict(
                "configurationGUI",
                self._gui_config_for_h5(self.getGUI_data()),
            )

            h5mgr.metadata_add_dict(
                "configurationGUI_beforeStart",
                self._gui_config_for_h5(self.configurationGUI_dict_beforeStart),
            )

            if self.raw_stream_mode:
                raw_stream_metadata = legacy_raw_stream_metadata(
                    self.mcs_manager,
                    spad_channels=self.spad_channels,
                    clock_base_mhz=self.clock_base,
                    raw_files=self.raw_stream_output_files,
                    include_pi23=detector_uses_pi23_pipeline(
                        self.mcs_manager.detector_model
                    ),
                )
                h5mgr.metadata_add_dict(
                    "rawStreamAcquisition",
                    raw_stream_metadata,
                )
            else:
                h5mgr.metadata_add_thumbnail(self.im_widget.imageItem)
            h5mgr.print_keys()

            logger.debug("%s %s", "currentImage_size", self.currentImage_size)
            logger.debug("%s %s", "currentImage_pos", self.currentImage_pos)
            logger.debug("%s %s", "currentImage_pixels", self.currentImage_pixels)

            self._pending_program_state_after_stop = (
                self.PROGRAM_STATE_ACQUISITION_DONE
            )
            self.stop()

            if self.started_normal and not self.raw_stream_mode:
                self.finalizeImage()

            h5mgr.close()
            self._publish_filename_to_console(self.last_saved_filename)

            if self.ttm_remote_is_up():
                self.ttm_remote_manager.wait_ttm_filename(self.ui.listWidget.addItem)

            self.ui.pushButton_externalProgram.setEnabled(True)
            self.plugin_signals.signal.emit(
                "acquisitionDone %s" % self.last_saved_filename
            )

    @staticmethod
    def _gui_config_for_h5(configuration):
        """
        Write GUI metadata with the legacy public H5 keys.

        Python-side names now distinguish SPAD-specific settings from the MCS
        manager, but existing H5 readers expect these original attribute names.
        """
        return legacy_gui_metadata(configuration, spad_array_model=DETECTOR_SPAD_ARRAY)

    @Slot()
    def cmd_filename_ttm(self):
        """
        call the dialog for setting the filename for the TTM data receiver
        """
        dialog = QFileDialog(self)
        dialog.setFileMode(QFileDialog.Directory)
        if dialog.exec_():
            self.ui.lineEdit_destinationfolder.setText(dialog.selectedFiles()[0])
            self.ui.lineEdit_ttm_filename.setText(dialog.selectedFiles()[0])

    def analog_before_stop(self):
        """
        set the analog output to 0V before stopping the acquisition
        """
        logger.debug("analog_before_stop()")

        mydict = {}
        for ch in range(0, 8):
            if self.ui.checkBox_AnalogOut[ch].isChecked() == True:
                logger.debug("analog_output_%d_dc_volts set to 0V as requested" % ch)
                mydict["analog_output_%d_dc_volts" % ch] = 0

        self.setRegistersDict(mydict)
        # time.sleep(0.2)

    def stopAcquisition(self):
        """
        stop the acquisition
        """
        logger.debug("stopAcquisition")
        # Do not infer this from the hardware connection: every acquisition
        # connects automatically.  Only an explicit click on Keep FPGA On
        # should preserve the session after a manual or natural stop.
        keep_fpga_loaded = bool(
            getattr(
                self,
                "_keep_fpga_on_requested",
                self.ui.pushButton_fpga_connection_cmd.isChecked(),
            )
        )
        reset_error = None
        try:
            self.mcs_manager.quick_reset_fpga(
                timeout=self.FPGA_IDLE_TIMEOUT_SECONDS
            )
        except Exception as error:
            reset_error = error
        finally:
            self.mcs_manager.stopPreview()
            self.timerPreviewImg.stop()
            logger.debug("self.timerPreviewImg.stop()")
            if not keep_fpga_loaded:
                self.mcs_manager.stopFPGA()
            self.mcs_manager.stopAcquisition(
                keep_fpga_loaded=keep_fpga_loaded and reset_error is None
            )
            self.mcs_manager.stopPreview()
            self._update_fpga_connection_button()

        if reset_error is not None:
            if keep_fpga_loaded:
                self.mcs_manager.stopFPGA()
            raise reset_error

    @Slot()
    def stop(self):
        """
        stop the acquisition clicked event
        """
        self.analog_before_stop()
        logger.debug("GUI.Stop")

        if self.ttm_remote_is_up() and not self.do_not_save:
            self.ttm_remote_manager.stop_ttm_recv()

        if self.started_preview:
            # self.ui.spinBox_nframe.setValue(self.nframe_before_run_preview)
            # self.ui.spinBox_nframe.setEnabled(1)

            old_lock = self.lockspatialSettingsChanged
            self.lockspatialSettingsChanged = True
            self.ui.spinBox_nrepetition.setValue(self.nrepetition_before_run_preview)
            self.ui.spinBox_nx.setEnabled(1)
            self.ui.spinBox_ny.setEnabled(1)
            self.ui.spinBox_nframe.setEnabled(1)
            self.ui.spinBox_nrepetition.setEnabled(1)
            self.lockspatialSettingsChanged = old_lock

        # self.rect_roi.show()
        self.ui.pushButton_previewStart.setEnabled(True)
        self.ui.pushButton_acquisitionStart.setEnabled(True)
        self.ui.pushButton_stop.setEnabled(False)
        self.ui.pushButton_fpga_connection_cmd.setEnabled(True)

        self.ui.checkBox_fifo_digital.setEnabled(True)
        self.ui.checkBox_fifo_analog.setEnabled(True)
        self.ui.checkBox_DFD.setEnabled(True)
        self.ui.checkBox_uttmActivate.setEnabled(True)
        self.ui.checkBox_ttmActivate.setEnabled(True)

        self.stopAcquisition()

        # self.timerPreviewImg.stop()
        self.update()
        self.repaint()

        self.started_normal = False
        self.started_preview = False
        self.raw_stream_mode = False
        next_state = self._pending_program_state_after_stop
        self._pending_program_state_after_stop = None

        if next_state is None:
            self._set_program_state(self.PROGRAM_STATE_IDLE, "stopped")
        else:
            self._set_program_state(next_state, "acquisition_completed")

    # @Slot()
    # def connectCmd(self):
    #     debug("Connect FPGA")
    #     self.connectFPGA()

    # @Slot()
    # def Connect(self):
    #     self.connectFPGA()

    def sendCmdRun(self):
        """
        send the run command to the FPGA
        """
        if self.ui.pushButton_fpga_connection_cmd.isChecked():
            # A reused VI needs a fresh edge for every acquisition.
            self.setRegistersDict({"stop_command": False, "start_command": True})
            self.setRegistersDict({"start_command": False})
        else:
            # Preserve the normal firmware protocol: Run remains asserted until
            # the acquisition is stopped and the FPGA session is closed.
            self.setRegistersDict({"stop_command": False, "start_command": False})
            self.setRegistersDict({"start_command": True})

    def sendCmdStop(self):
        """
        send the stop command to the FPGA
        """
        self.setRegistersDict({"stop_command": False})
        self.setRegistersDict({"stop_command": True})

    def getPreviewImage(self, projection="xy", rgb=False):
        """
        get the preview image
        """
        return self.preview_controller.image(
            self.mcs_manager, self.currentImage, projection, rgb
        )

    def getPreviewFlatData(self):
        """
        get the preview flat data
        """
        return self.preview_controller.flat_data(self.mcs_manager, self.activeFile)

    # def calculateAutoCorrelation(self, temporaldata):
    #     mu = np.mean(temporaldata)
    #     if mu != 0:
    #         result = signal.fftconvolve(temporaldata, temporaldata[::-1])
    #         return result[result.size // 2 :] / (mu**2) - 1
    #     else:
    #         return np.zeros(2)

    def getCurrentPreviewImage(self, preview_img=None):
        """
        get the current preview image
        """
        # print("plotPreviewImage")
        # print("self.autoscale_image", self.autoscale_image)
        proj = self.ui.comboBox_view_projection.currentText()
        ch = self.ui.comboBox_plot_channel.currentText()
        if preview_img is None:
            if self.isLifetimeColorChannel(ch) or ch in ("LIFETIME", "QUALITY"):
                preview_hcl = self.mcs_manager.getPreviewHclImage()
                if self.isLifetimeColorChannel(ch):
                    preview_img = preview_hcl
                elif ch == "LIFETIME":
                    preview_img = preview_hcl[:, :, 0]
                else:
                    preview_img = preview_hcl[:, :, 1]
                if ch in ("LIFETIME", "QUALITY"):
                    proj = "xy"
            elif ch.startswith("RGB"):
                preview_img = self.getPreviewImage(proj, rgb=True)
            else:
                preview_img = self.getPreviewImage(proj)
        else:
            preview_img = np.asarray(preview_img)

        currentImage_size = self.currentImage_size
        currentImage_pos  = self.currentImage_pos
        currentImage_pixels = self.currentImage_pixels

        if currentImage_size[0] == 0.:
            currentImage_size[0] = 1e-12
        if currentImage_size[1] == 0.:
            currentImage_size[1] = 1e-12
        if currentImage_size[2] == 0.:
            currentImage_size[2] = 1e-12


        if ch.startswith("RGB") or self.isLifetimeColorChannel(ch):
            preview_img = np.moveaxis(preview_img, 0, 1)
            autoLevels = self.autoscale_image
            autoRange = False
            pos = (
                currentImage_pos[0] - currentImage_size[0] / 2.0,
                currentImage_pos[1] - currentImage_size[1] / 2.0,
            )
            scale = (
                currentImage_size[0] / currentImage_pixels[0],
                currentImage_size[1] / currentImage_pixels[1],
            )

        elif proj == "xy":
            preview_img = preview_img.T
            autoLevels = self.autoscale_image
            autoRange = False
            pos = (
                currentImage_pos[0] - currentImage_size[0] / 2.0,
                currentImage_pos[1] - currentImage_size[1] / 2.0,
            )
            scale = (
                currentImage_size[0] / currentImage_pixels[0],
                currentImage_size[1] / currentImage_pixels[1],
            )

        elif proj == "yx":
            autoLevels = self.autoscale_image
            autoRange = False
            pos = (
                currentImage_pos[1] - currentImage_size[1] / 2.0,
                currentImage_pos[0] - currentImage_size[0] / 2.0,
            )
            scale = (
                currentImage_size[1] / currentImage_pixels[1],
                currentImage_size[0] / currentImage_pixels[0],
            )

        elif proj == "zy":
            preview_img = preview_img.T
            autoLevels = self.autoscale_image
            autoRange = False
            pos = (
                currentImage_pos[2] - currentImage_size[2] / 2.0,
                currentImage_pos[1] - currentImage_size[1] / 2.0,
            )
            scale = (
                currentImage_size[2] / currentImage_pixels[2],
                currentImage_size[1] / currentImage_pixels[1],
            )

        elif proj == "yz":
            autoLevels = self.autoscale_image
            autoRange = False
            pos = (
                currentImage_pos[1] - currentImage_size[1] / 2.0,
                currentImage_pos[2] - currentImage_size[2] / 2.0,
            )
            scale = (
                currentImage_size[1] / currentImage_pixels[1],
                currentImage_size[2] / currentImage_pixels[2],
            )

        elif proj == "zx":
            autoLevels = self.autoscale_image
            autoRange = False
            pos = (
                currentImage_pos[2] - currentImage_size[2] / 2.0,
                currentImage_pos[0] - currentImage_size[0] / 2.0,
            )
            scale = (
                currentImage_size[2] / currentImage_pixels[2],
                currentImage_size[0] / currentImage_pixels[0],
            )

        elif proj == "xz":
            preview_img = preview_img.T
            autoLevels = self.autoscale_image
            autoRange = False
            pos = (
                currentImage_pos[0] - currentImage_size[0] / 2.0,
                currentImage_pos[2] - currentImage_size[2] / 2.0,
            )
            scale = (
                currentImage_size[0] / currentImage_pixels[0],
                currentImage_size[2] / currentImage_pixels[2],
            )

        else:  #
            logger.debug("NOT IMPLEMENTED BOH!!")
            return

        return (preview_img,
                ch,
                autoLevels,
                autoRange,
                pos,
                scale)

    def plotPreviewImage(self, img=None):
        """
        plot the preview image
        """
        # Keep projection-specific transforms in the GUI layer so the worker can
        # publish compact shared buffers without duplicating display logic.
        (preview_img,
         ch,
         autoLevels,
         autoRange,
         pos,
         scale) = self.getCurrentPreviewImage(img)
        #debug("preview_img",preview_img)
        if self.isLifetimeColorChannel(ch):
            preview_hcl = preview_img
            tcycle_ns = 1e3 / (
                max(float(self.dfd_cycle_mhz), 1e-12)
                * max(int(self.mcs_manager.clk_multiplier), 1)
            )
            self.updateColorLifetimeShiftControls()
            h_shift = 0.0
            if tcycle_ns > 0.0:
                h_shift = (
                    self.ui.doubleSpinBox_delta_tau_ns.value() % tcycle_ns
                ) / tcycle_ns
            self.im_widget.setFlimImage(
                preview_hcl,
                valid=preview_hcl[:, :, 2],
                h_display_max=tcycle_ns,
                h_shift=h_shift,
                render_mode=self.getLifetimeColorRenderMode(ch),
                hue_display_range=self.getLifetimeHueDisplayRange(),
                force_quality_full=self.getLifetimeForceQualityFull(),
                autoLevels=autoLevels,
                autoRange=autoRange,
                pos=pos,
                scale=scale,
            )
        elif ch.startswith("RGB"):
            print(preview_img.shape)
            self.im_widget.setImage(
                preview_img,
                levelMode="rgba",
                autoLevels=autoLevels,
                autoRange=autoRange,
                pos=pos,
                scale=scale,
            )
        elif ch.startswith("Analog"):
            self.im_widget.setImage(
                preview_img,
                autoLevels=autoLevels,
                levelMode="mono",
                autoRange=autoRange,
                pos=pos,
                scale=scale,
            )
        else:
            self.im_widget.setImage(
                preview_img,
                autoLevels=autoLevels,
                levelMode="mono",
                autoRange=autoRange,
                pos=pos,
                scale=scale,
            )
    def plotCurrentImage(self):
        """
        plot the current image
        """
        logger.debug(self.currentImage.shape)
        logger.debug("Calculating sum")
        img = np.sum(
            self.currentImage, axis=(0, 1, 4)
        )  # sum over bin, repetition, and frame
        logger.debug(img.shape)
        if isinstance(self.selected_channel, int):
            self.im_widget.setImage(
                np.moveaxis(img[:, :, self.selected_channel], [0, -1], [-1, 0]),
                autoLevels=self.autoscale_image,
                pos=(
                    self.ui.spinBox_off_x_um.value()
                    - self.ui.spinBox_range_x.value() / 2.0,
                    self.ui.spinBox_off_y_um.value()
                    - self.ui.spinBox_range_y.value() / 2.0,
                ),
                scale=(
                    self.ui.spinBox_range_x.value() / self.ui.spinBox_nx.value(),
                    self.ui.spinBox_range_y.value() / self.ui.spinBox_ny.value(),
                ),
            )
            logger.debug("%s %s %s", "Total photon [%d]", self.selected_channel, img[:, :, self.selected_channel].sum())
        elif self.selected_channel == "Sum":
            self.im_widget.setImage(
                np.moveaxis(img[:, :, :].sum(axis=-1), [0, -1], [-1, 0]),
                autoLevels=self.autoscale_image,
                pos=(
                    self.ui.spinBox_off_x_um.value()
                    - self.ui.spinBox_range_x.value() / 2.0,
                    self.ui.spinBox_off_y_um.value()
                    - self.ui.spinBox_range_y.value() / 2.0,
                ),
                scale=(
                    self.ui.spinBox_range_x.value() / self.ui.spinBox_nx.value(),
                    self.ui.spinBox_range_y.value() / self.ui.spinBox_ny.value(),
                ),
            )
            logger.debug("%s %s %s", "Total photon [sum]", self.selected_channel, img[:].sum())

    @Slot()
    def selectChannelSum(self):
        """
        select the sum channel
        """
        self.setSelectedChannel(-1)
        # self.plotCurrentImage()

    # @Slot()
    # def selectISM(self):
    #     self.setSelectedChannel(-2)
    #     # self.plotCurrentImage()

    @Slot()
    def SaveConfigurationCmd(self):
        """
        save the configuration clicked event
        """
        save_options = self._show_save_configuration_menu()
        if save_options is None:
            return

        if not save_options["save_gui"]:
            self.SavePluginConfiguration()
            return

        self.SaveConfiguration(
            preserve_default_fov=save_options["preserve_default_fov"],
            save_plugins=save_options["save_plugins"],
            plugin_names=list(self.plugin_configuration_files),
            make_permanent=save_options["make_permanent"],
        )

    def _show_save_configuration_menu(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Save Configuration")

        layout = QVBoxLayout(dialog)

        save_gui = QCheckBox("Saving GUI configuration", dialog)
        save_gui.setChecked(True)
        layout.addWidget(save_gui)

        preserve_default_fov = QCheckBox("Preserving default FOV", dialog)
        preserve_default_fov.setChecked(True)
        layout.addWidget(preserve_default_fov)

        save_plugins = QCheckBox("Configuration of plugins", dialog)
        save_plugins.setChecked(True)
        layout.addWidget(save_plugins)

        make_permanent = QCheckBox("Make it permanent default configuration", dialog)
        make_permanent.setChecked(True)
        layout.addWidget(make_permanent)

        only_plugins_label = QLabel("ONLY plugins configuration will be saved", dialog)
        only_plugins_label.setWordWrap(True)
        layout.addWidget(only_plugins_label)

        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            dialog,
        )
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        def update_enabled_options():
            gui_enabled = save_gui.isChecked()
            preserve_default_fov.setEnabled(gui_enabled)
            save_plugins.setEnabled(gui_enabled)
            make_permanent.setEnabled(gui_enabled)
            only_plugins_label.setVisible(not gui_enabled)
            if not gui_enabled:
                save_plugins.setChecked(True)

        save_gui.toggled.connect(lambda _checked: update_enabled_options())
        update_enabled_options()

        if dialog.exec() != QDialog.Accepted:
            return None

        return {
            "save_gui": save_gui.isChecked(),
            "preserve_default_fov": preserve_default_fov.isChecked(),
            "save_plugins": save_plugins.isChecked(),
            "make_permanent": make_permanent.isChecked(),
        }

    def _preserved_default_fov_keys(self):
        return [
            "default_offset_x_um",
            "default_offset_y_um",
            "default_offset_z_um",
            "default_range_x",
            "default_range_y",
            "default_range_z",
        ]

    def _load_cfg_payload_if_exists(self, filecfg):
        if not filecfg or not os.path.exists(filecfg):
            return {}
        try:
            return LegacyConfigurationCodec.load(filecfg)
        except Exception as error:
            logger.debug("%s %s %s", "Unable to read existing cfg for preservation", filecfg, repr(error))
            return {}

    def _preserve_default_fov_settings(self, configuration, filecfg):
        previous_configuration = self._load_cfg_payload_if_exists(filecfg)
        if not previous_configuration:
            return configuration

        for key in self._preserved_default_fov_keys():
            if key in previous_configuration:
                configuration[key] = previous_configuration[key]
        return configuration

    @Slot()
    def SaveConfiguration(
        self,
        preserve_default_fov=False,
        save_plugins=False,
        plugin_names=None,
        make_permanent=None,
    ):
        """
        save the configuration to a .cfg file
        """
        filecfg = QFileDialog().getSaveFileName(
            caption="Save Configuration",
            filter="Config File (*.cfg)",
            dir=self.ui.lineEdit_configurationfile.text(),
        )[0]
        if filecfg != "":
            if save_plugins:
                self._save_plugin_configuration_files(plugin_names)

            configuration = self.configuration_controller.merge_for_save(
                getattr(self, "_loaded_configuration_payload", {}),
                self.getGUI_data(),
            )
            if preserve_default_fov:
                configuration = self._preserve_default_fov_settings(
                    configuration,
                    filecfg,
                )

            text = LegacyConfigurationCodec.dumps(
                configuration, encoder=NumpyJSONEncoder
            )
            logger.debug(text)

            self.configuration_controller.save(
                filecfg, configuration, encoder=NumpyJSONEncoder
            )
            self.ui.statusBar.showMessage("%s saved." % filecfg, 5000)

            current_folder = QDir.fromNativeSeparators(os.getcwd()) + "/"

            logger.debug(filecfg)
            logger.debug(current_folder)

            filecfg_nicer = filecfg.replace(current_folder, "")
            self.ui.lineEdit_configurationfile.setText(filecfg_nicer)

            if make_permanent is True:
                self.setNewDefaultCfg(filecfg_nicer)
            elif make_permanent is None:
                self.ask_to_save_cfg_as_permanent(filecfg_nicer)

    @Slot()
    def LoadConfigurationCmd(self):
        """
        load the configuration clicked event
        """
        self.LoadConfiguration()

    @Slot()
    def LoadConfiguration(self, filecfg=""):
        """
        load the configuration from a .cfg file
        """
        filecfg = filecfg.strip()
        logger.debug("%s %s %s", "Load_Configuration'", filecfg, "'")

        if filecfg == "":
            filecfg = QFileDialog.getOpenFileName(
                self,
                caption="Save Configuration",
                filter="Config File (*.cfg)",
                dir=self.ui.lineEdit_configurationfile.text(),
            )[0]

            current_folder = QDir.fromNativeSeparators(os.getcwd()) + "/"
            logger.debug(filecfg)
            logger.debug(current_folder)

            file_cfg_nicer = filecfg.replace(current_folder, "")

            if file_cfg_nicer.strip() != "":
                self.ask_to_save_cfg_as_permanent(file_cfg_nicer)

        if filecfg != "":
            logger.debug("%s %s", "filecfg", filecfg)
            mydict, _typed_configuration = self.configuration_controller.load(filecfg)
            if mydict:
                mydict = dict(mydict)
                mydict.pop("load_firmware_once", None)
                mydict.pop("keep_fpga_connected", None)
                self._loaded_configuration_payload = dict(mydict)
                logger.debug(mydict)
                l1 = self.lock_parameters_changed_call
                l2 = self.lock_range_changing

                self.lock_parameters_changed_call = True
                self.lock_range_changing = True

                self._loading_configuration_file = filecfg
                self.setGUI_data(mydict)
                self._loading_configuration_file = ""
                self._load_startup_plugins()

                self.lock_parameters_changed_call = l1
                self.lock_range_changing = l2

                self.updatePixelValueChanged()

                self.ui.statusBar.showMessage(
                    "%s opened and GUI configuration updated." % filecfg, 5000
                )
                self.ui.label_loadedcfg.setText(filecfg)

    @Slot()
    def openInExplorer(self):
        folder_path = os.path.abspath((self.ui.lineEdit_destinationfolder.text().replace("/","\\")))
        logger.debug(folder_path)
        url = QUrl.fromLocalFile(folder_path)
        QDesktopServices.openUrl(url)

    def script_plot_fingerprint(self, fingerprint):
        """
        plot the fingerprint, handle for scripts
        """
        self.fingerprint_widget.setImage(fingerprint.T)

    def script_plot_shiftvector(self, sv=None):
        """
        plot the shift vector, handle for scripts
        """
        if sv is not None:
            if hasattr(self, "panorama_marker_text"):
                for i in self.panorama_marker_text:
                    self.im_plugin_plot_item.removeItem(i)
            self.panorama_marker_text = []

            if hasattr(self, "panorama_marker"):
                self.panorama_marker.clear()
            self.panorama_marker = pg.ScatterPlotItem()

            self.im_plugin_plot_item.addItem(self.panorama_marker)

            for n, (x, y) in enumerate(sv.tolist()):
                self.panorama_marker.addPoints(
                    x=[
                        x,
                    ],
                    y=[
                        y,
                    ],
                    pen="w",
                    brush="w",
                    size=3,
                    symbol="o",
                )
                self.panorama_marker_text.append(pg.TextItem("%d" % n))
                self.im_plugin_plot_item.addItem(self.panorama_marker_text[-1])
                self.panorama_marker_text[-1].setPos(x * 1.0, y * 1.0)
                print("%d\t%f\t%f" % (n, x, y))
            self.ui.dockWidget_pluginImage.raise_()
        else:
            if hasattr(self, "panorama_marker_text"):
                for i in self.panorama_marker_text:
                    self.im_plugin_plot_item.removeItem(i)
            self.panorama_marker_text = []

            if hasattr(self, "panorama_marker"):
                self.panorama_marker.clear()
