# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'main_window_design.ui'
##
## Created by: Qt User Interface Compiler version 6.9.0
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QComboBox,
    QDockWidget, QDoubleSpinBox, QGridLayout, QGroupBox,
    QHBoxLayout, QHeaderView, QLabel, QLayout,
    QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
    QProgressBar, QPushButton, QRadioButton, QScrollArea,
    QSizePolicy, QSpacerItem, QSpinBox, QStatusBar,
    QTabWidget, QTableWidget, QTableWidgetItem, QTextEdit,
    QToolButton, QTreeView, QVBoxLayout, QWidget)

from .scispinbox import sciSpinBox

class Ui_MainWindowDesign(object):
    def setupUi(self, MainWindowDesign):
        if not MainWindowDesign.objectName():
            MainWindowDesign.setObjectName(u"MainWindowDesign")
        MainWindowDesign.resize(1667, 1838)
        self.centralwidget = QWidget(MainWindowDesign)
        self.centralwidget.setObjectName(u"centralwidget")
        self.gridLayout_2 = QGridLayout(self.centralwidget)
        self.gridLayout_2.setObjectName(u"gridLayout_2")
        self.gridLayout_11 = QGridLayout()
        self.gridLayout_11.setObjectName(u"gridLayout_11")
        self.tabWidget = QTabWidget(self.centralwidget)
        self.tabWidget.setObjectName(u"tabWidget")
        self.tabWidget.setMovable(True)
        self.tab_preview = QWidget()
        self.tab_preview.setObjectName(u"tab_preview")
        self.gridLayout_32 = QGridLayout(self.tab_preview)
        self.gridLayout_32.setObjectName(u"gridLayout_32")
        self.gridLayout_im = QGridLayout()
        self.gridLayout_im.setObjectName(u"gridLayout_im")
        self.verticalSpacer_5 = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.gridLayout_im.addItem(self.verticalSpacer_5, 0, 0, 1, 1)

        self.gridLayout_4 = QGridLayout()
        self.gridLayout_4.setObjectName(u"gridLayout_4")
        self.comboBox_view_projection = QComboBox(self.tab_preview)
        self.comboBox_view_projection.addItem("")
        self.comboBox_view_projection.addItem("")
        self.comboBox_view_projection.addItem("")
        self.comboBox_view_projection.addItem("")
        self.comboBox_view_projection.addItem("")
        self.comboBox_view_projection.addItem("")
        self.comboBox_view_projection.setObjectName(u"comboBox_view_projection")

        self.gridLayout_4.addWidget(self.comboBox_view_projection, 0, 3, 1, 1)

        self.checkBox_autoscale_img = QCheckBox(self.tab_preview)
        self.checkBox_autoscale_img.setObjectName(u"checkBox_autoscale_img")
        self.checkBox_autoscale_img.setChecked(True)

        self.gridLayout_4.addWidget(self.checkBox_autoscale_img, 2, 0, 1, 1)

        self.label_plot_ch = QLabel(self.tab_preview)
        self.label_plot_ch.setObjectName(u"label_plot_ch")

        self.gridLayout_4.addWidget(self.label_plot_ch, 2, 2, 1, 1)

        self.comboBox_plot_channel = QComboBox(self.tab_preview)
        self.comboBox_plot_channel.addItem("")
        self.comboBox_plot_channel.addItem("")
        self.comboBox_plot_channel.addItem("")
        self.comboBox_plot_channel.addItem("")
        self.comboBox_plot_channel.addItem("")
        self.comboBox_plot_channel.addItem("")
        self.comboBox_plot_channel.addItem("")
        self.comboBox_plot_channel.addItem("")
        self.comboBox_plot_channel.addItem("")
        self.comboBox_plot_channel.addItem("")
        self.comboBox_plot_channel.addItem("")
        self.comboBox_plot_channel.addItem("")
        self.comboBox_plot_channel.addItem("")
        self.comboBox_plot_channel.addItem("")
        self.comboBox_plot_channel.addItem("")
        self.comboBox_plot_channel.addItem("")
        self.comboBox_plot_channel.addItem("")
        self.comboBox_plot_channel.addItem("")
        self.comboBox_plot_channel.addItem("")
        self.comboBox_plot_channel.addItem("")
        self.comboBox_plot_channel.addItem("")
        self.comboBox_plot_channel.addItem("")
        self.comboBox_plot_channel.addItem("")
        self.comboBox_plot_channel.addItem("")
        self.comboBox_plot_channel.addItem("")
        self.comboBox_plot_channel.addItem("")
        self.comboBox_plot_channel.addItem("")
        self.comboBox_plot_channel.addItem("")
        self.comboBox_plot_channel.setObjectName(u"comboBox_plot_channel")
        self.comboBox_plot_channel.setEditable(True)

        self.gridLayout_4.addWidget(self.comboBox_plot_channel, 2, 3, 1, 1)

        self.label_60 = QLabel(self.tab_preview)
        self.label_60.setObjectName(u"label_60")

        self.gridLayout_4.addWidget(self.label_60, 0, 2, 1, 1)

        self.checkBox_lockMove = QCheckBox(self.tab_preview)
        self.checkBox_lockMove.setObjectName(u"checkBox_lockMove")

        self.gridLayout_4.addWidget(self.checkBox_lockMove, 0, 0, 1, 1)

        self.horizontalSpacer_13 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.gridLayout_4.addItem(self.horizontalSpacer_13, 0, 4, 1, 1)

        self.label_106 = QLabel(self.tab_preview)
        self.label_106.setObjectName(u"label_106")

        self.gridLayout_4.addWidget(self.label_106, 0, 5, 1, 1)

        self.label_107 = QLabel(self.tab_preview)
        self.label_107.setObjectName(u"label_107")

        self.gridLayout_4.addWidget(self.label_107, 2, 5, 1, 1)


        self.gridLayout_im.addLayout(self.gridLayout_4, 2, 0, 1, 1)


        self.gridLayout_32.addLayout(self.gridLayout_im, 0, 1, 1, 1)

        self.tabWidget.addTab(self.tab_preview, "")
        self.tab_fcs = QWidget()
        self.tab_fcs.setObjectName(u"tab_fcs")
        self.gridLayout_39 = QGridLayout(self.tab_fcs)
        self.gridLayout_39.setObjectName(u"gridLayout_39")
        self.gridLayout_44 = QGridLayout()
        self.gridLayout_44.setObjectName(u"gridLayout_44")
        self.horizontalSpacer_8 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.gridLayout_44.addItem(self.horizontalSpacer_8, 0, 4, 1, 1)

        self.pushButton_13 = QPushButton(self.tab_fcs)
        self.pushButton_13.setObjectName(u"pushButton_13")

        self.gridLayout_44.addWidget(self.pushButton_13, 0, 5, 2, 1)

        self.pushButton_copyPositionsMarkersFCS = QPushButton(self.tab_fcs)
        self.pushButton_copyPositionsMarkersFCS.setObjectName(u"pushButton_copyPositionsMarkersFCS")

        self.gridLayout_44.addWidget(self.pushButton_copyPositionsMarkersFCS, 1, 2, 1, 1)

        self.pushButton_copyPositionsMarkers = QPushButton(self.tab_fcs)
        self.pushButton_copyPositionsMarkers.setObjectName(u"pushButton_copyPositionsMarkers")

        self.gridLayout_44.addWidget(self.pushButton_copyPositionsMarkers, 0, 2, 1, 1)

        self.pushButton_currentConfToBatch = QPushButton(self.tab_fcs)
        self.pushButton_currentConfToBatch.setObjectName(u"pushButton_currentConfToBatch")

        self.gridLayout_44.addWidget(self.pushButton_currentConfToBatch, 0, 1, 1, 1)

        self.pushButton_currentConfToBatchFCS = QPushButton(self.tab_fcs)
        self.pushButton_currentConfToBatchFCS.setObjectName(u"pushButton_currentConfToBatchFCS")

        self.gridLayout_44.addWidget(self.pushButton_currentConfToBatchFCS, 1, 1, 1, 1)

        self.label_103 = QLabel(self.tab_fcs)
        self.label_103.setObjectName(u"label_103")

        self.gridLayout_44.addWidget(self.label_103, 1, 3, 1, 1)


        self.gridLayout_39.addLayout(self.gridLayout_44, 0, 0, 1, 1)

        self.tableWidget = QTableWidget(self.tab_fcs)
        self.tableWidget.setObjectName(u"tableWidget")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.tableWidget.sizePolicy().hasHeightForWidth())
        self.tableWidget.setSizePolicy(sizePolicy)
        font = QFont()
        font.setFamilies([u"MS Shell Dlg 2"])
        font.setPointSize(8)
        self.tableWidget.setFont(font)
        self.tableWidget.setRowCount(0)
        self.tableWidget.setColumnCount(0)
        self.tableWidget.horizontalHeader().setMinimumSectionSize(21)
        self.tableWidget.verticalHeader().setDefaultSectionSize(21)

        self.gridLayout_39.addWidget(self.tableWidget, 2, 0, 1, 1)

        self.gridLayout_FCS = QGridLayout()
        self.gridLayout_FCS.setObjectName(u"gridLayout_FCS")
        self.gridLayout_FCS.setSizeConstraint(QLayout.SizeConstraint.SetMaximumSize)

        self.gridLayout_39.addLayout(self.gridLayout_FCS, 4, 0, 1, 1)

        self.gridLayout_40 = QGridLayout()
        self.gridLayout_40.setObjectName(u"gridLayout_40")
        self.horizontalLayout_2 = QHBoxLayout()
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.horizontalSpacer_3 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_2.addItem(self.horizontalSpacer_3)

        self.label_68 = QLabel(self.tab_fcs)
        self.label_68.setObjectName(u"label_68")

        self.horizontalLayout_2.addWidget(self.label_68)

        self.label_69 = QLabel(self.tab_fcs)
        self.label_69.setObjectName(u"label_69")

        self.horizontalLayout_2.addWidget(self.label_69)

        self.spinBox_FCSbins = QSpinBox(self.tab_fcs)
        self.spinBox_FCSbins.setObjectName(u"spinBox_FCSbins")
        self.spinBox_FCSbins.setMinimum(1)
        self.spinBox_FCSbins.setMaximum(30)
        self.spinBox_FCSbins.setValue(20)

        self.horizontalLayout_2.addWidget(self.spinBox_FCSbins)

        self.pushButton_FCS_reset = QPushButton(self.tab_fcs)
        self.pushButton_FCS_reset.setObjectName(u"pushButton_FCS_reset")

        self.horizontalLayout_2.addWidget(self.pushButton_FCS_reset)


        self.gridLayout_40.addLayout(self.horizontalLayout_2, 4, 0, 1, 1)

        self.progressBar_batch = QProgressBar(self.tab_fcs)
        self.progressBar_batch.setObjectName(u"progressBar_batch")
        self.progressBar_batch.setEnabled(False)
        self.progressBar_batch.setValue(0)

        self.gridLayout_40.addWidget(self.progressBar_batch, 0, 0, 1, 1)

        self.pushButton_12 = QPushButton(self.tab_fcs)
        self.pushButton_12.setObjectName(u"pushButton_12")

        self.gridLayout_40.addWidget(self.pushButton_12, 2, 1, 1, 1)

        self.label_batch = QLabel(self.tab_fcs)
        self.label_batch.setObjectName(u"label_batch")

        self.gridLayout_40.addWidget(self.label_batch, 2, 0, 1, 1)

        self.pushButton_startBatchFCS = QPushButton(self.tab_fcs)
        self.pushButton_startBatchFCS.setObjectName(u"pushButton_startBatchFCS")

        self.gridLayout_40.addWidget(self.pushButton_startBatchFCS, 0, 1, 1, 1)

        self.checkBox_fcs_preview = QCheckBox(self.tab_fcs)
        self.checkBox_fcs_preview.setObjectName(u"checkBox_fcs_preview")

        self.gridLayout_40.addWidget(self.checkBox_fcs_preview, 4, 1, 1, 1)


        self.gridLayout_39.addLayout(self.gridLayout_40, 3, 0, 1, 1)

        self.tabWidget.addTab(self.tab_fcs, "")
        self.tab_statusmonitor = QWidget()
        self.tab_statusmonitor.setObjectName(u"tab_statusmonitor")
        self.gridLayout = QGridLayout(self.tab_statusmonitor)
        self.gridLayout.setObjectName(u"gridLayout")
        self.checkBox_updateStatus = QCheckBox(self.tab_statusmonitor)
        self.checkBox_updateStatus.setObjectName(u"checkBox_updateStatus")
        self.checkBox_updateStatus.setChecked(False)

        self.gridLayout.addWidget(self.checkBox_updateStatus, 0, 0, 1, 1)

        self.horizontalSpacer_11 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.gridLayout.addItem(self.horizontalSpacer_11, 0, 1, 1, 1)

        self.tabWidget_circular = QTabWidget(self.tab_statusmonitor)
        self.tabWidget_circular.setObjectName(u"tabWidget_circular")
        self.tab_10 = QWidget()
        self.tab_10.setObjectName(u"tab_10")
        self.gridLayout_10 = QGridLayout(self.tab_10)
        self.gridLayout_10.setObjectName(u"gridLayout_10")
        self.treeView = QTreeView(self.tab_10)
        self.treeView.setObjectName(u"treeView")

        self.gridLayout_10.addWidget(self.treeView, 0, 0, 1, 1)

        self.tabWidget_circular.addTab(self.tab_10, "")
        self.tab_11 = QWidget()
        self.tab_11.setObjectName(u"tab_11")
        self.gridLayout_31 = QGridLayout(self.tab_11)
        self.gridLayout_31.setObjectName(u"gridLayout_31")
        self.treeView_2 = QTreeView(self.tab_11)
        self.treeView_2.setObjectName(u"treeView_2")

        self.gridLayout_31.addWidget(self.treeView_2, 0, 0, 1, 1)

        self.tabWidget_circular.addTab(self.tab_11, "")
        self.tab_3 = QWidget()
        self.tab_3.setObjectName(u"tab_3")
        self.gridLayout_34 = QGridLayout(self.tab_3)
        self.gridLayout_34.setObjectName(u"gridLayout_34")
        self.treeView_3 = QTreeView(self.tab_3)
        self.treeView_3.setObjectName(u"treeView_3")

        self.gridLayout_34.addWidget(self.treeView_3, 0, 0, 1, 1)

        self.tabWidget_circular.addTab(self.tab_3, "")
        self.tab_4 = QWidget()
        self.tab_4.setObjectName(u"tab_4")
        self.gridLayout_50 = QGridLayout(self.tab_4)
        self.gridLayout_50.setObjectName(u"gridLayout_50")
        self.treeView_4 = QTreeView(self.tab_4)
        self.treeView_4.setObjectName(u"treeView_4")

        self.gridLayout_50.addWidget(self.treeView_4, 0, 0, 1, 1)

        self.tabWidget_circular.addTab(self.tab_4, "")

        self.gridLayout.addWidget(self.tabWidget_circular, 1, 0, 1, 2)

        self.tabWidget.addTab(self.tab_statusmonitor, "")
        self.tab_terminal = QWidget()
        self.tab_terminal.setObjectName(u"tab_terminal")
        self.gridLayout_56 = QGridLayout(self.tab_terminal)
        self.gridLayout_56.setObjectName(u"gridLayout_56")
        self.gridLayout_Terminal = QGridLayout()
        self.gridLayout_Terminal.setObjectName(u"gridLayout_Terminal")

        self.gridLayout_56.addLayout(self.gridLayout_Terminal, 0, 0, 1, 1)

        self.tabWidget.addTab(self.tab_terminal, "")

        self.gridLayout_11.addWidget(self.tabWidget, 0, 0, 1, 1)


        self.gridLayout_2.addLayout(self.gridLayout_11, 0, 0, 1, 1)

        MainWindowDesign.setCentralWidget(self.centralwidget)
        self.dockWidget_preview = QDockWidget(MainWindowDesign)
        self.dockWidget_preview.setObjectName(u"dockWidget_preview")
        self.dockWidget_preview.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetFloatable|QDockWidget.DockWidgetFeature.DockWidgetMovable)
        self.dockWidgetContents_8 = QWidget()
        self.dockWidgetContents_8.setObjectName(u"dockWidgetContents_8")
        self.gridLayout_15 = QGridLayout(self.dockWidgetContents_8)
        self.gridLayout_15.setObjectName(u"gridLayout_15")
        self.gridLayout_55 = QGridLayout()
        self.gridLayout_55.setObjectName(u"gridLayout_55")
        self.pushButton_previewStart = QPushButton(self.dockWidgetContents_8)
        self.pushButton_previewStart.setObjectName(u"pushButton_previewStart")

        self.gridLayout_55.addWidget(self.pushButton_previewStart, 0, 0, 1, 1)

        self.pushButton_acquisitionStart = QPushButton(self.dockWidgetContents_8)
        self.pushButton_acquisitionStart.setObjectName(u"pushButton_acquisitionStart")

        self.gridLayout_55.addWidget(self.pushButton_acquisitionStart, 0, 1, 1, 1)

        self.pushButton_14 = QPushButton(self.dockWidgetContents_8)
        self.pushButton_14.setObjectName(u"pushButton_14")

        self.gridLayout_55.addWidget(self.pushButton_14, 1, 1, 1, 1)

        self.pushButton_externalProgram = QPushButton(self.dockWidgetContents_8)
        self.pushButton_externalProgram.setObjectName(u"pushButton_externalProgram")
        self.pushButton_externalProgram.setEnabled(False)

        self.gridLayout_55.addWidget(self.pushButton_externalProgram, 2, 1, 1, 1)

        self.verticalLayout_2 = QVBoxLayout()
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.radioButton_digital = QRadioButton(self.dockWidgetContents_8)
        self.radioButton_digital.setObjectName(u"radioButton_digital")
        self.radioButton_digital.setChecked(True)

        self.verticalLayout_2.addWidget(self.radioButton_digital)

        self.radioButton_analog = QRadioButton(self.dockWidgetContents_8)
        self.radioButton_analog.setObjectName(u"radioButton_analog")

        self.verticalLayout_2.addWidget(self.radioButton_analog)

        self.checkBox_ttmActivate = QCheckBox(self.dockWidgetContents_8)
        self.checkBox_ttmActivate.setObjectName(u"checkBox_ttmActivate")

        self.verticalLayout_2.addWidget(self.checkBox_ttmActivate)

        self.checkBox_DFD = QCheckBox(self.dockWidgetContents_8)
        self.checkBox_DFD.setObjectName(u"checkBox_DFD")

        self.verticalLayout_2.addWidget(self.checkBox_DFD)


        self.gridLayout_55.addLayout(self.verticalLayout_2, 0, 2, 3, 1)

        self.pushButton_stop = QPushButton(self.dockWidgetContents_8)
        self.pushButton_stop.setObjectName(u"pushButton_stop")
        self.pushButton_stop.setEnabled(False)
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.pushButton_stop.sizePolicy().hasHeightForWidth())
        self.pushButton_stop.setSizePolicy(sizePolicy1)

        self.gridLayout_55.addWidget(self.pushButton_stop, 1, 0, 2, 1)


        self.gridLayout_15.addLayout(self.gridLayout_55, 0, 1, 1, 1)

        self.dockWidget_preview.setWidget(self.dockWidgetContents_8)
        MainWindowDesign.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.dockWidget_preview)
        self.dockWidget_temporal = QDockWidget(MainWindowDesign)
        self.dockWidget_temporal.setObjectName(u"dockWidget_temporal")
        self.dockWidget_temporal.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetFloatable|QDockWidget.DockWidgetFeature.DockWidgetMovable)
        self.dockWidgetContents_3 = QWidget()
        self.dockWidgetContents_3.setObjectName(u"dockWidgetContents_3")
        self.gridLayout_9 = QGridLayout(self.dockWidgetContents_3)
        self.gridLayout_9.setObjectName(u"gridLayout_9")
        self.gridLayout_8 = QGridLayout()
        self.gridLayout_8.setObjectName(u"gridLayout_8")
        self.spinBox_waitAfterFrame = QDoubleSpinBox(self.dockWidgetContents_3)
        self.spinBox_waitAfterFrame.setObjectName(u"spinBox_waitAfterFrame")
        self.spinBox_waitAfterFrame.setKeyboardTracking(False)
        self.spinBox_waitAfterFrame.setMaximum(3600000.000000000000000)

        self.gridLayout_8.addWidget(self.spinBox_waitAfterFrame, 4, 1, 1, 1)

        self.label_time_bin_per_px = QLabel(self.dockWidgetContents_3)
        self.label_time_bin_per_px.setObjectName(u"label_time_bin_per_px")

        self.gridLayout_8.addWidget(self.label_time_bin_per_px, 2, 0, 1, 1)

        self.checkBox_waitOnlyFirstTime = QCheckBox(self.dockWidgetContents_3)
        self.checkBox_waitOnlyFirstTime.setObjectName(u"checkBox_waitOnlyFirstTime")

        self.gridLayout_8.addWidget(self.checkBox_waitOnlyFirstTime, 3, 2, 1, 1)

        self.label_frame_time = QLabel(self.dockWidgetContents_3)
        self.label_frame_time.setObjectName(u"label_frame_time")

        self.gridLayout_8.addWidget(self.label_frame_time, 3, 0, 1, 1)

        self.spinBox_timeresolution = QDoubleSpinBox(self.dockWidgetContents_3)
        self.spinBox_timeresolution.setObjectName(u"spinBox_timeresolution")
        self.spinBox_timeresolution.setKeyboardTracking(False)
        self.spinBox_timeresolution.setMaximum(10000000000000.000000000000000)
        self.spinBox_timeresolution.setValue(1.000000000000000)

        self.gridLayout_8.addWidget(self.spinBox_timeresolution, 1, 1, 1, 1)

        self.spinBox_waitForLaser = QDoubleSpinBox(self.dockWidgetContents_3)
        self.spinBox_waitForLaser.setObjectName(u"spinBox_waitForLaser")
        self.spinBox_waitForLaser.setKeyboardTracking(False)
        self.spinBox_waitForLaser.setMaximum(3600000.000000000000000)

        self.gridLayout_8.addWidget(self.spinBox_waitForLaser, 3, 1, 1, 1)

        self.label_29 = QLabel(self.dockWidgetContents_3)
        self.label_29.setObjectName(u"label_29")

        self.gridLayout_8.addWidget(self.label_29, 4, 2, 1, 1)

        self.label_frame_time_2 = QLabel(self.dockWidgetContents_3)
        self.label_frame_time_2.setObjectName(u"label_frame_time_2")

        self.gridLayout_8.addWidget(self.label_frame_time_2, 4, 0, 1, 1)

        self.label_timeresolution = QLabel(self.dockWidgetContents_3)
        self.label_timeresolution.setObjectName(u"label_timeresolution")

        self.gridLayout_8.addWidget(self.label_timeresolution, 1, 0, 1, 1)

        self.checkBox_laserOffAfterMeas = QCheckBox(self.dockWidgetContents_3)
        self.checkBox_laserOffAfterMeas.setObjectName(u"checkBox_laserOffAfterMeas")
        self.checkBox_laserOffAfterMeas.setChecked(True)

        self.gridLayout_8.addWidget(self.checkBox_laserOffAfterMeas, 4, 3, 1, 1)

        self.spinBox_time_bin_per_px = QSpinBox(self.dockWidgetContents_3)
        self.spinBox_time_bin_per_px.setObjectName(u"spinBox_time_bin_per_px")
        self.spinBox_time_bin_per_px.setKeyboardTracking(False)
        self.spinBox_time_bin_per_px.setMaximum(100000)
        self.spinBox_time_bin_per_px.setValue(10)

        self.gridLayout_8.addWidget(self.spinBox_time_bin_per_px, 2, 1, 1, 1)

        self.label_dwell_time_2 = QLabel(self.dockWidgetContents_3)
        self.label_dwell_time_2.setObjectName(u"label_dwell_time_2")

        self.gridLayout_8.addWidget(self.label_dwell_time_2, 1, 2, 2, 1)

        self.label_dwell_time_val = QLabel(self.dockWidgetContents_3)
        self.label_dwell_time_val.setObjectName(u"label_dwell_time_val")

        self.gridLayout_8.addWidget(self.label_dwell_time_val, 1, 3, 2, 1)


        self.gridLayout_9.addLayout(self.gridLayout_8, 0, 0, 1, 1)

        self.dockWidget_temporal.setWidget(self.dockWidgetContents_3)
        MainWindowDesign.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.dockWidget_temporal)
        self.dockWidget_2 = QDockWidget(MainWindowDesign)
        self.dockWidget_2.setObjectName(u"dockWidget_2")
        self.dockWidget_2.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetFloatable|QDockWidget.DockWidgetFeature.DockWidgetMovable)
        self.dockWidgetContents_2 = QWidget()
        self.dockWidgetContents_2.setObjectName(u"dockWidgetContents_2")
        self.gridLayout_6 = QGridLayout(self.dockWidgetContents_2)
        self.gridLayout_6.setObjectName(u"gridLayout_6")
        self.gridLayout_5 = QGridLayout()
        self.gridLayout_5.setObjectName(u"gridLayout_5")
        self.gridLayout_5.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        self.spinBox_nrepetition = QSpinBox(self.dockWidgetContents_2)
        self.spinBox_nrepetition.setObjectName(u"spinBox_nrepetition")
        self.spinBox_nrepetition.setMinimum(1)
        self.spinBox_nrepetition.setMaximum(200000)
        self.spinBox_nrepetition.setValue(1)

        self.gridLayout_5.addWidget(self.spinBox_nrepetition, 3, 1, 1, 1)

        self.spinBox_ny = QSpinBox(self.dockWidgetContents_2)
        self.spinBox_ny.setObjectName(u"spinBox_ny")
        self.spinBox_ny.setMinimum(1)
        self.spinBox_ny.setMaximum(999999999)
        self.spinBox_ny.setValue(512)

        self.gridLayout_5.addWidget(self.spinBox_ny, 1, 1, 1, 1)

        self.label_104 = QLabel(self.dockWidgetContents_2)
        self.label_104.setObjectName(u"label_104")

        self.gridLayout_5.addWidget(self.label_104, 1, 2, 1, 1)

        self.label_nframe = QLabel(self.dockWidgetContents_2)
        self.label_nframe.setObjectName(u"label_nframe")

        self.gridLayout_5.addWidget(self.label_nframe, 2, 0, 1, 1)

        self.spinBox_nframe = QSpinBox(self.dockWidgetContents_2)
        self.spinBox_nframe.setObjectName(u"spinBox_nframe")
        self.spinBox_nframe.setMinimum(1)
        self.spinBox_nframe.setMaximum(999999999)
        self.spinBox_nframe.setValue(1)

        self.gridLayout_5.addWidget(self.spinBox_nframe, 2, 1, 1, 1)

        self.label_ny = QLabel(self.dockWidgetContents_2)
        self.label_ny.setObjectName(u"label_ny")

        self.gridLayout_5.addWidget(self.label_ny, 1, 0, 1, 1)

        self.label_nx = QLabel(self.dockWidgetContents_2)
        self.label_nx.setObjectName(u"label_nx")

        self.gridLayout_5.addWidget(self.label_nx, 0, 0, 1, 1)

        self.label_105 = QLabel(self.dockWidgetContents_2)
        self.label_105.setObjectName(u"label_105")

        self.gridLayout_5.addWidget(self.label_105, 0, 2, 1, 1)

        self.label_pixelsize_z = QLabel(self.dockWidgetContents_2)
        self.label_pixelsize_z.setObjectName(u"label_pixelsize_z")

        self.gridLayout_5.addWidget(self.label_pixelsize_z, 2, 3, 1, 1)

        self.label_pixelsize_x = QLabel(self.dockWidgetContents_2)
        self.label_pixelsize_x.setObjectName(u"label_pixelsize_x")

        self.gridLayout_5.addWidget(self.label_pixelsize_x, 0, 3, 1, 1)

        self.label_nrepetition = QLabel(self.dockWidgetContents_2)
        self.label_nrepetition.setObjectName(u"label_nrepetition")

        self.gridLayout_5.addWidget(self.label_nrepetition, 3, 0, 1, 1)

        self.label_101 = QLabel(self.dockWidgetContents_2)
        self.label_101.setObjectName(u"label_101")

        self.gridLayout_5.addWidget(self.label_101, 2, 2, 1, 1)

        self.spinBox_nx = QSpinBox(self.dockWidgetContents_2)
        self.spinBox_nx.setObjectName(u"spinBox_nx")
        self.spinBox_nx.setMinimum(1)
        self.spinBox_nx.setMaximum(999999999)
        self.spinBox_nx.setValue(512)

        self.gridLayout_5.addWidget(self.spinBox_nx, 0, 1, 1, 1)

        self.label_pixelsize_y = QLabel(self.dockWidgetContents_2)
        self.label_pixelsize_y.setObjectName(u"label_pixelsize_y")

        self.gridLayout_5.addWidget(self.label_pixelsize_y, 1, 3, 1, 1)

        self.pushButton_18 = QPushButton(self.dockWidgetContents_2)
        self.pushButton_18.setObjectName(u"pushButton_18")

        self.gridLayout_5.addWidget(self.pushButton_18, 3, 2, 1, 2)


        self.gridLayout_6.addLayout(self.gridLayout_5, 0, 0, 1, 1)

        self.dockWidget_2.setWidget(self.dockWidgetContents_2)
        MainWindowDesign.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.dockWidget_2)
        self.dockWidget_fingerprint = QDockWidget(MainWindowDesign)
        self.dockWidget_fingerprint.setObjectName(u"dockWidget_fingerprint")
        self.dockWidget_fingerprint.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetFloatable|QDockWidget.DockWidgetFeature.DockWidgetMovable)
        self.dockWidgetContents_5 = QWidget()
        self.dockWidgetContents_5.setObjectName(u"dockWidgetContents_5")
        self.gridLayout_12 = QGridLayout(self.dockWidgetContents_5)
        self.gridLayout_12.setObjectName(u"gridLayout_12")
        self.scrollArea_6 = QScrollArea(self.dockWidgetContents_5)
        self.scrollArea_6.setObjectName(u"scrollArea_6")
        self.scrollArea_6.setWidgetResizable(True)
        self.scrollAreaWidgetContents_4 = QWidget()
        self.scrollAreaWidgetContents_4.setObjectName(u"scrollAreaWidgetContents_4")
        self.scrollAreaWidgetContents_4.setGeometry(QRect(0, 0, 422, 148))
        self.gridLayout_68 = QGridLayout(self.scrollAreaWidgetContents_4)
        self.gridLayout_68.setObjectName(u"gridLayout_68")
        self.gridLayout_3434 = QGridLayout()
        self.gridLayout_3434.setObjectName(u"gridLayout_3434")
        self.gridLayout_3434.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        self.gridLayout_47 = QGridLayout()
        self.gridLayout_47.setObjectName(u"gridLayout_47")
        self.gridLayout_microimage = QGridLayout()
        self.gridLayout_microimage.setObjectName(u"gridLayout_microimage")

        self.gridLayout_47.addLayout(self.gridLayout_microimage, 0, 0, 4, 4)

        self.label_microimage = QLabel(self.scrollAreaWidgetContents_4)
        self.label_microimage.setObjectName(u"label_microimage")

        self.gridLayout_47.addWidget(self.label_microimage, 0, 4, 1, 1)

        self.comboBox_fingerprint = QComboBox(self.scrollAreaWidgetContents_4)
        self.comboBox_fingerprint.addItem("")
        self.comboBox_fingerprint.addItem("")
        self.comboBox_fingerprint.addItem("")
        self.comboBox_fingerprint.setObjectName(u"comboBox_fingerprint")
        sizePolicy2 = QSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.comboBox_fingerprint.sizePolicy().hasHeightForWidth())
        self.comboBox_fingerprint.setSizePolicy(sizePolicy2)
        self.comboBox_fingerprint.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)

        self.gridLayout_47.addWidget(self.comboBox_fingerprint, 0, 5, 1, 1)

        self.pushButton_4 = QPushButton(self.scrollAreaWidgetContents_4)
        self.pushButton_4.setObjectName(u"pushButton_4")

        self.gridLayout_47.addWidget(self.pushButton_4, 1, 4, 1, 2)

        self.checkBox_autoscale_fingerprint = QCheckBox(self.scrollAreaWidgetContents_4)
        self.checkBox_autoscale_fingerprint.setObjectName(u"checkBox_autoscale_fingerprint")
        self.checkBox_autoscale_fingerprint.setChecked(True)

        self.gridLayout_47.addWidget(self.checkBox_autoscale_fingerprint, 2, 4, 1, 2)

        self.verticalSpacer_15 = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.gridLayout_47.addItem(self.verticalSpacer_15, 3, 4, 1, 1)


        self.gridLayout_3434.addLayout(self.gridLayout_47, 0, 0, 1, 1)


        self.gridLayout_68.addLayout(self.gridLayout_3434, 0, 0, 1, 1)

        self.scrollArea_6.setWidget(self.scrollAreaWidgetContents_4)

        self.gridLayout_12.addWidget(self.scrollArea_6, 0, 0, 1, 1)

        self.dockWidget_fingerprint.setWidget(self.dockWidgetContents_5)
        MainWindowDesign.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dockWidget_fingerprint)
        self.dockWidget_trace = QDockWidget(MainWindowDesign)
        self.dockWidget_trace.setObjectName(u"dockWidget_trace")
        self.dockWidget_trace.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetFloatable|QDockWidget.DockWidgetFeature.DockWidgetMovable)
        self.dockWidgetContents_19 = QWidget()
        self.dockWidgetContents_19.setObjectName(u"dockWidgetContents_19")
        self.gridLayout_19 = QGridLayout(self.dockWidgetContents_19)
        self.gridLayout_19.setObjectName(u"gridLayout_19")
        self.gridLayout_trace = QGridLayout()
        self.gridLayout_trace.setObjectName(u"gridLayout_trace")

        self.gridLayout_19.addLayout(self.gridLayout_trace, 0, 0, 1, 1)

        self.dockWidget_trace.setWidget(self.dockWidgetContents_19)
        MainWindowDesign.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dockWidget_trace)
        self.dockWidget_statistics = QDockWidget(MainWindowDesign)
        self.dockWidget_statistics.setObjectName(u"dockWidget_statistics")
        self.dockWidget_statistics.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetFloatable|QDockWidget.DockWidgetFeature.DockWidgetMovable)
        self.dockWidgetContents_6 = QWidget()
        self.dockWidgetContents_6.setObjectName(u"dockWidgetContents_6")
        self.gridLayout_14 = QGridLayout(self.dockWidgetContents_6)
        self.gridLayout_14.setObjectName(u"gridLayout_14")
        self.gridLayout_13 = QGridLayout()
        self.gridLayout_13.setObjectName(u"gridLayout_13")
        self.gridLayout_13.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        self.progressBar_repetition = QProgressBar(self.dockWidgetContents_6)
        self.progressBar_repetition.setObjectName(u"progressBar_repetition")
        sizePolicy3 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        sizePolicy3.setHorizontalStretch(0)
        sizePolicy3.setVerticalStretch(0)
        sizePolicy3.setHeightForWidth(self.progressBar_repetition.sizePolicy().hasHeightForWidth())
        self.progressBar_repetition.setSizePolicy(sizePolicy3)
        self.progressBar_repetition.setStyleSheet(u"height: 8px;")
        self.progressBar_repetition.setValue(24)

        self.gridLayout_13.addWidget(self.progressBar_repetition, 9, 2, 1, 10)

        self.label_70 = QLabel(self.dockWidgetContents_6)
        self.label_70.setObjectName(u"label_70")

        self.gridLayout_13.addWidget(self.label_70, 8, 0, 1, 1)

        self.label_current_repetition_val = QLabel(self.dockWidgetContents_6)
        self.label_current_repetition_val.setObjectName(u"label_current_repetition_val")
        sizePolicy1.setHeightForWidth(self.label_current_repetition_val.sizePolicy().hasHeightForWidth())
        self.label_current_repetition_val.setSizePolicy(sizePolicy1)
        self.label_current_repetition_val.setAlignment(Qt.AlignmentFlag.AlignLeading|Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter)

        self.gridLayout_13.addWidget(self.label_current_repetition_val, 9, 1, 1, 1)

        self.label_expected_dur = QLabel(self.dockWidgetContents_6)
        self.label_expected_dur.setObjectName(u"label_expected_dur")
        self.label_expected_dur.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)

        self.gridLayout_13.addWidget(self.label_expected_dur, 4, 0, 1, 1)

        self.label_71 = QLabel(self.dockWidgetContents_6)
        self.label_71.setObjectName(u"label_71")

        self.gridLayout_13.addWidget(self.label_71, 9, 0, 1, 1)

        self.label_expected_dur_val = QLabel(self.dockWidgetContents_6)
        self.label_expected_dur_val.setObjectName(u"label_expected_dur_val")
        self.label_expected_dur_val.setAlignment(Qt.AlignmentFlag.AlignLeading|Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter)

        self.gridLayout_13.addWidget(self.label_expected_dur_val, 3, 9, 1, 3)

        self.progressBar_saving = QProgressBar(self.dockWidgetContents_6)
        self.progressBar_saving.setObjectName(u"progressBar_saving")
        sizePolicy3.setHeightForWidth(self.progressBar_saving.sizePolicy().hasHeightForWidth())
        self.progressBar_saving.setSizePolicy(sizePolicy3)
        self.progressBar_saving.setStyleSheet(u"height: 8px;")
        self.progressBar_saving.setValue(0)

        self.gridLayout_13.addWidget(self.progressBar_saving, 5, 2, 1, 10)

        self.progressBar_fifo_digital = QProgressBar(self.dockWidgetContents_6)
        self.progressBar_fifo_digital.setObjectName(u"progressBar_fifo_digital")
        sizePolicy3.setHeightForWidth(self.progressBar_fifo_digital.sizePolicy().hasHeightForWidth())
        self.progressBar_fifo_digital.setSizePolicy(sizePolicy3)
        self.progressBar_fifo_digital.setStyleSheet(u"height: 8px;")
        self.progressBar_fifo_digital.setValue(24)
        self.progressBar_fifo_digital.setTextVisible(True)

        self.gridLayout_13.addWidget(self.progressBar_fifo_digital, 6, 2, 1, 10)

        self.label_current_frame_val = QLabel(self.dockWidgetContents_6)
        self.label_current_frame_val.setObjectName(u"label_current_frame_val")
        sizePolicy1.setHeightForWidth(self.label_current_frame_val.sizePolicy().hasHeightForWidth())
        self.label_current_frame_val.setSizePolicy(sizePolicy1)
        self.label_current_frame_val.setAlignment(Qt.AlignmentFlag.AlignLeading|Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter)

        self.gridLayout_13.addWidget(self.label_current_frame_val, 8, 1, 1, 1)

        self.progressBar_frame = QProgressBar(self.dockWidgetContents_6)
        self.progressBar_frame.setObjectName(u"progressBar_frame")
        sizePolicy3.setHeightForWidth(self.progressBar_frame.sizePolicy().hasHeightForWidth())
        self.progressBar_frame.setSizePolicy(sizePolicy3)
        self.progressBar_frame.setStyleSheet(u"height: 8px;")
        self.progressBar_frame.setValue(24)

        self.gridLayout_13.addWidget(self.progressBar_frame, 8, 2, 1, 10)

        self.label_preview_delay = QLabel(self.dockWidgetContents_6)
        self.label_preview_delay.setObjectName(u"label_preview_delay")
        self.label_preview_delay.setAlignment(Qt.AlignmentFlag.AlignLeading|Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter)

        self.gridLayout_13.addWidget(self.label_preview_delay, 4, 9, 1, 3)

        self.label_72 = QLabel(self.dockWidgetContents_6)
        self.label_72.setObjectName(u"label_72")

        self.gridLayout_13.addWidget(self.label_72, 6, 0, 1, 1)

        self.label_current_time_3 = QLabel(self.dockWidgetContents_6)
        self.label_current_time_3.setObjectName(u"label_current_time_3")
        self.label_current_time_3.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)

        self.gridLayout_13.addWidget(self.label_current_time_3, 3, 6, 1, 3)

        self.progressBar_fifo_analog = QProgressBar(self.dockWidgetContents_6)
        self.progressBar_fifo_analog.setObjectName(u"progressBar_fifo_analog")
        sizePolicy3.setHeightForWidth(self.progressBar_fifo_analog.sizePolicy().hasHeightForWidth())
        self.progressBar_fifo_analog.setSizePolicy(sizePolicy3)
        self.progressBar_fifo_analog.setStyleSheet(u"height: 8px;")
        self.progressBar_fifo_analog.setValue(24)

        self.gridLayout_13.addWidget(self.progressBar_fifo_analog, 7, 2, 1, 10)

        self.label_85 = QLabel(self.dockWidgetContents_6)
        self.label_85.setObjectName(u"label_85")

        self.gridLayout_13.addWidget(self.label_85, 7, 0, 1, 1)

        self.label_87 = QLabel(self.dockWidgetContents_6)
        self.label_87.setObjectName(u"label_87")

        self.gridLayout_13.addWidget(self.label_87, 5, 0, 1, 1)

        self.label_preview_delay_label = QLabel(self.dockWidgetContents_6)
        self.label_preview_delay_label.setObjectName(u"label_preview_delay_label")
        self.label_preview_delay_label.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)

        self.gridLayout_13.addWidget(self.label_preview_delay_label, 4, 6, 1, 3)

        self.label_tot_num_dat_point = QLabel(self.dockWidgetContents_6)
        self.label_tot_num_dat_point.setObjectName(u"label_tot_num_dat_point")
        sizePolicy4 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        sizePolicy4.setHorizontalStretch(0)
        sizePolicy4.setVerticalStretch(0)
        sizePolicy4.setHeightForWidth(self.label_tot_num_dat_point.sizePolicy().hasHeightForWidth())
        self.label_tot_num_dat_point.setSizePolicy(sizePolicy4)
        self.label_tot_num_dat_point.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)

        self.gridLayout_13.addWidget(self.label_tot_num_dat_point, 2, 0, 1, 1)

        self.label_current_time = QLabel(self.dockWidgetContents_6)
        self.label_current_time.setObjectName(u"label_current_time")
        self.label_current_time.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)

        self.gridLayout_13.addWidget(self.label_current_time, 3, 0, 1, 1)

        self.label_current_time_val = QLabel(self.dockWidgetContents_6)
        self.label_current_time_val.setObjectName(u"label_current_time_val")
        self.label_current_time_val.setAlignment(Qt.AlignmentFlag.AlignLeading|Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter)

        self.gridLayout_13.addWidget(self.label_current_time_val, 3, 1, 1, 3)

        self.label_frame_time_val = QLabel(self.dockWidgetContents_6)
        self.label_frame_time_val.setObjectName(u"label_frame_time_val")
        self.label_frame_time_val.setAlignment(Qt.AlignmentFlag.AlignLeading|Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter)

        self.gridLayout_13.addWidget(self.label_frame_time_val, 4, 1, 1, 3)

        self.label_tot_num_dat_point_val = QLabel(self.dockWidgetContents_6)
        self.label_tot_num_dat_point_val.setObjectName(u"label_tot_num_dat_point_val")
        sizePolicy.setHeightForWidth(self.label_tot_num_dat_point_val.sizePolicy().hasHeightForWidth())
        self.label_tot_num_dat_point_val.setSizePolicy(sizePolicy)
        self.label_tot_num_dat_point_val.setAlignment(Qt.AlignmentFlag.AlignLeading|Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter)

        self.gridLayout_13.addWidget(self.label_tot_num_dat_point_val, 2, 1, 1, 11)


        self.gridLayout_14.addLayout(self.gridLayout_13, 4, 0, 1, 1)

        self.verticalSpacer_13 = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.gridLayout_14.addItem(self.verticalSpacer_13, 5, 0, 1, 1)

        self.dockWidget_statistics.setWidget(self.dockWidgetContents_6)
        MainWindowDesign.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dockWidget_statistics)
        self.statusBar = QStatusBar(MainWindowDesign)
        self.statusBar.setObjectName(u"statusBar")
        MainWindowDesign.setStatusBar(self.statusBar)
        self.dockWidget_pos = QDockWidget(MainWindowDesign)
        self.dockWidget_pos.setObjectName(u"dockWidget_pos")
        self.dockWidget_pos.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetFloatable|QDockWidget.DockWidgetFeature.DockWidgetMovable)
        self.dockWidgetContents_9 = QWidget()
        self.dockWidgetContents_9.setObjectName(u"dockWidgetContents_9")
        self.gridLayout_17 = QGridLayout(self.dockWidgetContents_9)
        self.gridLayout_17.setObjectName(u"gridLayout_17")
        self.horizontalLayout = QHBoxLayout()
        self.horizontalLayout.setObjectName(u"horizontalLayout")

        self.gridLayout_17.addLayout(self.horizontalLayout, 10, 0, 1, 1)

        self.gridLayout_18 = QGridLayout()
        self.gridLayout_18.setObjectName(u"gridLayout_18")
        self.label = QLabel(self.dockWidgetContents_9)
        self.label.setObjectName(u"label")

        self.gridLayout_18.addWidget(self.label, 1, 0, 1, 1)

        self.label_3 = QLabel(self.dockWidgetContents_9)
        self.label_3.setObjectName(u"label_3")

        self.gridLayout_18.addWidget(self.label_3, 2, 0, 1, 1)

        self.label_13 = QLabel(self.dockWidgetContents_9)
        self.label_13.setObjectName(u"label_13")

        self.gridLayout_18.addWidget(self.label_13, 1, 4, 1, 1)

        self.label_27 = QLabel(self.dockWidgetContents_9)
        self.label_27.setObjectName(u"label_27")

        self.gridLayout_18.addWidget(self.label_27, 2, 8, 1, 1)

        self.spinBox_range_z = sciSpinBox(self.dockWidgetContents_9)
        self.spinBox_range_z.setObjectName(u"spinBox_range_z")
        self.spinBox_range_z.setKeyboardTracking(False)
        self.spinBox_range_z.setDecimals(3)
        self.spinBox_range_z.setMinimum(0.000000000000000)
        self.spinBox_range_z.setMaximum(150.000000000000000)

        self.gridLayout_18.addWidget(self.spinBox_range_z, 3, 7, 1, 1)

        self.spinBox_range_x = sciSpinBox(self.dockWidgetContents_9)
        self.spinBox_range_x.setObjectName(u"spinBox_range_x")
        self.spinBox_range_x.setKeyboardTracking(False)
        self.spinBox_range_x.setDecimals(3)
        self.spinBox_range_x.setMinimum(0.000000000000000)
        self.spinBox_range_x.setMaximum(1000.000000000000000)
        self.spinBox_range_x.setValue(200.000000000000000)

        self.gridLayout_18.addWidget(self.spinBox_range_x, 1, 7, 1, 1)

        self.label_26 = QLabel(self.dockWidgetContents_9)
        self.label_26.setObjectName(u"label_26")

        self.gridLayout_18.addWidget(self.label_26, 1, 8, 1, 1)

        self.spinBox_off_y_um = sciSpinBox(self.dockWidgetContents_9)
        self.spinBox_off_y_um.setObjectName(u"spinBox_off_y_um")
        self.spinBox_off_y_um.setKeyboardTracking(False)
        self.spinBox_off_y_um.setDecimals(3)
        self.spinBox_off_y_um.setMinimum(-120.000000000000000)
        self.spinBox_off_y_um.setMaximum(120.000000000000000)
        self.spinBox_off_y_um.setValue(0.000000000000000)

        self.gridLayout_18.addWidget(self.spinBox_off_y_um, 2, 3, 1, 1)

        self.label_23 = QLabel(self.dockWidgetContents_9)
        self.label_23.setObjectName(u"label_23")

        self.gridLayout_18.addWidget(self.label_23, 3, 6, 1, 1)

        self.spinBox_off_z_um = sciSpinBox(self.dockWidgetContents_9)
        self.spinBox_off_z_um.setObjectName(u"spinBox_off_z_um")
        self.spinBox_off_z_um.setKeyboardTracking(False)
        self.spinBox_off_z_um.setDecimals(3)
        self.spinBox_off_z_um.setMinimum(-200.000000000000000)
        self.spinBox_off_z_um.setMaximum(200.000000000000000)

        self.gridLayout_18.addWidget(self.spinBox_off_z_um, 3, 3, 1, 1)

        self.label_14 = QLabel(self.dockWidgetContents_9)
        self.label_14.setObjectName(u"label_14")

        self.gridLayout_18.addWidget(self.label_14, 2, 4, 1, 1)

        self.label_24 = QLabel(self.dockWidgetContents_9)
        self.label_24.setObjectName(u"label_24")

        self.gridLayout_18.addWidget(self.label_24, 0, 3, 1, 1)

        self.label_15 = QLabel(self.dockWidgetContents_9)
        self.label_15.setObjectName(u"label_15")

        self.gridLayout_18.addWidget(self.label_15, 3, 4, 1, 1)

        self.spinBox_off_x_um = sciSpinBox(self.dockWidgetContents_9)
        self.spinBox_off_x_um.setObjectName(u"spinBox_off_x_um")
        self.spinBox_off_x_um.setKeyboardTracking(False)
        self.spinBox_off_x_um.setDecimals(3)
        self.spinBox_off_x_um.setMinimum(-200.000000000000000)
        self.spinBox_off_x_um.setMaximum(200.000000000000000)
        self.spinBox_off_x_um.setValue(0.000000000000000)

        self.gridLayout_18.addWidget(self.spinBox_off_x_um, 1, 3, 1, 1)

        self.label_21 = QLabel(self.dockWidgetContents_9)
        self.label_21.setObjectName(u"label_21")

        self.gridLayout_18.addWidget(self.label_21, 1, 6, 1, 1)

        self.label_28 = QLabel(self.dockWidgetContents_9)
        self.label_28.setObjectName(u"label_28")

        self.gridLayout_18.addWidget(self.label_28, 3, 8, 1, 1)

        self.label_4 = QLabel(self.dockWidgetContents_9)
        self.label_4.setObjectName(u"label_4")

        self.gridLayout_18.addWidget(self.label_4, 3, 0, 1, 1)

        self.spinBox_range_y = sciSpinBox(self.dockWidgetContents_9)
        self.spinBox_range_y.setObjectName(u"spinBox_range_y")
        self.spinBox_range_y.setKeyboardTracking(False)
        self.spinBox_range_y.setDecimals(3)
        self.spinBox_range_y.setMinimum(0.000000000000000)
        self.spinBox_range_y.setMaximum(1000.000000000000000)
        self.spinBox_range_y.setValue(10.000000000000000)

        self.gridLayout_18.addWidget(self.spinBox_range_y, 2, 7, 1, 1)

        self.label_25 = QLabel(self.dockWidgetContents_9)
        self.label_25.setObjectName(u"label_25")

        self.gridLayout_18.addWidget(self.label_25, 0, 7, 1, 1)

        self.horizontalSpacer_7 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.gridLayout_18.addItem(self.horizontalSpacer_7, 1, 5, 1, 1)

        self.label_22 = QLabel(self.dockWidgetContents_9)
        self.label_22.setObjectName(u"label_22")

        self.gridLayout_18.addWidget(self.label_22, 2, 6, 1, 1)

        self.horizontalSpacer_4 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.gridLayout_18.addItem(self.horizontalSpacer_4, 0, 9, 1, 1)

        self.checkBoxLockRatio = QCheckBox(self.dockWidgetContents_9)
        self.checkBoxLockRatio.setObjectName(u"checkBoxLockRatio")

        self.gridLayout_18.addWidget(self.checkBoxLockRatio, 1, 9, 2, 1)


        self.gridLayout_17.addLayout(self.gridLayout_18, 2, 0, 1, 5)

        self.groupBox = QGroupBox(self.dockWidgetContents_9)
        self.groupBox.setObjectName(u"groupBox")
        self.gridLayout_69 = QGridLayout(self.groupBox)
        self.gridLayout_69.setObjectName(u"gridLayout_69")
        self.pushButton_loadPreset = QPushButton(self.groupBox)
        self.pushButton_loadPreset.setObjectName(u"pushButton_loadPreset")

        self.gridLayout_69.addWidget(self.pushButton_loadPreset, 0, 1, 1, 1)

        self.pushButton_savePreset = QPushButton(self.groupBox)
        self.pushButton_savePreset.setObjectName(u"pushButton_savePreset")

        self.gridLayout_69.addWidget(self.pushButton_savePreset, 0, 2, 1, 1)

        self.comboBox_preset = QComboBox(self.groupBox)
        self.comboBox_preset.addItem("")
        self.comboBox_preset.addItem("")
        self.comboBox_preset.addItem("")
        self.comboBox_preset.addItem("")
        self.comboBox_preset.addItem("")
        self.comboBox_preset.addItem("")
        self.comboBox_preset.addItem("")
        self.comboBox_preset.addItem("")
        self.comboBox_preset.addItem("")
        self.comboBox_preset.addItem("")
        self.comboBox_preset.setObjectName(u"comboBox_preset")

        self.gridLayout_69.addWidget(self.comboBox_preset, 0, 0, 1, 1)


        self.gridLayout_17.addWidget(self.groupBox, 3, 0, 2, 1)

        self.verticalSpacer_3 = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.gridLayout_17.addItem(self.verticalSpacer_3, 15, 0, 1, 1)

        self.tableWidget_markers = QTableWidget(self.dockWidgetContents_9)
        if (self.tableWidget_markers.columnCount() < 4):
            self.tableWidget_markers.setColumnCount(4)
        __qtablewidgetitem = QTableWidgetItem()
        self.tableWidget_markers.setHorizontalHeaderItem(0, __qtablewidgetitem)
        __qtablewidgetitem1 = QTableWidgetItem()
        self.tableWidget_markers.setHorizontalHeaderItem(1, __qtablewidgetitem1)
        __qtablewidgetitem2 = QTableWidgetItem()
        self.tableWidget_markers.setHorizontalHeaderItem(2, __qtablewidgetitem2)
        __qtablewidgetitem3 = QTableWidgetItem()
        self.tableWidget_markers.setHorizontalHeaderItem(3, __qtablewidgetitem3)
        self.tableWidget_markers.setObjectName(u"tableWidget_markers")
        self.tableWidget_markers.setFont(font)
        self.tableWidget_markers.setColumnCount(4)
        self.tableWidget_markers.horizontalHeader().setMinimumSectionSize(10)
        self.tableWidget_markers.verticalHeader().setMinimumSectionSize(10)
        self.tableWidget_markers.verticalHeader().setDefaultSectionSize(10)

        self.gridLayout_17.addWidget(self.tableWidget_markers, 7, 0, 1, 5)

        self.verticalSpacer_2 = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.gridLayout_17.addItem(self.verticalSpacer_2, 11, 1, 1, 1)

        self.pushButton_15 = QPushButton(self.dockWidgetContents_9)
        self.pushButton_15.setObjectName(u"pushButton_15")

        self.gridLayout_17.addWidget(self.pushButton_15, 4, 1, 1, 1)

        self.pushButton_Panorama = QPushButton(self.dockWidgetContents_9)
        self.pushButton_Panorama.setObjectName(u"pushButton_Panorama")

        self.gridLayout_17.addWidget(self.pushButton_Panorama, 3, 1, 1, 1)

        self.dockWidget_pos.setWidget(self.dockWidgetContents_9)
        MainWindowDesign.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.dockWidget_pos)
        self.dockWidget_activatefifo = QDockWidget(MainWindowDesign)
        self.dockWidget_activatefifo.setObjectName(u"dockWidget_activatefifo")
        self.dockWidget_activatefifo.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetFloatable|QDockWidget.DockWidgetFeature.DockWidgetMovable)
        self.dockWidgetContents_4 = QWidget()
        self.dockWidgetContents_4.setObjectName(u"dockWidgetContents_4")
        self.gridLayout_27 = QGridLayout(self.dockWidgetContents_4)
        self.gridLayout_27.setObjectName(u"gridLayout_27")
        self.checkBox_snake = QCheckBox(self.dockWidgetContents_4)
        self.checkBox_snake.setObjectName(u"checkBox_snake")

        self.gridLayout_27.addWidget(self.checkBox_snake, 1, 1, 1, 1)

        self.checkBox_showPreview = QCheckBox(self.dockWidgetContents_4)
        self.checkBox_showPreview.setObjectName(u"checkBox_showPreview")
        self.checkBox_showPreview.setChecked(True)

        self.gridLayout_27.addWidget(self.checkBox_showPreview, 0, 1, 1, 1)

        self.groupBox_8 = QGroupBox(self.dockWidgetContents_4)
        self.groupBox_8.setObjectName(u"groupBox_8")
        self.gridLayout_28 = QGridLayout(self.groupBox_8)
        self.gridLayout_28.setObjectName(u"gridLayout_28")
        self.checkBox_slavemode_enable = QCheckBox(self.groupBox_8)
        self.checkBox_slavemode_enable.setObjectName(u"checkBox_slavemode_enable")

        self.gridLayout_28.addWidget(self.checkBox_slavemode_enable, 0, 0, 2, 2)

        self.label_112 = QLabel(self.groupBox_8)
        self.label_112.setObjectName(u"label_112")

        self.gridLayout_28.addWidget(self.label_112, 2, 0, 1, 1)

        self.comboBox_slavemode_type = QComboBox(self.groupBox_8)
        self.comboBox_slavemode_type.addItem("")
        self.comboBox_slavemode_type.addItem("")
        self.comboBox_slavemode_type.addItem("")
        self.comboBox_slavemode_type.addItem("")
        self.comboBox_slavemode_type.addItem("")
        self.comboBox_slavemode_type.addItem("")
        self.comboBox_slavemode_type.setObjectName(u"comboBox_slavemode_type")

        self.gridLayout_28.addWidget(self.comboBox_slavemode_type, 3, 0, 1, 1)


        self.gridLayout_27.addWidget(self.groupBox_8, 2, 1, 1, 1)

        self.groupBox_2 = QGroupBox(self.dockWidgetContents_4)
        self.groupBox_2.setObjectName(u"groupBox_2")
        self.gridLayout_20 = QGridLayout(self.groupBox_2)
        self.gridLayout_20.setObjectName(u"gridLayout_20")
        self.spinBox_circular_radius_nm = sciSpinBox(self.groupBox_2)
        self.spinBox_circular_radius_nm.setObjectName(u"spinBox_circular_radius_nm")
        self.spinBox_circular_radius_nm.setKeyboardTracking(False)
        self.spinBox_circular_radius_nm.setDecimals(3)
        self.spinBox_circular_radius_nm.setMinimum(-1000000.000000000000000)
        self.spinBox_circular_radius_nm.setMaximum(1000000.000000000000000)
        self.spinBox_circular_radius_nm.setValue(0.000000000000000)

        self.gridLayout_20.addWidget(self.spinBox_circular_radius_nm, 4, 1, 1, 1)

        self.label_109 = QLabel(self.groupBox_2)
        self.label_109.setObjectName(u"label_109")

        self.gridLayout_20.addWidget(self.label_109, 4, 2, 1, 1)

        self.label_108 = QLabel(self.groupBox_2)
        self.label_108.setObjectName(u"label_108")

        self.gridLayout_20.addWidget(self.label_108, 4, 0, 1, 1)

        self.horizontalSpacer_14 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.gridLayout_20.addItem(self.horizontalSpacer_14, 2, 2, 1, 1)

        self.label_43 = QLabel(self.groupBox_2)
        self.label_43.setObjectName(u"label_43")

        self.gridLayout_20.addWidget(self.label_43, 2, 0, 1, 1)

        self.spinBox_circular_points = QSpinBox(self.groupBox_2)
        self.spinBox_circular_points.setObjectName(u"spinBox_circular_points")
        self.spinBox_circular_points.setMinimum(1)
        self.spinBox_circular_points.setMaximum(32)
        self.spinBox_circular_points.setValue(1)

        self.gridLayout_20.addWidget(self.spinBox_circular_points, 2, 1, 1, 1)

        self.label_110 = QLabel(self.groupBox_2)
        self.label_110.setObjectName(u"label_110")

        self.gridLayout_20.addWidget(self.label_110, 3, 0, 1, 1)

        self.spinBox_circular_repetition = QSpinBox(self.groupBox_2)
        self.spinBox_circular_repetition.setObjectName(u"spinBox_circular_repetition")
        self.spinBox_circular_repetition.setMinimum(1)
        self.spinBox_circular_repetition.setMaximum(32)
        self.spinBox_circular_repetition.setValue(1)

        self.gridLayout_20.addWidget(self.spinBox_circular_repetition, 3, 1, 1, 1)

        self.checkBox_circular = QCheckBox(self.groupBox_2)
        self.checkBox_circular.setObjectName(u"checkBox_circular")

        self.gridLayout_20.addWidget(self.checkBox_circular, 0, 0, 1, 3)


        self.gridLayout_27.addWidget(self.groupBox_2, 0, 2, 3, 1)

        self.dockWidget_activatefifo.setWidget(self.dockWidgetContents_4)
        MainWindowDesign.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.dockWidget_activatefifo)
        self.dockWidget_laser = QDockWidget(MainWindowDesign)
        self.dockWidget_laser.setObjectName(u"dockWidget_laser")
        sizePolicy4.setHeightForWidth(self.dockWidget_laser.sizePolicy().hasHeightForWidth())
        self.dockWidget_laser.setSizePolicy(sizePolicy4)
        self.dockWidgetContents_13 = QWidget()
        self.dockWidgetContents_13.setObjectName(u"dockWidgetContents_13")
        self.gridLayout_42 = QGridLayout(self.dockWidgetContents_13)
        self.gridLayout_42.setObjectName(u"gridLayout_42")
        self.groupBox_3 = QGroupBox(self.dockWidgetContents_13)
        self.groupBox_3.setObjectName(u"groupBox_3")
        sizePolicy4.setHeightForWidth(self.groupBox_3.sizePolicy().hasHeightForWidth())
        self.groupBox_3.setSizePolicy(sizePolicy4)
        self.gridLayout_75 = QGridLayout(self.groupBox_3)
        self.gridLayout_75.setObjectName(u"gridLayout_75")
        self.checkBox_laser0 = QCheckBox(self.groupBox_3)
        self.checkBox_laser0.setObjectName(u"checkBox_laser0")
        self.checkBox_laser0.setChecked(True)

        self.gridLayout_75.addWidget(self.checkBox_laser0, 0, 0, 1, 1)

        self.checkBox_laser3 = QCheckBox(self.groupBox_3)
        self.checkBox_laser3.setObjectName(u"checkBox_laser3")

        self.gridLayout_75.addWidget(self.checkBox_laser3, 0, 3, 1, 1)

        self.checkBox_laser1 = QCheckBox(self.groupBox_3)
        self.checkBox_laser1.setObjectName(u"checkBox_laser1")

        self.gridLayout_75.addWidget(self.checkBox_laser1, 0, 1, 1, 1)

        self.checkBox_laser2 = QCheckBox(self.groupBox_3)
        self.checkBox_laser2.setObjectName(u"checkBox_laser2")

        self.gridLayout_75.addWidget(self.checkBox_laser2, 0, 2, 1, 1)


        self.gridLayout_42.addWidget(self.groupBox_3, 0, 0, 1, 1)

        self.groupBox_7 = QGroupBox(self.dockWidgetContents_13)
        self.groupBox_7.setObjectName(u"groupBox_7")
        self.gridLayout_7 = QGridLayout(self.groupBox_7)
        self.gridLayout_7.setObjectName(u"gridLayout_7")
        self.comboBox_channels = QComboBox(self.groupBox_7)
        self.comboBox_channels.addItem("")
        self.comboBox_channels.addItem("")
        self.comboBox_channels.setObjectName(u"comboBox_channels")

        self.gridLayout_7.addWidget(self.comboBox_channels, 2, 1, 1, 1)

        self.label_35 = QLabel(self.groupBox_7)
        self.label_35.setObjectName(u"label_35")

        self.gridLayout_7.addWidget(self.label_35, 2, 0, 1, 1)

        self.spinBox_DFD_nbins = QSpinBox(self.groupBox_7)
        self.spinBox_DFD_nbins.setObjectName(u"spinBox_DFD_nbins")
        self.spinBox_DFD_nbins.setMaximum(1023)
        self.spinBox_DFD_nbins.setValue(81)

        self.gridLayout_7.addWidget(self.spinBox_DFD_nbins, 1, 1, 1, 1)

        self.label_111 = QLabel(self.groupBox_7)
        self.label_111.setObjectName(u"label_111")

        self.gridLayout_7.addWidget(self.label_111, 1, 0, 1, 1)

        self.checkBox_DFD_LaserDebug = QCheckBox(self.groupBox_7)
        self.checkBox_DFD_LaserDebug.setObjectName(u"checkBox_DFD_LaserDebug")
        self.checkBox_DFD_LaserDebug.setChecked(True)

        self.gridLayout_7.addWidget(self.checkBox_DFD_LaserDebug, 3, 0, 1, 1)


        self.gridLayout_42.addWidget(self.groupBox_7, 0, 1, 1, 1)

        self.groupBox_6 = QGroupBox(self.dockWidgetContents_13)
        self.groupBox_6.setObjectName(u"groupBox_6")
        sizePolicy4.setHeightForWidth(self.groupBox_6.sizePolicy().hasHeightForWidth())
        self.groupBox_6.setSizePolicy(sizePolicy4)
        self.gridLayout_41 = QGridLayout(self.groupBox_6)
        self.gridLayout_41.setObjectName(u"gridLayout_41")
        self.comboLaserSeq_3 = QComboBox(self.groupBox_6)
        self.comboLaserSeq_3.addItem("")
        self.comboLaserSeq_3.addItem("")
        self.comboLaserSeq_3.addItem("")
        self.comboLaserSeq_3.addItem("")
        self.comboLaserSeq_3.addItem("")
        self.comboLaserSeq_3.setObjectName(u"comboLaserSeq_3")
        sizePolicy2.setHeightForWidth(self.comboLaserSeq_3.sizePolicy().hasHeightForWidth())
        self.comboLaserSeq_3.setSizePolicy(sizePolicy2)

        self.gridLayout_41.addWidget(self.comboLaserSeq_3, 0, 2, 1, 1)

        self.comboLaserSeq_5 = QComboBox(self.groupBox_6)
        self.comboLaserSeq_5.addItem("")
        self.comboLaserSeq_5.addItem("")
        self.comboLaserSeq_5.addItem("")
        self.comboLaserSeq_5.addItem("")
        self.comboLaserSeq_5.addItem("")
        self.comboLaserSeq_5.setObjectName(u"comboLaserSeq_5")
        sizePolicy2.setHeightForWidth(self.comboLaserSeq_5.sizePolicy().hasHeightForWidth())
        self.comboLaserSeq_5.setSizePolicy(sizePolicy2)

        self.gridLayout_41.addWidget(self.comboLaserSeq_5, 0, 4, 1, 1)

        self.comboLaserSeq_1 = QComboBox(self.groupBox_6)
        self.comboLaserSeq_1.addItem("")
        self.comboLaserSeq_1.addItem("")
        self.comboLaserSeq_1.addItem("")
        self.comboLaserSeq_1.addItem("")
        self.comboLaserSeq_1.addItem("")
        self.comboLaserSeq_1.setObjectName(u"comboLaserSeq_1")
        sizePolicy2.setHeightForWidth(self.comboLaserSeq_1.sizePolicy().hasHeightForWidth())
        self.comboLaserSeq_1.setSizePolicy(sizePolicy2)

        self.gridLayout_41.addWidget(self.comboLaserSeq_1, 0, 0, 1, 1)

        self.comboLaserSeq_4 = QComboBox(self.groupBox_6)
        self.comboLaserSeq_4.addItem("")
        self.comboLaserSeq_4.addItem("")
        self.comboLaserSeq_4.addItem("")
        self.comboLaserSeq_4.addItem("")
        self.comboLaserSeq_4.addItem("")
        self.comboLaserSeq_4.setObjectName(u"comboLaserSeq_4")
        sizePolicy2.setHeightForWidth(self.comboLaserSeq_4.sizePolicy().hasHeightForWidth())
        self.comboLaserSeq_4.setSizePolicy(sizePolicy2)

        self.gridLayout_41.addWidget(self.comboLaserSeq_4, 0, 3, 1, 1)

        self.comboLaserSeq_2 = QComboBox(self.groupBox_6)
        self.comboLaserSeq_2.addItem("")
        self.comboLaserSeq_2.addItem("")
        self.comboLaserSeq_2.addItem("")
        self.comboLaserSeq_2.addItem("")
        self.comboLaserSeq_2.addItem("")
        self.comboLaserSeq_2.setObjectName(u"comboLaserSeq_2")
        sizePolicy2.setHeightForWidth(self.comboLaserSeq_2.sizePolicy().hasHeightForWidth())
        self.comboLaserSeq_2.setSizePolicy(sizePolicy2)

        self.gridLayout_41.addWidget(self.comboLaserSeq_2, 0, 1, 1, 1)

        self.comboLaserSeq_6 = QComboBox(self.groupBox_6)
        self.comboLaserSeq_6.addItem("")
        self.comboLaserSeq_6.addItem("")
        self.comboLaserSeq_6.addItem("")
        self.comboLaserSeq_6.addItem("")
        self.comboLaserSeq_6.addItem("")
        self.comboLaserSeq_6.setObjectName(u"comboLaserSeq_6")
        sizePolicy2.setHeightForWidth(self.comboLaserSeq_6.sizePolicy().hasHeightForWidth())
        self.comboLaserSeq_6.setSizePolicy(sizePolicy2)

        self.gridLayout_41.addWidget(self.comboLaserSeq_6, 0, 5, 1, 1)


        self.gridLayout_42.addWidget(self.groupBox_6, 2, 0, 1, 2)

        self.dockWidget_laser.setWidget(self.dockWidgetContents_13)
        MainWindowDesign.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dockWidget_laser)
        self.dockWidget_adv = QDockWidget(MainWindowDesign)
        self.dockWidget_adv.setObjectName(u"dockWidget_adv")
        self.dockWidget_adv.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetFloatable|QDockWidget.DockWidgetFeature.DockWidgetMovable)
        self.dockWidgetContents_15 = QWidget()
        self.dockWidgetContents_15.setObjectName(u"dockWidgetContents_15")
        self.gridLayout_37 = QGridLayout(self.dockWidgetContents_15)
        self.gridLayout_37.setObjectName(u"gridLayout_37")
        self.scrollArea_2 = QScrollArea(self.dockWidgetContents_15)
        self.scrollArea_2.setObjectName(u"scrollArea_2")
        self.scrollArea_2.setWidgetResizable(True)
        self.scrollAreaWidgetContents_2 = QWidget()
        self.scrollAreaWidgetContents_2.setObjectName(u"scrollAreaWidgetContents_2")
        self.scrollAreaWidgetContents_2.setGeometry(QRect(0, 0, 400, 316))
        self.gridLayout_64 = QGridLayout(self.scrollAreaWidgetContents_2)
        self.gridLayout_64.setObjectName(u"gridLayout_64")
        self.tabWidget_2 = QTabWidget(self.scrollAreaWidgetContents_2)
        self.tabWidget_2.setObjectName(u"tabWidget_2")
        self.tab_2 = QWidget()
        self.tab_2.setObjectName(u"tab_2")
        self.gridLayout_36 = QGridLayout(self.tab_2)
        self.gridLayout_36.setObjectName(u"gridLayout_36")
        self.gridLayout_24 = QGridLayout()
        self.gridLayout_24.setObjectName(u"gridLayout_24")
        self.lineEdit_fpga2bitfile = QLineEdit(self.tab_2)
        self.lineEdit_fpga2bitfile.setObjectName(u"lineEdit_fpga2bitfile")

        self.gridLayout_24.addWidget(self.lineEdit_fpga2bitfile, 9, 1, 1, 1)

        self.label_98 = QLabel(self.tab_2)
        self.label_98.setObjectName(u"label_98")

        self.gridLayout_24.addWidget(self.label_98, 8, 0, 1, 1)

        self.lineEdit_ni_addr = QLineEdit(self.tab_2)
        self.lineEdit_ni_addr.setObjectName(u"lineEdit_ni_addr")

        self.gridLayout_24.addWidget(self.lineEdit_ni_addr, 6, 1, 1, 1)

        self.pushButton_FPGA_file_selection = QPushButton(self.tab_2)
        self.pushButton_FPGA_file_selection.setObjectName(u"pushButton_FPGA_file_selection")
        sizePolicy2.setHeightForWidth(self.pushButton_FPGA_file_selection.sizePolicy().hasHeightForWidth())
        self.pushButton_FPGA_file_selection.setSizePolicy(sizePolicy2)

        self.gridLayout_24.addWidget(self.pushButton_FPGA_file_selection, 5, 2, 1, 1)

        self.label_66 = QLabel(self.tab_2)
        self.label_66.setObjectName(u"label_66")

        self.gridLayout_24.addWidget(self.label_66, 6, 0, 1, 1)

        self.label_88 = QLabel(self.tab_2)
        self.label_88.setObjectName(u"label_88")

        self.gridLayout_24.addWidget(self.label_88, 3, 0, 1, 1)

        self.label_67 = QLabel(self.tab_2)
        self.label_67.setObjectName(u"label_67")

        self.gridLayout_24.addWidget(self.label_67, 4, 0, 1, 1)

        self.label_75 = QLabel(self.tab_2)
        self.label_75.setObjectName(u"label_75")

        self.gridLayout_24.addWidget(self.label_75, 1, 1, 1, 1)

        self.lineEdit_fpgabitfile = QLineEdit(self.tab_2)
        self.lineEdit_fpgabitfile.setObjectName(u"lineEdit_fpgabitfile")

        self.gridLayout_24.addWidget(self.lineEdit_fpgabitfile, 5, 1, 1, 1)

        self.lineEdit_ni2addr = QLineEdit(self.tab_2)
        self.lineEdit_ni2addr.setObjectName(u"lineEdit_ni2addr")

        self.gridLayout_24.addWidget(self.lineEdit_ni2addr, 10, 1, 1, 1)

        self.pushButton_saveCfg = QPushButton(self.tab_2)
        self.pushButton_saveCfg.setObjectName(u"pushButton_saveCfg")

        self.gridLayout_24.addWidget(self.pushButton_saveCfg, 2, 2, 1, 1)

        self.pushButton_loadCfg = QPushButton(self.tab_2)
        self.pushButton_loadCfg.setObjectName(u"pushButton_loadCfg")

        self.gridLayout_24.addWidget(self.pushButton_loadCfg, 1, 2, 1, 1)

        self.label_92 = QLabel(self.tab_2)
        self.label_92.setObjectName(u"label_92")

        self.gridLayout_24.addWidget(self.label_92, 10, 0, 1, 1)

        self.pushButton_FPGA2_file_selection = QPushButton(self.tab_2)
        self.pushButton_FPGA2_file_selection.setObjectName(u"pushButton_FPGA2_file_selection")
        sizePolicy2.setHeightForWidth(self.pushButton_FPGA2_file_selection.sizePolicy().hasHeightForWidth())
        self.pushButton_FPGA2_file_selection.setSizePolicy(sizePolicy2)

        self.gridLayout_24.addWidget(self.pushButton_FPGA2_file_selection, 9, 2, 1, 1)

        self.lineEdit_configurationfile = QLineEdit(self.tab_2)
        self.lineEdit_configurationfile.setObjectName(u"lineEdit_configurationfile")

        self.gridLayout_24.addWidget(self.lineEdit_configurationfile, 4, 1, 1, 1)

        self.label_91 = QLabel(self.tab_2)
        self.label_91.setObjectName(u"label_91")

        self.gridLayout_24.addWidget(self.label_91, 9, 0, 1, 1)

        self.label_81 = QLabel(self.tab_2)
        self.label_81.setObjectName(u"label_81")

        self.gridLayout_24.addWidget(self.label_81, 2, 1, 1, 1)

        self.label_loadedcfg = QLabel(self.tab_2)
        self.label_loadedcfg.setObjectName(u"label_loadedcfg")

        self.gridLayout_24.addWidget(self.label_loadedcfg, 3, 1, 1, 1)

        self.label_65 = QLabel(self.tab_2)
        self.label_65.setObjectName(u"label_65")

        self.gridLayout_24.addWidget(self.label_65, 5, 0, 1, 1)

        self.verticalSpacer_7 = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.gridLayout_24.addItem(self.verticalSpacer_7, 8, 1, 1, 1)


        self.gridLayout_36.addLayout(self.gridLayout_24, 1, 0, 1, 1)

        self.tabWidget_2.addTab(self.tab_2, "")
        self.tab = QWidget()
        self.tab.setObjectName(u"tab")
        self.gridLayout_61 = QGridLayout(self.tab)
        self.gridLayout_61.setObjectName(u"gridLayout_61")
        self.gridLayout_59 = QGridLayout()
        self.gridLayout_59.setObjectName(u"gridLayout_59")
        self.lineEdit_spad_data = QLineEdit(self.tab)
        self.lineEdit_spad_data.setObjectName(u"lineEdit_spad_data")

        self.gridLayout_59.addWidget(self.lineEdit_spad_data, 1, 1, 1, 1)

        self.label_94 = QLabel(self.tab)
        self.label_94.setObjectName(u"label_94")

        self.gridLayout_59.addWidget(self.label_94, 1, 0, 1, 1)

        self.verticalSpacer_12 = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.gridLayout_59.addItem(self.verticalSpacer_12, 3, 1, 1, 1)

        self.label_93 = QLabel(self.tab)
        self.label_93.setObjectName(u"label_93")

        self.gridLayout_59.addWidget(self.label_93, 0, 0, 1, 1)

        self.checkBox_spad_invert = QCheckBox(self.tab)
        self.checkBox_spad_invert.setObjectName(u"checkBox_spad_invert")

        self.gridLayout_59.addWidget(self.checkBox_spad_invert, 1, 2, 1, 1)

        self.lineEdit_spad_length = QLineEdit(self.tab)
        self.lineEdit_spad_length.setObjectName(u"lineEdit_spad_length")

        self.gridLayout_59.addWidget(self.lineEdit_spad_length, 0, 1, 1, 2)


        self.gridLayout_61.addLayout(self.gridLayout_59, 0, 0, 1, 1)

        self.tabWidget_2.addTab(self.tab, "")
        self.tab_6 = QWidget()
        self.tab_6.setObjectName(u"tab_6")
        self.gridLayout_43 = QGridLayout(self.tab_6)
        self.gridLayout_43.setObjectName(u"gridLayout_43")
        self.gridLayout_33 = QGridLayout()
        self.gridLayout_33.setObjectName(u"gridLayout_33")
        self.label_56 = QLabel(self.tab_6)
        self.label_56.setObjectName(u"label_56")

        self.gridLayout_33.addWidget(self.label_56, 3, 2, 1, 1)

        self.spinBox_default_off_z_um = sciSpinBox(self.tab_6)
        self.spinBox_default_off_z_um.setObjectName(u"spinBox_default_off_z_um")
        self.spinBox_default_off_z_um.setDecimals(6)
        self.spinBox_default_off_z_um.setMinimum(-99.000000000000000)

        self.gridLayout_33.addWidget(self.spinBox_default_off_z_um, 3, 1, 1, 1)

        self.label_49 = QLabel(self.tab_6)
        self.label_49.setObjectName(u"label_49")

        self.gridLayout_33.addWidget(self.label_49, 1, 6, 1, 1)

        self.spinBox_default_off_x_um = sciSpinBox(self.tab_6)
        self.spinBox_default_off_x_um.setObjectName(u"spinBox_default_off_x_um")
        self.spinBox_default_off_x_um.setDecimals(6)
        self.spinBox_default_off_x_um.setMinimum(-99.000000000000000)

        self.gridLayout_33.addWidget(self.spinBox_default_off_x_um, 1, 1, 1, 1)

        self.label_47 = QLabel(self.tab_6)
        self.label_47.setObjectName(u"label_47")

        self.gridLayout_33.addWidget(self.label_47, 2, 4, 1, 1)

        self.label_50 = QLabel(self.tab_6)
        self.label_50.setObjectName(u"label_50")

        self.gridLayout_33.addWidget(self.label_50, 2, 6, 1, 1)

        self.label_55 = QLabel(self.tab_6)
        self.label_55.setObjectName(u"label_55")

        self.gridLayout_33.addWidget(self.label_55, 3, 0, 1, 1)

        self.spinBox_default_range_z = sciSpinBox(self.tab_6)
        self.spinBox_default_range_z.setObjectName(u"spinBox_default_range_z")
        self.spinBox_default_range_z.setDecimals(6)
        self.spinBox_default_range_z.setMaximum(300.000000000000000)

        self.gridLayout_33.addWidget(self.spinBox_default_range_z, 3, 5, 1, 1)

        self.label_52 = QLabel(self.tab_6)
        self.label_52.setObjectName(u"label_52")

        self.gridLayout_33.addWidget(self.label_52, 1, 2, 1, 1)

        self.spinBox_default_off_y_um = sciSpinBox(self.tab_6)
        self.spinBox_default_off_y_um.setObjectName(u"spinBox_default_off_y_um")
        self.spinBox_default_off_y_um.setDecimals(6)
        self.spinBox_default_off_y_um.setMinimum(-99.000000000000000)

        self.gridLayout_33.addWidget(self.spinBox_default_off_y_um, 2, 1, 1, 1)

        self.label_54 = QLabel(self.tab_6)
        self.label_54.setObjectName(u"label_54")

        self.gridLayout_33.addWidget(self.label_54, 2, 2, 1, 1)

        self.horizontalSpacer_9 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.gridLayout_33.addItem(self.horizontalSpacer_9, 1, 3, 1, 1)

        self.label_46 = QLabel(self.tab_6)
        self.label_46.setObjectName(u"label_46")

        self.gridLayout_33.addWidget(self.label_46, 1, 4, 1, 1)

        self.label_48 = QLabel(self.tab_6)
        self.label_48.setObjectName(u"label_48")

        self.gridLayout_33.addWidget(self.label_48, 3, 4, 1, 1)

        self.label_53 = QLabel(self.tab_6)
        self.label_53.setObjectName(u"label_53")

        self.gridLayout_33.addWidget(self.label_53, 2, 0, 1, 1)

        self.spinBox_default_range_y = sciSpinBox(self.tab_6)
        self.spinBox_default_range_y.setObjectName(u"spinBox_default_range_y")
        self.spinBox_default_range_y.setDecimals(6)
        self.spinBox_default_range_y.setMaximum(300.000000000000000)

        self.gridLayout_33.addWidget(self.spinBox_default_range_y, 2, 5, 1, 1)

        self.label_57 = QLabel(self.tab_6)
        self.label_57.setObjectName(u"label_57")

        self.gridLayout_33.addWidget(self.label_57, 1, 0, 1, 1)

        self.label_51 = QLabel(self.tab_6)
        self.label_51.setObjectName(u"label_51")

        self.gridLayout_33.addWidget(self.label_51, 3, 6, 1, 1)

        self.spinBox_default_range_x = sciSpinBox(self.tab_6)
        self.spinBox_default_range_x.setObjectName(u"spinBox_default_range_x")
        self.spinBox_default_range_x.setDecimals(6)
        self.spinBox_default_range_x.setMaximum(300.000000000000000)

        self.gridLayout_33.addWidget(self.spinBox_default_range_x, 1, 5, 1, 1)

        self.label_58 = QLabel(self.tab_6)
        self.label_58.setObjectName(u"label_58")

        self.gridLayout_33.addWidget(self.label_58, 0, 1, 1, 1)

        self.label_59 = QLabel(self.tab_6)
        self.label_59.setObjectName(u"label_59")

        self.gridLayout_33.addWidget(self.label_59, 0, 5, 1, 1)


        self.gridLayout_43.addLayout(self.gridLayout_33, 0, 0, 1, 1)

        self.verticalSpacer_6 = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.gridLayout_43.addItem(self.verticalSpacer_6, 1, 0, 1, 1)

        self.tabWidget_2.addTab(self.tab_6, "")
        self.tab_7 = QWidget()
        self.tab_7.setObjectName(u"tab_7")
        self.gridLayout_45 = QGridLayout(self.tab_7)
        self.gridLayout_45.setObjectName(u"gridLayout_45")
        self.label_17 = QLabel(self.tab_7)
        self.label_17.setObjectName(u"label_17")

        self.gridLayout_45.addWidget(self.label_17, 0, 0, 1, 1)

        self.gridLayout_25 = QGridLayout()
        self.gridLayout_25.setObjectName(u"gridLayout_25")
        self.label_30 = QLabel(self.tab_7)
        self.label_30.setObjectName(u"label_30")

        self.gridLayout_25.addWidget(self.label_30, 0, 2, 1, 1)

        self.spinBox_offExtra_y_V = sciSpinBox(self.tab_7)
        self.spinBox_offExtra_y_V.setObjectName(u"spinBox_offExtra_y_V")
        self.spinBox_offExtra_y_V.setDecimals(6)
        self.spinBox_offExtra_y_V.setMinimum(-99.000000000000000)

        self.gridLayout_25.addWidget(self.spinBox_offExtra_y_V, 1, 1, 1, 1)

        self.spinBox_offExtra_z_V = sciSpinBox(self.tab_7)
        self.spinBox_offExtra_z_V.setObjectName(u"spinBox_offExtra_z_V")
        self.spinBox_offExtra_z_V.setDecimals(6)
        self.spinBox_offExtra_z_V.setMinimum(-99.000000000000000)

        self.gridLayout_25.addWidget(self.spinBox_offExtra_z_V, 2, 1, 1, 1)

        self.label_31 = QLabel(self.tab_7)
        self.label_31.setObjectName(u"label_31")

        self.gridLayout_25.addWidget(self.label_31, 1, 0, 1, 1)

        self.label_32 = QLabel(self.tab_7)
        self.label_32.setObjectName(u"label_32")

        self.gridLayout_25.addWidget(self.label_32, 1, 2, 1, 1)

        self.label_33 = QLabel(self.tab_7)
        self.label_33.setObjectName(u"label_33")

        self.gridLayout_25.addWidget(self.label_33, 2, 0, 1, 1)

        self.label_34 = QLabel(self.tab_7)
        self.label_34.setObjectName(u"label_34")

        self.gridLayout_25.addWidget(self.label_34, 2, 2, 1, 1)

        self.horizontalSpacer_5 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.gridLayout_25.addItem(self.horizontalSpacer_5, 2, 3, 1, 1)

        self.spinBox_offExtra_x_V = sciSpinBox(self.tab_7)
        self.spinBox_offExtra_x_V.setObjectName(u"spinBox_offExtra_x_V")
        self.spinBox_offExtra_x_V.setDecimals(6)
        self.spinBox_offExtra_x_V.setMinimum(-99.000000000000000)

        self.gridLayout_25.addWidget(self.spinBox_offExtra_x_V, 0, 1, 1, 1)

        self.label_45 = QLabel(self.tab_7)
        self.label_45.setObjectName(u"label_45")

        self.gridLayout_25.addWidget(self.label_45, 0, 0, 1, 1)


        self.gridLayout_45.addLayout(self.gridLayout_25, 1, 0, 1, 1)

        self.gridLayout_26 = QGridLayout()
        self.gridLayout_26.setObjectName(u"gridLayout_26")
        self.spinBox_min_x_V = sciSpinBox(self.tab_7)
        self.spinBox_min_x_V.setObjectName(u"spinBox_min_x_V")
        self.spinBox_min_x_V.setDecimals(6)
        self.spinBox_min_x_V.setMinimum(-99.000000000000000)
        self.spinBox_min_x_V.setValue(-10.000000000000000)

        self.gridLayout_26.addWidget(self.spinBox_min_x_V, 1, 1, 1, 1)

        self.spinBox_max_z_V = sciSpinBox(self.tab_7)
        self.spinBox_max_z_V.setObjectName(u"spinBox_max_z_V")
        self.spinBox_max_z_V.setDecimals(6)
        self.spinBox_max_z_V.setMinimum(-99.000000000000000)
        self.spinBox_max_z_V.setValue(5.000000000000000)

        self.gridLayout_26.addWidget(self.spinBox_max_z_V, 3, 2, 1, 1)

        self.label_38 = QLabel(self.tab_7)
        self.label_38.setObjectName(u"label_38")

        self.gridLayout_26.addWidget(self.label_38, 1, 0, 1, 1)

        self.label_39 = QLabel(self.tab_7)
        self.label_39.setObjectName(u"label_39")

        self.gridLayout_26.addWidget(self.label_39, 2, 0, 1, 1)

        self.spinBox_max_y_V = sciSpinBox(self.tab_7)
        self.spinBox_max_y_V.setObjectName(u"spinBox_max_y_V")
        self.spinBox_max_y_V.setDecimals(6)
        self.spinBox_max_y_V.setMinimum(-99.000000000000000)
        self.spinBox_max_y_V.setValue(10.000000000000000)

        self.gridLayout_26.addWidget(self.spinBox_max_y_V, 2, 2, 1, 1)

        self.label_41 = QLabel(self.tab_7)
        self.label_41.setObjectName(u"label_41")

        self.gridLayout_26.addWidget(self.label_41, 0, 1, 1, 1)

        self.spinBox_max_x_V = sciSpinBox(self.tab_7)
        self.spinBox_max_x_V.setObjectName(u"spinBox_max_x_V")
        self.spinBox_max_x_V.setDecimals(6)
        self.spinBox_max_x_V.setMinimum(-99.000000000000000)
        self.spinBox_max_x_V.setValue(10.000000000000000)

        self.gridLayout_26.addWidget(self.spinBox_max_x_V, 1, 2, 1, 1)

        self.label_42 = QLabel(self.tab_7)
        self.label_42.setObjectName(u"label_42")

        self.gridLayout_26.addWidget(self.label_42, 0, 2, 1, 1)

        self.spinBox_min_z_V = sciSpinBox(self.tab_7)
        self.spinBox_min_z_V.setObjectName(u"spinBox_min_z_V")
        self.spinBox_min_z_V.setDecimals(6)
        self.spinBox_min_z_V.setMinimum(-99.000000000000000)
        self.spinBox_min_z_V.setValue(-5.000000000000000)

        self.gridLayout_26.addWidget(self.spinBox_min_z_V, 3, 1, 1, 1)

        self.label_40 = QLabel(self.tab_7)
        self.label_40.setObjectName(u"label_40")

        self.gridLayout_26.addWidget(self.label_40, 3, 0, 1, 1)

        self.spinBox_min_y_V = sciSpinBox(self.tab_7)
        self.spinBox_min_y_V.setObjectName(u"spinBox_min_y_V")
        self.spinBox_min_y_V.setDecimals(6)
        self.spinBox_min_y_V.setMinimum(-99.000000000000000)
        self.spinBox_min_y_V.setValue(-10.000000000000000)

        self.gridLayout_26.addWidget(self.spinBox_min_y_V, 2, 1, 1, 1)

        self.horizontalSpacer_6 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.gridLayout_26.addItem(self.horizontalSpacer_6, 2, 3, 1, 1)


        self.gridLayout_45.addLayout(self.gridLayout_26, 3, 0, 1, 1)

        self.label_37 = QLabel(self.tab_7)
        self.label_37.setObjectName(u"label_37")

        self.gridLayout_45.addWidget(self.label_37, 2, 0, 1, 1)

        self.verticalSpacer_8 = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.gridLayout_45.addItem(self.verticalSpacer_8, 4, 0, 1, 1)

        self.tabWidget_2.addTab(self.tab_7, "")
        self.tab_13 = QWidget()
        self.tab_13.setObjectName(u"tab_13")
        self.gridLayout_58 = QGridLayout(self.tab_13)
        self.gridLayout_58.setObjectName(u"gridLayout_58")
        self.label_86 = QLabel(self.tab_13)
        self.label_86.setObjectName(u"label_86")

        self.gridLayout_58.addWidget(self.label_86, 0, 0, 1, 1)

        self.lineEdit_externalProgram = QLineEdit(self.tab_13)
        self.lineEdit_externalProgram.setObjectName(u"lineEdit_externalProgram")

        self.gridLayout_58.addWidget(self.lineEdit_externalProgram, 0, 1, 1, 1)

        self.verticalSpacer_11 = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.gridLayout_58.addItem(self.verticalSpacer_11, 1, 0, 1, 1)

        self.tabWidget_2.addTab(self.tab_13, "")
        self.tab_12 = QWidget()
        self.tab_12.setObjectName(u"tab_12")
        self.gridLayout_73 = QGridLayout(self.tab_12)
        self.gridLayout_73.setObjectName(u"gridLayout_73")
        self.verticalSpacer_10 = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.gridLayout_73.addItem(self.verticalSpacer_10, 3, 0, 1, 1)

        self.gridLayout_72 = QGridLayout()
        self.gridLayout_72.setObjectName(u"gridLayout_72")
        self.checkBox_httpServer = QCheckBox(self.tab_12)
        self.checkBox_httpServer.setObjectName(u"checkBox_httpServer")

        self.gridLayout_72.addWidget(self.checkBox_httpServer, 1, 1, 1, 1)

        self.label_100 = QLabel(self.tab_12)
        self.label_100.setObjectName(u"label_100")

        self.gridLayout_72.addWidget(self.label_100, 1, 0, 1, 1)

        self.lineEdit_httpPort = QLineEdit(self.tab_12)
        self.lineEdit_httpPort.setObjectName(u"lineEdit_httpPort")
        sizePolicy2.setHeightForWidth(self.lineEdit_httpPort.sizePolicy().hasHeightForWidth())
        self.lineEdit_httpPort.setSizePolicy(sizePolicy2)

        self.gridLayout_72.addWidget(self.lineEdit_httpPort, 3, 1, 1, 1)

        self.lineEdit_httpAddr = QLineEdit(self.tab_12)
        self.lineEdit_httpAddr.setObjectName(u"lineEdit_httpAddr")
        sizePolicy2.setHeightForWidth(self.lineEdit_httpAddr.sizePolicy().hasHeightForWidth())
        self.lineEdit_httpAddr.setSizePolicy(sizePolicy2)

        self.gridLayout_72.addWidget(self.lineEdit_httpAddr, 2, 1, 1, 1)

        self.label_99 = QLabel(self.tab_12)
        self.label_99.setObjectName(u"label_99")

        self.gridLayout_72.addWidget(self.label_99, 3, 0, 1, 1)

        self.label_44 = QLabel(self.tab_12)
        self.label_44.setObjectName(u"label_44")

        self.gridLayout_72.addWidget(self.label_44, 2, 0, 1, 1)

        self.label_102 = QLabel(self.tab_12)
        self.label_102.setObjectName(u"label_102")

        self.gridLayout_72.addWidget(self.label_102, 4, 0, 1, 1)

        self.label_httpLink = QLabel(self.tab_12)
        self.label_httpLink.setObjectName(u"label_httpLink")

        self.gridLayout_72.addWidget(self.label_httpLink, 4, 1, 1, 1)


        self.gridLayout_73.addLayout(self.gridLayout_72, 0, 0, 1, 1)

        self.tabWidget_2.addTab(self.tab_12, "")
        self.tab_8 = QWidget()
        self.tab_8.setObjectName(u"tab_8")
        self.gridLayout_46 = QGridLayout(self.tab_8)
        self.gridLayout_46.setObjectName(u"gridLayout_46")
        self.gridLayout_21 = QGridLayout()
        self.gridLayout_21.setObjectName(u"gridLayout_21")
        self.label_10 = QLabel(self.tab_8)
        self.label_10.setObjectName(u"label_10")

        self.gridLayout_21.addWidget(self.label_10, 0, 2, 1, 1)

        self.spinBox_off_x_V = QDoubleSpinBox(self.tab_8)
        self.spinBox_off_x_V.setObjectName(u"spinBox_off_x_V")
        self.spinBox_off_x_V.setDecimals(6)
        self.spinBox_off_x_V.setMinimum(-99.000000000000000)

        self.gridLayout_21.addWidget(self.spinBox_off_x_V, 0, 1, 1, 1)

        self.spinBox_off_y_V = QDoubleSpinBox(self.tab_8)
        self.spinBox_off_y_V.setObjectName(u"spinBox_off_y_V")
        self.spinBox_off_y_V.setDecimals(6)
        self.spinBox_off_y_V.setMinimum(-99.000000000000000)

        self.gridLayout_21.addWidget(self.spinBox_off_y_V, 1, 1, 1, 1)

        self.spinBox_off_z_V = QDoubleSpinBox(self.tab_8)
        self.spinBox_off_z_V.setObjectName(u"spinBox_off_z_V")
        self.spinBox_off_z_V.setDecimals(6)
        self.spinBox_off_z_V.setMinimum(-99.000000000000000)

        self.gridLayout_21.addWidget(self.spinBox_off_z_V, 2, 1, 1, 1)

        self.label_8 = QLabel(self.tab_8)
        self.label_8.setObjectName(u"label_8")

        self.gridLayout_21.addWidget(self.label_8, 1, 0, 1, 1)

        self.label_11 = QLabel(self.tab_8)
        self.label_11.setObjectName(u"label_11")

        self.gridLayout_21.addWidget(self.label_11, 1, 2, 1, 1)

        self.label_9 = QLabel(self.tab_8)
        self.label_9.setObjectName(u"label_9")

        self.gridLayout_21.addWidget(self.label_9, 2, 0, 1, 1)

        self.label_12 = QLabel(self.tab_8)
        self.label_12.setObjectName(u"label_12")

        self.gridLayout_21.addWidget(self.label_12, 2, 2, 1, 1)

        self.label_7 = QLabel(self.tab_8)
        self.label_7.setObjectName(u"label_7")

        self.gridLayout_21.addWidget(self.label_7, 0, 0, 1, 1)

        self.horizontalSpacer_2 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.gridLayout_21.addItem(self.horizontalSpacer_2, 2, 3, 1, 1)


        self.gridLayout_46.addLayout(self.gridLayout_21, 3, 0, 1, 1)

        self.label_16 = QLabel(self.tab_8)
        self.label_16.setObjectName(u"label_16")

        self.gridLayout_46.addWidget(self.label_16, 0, 0, 1, 1)

        self.label_36 = QLabel(self.tab_8)
        self.label_36.setObjectName(u"label_36")

        self.gridLayout_46.addWidget(self.label_36, 2, 0, 1, 1)

        self.gridLayout_16 = QGridLayout()
        self.gridLayout_16.setObjectName(u"gridLayout_16")
        self.spinBox_calib_x = QDoubleSpinBox(self.tab_8)
        self.spinBox_calib_x.setObjectName(u"spinBox_calib_x")
        self.spinBox_calib_x.setDecimals(6)
        self.spinBox_calib_x.setMinimum(-1000.000000000000000)
        self.spinBox_calib_x.setMaximum(1000.000000000000000)
        self.spinBox_calib_x.setValue(8.900000000000000)

        self.gridLayout_16.addWidget(self.spinBox_calib_x, 0, 1, 1, 1)

        self.label_19 = QLabel(self.tab_8)
        self.label_19.setObjectName(u"label_19")

        self.gridLayout_16.addWidget(self.label_19, 1, 2, 1, 1)

        self.label_18 = QLabel(self.tab_8)
        self.label_18.setObjectName(u"label_18")

        self.gridLayout_16.addWidget(self.label_18, 0, 2, 1, 1)

        self.label_6 = QLabel(self.tab_8)
        self.label_6.setObjectName(u"label_6")

        self.gridLayout_16.addWidget(self.label_6, 2, 0, 1, 1)

        self.label_2 = QLabel(self.tab_8)
        self.label_2.setObjectName(u"label_2")

        self.gridLayout_16.addWidget(self.label_2, 0, 0, 1, 1)

        self.spinBox_calib_z = QDoubleSpinBox(self.tab_8)
        self.spinBox_calib_z.setObjectName(u"spinBox_calib_z")
        self.spinBox_calib_z.setDecimals(6)
        self.spinBox_calib_z.setMinimum(-1000.000000000000000)
        self.spinBox_calib_z.setMaximum(1000.000000000000000)
        self.spinBox_calib_z.setValue(10.000000000000000)

        self.gridLayout_16.addWidget(self.spinBox_calib_z, 2, 1, 1, 1)

        self.label_20 = QLabel(self.tab_8)
        self.label_20.setObjectName(u"label_20")

        self.gridLayout_16.addWidget(self.label_20, 2, 2, 1, 1)

        self.label_5 = QLabel(self.tab_8)
        self.label_5.setObjectName(u"label_5")

        self.gridLayout_16.addWidget(self.label_5, 1, 0, 1, 1)

        self.spinBox_calib_y = QDoubleSpinBox(self.tab_8)
        self.spinBox_calib_y.setObjectName(u"spinBox_calib_y")
        self.spinBox_calib_y.setDecimals(6)
        self.spinBox_calib_y.setMinimum(-1000.000000000000000)
        self.spinBox_calib_y.setMaximum(1000.000000000000000)
        self.spinBox_calib_y.setValue(8.900000000000000)

        self.gridLayout_16.addWidget(self.spinBox_calib_y, 1, 1, 1, 1)

        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.gridLayout_16.addItem(self.horizontalSpacer, 0, 3, 1, 1)


        self.gridLayout_46.addLayout(self.gridLayout_16, 1, 0, 1, 1)

        self.verticalSpacer_4 = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.gridLayout_46.addItem(self.verticalSpacer_4, 4, 0, 1, 1)

        self.tabWidget_2.addTab(self.tab_8, "")
        self.tab_9 = QWidget()
        self.tab_9.setObjectName(u"tab_9")
        self.gridLayout_30 = QGridLayout(self.tab_9)
        self.gridLayout_30.setObjectName(u"gridLayout_30")
        self.gridLayout_29 = QGridLayout()
        self.gridLayout_29.setObjectName(u"gridLayout_29")
        self.label_ttm_IP = QLabel(self.tab_9)
        self.label_ttm_IP.setObjectName(u"label_ttm_IP")
        self.label_ttm_IP.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)

        self.gridLayout_29.addWidget(self.label_ttm_IP, 1, 1, 1, 1)

        self.label_ttm_IP_5 = QLabel(self.tab_9)
        self.label_ttm_IP_5.setObjectName(u"label_ttm_IP_5")

        self.gridLayout_29.addWidget(self.label_ttm_IP_5, 2, 0, 1, 1)

        self.toolButton_ttm_filename = QToolButton(self.tab_9)
        self.toolButton_ttm_filename.setObjectName(u"toolButton_ttm_filename")

        self.gridLayout_29.addWidget(self.toolButton_ttm_filename, 2, 3, 1, 1)

        self.toolButton_ttm_executable_path = QToolButton(self.tab_9)
        self.toolButton_ttm_executable_path.setObjectName(u"toolButton_ttm_executable_path")

        self.gridLayout_29.addWidget(self.toolButton_ttm_executable_path, 3, 3, 1, 1)

        self.lineEdit_ttm_executable_path = QLineEdit(self.tab_9)
        self.lineEdit_ttm_executable_path.setObjectName(u"lineEdit_ttm_executable_path")

        self.gridLayout_29.addWidget(self.lineEdit_ttm_executable_path, 3, 1, 1, 1)

        self.label_ttm_IP_4 = QLabel(self.tab_9)
        self.label_ttm_IP_4.setObjectName(u"label_ttm_IP_4")

        self.gridLayout_29.addWidget(self.label_ttm_IP_4, 1, 0, 1, 1)

        self.label_ttm_IP_3 = QLabel(self.tab_9)
        self.label_ttm_IP_3.setObjectName(u"label_ttm_IP_3")

        self.gridLayout_29.addWidget(self.label_ttm_IP_3, 3, 0, 1, 1)

        self.lineEdit_ttmPort = QLineEdit(self.tab_9)
        self.lineEdit_ttmPort.setObjectName(u"lineEdit_ttmPort")
        sizePolicy2.setHeightForWidth(self.lineEdit_ttmPort.sizePolicy().hasHeightForWidth())
        self.lineEdit_ttmPort.setSizePolicy(sizePolicy2)

        self.gridLayout_29.addWidget(self.lineEdit_ttmPort, 1, 3, 1, 1)

        self.lineEdit_ttm_filename = QLineEdit(self.tab_9)
        self.lineEdit_ttm_filename.setObjectName(u"lineEdit_ttm_filename")

        self.gridLayout_29.addWidget(self.lineEdit_ttm_filename, 2, 1, 1, 1)

        self.radioButton_ttm_local = QRadioButton(self.tab_9)
        self.radioButton_ttm_local.setObjectName(u"radioButton_ttm_local")
        self.radioButton_ttm_local.setChecked(True)

        self.gridLayout_29.addWidget(self.radioButton_ttm_local, 0, 1, 1, 1)

        self.radioButton_ttm_remote = QRadioButton(self.tab_9)
        self.radioButton_ttm_remote.setObjectName(u"radioButton_ttm_remote")

        self.gridLayout_29.addWidget(self.radioButton_ttm_remote, 0, 3, 1, 1)


        self.gridLayout_30.addLayout(self.gridLayout_29, 0, 0, 1, 1)

        self.tabWidget_2.addTab(self.tab_9, "")
        self.tab_5 = QWidget()
        self.tab_5.setObjectName(u"tab_5")
        self.gridLayout_52 = QGridLayout(self.tab_5)
        self.gridLayout_52.setObjectName(u"gridLayout_52")
        self.label_90 = QLabel(self.tab_5)
        self.label_90.setObjectName(u"label_90")

        self.gridLayout_52.addWidget(self.label_90, 3, 0, 1, 1)

        self.label_63 = QLabel(self.tab_5)
        self.label_63.setObjectName(u"label_63")

        self.gridLayout_52.addWidget(self.label_63, 5, 0, 1, 1)

        self.comboBox_fifobackend = QComboBox(self.tab_5)
        self.comboBox_fifobackend.addItem("")
        self.comboBox_fifobackend.addItem("")
        self.comboBox_fifobackend.setObjectName(u"comboBox_fifobackend")

        self.gridLayout_52.addWidget(self.comboBox_fifobackend, 10, 1, 1, 3)

        self.spinBox_preview_buffer_size = QSpinBox(self.tab_5)
        self.spinBox_preview_buffer_size.setObjectName(u"spinBox_preview_buffer_size")
        self.spinBox_preview_buffer_size.setMaximum(1000000)
        self.spinBox_preview_buffer_size.setValue(15000)

        self.gridLayout_52.addWidget(self.spinBox_preview_buffer_size, 5, 1, 1, 1)

        self.spinBox_fifo_buffer_size = QSpinBox(self.tab_5)
        self.spinBox_fifo_buffer_size.setObjectName(u"spinBox_fifo_buffer_size")
        self.spinBox_fifo_buffer_size.setMaximum(10000000)
        self.spinBox_fifo_buffer_size.setValue(100000)

        self.gridLayout_52.addWidget(self.spinBox_fifo_buffer_size, 0, 1, 1, 1)

        self.label_fifo_prebuffer_len = QLabel(self.tab_5)
        self.label_fifo_prebuffer_len.setObjectName(u"label_fifo_prebuffer_len")

        self.gridLayout_52.addWidget(self.label_fifo_prebuffer_len, 4, 1, 1, 1)

        self.label_64 = QLabel(self.tab_5)
        self.label_64.setObjectName(u"label_64")

        self.gridLayout_52.addWidget(self.label_64, 1, 0, 1, 1)

        self.verticalSpacer_9 = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.gridLayout_52.addItem(self.verticalSpacer_9, 9, 0, 1, 1)

        self.label_actual_buffer_size = QLabel(self.tab_5)
        self.label_actual_buffer_size.setObjectName(u"label_actual_buffer_size")

        self.gridLayout_52.addWidget(self.label_actual_buffer_size, 1, 1, 1, 1)

        self.label_62 = QLabel(self.tab_5)
        self.label_62.setObjectName(u"label_62")

        self.gridLayout_52.addWidget(self.label_62, 0, 0, 1, 1)

        self.label_78 = QLabel(self.tab_5)
        self.label_78.setObjectName(u"label_78")

        self.gridLayout_52.addWidget(self.label_78, 2, 0, 1, 1)

        self.label_actual_preview_buffer_size = QLabel(self.tab_5)
        self.label_actual_preview_buffer_size.setObjectName(u"label_actual_preview_buffer_size")

        self.gridLayout_52.addWidget(self.label_actual_preview_buffer_size, 6, 1, 1, 1)

        self.label_fifo_last_pkt_size = QLabel(self.tab_5)
        self.label_fifo_last_pkt_size.setObjectName(u"label_fifo_last_pkt_size")

        self.gridLayout_52.addWidget(self.label_fifo_last_pkt_size, 2, 1, 1, 1)

        self.spinBox_fifo_timeout = QSpinBox(self.tab_5)
        self.spinBox_fifo_timeout.setObjectName(u"spinBox_fifo_timeout")
        self.spinBox_fifo_timeout.setMaximum(1000000)
        self.spinBox_fifo_timeout.setValue(10000)

        self.gridLayout_52.addWidget(self.spinBox_fifo_timeout, 7, 1, 1, 1)

        self.label_79 = QLabel(self.tab_5)
        self.label_79.setObjectName(u"label_79")

        self.gridLayout_52.addWidget(self.label_79, 6, 0, 1, 1)

        self.label_89 = QLabel(self.tab_5)
        self.label_89.setObjectName(u"label_89")

        self.gridLayout_52.addWidget(self.label_89, 4, 0, 1, 1)

        self.label_96 = QLabel(self.tab_5)
        self.label_96.setObjectName(u"label_96")

        self.gridLayout_52.addWidget(self.label_96, 7, 0, 1, 1)

        self.spinBox_fifo_prebuffer = QSpinBox(self.tab_5)
        self.spinBox_fifo_prebuffer.setObjectName(u"spinBox_fifo_prebuffer")
        self.spinBox_fifo_prebuffer.setMaximum(10000000)
        self.spinBox_fifo_prebuffer.setValue(12000)

        self.gridLayout_52.addWidget(self.spinBox_fifo_prebuffer, 3, 1, 1, 1)

        self.label_95 = QLabel(self.tab_5)
        self.label_95.setObjectName(u"label_95")

        self.gridLayout_52.addWidget(self.label_95, 10, 0, 1, 1)

        self.label_97 = QLabel(self.tab_5)
        self.label_97.setObjectName(u"label_97")

        self.gridLayout_52.addWidget(self.label_97, 8, 0, 1, 1)

        self.checkBox_DummyData = QCheckBox(self.tab_5)
        self.checkBox_DummyData.setObjectName(u"checkBox_DummyData")

        self.gridLayout_52.addWidget(self.checkBox_DummyData, 8, 1, 1, 1)

        self.tabWidget_2.addTab(self.tab_5, "")

        self.gridLayout_64.addWidget(self.tabWidget_2, 0, 0, 1, 1)

        self.scrollArea_2.setWidget(self.scrollAreaWidgetContents_2)

        self.gridLayout_37.addWidget(self.scrollArea_2, 0, 0, 1, 1)

        self.dockWidget_adv.setWidget(self.dockWidgetContents_15)
        MainWindowDesign.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.dockWidget_adv)
        self.dockWidget_debug = QDockWidget(MainWindowDesign)
        self.dockWidget_debug.setObjectName(u"dockWidget_debug")
        self.dockWidgetContents = QWidget()
        self.dockWidgetContents.setObjectName(u"dockWidgetContents")
        self.gridLayout_38 = QGridLayout(self.dockWidgetContents)
        self.gridLayout_38.setObjectName(u"gridLayout_38")
        self.scrollArea_5 = QScrollArea(self.dockWidgetContents)
        self.scrollArea_5.setObjectName(u"scrollArea_5")
        self.scrollArea_5.setWidgetResizable(True)
        self.scrollAreaWidgetContents_6 = QWidget()
        self.scrollAreaWidgetContents_6.setObjectName(u"scrollAreaWidgetContents_6")
        self.scrollAreaWidgetContents_6.setGeometry(QRect(0, 0, 422, 323))
        self.gridLayout_67 = QGridLayout(self.scrollAreaWidgetContents_6)
        self.gridLayout_67.setObjectName(u"gridLayout_67")
        self.checkBox_correlationMatrix = QCheckBox(self.scrollAreaWidgetContents_6)
        self.checkBox_correlationMatrix.setObjectName(u"checkBox_correlationMatrix")

        self.gridLayout_67.addWidget(self.checkBox_correlationMatrix, 1, 0, 1, 1)

        self.verticalSpacer_16 = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.gridLayout_67.addItem(self.verticalSpacer_16, 6, 0, 1, 1)

        self.progressBar_3 = QProgressBar(self.scrollAreaWidgetContents_6)
        self.progressBar_3.setObjectName(u"progressBar_3")
        self.progressBar_3.setValue(24)

        self.gridLayout_67.addWidget(self.progressBar_3, 3, 0, 1, 1)

        self.label_dummy = QLabel(self.scrollAreaWidgetContents_6)
        self.label_dummy.setObjectName(u"label_dummy")
        self.label_dummy.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)

        self.gridLayout_67.addWidget(self.label_dummy, 5, 0, 1, 1)

        self.gridLayout_23 = QGridLayout()
        self.gridLayout_23.setObjectName(u"gridLayout_23")
        self.pushButton_8 = QPushButton(self.scrollAreaWidgetContents_6)
        self.pushButton_8.setObjectName(u"pushButton_8")

        self.gridLayout_23.addWidget(self.pushButton_8, 2, 2, 1, 1)

        self.pushButton = QPushButton(self.scrollAreaWidgetContents_6)
        self.pushButton.setObjectName(u"pushButton")

        self.gridLayout_23.addWidget(self.pushButton, 1, 0, 1, 1)

        self.pushButton_6 = QPushButton(self.scrollAreaWidgetContents_6)
        self.pushButton_6.setObjectName(u"pushButton_6")

        self.gridLayout_23.addWidget(self.pushButton_6, 2, 0, 1, 1)

        self.pushButton_2 = QPushButton(self.scrollAreaWidgetContents_6)
        self.pushButton_2.setObjectName(u"pushButton_2")

        self.gridLayout_23.addWidget(self.pushButton_2, 1, 1, 1, 1)

        self.pushButton_11 = QPushButton(self.scrollAreaWidgetContents_6)
        self.pushButton_11.setObjectName(u"pushButton_11")

        self.gridLayout_23.addWidget(self.pushButton_11, 3, 2, 1, 1)

        self.pushButton_3 = QPushButton(self.scrollAreaWidgetContents_6)
        self.pushButton_3.setObjectName(u"pushButton_3")

        self.gridLayout_23.addWidget(self.pushButton_3, 1, 2, 1, 1)

        self.pushButton_10 = QPushButton(self.scrollAreaWidgetContents_6)
        self.pushButton_10.setObjectName(u"pushButton_10")

        self.gridLayout_23.addWidget(self.pushButton_10, 3, 1, 1, 1)

        self.pushButton_9 = QPushButton(self.scrollAreaWidgetContents_6)
        self.pushButton_9.setObjectName(u"pushButton_9")

        self.gridLayout_23.addWidget(self.pushButton_9, 3, 0, 1, 1)

        self.pushButton_7 = QPushButton(self.scrollAreaWidgetContents_6)
        self.pushButton_7.setObjectName(u"pushButton_7")

        self.gridLayout_23.addWidget(self.pushButton_7, 2, 1, 1, 1)

        self.pushButton_about = QPushButton(self.scrollAreaWidgetContents_6)
        self.pushButton_about.setObjectName(u"pushButton_about")

        self.gridLayout_23.addWidget(self.pushButton_about, 0, 0, 1, 1)

        self.pushButton_19 = QPushButton(self.scrollAreaWidgetContents_6)
        self.pushButton_19.setObjectName(u"pushButton_19")

        self.gridLayout_23.addWidget(self.pushButton_19, 4, 0, 1, 1)


        self.gridLayout_67.addLayout(self.gridLayout_23, 0, 0, 1, 1)

        self.progressBar_2 = QProgressBar(self.scrollAreaWidgetContents_6)
        self.progressBar_2.setObjectName(u"progressBar_2")
        self.progressBar_2.setValue(24)

        self.gridLayout_67.addWidget(self.progressBar_2, 2, 0, 1, 1)

        self.scrollArea_5.setWidget(self.scrollAreaWidgetContents_6)

        self.gridLayout_38.addWidget(self.scrollArea_5, 0, 0, 1, 1)

        self.dockWidget_debug.setWidget(self.dockWidgetContents)
        MainWindowDesign.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dockWidget_debug)
        self.dockWidget_panorama = QDockWidget(MainWindowDesign)
        self.dockWidget_panorama.setObjectName(u"dockWidget_panorama")
        self.dockWidget_panorama.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetFloatable|QDockWidget.DockWidgetFeature.DockWidgetMovable)
        self.dockWidgetContents_7 = QWidget()
        self.dockWidgetContents_7.setObjectName(u"dockWidgetContents_7")
        self.gridLayout_3 = QGridLayout(self.dockWidgetContents_7)
        self.gridLayout_3.setObjectName(u"gridLayout_3")
        self.gridLayout_22 = QGridLayout()
        self.gridLayout_22.setObjectName(u"gridLayout_22")

        self.gridLayout_3.addLayout(self.gridLayout_22, 0, 0, 1, 1)

        self.pushButton_grabPanorama = QPushButton(self.dockWidgetContents_7)
        self.pushButton_grabPanorama.setObjectName(u"pushButton_grabPanorama")

        self.gridLayout_3.addWidget(self.pushButton_grabPanorama, 1, 0, 1, 1)

        self.dockWidget_panorama.setWidget(self.dockWidgetContents_7)
        MainWindowDesign.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dockWidget_panorama)
        self.dockWidget_filename = QDockWidget(MainWindowDesign)
        self.dockWidget_filename.setObjectName(u"dockWidget_filename")
        self.dockWidget_filename.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetFloatable|QDockWidget.DockWidgetFeature.DockWidgetMovable)
        self.dockWidgetContents_11 = QWidget()
        self.dockWidgetContents_11.setObjectName(u"dockWidgetContents_11")
        self.gridLayout_51 = QGridLayout(self.dockWidgetContents_11)
        self.gridLayout_51.setObjectName(u"gridLayout_51")
        self.gridLayout_35 = QGridLayout()
        self.gridLayout_35.setObjectName(u"gridLayout_35")
        self.lineEdit_filename = QLineEdit(self.dockWidgetContents_11)
        self.lineEdit_filename.setObjectName(u"lineEdit_filename")

        self.gridLayout_35.addWidget(self.lineEdit_filename, 1, 1, 1, 1)

        self.label_61 = QLabel(self.dockWidgetContents_11)
        self.label_61.setObjectName(u"label_61")
        sizePolicy.setHeightForWidth(self.label_61.sizePolicy().hasHeightForWidth())
        self.label_61.setSizePolicy(sizePolicy)

        self.gridLayout_35.addWidget(self.label_61, 0, 0, 1, 1)

        self.label_77 = QLabel(self.dockWidgetContents_11)
        self.label_77.setObjectName(u"label_77")
        sizePolicy.setHeightForWidth(self.label_77.sizePolicy().hasHeightForWidth())
        self.label_77.setSizePolicy(sizePolicy)

        self.gridLayout_35.addWidget(self.label_77, 1, 0, 1, 1)

        self.toolButton_filename = QToolButton(self.dockWidgetContents_11)
        self.toolButton_filename.setObjectName(u"toolButton_filename")

        self.gridLayout_35.addWidget(self.toolButton_filename, 1, 2, 1, 1)

        self.lineEdit_destinationfolder = QLineEdit(self.dockWidgetContents_11)
        self.lineEdit_destinationfolder.setObjectName(u"lineEdit_destinationfolder")

        self.gridLayout_35.addWidget(self.lineEdit_destinationfolder, 0, 1, 1, 1)

        self.toolButton_destinationfolder = QToolButton(self.dockWidgetContents_11)
        self.toolButton_destinationfolder.setObjectName(u"toolButton_destinationfolder")

        self.gridLayout_35.addWidget(self.toolButton_destinationfolder, 0, 2, 1, 1)


        self.gridLayout_51.addLayout(self.gridLayout_35, 0, 0, 1, 1)

        self.lineEdit_comment = QTextEdit(self.dockWidgetContents_11)
        self.lineEdit_comment.setObjectName(u"lineEdit_comment")
        self.lineEdit_comment.setAcceptRichText(False)

        self.gridLayout_51.addWidget(self.lineEdit_comment, 1, 0, 1, 1)

        self.dockWidget_filename.setWidget(self.dockWidgetContents_11)
        MainWindowDesign.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.dockWidget_filename)
        self.dockWidget_listfile = QDockWidget(MainWindowDesign)
        self.dockWidget_listfile.setObjectName(u"dockWidget_listfile")
        self.dockWidget_listfile.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetFloatable|QDockWidget.DockWidgetFeature.DockWidgetMovable)
        self.dockWidgetContents_12 = QWidget()
        self.dockWidgetContents_12.setObjectName(u"dockWidgetContents_12")
        self.gridLayout_49 = QGridLayout(self.dockWidgetContents_12)
        self.gridLayout_49.setObjectName(u"gridLayout_49")
        self.horizontalSpacer_12 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.gridLayout_49.addItem(self.horizontalSpacer_12, 1, 0, 1, 1)

        self.pushButton_copyListFile = QPushButton(self.dockWidgetContents_12)
        self.pushButton_copyListFile.setObjectName(u"pushButton_copyListFile")

        self.gridLayout_49.addWidget(self.pushButton_copyListFile, 1, 2, 1, 1)

        self.pushButton_17 = QPushButton(self.dockWidgetContents_12)
        self.pushButton_17.setObjectName(u"pushButton_17")

        self.gridLayout_49.addWidget(self.pushButton_17, 1, 1, 1, 1)

        self.pushButton_openInExplorer = QPushButton(self.dockWidgetContents_12)
        self.pushButton_openInExplorer.setObjectName(u"pushButton_openInExplorer")

        self.gridLayout_49.addWidget(self.pushButton_openInExplorer, 1, 3, 1, 1)

        self.listWidget = QListWidget(self.dockWidgetContents_12)
        self.listWidget.setObjectName(u"listWidget")
        self.listWidget.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.listWidget.setSelectionRectVisible(True)

        self.gridLayout_49.addWidget(self.listWidget, 0, 0, 1, 4)

        self.dockWidget_listfile.setWidget(self.dockWidgetContents_12)
        MainWindowDesign.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.dockWidget_listfile)
        self.dockWidget_AnalogCfg = QDockWidget(MainWindowDesign)
        self.dockWidget_AnalogCfg.setObjectName(u"dockWidget_AnalogCfg")
        self.dockWidget_AnalogCfg.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetFloatable|QDockWidget.DockWidgetFeature.DockWidgetMovable)
        self.dockWidgetContents_14 = QWidget()
        self.dockWidgetContents_14.setObjectName(u"dockWidgetContents_14")
        self.gridLayout_53 = QGridLayout(self.dockWidgetContents_14)
        self.gridLayout_53.setObjectName(u"gridLayout_53")
        self.scrollArea = QScrollArea(self.dockWidgetContents_14)
        self.scrollArea.setObjectName(u"scrollArea")
        self.scrollArea.setWidgetResizable(True)
        self.scrollAreaWidgetContents = QWidget()
        self.scrollAreaWidgetContents.setObjectName(u"scrollAreaWidgetContents")
        self.scrollAreaWidgetContents.setGeometry(QRect(0, 0, 374, 184))
        self.gridLayout_63 = QGridLayout(self.scrollAreaWidgetContents)
        self.gridLayout_63.setObjectName(u"gridLayout_63")
        self.groupBox_4 = QGroupBox(self.scrollAreaWidgetContents)
        self.groupBox_4.setObjectName(u"groupBox_4")
        self.horizontalLayout_7 = QHBoxLayout(self.groupBox_4)
        self.horizontalLayout_7.setObjectName(u"horizontalLayout_7")
        self.comboBox_analogSelect_A = QComboBox(self.groupBox_4)
        self.comboBox_analogSelect_A.addItem("")
        self.comboBox_analogSelect_A.addItem("")
        self.comboBox_analogSelect_A.addItem("")
        self.comboBox_analogSelect_A.addItem("")
        self.comboBox_analogSelect_A.addItem("")
        self.comboBox_analogSelect_A.addItem("")
        self.comboBox_analogSelect_A.addItem("")
        self.comboBox_analogSelect_A.addItem("")
        self.comboBox_analogSelect_A.addItem("")
        self.comboBox_analogSelect_A.addItem("")
        self.comboBox_analogSelect_A.addItem("")
        self.comboBox_analogSelect_A.addItem("")
        self.comboBox_analogSelect_A.addItem("")
        self.comboBox_analogSelect_A.addItem("")
        self.comboBox_analogSelect_A.addItem("")
        self.comboBox_analogSelect_A.addItem("")
        self.comboBox_analogSelect_A.addItem("")
        self.comboBox_analogSelect_A.setObjectName(u"comboBox_analogSelect_A")

        self.horizontalLayout_7.addWidget(self.comboBox_analogSelect_A)

        self.checkBox_analog_in_differentiate_A = QCheckBox(self.groupBox_4)
        self.checkBox_analog_in_differentiate_A.setObjectName(u"checkBox_analog_in_differentiate_A")

        self.horizontalLayout_7.addWidget(self.checkBox_analog_in_differentiate_A)


        self.gridLayout_63.addWidget(self.groupBox_4, 1, 0, 1, 1)

        self.groupBox_5 = QGroupBox(self.scrollAreaWidgetContents)
        self.groupBox_5.setObjectName(u"groupBox_5")
        self.horizontalLayout_8 = QHBoxLayout(self.groupBox_5)
        self.horizontalLayout_8.setObjectName(u"horizontalLayout_8")
        self.comboBox_analogSelect_B = QComboBox(self.groupBox_5)
        self.comboBox_analogSelect_B.addItem("")
        self.comboBox_analogSelect_B.addItem("")
        self.comboBox_analogSelect_B.addItem("")
        self.comboBox_analogSelect_B.addItem("")
        self.comboBox_analogSelect_B.addItem("")
        self.comboBox_analogSelect_B.addItem("")
        self.comboBox_analogSelect_B.addItem("")
        self.comboBox_analogSelect_B.addItem("")
        self.comboBox_analogSelect_B.addItem("")
        self.comboBox_analogSelect_B.addItem("")
        self.comboBox_analogSelect_B.addItem("")
        self.comboBox_analogSelect_B.addItem("")
        self.comboBox_analogSelect_B.addItem("")
        self.comboBox_analogSelect_B.addItem("")
        self.comboBox_analogSelect_B.addItem("")
        self.comboBox_analogSelect_B.addItem("")
        self.comboBox_analogSelect_B.addItem("")
        self.comboBox_analogSelect_B.setObjectName(u"comboBox_analogSelect_B")

        self.horizontalLayout_8.addWidget(self.comboBox_analogSelect_B)

        self.checkBox_analog_in_differentiate_B = QCheckBox(self.groupBox_5)
        self.checkBox_analog_in_differentiate_B.setObjectName(u"checkBox_analog_in_differentiate_B")

        self.horizontalLayout_8.addWidget(self.checkBox_analog_in_differentiate_B)


        self.gridLayout_63.addWidget(self.groupBox_5, 1, 1, 1, 1)

        self.gridLayout_48 = QGridLayout()
        self.gridLayout_48.setObjectName(u"gridLayout_48")
        self.gridLayout_54 = QGridLayout()
        self.gridLayout_54.setObjectName(u"gridLayout_54")
        self.checkBox_analog_in_invert_AI1 = QCheckBox(self.scrollAreaWidgetContents)
        self.checkBox_analog_in_invert_AI1.setObjectName(u"checkBox_analog_in_invert_AI1")

        self.gridLayout_54.addWidget(self.checkBox_analog_in_invert_AI1, 1, 1, 1, 1)

        self.label_83 = QLabel(self.scrollAreaWidgetContents)
        self.label_83.setObjectName(u"label_83")

        self.gridLayout_54.addWidget(self.label_83, 2, 0, 1, 1)

        self.checkBox_analog_in_integrate_AI0 = QCheckBox(self.scrollAreaWidgetContents)
        self.checkBox_analog_in_integrate_AI0.setObjectName(u"checkBox_analog_in_integrate_AI0")

        self.gridLayout_54.addWidget(self.checkBox_analog_in_integrate_AI0, 0, 2, 1, 1)

        self.label_82 = QLabel(self.scrollAreaWidgetContents)
        self.label_82.setObjectName(u"label_82")

        self.gridLayout_54.addWidget(self.label_82, 1, 0, 1, 1)

        self.checkBox_analog_in_invert_AI3 = QCheckBox(self.scrollAreaWidgetContents)
        self.checkBox_analog_in_invert_AI3.setObjectName(u"checkBox_analog_in_invert_AI3")

        self.gridLayout_54.addWidget(self.checkBox_analog_in_invert_AI3, 3, 1, 1, 1)

        self.checkBox_analog_in_invert_AI0 = QCheckBox(self.scrollAreaWidgetContents)
        self.checkBox_analog_in_invert_AI0.setObjectName(u"checkBox_analog_in_invert_AI0")

        self.gridLayout_54.addWidget(self.checkBox_analog_in_invert_AI0, 0, 1, 1, 1)

        self.checkBox_analog_in_invert_AI2 = QCheckBox(self.scrollAreaWidgetContents)
        self.checkBox_analog_in_invert_AI2.setObjectName(u"checkBox_analog_in_invert_AI2")

        self.gridLayout_54.addWidget(self.checkBox_analog_in_invert_AI2, 2, 1, 1, 1)

        self.label_80 = QLabel(self.scrollAreaWidgetContents)
        self.label_80.setObjectName(u"label_80")

        self.gridLayout_54.addWidget(self.label_80, 0, 0, 1, 1)

        self.label_84 = QLabel(self.scrollAreaWidgetContents)
        self.label_84.setObjectName(u"label_84")

        self.gridLayout_54.addWidget(self.label_84, 3, 0, 1, 1)

        self.checkBox_analog_in_integrate_AI1 = QCheckBox(self.scrollAreaWidgetContents)
        self.checkBox_analog_in_integrate_AI1.setObjectName(u"checkBox_analog_in_integrate_AI1")

        self.gridLayout_54.addWidget(self.checkBox_analog_in_integrate_AI1, 1, 2, 1, 1)

        self.checkBox_analog_in_integrate_AI2 = QCheckBox(self.scrollAreaWidgetContents)
        self.checkBox_analog_in_integrate_AI2.setObjectName(u"checkBox_analog_in_integrate_AI2")

        self.gridLayout_54.addWidget(self.checkBox_analog_in_integrate_AI2, 2, 2, 1, 1)

        self.checkBox_analog_in_integrate_AI3 = QCheckBox(self.scrollAreaWidgetContents)
        self.checkBox_analog_in_integrate_AI3.setObjectName(u"checkBox_analog_in_integrate_AI3")

        self.gridLayout_54.addWidget(self.checkBox_analog_in_integrate_AI3, 3, 2, 1, 1)


        self.gridLayout_48.addLayout(self.gridLayout_54, 0, 0, 1, 1)


        self.gridLayout_63.addLayout(self.gridLayout_48, 0, 0, 1, 2)

        self.scrollArea.setWidget(self.scrollAreaWidgetContents)

        self.gridLayout_53.addWidget(self.scrollArea, 0, 0, 1, 1)

        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.gridLayout_53.addItem(self.verticalSpacer, 1, 0, 1, 1)

        self.dockWidget_AnalogCfg.setWidget(self.dockWidgetContents_14)
        MainWindowDesign.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.dockWidget_AnalogCfg)
        self.dockWidget_plugins = QDockWidget(MainWindowDesign)
        self.dockWidget_plugins.setObjectName(u"dockWidget_plugins")
        self.dockWidget_plugins.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetFloatable|QDockWidget.DockWidgetFeature.DockWidgetMovable)
        self.dockWidgetContents_17 = QWidget()
        self.dockWidgetContents_17.setObjectName(u"dockWidgetContents_17")
        self.gridLayout_57 = QGridLayout(self.dockWidgetContents_17)
        self.gridLayout_57.setObjectName(u"gridLayout_57")
        self.scrollArea_4 = QScrollArea(self.dockWidgetContents_17)
        self.scrollArea_4.setObjectName(u"scrollArea_4")
        self.scrollArea_4.setWidgetResizable(True)
        self.scrollAreaWidgetContents_5 = QWidget()
        self.scrollAreaWidgetContents_5.setObjectName(u"scrollAreaWidgetContents_5")
        self.scrollAreaWidgetContents_5.setGeometry(QRect(0, 0, 422, 244))
        self.gridLayout_66 = QGridLayout(self.scrollAreaWidgetContents_5)
        self.gridLayout_66.setObjectName(u"gridLayout_66")
        self.pushButton_loadPlugin = QPushButton(self.scrollAreaWidgetContents_5)
        self.pushButton_loadPlugin.setObjectName(u"pushButton_loadPlugin")

        self.gridLayout_66.addWidget(self.pushButton_loadPlugin, 1, 0, 1, 1)

        self.horizontalSpacer_10 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.gridLayout_66.addItem(self.horizontalSpacer_10, 1, 2, 1, 1)

        self.pushButton_5 = QPushButton(self.scrollAreaWidgetContents_5)
        self.pushButton_5.setObjectName(u"pushButton_5")

        self.gridLayout_66.addWidget(self.pushButton_5, 1, 3, 1, 1)

        self.pushButton_closePlugin = QPushButton(self.scrollAreaWidgetContents_5)
        self.pushButton_closePlugin.setObjectName(u"pushButton_closePlugin")

        self.gridLayout_66.addWidget(self.pushButton_closePlugin, 1, 1, 1, 1)

        self.listWidget_plugins = QListWidget(self.scrollAreaWidgetContents_5)
        self.listWidget_plugins.setObjectName(u"listWidget_plugins")

        self.gridLayout_66.addWidget(self.listWidget_plugins, 2, 0, 1, 4)

        self.scrollArea_4.setWidget(self.scrollAreaWidgetContents_5)

        self.gridLayout_57.addWidget(self.scrollArea_4, 0, 0, 1, 1)

        self.dockWidget_plugins.setWidget(self.dockWidgetContents_17)
        MainWindowDesign.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dockWidget_plugins)
        self.dockWidget_analogOut = QDockWidget(MainWindowDesign)
        self.dockWidget_analogOut.setObjectName(u"dockWidget_analogOut")
        self.dockWidget_analogOut.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetFloatable|QDockWidget.DockWidgetFeature.DockWidgetMovable)
        self.dockWidgetContents_18 = QWidget()
        self.dockWidgetContents_18.setObjectName(u"dockWidgetContents_18")
        self.gridLayout_60 = QGridLayout(self.dockWidgetContents_18)
        self.gridLayout_60.setObjectName(u"gridLayout_60")
        self.scrollArea_3 = QScrollArea(self.dockWidgetContents_18)
        self.scrollArea_3.setObjectName(u"scrollArea_3")
        self.scrollArea_3.setWidgetResizable(True)
        self.scrollAreaWidgetContents_3 = QWidget()
        self.scrollAreaWidgetContents_3.setObjectName(u"scrollAreaWidgetContents_3")
        self.scrollAreaWidgetContents_3.setGeometry(QRect(0, 0, 422, 112))
        self.gridLayout_65 = QGridLayout(self.scrollAreaWidgetContents_3)
        self.gridLayout_65.setObjectName(u"gridLayout_65")
        self.gridLayout_AO = QGridLayout()
        self.gridLayout_AO.setObjectName(u"gridLayout_AO")
        self.label_AnalogOut_checkbox_titl = QLabel(self.scrollAreaWidgetContents_3)
        self.label_AnalogOut_checkbox_titl.setObjectName(u"label_AnalogOut_checkbox_titl")

        self.gridLayout_AO.addWidget(self.label_AnalogOut_checkbox_titl, 0, 3, 1, 1)

        self.label_AnalogOut_title2 = QLabel(self.scrollAreaWidgetContents_3)
        self.label_AnalogOut_title2.setObjectName(u"label_AnalogOut_title2")

        self.gridLayout_AO.addWidget(self.label_AnalogOut_title2, 0, 1, 1, 1)

        self.spinBox_AnalogOut = QDoubleSpinBox(self.scrollAreaWidgetContents_3)
        self.spinBox_AnalogOut.setObjectName(u"spinBox_AnalogOut")
        self.spinBox_AnalogOut.setDecimals(4)
        self.spinBox_AnalogOut.setMinimum(-10.000000000000000)
        self.spinBox_AnalogOut.setMaximum(10.000000000000000)

        self.gridLayout_AO.addWidget(self.spinBox_AnalogOut, 1, 2, 1, 1)

        self.comboBox_AnalogOut = QComboBox(self.scrollAreaWidgetContents_3)
        self.comboBox_AnalogOut.addItem("")
        self.comboBox_AnalogOut.addItem("")
        self.comboBox_AnalogOut.addItem("")
        self.comboBox_AnalogOut.addItem("")
        self.comboBox_AnalogOut.setObjectName(u"comboBox_AnalogOut")

        self.gridLayout_AO.addWidget(self.comboBox_AnalogOut, 1, 1, 1, 1)

        self.label_AnalogOut = QLabel(self.scrollAreaWidgetContents_3)
        self.label_AnalogOut.setObjectName(u"label_AnalogOut")

        self.gridLayout_AO.addWidget(self.label_AnalogOut, 1, 0, 1, 1)

        self.label_AnalogOut_title1 = QLabel(self.scrollAreaWidgetContents_3)
        self.label_AnalogOut_title1.setObjectName(u"label_AnalogOut_title1")

        self.gridLayout_AO.addWidget(self.label_AnalogOut_title1, 0, 0, 1, 1)

        self.label_AnalogOut_title3 = QLabel(self.scrollAreaWidgetContents_3)
        self.label_AnalogOut_title3.setObjectName(u"label_AnalogOut_title3")

        self.gridLayout_AO.addWidget(self.label_AnalogOut_title3, 0, 2, 1, 1)

        self.checkBox_AnalogOut = QCheckBox(self.scrollAreaWidgetContents_3)
        self.checkBox_AnalogOut.setObjectName(u"checkBox_AnalogOut")

        self.gridLayout_AO.addWidget(self.checkBox_AnalogOut, 1, 3, 1, 1)


        self.gridLayout_65.addLayout(self.gridLayout_AO, 0, 0, 1, 1)

        self.verticalSpacer_14 = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.gridLayout_65.addItem(self.verticalSpacer_14, 1, 0, 1, 1)

        self.scrollArea_3.setWidget(self.scrollAreaWidgetContents_3)

        self.gridLayout_60.addWidget(self.scrollArea_3, 0, 0, 1, 1)

        self.dockWidget_analogOut.setWidget(self.dockWidgetContents_18)
        MainWindowDesign.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dockWidget_analogOut)
        self.dockWidget_traceConf = QDockWidget(MainWindowDesign)
        self.dockWidget_traceConf.setObjectName(u"dockWidget_traceConf")
        self.dockWidget_traceConf.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetFloatable|QDockWidget.DockWidgetFeature.DockWidgetMovable)
        self.dockWidgetContents_20 = QWidget()
        self.dockWidgetContents_20.setObjectName(u"dockWidgetContents_20")
        self.gridLayout_70 = QGridLayout(self.dockWidgetContents_20)
        self.gridLayout_70.setObjectName(u"gridLayout_70")
        self.gridLayout_62 = QGridLayout()
        self.gridLayout_62.setObjectName(u"gridLayout_62")
        self.gridLayout_62.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        self.label_73 = QLabel(self.dockWidgetContents_20)
        self.label_73.setObjectName(u"label_73")

        self.gridLayout_62.addWidget(self.label_73, 2, 0, 1, 1)

        self.checkBox_trace_on = QCheckBox(self.dockWidgetContents_20)
        self.checkBox_trace_on.setObjectName(u"checkBox_trace_on")
        self.checkBox_trace_on.setChecked(True)

        self.gridLayout_62.addWidget(self.checkBox_trace_on, 0, 2, 1, 1)

        self.pushButton_trace = QPushButton(self.dockWidgetContents_20)
        self.pushButton_trace.setObjectName(u"pushButton_trace")

        self.gridLayout_62.addWidget(self.pushButton_trace, 0, 0, 1, 1)

        self.checkBox_trace_autorange = QCheckBox(self.dockWidgetContents_20)
        self.checkBox_trace_autorange.setObjectName(u"checkBox_trace_autorange")
        self.checkBox_trace_autorange.setChecked(True)

        self.gridLayout_62.addWidget(self.checkBox_trace_autorange, 0, 3, 1, 1)

        self.doubleSpinBox_binsize = QDoubleSpinBox(self.dockWidgetContents_20)
        self.doubleSpinBox_binsize.setObjectName(u"doubleSpinBox_binsize")
        self.doubleSpinBox_binsize.setDecimals(4)
        self.doubleSpinBox_binsize.setMinimum(0.010000000000000)
        self.doubleSpinBox_binsize.setValue(10.000000000000000)

        self.gridLayout_62.addWidget(self.doubleSpinBox_binsize, 2, 1, 1, 1)

        self.doubleSpinBox_maxlength = QDoubleSpinBox(self.dockWidgetContents_20)
        self.doubleSpinBox_maxlength.setObjectName(u"doubleSpinBox_maxlength")
        self.doubleSpinBox_maxlength.setDecimals(4)
        self.doubleSpinBox_maxlength.setMinimum(0.010000000000000)
        self.doubleSpinBox_maxlength.setMaximum(99999.990000000005239)
        self.doubleSpinBox_maxlength.setValue(300.000000000000000)

        self.gridLayout_62.addWidget(self.doubleSpinBox_maxlength, 2, 3, 1, 1)

        self.label_74 = QLabel(self.dockWidgetContents_20)
        self.label_74.setObjectName(u"label_74")

        self.gridLayout_62.addWidget(self.label_74, 2, 2, 1, 1)

        self.label_trace_total_bins = QLabel(self.dockWidgetContents_20)
        self.label_trace_total_bins.setObjectName(u"label_trace_total_bins")

        self.gridLayout_62.addWidget(self.label_trace_total_bins, 4, 3, 1, 1)

        self.label_76 = QLabel(self.dockWidgetContents_20)
        self.label_76.setObjectName(u"label_76")

        self.gridLayout_62.addWidget(self.label_76, 4, 2, 1, 1)

        self.label_plot_channel = QLabel(self.dockWidgetContents_20)
        self.label_plot_channel.setObjectName(u"label_plot_channel")
        sizePolicy.setHeightForWidth(self.label_plot_channel.sizePolicy().hasHeightForWidth())
        self.label_plot_channel.setSizePolicy(sizePolicy)

        self.gridLayout_62.addWidget(self.label_plot_channel, 4, 0, 1, 1)


        self.gridLayout_70.addLayout(self.gridLayout_62, 0, 0, 1, 1)

        self.dockWidget_traceConf.setWidget(self.dockWidgetContents_20)
        MainWindowDesign.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dockWidget_traceConf)
        self.dockWidget_pluginImage = QDockWidget(MainWindowDesign)
        self.dockWidget_pluginImage.setObjectName(u"dockWidget_pluginImage")
        self.dockWidget_pluginImage.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetFloatable|QDockWidget.DockWidgetFeature.DockWidgetMovable)
        self.dockWidgetContents_21 = QWidget()
        self.dockWidgetContents_21.setObjectName(u"dockWidgetContents_21")
        self.gridLayout_71 = QGridLayout(self.dockWidgetContents_21)
        self.gridLayout_71.setObjectName(u"gridLayout_71")
        self.gridLayout_pluginImage = QGridLayout()
        self.gridLayout_pluginImage.setObjectName(u"gridLayout_pluginImage")

        self.gridLayout_71.addLayout(self.gridLayout_pluginImage, 0, 0, 1, 1)

        self.dockWidget_pluginImage.setWidget(self.dockWidgetContents_21)
        MainWindowDesign.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dockWidget_pluginImage)
        QWidget.setTabOrder(self.spinBox_time_bin_per_px, self.spinBox_timeresolution)
        QWidget.setTabOrder(self.spinBox_timeresolution, self.pushButton)
        QWidget.setTabOrder(self.pushButton, self.pushButton_7)
        QWidget.setTabOrder(self.pushButton_7, self.pushButton_3)
        QWidget.setTabOrder(self.pushButton_3, self.pushButton_8)
        QWidget.setTabOrder(self.pushButton_8, self.pushButton_2)
        QWidget.setTabOrder(self.pushButton_2, self.pushButton_6)
        QWidget.setTabOrder(self.pushButton_6, self.pushButton_9)
        QWidget.setTabOrder(self.pushButton_9, self.pushButton_10)
        QWidget.setTabOrder(self.pushButton_10, self.pushButton_11)
        QWidget.setTabOrder(self.pushButton_11, self.spinBox_nframe)
        QWidget.setTabOrder(self.spinBox_nframe, self.spinBox_ny)
        QWidget.setTabOrder(self.spinBox_ny, self.spinBox_nx)
        QWidget.setTabOrder(self.spinBox_nx, self.spinBox_nrepetition)
        QWidget.setTabOrder(self.spinBox_nrepetition, self.spinBox_off_z_um)
        QWidget.setTabOrder(self.spinBox_off_z_um, self.spinBox_off_y_um)
        QWidget.setTabOrder(self.spinBox_off_y_um, self.spinBox_off_x_um)
        QWidget.setTabOrder(self.spinBox_off_x_um, self.spinBox_off_x_V)
        QWidget.setTabOrder(self.spinBox_off_x_V, self.spinBox_off_y_V)
        QWidget.setTabOrder(self.spinBox_off_y_V, self.spinBox_off_z_V)
        QWidget.setTabOrder(self.spinBox_off_z_V, self.spinBox_calib_x)
        QWidget.setTabOrder(self.spinBox_calib_x, self.spinBox_calib_z)
        QWidget.setTabOrder(self.spinBox_calib_z, self.spinBox_calib_y)

        self.retranslateUi(MainWindowDesign)
        self.spinBox_timeresolution.valueChanged.connect(MainWindowDesign.temporalSettingsChanged)
        self.spinBox_time_bin_per_px.valueChanged.connect(MainWindowDesign.temporalSettingsChanged)
        self.pushButton.clicked.connect(MainWindowDesign.test1)
        self.pushButton_2.clicked.connect(MainWindowDesign.test2)
        self.pushButton_3.clicked.connect(MainWindowDesign.test3)
        self.spinBox_calib_x.valueChanged.connect(MainWindowDesign.calibrationFactorChanged)
        self.spinBox_calib_y.valueChanged.connect(MainWindowDesign.calibrationFactorChanged)
        self.spinBox_calib_z.valueChanged.connect(MainWindowDesign.calibrationFactorChanged)
        self.spinBox_off_x_V.valueChanged.connect(MainWindowDesign.offset_V_Changed)
        self.spinBox_off_y_V.valueChanged.connect(MainWindowDesign.offset_V_Changed)
        self.spinBox_off_z_V.valueChanged.connect(MainWindowDesign.offset_V_Changed)
        self.spinBox_off_x_um.valueChanged.connect(MainWindowDesign.offset_um_Changed)
        self.spinBox_off_y_um.valueChanged.connect(MainWindowDesign.offset_um_Changed)
        self.spinBox_off_z_um.valueChanged.connect(MainWindowDesign.offset_um_Changed)
        self.pushButton_6.clicked.connect(MainWindowDesign.test4)
        self.pushButton_7.clicked.connect(MainWindowDesign.test5)
        self.pushButton_8.clicked.connect(MainWindowDesign.test6)
        self.pushButton_9.clicked.connect(MainWindowDesign.test7)
        self.pushButton_10.clicked.connect(MainWindowDesign.test8)
        self.pushButton_11.clicked.connect(MainWindowDesign.test9)
        self.checkBoxLockRatio.clicked.connect(MainWindowDesign.checkBoxLockRatioChanged)
        self.spinBox_offExtra_x_V.valueChanged.connect(MainWindowDesign.positionSettingsChanged)
        self.spinBox_offExtra_y_V.valueChanged.connect(MainWindowDesign.positionSettingsChanged)
        self.spinBox_offExtra_z_V.valueChanged.connect(MainWindowDesign.positionSettingsChanged)
        self.spinBox_range_x.valueChanged.connect(MainWindowDesign.rangeValueChanged)
        self.spinBox_range_y.valueChanged.connect(MainWindowDesign.rangeValueChanged)
        self.spinBox_range_z.valueChanged.connect(MainWindowDesign.rangeValueChanged)
        self.pushButton_previewStart.clicked.connect(MainWindowDesign.previewButtonClicked)
        self.pushButton_acquisitionStart.clicked.connect(MainWindowDesign.startButtonClicked)
        self.pushButton_stop.clicked.connect(MainWindowDesign.stopButtonClicked)
        self.comboBox_plot_channel.currentTextChanged.connect(MainWindowDesign.plotSettingsChanged)
        self.checkBox_autoscale_img.stateChanged.connect(MainWindowDesign.selectedAutoscaleImg)
        self.comboBox_view_projection.currentTextChanged.connect(MainWindowDesign.projChanged)
        self.pushButton_startBatchFCS.clicked.connect(MainWindowDesign.startBatchFCS)
        self.pushButton_copyPositionsMarkers.clicked.connect(MainWindowDesign.copyPositionsMarkers)
        self.pushButton_12.clicked.connect(MainWindowDesign.stopBatchFCS)
        self.checkBox_laser0.clicked.connect(MainWindowDesign.laserChanged)
        self.checkBox_laser1.clicked.connect(MainWindowDesign.laserChanged)
        self.checkBox_laser2.clicked.connect(MainWindowDesign.laserChanged)
        self.checkBox_laser3.clicked.connect(MainWindowDesign.laserChanged)
        self.pushButton_13.clicked.connect(MainWindowDesign.cmd_moveToSelectedColumnFCS)
        self.pushButton_15.clicked.connect(MainWindowDesign.cmd_moveToSelectedRowMarker)
        self.pushButton_14.clicked.connect(MainWindowDesign.addToBatch)
        self.toolButton_destinationfolder.clicked.connect(MainWindowDesign.cmd_path_destinationfolder)
        self.pushButton_FPGA_file_selection.clicked.connect(MainWindowDesign.bit_file_clicked)
        self.pushButton_grabPanorama.clicked.connect(MainWindowDesign.grabPanorama)
        self.spinBox_nrepetition.valueChanged.connect(MainWindowDesign.spatialSettingsChanged)
        self.spinBox_nframe.valueChanged.connect(MainWindowDesign.spatialSettingsChanged)
        self.spinBox_nx.valueChanged.connect(MainWindowDesign.spatialSettingsChanged)
        self.pushButton_Panorama.clicked.connect(MainWindowDesign.panoramaButton)
        self.spinBox_ny.valueChanged.connect(MainWindowDesign.spatialSettingsChanged)
        self.pushButton_FCS_reset.clicked.connect(MainWindowDesign.FCSReset)
        self.toolButton_filename.clicked.connect(MainWindowDesign.cmd_filename)
        self.toolButton_ttm_executable_path.clicked.connect(MainWindowDesign.cmd_path_ttm)
        self.toolButton_ttm_filename.clicked.connect(MainWindowDesign.cmd_filename_ttm)
        self.checkBox_ttmActivate.stateChanged.connect(MainWindowDesign.ttm_activate_change_state)
        self.radioButton_ttm_local.toggled.connect(MainWindowDesign.radio_ttm_local)
        self.radioButton_ttm_remote.toggled.connect(MainWindowDesign.radio_ttm_remote)
        self.pushButton_loadPlugin.clicked.connect(MainWindowDesign.cmd_load_plugin)
        self.pushButton_closePlugin.clicked.connect(MainWindowDesign.cmd_close_plugin)
        self.pushButton_5.clicked.connect(MainWindowDesign.cmd_update_plugin_list)
        self.listWidget_plugins.itemDoubleClicked.connect(MainWindowDesign.cmd_load_plugin)
        self.pushButton_externalProgram.clicked.connect(MainWindowDesign.cmd_call_external)
        self.pushButton_copyListFile.clicked.connect(MainWindowDesign.copy_list_file)
        self.pushButton_17.clicked.connect(MainWindowDesign.delete_list_file)
        self.spinBox_AnalogOut.valueChanged.connect(MainWindowDesign.analogOutChanged)
        self.comboBox_AnalogOut.currentIndexChanged.connect(MainWindowDesign.analogOutChanged)
        self.pushButton_FPGA2_file_selection.clicked.connect(MainWindowDesign.bit_file_clicked2)
        self.comboBox_fingerprint.currentIndexChanged.connect(MainWindowDesign.microimageType)
        self.checkBox_autoscale_fingerprint.stateChanged.connect(MainWindowDesign.selectedAutoscaleFingerprint)
        self.pushButton_4.clicked.connect(MainWindowDesign.selectChannelSum)
        self.pushButton_18.clicked.connect(MainWindowDesign.updatePixelValueChanged)
        self.checkBox_DFD.clicked.connect(MainWindowDesign.DFD_clicked)
        self.pushButton_loadPreset.clicked.connect(MainWindowDesign.loadPreset)
        self.pushButton_savePreset.clicked.connect(MainWindowDesign.savePreset)
        self.pushButton_trace.clicked.connect(MainWindowDesign.traceReset)
        self.doubleSpinBox_binsize.valueChanged.connect(MainWindowDesign.trace_parameters_changed)
        self.doubleSpinBox_maxlength.valueChanged.connect(MainWindowDesign.trace_parameters_changed)
        self.checkBox_trace_autorange.clicked.connect(MainWindowDesign.trace_parameters_changed)
        self.checkBox_trace_on.clicked.connect(MainWindowDesign.trace_parameters_changed)
        self.pushButton_about.clicked.connect(MainWindowDesign.about)
        self.radioButton_digital.clicked.connect(MainWindowDesign.checkAlerts)
        self.radioButton_analog.clicked.connect(MainWindowDesign.checkAlerts)
        self.checkBox_circular.clicked.connect(MainWindowDesign.circularMotionActivateChanged)
        self.spinBox_circular_points.valueChanged.connect(MainWindowDesign.circularMotionActivateChanged)
        self.pushButton_19.clicked.connect(MainWindowDesign.test_analog_digital)
        self.checkBox_httpServer.stateChanged.connect(MainWindowDesign.httpServerCheckBoxChanged)
        self.pushButton_currentConfToBatch.clicked.connect(MainWindowDesign.addcurrentconfmacro)
        self.pushButton_currentConfToBatchFCS.clicked.connect(MainWindowDesign.addcurrentconfmacrofcs)
        self.pushButton_copyPositionsMarkersFCS.clicked.connect(MainWindowDesign.copyPositionsMarkersFCS)
        self.spinBox_circular_radius_nm.valueChanged.connect(MainWindowDesign.circularMotionActivateChanged)
        self.spinBox_circular_repetition.valueChanged.connect(MainWindowDesign.circularMotionActivateChanged)
        self.pushButton_openInExplorer.clicked.connect(MainWindowDesign.openInExplorer)

        self.tabWidget.setCurrentIndex(0)
        self.tabWidget_circular.setCurrentIndex(0)
        self.comboBox_slavemode_type.setCurrentIndex(2)
        self.comboLaserSeq_1.setCurrentIndex(1)
        self.tabWidget_2.setCurrentIndex(0)
        self.comboBox_analogSelect_B.setCurrentIndex(0)


        QMetaObject.connectSlotsByName(MainWindowDesign)
    # setupUi

    def retranslateUi(self, MainWindowDesign):
        MainWindowDesign.setWindowTitle(QCoreApplication.translate("MainWindowDesign", u"MainWindow", None))
        self.comboBox_view_projection.setItemText(0, QCoreApplication.translate("MainWindowDesign", u"xy", None))
        self.comboBox_view_projection.setItemText(1, QCoreApplication.translate("MainWindowDesign", u"zy", None))
        self.comboBox_view_projection.setItemText(2, QCoreApplication.translate("MainWindowDesign", u"xz", None))
        self.comboBox_view_projection.setItemText(3, QCoreApplication.translate("MainWindowDesign", u"yz", None))
        self.comboBox_view_projection.setItemText(4, QCoreApplication.translate("MainWindowDesign", u"zx", None))
        self.comboBox_view_projection.setItemText(5, QCoreApplication.translate("MainWindowDesign", u"yx", None))

        self.checkBox_autoscale_img.setText(QCoreApplication.translate("MainWindowDesign", u"Autoscale", None))
        self.label_plot_ch.setText(QCoreApplication.translate("MainWindowDesign", u"View Ch.", None))
        self.comboBox_plot_channel.setItemText(0, QCoreApplication.translate("MainWindowDesign", u"0", None))
        self.comboBox_plot_channel.setItemText(1, QCoreApplication.translate("MainWindowDesign", u"1", None))
        self.comboBox_plot_channel.setItemText(2, QCoreApplication.translate("MainWindowDesign", u"2", None))
        self.comboBox_plot_channel.setItemText(3, QCoreApplication.translate("MainWindowDesign", u"3", None))
        self.comboBox_plot_channel.setItemText(4, QCoreApplication.translate("MainWindowDesign", u"4", None))
        self.comboBox_plot_channel.setItemText(5, QCoreApplication.translate("MainWindowDesign", u"5", None))
        self.comboBox_plot_channel.setItemText(6, QCoreApplication.translate("MainWindowDesign", u"6", None))
        self.comboBox_plot_channel.setItemText(7, QCoreApplication.translate("MainWindowDesign", u"7", None))
        self.comboBox_plot_channel.setItemText(8, QCoreApplication.translate("MainWindowDesign", u"8", None))
        self.comboBox_plot_channel.setItemText(9, QCoreApplication.translate("MainWindowDesign", u"9", None))
        self.comboBox_plot_channel.setItemText(10, QCoreApplication.translate("MainWindowDesign", u"10", None))
        self.comboBox_plot_channel.setItemText(11, QCoreApplication.translate("MainWindowDesign", u"11", None))
        self.comboBox_plot_channel.setItemText(12, QCoreApplication.translate("MainWindowDesign", u"12", None))
        self.comboBox_plot_channel.setItemText(13, QCoreApplication.translate("MainWindowDesign", u"13", None))
        self.comboBox_plot_channel.setItemText(14, QCoreApplication.translate("MainWindowDesign", u"14", None))
        self.comboBox_plot_channel.setItemText(15, QCoreApplication.translate("MainWindowDesign", u"15", None))
        self.comboBox_plot_channel.setItemText(16, QCoreApplication.translate("MainWindowDesign", u"16", None))
        self.comboBox_plot_channel.setItemText(17, QCoreApplication.translate("MainWindowDesign", u"17", None))
        self.comboBox_plot_channel.setItemText(18, QCoreApplication.translate("MainWindowDesign", u"18", None))
        self.comboBox_plot_channel.setItemText(19, QCoreApplication.translate("MainWindowDesign", u"19", None))
        self.comboBox_plot_channel.setItemText(20, QCoreApplication.translate("MainWindowDesign", u"20", None))
        self.comboBox_plot_channel.setItemText(21, QCoreApplication.translate("MainWindowDesign", u"21", None))
        self.comboBox_plot_channel.setItemText(22, QCoreApplication.translate("MainWindowDesign", u"22", None))
        self.comboBox_plot_channel.setItemText(23, QCoreApplication.translate("MainWindowDesign", u"23", None))
        self.comboBox_plot_channel.setItemText(24, QCoreApplication.translate("MainWindowDesign", u"24", None))
        self.comboBox_plot_channel.setItemText(25, QCoreApplication.translate("MainWindowDesign", u"Sum", None))
        self.comboBox_plot_channel.setItemText(26, QCoreApplication.translate("MainWindowDesign", u"Analog A", None))
        self.comboBox_plot_channel.setItemText(27, QCoreApplication.translate("MainWindowDesign", u"Analog B", None))

        self.label_60.setText(QCoreApplication.translate("MainWindowDesign", u"View Projection", None))
