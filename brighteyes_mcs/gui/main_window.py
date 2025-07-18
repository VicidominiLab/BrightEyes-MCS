"""main_window.py: BrightEyes-MCS - MainWindow."""
__author__ = "Mattia Donato"
__copyright__ = "Copyright (C) 2023, Istituto Italiano di Tecnologia"
__license__ = "GPL"
__version__ = "0.0.1"
__email__ = ["mattia.donato@iit.it", "giuseppe.vicidomini@iit.it"]

# pyside6-uic main_design.ui -o main_design.py

from PySide6.QtWidgets import QMainWindow, QSplashScreen, QFileDialog
from PySide6.QtWidgets import QMessageBox, QTableWidgetItem, QLabel
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QComboBox,
    QCheckBox,
    QWidget,
    QTextBrowser,
)
from PySide6.QtGui import QScreen  # Replaces QDesktopWidget

from PySide6.QtCore import (
    Slot,
    Signal,
    QTimer,
    Qt,
    QDir,
    QFile,
    QCoreApplication,
    QTime,
    QIODevice,
    QBuffer
)
from PySide6.QtCore import QEvent, QRectF, QObject, QThread, QMutex, QMimeData, QUrl
from PySide6.QtGui import QPixmap, QIcon, QGuiApplication, QDesktopServices

from datetime import datetime

from .main_window_design import Ui_MainWindowDesign

from ..gui.console_widget import ConsoleWidget
from ..libs.spad_fcs_manager import SpadFcsManager
from ..libs.table_manager import TableManager

from ..libs.print_dec import print_dec
from .dict_to_tree import TreeModel
from ..libs.ttm import TtmRemoteManager
from ..libs.plugin_loader import PluginsManager
from ..gui.dfd_widget import DfdWidget
from ..libs.restapi import FastAPIServerThread

import numpy as np
import time

import psutil

import json
import h5py
from ..libs.h5manager import H5Manager

import os, sys

import socket

import pyqtgraph as pg

try:
    import imageio as iio
except:
    print(
        "Warning: 'import imageio' failed. \n"
        + "This function is optional so the software will run but some functions  not work.\n"
    )

try:
    import napari
except:
    print(
        "Warning: 'import napari' failed. \n"
        + "This function is optional so the software will run but some functions  not work.\n"
    )

# ================== end of imports ====================================

pg.setConfigOption("background", "k")
pg.setConfigOption("foreground", "w")

class RectROI_noHandle(pg.RectROI):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Remove existing handles
        for h in self.getHandles():
            self.removeHandle(h)

class PluginSignals(QObject):
    """
    Class for defining custom signals for the plugins
    """
    signal = Signal(str)


