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
        Form.resize(692, 375)
        self.gridLayout = QGridLayout(Form)
        self.gridLayout.setObjectName("gridLayout")
        self.pushButton_cmd6 = QPushButton(Form)
        self.pushButton_cmd6.setObjectName("pushButton_cmd6")

        self.gridLayout.addWidget(self.pushButton_cmd6, 3, 6, 1, 1)

        self.pushButton_cmd3 = QPushButton(Form)
        self.pushButton_cmd3.setObjectName("pushButton_cmd3")

        self.gridLayout.addWidget(self.pushButton_cmd3, 3, 3, 1, 1)

        self.pushButton_cmd1 = QPushButton(Form)
        self.pushButton_cmd1.setObjectName("pushButton_cmd1")

        self.gridLayout.addWidget(self.pushButton_cmd1, 3, 1, 1, 1)

        self.pushButton_fileBrowser = QPushButton(Form)
        self.pushButton_fileBrowser.setObjectName("pushButton_fileBrowser")

        self.gridLayout.addWidget(self.pushButton_fileBrowser, 1, 8, 1, 1)

        self.gridLayout_placeholder = QGridLayout()
        self.gridLayout_placeholder.setObjectName("gridLayout_placeholder")

        self.gridLayout.addLayout(self.gridLayout_placeholder, 5, 0, 1, 9)

        self.pushButton_cmd4 = QPushButton(Form)
        self.pushButton_cmd4.setObjectName("pushButton_cmd4")

        self.gridLayout.addWidget(self.pushButton_cmd4, 3, 4, 1, 1)

        self.label = QLabel(Form)
        self.label.setObjectName("label")

        self.gridLayout.addWidget(self.label, 1, 0, 1, 1)

        self.pushButton_cmd5 = QPushButton(Form)
        self.pushButton_cmd5.setObjectName("pushButton_cmd5")

        self.gridLayout.addWidget(self.pushButton_cmd5, 3, 5, 1, 1)

        self.pushButton_cmd2 = QPushButton(Form)
        self.pushButton_cmd2.setObjectName("pushButton_cmd2")

        self.gridLayout.addWidget(self.pushButton_cmd2, 3, 2, 1, 1)

        self.lineEdit = QLineEdit(Form)
        self.lineEdit.setObjectName("lineEdit")

        self.gridLayout.addWidget(self.lineEdit, 1, 1, 1, 7)

        self.comboBox_script = QComboBox(Form)
        self.comboBox_script.setObjectName("comboBox_script")

        self.gridLayout.addWidget(self.comboBox_script, 2, 1, 1, 7)

        self.pushButton_cmdLoad = QPushButton(Form)
        self.pushButton_cmdLoad.setObjectName("pushButton_cmdLoad")

        self.gridLayout.addWidget(self.pushButton_cmdLoad, 2, 8, 1, 1)

        self.label_2 = QLabel(Form)
        self.label_2.setObjectName("label_2")

        self.gridLayout.addWidget(self.label_2, 2, 0, 1, 1)

        self.checkBox_autorun = QCheckBox(Form)
        self.checkBox_autorun.setObjectName("checkBox_autorun")

        self.gridLayout.addWidget(self.checkBox_autorun, 3, 8, 1, 1)

        self.retranslateUi(Form)

        QMetaObject.connectSlotsByName(Form)

    # setupUi

    def retranslateUi(self, Form):
        Form.setWindowTitle(QCoreApplication.translate("Form", "Form", None))
        self.pushButton_cmd6.setText(QCoreApplication.translate("Form", "Cmd6", None))
        self.pushButton_cmd3.setText(QCoreApplication.translate("Form", "Cmd3", None))
        self.pushButton_cmd1.setText(QCoreApplication.translate("Form", "Cmd1", None))
        self.pushButton_fileBrowser.setText(
            QCoreApplication.translate("Form", "...", None)
        )
        self.pushButton_cmd4.setText(QCoreApplication.translate("Form", "Cmd4", None))
        self.label.setText(QCoreApplication.translate("Form", "File HDF5:", None))
        self.pushButton_cmd5.setText(QCoreApplication.translate("Form", "Cmd5", None))
        self.pushButton_cmd2.setText(QCoreApplication.translate("Form", "Cmd2", None))
        self.pushButton_cmdLoad.setText(
            QCoreApplication.translate("Form", "Load", None)
        )
        self.label_2.setText(QCoreApplication.translate("Form", "Script:", None))
        self.checkBox_autorun.setText(
            QCoreApplication.translate("Form", "Autorun", None)
        )

    # retranslateUi