#if QT_CONFIG(tooltip)
        self.checkBox_lockMove.setToolTip(QCoreApplication.translate("MainWindowDesign", u"<html><head/><body><p>It is locking the autorange of the image.</p></body></html>", None))
#endif // QT_CONFIG(tooltip)
        self.checkBox_lockMove.setText(QCoreApplication.translate("MainWindowDesign", u"Lock Move", None))
        self.label_106.setText(QCoreApplication.translate("MainWindowDesign", u"Double-Click: move to position", None))
        self.label_107.setText(QCoreApplication.translate("MainWindowDesign", u"Ctrl+Double-Click: set a Marker", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab_preview), QCoreApplication.translate("MainWindowDesign", u"Preview", None))
        self.pushButton_13.setText(QCoreApplication.translate("MainWindowDesign", u"Move to selected offset", None))
        self.pushButton_copyPositionsMarkersFCS.setText(QCoreApplication.translate("MainWindowDesign", u"Add Markers in Batch acq. (FCS)", None))
        self.pushButton_copyPositionsMarkers.setText(QCoreApplication.translate("MainWindowDesign", u"Add Markers in Batch acq.", None))
        self.pushButton_currentConfToBatch.setText(QCoreApplication.translate("MainWindowDesign", u"Add current configuration in Batch acq.", None))
        self.pushButton_currentConfToBatchFCS.setText(QCoreApplication.translate("MainWindowDesign", u"Add current configuration in Batch acq. (FCS)", None))
        self.label_103.setText(QCoreApplication.translate("MainWindowDesign", u"FCS Mode: X,Y,Z range forced to 0", None))
        self.label_68.setText("")
        self.label_69.setText(QCoreApplication.translate("MainWindowDesign", u"Number of FCS bins", None))
        self.pushButton_FCS_reset.setText(QCoreApplication.translate("MainWindowDesign", u"Reset FCS Buffer", None))
        self.pushButton_12.setText(QCoreApplication.translate("MainWindowDesign", u"Stop Batch Acquisition", None))
        self.label_batch.setText("")
        self.pushButton_startBatchFCS.setText(QCoreApplication.translate("MainWindowDesign", u"Start Batch Acquisition", None))
        self.checkBox_fcs_preview.setText(QCoreApplication.translate("MainWindowDesign", u"FCS Preview", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab_fcs), QCoreApplication.translate("MainWindowDesign", u" FCS && Batch acq.", None))
        self.checkBox_updateStatus.setText(QCoreApplication.translate("MainWindowDesign", u"Update automatically", None))
        self.tabWidget_circular.setTabText(self.tabWidget_circular.indexOf(self.tab_10), QCoreApplication.translate("MainWindowDesign", u"Tree1", None))
        self.tabWidget_circular.setTabText(self.tabWidget_circular.indexOf(self.tab_11), QCoreApplication.translate("MainWindowDesign", u"Tree2", None))
        self.tabWidget_circular.setTabText(self.tabWidget_circular.indexOf(self.tab_3), QCoreApplication.translate("MainWindowDesign", u"Tree3", None))
        self.tabWidget_circular.setTabText(self.tabWidget_circular.indexOf(self.tab_4), QCoreApplication.translate("MainWindowDesign", u"Circular", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab_statusmonitor), QCoreApplication.translate("MainWindowDesign", u"Status", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab_terminal), QCoreApplication.translate("MainWindowDesign", u"Terminal", None))
        self.dockWidget_preview.setWindowTitle(QCoreApplication.translate("MainWindowDesign", u"Commands", None))