class MainWindow(QMainWindow):
    """
    Main window class for the BrightEyes-MCS application.

    Attributes:
        http_server_thread (FastAPIServerThread): Thread for the HTTP server.
        guiReadyFlag (bool): Flag indicating if the GUI is ready.
        init_ready (bool): Flag indicating if the initialization is ready.
        splash (QSplashScreen): Splash screen for the application.
    """

    def __init__(self, args=None):
        self.http_server_thread = None
        self.guiReadyFlag = False
        self.init_ready = False
        primary_screen = QGuiApplication.primaryScreen()
        splash_image = QPixmap("images/splash.png").scaled(
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

        qp = QPixmap("images/icon.png")
        appIcon = QIcon(qp)
        self.setWindowIcon(appIcon)

        self.preset_dict = {}

        self.CHANNELS = 25
        self.CHANNELS_x = 5
        self.CHANNELS_y = 5
        self.started_preview = False
        self.started_normal = False
        self.console_widget = None
        self.selected_channel = None
        self.webcam_capture = None
        self.ui = Ui_MainWindowDesign()
        self.ui.setupUi(self)

        self.configuration_helper = self.configuration_helper_init()

        self.ui.pushButton_loadCfg.clicked.connect(self.LoadConfigurationCmd)
        self.ui.pushButton_saveCfg.clicked.connect(self.SaveConfigurationCmd)

        # self.ui.listWidget.clicked.connect(self.listwidget_click)
        # self.thread_timerPreviewImg_tick = Runnable(self.timerPreviewImg_tick)
        # self.thread_timerConfigurationViewer_tick = Runnable(self.timerConfigurationViewer_tick)

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

        self.im_widget_plot_item = pg.PlotItem()
        self.im_widget_plot_item.setLabel("left", "y (um)")
        self.im_widget_plot_item.setLabel("bottom", "x (um)")

        self.im_plugin_plot_item = pg.PlotItem()
        self.im_plugin_plot_item.setLabel("left", "y (nm)")
        self.im_plugin_plot_item.setLabel("bottom", "x (nm)")

        self.im_plugin = pg.ImageView(self, view=self.im_plugin_plot_item)
        self.ui.gridLayout_pluginImage.addWidget(self.im_plugin)

        self.im_widget = pg.ImageView(self, view=self.im_widget_plot_item)

        self.ui.gridLayout_im.addWidget(self.im_widget, 0, 0, 1, 3)

        self.im_widget.show()
        self.im_widget.getView().showGrid(True, True)

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

        self.trace_widget = pg.PlotWidget(self)
        self.trace_widget.setToolTip("Double-click for reset the trace")
        self.trace_widget.setLabel("left", "Freq.", "Hz")
        self.trace_widget.setLabel("bottom", "Time", "s")
        self.ui.gridLayout_trace.addWidget(self.trace_widget, 0, 0)
        self.trace_widget.show()
        self.trace_widget.setDownsampling(1, True, "mean")
        self.trace_widget.setMinimumSize(100, 130)
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

        self.old_status_lockmovecheckbox = False
        self.lock_parameters_changed_call = False
        print_dec("self.lock_parameters_changed_call UNSET False")

        self.configurationFPGA_dict = {}
        self.configurationGUI_dict = {}

        self.spadfcsmanager_inst = SpadFcsManager()
        print_dec("SpadFcsManager()")
        self.qthread = QThread()
        self.spadfcsmanager_inst.moveToThread(self.qthread)
        print_dec("spadfcsmanager_inst.moveToThread()")

        self.ui.checkBoxLockRatio.setText("🔒")

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



        self.rect_roi_panorama_limit = RectROI_noHandle(
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

        self.rect_roi_panorama = RectROI_noHandle(
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

        self.get_fifo_elements = 0
        self.get_expected_fifo_elements = 0
        self.get_expected_fifo_elements_per_frame = 0

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
        self.tabifyDockWidget(self.ui.dockWidget_pos, self.ui.dockWidget_adv)

        self.tabifyDockWidget(
            self.ui.dockWidget_preview, self.ui.dockWidget_activatefifo
        )
        # self.tabifyDockWidget(self.ui.dockWidget_preview, self.ui.dockWidget_PMT_adv)
        self.tabifyDockWidget(self.ui.dockWidget_preview, self.ui.dockWidget_laser)
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
        self.plugin_manager = PluginsManager(self)
        self.plugin_configuration = {}

        self.cmd_update_plugin_list()

        self.last_saved_filename = None

        self.clock_base = 40 #MHz

        self.DFD_Activate = False
        self.DFD_nbins = 81
        self.snake_walk_Activate = False

        self.setupAnalogOutputGUI()
        # Replace the terminal with ScriptLauncher
        self.plugin_manager.plugin_loader("script_launcher")

        print_dec("Added DfdWidget")
        self.dfd_page = DfdWidget(self)
        self.ui.tabWidget.addTab(self.dfd_page, "DFD Preview")

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
            print_dec("call guiReadyEvent from __init__")

        self.init_ready = True

    # @staticmethod
    # def _add_padding_to_plot_widget(plot_widget, padding=0.1):
    #     """
    #     zooms out the view of a plot widget to show 'padding' around the contents of a PlotWidget
    #     :param plot_widget: The widget to add padding to
    #     :param padding: the percentage of padding expressed between 0.0 and 1.0
    #     :return:
    #     """
    #     print_dec("_add_padding_to_plot_widget")
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
        print_dec("httpApiServer_start()")
        if self.http_server_thread is None:
            self.http_server_thread = FastAPIServerThread(self, self.ui.lineEdit_httpAddr.text(), int(self.ui.lineEdit_httpPort.text()))
            print_dec("HTTP Server FastAPIServerThread Start")
            self.http_server_thread.start()
            self.ui.label_httpLink.setOpenExternalLinks(True)
            self.ui.label_httpLink.setText('<a href="http://%s:%s/docs">http://%s:%s/docs</a>' %
                                           (self.ui.lineEdit_httpAddr.text(), self.ui.lineEdit_httpPort.text(),
                                            self.ui.lineEdit_httpAddr.text(), self.ui.lineEdit_httpPort.text()))
        else:
            print_dec("HTTP Server FastAPIServerThread ALREADY RUNNING")

    def httpApiServer_stop(self):
        """
        Stops the FastAPI HTTP server
        """
        print_dec("htttApiServer_stop()")
        self.http_server_thread.stop()
        print_dec("HTTP Server FastAPIServerThread Stop")
        self.http_server_thread.join()
        print_dec("HTTP Server FastAPIServerThread Join")
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

        configuration_helper["LaserEnable0"] = (
            "Laser 0 En.",
            bool,
            self.ui.checkBox_laser0,
            True,
        )
        configuration_helper["LaserEnable1"] = (
            "Laser 1 En.",
            bool,
            self.ui.checkBox_laser1,
            True,
        )
        configuration_helper["LaserEnable2"] = (
            "Laser 2 En.",
            bool,
            self.ui.checkBox_laser2,
            True,
        )
        configuration_helper["LaserEnable3"] = (
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

        configuration_helper["spad_number_of_channels"] = (
            "SPAD channels",
            str,
            self.ui.comboBox_channels,
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

        configuration_helper["spadCmdLength"] = (
            "Spad Comman Length",
            str,
            self.ui.lineEdit_spad_length,
            False,
        )
        configuration_helper["spadCmdData"] = (
            "Spad Comman Data",
            str,
            self.ui.lineEdit_spad_data,
            False,
        )
        configuration_helper["spadCmdInvert"] = (
            "Spad Comman Invert",
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

        configuration_helper["backendDataRecv"] = (
            "backendDataRecv",
            str,
            self.ui.comboBox_fifobackend,
            False,
        )

        configuration_helper["plugins"] = ("Plugins", dict, None, False)

        return configuration_helper

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
        print_dec("analogOutChanged()")

        mydict = {}
        for ch in range(0, 8):
            sel = self.ui.comboBox_AnalogOut[ch].currentIndex()
            if self.ui.comboBox_AnalogOut[ch].currentText() == "Constant":
                sel = 15

            mydict["AnalogSelector_%d" % ch] = sel
            mydict["AnalogOutDC_%d" % ch] = self.ui.spinBox_AnalogOut[ch].value()

        self.setRegistersDict(mydict)

    @Slot()
    def laserChanged(self):
        """
        Slot for the Laser changed event
        """
        print_dec("laserChanged")
        self.setRegistersDict(
            {
                "LaserEnable0": self.ui.checkBox_laser0.isChecked(),
                "LaserEnable1": self.ui.checkBox_laser1.isChecked(),
                "LaserEnable2": self.ui.checkBox_laser2.isChecked(),
                "LaserEnable3": self.ui.checkBox_laser3.isChecked(),
            }
        )

    @Slot()
    def table_keyPressEvent(self, event):
        """
        Slot for the table key pressed
        """
        widget = self.ui.tableWidget
        print_dec(
            "Remove from",
            widget.selectedRanges()[0].leftColumn(),
            "to",
            widget.selectedRanges()[0].rightColumn(),
        )
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
        print_dec("traceReset")
        self.spadfcsmanager_inst.trace_reset()

    @Slot()
    def FCSReset(self):
        """
        Slot for the FCS reset event.
        """

        print_dec("FCSReset")
        self.spadfcsmanager_inst.FCS_reset()

    @Slot()
    def table_markers_keyPressEvent(self, event):
        """
        Slot for the table of the markers when a key pressed
        It handles the delete key
        """
        widget = self.ui.tableWidget_markers
        print_dec(
            "Remove from",
            widget.selectedRanges()[0].topRow(),
            "to",
            widget.selectedRanges()[0].bottomRow(),
        )
        if event.key() == Qt.Key_Delete:
            a = widget.selectedRanges()[0].topRow()
            b = widget.selectedRanges()[0].bottomRow() + 1
            print_dec(len(self.markers_list))
            for n, row in enumerate(range(a, b)):
                print_dec(row)
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
        print_dec("cmd_path_ttm")

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
        print_dec("cmd_path_destinationfolder")

        dialog = QFileDialog(self)
        dialog.setFileMode(QFileDialog.Directory)
        if dialog.exec_():
            self.ui.lineEdit_destinationfolder.setText(dialog.selectedFiles()[0])

    @Slot()
    def numberChannelsChanged(self):
        """
        Slot for the number of channels changed event
        """
        ch = int(self.ui.comboBox_channels.currentText())
        print_dec("numberChannelsChanged to", self.ui.comboBox_channels.currentText())
        self.CHANNELS = ch
        self.CHANNELS_x = int(np.sqrt(ch))
        self.CHANNELS_y = self.CHANNELS_x
        self.fingerprint_mask = np.ones((self.CHANNELS_x, self.CHANNELS_y), dtype=np.uint8)

    @Slot()
    def cmd_filename(self):
        """
        Slot for selecting the filename
        """
        print_dec("cmd_filename")

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
    def cmd_moveToSelectedRowMarker(self):
        """
        Slot for moving to the selected row marker
        """
        print_dec("cmd_moveToSelectedRowMarker")
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
        print_dec("moveToSelectedColumnFCS")
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
            print_dec(n, k)
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
        print_dec("cmd_moveToSelectedColumnFCS")
        widget = self.ui.tableWidget
        k = widget.currentColumn()
        if not k:
            return
        self.moveToSelectedColumnFCS(k)

    @Slot()
    def prova(self, ev):
        """
        dummy button
        """
        print_dec("prova", ev)

    @Slot()
    def getTabWinMinimization(self, widget, event):
        """
        Slot for the tab window minimization event
        """
        print_dec(widget, event, event.type())
        if event.type() is QEvent.Type.WindowStateChange:
            print_dec("WindowStateChange")
            if widget.isMinimized():
                print_dec("minimize")
                widget.setWindowFlags(Qt.Widget)
                self.ui.tabWidget.addTab(widget, widget.windowTitle())

    @Slot()
    def tabDoubleClick(self, number):
        """
        Slot for the tab double click event: it moves the tab to a new window
        """
        print_dec("tabDoubleClick", number)
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
        print_dec("guiReadyEvent()")
        self.im_widget.show()
        default_cfg = self.checkDefaultCfg()
        self.ui.lineEdit_configurationfile.setText(default_cfg)
        print("loading cfg", default_cfg)
        self.LoadConfiguration(default_cfg)
        self.panoramaButton()
        # self.splash.close()
        QTimer.singleShot(100, self.splash.close)

        current_conf = self.getGUI_data()
        self.ui.comboBox_preset.clear()
        for i in range(0, 26):
            self.preset_dict[chr(ord("A") + i)] = current_conf
            self.ui.comboBox_preset.addItem(chr(ord("A") + i))

        print_dec("Launch the QTimer.singleShot")
        QTimer.singleShot(100, self.raise_)
        QTimer.singleShot(250, self.showMaximized)

    @Slot()
    def showEvent(self, event):
        """
        Overridden showEvent method for generating the GUI ready event
        """
        print_dec("showEvent", event.spontaneous())
        super(MainWindow, self).showEvent(event)

        if not event.spontaneous():  # case when is the first paint
            self.guiReadyFlag = True
            if self.init_ready == True:
                print_dec("call guiReadyEvent from showEvent")
                QTimer.singleShot(10, self.guiReadyEvent)

    # @Slot()
    # def mouseMovedOnImage(self, ev):
    #     print_dec("self.mouseMovedOnImage", ev)

    # @Slot()
    # def pmtThresholdChanged(self, value=0):
    #     print_dec("pmtThresholdChanged")
    #     self.setRegistersDict({"PMT_VThreshold": self.ui.spinBox_PMT_Threshold.value(),
    #                            "PMT_VThreshold_Min": self.ui.spinBox_PMT_Threshold_Min.value(),
    #                            "PMT_VThreshold_Max": self.ui.spinBox_PMT_Threshold_Max.value()})

    # @Slot()
    # def cfg_file_clicked(self):
    #     print_dec("cfg_file_clicked()")
    #
    #
    #     file_cfg = QFileDialog.getOpenFileName(self, caption="Save Configuration",
    #                                            filter="Config File (*.cfg)",
    #                                            dir=self.ui.lineEdit_configurationfile.text())[0]
    #
    #     current_folder = QDir.fromNativeSeparators(os.getcwd()) + "/"
    #     if file_cfg != "":
    #         print_dec(file_cfg)
    #         print_dec(current_folder)
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
            print_dec("No")

    @Slot()
    def bit_file_clicked(self):
        """
        Slot for the selecting the bitfile of the 1st FPGA
        """
        print_dec("bit_file_clicked()")

        file_bit = QFileDialog.getOpenFileName(
            self,
            caption="FPGA Bit File",
            filter="FPGA Bit File (*.lvbitx)",
            dir="../bitfiles",
        )[0]
        current_folder = QDir.fromNativeSeparators(os.getcwd()) + "/"
        if file_bit != "":
            print_dec(file_bit)
            print_dec(current_folder)
            file_bit_nicer = file_bit.replace(current_folder, "")
            self.ui.lineEdit_fpgabitfile.setText(file_bit_nicer)

    @Slot()
    def bit_file_clicked2(self):
        """
        Slot for the selecting the bitfile of the 2nd FPGA
        """
        print_dec("bit_file_clicked2()")

        file_bit = QFileDialog.getOpenFileName(
            self,
            caption="FPGA Bit File",
            filter="FPGA Bit File (*.lvbitx)",
            dir="../bitfiles",
        )[0]
        current_folder = QDir.fromNativeSeparators(os.getcwd()) + "/"
        if file_bit != "":
            print_dec(file_bit)
            print_dec(current_folder)
            file_bit_nicer = file_bit.replace(current_folder, "")
            self.ui.lineEdit_fpga2bitfile.setText(file_bit_nicer)

    def checkDefaultCfg(self, default_name="cfg/current_system"):
        """
        Check if the default configuration file exists
        """
        if os.path.exists(default_name):
            with open(default_name, "r") as f:
                a = f.read().splitlines()
                print_dec("current_system opened:", a[1])
                return a[1]
        else:
            file = self.setNewDefaultCfg("cfg/default.cfg", "cfg/current_system")
            print_dec("'current_system' file not found")
            return file
        raise ("Error in checkDefaultCfg")

    def setNewDefaultCfg(self, default_cfg, default_name="cfg/current_system"):
        """
        Set a new default configuration file
        """
        with open(default_name, "w") as f:
            f.write(
                "\n".join(
                    [
                        "# the line below provides the default configuration file",
                        default_cfg,
                    ]
                )
            )
            print_dec(
                "A new '"
                + default_name
                + "' generated in which '"
                + default_cfg
                + "' is selected."
            )
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
                    configuration[name] = self.plugin_configuration
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
                                    print_dec(
                                        "Wrong methods to read str",
                                        n,
                                        (name, (caption, mtype, ref_obj, visible)),
                                    )
                    elif mtype is bool:
                        configuration[name] = ref_obj.isChecked()

            except Exception as e:
                print_dec("ERROR getGUI_data")
                print_dec(n, (name, (caption, mtype, ref_obj, visible)))
                print_dec(repr(e))

        return configuration

    def setGUI_data(self, configuration={}):
        """
        Set the GUI data from a dictionary (it can be also a partial configuration)
        """
        # lock_old = self.lock_parameters_changed_call
        # self.lock_parameters_changed_call = True

        for name in configuration:
            try:
                caption, mtype, ref_obj, visible = self.configuration_helper[name]
                if name == "plugins":
                    self.plugin_configuration.update(configuration[name])
                    print(
                        "PLUGINS CONFIGURATION",
                        type(configuration[name]),
                        configuration[name],
                    )
                    print(
                        "PLUGINS CONFIGURATION",
                        type(self.plugin_configuration),
                        self.plugin_configuration,
                    )

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
                print_dec("ERROR setGUI_data")
                print_dec(name, (caption, mtype, ref_obj, visible))
                print_dec(repr(e))
        #
        # self.lock_parameters_changed_call = lock_old
        # self.positionSettingsChanged()
        # self.axesRangeChanged()

    # @Slot()
    # def testevent(self, ev):
    #     print_dec("testevent", ev)

    @Slot()
    def delete_list_file(self):
        """
        delete the selected files in the list
        """
        print_dec("delete_list_file()")
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
        print_dec("copy_list_file()")
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
            print_dec(plugin_to_be_loaded)
            self.plugin_manager.plugin_loader(plugin_to_be_loaded)

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
        l = self.plugin_manager.plugin_list()
        print_dec("cmd_update_plugin_list()", l)
        for i in l:
            self.ui.listWidget_plugins.addItem(i)

    @Slot()
    def axesRangeChanged(self, ev=None):
        """
        Slot for the axes range changed event, when the range of the axes of the Image Preview is changed
        """
        print_dec("axesRangeChanged(...)")
        if not self.ui.checkBox_lockMove.isChecked():
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

                print_dec("bottom_range:", bottom_range)
                print_dec("left_range:", left_range)
                print_dec(
                    "R ",
                    bottom_gap,
                    left_gap,
                    "    ",
                    min(bottom_gap, left_gap),
                    min(bottom_gap, left_gap),
                )

                self.lock_parameters_changed_call = True
                print_dec("axesRangeChanged self.lock_parameters_changed_call SET True")
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
                print_dec(
                    "axesRangeChanged self.lock_parameters_changed_call UNSET False"
                )

                self.updateLabelPixelSize()

                self.lock_range_changing = False

                if self.started_preview:
                    self.plotPreviewImage()
                if self.started_preview or self.started_normal:
                    self.positionSettingsChanged()

    @Slot()
    def closeEvent(self, event):
        """
        Overridden closeEvent method for closing the application
        """
        print_dec("=======================")
        print_dec("   CLOSE EVERYTHING")
        print_dec("=======================")

        print_dec("self.spadfcsmanager_inst.stopPreview()")
        try:
            self.spadfcsmanager_inst.stopPreview()
        except Exception as e:
            print_dec("not present", repr(e))

        print_dec("self.timerPreviewImg.stop()")
        try:
            self.timerPreviewImg.stop()
        except Exception as e:
            print_dec("not present", repr(e))

        print_dec("self.spadfcsmanager_inst.stopAcquisition()")
        try:
            self.spadfcsmanager_inst.stopAcquisition()
        except Exception as e:
            print_dec("not present", repr(e))

        print_dec("self.spadfcsmanager_inst.stopPreview()")
        try:
            self.spadfcsmanager_inst.stopPreview()
        except Exception as e:
            print_dec("not present", repr(e))

        print_dec("self.ttm_remote_manager.close()")
        try:
            if self.ttm_remote_manager is not None:
                self.ttm_remote_manager.close()
                self.ttm_remote_manager = None
        except Exception as e:
            print_dec("not present", repr(e))

        print_dec("Now every process should be closed.")
        event.accept()

        print_dec(
            "Now every process should be closed,Really! \n=============\n=== CIAO! ===\n============="
        )

    def bitfile_check(self, path):
        """
        Check if the bitfile exists
        """
        if not os.path.isfile(path):
            msgBox = QMessageBox()
            msgBox.setText("The firmware file %s does not exist!\n"
                           "Please check if the path in the menu Adv./Board configuration/FPGA Bitfiles is correct.\n"
                           "IMPORTANT: the firmwares are not included in BrightEyes-MCS tree\n"
                           "you need to download them a part. Please find in the documentation the link.\n" % path
                           )
            msgBox.exec_()
            raise (ValueError("Firmware file not found!"))

    def connectFPGA(self):
        """
        Connect to the FPGA(s)
        """
        print_dec("ConnectFPGA")

        self.bitfile_check(self.ui.lineEdit_fpgabitfile.text())

        self.spadfcsmanager_inst.set_bit_file(self.ui.lineEdit_fpgabitfile.text())
        self.spadfcsmanager_inst.set_ni_addr(self.ui.lineEdit_ni_addr.text())

        self.spadfcsmanager_inst.set_bit_file_second_fpga(self.ui.lineEdit_fpga2bitfile.text())
        self.spadfcsmanager_inst.set_ni_addr_second_fpga(self.ui.lineEdit_ni2addr.text())

        self.spadfcsmanager_inst.set_timeout_fifos(
            self.ui.spinBox_fifo_timeout.value() * 1000
        )

        if self.spadfcsmanager_inst.is_connected:
            print_dec("Already connected")
        else:
            print_dec("FPGA NOT CONNECTED NOW CONNECTING")
            mydict = {}
            mydict.update(self.spadfcsmanager_inst.default_configuration)
            mydict.update(self.configurationFPGA_dict)

            invert_sdata = (self.ui.checkBox_spad_invert.isChecked(),)

            rust_fifo_active = self.ui.comboBox_fifobackend.currentText().startswith(
                "Rust"
            )
            print_dec("rust_fifo_active", rust_fifo_active)
            self.spadfcsmanager_inst.set_use_rust_fifo(rust_fifo_active)

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
                    "Invert SDATA": self.ui.checkBox_spad_invert.isChecked(),
                    "msgOut": msg_out,
                    "msgLen": msg_len,
                }
            )

            if self.CHANNELS == 49:
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

            # self.spadfcsmanager_inst.set(self.ui.spinBox_fifo_buffer_size.value())
            self.spadfcsmanager_inst.set_preview_buffer_size_in_words(
                self.ui.spinBox_preview_buffer_size.value()
            )
            self.ui.label_actual_preview_buffer_size.setText(
                "%d"
                % (
                        self.ui.spinBox_preview_buffer_size.value()
                        * self.ui.spinBox_time_bin_per_px.value()
                )
            )

            fifo = []
            if self.ui.radioButton_analog.isChecked():
                fifo.append("FIFOAnalog")
            if self.ui.radioButton_digital.isChecked():
                fifo.append("FIFO")

            self.spadfcsmanager_inst.set_len_fifo_prebuffer(
                self.ui.spinBox_fifo_prebuffer.value()
            )
            self.spadfcsmanager_inst.set_requested_depth(
                self.ui.spinBox_fifo_buffer_size.value()
            )
            self.spadfcsmanager_inst.connect(mydict, list_fifos=fifo)
            # self.spadfcsmanager_inst.start()

    def setRegistersDict(self, myconf):
        """
        Set the registers dictionary which is mapped to the FPGA
        """
        self.configurationFPGA_dict.update(myconf)
        # print_dec("setRegistersDict", self.configurationFPGA_dict)
        self.spadfcsmanager_inst.setRegistersDict(myconf)
        # print_dec("Waiting setRegistersDict")

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
    #     print_dec(event.pos().x(), event.pos().y(), event.size().x(), event.size().y())
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
    #             print_dec(exc)
    #
    #     else:
    #         print_dec("self.rect_roi_panorama_modified_lock")

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
        print_dec("updateRoiPanaorama")
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
        print_dec("SKIP roiModified")
        return
        # self.rect_roi_panorama.setPos(self.rect_roi.pos())
        # self.rect_roi_panorama.setSize(self.rect_roi.size())
        # print(event)
        # print_dec(event.pos().x(), event.pos().y(), event.size().x(), event.size().y())
        # if not self.rect_roi_modified_lock:
        #     # print(event.pos().x(), event.pos().y(), event.size().x(), event.size().y())
        #
        #     self.lock_parameters_changed_call = True
        #     print_dec("roiModified self.lock_parameters_changed_call SET True")
        #
        #     self.ui.spinBox_off_x_um.setValue(self.rect_roi.pos().x())
        #     self.ui.spinBox_off_y_um.setValue(self.rect_roi.pos().y())
        #
        #     self.ui.spinBox_range_x.setValue(self.rect_roi.size().x())
        #     self.ui.spinBox_range_y.setValue(self.rect_roi.size().y())
        #     self.offset_um_Changed(force=True)
        #     self.lock_parameters_changed_call = False
        #     print_dec("roiModified self.lock_parameters_changed_call UNSET False")
        # else:
        #     print_dec("self.rect_roi_modified_lock")

    def setSelectedChannel(self, ch):
        """
        set the selected channel
        """
        self.selected_channel = ch
        print_dec("setSelectedChannel", ch)
        i = self.ui.comboBox_plot_channel.findText("%d" % ch)
        print_dec(i)
        if 0 <= i < self.CHANNELS:
            self.ui.comboBox_plot_channel.setCurrentIndex(i)
        else:
            ii = self.ui.comboBox_plot_channel.findText("Sum")
            print_dec(ii)
            self.ui.comboBox_plot_channel.setCurrentIndex(ii)

    @Slot()
    def about(self):
        """
        Show the about dialog box with license
        """

        self.textBrowser = QTextBrowser(None)
        self.textBrowser.setObjectName("textBrowser")
        f = open("gui/about.html", "r")
        self.textBrowser.setHtml(f.read())
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
        image clicked event.
        if the CTRL key is pressed, it will add a marker
        else it will center the image on the clicked point
        """
        mouse_event = event
        mouse_point = mouse_event.pos()
        projection = self.ui.comboBox_view_projection.currentText()

        if mouse_event.double():
            print_dec("Double click")
            print_dec(mouse_point)
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

            print_dec("event.modifiers()", event.modifiers())

            if event.modifiers()  & Qt.ControlModifier:
                conf = self.getGUI_data()

                conf["offset_x_um"] = a[0]
                conf["offset_y_um"] = a[1]
                conf["offset_z_um"] = a[2]

                self.markers_list.append(conf)
                self.drawMarkers()
                self.markersViewTable()
            else:
                print_dec("imageClicked() + Qt.CTRL")
                self.ui.spinBox_off_x_um.setValue(a[0])
                self.ui.spinBox_off_y_um.setValue(a[1])
                self.ui.spinBox_off_z_um.setValue(a[2])
                self.offset_um_Changed()


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
            print_dec("NO PROJECTION IN DRAWMARKES")

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
            print_dec("Double click")

        self.fingerprint_widget.scene.itemsBoundingRect().contains(mouse_point)
        print_dec("x=", mouse_point.x(), " y=", mouse_point.y())
        pos = self.fingerprint_widget.view.mapSceneToView(mouse_point)
        print_dec(pos)
        print_dec(event)
        selected_ch_x = int((pos.x()))
        selected_ch_y = int((pos.y()))
        print_dec(event.modifiers())
        if event.modifiers() & Qt.ControlModifier:
            print_dec("Qt.CTRL")
            if self.fingerprint_mask[selected_ch_y, selected_ch_x] == 1:
                self.fingerprint_mask[selected_ch_y, selected_ch_x] = 0
            else:
                self.fingerprint_mask[selected_ch_y, selected_ch_x] = 1
            self.update_fingerprint_mask()

        else:
            self.setSelectedChannel(selected_ch_x + 5 * selected_ch_y)
            print_dec(
                "You clicked on the channel ",
                self.selected_channel,
                "(x:",
                selected_ch_x,
                " y:",
                selected_ch_y,
                ")",
            )
            # self.plotCurrentImage()

    def update_fingerprint_mask(self):
        """
        update the fingerprint mask
        """
        print_dec("update_fingerprint_mask")
        self.fingerprint_markers_mask.clear()
        for xxx in range(self.CHANNELS_x):
            for yyy in range(self.CHANNELS_y):
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

        if self.spadfcsmanager_inst.shared_arrays_ready:
            print_dec("ready self.spadfcsmanager_inst.shared_arrays_ready")
            self.spadfcsmanager_inst.set_fingerprint_mask(
                np.ravel(self.fingerprint_mask)
            )
        else:
            print_dec("not ready self.spadfcsmanager_inst.shared_arrays_ready")

    # def dragEnterEvent(self, event):
    #     print_dec(event)
    #     if event.mimeData().hasUrls:
    #         event.accept()
    #     else:
    #         event.ignore()

    # def dragMoveEvent(self, event):
    #     print_dec(event)
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
    #             print_dec(url.toLocalFile())
    #             self.loadFile(url.toLocalFile())
    #     else:
    #         event.ignore()

    # def loadFile(self, file_name):
    #     self.activeFile = True
    #     hf = h5py.File(file_name, "r")
    #
    #     print_dec(hf)
    #
    #     if "default" in hf.attrs:
    #         print_dec("h5.attrs default", hf.attrs["default"])
    #     else:
    #         print_dec("h5.attrs default NOT FOUND")
    #
    #     if "data_format_version" in hf.attrs:
    #         print_dec("h5.attrs data_format_version", hf.attrs["data_format_version"])
    #     else:
    #         print_dec("h5.attrs data_format_version NOT FOUND")
    #
    #     self.currentImage = np.asarray(hf["data"])
    #     print_dec(self.currentImage.shape)
    #
    #     if 'configuration' in hf.attrs:
    #         for i in hf['configuration'].attrs:
    #             print_dec(i, hf['configuration'].attrs[i])
    #             self.configurationFPGA_dict.update({i: hf['configuration'].attrs[i]})
    #     else:
    #         print_dec("h5.attrs configuration NOT FOUND")
    #
    #     self.plotCurrentImage()
    #
    #     data_finger_print = self.currentImage.sum(axis=(0, 1, 2, 3, 4)).reshape(5, 5)
    #
    #     self.draw_fingerprint(data_finger_print)
    #
    #     self.ui.pushButton_napari.setEnabled(True)

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
        print_dec("selectedAutoscaleImg()", self.autoscale_image)

    @Slot()
    def selectedAutoscaleFingerprint(self):
        """
        Slot for the autoscale fingerprint checkbox
        """
        self.autoscale_fingerprint = self.ui.checkBox_autoscale_fingerprint.isChecked()
        print_dec("selectedAutoscaleFingerprint", self.autoscale_fingerprint)

    # @Slot()
    # def selectedCumulativeFingerprint(self):
    #     self.cumulative_fingerprint = self.ui.checkBox_cumulative_fingerprint.isChecked()
    #     print("selectedCumulativeFingerprint", self.cumulative_fingerprint)

    @Slot()
    def microimageType(self, num):
        """
        Slot for the microimage type selection
        """
        print_dec("microimageType ", num)
        self.fingerprint_visualization = num
        # if num == 0:    # cumulative
        # elif num == 1:  # 10000 bins
        # elif num == 2:  # fingerprint

    @Slot()
    def addToBatch(self):
        self.table_manager.add_dict(self.getGUI_data())

    def finalizeImage(self):
        print_dec("finalizeImage()")
        self.plotCurrentImage()
        data_finger_print = self.spadfcsmanager_inst.getFingerprint()
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

    @Slot()
    def updateTables(self):
        """
        Update the Status tables
        """
        if self.spadfcsmanager_inst.is_connected == True:
            fff = self.spadfcsmanager_inst.fpga_handle.register_read_all()
        else:
            fff = self.spadfcsmanager_inst.get_registers_configuration()

        try:
            t = [
                str(fff[i])
                for i in (
                    "cur_t",
                    "cur_x",
                    "cur_y",
                    "cur_z",
                    "cur_rep",
                    # "current_cycle",
                )
            ]
        except:
            t = ["na"] * 5

        self.statusBar_currentPosition.setText(
            "B:%s X:%s Y:%s Z:%s R:%s" % (t[0], t[1], t[2], t[3], t[4])
        )

        model = TreeModel(["Parameter", "Data"], fff)
        self.ui.treeView.setModel(model)

        fff = self.configurationFPGA_dict
        model = TreeModel(["Parameter", "Data"], fff)
        self.ui.treeView_2.setModel(model)

        fff = self.configurationGUI_dict
        model = TreeModel(["Parameter", "Data"], fff)
        self.ui.treeView_3.setModel(model)

        # fff = self.markers_dict
        # model = TreeModel(["Parameter", "Data", "Second", "Third"], fff)
        # self.ui.treeView_FCS.setModel(model)

    @Slot()
    def test1(self):
        """
        dummy button clicked event for test
        """
        print_dec("test1()")
        self.finalizeImage()

    @Slot()
    def test2(self):
        """
        dummy button clicked event for test
        """
        print_dec("test2()")
        self.webcam_capture = iio.get_reader("<video0>")

    @Slot()
    def test3(self):
        """
        dummy button clicked event for test
        """
        frame = self.webcam_capture.get_next_data()
        print_dec(frame.shape)
        self.webcam_widget.setImage(np.moveaxis(frame, [0, 1, 2], [1, 0, 2]))
        print_dec("test3()")

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
        print_dec("test5()")
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
        print_dec("test7() as start but no run")

        if self.ui.checkBox_ttmActivate.isChecked():
            self.ttm_activate_change_state()

        # self.myfpgainst.acquisitionThread.reset_data()
        self.ui.pushButton_acquisitionStart.setEnabled(False)
        self.ui.pushButton_externalProgram.setEnabled(False)
        self.ui.pushButton_stop.setEnabled(True)

        if not self.spadfcsmanager_inst.is_connected:
            print_dec("not self.spadfcsmanager_inst.is_connected")
            self.connectFPGA()
        else:
            print_dec("FPGA Already connected!")

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

        self.startAcquisition(activate_preview=True, do_run=False)

    @Slot()
    def test8(self):
        """
        dummy button clicked event for test
        """
        pass
        # self.define_circular()

    def define_circular(self, circular_points):
        """
        define the points for the circular scan
        """
        radius = self.ui.spinBox_circular_radius_nm.value() / 1000.

        calib_xx = self.ui.spinBox_calib_x.value()
        calib_yy = self.ui.spinBox_calib_y.value()
        calib_zz = self.ui.spinBox_calib_z.value()

        t = np.linspace(0, 2 * np.pi, circular_points + 1)[:-1]

        self.X_array_um = (np.cos(t) * radius)
        self.Y_array_um = (np.sin(t) * radius)
        self.Z_array_um = np.zeros(circular_points + 1)

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
        #     print_dec("NO PROJECTION IN DRAWMARKES")
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

        # print_dec("previewLoop CIRCULAR <======================================================")
        #
        # self.nrepetition_before_run_preview = self.ui.spinBox_nrepetition.value()
        #
        # # self.myfpgainst.acquisitionThread.reset_data()
        # if not self.spadfcsmanager_inst.is_connected:
        #     print_dec("not self.spadfcsmanager_inst.is_connected")
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
                "ScanXVoltages": X_arr,
                "ScanYVoltages": Y_arr,
                "ScanZVoltages": Z_arr,
            }
        )

        # print_dec("Start")
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
        # self.startAcquisition(activate_preview=True)
    @Slot()
    def addcurrentconfmacro(self):
        """
        Slot for the add current configuration to the table for macros
        """
        print_dec("addcurrentconfmacro")
        conf = self.getGUI_data()
        self.table_manager.add_dict(conf)
    @Slot()
    def addcurrentconfmacrofcs(self):
        """
        Slot for the add current configuration to the table for macros
        activating FCS preview and forcing to zero the range
        """
        print_dec("addcurrentconfmacrofcs")
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
        print_dec("copyPositionMarkers")
        self.table_manager.add_list_of_dict(self.markers_list)

    @Slot()
    def copyPositionsMarkersFCS(self):
        """
        copy the markers to the table for macros
        activating FCS preview and forcing to zero the range
        """
        print_dec("copyPositionMarkersFCS")
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
        print_dec("startBatchFCS started")
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

            t = QTime()
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
        print_dec("startedBatch FCS ended")

    @Slot()
    def stopBatchFCS(self):
        """
        stop the batch event
        """
        self.runBatchFCS = False
        print_dec("stopBatchFCS")

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
            if self.spadfcsmanager_inst.previewProcess_isAlive():
                P = "⏩"
        except:
            pass

        try:
            if self.spadfcsmanager_inst.dataProcess_isAlive():
                D = "⏩"
        except:
            pass

        try:
            if self.spadfcsmanager_inst.fpga_handle.fpga_handle_process_isAlive():
                F = "⏩"
        except:
            pass
        self.statusBar_cpu.setText("CPU: %d%%" % psutil.cpu_percent())
        self.statusBar_mem.setText("RAM: %d%%" % psutil.virtual_memory().percent)

        self.statusBar_processes.setText(P + D + F)
        self.timerConfigurationViewer_tick_mutex.unlock()

    @Slot()
    def cmd_call_external(self):
        import subprocess

        line = self.ui.lineEdit_externalProgram.text()
        line = line.replace("%python", sys.executable)
        line = line.replace("%lastfilename", self.last_saved_filename)
        cmds = line.split(" ")
        print_dec("cmd_call_external", cmds)
        print_dec(sys.platform)
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
        if not self.timerPreviewImg_tick_mutex.tryLock():
            print_dec("self.timerPreviewImg_tick_lock called but busy")
            return

        time_res = self.ui.spinBox_timeresolution.value()
        time_bin = self.ui.spinBox_time_bin_per_px.value()
        frames = self.ui.spinBox_nframe.value()
        repetition = self.ui.spinBox_nrepetition.value()

        if self.ui.radioButton_analog.isChecked():
            fifo_name = "FIFOAnalog"
        if self.ui.radioButton_digital.isChecked():
            fifo_name = "FIFO"

        self.get_fifo_elements = self.spadfcsmanager_inst.getCurrentAcquistionElement(
            fifo_name
        )
        self.get_expected_fifo_elements = (
            self.spadfcsmanager_inst.getExpectedFifoElements()
        )
        self.get_expected_fifo_elements_per_frame = (
            self.spadfcsmanager_inst.getExpectedFifoElementsPerFrame()
        )
        self.get_number_of_threads_h5 = (
            self.spadfcsmanager_inst.get_number_of_threads_h5()
        )

        self.ui.label_tot_num_dat_point_val.setText(
            "%d %% (%d / %d)"
            % (
                100 * self.get_fifo_elements / self.get_expected_fifo_elements,
                self.get_fifo_elements,
                self.get_expected_fifo_elements,
            )
        )
        # self.ui.label_exp_num_data_val.setText("%d" % self.get_expected_fifo_elements)

        self.ui.progressBar_repetition.setMaximum(100.0)

        get_current_preview_element = self.spadfcsmanager_inst.getCurrentPreviewElement(
            fifo_name
        )
        get_expected_fifo_elements = self.spadfcsmanager_inst.getExpectedFifoElements()

        current_time = (
                get_current_preview_element * (time_res * time_bin * 1e-6) / self.CHANNELS
        )
        current_frame = self.spadfcsmanager_inst.get_current_z()
        current_rep = self.spadfcsmanager_inst.get_current_rep()

        self.ui.label_current_time_val.setText("%0.2f" % current_time)
        self.ui.label_current_frame_val.setText("%d" % current_frame)
        self.ui.label_current_repetition_val.setText("%d" % current_rep)

        if self.get_expected_fifo_elements != 0:
            self.ui.progressBar_repetition.setValue(
                100.0 * self.get_fifo_elements / self.get_expected_fifo_elements
            )
        else:
            self.ui.progressBar_repetition.setValue(0)

        if self.get_fifo_elements != 0:
            self.ui.progressBar_frame.setMaximum(100.0)
        else:
            self.ui.progressBar_frame.setMaximum(0)
        self.ui.progressBar_frame.setValue(
            100.0
            * (self.get_fifo_elements % self.get_expected_fifo_elements_per_frame)
            / self.get_expected_fifo_elements_per_frame
        )

        corralation = self.spadfcsmanager_inst.getAutocorrelation()
        self.fcs_widget.plot(
            corralation[0, :] * time_res * 1e-6,
            corralation[1, :],
            clear=True,
            symbol="o",
        )

        trace, trace_pos = self.spadfcsmanager_inst.getTrace()

        if (
                "Analog" in self.ui.comboBox_plot_channel.currentText()
                and not self.DFD_Activate
        ):
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
                trace[0, :trace_pos], trace[1, :trace_pos] * coeff, clear=True
            )
        else:
            self.trace_widget.plot(trace[0, :], trace[1, :], clear=True)

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
            if (
                    self.get_fifo_elements % self.get_expected_fifo_elements_per_frame
            ) != 0:
                data_finger_print = (
                        self.spadfcsmanager_inst.getFingerprintCumulative()
                        / (
                                (
                                        (
                                                self.get_fifo_elements
                                                % self.get_expected_fifo_elements_per_frame
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
                    self.spadfcsmanager_inst.getFingerprintCumulativeLast10000()
                    / (10000 * time_res * 1e-6)
            )
        elif self.fingerprint_visualization == 2:
            data_finger_print = (
                    self.spadfcsmanager_inst.getFingerprintCumulativeLastFrame()
                    / (self.get_expected_fifo_elements_per_frame / 2 * time_res * 1e-6)
            )

        saturation_data = self.spadfcsmanager_inst.getFingerprintSaturation()

        if data_finger_print is not None:
            data_finger_print = data_finger_print * self.fingerprint_mask

            if self.ui.checkBox_correlationMatrix.isChecked():
                self.microimage_analysis(data_finger_print)

            self.draw_fingerprint(data_finger_print, saturation_data)

        if self.spadfcsmanager_inst.acquisition_is_almost_done():
            print_dec(
                "self.spadfcsmanager_inst.acquisition_is_almost_done()",
                self.get_number_of_threads_h5,
            )
            self.ui.pushButton_stop.setEnabled(False)
            self.ui.pushButton_acquisitionStart.setEnabled(False)

        if self.spadfcsmanager_inst.acquisition_is_done():
            print_dec(
                "self.spadfcsmanager_inst.acquisition_is_done()",
                self.spadfcsmanager_inst.acquisition_is_done(),
            )
            self.my_tick_counter += self.timerPreviewImg.interval()

            if (self.my_tick_counter > 5000) or (
                    get_current_preview_element >= get_expected_fifo_elements
            ):
                print_dec(
                    "get_fifo_elements >= get_expected_fifo_elements and 1s passed"
                )
                self.spadfcsmanager_inst.acquisition_done_reset()
                self.finalizeAcquisition()

        fifo1, fifo2 = self.spadfcsmanager_inst.get_FIFO_status()

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
                    * self.spadfcsmanager_inst.shared_dict["last_packet_size"]
                    * self.ui.spinBox_timeresolution.value()
                    / 2e6
            )
        )

        if self.get_number_of_threads_h5 > 0.9 * self.ui.progressBar_saving.maximum():
            self.ui.progressBar_saving.setMaximum(self.get_number_of_threads_h5 * 1.2)
        self.ui.progressBar_saving.setValue(self.get_number_of_threads_h5)

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
                "%d" % self.spadfcsmanager_inst.shared_dict["last_packet_size"]
            )
        except:
            print_dec("self.ui.last_packet_size FAIL")

        try:
            # print(self.spadfcsmanager_inst.last_preprocessed_len)
            # print(self.spadfcsmanager_inst.last_preprocessed_len["FIFO"].value)
            self.ui.label_fifo_prebuffer_len.setText(
                "%d"
                % self.spadfcsmanager_inst.last_preprocessed_len["FIFOAnalog"].value
            )
        except:
            print_dec("self.ui.last_preprocessed_len FIFOAnalog FAIL")

        try:
            # print(self.spadfcsmanager_inst.last_preprocessed_len)
            # print(self.spadfcsmanager_inst.last_preprocessed_len["FIFO"].value)
            self.ui.label_fifo_prebuffer_len.setText(
                "%d" % self.spadfcsmanager_inst.last_preprocessed_len["FIFO"].value
            )

        except:
            print_dec("self.ui.last_preprocessed_len FIFO FAIL")

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

        coeff = 25. / self.CHANNELS

        for xxx in range(self.CHANNELS_x):
            for yyy in range(self.CHANNELS_y):
                if saturation_data[yyy, xxx] > 0:
                    v = self.spadfcsmanager_inst.getFingerprintCumulative() * 1.
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
        print_dec("Start QTConsole")
        namespace = {
            "np": np,
            "h5py": h5py,
            "pg": pg,
            "main_window": self,
            "spadfcsmanager": self.spadfcsmanager_inst,
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
'main_window' for the current QT window instantiation
'spadfcsmanager' for the current spadfcsmanager instantiation\n\n
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
        print_dec("temporalSettingsChanged")

        waitForLaserInCycle = self.ui.spinBox_waitForLaser.value() * 40e6
        waitAfterFrame = self.ui.spinBox_waitAfterFrame.value() * 40e6
        waitOnlyFirstTime = self.ui.checkBox_waitOnlyFirstTime.isChecked()

        print_dec("temporalSettingsChanged")

        self.setRegistersDict(
            {
                "Cx": int(Cx),
                "#timebinsPerPixel": int(time_bin),
                "ClockDur": int(clock_duration),
                "WaitForLaser": int(waitForLaserInCycle),
                "WaitAfterFrame": int(waitAfterFrame),
                "WaitOnlyFirstTime": waitOnlyFirstTime,
                "#circular_points": circ_points,
                "#circular_rep": circ_repetition
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
        print_dec("loadPreset")
        combo_str = self.ui.comboBox_preset.currentText()
        self.setGUI_data(self.preset_dict[combo_str])
        print_dec("preset %d loaded" % combo_str)

    @Slot()
    def savePreset(self):
        """
        save the preset configuration
        """
        print_dec("savePreset")
        combo_str = self.ui.comboBox_preset.currentText()
        self.preset_dict[combo_str] = self.getGUI_data()
        print_dec("preset %d saved" % combo_str)

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
        print_dec("updatePixelValueChanged")

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

        print_dec(self.rect_roi.state)
        # self.rect_roi_modified_lock = False

        self.rect_roi.hide()

        self.positionSettingsChanged_apply()
        self.temporalSettingsChanged()
        self.plotSettingsChanged()

        #
        self.axesRangeChanged()
        # self.positionSettingsChanged()

        # pass
        if self.ui.checkBox_lockMove.isChecked():
            print_dec("self.im_widget.autoRange()")
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
            print_dec("offset_um_update self.lock_parameters_changed_call SET True")
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
            print_dec(self.started_normal, self.started_preview)
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
            print_dec("offset_um_update lock_parameters_changed_call is True")

        self.lock_parameters_changed_call = oldlock_parameters_changed_call
        self.lock_range_changing = oldlock_range_changing

    @Slot()
    def spatialSettingsChanged(self, force=False):
        """
        spatial settings changed event
        """
        if self.lockspatialSettingsChanged == False:
            lockmove = self.ui.checkBox_lockMove.isChecked()

            self.ui.checkBox_lockMove.setChecked(True)
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
            self.ui.checkBox_lockMove.setChecked(lockmove)

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
            print_dec("positionSettingsChanged_apply")
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
                    "CalibrationFactors(V/step)": calibration_v_step,
                    "Offset/StartValue (V)": start_offset,
                    "#pixels": numbers_xx,
                    "#lines": numbers_yy,
                    "#frames": numbers_ff,
                    "#repetition": numbers_repetition + 1,
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
            print_dec(self.rect_roi.state)
            # self.rect_roi_modified_lock = False

            self.updateRectLimit() #update the rectangle in the panaorma

        else:
            print_dec(
                "positionSettingsChanged_apply lock_parameters_changed_call is True"
            )

        self.checkAlerts()

    @Slot()
    def DFD_clicked(self):
        """
        activate the DFD mode
        """
        self.DFD_nbins = self.ui.spinBox_DFD_nbins.value()
        if self.ui.checkBox_DFD.isChecked():
            self.ui.spinBox_time_bin_per_px.setValue(self.DFD_nbins)
            self.ui.spinBox_timeresolution.setValue(2.0)

    @Slot()
    def updateMaxMinVoltages(self):
        """
        event when the max and min voltages are changed
        """
        print_dec("updateMaxMinVoltages")
        min_x_V = self.ui.spinBox_min_x_V.value()
        min_y_V = self.ui.spinBox_min_y_V.value()
        min_z_V = self.ui.spinBox_min_z_V.value()

        max_x_V = self.ui.spinBox_max_x_V.value()
        max_y_V = self.ui.spinBox_max_y_V.value()
        max_z_V = self.ui.spinBox_max_z_V.value()

        self.setRegistersDict(
            {
                "MinXVoltages": min_x_V,
                "MinYVoltages": min_y_V,
                "MinZVoltages": min_z_V,
                "MaxXVoltages": max_x_V,
                "MaxYVoltages": max_y_V,
                "MaxZVoltages": max_z_V,
            }
        )

    @Slot()
    def plotSettingsChanged(self):
        """

        """
        print_dec("plotSettingsChanged")
        self.updatePreviewConfiguration()
        self.checkAlerts()

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

    # @Slot()
    # def connectButtonClicked(self):
    #     self.connectCmd()

    # def afterFpgaRun(self):
    #     pass

    def startAcquisition(self, activate_preview=False, do_run=True):
        """
        the actual start acquisition function
        """
        self.activate_preview = activate_preview

        self.DFD_Activate = self.ui.checkBox_DFD.isChecked()
        self.DFD_nbins = self.ui.spinBox_DFD_nbins.value()

        self.numberChannelsChanged()
        self.spadfcsmanager_inst.set_channels(int(self.ui.comboBox_channels.currentText()))

        self.spadfcsmanager_inst.set_activate_DFD(self.DFD_Activate)
        self.spadfcsmanager_inst.set_DFD_nbins(self.DFD_nbins)

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

        print_dec("temporalSettingsChanged")

        circular_motion = self.ui.checkBox_circular.isChecked()
        dummy_data = self.ui.checkBox_DummyData.isChecked()

        laser_seq_gui = [int(self.ui.comboLaserSeq_1.currentText()),
                        int(self.ui.comboLaserSeq_2.currentText()),
                        int(self.ui.comboLaserSeq_3.currentText()),
                        int(self.ui.comboLaserSeq_4.currentText()),
                        int(self.ui.comboLaserSeq_5.currentText()),
                        int(self.ui.comboLaserSeq_6.currentText())]

        laser_sequence =  [0, laser_seq_gui[0], 0, laser_seq_gui[1], 0, laser_seq_gui[2], 0, laser_seq_gui[3], 0,
                                laser_seq_gui[4], 0, laser_seq_gui[5]]

        slave_mode = self.ui.checkBox_slavemode_enable.isChecked()
        slave_type = self.ui.comboBox_slavemode_type.currentIndex()

        self.setRegistersDict(
            {
                "Cx": int(Cx),
                "#timebinsPerPixel": int(time_bin),
                "ClockDur": int(clock_duration),
                "WaitForLaser": int(waitForLaserInCycle),
                "WaitAfterFrame": int(waitAfterFrame),
                "WaitOnlyFirstTime": waitOnlyFirstTime,
                "#circular_points": circ_points,
                "#circular_rep": circ_repetition,
                "CircularMotionActivate": circular_motion,
                "DummyData": dummy_data,
                "excitation sequence": laser_sequence,
                "ext_px_selector": slave_type,
                "SlaveMode": slave_mode
                # "AD5764_MaxBit": 1,
            }
        )

        xx = self.ui.spinBox_range_x.value()
        yy = self.ui.spinBox_range_y.value()
        zz = self.ui.spinBox_range_z.value()

        calib_xx = self.ui.spinBox_calib_x.value()
        calib_yy = self.ui.spinBox_calib_y.value()
        calib_zz = self.ui.spinBox_calib_z.value()

        if self.CHANNELS == 49:
            self.setRegistersDict(
                {
                    "49_enable": True
                }
            )
        else:
            self.setRegistersDict(
                {
                    "49_enable": False
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

        start_offset = np.asarray(
            [
                offset_xx - (0.5 * xx / calib_xx) + offExtra_x_V,
                offset_yy - (0.5 * yy / calib_yy) + offExtra_y_V,
                offset_zz - (0.5 * zz / calib_zz) + offExtra_z_V,
            ]
        )

        self.setRegistersDict(
            {
                "CalibrationFactors(V/step)": calibration_v_step,
                "Offset/StartValue (V)": start_offset,
                "#pixels": numbers_xx,
                "#lines": numbers_yy,
                "#frames": numbers_ff,
                "#repetition": numbers_repetition + 1,
                "LaserEnable0": laserEnable0,
                "LaserEnable1": laserEnable1,
                "LaserEnable2": laserEnable2,
                "LaserEnable3": laserEnable3,
            }
        )

        self.configurationFPGA_dict.update(
            self.spadfcsmanager_inst.registers_configuration
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

        print_dec(self.rect_roi.state)

        # self.rect_roi_modified_lock = False
        self.timerPreviewImg.start()

        print_dec(self.rect_roi.state)
        self.updateMaxMinVoltages()

        self.analogOutChanged()
        self.configure_analog()

        if do_run:
            self.activateFIFOflag()
        self.activateShowPreview(self.ui.checkBox_showPreview.isChecked())

        # self.pmtThresholdChanged()

        self.snake_walk_Activate = self.ui.checkBox_snake.isChecked()
        self.spadfcsmanager_inst.set_activate_snake_walk(self.snake_walk_Activate)

        self.setRegistersDict({"snake": self.snake_walk_Activate})

        laser_debug = self.ui.checkBox_DFD_LaserDebug.isChecked()
        self.setRegistersDict({"DFD_LaserSyncDebug": laser_debug})

        self.spadfcsmanager_inst.set_activate_preview(activate_preview)

        filename_for_ttm = self.defineFilename(with_folder=False)
        if self.ttm_remote_is_up() and not activate_preview:
            self.ttm_remote_manager.set_folder_name_remote(
                self.ui.lineEdit_ttm_filename.text()
            )
            self.ttm_remote_manager.set_file_name_remote(
                filename_for_ttm.replace(".h5", ".ttr")
            )

        filename = self.defineFilename(with_folder=True)
        self.spadfcsmanager_inst.set_filename_h5(filename)
        self.spadfcsmanager_inst.set_autocorrelation_maxx(
            self.ui.spinBox_FCSbins.value()
        )

        if self.DFD_Activate:
            trace_bins = self.DFD_nbins

            trace_length = self.DFD_nbins

            trace_sample_per_bins = int(trace_length // trace_bins)

            print_dec("trace_bins", trace_bins)
            print_dec("trace_length", trace_length)
            print_dec("trace_sample_per_bins", trace_sample_per_bins)

            self.spadfcsmanager_inst.set_trace_bins(trace_bins=trace_bins)
            self.spadfcsmanager_inst.set_trace_sample_per_bins(
                trace_sample_per_bins=trace_sample_per_bins
            )
        else:
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

            print_dec("trace_bins", trace_bins)
            print_dec("trace_length", trace_length)
            print_dec("trace_sample_per_bins", trace_sample_per_bins)

            self.spadfcsmanager_inst.set_trace_bins(trace_bins=trace_bins)
            self.spadfcsmanager_inst.set_trace_sample_per_bins(
                trace_sample_per_bins=trace_sample_per_bins
            )

            self.ui.label_trace_total_bins.setText("%s" % trace_sample_per_bins)
            self.ui.label_actual_buffer_size.setText(
                "%d" % self.spadfcsmanager_inst.fpga_handle.get_actual_depth()
            )

        # self.spadfcsmanager_inst.acquistion_run()
        if self.ttm_remote_is_up() and not activate_preview:
            self.ttm_remote_manager.start_ttm_recv()

        self.spadfcsmanager_inst.run()

        self.plugin_signals.signal.emit("beforeRun")

        if do_run:
            self.sendCmdRun()

        self.update_fingerprint_mask()

    @Slot()
    def test_analog_digital(self):
        """experimental mixed analog and digital mode"""
        print_dec("test_analog_digital()")
        self.ui.radioButton_analog.setAutoExclusive(False)
        self.ui.radioButton_digital.setAutoExclusive(False)
        print_dec("now the ratioButton can be on at the same time")

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
        print_dec("Configure Analog")
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
                "AnalogA0 integrate": self.ui.checkBox_analog_in_integrate_AI0.isChecked(),
                "AnalogA0 invert": self.ui.checkBox_analog_in_invert_AI0.isChecked(),
                "AnalogA1 integrate": self.ui.checkBox_analog_in_integrate_AI1.isChecked(),
                "AnalogA1 invert": self.ui.checkBox_analog_in_invert_AI1.isChecked(),
                "AnalogA2 integrate": self.ui.checkBox_analog_in_integrate_AI2.isChecked(),
                "AnalogA2 invert": self.ui.checkBox_analog_in_invert_AI2.isChecked(),
                "AnalogA3 integrate": self.ui.checkBox_analog_in_integrate_AI3.isChecked(),
                "AnalogA3 invert": self.ui.checkBox_analog_in_invert_AI3.isChecked(),
                "AnalogInputA": self.ui.comboBox_analogSelect_A.currentIndex(),
                "AnalogInputB": self.ui.comboBox_analogSelect_B.currentIndex(),
                "AnalogA differential": self.ui.checkBox_analog_in_differentiate_A.isChecked(),
                "AnalogB differential": self.ui.checkBox_analog_in_differentiate_B.isChecked(),
            }
        )

    def activateShowPreview(self, enable):
        """
        activate the preview mode
        """
        self.spadfcsmanager_inst.activateShowPreview(enable)

    def activateFIFOflag(self):
        """
        activate the FIFO flag
        """

        print_dec("activateFIFOflag")
        print_dec("DFD", self.DFD_Activate)

        fifo = []
        if self.ui.radioButton_digital.isChecked():
            fifo.append("FIFO")
        if self.ui.radioButton_analog.isChecked():
            fifo.append("FIFOAnalog")

        self.spadfcsmanager_inst.setActivatedFifo(fifo)

        if self.DFD_Activate:
            self.setRegistersDict(
                {
                    "DFD_Activate": True,
                    "activateFIFOAnalog": self.ui.radioButton_analog.isChecked(),
                    "activateFIFODigital": self.ui.radioButton_digital.isChecked(),
                }
            )
        else:
            self.setRegistersDict(
                {
                    "DFD_Activate": False,
                    "activateFIFOAnalog": self.ui.radioButton_analog.isChecked(),
                    "activateFIFODigital": self.ui.radioButton_digital.isChecked(),
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

        # print_dec("Panorama")
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
        # print_dec(pos_x, pos_y, size_x, size_y)
        # self.im_widget_panorama.setItem(img)


    @Slot()
    def grabPanorama(self):
        """
        grab the panorama image
        """
        print_dec("Panorama")

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
        print_dec(pos_x, pos_y, size_x, size_y)
        # self.im_widget_panorama.setItem(img)

    def updatePreviewConfiguration(self):
        """
        update the preview configuration - channel selection
        """
        print_dec("updatePreviewConfiguration")

        t = self.ui.comboBox_plot_channel.currentText()
        self.ui.label_plot_channel.setText("Ch. selected: %s" % t.upper())

        if t.isnumeric():
            self.selected_channel = int(t)
        else:
            self.selected_channel = t

        self.spadfcsmanager_inst.update_shared_dict(
            {
                "proj": self.ui.comboBox_view_projection.currentText(),
                "channel": self.selected_channel,
                "activate_autocorrelation": self.ui.checkBox_fcs_preview.isChecked(),
                "activate_trace": self.ui.checkBox_trace_on.isChecked(),
            }
        )
        print_dec(self.spadfcsmanager_inst.read_shared_dict())

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
                print_dec("FILE EXISTS")
        print_dec(filename)
        if with_folder:
            return folder + filename
        else:
            return filename

    @Slot()
    def start(self):
        """
        start the acquisition
        """
        print_dec("start()")

        if self.ui.checkBox_ttmActivate.isChecked():
            self.ttm_activate_change_state()

        # self.myfpgainst.acquisitionThread.reset_data()
        self.ui.pushButton_acquisitionStart.setEnabled(False)
        self.ui.pushButton_stop.setEnabled(True)

        if not self.spadfcsmanager_inst.is_connected:
            print_dec("not self.spadfcsmanager_inst.is_connected")
            self.connectFPGA()
        else:
            print_dec("FPGA Already connected!")

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

        self.old_status_lockmovecheckbox = self.ui.checkBox_lockMove.isChecked()
        self.ui.checkBox_lockMove.setChecked(True)
        self.startAcquisition()

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
                    print_dec("self.ui.radioButton_ttm_local.isChecked()==True")
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
        print_dec("check if ttm_remote_is_up")
        if self.ttm_remote_manager is not None:
            if self.ttm_remote_manager.is_ready():
                return True
        return False

    @Slot()
    def checkAlerts(self):
        """
        check the GUI alerts i.e. potential wrong parameters
        """
        print_dec("checkAlerts")

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
        self.ui.radioButton_analog.setStyleSheet("")
        self.ui.radioButton_digital.setStyleSheet("")

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
                not self.ui.radioButton_analog.isChecked()
        ):
            self.ui.comboBox_plot_channel.setStyleSheet("border: 1px solid red;")
            self.ui.radioButton_analog.setStyleSheet("border: 1px solid red;")

        if not ("analog" in (self.ui.comboBox_plot_channel.currentText().lower())) and (
                not self.ui.radioButton_digital.isChecked()
        ):
            self.ui.comboBox_plot_channel.setStyleSheet("border: 1px solid red;")
            self.ui.radioButton_digital.setStyleSheet("border: 1px solid red;")

        if self.ui.radioButton_digital.isChecked():
            self.ui.checkBox_DFD.setEnabled(True)
        else:
            self.ui.checkBox_DFD.setEnabled(False)

    def previewLoop(self):
        """
        the actual preview loop
        """
        print_dec("previewLoop <======================================================")

        self.nrepetition_before_run_preview = self.ui.spinBox_nrepetition.value()

        old_lock = self.lockspatialSettingsChanged
        self.lockspatialSettingsChanged = True
        self.ui.spinBox_nrepetition.setValue(30000)
        self.ui.spinBox_nx.setEnabled(0)
        self.ui.spinBox_ny.setEnabled(0)
        self.ui.spinBox_nframe.setEnabled(0)
        self.ui.spinBox_nrepetition.setEnabled(0)
        self.lockspatialSettingsChanged = old_lock

        # self.myfpgainst.acquisitionThread.reset_data()
        if not self.spadfcsmanager_inst.is_connected:
            print_dec("not self.spadfcsmanager_inst.is_connected")
            self.connectFPGA()

        self.positionSettingsChanged_apply()
        self.temporalSettingsChanged()
        self.plotSettingsChanged()

        print_dec("Start")
        self.currentImage = None
        self.activeFile = False

        self.ui.pushButton_previewStart.setEnabled(False)
        self.ui.pushButton_acquisitionStart.setEnabled(False)
        self.ui.pushButton_externalProgram.setEnabled(False)

        self.started_normal = False
        self.started_preview = True

        self.rect_roi.hide()

        self.ui.progressBar_repetition.setValue(0)
        self.ui.progressBar_frame.setMaximum(0)

        self.old_status_lockmovecheckbox = self.ui.checkBox_lockMove.isChecked()

        self.startAcquisition(activate_preview=True)

        self.ui.pushButton_stop.setEnabled(True)

    @Slot()
    def projChanged(self):
        print_dec("projChanged()")
        self.plotPreviewImage()

        if self.ui.checkBox_lockMove.isChecked():
            print_dec("self.im_widget.autoRange()")
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
        print_dec("finalizeAcquisition")

        if self.started_normal:
            print_dec(self.spadfcsmanager_inst.shared_dict)
            self.last_saved_filename = self.spadfcsmanager_inst.shared_dict[
                "filenameh5"
            ]

            h5mgr = H5Manager(self.last_saved_filename, new_file=False)

            comment = self.ui.lineEdit_comment.toPlainText()
            self.ui.lineEdit_comment.setText("")
            self.ui.listWidget.addItem(self.last_saved_filename + "   " + comment)
            print_dec("saveHDF()")

            h5mgr.metadata_add_initial(comment)

            h5mgr.metadata_add_dict(
                "configurationSpadFCSmanager",
                self.spadfcsmanager_inst.registers_configuration,
            )

            h5mgr.metadata_add_dict("configurationFPGA", self.configurationFPGA_dict)

            h5mgr.metadata_add_dict("configurationGUI", self.getGUI_data())

            h5mgr.metadata_add_dict(
                "configurationGUI_beforeStart", self.configurationGUI_dict_beforeStart
            )

            h5mgr.metadata_add_thumbnail(self.im_widget.imageItem)
            h5mgr.print_keys()

            print_dec("currentImage_size", self.currentImage_size)
            print_dec("currentImage_pos", self.currentImage_pos)
            print_dec("currentImage_pixels", self.currentImage_pixels)

            self.stop()

            if self.started_normal:
                self.finalizeImage()

            h5mgr.close()

            if self.ttm_remote_is_up():
                self.ttm_remote_manager.wait_ttm_filename(self.ui.listWidget.addItem)

            self.ui.pushButton_externalProgram.setEnabled(True)
            self.plugin_signals.signal.emit(
                "acquisitionDone %s" % self.last_saved_filename
            )

            try:
                self.dfd_page.lineEdit_file_meas.setText(self.last_saved_filename)
            except:
                print_dec(
                    "Failed to dfd_page.lineEdit_file_meas.setText(last_saved_filename) "
                )

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
        print_dec("analog_before_stop()")

        mydict = {}
        for ch in range(0, 8):
            if self.ui.checkBox_AnalogOut[ch].isChecked() == True:
                print_dec("AnalogOutDC_%d set to 0V as requested" % ch)
                mydict["AnalogOutDC_%d" % ch] = 0

        self.setRegistersDict(mydict)
        # time.sleep(0.2)

    def stopAcquisition(self):
        """
        stop the acquisition
        """
        print_dec("stopAcquisition")
        self.sendCmdStop()
        self.spadfcsmanager_inst.stopPreview()
        self.timerPreviewImg.stop()
        print_dec("self.timerPreviewImg.stop()")
        self.spadfcsmanager_inst.stopFPGA()
        self.spadfcsmanager_inst.stopAcquisition()
        self.spadfcsmanager_inst.stopPreview()

    @Slot()
    def stop(self):
        """
        stop the acquisition clicked event
        """
        self.analog_before_stop()
        print_dec("GUI.Stop")

        if self.ttm_remote_is_up() and not self.activate_preview:
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
        self.ui.checkBox_lockMove.setChecked(self.old_status_lockmovecheckbox)
        self.stopAcquisition()

        # self.timerPreviewImg.stop()
        self.update()
        self.repaint()

        self.started_normal = False
        self.started_preview = False

    # @Slot()
    # def connectCmd(self):
    #     print_dec("Connect FPGA")
    #     self.connectFPGA()

    # @Slot()
    # def Connect(self):
    #     self.connectFPGA()

    def sendCmdRun(self):
        """
        send the run command to the FPGA
        """
        self.setRegistersDict({"stop": False, "Run": False})
        self.setRegistersDict({"Run": True})

    def sendCmdStop(self):
        """
        send the stop command to the FPGA
        """
        self.setRegistersDict({"stop": False})
        self.setRegistersDict({"stop": True})

    def getPreviewImage(self, projection="xy", rgb=False):
        """
        get the preview image
        """
        if self.spadfcsmanager_inst.shared_arrays_ready:
            # print_dec("ready self.spadfcsmanager_inst.shared_arrays_ready")
            return self.spadfcsmanager_inst.getPreviewImage(projection, rgb)
        else:
            print_dec("not ready self.spadfcsmanager_inst.shared_arrays_ready")
            print_dec("getPreviewImage DUMMY")
            return self.currentImage  # DUMMY

    def getPreviewFlatData(self):
        """
        get the preview flat data
        """
        if not self.activeFile:
            return self.spadfcsmanager_inst.getPreviewFlatData()
        else:
            print_dec("self.myfpgainst.getImage() TO BE WRITTEN FOR FILES")

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
            if ch.startswith("RGB"):
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


        if ch.startswith("RGB"):
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
            print_dec("NOT IMPLEMENTED BOH!!")
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
        (preview_img,
         ch,
         autoLevels,
         autoRange,
         pos,
         scale) = self.getCurrentPreviewImage(img)

        if ch.startswith("RGB"):
            print(preview_img.shape)
            self.im_widget.setImage(
                preview_img,
                levelMode="rgba",
                autoLevels=autoLevels,
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
        print_dec(self.currentImage.shape)
        print_dec("Calculating sum")
        img = np.sum(
            self.currentImage, axis=(0, 1, 4)
        )  # sum over bin, repetition, and frame
        print_dec(img.shape)
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
            print_dec(
                "Total photon [%d]",
                self.selected_channel,
                img[:, :, self.selected_channel].sum(),
            )
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
            print_dec("Total photon [sum]", self.selected_channel, img[:].sum())

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
        self.SaveConfiguration()

    @Slot()
    def SaveConfiguration(self):
        """
        save the configuration to a .cfg file
        """
        configuration = self.getGUI_data()
        filecfg = QFileDialog().getSaveFileName(
            caption="Save Configuration",
            filter="Config File (*.cfg)",
            dir=self.ui.lineEdit_configurationfile.text(),
        )[0]
        if filecfg != "":
            text = json.dumps(self.getGUI_data(), cls=NumpyEncoder)
            print_dec(text)

            with open(filecfg, "w") as file:
                file.write(text.replace(",", ",\n"))
                self.ui.statusBar.showMessage("%s saved." % filecfg, 5000)

            current_folder = QDir.fromNativeSeparators(os.getcwd()) + "/"

            print_dec(filecfg)
            print_dec(current_folder)

            filecfg_nicer = filecfg.replace(current_folder, "")
            self.ui.lineEdit_configurationfile.setText(filecfg_nicer)

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
        print_dec("Load_Configuration'", filecfg, "'")

        if filecfg == "":
            filecfg = QFileDialog.getOpenFileName(
                self,
                caption="Save Configuration",
                filter="Config File (*.cfg)",
                dir=self.ui.lineEdit_configurationfile.text(),
            )[0]

            current_folder = QDir.fromNativeSeparators(os.getcwd()) + "/"
            print_dec(filecfg)
            print_dec(current_folder)

            file_cfg_nicer = filecfg.replace(current_folder, "")

            if file_cfg_nicer.strip() != "":
                self.ask_to_save_cfg_as_permanent(file_cfg_nicer)

        if filecfg != "":
            print("filecfg", filecfg)
            with open(filecfg, "r") as file:
                text = file.read().replace(", \n", ",")
                mydict = dict(json.loads(text))
                print_dec(mydict)
                l1 = self.lock_parameters_changed_call
                l2 = self.lock_range_changing

                self.lock_parameters_changed_call = True
                self.lock_range_changing = True

                self.setGUI_data(mydict)

                self.lock_parameters_changed_call = l1
                self.lock_range_changing = l2

                self.updatePixelValueChanged()

                self.ui.statusBar.showMessage(
                    "%s opened and GUI configuration updated." % filecfg, 5000
                )
                self.ui.label_loadedcfg.setText(filecfg)

                try:
                    self.dfd_page.UpdateTable()
                except:
                    print("self.dfd_page.UpdateTable() FAILED")
                    pass

    @Slot()
    def openInExplorer(self):
        folder_path = os.path.abspath((self.ui.lineEdit_destinationfolder.text().replace("/","\\")))
        print_dec(folder_path)
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


class NumpyEncoder(json.JSONEncoder):
    """
    helper class for encoding numpy arrays to json
    """
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return json.JSONEncoder.default(self, obj)

