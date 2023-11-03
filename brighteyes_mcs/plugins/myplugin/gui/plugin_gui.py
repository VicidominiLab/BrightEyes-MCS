# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'plugin_gui.ui'
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
            Form.setObjectName("Form")
        Form.resize(661, 300)
        self.gridLayout = QGridLayout(Form)
        self.gridLayout.setObjectName("gridLayout")
        self.pushButton = QPushButton(Form)
        self.pushButton.setObjectName("pushButton")

        self.gridLayout.addWidget(self.pushButton, 0, 0, 1, 1)

        self.pushButton_2 = QPushButton(Form)
        self.pushButton_2.setObjectName("pushButton_2")

        self.gridLayout.addWidget(self.pushButton_2, 0, 1, 1, 1)

        self.listView = QListView(Form)
        self.listView.setObjectName("listView")

        self.gridLayout.addWidget(self.listView, 1, 0, 1, 2)

        self.retranslateUi(Form)

        QMetaObject.connectSlotsByName(Form)

    # setupUi

    def retranslateUi(self, Form):
        Form.setWindowTitle(QCoreApplication.translate("Form", "Form", None))
        self.pushButton.setText(QCoreApplication.translate("Form", "PushButton", None))
        self.pushButton_2.setText(
            QCoreApplication.translate("Form", "PushButton", None)
        )

    # retranslateUi
