# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'dfd_widget_design.ui'
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
from PySide6.QtWidgets import (QAbstractScrollArea, QApplication, QCheckBox, QComboBox,
    QDoubleSpinBox, QGridLayout, QGroupBox, QHeaderView,
    QLabel, QLineEdit, QPushButton, QScrollArea,
    QSizePolicy, QSpacerItem, QSpinBox, QTabWidget,
    QTableView, QWidget)

from .scispinbox import sciSpinBox

class Ui_Form(object):
    def setupUi(self, Form):
        if not Form.objectName():
            Form.setObjectName(u"Form")
        Form.resize(972, 757)
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(Form.sizePolicy().hasHeightForWidth())
        Form.setSizePolicy(sizePolicy)
        self.gridLayout_2 = QGridLayout(Form)
        self.gridLayout_2.setObjectName(u"gridLayout_2")
        self.tabWidget = QTabWidget(Form)
        self.tabWidget.setObjectName(u"tabWidget")
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.MinimumExpanding)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.tabWidget.sizePolicy().hasHeightForWidth())
        self.tabWidget.setSizePolicy(sizePolicy1)
        self.tabWidget_conf = QWidget()
        self.tabWidget_conf.setObjectName(u"tabWidget_conf")
        self.gridLayout_10 = QGridLayout(self.tabWidget_conf)
        self.gridLayout_10.setObjectName(u"gridLayout_10")
        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.gridLayout_10.addItem(self.verticalSpacer, 5, 0, 1, 1)

        self.groupBox_3 = QGroupBox(self.tabWidget_conf)
        self.groupBox_3.setObjectName(u"groupBox_3")
        self.gridLayout_4 = QGridLayout(self.groupBox_3)
        self.gridLayout_4.setObjectName(u"gridLayout_4")
        self.lineEdit_file_meas = QLineEdit(self.groupBox_3)
        self.lineEdit_file_meas.setObjectName(u"lineEdit_file_meas")

        self.gridLayout_4.addWidget(self.lineEdit_file_meas, 0, 0, 1, 1)

        self.pushButton_meas_file = QPushButton(self.groupBox_3)
        self.pushButton_meas_file.setObjectName(u"pushButton_meas_file")
        sizePolicy2 = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.pushButton_meas_file.sizePolicy().hasHeightForWidth())
        self.pushButton_meas_file.setSizePolicy(sizePolicy2)
        self.pushButton_meas_file.setMaximumSize(QSize(40, 40))

        self.gridLayout_4.addWidget(self.pushButton_meas_file, 0, 1, 1, 1)

        self.pushButton_meas_last_acq = QPushButton(self.groupBox_3)
        self.pushButton_meas_last_acq.setObjectName(u"pushButton_meas_last_acq")

        self.gridLayout_4.addWidget(self.pushButton_meas_last_acq, 0, 2, 1, 1)

        self.pushButton_meas_load = QPushButton(self.groupBox_3)
        self.pushButton_meas_load.setObjectName(u"pushButton_meas_load")

        self.gridLayout_4.addWidget(self.pushButton_meas_load, 0, 3, 1, 1)

        self.groupBox_8 = QGroupBox(self.groupBox_3)
        self.groupBox_8.setObjectName(u"groupBox_8")
        self.groupBox_8.setCheckable(False)
        self.gridLayout_12 = QGridLayout(self.groupBox_8)
        self.gridLayout_12.setObjectName(u"gridLayout_12")
        self.label_7 = QLabel(self.groupBox_8)
        self.label_7.setObjectName(u"label_7")

        self.gridLayout_12.addWidget(self.label_7, 1, 0, 1, 1)

        self.spinBox_merge_pixel = QSpinBox(self.groupBox_8)
        self.spinBox_merge_pixel.setObjectName(u"spinBox_merge_pixel")
        self.spinBox_merge_pixel.setMaximum(1024)

        self.gridLayout_12.addWidget(self.spinBox_merge_pixel, 1, 1, 1, 1)

        self.checkBox_correction_activate = QCheckBox(self.groupBox_8)
        self.checkBox_correction_activate.setObjectName(u"checkBox_correction_activate")
        self.checkBox_correction_activate.setChecked(True)

        self.gridLayout_12.addWidget(self.checkBox_correction_activate, 0, 0, 1, 2)


        self.gridLayout_4.addWidget(self.groupBox_8, 1, 2, 1, 2)

        self.groupBox_7 = QGroupBox(self.groupBox_3)
        self.groupBox_7.setObjectName(u"groupBox_7")
        self.gridLayout_6 = QGridLayout(self.groupBox_7)
        self.gridLayout_6.setObjectName(u"gridLayout_6")
        self.horizontalSpacer_4 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.gridLayout_6.addItem(self.horizontalSpacer_4, 1, 1, 1, 1)

        self.pushButton_export_h5 = QPushButton(self.groupBox_7)
        self.pushButton_export_h5.setObjectName(u"pushButton_export_h5")

        self.gridLayout_6.addWidget(self.pushButton_export_h5, 0, 2, 1, 1)

        self.lineEdit_file_h5_export = QLineEdit(self.groupBox_7)
        self.lineEdit_file_h5_export.setObjectName(u"lineEdit_file_h5_export")

        self.gridLayout_6.addWidget(self.lineEdit_file_h5_export, 0, 1, 1, 1)


        self.gridLayout_4.addWidget(self.groupBox_7, 1, 0, 1, 2)


        self.gridLayout_10.addWidget(self.groupBox_3, 3, 0, 1, 1)

        self.groupBox_5 = QGroupBox(self.tabWidget_conf)
        self.groupBox_5.setObjectName(u"groupBox_5")
        sizePolicy3 = QSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
        sizePolicy3.setHorizontalStretch(0)
        sizePolicy3.setVerticalStretch(0)
        sizePolicy3.setHeightForWidth(self.groupBox_5.sizePolicy().hasHeightForWidth())
        self.groupBox_5.setSizePolicy(sizePolicy3)
        self.gridLayout_7 = QGridLayout(self.groupBox_5)
        self.gridLayout_7.setObjectName(u"gridLayout_7")
        self.tableView_meas_2 = QTabWidget(self.groupBox_5)
        self.tableView_meas_2.setObjectName(u"tableView_meas_2")
        sizePolicy3.setHeightForWidth(self.tableView_meas_2.sizePolicy().hasHeightForWidth())
        self.tableView_meas_2.setSizePolicy(sizePolicy3)
        self.tab = QWidget()
        self.tab.setObjectName(u"tab")
        self.gridLayout_3 = QGridLayout(self.tab)
        self.gridLayout_3.setObjectName(u"gridLayout_3")
        self.pushButton_import_phasors_txt = QPushButton(self.tab)
        self.pushButton_import_phasors_txt.setObjectName(u"pushButton_import_phasors_txt")

        self.gridLayout_3.addWidget(self.pushButton_import_phasors_txt, 1, 0, 1, 1)

        self.pushButton_export_phasors_txt = QPushButton(self.tab)
        self.pushButton_export_phasors_txt.setObjectName(u"pushButton_export_phasors_txt")

        self.gridLayout_3.addWidget(self.pushButton_export_phasors_txt, 1, 1, 1, 1)

        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.gridLayout_3.addItem(self.horizontalSpacer, 1, 2, 1, 1)

        self.tableView_corr = QTableView(self.tab)
        self.tableView_corr.setObjectName(u"tableView_corr")
        sizePolicy3.setHeightForWidth(self.tableView_corr.sizePolicy().hasHeightForWidth())
        self.tableView_corr.setSizePolicy(sizePolicy3)
        self.tableView_corr.setSizeAdjustPolicy(QAbstractScrollArea.AdjustIgnored)

        self.gridLayout_3.addWidget(self.tableView_corr, 2, 0, 1, 3)

        self.tableView_meas_2.addTab(self.tab, "")
        self.tab_2 = QWidget()
        self.tab_2.setObjectName(u"tab_2")
        self.gridLayout_5 = QGridLayout(self.tab_2)
        self.gridLayout_5.setObjectName(u"gridLayout_5")
        self.tableView_meas = QTableView(self.tab_2)
        self.tableView_meas.setObjectName(u"tableView_meas")
        sizePolicy3.setHeightForWidth(self.tableView_meas.sizePolicy().hasHeightForWidth())
        self.tableView_meas.setSizePolicy(sizePolicy3)
        self.tableView_meas.setSizeAdjustPolicy(QAbstractScrollArea.AdjustIgnored)

        self.gridLayout_5.addWidget(self.tableView_meas, 1, 0, 1, 1)

        self.label_average = QLabel(self.tab_2)
        self.label_average.setObjectName(u"label_average")

        self.gridLayout_5.addWidget(self.label_average, 2, 0, 1, 1)

        self.tableView_meas_2.addTab(self.tab_2, "")

        self.gridLayout_7.addWidget(self.tableView_meas_2, 0, 1, 1, 1)


        self.gridLayout_10.addWidget(self.groupBox_5, 4, 0, 1, 2)

        self.groupBox = QGroupBox(self.tabWidget_conf)
        self.groupBox.setObjectName(u"groupBox")
        self.gridLayout = QGridLayout(self.groupBox)
        self.gridLayout.setObjectName(u"gridLayout")
        self.pushButton_ref_load = QPushButton(self.groupBox)
        self.pushButton_ref_load.setObjectName(u"pushButton_ref_load")

        self.gridLayout.addWidget(self.pushButton_ref_load, 0, 6, 1, 1)

        self.pushButton_ref_last_acq = QPushButton(self.groupBox)
        self.pushButton_ref_last_acq.setObjectName(u"pushButton_ref_last_acq")

        self.gridLayout.addWidget(self.pushButton_ref_last_acq, 0, 5, 1, 1)

        self.groupBox_4 = QGroupBox(self.groupBox)
        self.groupBox_4.setObjectName(u"groupBox_4")
        self.gridLayout_8 = QGridLayout(self.groupBox_4)
        self.gridLayout_8.setObjectName(u"gridLayout_8")
        self.doubleSpinBox_ref_tau = QDoubleSpinBox(self.groupBox_4)
        self.doubleSpinBox_ref_tau.setObjectName(u"doubleSpinBox_ref_tau")

        self.gridLayout_8.addWidget(self.doubleSpinBox_ref_tau, 0, 1, 1, 1)

        self.horizontalSpacer_2 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.gridLayout_8.addItem(self.horizontalSpacer_2, 0, 3, 1, 1)

        self.label_6 = QLabel(self.groupBox_4)
        self.label_6.setObjectName(u"label_6")

        self.gridLayout_8.addWidget(self.label_6, 0, 2, 1, 1)

        self.label_5 = QLabel(self.groupBox_4)
        self.label_5.setObjectName(u"label_5")

        self.gridLayout_8.addWidget(self.label_5, 0, 0, 1, 1)


        self.gridLayout.addWidget(self.groupBox_4, 2, 1, 1, 4)

        self.groupBox_2 = QGroupBox(self.groupBox)
        self.groupBox_2.setObjectName(u"groupBox_2")
        self.gridLayout_9 = QGridLayout(self.groupBox_2)
        self.gridLayout_9.setObjectName(u"gridLayout_9")
        self.lineEdit_ref_irf_filter = QLineEdit(self.groupBox_2)
        self.lineEdit_ref_irf_filter.setObjectName(u"lineEdit_ref_irf_filter")

        self.gridLayout_9.addWidget(self.lineEdit_ref_irf_filter, 1, 1, 1, 1)

        self.label = QLabel(self.groupBox_2)
        self.label.setObjectName(u"label")

        self.gridLayout_9.addWidget(self.label, 0, 1, 1, 1)


        self.gridLayout.addWidget(self.groupBox_2, 2, 5, 1, 2)

        self.pushButton_ref_file = QPushButton(self.groupBox)
        self.pushButton_ref_file.setObjectName(u"pushButton_ref_file")
        sizePolicy2.setHeightForWidth(self.pushButton_ref_file.sizePolicy().hasHeightForWidth())
        self.pushButton_ref_file.setSizePolicy(sizePolicy2)
        self.pushButton_ref_file.setMaximumSize(QSize(40, 40))

        self.gridLayout.addWidget(self.pushButton_ref_file, 0, 4, 1, 1)

        self.horizontalSpacer_5 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.gridLayout.addItem(self.horizontalSpacer_5, 2, 0, 1, 1)

        self.lineEdit_file_ref = QLineEdit(self.groupBox)
        self.lineEdit_file_ref.setObjectName(u"lineEdit_file_ref")
        sizePolicy4 = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        sizePolicy4.setHorizontalStretch(0)
        sizePolicy4.setVerticalStretch(0)
        sizePolicy4.setHeightForWidth(self.lineEdit_file_ref.sizePolicy().hasHeightForWidth())
        self.lineEdit_file_ref.setSizePolicy(sizePolicy4)

        self.gridLayout.addWidget(self.lineEdit_file_ref, 0, 0, 1, 4)


        self.gridLayout_10.addWidget(self.groupBox, 2, 0, 1, 1)

        self.tabWidget.addTab(self.tabWidget_conf, "")
        self.tabWidget_hist = QWidget()
        self.tabWidget_hist.setObjectName(u"tabWidget_hist")
        self.gridLayout_18 = QGridLayout(self.tabWidget_hist)
        self.gridLayout_18.setObjectName(u"gridLayout_18")
        self.gridLayout_hist = QGridLayout()
        self.gridLayout_hist.setObjectName(u"gridLayout_hist")

        self.gridLayout_18.addLayout(self.gridLayout_hist, 0, 0, 1, 1)

        self.tabWidget.addTab(self.tabWidget_hist, "")
        self.tabWidget_phasor = QWidget()
        self.tabWidget_phasor.setObjectName(u"tabWidget_phasor")
        self.gridLayout_15 = QGridLayout(self.tabWidget_phasor)
        self.gridLayout_15.setObjectName(u"gridLayout_15")
        self.gridLayout_phasor = QGridLayout()
        self.gridLayout_phasor.setObjectName(u"gridLayout_phasor")

        self.gridLayout_15.addLayout(self.gridLayout_phasor, 0, 0, 1, 1)

        self.tabWidget.addTab(self.tabWidget_phasor, "")
        self.tabWidget_flim = QWidget()
        self.tabWidget_flim.setObjectName(u"tabWidget_flim")
        self.gridLayout_13 = QGridLayout(self.tabWidget_flim)
        self.gridLayout_13.setObjectName(u"gridLayout_13")
        self.groupBox_9 = QGroupBox(self.tabWidget_flim)
        self.groupBox_9.setObjectName(u"groupBox_9")
        sizePolicy5 = QSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.MinimumExpanding)
        sizePolicy5.setHorizontalStretch(0)
        sizePolicy5.setVerticalStretch(0)
        sizePolicy5.setHeightForWidth(self.groupBox_9.sizePolicy().hasHeightForWidth())
        self.groupBox_9.setSizePolicy(sizePolicy5)
        self.gridLayout_16 = QGridLayout(self.groupBox_9)
        self.gridLayout_16.setObjectName(u"gridLayout_16")
        self.scrollArea = QScrollArea(self.groupBox_9)
        self.scrollArea.setObjectName(u"scrollArea")
        self.scrollArea.setWidgetResizable(True)
        self.scrollAreaWidgetContents = QWidget()
        self.scrollAreaWidgetContents.setObjectName(u"scrollAreaWidgetContents")
        self.scrollAreaWidgetContents.setGeometry(QRect(0, 0, 908, 350))
        self.gridLayout_17 = QGridLayout(self.scrollAreaWidgetContents)
        self.gridLayout_17.setObjectName(u"gridLayout_17")
        self.gridLayout_flim = QGridLayout()
        self.gridLayout_flim.setObjectName(u"gridLayout_flim")

        self.gridLayout_17.addLayout(self.gridLayout_flim, 0, 0, 1, 1)

        self.scrollArea.setWidget(self.scrollAreaWidgetContents)

        self.gridLayout_16.addWidget(self.scrollArea, 0, 0, 1, 1)


        self.gridLayout_13.addWidget(self.groupBox_9, 0, 0, 1, 1)

        self.groupBox_10 = QGroupBox(self.tabWidget_flim)
        self.groupBox_10.setObjectName(u"groupBox_10")
        self.gridLayout_14 = QGridLayout(self.groupBox_10)
        self.gridLayout_14.setObjectName(u"gridLayout_14")
        self.label_suggest = QLabel(self.groupBox_10)
        self.label_suggest.setObjectName(u"label_suggest")

        self.gridLayout_14.addWidget(self.label_suggest, 2, 0, 1, 1)

        self.pushButton_file_h5_input = QPushButton(self.groupBox_10)
        self.pushButton_file_h5_input.setObjectName(u"pushButton_file_h5_input")
        sizePolicy2.setHeightForWidth(self.pushButton_file_h5_input.sizePolicy().hasHeightForWidth())
        self.pushButton_file_h5_input.setSizePolicy(sizePolicy2)
        self.pushButton_file_h5_input.setMaximumSize(QSize(40, 40))

        self.gridLayout_14.addWidget(self.pushButton_file_h5_input, 0, 5, 1, 1)

        self.groupBox_11 = QGroupBox(self.groupBox_10)
        self.groupBox_11.setObjectName(u"groupBox_11")
        self.gridLayout_19 = QGridLayout(self.groupBox_11)
        self.gridLayout_19.setObjectName(u"gridLayout_19")
        self.comboBox_flim_tau = QComboBox(self.groupBox_11)
        self.comboBox_flim_tau.addItem("")
        self.comboBox_flim_tau.addItem("")
        self.comboBox_flim_tau.addItem("")
        self.comboBox_flim_tau.addItem("")
        self.comboBox_flim_tau.addItem("")
        self.comboBox_flim_tau.setObjectName(u"comboBox_flim_tau")

        self.gridLayout_19.addWidget(self.comboBox_flim_tau, 0, 1, 1, 1)

        self.label_13 = QLabel(self.groupBox_11)
        self.label_13.setObjectName(u"label_13")

        self.gridLayout_19.addWidget(self.label_13, 0, 2, 1, 1)

        self.label_11 = QLabel(self.groupBox_11)
        self.label_11.setObjectName(u"label_11")

        self.gridLayout_19.addWidget(self.label_11, 0, 0, 1, 1)

        self.comboBox_tau_channel = QComboBox(self.groupBox_11)
        self.comboBox_tau_channel.addItem("")
        self.comboBox_tau_channel.addItem("")
        self.comboBox_tau_channel.addItem("")
        self.comboBox_tau_channel.addItem("")
        self.comboBox_tau_channel.addItem("")
        self.comboBox_tau_channel.addItem("")
        self.comboBox_tau_channel.addItem("")
        self.comboBox_tau_channel.addItem("")
        self.comboBox_tau_channel.addItem("")
        self.comboBox_tau_channel.addItem("")
        self.comboBox_tau_channel.addItem("")
        self.comboBox_tau_channel.addItem("")
        self.comboBox_tau_channel.addItem("")
        self.comboBox_tau_channel.addItem("")
        self.comboBox_tau_channel.addItem("")
        self.comboBox_tau_channel.addItem("")
        self.comboBox_tau_channel.addItem("")
        self.comboBox_tau_channel.addItem("")
        self.comboBox_tau_channel.addItem("")
        self.comboBox_tau_channel.addItem("")
        self.comboBox_tau_channel.addItem("")
        self.comboBox_tau_channel.addItem("")
        self.comboBox_tau_channel.addItem("")
        self.comboBox_tau_channel.addItem("")
        self.comboBox_tau_channel.addItem("")
        self.comboBox_tau_channel.addItem("")
        self.comboBox_tau_channel.setObjectName(u"comboBox_tau_channel")

        self.gridLayout_19.addWidget(self.comboBox_tau_channel, 0, 3, 1, 1)

        self.doubleSpinBox_outOfBoundsHue = sciSpinBox(self.groupBox_11)
        self.doubleSpinBox_outOfBoundsHue.setObjectName(u"doubleSpinBox_outOfBoundsHue")
        self.doubleSpinBox_outOfBoundsHue.setDecimals(3)
        self.doubleSpinBox_outOfBoundsHue.setMinimum(-99.989999999999995)
        self.doubleSpinBox_outOfBoundsHue.setValue(0.800000000000000)

        self.gridLayout_19.addWidget(self.doubleSpinBox_outOfBoundsHue, 2, 3, 1, 1)

        self.label_16 = QLabel(self.groupBox_11)
        self.label_16.setObjectName(u"label_16")

        self.gridLayout_19.addWidget(self.label_16, 2, 4, 1, 1)

        self.label_14 = QLabel(self.groupBox_11)
        self.label_14.setObjectName(u"label_14")

        self.gridLayout_19.addWidget(self.label_14, 2, 2, 1, 1)

        self.checkBox_flim_invertcolor = QCheckBox(self.groupBox_11)
        self.checkBox_flim_invertcolor.setObjectName(u"checkBox_flim_invertcolor")

        self.gridLayout_19.addWidget(self.checkBox_flim_invertcolor, 2, 6, 1, 1)

        self.doubleSpinBox_satFactor = sciSpinBox(self.groupBox_11)
        self.doubleSpinBox_satFactor.setObjectName(u"doubleSpinBox_satFactor")
        self.doubleSpinBox_satFactor.setDecimals(3)
        self.doubleSpinBox_satFactor.setMinimum(-99.989999999999995)
        self.doubleSpinBox_satFactor.setValue(0.660000000000000)

        self.gridLayout_19.addWidget(self.doubleSpinBox_satFactor, 2, 5, 1, 1)

        self.label_8 = QLabel(self.groupBox_11)
        self.label_8.setObjectName(u"label_8")

        self.gridLayout_19.addWidget(self.label_8, 1, 2, 1, 1)

        self.doubleSpinBox_min_tau = sciSpinBox(self.groupBox_11)
        self.doubleSpinBox_min_tau.setObjectName(u"doubleSpinBox_min_tau")
        self.doubleSpinBox_min_tau.setMinimum(-99.989999999999995)
        self.doubleSpinBox_min_tau.setValue(3.000000000000000)

        self.gridLayout_19.addWidget(self.doubleSpinBox_min_tau, 1, 3, 1, 1)

        self.label_9 = QLabel(self.groupBox_11)
        self.label_9.setObjectName(u"label_9")

        self.gridLayout_19.addWidget(self.label_9, 1, 4, 1, 1)

        self.doubleSpinBox_max_tau = sciSpinBox(self.groupBox_11)
        self.doubleSpinBox_max_tau.setObjectName(u"doubleSpinBox_max_tau")
        self.doubleSpinBox_max_tau.setMinimum(-99.000000000000000)
        self.doubleSpinBox_max_tau.setValue(5.000000000000000)

        self.gridLayout_19.addWidget(self.doubleSpinBox_max_tau, 1, 5, 1, 1)

        self.label_10 = QLabel(self.groupBox_11)
        self.label_10.setObjectName(u"label_10")

        self.gridLayout_19.addWidget(self.label_10, 1, 6, 1, 1)


        self.gridLayout_14.addWidget(self.groupBox_11, 3, 0, 2, 5)

        self.label_12 = QLabel(self.groupBox_10)
        self.label_12.setObjectName(u"label_12")

        self.gridLayout_14.addWidget(self.label_12, 0, 0, 1, 1)

        self.checkBox_hist_std_range = QCheckBox(self.groupBox_10)
        self.checkBox_hist_std_range.setObjectName(u"checkBox_hist_std_range")
        self.checkBox_hist_std_range.setChecked(True)

        self.gridLayout_14.addWidget(self.checkBox_hist_std_range, 1, 0, 1, 1)

        self.pushButton_show_flim_hist = QPushButton(self.groupBox_10)
        self.pushButton_show_flim_hist.setObjectName(u"pushButton_show_flim_hist")

        self.gridLayout_14.addWidget(self.pushButton_show_flim_hist, 1, 1, 1, 1)

        self.lineEdit_file_h5_input = QLineEdit(self.groupBox_10)
        self.lineEdit_file_h5_input.setObjectName(u"lineEdit_file_h5_input")

        self.gridLayout_14.addWidget(self.lineEdit_file_h5_input, 0, 1, 1, 4)

        self.pushButton_show_flim_img = QPushButton(self.groupBox_10)
        self.pushButton_show_flim_img.setObjectName(u"pushButton_show_flim_img")

        self.gridLayout_14.addWidget(self.pushButton_show_flim_img, 1, 2, 1, 1)

        self.pushButton_flim_plot_phasors = QPushButton(self.groupBox_10)
        self.pushButton_flim_plot_phasors.setObjectName(u"pushButton_flim_plot_phasors")

        self.gridLayout_14.addWidget(self.pushButton_flim_plot_phasors, 1, 3, 1, 1)

        self.groupBox_12 = QGroupBox(self.groupBox_10)
        self.groupBox_12.setObjectName(u"groupBox_12")
        self.gridLayout_20 = QGridLayout(self.groupBox_12)
        self.gridLayout_20.setObjectName(u"gridLayout_20")
        self.comboBox_flim_intensity = QComboBox(self.groupBox_12)
        self.comboBox_flim_intensity.addItem("")
        self.comboBox_flim_intensity.addItem("")
        self.comboBox_flim_intensity.addItem("")
        self.comboBox_flim_intensity.addItem("")
        self.comboBox_flim_intensity.addItem("")
        self.comboBox_flim_intensity.addItem("")
        self.comboBox_flim_intensity.addItem("")
        self.comboBox_flim_intensity.addItem("")
        self.comboBox_flim_intensity.addItem("")
        self.comboBox_flim_intensity.addItem("")
        self.comboBox_flim_intensity.addItem("")
        self.comboBox_flim_intensity.addItem("")
        self.comboBox_flim_intensity.addItem("")
        self.comboBox_flim_intensity.addItem("")
        self.comboBox_flim_intensity.addItem("")
        self.comboBox_flim_intensity.addItem("")
        self.comboBox_flim_intensity.addItem("")
        self.comboBox_flim_intensity.addItem("")
        self.comboBox_flim_intensity.addItem("")
        self.comboBox_flim_intensity.addItem("")
        self.comboBox_flim_intensity.addItem("")
        self.comboBox_flim_intensity.addItem("")
        self.comboBox_flim_intensity.addItem("")
        self.comboBox_flim_intensity.addItem("")
        self.comboBox_flim_intensity.addItem("")
        self.comboBox_flim_intensity.addItem("")
        self.comboBox_flim_intensity.addItem("")
        self.comboBox_flim_intensity.setObjectName(u"comboBox_flim_intensity")

        self.gridLayout_20.addWidget(self.comboBox_flim_intensity, 0, 1, 1, 1)

        self.label_15 = QLabel(self.groupBox_12)
        self.label_15.setObjectName(u"label_15")

        self.gridLayout_20.addWidget(self.label_15, 0, 0, 1, 1)


        self.gridLayout_14.addWidget(self.groupBox_12, 1, 4, 1, 1)


        self.gridLayout_13.addWidget(self.groupBox_10, 1, 0, 1, 1)

        self.tabWidget.addTab(self.tabWidget_flim, "")

        self.gridLayout_2.addWidget(self.tabWidget, 2, 0, 1, 2)

        self.groupBox_6 = QGroupBox(Form)
        self.groupBox_6.setObjectName(u"groupBox_6")
        sizePolicy3.setHeightForWidth(self.groupBox_6.sizePolicy().hasHeightForWidth())
        self.groupBox_6.setSizePolicy(sizePolicy3)
        self.gridLayout_11 = QGridLayout(self.groupBox_6)
        self.gridLayout_11.setObjectName(u"gridLayout_11")
        self.doubleSpinBox_dfd_freq = QDoubleSpinBox(self.groupBox_6)
        self.doubleSpinBox_dfd_freq.setObjectName(u"doubleSpinBox_dfd_freq")
        self.doubleSpinBox_dfd_freq.setDecimals(6)
        self.doubleSpinBox_dfd_freq.setValue(21.000000000000000)

        self.gridLayout_11.addWidget(self.doubleSpinBox_dfd_freq, 0, 2, 1, 1)

        self.label_2 = QLabel(self.groupBox_6)
        self.label_2.setObjectName(u"label_2")

        self.gridLayout_11.addWidget(self.label_2, 0, 1, 1, 1)

        self.label_over = QLabel(self.groupBox_6)
        self.label_over.setObjectName(u"label_over")
        self.label_over.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.gridLayout_11.addWidget(self.label_over, 0, 6, 1, 1)

        self.horizontalSpacer_3 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.gridLayout_11.addItem(self.horizontalSpacer_3, 0, 4, 1, 1)

        self.label_3 = QLabel(self.groupBox_6)
        self.label_3.setObjectName(u"label_3")

        self.gridLayout_11.addWidget(self.label_3, 0, 3, 1, 1)

        self.label_4 = QLabel(self.groupBox_6)
        self.label_4.setObjectName(u"label_4")

        self.gridLayout_11.addWidget(self.label_4, 0, 5, 1, 1)


        self.gridLayout_2.addWidget(self.groupBox_6, 0, 0, 1, 1)


        self.retranslateUi(Form)

        self.tabWidget.setCurrentIndex(3)
        self.tableView_meas_2.setCurrentIndex(0)


        QMetaObject.connectSlotsByName(Form)
    # setupUi

    def retranslateUi(self, Form):
        Form.setWindowTitle(QCoreApplication.translate("Form", u"Form", None))
        self.groupBox_3.setTitle(QCoreApplication.translate("Form", u"Measurement", None))
        self.pushButton_meas_file.setText(QCoreApplication.translate("Form", u"...", None))
        self.pushButton_meas_last_acq.setText(QCoreApplication.translate("Form", u"Use Current Acquistion", None))
        self.pushButton_meas_load.setText(QCoreApplication.translate("Form", u"Load", None))
        self.groupBox_8.setTitle(QCoreApplication.translate("Form", u"Adv.", None))
        self.label_7.setText(QCoreApplication.translate("Form", u"Join adjacent pixel", None))
        self.checkBox_correction_activate.setText(QCoreApplication.translate("Form", u"Use correction table", None))
        self.groupBox_7.setTitle(QCoreApplication.translate("Form", u"Export complete phasors data", None))
        self.pushButton_export_h5.setText(QCoreApplication.translate("Form", u"Save to .h5", None))
        self.groupBox_5.setTitle(QCoreApplication.translate("Form", u"Phasors", None))
        self.pushButton_import_phasors_txt.setText(QCoreApplication.translate("Form", u"Import from .txt", None))
        self.pushButton_export_phasors_txt.setText(QCoreApplication.translate("Form", u"Export to .txt", None))
        self.tableView_meas_2.setTabText(self.tableView_meas_2.indexOf(self.tab), QCoreApplication.translate("Form", u"Correction Phasors", None))
        self.label_average.setText(QCoreApplication.translate("Form", u"Average:", None))
        self.tableView_meas_2.setTabText(self.tableView_meas_2.indexOf(self.tab_2), QCoreApplication.translate("Form", u"Measured Phasors", None))
        self.groupBox.setTitle(QCoreApplication.translate("Form", u"Reference", None))
        self.pushButton_ref_load.setText(QCoreApplication.translate("Form", u"Load", None))
        self.pushButton_ref_last_acq.setText(QCoreApplication.translate("Form", u"Use Current Acquistion", None))
        self.groupBox_4.setTitle(QCoreApplication.translate("Form", u"Reference", None))
        self.label_6.setText(QCoreApplication.translate("Form", u"ns", None))
        self.label_5.setText(QCoreApplication.translate("Form", u"Lifetime", None))
        self.groupBox_2.setTitle(QCoreApplication.translate("Form", u"Filter (only for IRF)", None))
        self.lineEdit_ref_irf_filter.setText(QCoreApplication.translate("Form", u"0.1", None))
        self.label.setText(QCoreApplication.translate("Form", u"Example: \"None\", \"normalize\", \"0.1\", \"0.2\"", None))
        self.pushButton_ref_file.setText(QCoreApplication.translate("Form", u"...", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tabWidget_conf), QCoreApplication.translate("Form", u"Configuration", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tabWidget_hist), QCoreApplication.translate("Form", u"Histogram", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tabWidget_phasor), QCoreApplication.translate("Form", u"Phasor Plot", None))
        self.groupBox_9.setTitle(QCoreApplication.translate("Form", u"Image", None))
        self.groupBox_10.setTitle(QCoreApplication.translate("Form", u"Configure", None))
        self.label_suggest.setText(QCoreApplication.translate("Form", u".", None))
        self.pushButton_file_h5_input.setText(QCoreApplication.translate("Form", u"...", None))
        self.groupBox_11.setTitle(QCoreApplication.translate("Form", u"Color", None))
        self.comboBox_flim_tau.setItemText(0, QCoreApplication.translate("Form", u"Tau_m", None))
        self.comboBox_flim_tau.setItemText(1, QCoreApplication.translate("Form", u"Tau_phi", None))
        self.comboBox_flim_tau.setItemText(2, QCoreApplication.translate("Form", u"Tau_avg", None))
        self.comboBox_flim_tau.setItemText(3, QCoreApplication.translate("Form", u"Tau_diff", None))
        self.comboBox_flim_tau.setItemText(4, QCoreApplication.translate("Form", u"Tau_avg2", None))

        self.label_13.setText(QCoreApplication.translate("Form", u"Channel:", None))
        self.label_11.setText(QCoreApplication.translate("Form", u"Value:", None))
        self.comboBox_tau_channel.setItemText(0, QCoreApplication.translate("Form", u"Mean", None))
        self.comboBox_tau_channel.setItemText(1, QCoreApplication.translate("Form", u"0", None))
        self.comboBox_tau_channel.setItemText(2, QCoreApplication.translate("Form", u"1", None))
        self.comboBox_tau_channel.setItemText(3, QCoreApplication.translate("Form", u"2", None))
        self.comboBox_tau_channel.setItemText(4, QCoreApplication.translate("Form", u"3", None))
        self.comboBox_tau_channel.setItemText(5, QCoreApplication.translate("Form", u"4", None))
        self.comboBox_tau_channel.setItemText(6, QCoreApplication.translate("Form", u"5", None))
        self.comboBox_tau_channel.setItemText(7, QCoreApplication.translate("Form", u"6", None))
        self.comboBox_tau_channel.setItemText(8, QCoreApplication.translate("Form", u"7", None))
        self.comboBox_tau_channel.setItemText(9, QCoreApplication.translate("Form", u"8", None))
        self.comboBox_tau_channel.setItemText(10, QCoreApplication.translate("Form", u"9", None))
        self.comboBox_tau_channel.setItemText(11, QCoreApplication.translate("Form", u"10", None))
        self.comboBox_tau_channel.setItemText(12, QCoreApplication.translate("Form", u"11", None))
        self.comboBox_tau_channel.setItemText(13, QCoreApplication.translate("Form", u"12", None))
        self.comboBox_tau_channel.setItemText(14, QCoreApplication.translate("Form", u"13", None))
        self.comboBox_tau_channel.setItemText(15, QCoreApplication.translate("Form", u"14", None))
        self.comboBox_tau_channel.setItemText(16, QCoreApplication.translate("Form", u"15", None))
        self.comboBox_tau_channel.setItemText(17, QCoreApplication.translate("Form", u"16", None))
        self.comboBox_tau_channel.setItemText(18, QCoreApplication.translate("Form", u"17", None))
        self.comboBox_tau_channel.setItemText(19, QCoreApplication.translate("Form", u"18", None))
        self.comboBox_tau_channel.setItemText(20, QCoreApplication.translate("Form", u"19", None))
        self.comboBox_tau_channel.setItemText(21, QCoreApplication.translate("Form", u"20", None))
        self.comboBox_tau_channel.setItemText(22, QCoreApplication.translate("Form", u"21", None))
        self.comboBox_tau_channel.setItemText(23, QCoreApplication.translate("Form", u"22", None))
        self.comboBox_tau_channel.setItemText(24, QCoreApplication.translate("Form", u"23", None))
        self.comboBox_tau_channel.setItemText(25, QCoreApplication.translate("Form", u"24", None))

        self.label_16.setText(QCoreApplication.translate("Form", u"satFactor:", None))
        self.label_14.setText(QCoreApplication.translate("Form", u"outOfBoundsHue:", None))
        self.checkBox_flim_invertcolor.setText(QCoreApplication.translate("Form", u"InvertColorMap", None))
        self.label_8.setText(QCoreApplication.translate("Form", u"Min:", None))
        self.label_9.setText(QCoreApplication.translate("Form", u"ns         Max:", None))
        self.label_10.setText(QCoreApplication.translate("Form", u"ns", None))
        self.label_12.setText(QCoreApplication.translate("Form", u"H5 input file:", None))
        self.checkBox_hist_std_range.setText(QCoreApplication.translate("Form", u"Hist. Std. Range", None))
        self.pushButton_show_flim_hist.setText(QCoreApplication.translate("Form", u"Show Hist.", None))
        self.pushButton_show_flim_img.setText(QCoreApplication.translate("Form", u"Show FLIM", None))
        self.pushButton_flim_plot_phasors.setText(QCoreApplication.translate("Form", u"Show Phasor Plot", None))
        self.groupBox_12.setTitle(QCoreApplication.translate("Form", u"Intensity", None))
        self.comboBox_flim_intensity.setItemText(0, QCoreApplication.translate("Form", u"Sum", None))
        self.comboBox_flim_intensity.setItemText(1, QCoreApplication.translate("Form", u"0", None))
        self.comboBox_flim_intensity.setItemText(2, QCoreApplication.translate("Form", u"1", None))
        self.comboBox_flim_intensity.setItemText(3, QCoreApplication.translate("Form", u"2", None))
        self.comboBox_flim_intensity.setItemText(4, QCoreApplication.translate("Form", u"3", None))
        self.comboBox_flim_intensity.setItemText(5, QCoreApplication.translate("Form", u"4", None))
        self.comboBox_flim_intensity.setItemText(6, QCoreApplication.translate("Form", u"5", None))
        self.comboBox_flim_intensity.setItemText(7, QCoreApplication.translate("Form", u"6", None))
        self.comboBox_flim_intensity.setItemText(8, QCoreApplication.translate("Form", u"7", None))
        self.comboBox_flim_intensity.setItemText(9, QCoreApplication.translate("Form", u"8", None))
        self.comboBox_flim_intensity.setItemText(10, QCoreApplication.translate("Form", u"9", None))
        self.comboBox_flim_intensity.setItemText(11, QCoreApplication.translate("Form", u"10", None))
        self.comboBox_flim_intensity.setItemText(12, QCoreApplication.translate("Form", u"11", None))
        self.comboBox_flim_intensity.setItemText(13, QCoreApplication.translate("Form", u"12", None))
        self.comboBox_flim_intensity.setItemText(14, QCoreApplication.translate("Form", u"13", None))
        self.comboBox_flim_intensity.setItemText(15, QCoreApplication.translate("Form", u"14", None))
        self.comboBox_flim_intensity.setItemText(16, QCoreApplication.translate("Form", u"15", None))
        self.comboBox_flim_intensity.setItemText(17, QCoreApplication.translate("Form", u"16", None))
        self.comboBox_flim_intensity.setItemText(18, QCoreApplication.translate("Form", u"17", None))
        self.comboBox_flim_intensity.setItemText(19, QCoreApplication.translate("Form", u"18", None))
        self.comboBox_flim_intensity.setItemText(20, QCoreApplication.translate("Form", u"19", None))
        self.comboBox_flim_intensity.setItemText(21, QCoreApplication.translate("Form", u"20", None))
        self.comboBox_flim_intensity.setItemText(22, QCoreApplication.translate("Form", u"21", None))
        self.comboBox_flim_intensity.setItemText(23, QCoreApplication.translate("Form", u"22", None))
        self.comboBox_flim_intensity.setItemText(24, QCoreApplication.translate("Form", u"23", None))
        self.comboBox_flim_intensity.setItemText(25, QCoreApplication.translate("Form", u"24", None))
        self.comboBox_flim_intensity.setItemText(26, QCoreApplication.translate("Form", u"Uniform", None))

        self.label_15.setText(QCoreApplication.translate("Form", u"Channel:", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tabWidget_flim), QCoreApplication.translate("Form", u"FLIM", None))
        self.groupBox_6.setTitle(QCoreApplication.translate("Form", u"DFD", None))
        self.label_2.setText(QCoreApplication.translate("Form", u"Base Frequency", None))
        self.label_over.setText(QCoreApplication.translate("Form", u"g=0 s=0   m=0 phi=0    tau_phi=0 ns tau_m=0 ns", None))
        self.label_3.setText(QCoreApplication.translate("Form", u"MHz", None))
        self.label_4.setText(QCoreApplication.translate("Form", u"Position:", None))
    # retranslateUi

