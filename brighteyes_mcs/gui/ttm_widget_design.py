# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'ttm_widget_design.ui'
##
## Created by: Qt User Interface Compiler version 5.15.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide2.QtCore import *
from PySide2.QtGui import *
from PySide2.QtWidgets import *


class Ui_Form(object):
    def setupUi(self, Form):
        if not Form.objectName():
            Form.setObjectName(u"Form")
        Form.resize(916, 690)
        self.gridLayout_2 = QGridLayout(Form)
        self.gridLayout_2.setObjectName(u"gridLayout_2")
        self.gridLayout = QGridLayout()
        self.gridLayout.setObjectName(u"gridLayout")
        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.gridLayout.addItem(self.verticalSpacer, 5, 0, 1, 1)

        self.label = QLabel(Form)
        self.label.setObjectName(u"label")

        self.gridLayout.addWidget(self.label, 3, 0, 1, 1)

        self.pushButton_stop = QPushButton(Form)
        self.pushButton_stop.setObjectName(u"pushButton_stop")

        self.gridLayout.addWidget(self.pushButton_stop, 1, 0, 1, 1)

        self.pushButton_start = QPushButton(Form)
        self.pushButton_start.setObjectName(u"pushButton_start")

        self.gridLayout.addWidget(self.pushButton_start, 0, 0, 1, 1)

        self.pushButton_update = QPushButton(Form)
        self.pushButton_update.setObjectName(u"pushButton_update")

        self.gridLayout.addWidget(self.pushButton_update, 2, 0, 1, 1)

        self.gridLayout_central = QGridLayout()
        self.gridLayout_central.setObjectName(u"gridLayout_central")

        self.gridLayout.addLayout(self.gridLayout_central, 1, 1, 5, 1)

        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.gridLayout.addItem(self.horizontalSpacer, 0, 1, 1, 1)

        self.doubleSpinBox_refresh = QDoubleSpinBox(Form)
        self.doubleSpinBox_refresh.setObjectName(u"doubleSpinBox_refresh")
        self.doubleSpinBox_refresh.setDecimals(3)
        self.doubleSpinBox_refresh.setValue(1.000000000000000)

        self.gridLayout.addWidget(self.doubleSpinBox_refresh, 4, 0, 1, 1)

        self.plainTextEdit_debug = QPlainTextEdit(Form)
        self.plainTextEdit_debug.setObjectName(u"plainTextEdit_debug")

        self.gridLayout.addWidget(self.plainTextEdit_debug, 6, 1, 1, 1)


        self.gridLayout_2.addLayout(self.gridLayout, 0, 0, 1, 1)


        self.retranslateUi(Form)

        QMetaObject.connectSlotsByName(Form)
    # setupUi

    def retranslateUi(self, Form):
        Form.setWindowTitle(QCoreApplication.translate("Form", u"Form", None))
        self.label.setText(QCoreApplication.translate("Form", u"Autorefresh", None))
        self.pushButton_stop.setText(QCoreApplication.translate("Form", u"Stop", None))
        self.pushButton_start.setText(QCoreApplication.translate("Form", u"Start", None))
        self.pushButton_update.setText(QCoreApplication.translate("Form", u"Update Preview Image", None))
    # retranslateUi

