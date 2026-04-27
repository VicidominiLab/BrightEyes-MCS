"""Qt Designer-style layout for the channel delay skew editor."""

from PySide6.QtCore import QCoreApplication, QMetaObject, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTableView,
    QVBoxLayout,
)


class Ui_Form(object):
    def setupUi(self, Form):
        if not Form.objectName():
            Form.setObjectName("Form")
        Form.resize(960, 720)

        self.gridLayout_2 = QGridLayout(Form)
        self.gridLayout_2.setObjectName("gridLayout_2")

        self.groupBox_configuration = QGroupBox(Form)
        self.groupBox_configuration.setObjectName("groupBox_configuration")
        self.gridLayout_3 = QGridLayout(self.groupBox_configuration)
        self.gridLayout_3.setObjectName("gridLayout_3")

        self.label_description = QLabel(self.groupBox_configuration)
        self.label_description.setObjectName("label_description")
        self.label_description.setWordWrap(True)
        self.gridLayout_3.addWidget(self.label_description, 0, 0, 1, 2)

        self.groupBox_reference = QGroupBox(self.groupBox_configuration)
        self.groupBox_reference.setObjectName("groupBox_reference")
        self.formLayout_reference = QFormLayout(self.groupBox_reference)
        self.formLayout_reference.setObjectName("formLayout_reference")

        self.label_active_mode = QLabel(self.groupBox_reference)
        self.label_active_mode.setObjectName("label_active_mode")
        self.formLayout_reference.setWidget(
            0, QFormLayout.LabelRole, self.label_active_mode
        )

        self.label_active_mode_value = QLabel(self.groupBox_reference)
        self.label_active_mode_value.setObjectName("label_active_mode_value")
        self.formLayout_reference.setWidget(
            0, QFormLayout.FieldRole, self.label_active_mode_value
        )

        self.label_reference_source = QLabel(self.groupBox_reference)
        self.label_reference_source.setObjectName("label_reference_source")
        self.formLayout_reference.setWidget(
            1, QFormLayout.LabelRole, self.label_reference_source
        )

        self.comboBox_reference_source = QComboBox(self.groupBox_reference)
        self.comboBox_reference_source.setObjectName("comboBox_reference_source")
        self.formLayout_reference.setWidget(
            1, QFormLayout.FieldRole, self.comboBox_reference_source
        )

        self.label_reference_channel = QLabel(self.groupBox_reference)
        self.label_reference_channel.setObjectName("label_reference_channel")
        self.formLayout_reference.setWidget(
            2, QFormLayout.LabelRole, self.label_reference_channel
        )

        self.spinBox_reference_channel = QSpinBox(self.groupBox_reference)
        self.spinBox_reference_channel.setObjectName("spinBox_reference_channel")
        self.formLayout_reference.setWidget(
            2, QFormLayout.FieldRole, self.spinBox_reference_channel
        )

        self.label_data_file = QLabel(self.groupBox_reference)
        self.label_data_file.setObjectName("label_data_file")
        self.formLayout_reference.setWidget(
            3, QFormLayout.LabelRole, self.label_data_file
        )

        self.lineEdit_data_file = QLineEdit(self.groupBox_reference)
        self.lineEdit_data_file.setObjectName("lineEdit_data_file")
        self.lineEdit_data_file.setPlaceholderText(
            QCoreApplication.translate("Form", "Enter data filename", None)
        )
        self.formLayout_reference.setWidget(
            3, QFormLayout.FieldRole, self.lineEdit_data_file
        )

        self.gridLayout_3.addWidget(self.groupBox_reference, 1, 0, 1, 1)

        self.groupBox_actions = QGroupBox(self.groupBox_configuration)
        self.groupBox_actions.setObjectName("groupBox_actions")
        self.verticalLayout_actions = QVBoxLayout(self.groupBox_actions)
        self.verticalLayout_actions.setObjectName("verticalLayout_actions")
        self.verticalLayout_actions.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout_actions.setAlignment(Qt.AlignTop)

        self.pushButton_reset = QPushButton(self.groupBox_actions)
        self.pushButton_reset.setObjectName("pushButton_reset")
        self.verticalLayout_actions.addWidget(self.pushButton_reset)

        self.pushButton_estimate = QPushButton(self.groupBox_actions)
        self.pushButton_estimate.setObjectName("pushButton_estimate")
        self.verticalLayout_actions.addWidget(self.pushButton_estimate)

        self.label_status = QLabel(self.groupBox_actions)
        self.label_status.setObjectName("label_status")
        self.label_status.setWordWrap(True)
        self.verticalLayout_actions.addWidget(self.label_status)

        self.line_separator = QFrame(self.groupBox_actions)
        self.line_separator.setObjectName("line_separator")
        self.line_separator.setFrameShape(QFrame.HLine)
        self.line_separator.setFrameShadow(QFrame.Sunken)
        self.verticalLayout_actions.addWidget(self.line_separator)

        self.horizontalLayout_spacer = QHBoxLayout()
        self.horizontalLayout_spacer.setObjectName("horizontalLayout_spacer")
        self.horizontalLayout_spacer.addStretch(1)
        self.verticalLayout_actions.addLayout(self.horizontalLayout_spacer)

        self.gridLayout_3.addWidget(self.groupBox_actions, 1, 1, 1, 1)
        self.gridLayout_3.setColumnStretch(0, 4)
        self.gridLayout_3.setColumnStretch(1, 1)
        self.gridLayout_3.setRowStretch(2, 1)

        self.tableView_skew = QTableView(self.groupBox_configuration)
        self.tableView_skew.setObjectName("tableView_skew")
        self.gridLayout_3.addWidget(self.tableView_skew, 2, 0, 1, 2)

        self.gridLayout_2.addWidget(self.groupBox_configuration, 0, 0, 1, 1)

        self.retranslateUi(Form)
        QMetaObject.connectSlotsByName(Form)

    def retranslateUi(self, Form):
        Form.setWindowTitle(
            QCoreApplication.translate(
                "Form", "Channel Delay Skew", None
            )
        )
        self.groupBox_configuration.setTitle(
            QCoreApplication.translate("Form", "Configuration", None)
        )
        self.label_description.setText(
            QCoreApplication.translate(
                "Form",
                "Editable table for the per-channel delay skew. Data rows keep both "
                "49-channel and 25-channel indexing, while the last two rows are "
                "reserved for data_channel_extra.",
                None,
            )
        )
        self.groupBox_reference.setTitle(
            QCoreApplication.translate("Form", "Reference Channel", None)
        )
        self.groupBox_actions.setTitle(
            QCoreApplication.translate("Form", "Actions", None)
        )
        self.label_active_mode.setText(
            QCoreApplication.translate("Form", "Active data mode", None)
        )
        self.label_active_mode_value.setText(
            QCoreApplication.translate("Form", "25 channels", None)
        )
        self.label_reference_source.setText(
            QCoreApplication.translate(
                "Form",
                "channel_used_for_reference_in_time_skew source",
                None,
            )
        )
        self.label_reference_channel.setText(
            QCoreApplication.translate(
                "Form",
                "channel_used_for_reference_in_time_skew index",
                None,
            )
        )
        self.label_data_file.setText(
            QCoreApplication.translate("Form", "Data filename", None)
        )
        self.pushButton_reset.setText(
            QCoreApplication.translate("Form", "Reset Delay Skew", None)
        )
        self.pushButton_estimate.setText(
            QCoreApplication.translate(
                "Form", "Estimate Channel Delay Skew", None
            )
        )
        self.label_status.setText(
            QCoreApplication.translate("Form", "Ready", None)
        )