#if QT_CONFIG(tooltip)
        self.pushButton_previewStart.setToolTip(QCoreApplication.translate("MainWindowDesign", u"<html><head/><body><p>Start the scanning without storing data</p></body></html>", None))
#endif // QT_CONFIG(tooltip)
        self.pushButton_previewStart.setText(QCoreApplication.translate("MainWindowDesign", u"Preview", None))
#if QT_CONFIG(tooltip)
        self.pushButton_acquisitionStart.setToolTip(QCoreApplication.translate("MainWindowDesign", u"<html><head/><body><p>Start the scanning saving data</p></body></html>", None))
#endif // QT_CONFIG(tooltip)
        self.pushButton_acquisitionStart.setText(QCoreApplication.translate("MainWindowDesign", u"Acquisition", None))
#if QT_CONFIG(tooltip)
        self.pushButton_14.setToolTip(QCoreApplication.translate("MainWindowDesign", u"<html><head/><body><p>Add the current configuration to the Batch acquisition table</p></body></html>", None))
#endif // QT_CONFIG(tooltip)
        self.pushButton_14.setText(QCoreApplication.translate("MainWindowDesign", u"Add to Batch", None))
#if QT_CONFIG(tooltip)
        self.pushButton_externalProgram.setToolTip(QCoreApplication.translate("MainWindowDesign", u"<html><head/><body><p>Open the last saved file with Napari or another viewer as selected in the configuration</p></body></html>", None))
#endif // QT_CONFIG(tooltip)
        self.pushButton_externalProgram.setText(QCoreApplication.translate("MainWindowDesign", u"Ext. Viewer/Analysis", None))
        self.radioButton_digital.setText(QCoreApplication.translate("MainWindowDesign", u"Digital", None))
        self.radioButton_analog.setText(QCoreApplication.translate("MainWindowDesign", u"Analog", None))
#if QT_CONFIG(tooltip)
        self.checkBox_ttmActivate.setToolTip(QCoreApplication.translate("MainWindowDesign", u"<html><head/><body><p>Activate the TTM data receiver (external software) when start the acquisition</p></body></html>", None))
#endif // QT_CONFIG(tooltip)
        self.checkBox_ttmActivate.setText(QCoreApplication.translate("MainWindowDesign", u"TTM", None))
#if QT_CONFIG(tooltip)
        self.checkBox_DFD.setToolTip(QCoreApplication.translate("MainWindowDesign", u"<html><head/><body><p>Activate the Digital Frequency Domain data acquisition</p></body></html>", None))
#endif // QT_CONFIG(tooltip)
        self.checkBox_DFD.setText(QCoreApplication.translate("MainWindowDesign", u"DFD", None))
#if QT_CONFIG(tooltip)
        self.pushButton_stop.setToolTip(QCoreApplication.translate("MainWindowDesign", u"<html><head/><body><p>Stop the scan</p></body></html>", None))
#endif // QT_CONFIG(tooltip)
        self.pushButton_stop.setText(QCoreApplication.translate("MainWindowDesign", u"STOP!", None))
        self.dockWidget_temporal.setWindowTitle(QCoreApplication.translate("MainWindowDesign", u"Temporal settings", None))
#if QT_CONFIG(tooltip)
        self.spinBox_waitAfterFrame.setToolTip(QCoreApplication.translate("MainWindowDesign", u"<html><head/><body><p>Delay betweent two repetition in second.</p></body></html>", None))
#endif // QT_CONFIG(tooltip)
        self.label_time_bin_per_px.setText(QCoreApplication.translate("MainWindowDesign", u"Time bins per pixel", None))
#if QT_CONFIG(tooltip)
        self.checkBox_waitOnlyFirstTime.setToolTip(QCoreApplication.translate("MainWindowDesign", u"<html><head/><body><p>The delay laser is applied only the first acquisition and not each repetition.</p></body></html>", None))
#endif // QT_CONFIG(tooltip)
        self.checkBox_waitOnlyFirstTime.setText(QCoreApplication.translate("MainWindowDesign", u"Only First Time", None))
        self.label_frame_time.setText(QCoreApplication.translate("MainWindowDesign", u"Delay Laser [s]", None))
#if QT_CONFIG(tooltip)
        self.spinBox_timeresolution.setToolTip(QCoreApplication.translate("MainWindowDesign", u"<html><head/><body><p>The time resolution is the time duration of a single &quot;time bin&quot;.</p><p>Pixel_dwell_time = time_resolution * time_bins_per_pixel</p></body></html>", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(tooltip)
        self.spinBox_waitForLaser.setToolTip(QCoreApplication.translate("MainWindowDesign", u"<html><head/><body><p>The laser is turned on and before the scanning a &quot;delay laser&quot; is waited. </p></body></html>", None))
#endif // QT_CONFIG(tooltip)
        self.label_29.setText(QCoreApplication.translate("MainWindowDesign", u"Turn OFF Laser bw. rep.", None))
        self.label_frame_time_2.setText(QCoreApplication.translate("MainWindowDesign", u"Delay between rep. [s]", None))
        self.label_timeresolution.setText(QCoreApplication.translate("MainWindowDesign", u"Time Resolution [us]", None))
#if QT_CONFIG(tooltip)
        self.checkBox_laserOffAfterMeas.setToolTip(QCoreApplication.translate("MainWindowDesign", u"<html><head/><body><p>If activated between two repetition the laser is switched off.</p></body></html>", None))
#endif // QT_CONFIG(tooltip)
        self.checkBox_laserOffAfterMeas.setText("")
#if QT_CONFIG(tooltip)
        self.spinBox_time_bin_per_px.setToolTip(QCoreApplication.translate("MainWindowDesign", u"<html><head/><body><p>The number of bin in which the pixel is subdivided.</p><p>Pixel_dwell_time = time_resolution * time_bins_per_pixel</p></body></html>", None))
#endif // QT_CONFIG(tooltip)
        self.label_dwell_time_2.setText(QCoreApplication.translate("MainWindowDesign", u"Pixel dwell time [\u00b5s]", None))
#if QT_CONFIG(tooltip)
        self.label_dwell_time_val.setToolTip(QCoreApplication.translate("MainWindowDesign", u"<html><head/><body><p>Pixel_dwell_time = time_resolution * time_bins_per_pixel</p></body></html>", None))
#endif // QT_CONFIG(tooltip)
        self.label_dwell_time_val.setText("")
        self.dockWidget_2.setWindowTitle(QCoreApplication.translate("MainWindowDesign", u"Spatial settings", None))
#if QT_CONFIG(tooltip)
        self.spinBox_nrepetition.setToolTip(QCoreApplication.translate("MainWindowDesign", u"<html><head/><body><p>Number of repetition</p></body></html>", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(tooltip)
        self.spinBox_ny.setToolTip(QCoreApplication.translate("MainWindowDesign", u"<html><head/><body><p>Number of pixel along Y</p></body></html>", None))
#endif // QT_CONFIG(tooltip)
        self.label_104.setText(QCoreApplication.translate("MainWindowDesign", u"Y pixel size", None))
        self.label_nframe.setText(QCoreApplication.translate("MainWindowDesign", u"N. of pixel Z", None))
#if QT_CONFIG(tooltip)
        self.spinBox_nframe.setToolTip(QCoreApplication.translate("MainWindowDesign", u"<html><head/><body><p>Number of pixel along Z</p></body></html>", None))
#endif // QT_CONFIG(tooltip)
        self.label_ny.setText(QCoreApplication.translate("MainWindowDesign", u"N. of pixel Y", None))
        self.label_nx.setText(QCoreApplication.translate("MainWindowDesign", u"N. of pixel X", None))
        self.label_105.setText(QCoreApplication.translate("MainWindowDesign", u"X pixel size", None))
        self.label_pixelsize_z.setText(QCoreApplication.translate("MainWindowDesign", u"0.0 \u00b5m", None))
        self.label_pixelsize_x.setText(QCoreApplication.translate("MainWindowDesign", u"0.0 \u00b5m", None))
        self.label_nrepetition.setText(QCoreApplication.translate("MainWindowDesign", u"N. of repetition", None))
        self.label_101.setText(QCoreApplication.translate("MainWindowDesign", u"Z pixel size", None))
#if QT_CONFIG(tooltip)
        self.spinBox_nx.setToolTip(QCoreApplication.translate("MainWindowDesign", u"<html><head/><body><p>Number of pixel along X</p></body></html>", None))
#endif // QT_CONFIG(tooltip)
        self.label_pixelsize_y.setText(QCoreApplication.translate("MainWindowDesign", u"0.0 \u00b5m", None))
#if QT_CONFIG(tooltip)
        self.pushButton_18.setToolTip(QCoreApplication.translate("MainWindowDesign", u"<html><head/><body><p>Use this button each time you modified the number of pixel (X,Y,Z)</p></body></html>", None))
#endif // QT_CONFIG(tooltip)
        self.pushButton_18.setText(QCoreApplication.translate("MainWindowDesign", u"Update View", None))
        self.dockWidget_fingerprint.setWindowTitle(QCoreApplication.translate("MainWindowDesign", u"Micro image", None))
        self.label_microimage.setText(QCoreApplication.translate("MainWindowDesign", u"Type:", None))
        self.comboBox_fingerprint.setItemText(0, QCoreApplication.translate("MainWindowDesign", u"Cumulative", None))
        self.comboBox_fingerprint.setItemText(1, QCoreApplication.translate("MainWindowDesign", u"Last 10000 bins", None))
        self.comboBox_fingerprint.setItemText(2, QCoreApplication.translate("MainWindowDesign", u"Last Full Frame", None))

        self.pushButton_4.setText(QCoreApplication.translate("MainWindowDesign", u"Sum", None))
        self.checkBox_autoscale_fingerprint.setText(QCoreApplication.translate("MainWindowDesign", u"Img. Autoscale", None))
        self.dockWidget_trace.setWindowTitle(QCoreApplication.translate("MainWindowDesign", u"Trace", None))
        self.dockWidget_statistics.setWindowTitle(QCoreApplication.translate("MainWindowDesign", u"Statistics", None))
        self.progressBar_repetition.setFormat(QCoreApplication.translate("MainWindowDesign", u"%v%", None))
        self.label_70.setText(QCoreApplication.translate("MainWindowDesign", u"Frame status", None))
        self.label_current_repetition_val.setText(QCoreApplication.translate("MainWindowDesign", u"0", None))
        self.label_expected_dur.setText(QCoreApplication.translate("MainWindowDesign", u"Frame Duration  [s]", None))
        self.label_71.setText(QCoreApplication.translate("MainWindowDesign", u"Repetition status", None))
        self.label_expected_dur_val.setText(QCoreApplication.translate("MainWindowDesign", u"0", None))
        self.progressBar_saving.setFormat(QCoreApplication.translate("MainWindowDesign", u"%v", None))
        self.progressBar_fifo_digital.setFormat(QCoreApplication.translate("MainWindowDesign", u"%v", None))
        self.label_current_frame_val.setText(QCoreApplication.translate("MainWindowDesign", u"0", None))
        self.progressBar_frame.setFormat(QCoreApplication.translate("MainWindowDesign", u"%v%", None))
        self.label_preview_delay.setText(QCoreApplication.translate("MainWindowDesign", u"0", None))
        self.label_72.setText(QCoreApplication.translate("MainWindowDesign", u"Digital FIFO Queues", None))
        self.label_current_time_3.setText(QCoreApplication.translate("MainWindowDesign", u"Expected Total Time [s]", None))
        self.progressBar_fifo_analog.setFormat(QCoreApplication.translate("MainWindowDesign", u"%v", None))
        self.label_85.setText(QCoreApplication.translate("MainWindowDesign", u"Analog FIFO Queues", None))
        self.label_87.setText(QCoreApplication.translate("MainWindowDesign", u"Saving Queues", None))
        self.label_preview_delay_label.setText(QCoreApplication.translate("MainWindowDesign", u"Visualization delay [s]", None))
        self.label_tot_num_dat_point.setText(QCoreApplication.translate("MainWindowDesign", u"Raw data", None))
        self.label_current_time.setText(QCoreApplication.translate("MainWindowDesign", u"Time [s]", None))
        self.label_current_time_val.setText(QCoreApplication.translate("MainWindowDesign", u"0", None))
        self.label_frame_time_val.setText(QCoreApplication.translate("MainWindowDesign", u"0", None))
        self.label_tot_num_dat_point_val.setText(QCoreApplication.translate("MainWindowDesign", u"0", None))
        self.dockWidget_pos.setWindowTitle(QCoreApplication.translate("MainWindowDesign", u"Position", None))
        self.label.setText(QCoreApplication.translate("MainWindowDesign", u"X", None))
        self.label_3.setText(QCoreApplication.translate("MainWindowDesign", u"Y", None))
        self.label_13.setText(QCoreApplication.translate("MainWindowDesign", u"[\u00b5m]", None))
        self.label_27.setText(QCoreApplication.translate("MainWindowDesign", u"[\u00b5m]", None))
#if QT_CONFIG(tooltip)
        self.spinBox_range_z.setToolTip(QCoreApplication.translate("MainWindowDesign", u"Z range in \u00b5m (full range)", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(tooltip)
        self.spinBox_range_x.setToolTip(QCoreApplication.translate("MainWindowDesign", u"X range in \u00b5m (full range)", None))
#endif // QT_CONFIG(tooltip)
        self.label_26.setText(QCoreApplication.translate("MainWindowDesign", u"[\u00b5m]", None))
#if QT_CONFIG(tooltip)
        self.spinBox_off_y_um.setToolTip(QCoreApplication.translate("MainWindowDesign", u"Y position \u00b5m", None))
#endif // QT_CONFIG(tooltip)
        self.label_23.setText(QCoreApplication.translate("MainWindowDesign", u"Z", None))
#if QT_CONFIG(tooltip)
        self.spinBox_off_z_um.setToolTip(QCoreApplication.translate("MainWindowDesign", u"Z position \u00b5m", None))
#endif // QT_CONFIG(tooltip)
        self.label_14.setText(QCoreApplication.translate("MainWindowDesign", u"[\u00b5m]", None))
        self.label_24.setText(QCoreApplication.translate("MainWindowDesign", u"Position", None))
        self.label_15.setText(QCoreApplication.translate("MainWindowDesign", u"[\u00b5m]", None))
#if QT_CONFIG(tooltip)
        self.spinBox_off_x_um.setToolTip(QCoreApplication.translate("MainWindowDesign", u"X position \u00b5m", None))
#endif // QT_CONFIG(tooltip)
        self.label_21.setText(QCoreApplication.translate("MainWindowDesign", u"X", None))
        self.label_28.setText(QCoreApplication.translate("MainWindowDesign", u"[\u00b5m]", None))
        self.label_4.setText(QCoreApplication.translate("MainWindowDesign", u"Z", None))
#if QT_CONFIG(tooltip)
        self.spinBox_range_y.setToolTip(QCoreApplication.translate("MainWindowDesign", u"Y range in \u00b5m (full range)", None))
#endif // QT_CONFIG(tooltip)
        self.label_25.setText(QCoreApplication.translate("MainWindowDesign", u"Full Range", None))
        self.label_22.setText(QCoreApplication.translate("MainWindowDesign", u"Y", None))
#if QT_CONFIG(tooltip)
        self.checkBoxLockRatio.setToolTip(QCoreApplication.translate("MainWindowDesign", u"<html><head/><body><p>Force the 1:1 aspect-ratio </p></body></html>", None))
#endif // QT_CONFIG(tooltip)
        self.checkBoxLockRatio.setText(QCoreApplication.translate("MainWindowDesign", u"Lock", None))
        self.groupBox.setTitle(QCoreApplication.translate("MainWindowDesign", u"Presets", None))
        self.pushButton_loadPreset.setText(QCoreApplication.translate("MainWindowDesign", u"Load", None))
        self.pushButton_savePreset.setText(QCoreApplication.translate("MainWindowDesign", u"Save", None))
        self.comboBox_preset.setItemText(0, QCoreApplication.translate("MainWindowDesign", u"0", None))
        self.comboBox_preset.setItemText(1, QCoreApplication.translate("MainWindowDesign", u"1", None))
        self.comboBox_preset.setItemText(2, QCoreApplication.translate("MainWindowDesign", u"2", None))
        self.comboBox_preset.setItemText(3, QCoreApplication.translate("MainWindowDesign", u"3", None))
        self.comboBox_preset.setItemText(4, QCoreApplication.translate("MainWindowDesign", u"4", None))
        self.comboBox_preset.setItemText(5, QCoreApplication.translate("MainWindowDesign", u"5", None))
        self.comboBox_preset.setItemText(6, QCoreApplication.translate("MainWindowDesign", u"6", None))
        self.comboBox_preset.setItemText(7, QCoreApplication.translate("MainWindowDesign", u"7", None))
        self.comboBox_preset.setItemText(8, QCoreApplication.translate("MainWindowDesign", u"8", None))
        self.comboBox_preset.setItemText(9, QCoreApplication.translate("MainWindowDesign", u"9", None))

        ___qtablewidgetitem = self.tableWidget_markers.horizontalHeaderItem(0)
        ___qtablewidgetitem.setText(QCoreApplication.translate("MainWindowDesign", u"X", None));
        ___qtablewidgetitem1 = self.tableWidget_markers.horizontalHeaderItem(1)
        ___qtablewidgetitem1.setText(QCoreApplication.translate("MainWindowDesign", u"Y", None));
        ___qtablewidgetitem2 = self.tableWidget_markers.horizontalHeaderItem(2)
        ___qtablewidgetitem2.setText(QCoreApplication.translate("MainWindowDesign", u"Z", None));
        ___qtablewidgetitem3 = self.tableWidget_markers.horizontalHeaderItem(3)
        ___qtablewidgetitem3.setText(QCoreApplication.translate("MainWindowDesign", u"Comments", None));
#if QT_CONFIG(tooltip)
        self.tableWidget_markers.setToolTip(QCoreApplication.translate("MainWindowDesign", u"<html><head/><body><p>Table of position selected on the image. To add a point double-click on the image.</p></body></html>", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(tooltip)
        self.pushButton_15.setToolTip(QCoreApplication.translate("MainWindowDesign", u"<html><head/><body><p>Move the offset to the position on the row selected on the table below </p></body></html>", None))
#endif // QT_CONFIG(tooltip)
        self.pushButton_15.setText(QCoreApplication.translate("MainWindowDesign", u"Move to selected row", None))
        self.pushButton_Panorama.setText(QCoreApplication.translate("MainWindowDesign", u"Move to Default FOV", None))
        self.dockWidget_activatefifo.setWindowTitle(QCoreApplication.translate("MainWindowDesign", u"Adv.", None))
#if QT_CONFIG(tooltip)
        self.checkBox_snake.setToolTip(QCoreApplication.translate("MainWindowDesign", u"<html><head/><body><p>Use for the scanning a &quot;snake-walk&quot; instead of a normal &quot;raster-scan&quot;</p></body></html>", None))
#endif // QT_CONFIG(tooltip)
        self.checkBox_snake.setText(QCoreApplication.translate("MainWindowDesign", u"Snake walk", None))
#if QT_CONFIG(tooltip)
        self.checkBox_showPreview.setToolTip(QCoreApplication.translate("MainWindowDesign", u"<html><head/><body><p>The live-preview can be disabled.</p></body></html>", None))
#endif // QT_CONFIG(tooltip)
        self.checkBox_showPreview.setText(QCoreApplication.translate("MainWindowDesign", u"Show Image Preview", None))
        self.groupBox_8.setTitle(QCoreApplication.translate("MainWindowDesign", u"Slave Mode", None))
        self.checkBox_slavemode_enable.setText(QCoreApplication.translate("MainWindowDesign", u"Activate", None))
        self.label_112.setText(QCoreApplication.translate("MainWindowDesign", u"Wait a trigger for:", None))
        self.comboBox_slavemode_type.setItemText(0, QCoreApplication.translate("MainWindowDesign", u"Circ. Pos.", None))
        self.comboBox_slavemode_type.setItemText(1, QCoreApplication.translate("MainWindowDesign", u"Circ. Rep.", None))
        self.comboBox_slavemode_type.setItemText(2, QCoreApplication.translate("MainWindowDesign", u"Pixel", None))
        self.comboBox_slavemode_type.setItemText(3, QCoreApplication.translate("MainWindowDesign", u"Line", None))
        self.comboBox_slavemode_type.setItemText(4, QCoreApplication.translate("MainWindowDesign", u"Frame", None))
        self.comboBox_slavemode_type.setItemText(5, QCoreApplication.translate("MainWindowDesign", u"Repetition", None))

        self.groupBox_2.setTitle(QCoreApplication.translate("MainWindowDesign", u"Circular Motion", None))
#if QT_CONFIG(tooltip)
        self.spinBox_circular_radius_nm.setToolTip(QCoreApplication.translate("MainWindowDesign", u"X position \u00b5m", None))
#endif // QT_CONFIG(tooltip)
        self.label_109.setText(QCoreApplication.translate("MainWindowDesign", u"[nm]", None))
        self.label_108.setText(QCoreApplication.translate("MainWindowDesign", u"Radius", None))
        self.label_43.setText(QCoreApplication.translate("MainWindowDesign", u"Number of points", None))
        self.label_110.setText(QCoreApplication.translate("MainWindowDesign", u"Repetition", None))
#if QT_CONFIG(tooltip)
        self.checkBox_circular.setToolTip(QCoreApplication.translate("MainWindowDesign", u"<html><head/><body><p>This use instead of the scanning position the circular motion. This must be activated AFTER the circular motion is defined.</p></body></html>", None))
#endif // QT_CONFIG(tooltip)
        self.checkBox_circular.setText(QCoreApplication.translate("MainWindowDesign", u"Activate", None))
        self.dockWidget_laser.setWindowTitle(QCoreApplication.translate("MainWindowDesign", u"Laser configuration", None))
        self.groupBox_3.setTitle(QCoreApplication.translate("MainWindowDesign", u"Activate", None))
        self.checkBox_laser0.setText(QCoreApplication.translate("MainWindowDesign", u"L1", None))
        self.checkBox_laser3.setText(QCoreApplication.translate("MainWindowDesign", u"L4", None))
        self.checkBox_laser1.setText(QCoreApplication.translate("MainWindowDesign", u"L2", None))
        self.checkBox_laser2.setText(QCoreApplication.translate("MainWindowDesign", u"L3", None))
        self.groupBox_7.setTitle(QCoreApplication.translate("MainWindowDesign", u"DFD", None))
        self.comboBox_channels.setItemText(0, QCoreApplication.translate("MainWindowDesign", u"25", None))
        self.comboBox_channels.setItemText(1, QCoreApplication.translate("MainWindowDesign", u"49", None))

        self.label_35.setText(QCoreApplication.translate("MainWindowDesign", u"SPAD Channels", None))
        self.label_111.setText(QCoreApplication.translate("MainWindowDesign", u"DFD N. Bins", None))
#if QT_CONFIG(tooltip)
        self.checkBox_DFD_LaserDebug.setToolTip(QCoreApplication.translate("MainWindowDesign", u"<html><head/><body><p>The laser clock is internally to the FPGA send also to channel 26. This must be activated to perform a proper time reallignment of the DFD histogram.</p></body></html>", None))
#endif // QT_CONFIG(tooltip)
        self.checkBox_DFD_LaserDebug.setText(QCoreApplication.translate("MainWindowDesign", u"Laser Ref. in CH26 (for DFD)", None))
        self.groupBox_6.setTitle(QCoreApplication.translate("MainWindowDesign", u"Sequence", None))
        self.comboLaserSeq_3.setItemText(0, QCoreApplication.translate("MainWindowDesign", u"0", None))
        self.comboLaserSeq_3.setItemText(1, QCoreApplication.translate("MainWindowDesign", u"1", None))
        self.comboLaserSeq_3.setItemText(2, QCoreApplication.translate("MainWindowDesign", u"2", None))
        self.comboLaserSeq_3.setItemText(3, QCoreApplication.translate("MainWindowDesign", u"3", None))
        self.comboLaserSeq_3.setItemText(4, QCoreApplication.translate("MainWindowDesign", u"4", None))

        self.comboLaserSeq_5.setItemText(0, QCoreApplication.translate("MainWindowDesign", u"0", None))
        self.comboLaserSeq_5.setItemText(1, QCoreApplication.translate("MainWindowDesign", u"1", None))
        self.comboLaserSeq_5.setItemText(2, QCoreApplication.translate("MainWindowDesign", u"2", None))
        self.comboLaserSeq_5.setItemText(3, QCoreApplication.translate("MainWindowDesign", u"3", None))
        self.comboLaserSeq_5.setItemText(4, QCoreApplication.translate("MainWindowDesign", u"4", None))

        self.comboLaserSeq_1.setItemText(0, QCoreApplication.translate("MainWindowDesign", u"0", None))
        self.comboLaserSeq_1.setItemText(1, QCoreApplication.translate("MainWindowDesign", u"1", None))
        self.comboLaserSeq_1.setItemText(2, QCoreApplication.translate("MainWindowDesign", u"2", None))
        self.comboLaserSeq_1.setItemText(3, QCoreApplication.translate("MainWindowDesign", u"3", None))
        self.comboLaserSeq_1.setItemText(4, QCoreApplication.translate("MainWindowDesign", u"4", None))

        self.comboLaserSeq_4.setItemText(0, QCoreApplication.translate("MainWindowDesign", u"0", None))
        self.comboLaserSeq_4.setItemText(1, QCoreApplication.translate("MainWindowDesign", u"1", None))
        self.comboLaserSeq_4.setItemText(2, QCoreApplication.translate("MainWindowDesign", u"2", None))
        self.comboLaserSeq_4.setItemText(3, QCoreApplication.translate("MainWindowDesign", u"3", None))
        self.comboLaserSeq_4.setItemText(4, QCoreApplication.translate("MainWindowDesign", u"4", None))

        self.comboLaserSeq_2.setItemText(0, QCoreApplication.translate("MainWindowDesign", u"0", None))
        self.comboLaserSeq_2.setItemText(1, QCoreApplication.translate("MainWindowDesign", u"1", None))
        self.comboLaserSeq_2.setItemText(2, QCoreApplication.translate("MainWindowDesign", u"2", None))
        self.comboLaserSeq_2.setItemText(3, QCoreApplication.translate("MainWindowDesign", u"3", None))
        self.comboLaserSeq_2.setItemText(4, QCoreApplication.translate("MainWindowDesign", u"4", None))

        self.comboLaserSeq_6.setItemText(0, QCoreApplication.translate("MainWindowDesign", u"0", None))
        self.comboLaserSeq_6.setItemText(1, QCoreApplication.translate("MainWindowDesign", u"1", None))
        self.comboLaserSeq_6.setItemText(2, QCoreApplication.translate("MainWindowDesign", u"2", None))
        self.comboLaserSeq_6.setItemText(3, QCoreApplication.translate("MainWindowDesign", u"3", None))
        self.comboLaserSeq_6.setItemText(4, QCoreApplication.translate("MainWindowDesign", u"4", None))

        self.dockWidget_adv.setWindowTitle(QCoreApplication.translate("MainWindowDesign", u"Adv.", None))
        self.lineEdit_fpga2bitfile.setText("")
        self.label_98.setText("")
        self.lineEdit_ni_addr.setText(QCoreApplication.translate("MainWindowDesign", u"RIO0", None))
        self.pushButton_FPGA_file_selection.setText(QCoreApplication.translate("MainWindowDesign", u"...", None))
        self.label_66.setText(QCoreApplication.translate("MainWindowDesign", u"FPGA Addr.", None))
        self.label_88.setText(QCoreApplication.translate("MainWindowDesign", u"Loaded .cfg", None))
        self.label_67.setText(QCoreApplication.translate("MainWindowDesign", u"Default .cfg File", None))
        self.label_75.setText(QCoreApplication.translate("MainWindowDesign", u"Load .cfg file", None))
        self.lineEdit_fpgabitfile.setText(QCoreApplication.translate("MainWindowDesign", u"bitfiles/MyBitfileUSB.lvbitx", None))
        self.lineEdit_ni2addr.setText("")
        self.pushButton_saveCfg.setText(QCoreApplication.translate("MainWindowDesign", u"...", None))
        self.pushButton_loadCfg.setText(QCoreApplication.translate("MainWindowDesign", u"...", None))
        self.label_92.setText(QCoreApplication.translate("MainWindowDesign", u"FPGA 2nd Addr.", None))
        self.pushButton_FPGA2_file_selection.setText(QCoreApplication.translate("MainWindowDesign", u"...", None))
        self.lineEdit_configurationfile.setText(QCoreApplication.translate("MainWindowDesign", u"default.cfg", None))
        self.label_91.setText(QCoreApplication.translate("MainWindowDesign", u"FPGA 2nd Bitfile", None))
        self.label_81.setText(QCoreApplication.translate("MainWindowDesign", u"Save .cfg file", None))
        self.label_loadedcfg.setText(QCoreApplication.translate("MainWindowDesign", u".", None))
        self.label_65.setText(QCoreApplication.translate("MainWindowDesign", u"FPGA Bitfile", None))
        self.tabWidget_2.setTabText(self.tabWidget_2.indexOf(self.tab_2), QCoreApplication.translate("MainWindowDesign", u"Board Configuration", None))
        self.lineEdit_spad_data.setText(QCoreApplication.translate("MainWindowDesign", u"33554431", None))
        self.label_94.setText(QCoreApplication.translate("MainWindowDesign", u"Data cmd", None))
        self.label_93.setText(QCoreApplication.translate("MainWindowDesign", u"Data length", None))
        self.checkBox_spad_invert.setText(QCoreApplication.translate("MainWindowDesign", u"Invert", None))
        self.lineEdit_spad_length.setText(QCoreApplication.translate("MainWindowDesign", u"25", None))
        self.tabWidget_2.setTabText(self.tabWidget_2.indexOf(self.tab), QCoreApplication.translate("MainWindowDesign", u"SPAD", None))
        self.label_56.setText(QCoreApplication.translate("MainWindowDesign", u"[\u00b5m]", None))
        self.label_49.setText(QCoreApplication.translate("MainWindowDesign", u"[\u00b5m]", None))
        self.label_47.setText(QCoreApplication.translate("MainWindowDesign", u"Y", None))
        self.label_50.setText(QCoreApplication.translate("MainWindowDesign", u"[\u00b5m]", None))
        self.label_55.setText(QCoreApplication.translate("MainWindowDesign", u"Z", None))
        self.label_52.setText(QCoreApplication.translate("MainWindowDesign", u"[\u00b5m]", None))
        self.label_54.setText(QCoreApplication.translate("MainWindowDesign", u"[\u00b5m]", None))
        self.label_46.setText(QCoreApplication.translate("MainWindowDesign", u"X", None))
        self.label_48.setText(QCoreApplication.translate("MainWindowDesign", u"Z", None))
        self.label_53.setText(QCoreApplication.translate("MainWindowDesign", u"Y", None))
        self.label_57.setText(QCoreApplication.translate("MainWindowDesign", u"X", None))
        self.label_51.setText(QCoreApplication.translate("MainWindowDesign", u"[\u00b5m]", None))
        self.label_58.setText(QCoreApplication.translate("MainWindowDesign", u"Pos.", None))
        self.label_59.setText(QCoreApplication.translate("MainWindowDesign", u"Range", None))
        self.tabWidget_2.setTabText(self.tabWidget_2.indexOf(self.tab_6), QCoreApplication.translate("MainWindowDesign", u"Default FOV", None))
        self.label_17.setText(QCoreApplication.translate("MainWindowDesign", u"Offset [V]", None))
        self.label_30.setText(QCoreApplication.translate("MainWindowDesign", u"[V]", None))
        self.label_31.setText(QCoreApplication.translate("MainWindowDesign", u"Y", None))
        self.label_32.setText(QCoreApplication.translate("MainWindowDesign", u"[V]", None))
        self.label_33.setText(QCoreApplication.translate("MainWindowDesign", u"Z", None))
        self.label_34.setText(QCoreApplication.translate("MainWindowDesign", u"[V]", None))
        self.label_45.setText(QCoreApplication.translate("MainWindowDesign", u"X", None))
        self.label_38.setText(QCoreApplication.translate("MainWindowDesign", u"X", None))
        self.label_39.setText(QCoreApplication.translate("MainWindowDesign", u"Y", None))
        self.label_41.setText(QCoreApplication.translate("MainWindowDesign", u"Min.", None))
        self.label_42.setText(QCoreApplication.translate("MainWindowDesign", u"Max.", None))
        self.label_40.setText(QCoreApplication.translate("MainWindowDesign", u"Z", None))
        self.label_37.setText(QCoreApplication.translate("MainWindowDesign", u"Set Voltages Range [V]", None))
        self.tabWidget_2.setTabText(self.tabWidget_2.indexOf(self.tab_7), QCoreApplication.translate("MainWindowDesign", u"Limits", None))
        self.label_86.setText(QCoreApplication.translate("MainWindowDesign", u"External Call", None))
        self.lineEdit_externalProgram.setText(QCoreApplication.translate("MainWindowDesign", u"%python -m napari %lastfilename", None))
        self.tabWidget_2.setTabText(self.tabWidget_2.indexOf(self.tab_13), QCoreApplication.translate("MainWindowDesign", u"Ext.", None))
        self.checkBox_httpServer.setText(QCoreApplication.translate("MainWindowDesign", u"http API Server", None))
        self.label_100.setText(QCoreApplication.translate("MainWindowDesign", u"Activate", None))
        self.lineEdit_httpPort.setText(QCoreApplication.translate("MainWindowDesign", u"8000", None))
        self.lineEdit_httpAddr.setText(QCoreApplication.translate("MainWindowDesign", u"127.0.0.1", None))
        self.label_99.setText(QCoreApplication.translate("MainWindowDesign", u"Port", None))
        self.label_44.setText(QCoreApplication.translate("MainWindowDesign", u"Address", None))
        self.label_102.setText(QCoreApplication.translate("MainWindowDesign", u"Link", None))
        self.label_httpLink.setText(QCoreApplication.translate("MainWindowDesign", u".", None))
        self.tabWidget_2.setTabText(self.tabWidget_2.indexOf(self.tab_12), QCoreApplication.translate("MainWindowDesign", u"http Server", None))
        self.label_10.setText(QCoreApplication.translate("MainWindowDesign", u"[V]", None))
        self.label_8.setText(QCoreApplication.translate("MainWindowDesign", u"Y", None))
        self.label_11.setText(QCoreApplication.translate("MainWindowDesign", u"[V]", None))
        self.label_9.setText(QCoreApplication.translate("MainWindowDesign", u"Z", None))
        self.label_12.setText(QCoreApplication.translate("MainWindowDesign", u"[V]", None))
        self.label_7.setText(QCoreApplication.translate("MainWindowDesign", u"X", None))
        self.label_16.setText(QCoreApplication.translate("MainWindowDesign", u"CalibrationFactors ", None))
        self.label_36.setText(QCoreApplication.translate("MainWindowDesign", u"Current Position in [V]", None))
        self.label_19.setText(QCoreApplication.translate("MainWindowDesign", u"[\u00b5m/V]", None))
        self.label_18.setText(QCoreApplication.translate("MainWindowDesign", u"[\u00b5m/V]", None))
        self.label_6.setText(QCoreApplication.translate("MainWindowDesign", u"Z", None))
        self.label_2.setText(QCoreApplication.translate("MainWindowDesign", u"X", None))
        self.label_20.setText(QCoreApplication.translate("MainWindowDesign", u"[\u00b5m/V]", None))
        self.label_5.setText(QCoreApplication.translate("MainWindowDesign", u"Y", None))
        self.tabWidget_2.setTabText(self.tabWidget_2.indexOf(self.tab_8), QCoreApplication.translate("MainWindowDesign", u"Calibration", None))
        self.label_ttm_IP.setText(QCoreApplication.translate("MainWindowDesign", u"127.0.0.1", None))
        self.label_ttm_IP_5.setText(QCoreApplication.translate("MainWindowDesign", u"TTM-File Folder", None))
        self.toolButton_ttm_filename.setText(QCoreApplication.translate("MainWindowDesign", u"...", None))
        self.toolButton_ttm_executable_path.setText(QCoreApplication.translate("MainWindowDesign", u"...", None))
        self.lineEdit_ttm_executable_path.setText(QCoreApplication.translate("MainWindowDesign", u"C:/Users/Developer/BrightEyes-TTM/DataReceiverGUI/Debug/BrightEyesTTMrecv.exe", None))
        self.label_ttm_IP_4.setText(QCoreApplication.translate("MainWindowDesign", u"IP Port (server):", None))
        self.label_ttm_IP_3.setText(QCoreApplication.translate("MainWindowDesign", u"TTM reader:", None))
        self.lineEdit_ttmPort.setText(QCoreApplication.translate("MainWindowDesign", u"56000", None))
        self.lineEdit_ttm_filename.setText("")
        self.radioButton_ttm_local.setText(QCoreApplication.translate("MainWindowDesign", u"Local", None))
        self.radioButton_ttm_remote.setText(QCoreApplication.translate("MainWindowDesign", u"Remote", None))
        self.tabWidget_2.setTabText(self.tabWidget_2.indexOf(self.tab_9), QCoreApplication.translate("MainWindowDesign", u"TTM", None))
        self.label_90.setText(QCoreApplication.translate("MainWindowDesign", u"FIFO Last PreProcessed size", None))
        self.label_63.setText(QCoreApplication.translate("MainWindowDesign", u"Preview Buffer size (divided timebin)", None))
        self.comboBox_fifobackend.setItemText(0, QCoreApplication.translate("MainWindowDesign", u"Rust nifpga_fast_fifo_recv", None))
        self.comboBox_fifobackend.setItemText(1, QCoreApplication.translate("MainWindowDesign", u"Python nifpga library", None))

        self.label_fifo_prebuffer_len.setText(QCoreApplication.translate("MainWindowDesign", u"0", None))
        self.label_64.setText(QCoreApplication.translate("MainWindowDesign", u"FIFO Actual Buffer size", None))
        self.label_actual_buffer_size.setText(QCoreApplication.translate("MainWindowDesign", u"0", None))
        self.label_62.setText(QCoreApplication.translate("MainWindowDesign", u"FIFO Buffer size", None))
        self.label_78.setText(QCoreApplication.translate("MainWindowDesign", u"FIFO Last Packet Received size", None))
        self.label_actual_preview_buffer_size.setText(QCoreApplication.translate("MainWindowDesign", u"0", None))
        self.label_fifo_last_pkt_size.setText(QCoreApplication.translate("MainWindowDesign", u"0", None))
        self.label_79.setText(QCoreApplication.translate("MainWindowDesign", u"Preview Buffer size total", None))
        self.label_89.setText(QCoreApplication.translate("MainWindowDesign", u"FIFO Last PreProcessed actual size", None))
        self.label_96.setText(QCoreApplication.translate("MainWindowDesign", u"Timeout FIFO (us)", None))
        self.label_95.setText(QCoreApplication.translate("MainWindowDesign", u"FIFO reader backend", None))
        self.label_97.setText(QCoreApplication.translate("MainWindowDesign", u"DummyData", None))
        self.checkBox_DummyData.setText("")
        self.tabWidget_2.setTabText(self.tabWidget_2.indexOf(self.tab_5), QCoreApplication.translate("MainWindowDesign", u"FIFOs", None))
        self.dockWidget_debug.setWindowTitle(QCoreApplication.translate("MainWindowDesign", u"Menu && Debug", None))
        self.checkBox_correlationMatrix.setText(QCoreApplication.translate("MainWindowDesign", u"Activate Corr. Matrix", None))
        self.label_dummy.setText(QCoreApplication.translate("MainWindowDesign", u"0t", None))
        self.pushButton_8.setText(QCoreApplication.translate("MainWindowDesign", u"Test6", None))
        self.pushButton.setText(QCoreApplication.translate("MainWindowDesign", u"Test1", None))
        self.pushButton_6.setText(QCoreApplication.translate("MainWindowDesign", u"Test4", None))
        self.pushButton_2.setText(QCoreApplication.translate("MainWindowDesign", u"Test2", None))
        self.pushButton_11.setText(QCoreApplication.translate("MainWindowDesign", u"Test9", None))
        self.pushButton_3.setText(QCoreApplication.translate("MainWindowDesign", u"Test3", None))
        self.pushButton_10.setText(QCoreApplication.translate("MainWindowDesign", u"Test8", None))
        self.pushButton_9.setText(QCoreApplication.translate("MainWindowDesign", u"Test7", None))
        self.pushButton_7.setText(QCoreApplication.translate("MainWindowDesign", u"Test5", None))
        self.pushButton_about.setText(QCoreApplication.translate("MainWindowDesign", u"LICENSE", None))
        self.pushButton_19.setText(QCoreApplication.translate("MainWindowDesign", u"Set Analog+Digital", None))
        self.dockWidget_panorama.setWindowTitle(QCoreApplication.translate("MainWindowDesign", u"Panorama", None))
        self.pushButton_grabPanorama.setText(QCoreApplication.translate("MainWindowDesign", u"Use current image as panorama", None))
        self.dockWidget_filename.setWindowTitle(QCoreApplication.translate("MainWindowDesign", u"File", None))
#if QT_CONFIG(tooltip)
        self.lineEdit_filename.setToolTip(QCoreApplication.translate("MainWindowDesign", u"use %s for automatic filename", None))
#endif // QT_CONFIG(tooltip)
        self.lineEdit_filename.setText(QCoreApplication.translate("MainWindowDesign", u"DEFAULT.h5", None))
        self.label_61.setText(QCoreApplication.translate("MainWindowDesign", u"Destination Folder: ", None))
        self.label_77.setText(QCoreApplication.translate("MainWindowDesign", u"File name: ", None))
        self.toolButton_filename.setText(QCoreApplication.translate("MainWindowDesign", u"...", None))
        self.lineEdit_destinationfolder.setText(QCoreApplication.translate("MainWindowDesign", u"data/", None))
        self.toolButton_destinationfolder.setText(QCoreApplication.translate("MainWindowDesign", u"...", None))
        self.lineEdit_comment.setPlaceholderText(QCoreApplication.translate("MainWindowDesign", u"Add your comments here. They will be included in the H5 file as metadata.", None))
        self.dockWidget_listfile.setWindowTitle(QCoreApplication.translate("MainWindowDesign", u"List File", None))
#if QT_CONFIG(tooltip)
        self.pushButton_copyListFile.setToolTip(QCoreApplication.translate("MainWindowDesign", u"<html><head/><body><p>This will do the &quot;Ctrl+X&quot; on the selected files, ready to be pasted in another folder.</p></body></html>", None))
#endif // QT_CONFIG(tooltip)
        self.pushButton_copyListFile.setText(QCoreApplication.translate("MainWindowDesign", u"Copy to Clipboard", None))
        self.pushButton_17.setText(QCoreApplication.translate("MainWindowDesign", u"Delete", None))
        self.pushButton_openInExplorer.setText(QCoreApplication.translate("MainWindowDesign", u"Open in explorer", None))
#if QT_CONFIG(tooltip)
        self.listWidget.setToolTip(QCoreApplication.translate("MainWindowDesign", u"<html><head/><body><p>The list of the saved files</p></body></html>", None))
#endif // QT_CONFIG(tooltip)
        self.dockWidget_AnalogCfg.setWindowTitle(QCoreApplication.translate("MainWindowDesign", u"Analog IN", None))
        self.groupBox_4.setTitle(QCoreApplication.translate("MainWindowDesign", u"Analog A", None))
        self.comboBox_analogSelect_A.setItemText(0, QCoreApplication.translate("MainWindowDesign", u"AI 0", None))
        self.comboBox_analogSelect_A.setItemText(1, QCoreApplication.translate("MainWindowDesign", u"AI 1", None))
        self.comboBox_analogSelect_A.setItemText(2, QCoreApplication.translate("MainWindowDesign", u"AI 2", None))
        self.comboBox_analogSelect_A.setItemText(3, QCoreApplication.translate("MainWindowDesign", u"AI 3", None))
        self.comboBox_analogSelect_A.setItemText(4, QCoreApplication.translate("MainWindowDesign", u"AI 4", None))
        self.comboBox_analogSelect_A.setItemText(5, QCoreApplication.translate("MainWindowDesign", u"AI 5", None))
        self.comboBox_analogSelect_A.setItemText(6, QCoreApplication.translate("MainWindowDesign", u"AI 6", None))
        self.comboBox_analogSelect_A.setItemText(7, QCoreApplication.translate("MainWindowDesign", u"AI 7", None))
        self.comboBox_analogSelect_A.setItemText(8, QCoreApplication.translate("MainWindowDesign", u"AO 0", None))
        self.comboBox_analogSelect_A.setItemText(9, QCoreApplication.translate("MainWindowDesign", u"AO 1", None))
        self.comboBox_analogSelect_A.setItemText(10, QCoreApplication.translate("MainWindowDesign", u"AO 2", None))
        self.comboBox_analogSelect_A.setItemText(11, QCoreApplication.translate("MainWindowDesign", u"AO 3", None))
        self.comboBox_analogSelect_A.setItemText(12, QCoreApplication.translate("MainWindowDesign", u"AO 4", None))
        self.comboBox_analogSelect_A.setItemText(13, QCoreApplication.translate("MainWindowDesign", u"AO 5", None))
        self.comboBox_analogSelect_A.setItemText(14, QCoreApplication.translate("MainWindowDesign", u"AO 6", None))
        self.comboBox_analogSelect_A.setItemText(15, QCoreApplication.translate("MainWindowDesign", u"AO 7", None))
        self.comboBox_analogSelect_A.setItemText(16, QCoreApplication.translate("MainWindowDesign", u"OFF", None))

        self.checkBox_analog_in_differentiate_A.setText(QCoreApplication.translate("MainWindowDesign", u"Differentiate", None))
        self.groupBox_5.setTitle(QCoreApplication.translate("MainWindowDesign", u"Analog B", None))
        self.comboBox_analogSelect_B.setItemText(0, QCoreApplication.translate("MainWindowDesign", u"AI 0", None))
        self.comboBox_analogSelect_B.setItemText(1, QCoreApplication.translate("MainWindowDesign", u"AI 1", None))
        self.comboBox_analogSelect_B.setItemText(2, QCoreApplication.translate("MainWindowDesign", u"AI 2", None))
        self.comboBox_analogSelect_B.setItemText(3, QCoreApplication.translate("MainWindowDesign", u"AI 3", None))
        self.comboBox_analogSelect_B.setItemText(4, QCoreApplication.translate("MainWindowDesign", u"AI 4", None))
        self.comboBox_analogSelect_B.setItemText(5, QCoreApplication.translate("MainWindowDesign", u"AI 5", None))
        self.comboBox_analogSelect_B.setItemText(6, QCoreApplication.translate("MainWindowDesign", u"AI 6", None))
        self.comboBox_analogSelect_B.setItemText(7, QCoreApplication.translate("MainWindowDesign", u"AI 7", None))
        self.comboBox_analogSelect_B.setItemText(8, QCoreApplication.translate("MainWindowDesign", u"AO 0", None))
        self.comboBox_analogSelect_B.setItemText(9, QCoreApplication.translate("MainWindowDesign", u"AO 1", None))
        self.comboBox_analogSelect_B.setItemText(10, QCoreApplication.translate("MainWindowDesign", u"AO 2", None))
        self.comboBox_analogSelect_B.setItemText(11, QCoreApplication.translate("MainWindowDesign", u"AO 3", None))
        self.comboBox_analogSelect_B.setItemText(12, QCoreApplication.translate("MainWindowDesign", u"AO 4", None))
        self.comboBox_analogSelect_B.setItemText(13, QCoreApplication.translate("MainWindowDesign", u"AO 5", None))
        self.comboBox_analogSelect_B.setItemText(14, QCoreApplication.translate("MainWindowDesign", u"AO 6", None))
        self.comboBox_analogSelect_B.setItemText(15, QCoreApplication.translate("MainWindowDesign", u"AO 7", None))
        self.comboBox_analogSelect_B.setItemText(16, QCoreApplication.translate("MainWindowDesign", u"OFF", None))

        self.checkBox_analog_in_differentiate_B.setText(QCoreApplication.translate("MainWindowDesign", u"Differentiate", None))
        self.checkBox_analog_in_invert_AI1.setText(QCoreApplication.translate("MainWindowDesign", u"Invert", None))
        self.label_83.setText(QCoreApplication.translate("MainWindowDesign", u"AI 2", None))
        self.checkBox_analog_in_integrate_AI0.setText(QCoreApplication.translate("MainWindowDesign", u"Integrate", None))
        self.label_82.setText(QCoreApplication.translate("MainWindowDesign", u"AI 1", None))
        self.checkBox_analog_in_invert_AI3.setText(QCoreApplication.translate("MainWindowDesign", u"Invert", None))
        self.checkBox_analog_in_invert_AI0.setText(QCoreApplication.translate("MainWindowDesign", u"Invert", None))
        self.checkBox_analog_in_invert_AI2.setText(QCoreApplication.translate("MainWindowDesign", u"Invert", None))
        self.label_80.setText(QCoreApplication.translate("MainWindowDesign", u"AI 0", None))
        self.label_84.setText(QCoreApplication.translate("MainWindowDesign", u"AI 3", None))
        self.checkBox_analog_in_integrate_AI1.setText(QCoreApplication.translate("MainWindowDesign", u"Integrate", None))
        self.checkBox_analog_in_integrate_AI2.setText(QCoreApplication.translate("MainWindowDesign", u"Integrate", None))
        self.checkBox_analog_in_integrate_AI3.setText(QCoreApplication.translate("MainWindowDesign", u"Integrate", None))
        self.dockWidget_plugins.setWindowTitle(QCoreApplication.translate("MainWindowDesign", u"Plug-ins", None))
        self.pushButton_loadPlugin.setText(QCoreApplication.translate("MainWindowDesign", u"Load Plugin", None))
        self.pushButton_5.setText(QCoreApplication.translate("MainWindowDesign", u"Update List", None))
        self.pushButton_closePlugin.setText(QCoreApplication.translate("MainWindowDesign", u"Close Plugin", None))
        self.dockWidget_analogOut.setWindowTitle(QCoreApplication.translate("MainWindowDesign", u"Analog OUT", None))
        self.label_AnalogOut_checkbox_titl.setText(QCoreApplication.translate("MainWindowDesign", u"Set to 0V on Stop", None))
        self.label_AnalogOut_title2.setText(QCoreApplication.translate("MainWindowDesign", u"Signal", None))
        self.comboBox_AnalogOut.setItemText(0, QCoreApplication.translate("MainWindowDesign", u"X", None))
        self.comboBox_AnalogOut.setItemText(1, QCoreApplication.translate("MainWindowDesign", u"Y", None))
        self.comboBox_AnalogOut.setItemText(2, QCoreApplication.translate("MainWindowDesign", u"Z", None))
        self.comboBox_AnalogOut.setItemText(3, QCoreApplication.translate("MainWindowDesign", u"Constant", None))

        self.label_AnalogOut.setText(QCoreApplication.translate("MainWindowDesign", u"AnalogOut 0", None))
        self.label_AnalogOut_title1.setText(QCoreApplication.translate("MainWindowDesign", u"Channel", None))
        self.label_AnalogOut_title3.setText(QCoreApplication.translate("MainWindowDesign", u"Constant Value (V)", None))
        self.checkBox_AnalogOut.setText("")
        self.dockWidget_traceConf.setWindowTitle(QCoreApplication.translate("MainWindowDesign", u"Conf.", None))
        self.label_73.setText(QCoreApplication.translate("MainWindowDesign", u"Trace bin [ms]", None))
        self.checkBox_trace_on.setText(QCoreApplication.translate("MainWindowDesign", u"Trace Active", None))
        self.pushButton_trace.setText(QCoreApplication.translate("MainWindowDesign", u"Trace Reset", None))
        self.checkBox_trace_autorange.setText(QCoreApplication.translate("MainWindowDesign", u"Time-autorange", None))
        self.label_74.setText(QCoreApplication.translate("MainWindowDesign", u"Trace length [s]", None))
        self.label_trace_total_bins.setText(QCoreApplication.translate("MainWindowDesign", u"30000", None))
        self.label_76.setText(QCoreApplication.translate("MainWindowDesign", u"Trace tot. bins", None))
        self.label_plot_channel.setText(QCoreApplication.translate("MainWindowDesign", u"Selected Ch: X", None))
        self.dockWidget_pluginImage.setWindowTitle(QCoreApplication.translate("MainWindowDesign", u"Image Script", None))
    # retranslateUi

