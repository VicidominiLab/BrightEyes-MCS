"""Widget for editing the channel delay skew table."""

import traceback

from PySide6.QtCore import QAbstractTableModel, QObject, QRunnable, Qt, QThreadPool, Signal, Slot
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QMessageBox, QWidget

import h5py
import numpy as np

from . import channel_delay_skew_widget_design
from . import channel_delay_skew_extractor


TWENTY_FIVE_TO_FORTY_NINE = np.array(
    [(row + 1) * 7 + (col + 1) for row in range(5) for col in range(5)],
    dtype=int,
)


class ChannelDelaySkewWidget(QWidget, channel_delay_skew_widget_design.Ui_Form):
    CONFIG_KEY = "channel_delay_skew"
    DATA_CHANNELS_49 = 49
    DATA_CHANNELS_25 = 25
    EXTRA_CHANNELS = 2
    DEFAULT_REFERENCE_DATA_INDEX_49 = 24

    def __init__(self, main_window=None, channels=25):
        super().__init__()
        self.setupUi(self)

        self.main_window = main_window
        self.channels = channels
        self.threadpool = QThreadPool()
        self.analysis_lock = False
        self.analysis_worker = None

        conf = self._load_configuration()

        self.reference_source = conf["reference_source"]
        self.reference_data_index_49 = conf["reference_data_index_49"]
        self.reference_data_channel_extra_index = conf[
            "reference_data_channel_extra_index"
        ]

        self.comboBox_reference_source.addItems(["data", "data_channel_extra"])
        self.comboBox_reference_source.currentTextChanged.connect(
            self.reference_source_changed
        )
        self.spinBox_reference_channel.setMinimum(0)
        self.spinBox_reference_channel.valueChanged.connect(
            self.reference_channel_changed
        )
        self.pushButton_reset.clicked.connect(self.pushButton_reset_clicked)
        self.pushButton_estimate.clicked.connect(self.pushButton_estimate_clicked)
    

        if self.main_window is not None:
            try:
                self.main_window.ui.comboBox_channels.currentTextChanged.connect(
                    self.channel_mode_changed
                )
            except Exception:
                pass

        self.table_skew = SkewTableModel(data=conf["table_skew"])
        self.table_skew.data_changed_call = self.UpdateConf

        self.tableView_skew.setModel(self.table_skew)
        self.tableView_skew.horizontalHeader().setFont(QFont("Helvetica", 8))
        self.tableView_skew.verticalHeader().setFont(QFont("Helvetica", 8))
        self.tableView_skew.setFont(QFont("Helvetica", 8))
        self.tableView_skew.resizeColumnsToContents()
        self.tableView_skew.resizeRowsToContents()

        self.label_status.setText("Ready")
        self.refresh_reference_controls()
        self.UpdateConf()

    def _default_table(self):
        table = np.full(
            (self.DATA_CHANNELS_49 + self.EXTRA_CHANNELS, 4), np.nan, dtype=float
        )
        table[: self.DATA_CHANNELS_49, 0] = np.arange(self.DATA_CHANNELS_49)
        table[TWENTY_FIVE_TO_FORTY_NINE, 1] = np.arange(self.DATA_CHANNELS_25)
        table[:, 2] = 0.0
        table[:, 3] = np.nan
        return table

    def _normalize_table(self, table):
        normalized = self._default_table()
        if table is None:
            return normalized

        table = np.asarray(table, dtype=float)
        if table.ndim != 2:
            return normalized

        row_count = min(table.shape[0], normalized.shape[0])
        if table.shape[1] >= 3:
            normalized[:row_count, 2] = table[:row_count, 2]
        elif table.shape[1] >= 1:
            normalized[:row_count, 2] = table[:row_count, 0]
        if table.shape[1] >= 4:
            normalized[:row_count, 3] = table[:row_count, 3]
        return normalized

    def _legacy_configuration_to_table(self, configuration):
        table = self._default_table()

        data = np.asarray(configuration.get("data", []), dtype=float).reshape(-1)
        data_extra = np.asarray(
            configuration.get("data_channel_extra", []), dtype=float
        ).reshape(-1)

        table[: min(data.size, self.DATA_CHANNELS_49), 2] = data[
            : self.DATA_CHANNELS_49
        ]
        table[
            self.DATA_CHANNELS_49 : self.DATA_CHANNELS_49
            + min(data_extra.size, self.EXTRA_CHANNELS),
            2,
        ] = data_extra[: self.EXTRA_CHANNELS]
        return table

    def _load_configuration(self):
        configuration = {}

        try:
            stored_configuration = self.main_window.plugin_configuration[
                self.CONFIG_KEY
            ]
        except Exception:
            stored_configuration = {}

        if "table_skew" in stored_configuration:
            configuration["table_skew"] = self._normalize_table(
                stored_configuration["table_skew"]
            )
        elif ("data" in stored_configuration) or (
            "data_channel_extra" in stored_configuration
        ):
            configuration["table_skew"] = self._legacy_configuration_to_table(
                stored_configuration
            )
        else:
            configuration["table_skew"] = self._default_table()

        reference_source = stored_configuration.get("reference_source", "data")
        if reference_source not in ("data", "data_channel_extra"):
            reference_source = "data"
        configuration["reference_source"] = reference_source

        configuration["reference_data_index_49"] = int(
            np.clip(
                stored_configuration.get(
                    "reference_data_index_49",
                    self.DEFAULT_REFERENCE_DATA_INDEX_49,
                ),
                0,
                self.DATA_CHANNELS_49 - 1,
            )
        )
        configuration["reference_data_channel_extra_index"] = int(
            np.clip(
                stored_configuration.get(
                    "reference_data_channel_extra_index",
                    0,
                ),
                0,
                self.EXTRA_CHANNELS - 1,
            )
        )
        return configuration

    def get_current_channel_count(self):
        try:
            current_channels = int(self.main_window.ui.comboBox_channels.currentText())
        except Exception:
            try:
                current_channels = int(self.main_window.CHANNELS)
            except Exception:
                current_channels = int(self.channels)

        if current_channels not in (self.DATA_CHANNELS_25, self.DATA_CHANNELS_49):
            current_channels = self.DATA_CHANNELS_25
        return current_channels

    def map_49_to_25(self, channel_49):
        channel_49 = int(channel_49)
        matches = np.where(TWENTY_FIVE_TO_FORTY_NINE == channel_49)[0]
        if matches.size == 0:
            return None
        return int(matches[0])

    def map_25_to_49(self, channel_25):
        return int(TWENTY_FIVE_TO_FORTY_NINE[int(channel_25)])

    def refresh_reference_controls(self):
        current_channels = self.get_current_channel_count()
        self.label_active_mode_value.setText("%d channels" % current_channels)

        if (
            self.reference_source == "data"
            and current_channels == self.DATA_CHANNELS_25
            and self.map_49_to_25(self.reference_data_index_49) is None
        ):
            self.reference_data_index_49 = self.DEFAULT_REFERENCE_DATA_INDEX_49

        self.comboBox_reference_source.blockSignals(True)
        self.spinBox_reference_channel.blockSignals(True)

        self.comboBox_reference_source.setCurrentText(self.reference_source)

        if self.reference_source == "data":
            self.spinBox_reference_channel.setMaximum(current_channels - 1)
            if current_channels == self.DATA_CHANNELS_25:
                displayed_index = self.map_49_to_25(self.reference_data_index_49)
            else:
                displayed_index = self.reference_data_index_49
            self.spinBox_reference_channel.setValue(int(displayed_index))
        else:
            self.spinBox_reference_channel.setMaximum(self.EXTRA_CHANNELS - 1)
            self.spinBox_reference_channel.setValue(
                int(self.reference_data_channel_extra_index)
            )

        self.comboBox_reference_source.blockSignals(False)
        self.spinBox_reference_channel.blockSignals(False)

    def _resolve_dataset_name(self, h5_file, source_name):
        if source_name == "data":
            candidates = ["data"]
        else:
            candidates = ["data_channel_extra", "data_channels_extra"]

        for candidate in candidates:
            if candidate in h5_file:
                return candidate

        raise KeyError("Dataset not found for source %s" % source_name)

    def _dataset_to_histogram_matrix(self, dataset):
        data = np.asarray(dataset, dtype=float)
        if data.ndim < 2:
            raise ValueError("Dataset must have at least 2 dimensions")
        if data.ndim == 2:
            return data

        return data.sum(axis=tuple(range(data.ndim - 2)))

    def _row_indices_for_estimate(self, source_name, channel_count):
        if source_name == "data":
            if channel_count == self.DATA_CHANNELS_49:
                return np.arange(self.DATA_CHANNELS_49, dtype=int)
            if channel_count == self.DATA_CHANNELS_25:
                return np.array(TWENTY_FIVE_TO_FORTY_NINE, dtype=int)
            raise ValueError("Unsupported data channel count: %d" % channel_count)

        if channel_count != self.EXTRA_CHANNELS:
            raise ValueError(
                "data_channel_extra must contain %d channels, got %d"
                % (self.EXTRA_CHANNELS, channel_count)
            )
        return np.arange(
            self.DATA_CHANNELS_49,
            self.DATA_CHANNELS_49 + self.EXTRA_CHANNELS,
            dtype=int,
        )

    def _apply_estimated_values_to_table(self, source_name, channel_count, delay, error):
        table = self.get_delay_skew_table_numpy()
        row_indices = self._row_indices_for_estimate(source_name, channel_count)
        table[row_indices, 2] = np.asarray(delay, dtype=float)
        table[row_indices, 3] = np.asarray(error, dtype=float)
        normalized_table = self._normalize_table(table)
        self.table_skew.set_data(normalized_table)
        self.UpdateTable()
        self.tableView_skew.viewport().update()

    def _set_analysis_running(self, running):
        self.analysis_lock = running
        self.pushButton_estimate.setEnabled(not running)

    def _estimate_skew_job(self, filename, source_name, reference_channel):
        with h5py.File(filename, "r") as hf:
            dataset_name = self._resolve_dataset_name(hf, source_name)
            data_hist = self._dataset_to_histogram_matrix(hf[dataset_name][:])

        channel_count = int(data_hist.shape[1])
        resolved_reference = int(reference_channel)

        delay, delay_errs, _meta = channel_delay_skew_extractor.estimate_channel_skew(
            data_hist=data_hist,
            reference_hist=None,
            reference_channel=resolved_reference,
            upsampling=10,
            apodize=False,
        )
        return source_name, channel_count, delay, delay_errs

    def UpdateConf(self):
        table_skew = self.table_skew.get_data()
        reference_used = self.get_reference_channel_used_for_time_skew()

        if self.main_window is not None:
            if self.CONFIG_KEY not in self.main_window.plugin_configuration.keys():
                self.main_window.plugin_configuration[self.CONFIG_KEY] = {}

            self.main_window.plugin_configuration[self.CONFIG_KEY] = {
                "table_skew": table_skew,
                "reference_source": self.reference_source,
                "reference_data_index_49": self.reference_data_index_49,
                "reference_data_channel_extra_index": self.reference_data_channel_extra_index,
                "channel_used_for_reference_in_time_skew": reference_used["index"],
                "channel_used_for_reference_in_time_skew_source": reference_used[
                    "source"
                ],
            }

    def UpdateTable(self):
        self.table_skew.set_data(
            self._normalize_table(
                self.main_window.plugin_configuration[self.CONFIG_KEY]["table_skew"]
            )
        )
        self.tableView_skew.resizeColumnsToContents()
        self.tableView_skew.resizeRowsToContents()

    @Slot()
    def pushButton_reset_clicked(self):
        table = self._default_table()
        self.table_skew.set_data(table)
        self.tableView_skew.resizeColumnsToContents()
        self.tableView_skew.resizeRowsToContents()

    @Slot()
    def pushButton_estimate_clicked(self):
        filename = self.lineEdit_data_file.text().strip()
        if filename == "":
            self.label_status.setText("Ready")
            QMessageBox.warning(self, "Channel Delay Skew", "Select a data filename first.")
            return

        if self.analysis_lock:
            return

        try:
            reference_channel = self.get_reference_channel_used_for_time_skew()["index"]
            self.label_status.setText("Wait Analysis on-going")
            self._set_analysis_running(True)
            worker = ChannelDelaySkewAnalysisWorker(
                self._estimate_skew_job,
                filename,
                self.reference_source,
                reference_channel,
            )
            self.analysis_worker = worker
            worker.signals.result.connect(self._estimate_finished)
            worker.signals.error.connect(self._estimate_failed)
            worker.signals.finished.connect(self._estimate_cleanup)
            self.threadpool.start(worker)
        except Exception as error:
            self._set_analysis_running(False)
            self.label_status.setText("Ready")
            QMessageBox.critical(
                self,
                "Channel Delay Skew",
                "Unable to estimate channel delay skew:\n%s" % error,
            )

    @Slot(object)
    def _estimate_finished(self, result):
        source_name, channel_count, delay, delay_errs = result
        self._apply_estimated_values_to_table(
            source_name,
            channel_count,
            delay,
            delay_errs,
        )
        self.label_status.setText("Done")

    @Slot(str)
    def _estimate_failed(self, error):
        self.label_status.setText("Ready")
        QMessageBox.critical(
            self,
            "Channel Delay Skew",
            "Unable to estimate channel delay skew:\n%s" % error,
        )

    @Slot()
    def _estimate_cleanup(self):
        self.analysis_worker = None
        self._set_analysis_running(False)
            
    @Slot(str)
    def reference_source_changed(self, value):
        self.reference_source = value
        self.refresh_reference_controls()
        self.UpdateConf()

    @Slot(int)
    def reference_channel_changed(self, value):
        if self.reference_source == "data":
            if self.get_current_channel_count() == self.DATA_CHANNELS_25:
                self.reference_data_index_49 = self.map_25_to_49(value)
            else:
                self.reference_data_index_49 = int(value)
        else:
            self.reference_data_channel_extra_index = int(value)

        self.UpdateConf()

    @Slot(str)
    def channel_mode_changed(self, _value):
        self.refresh_reference_controls()
        self.UpdateConf()

    def get_delay_skew_table(self):
        return self.table_skew.get_data()

    def get_delay_skew_table_numpy(self):
        return np.array(self.table_skew.get_data(), dtype=float)

    def get_channel_delay_skew_array(self, channels=None):
        if channels is None:
            channels = self.get_current_channel_count()

        values = self.table_skew.get_data()[: self.DATA_CHANNELS_49, 2]

        if int(channels) == self.DATA_CHANNELS_49:
            return np.array(values, dtype=float)
        if int(channels) == self.DATA_CHANNELS_25:
            return np.array(values[TWENTY_FIVE_TO_FORTY_NINE], dtype=float)
        raise ValueError("channels must be 25 or 49")

    def get_channel_delay_skew_error_array(self, channels=None):
        if channels is None:
            channels = self.get_current_channel_count()

        values = self.table_skew.get_data()[: self.DATA_CHANNELS_49, 3]

        if int(channels) == self.DATA_CHANNELS_49:
            return np.array(values, dtype=float)
        if int(channels) == self.DATA_CHANNELS_25:
            return np.array(values[TWENTY_FIVE_TO_FORTY_NINE], dtype=float)
        raise ValueError("channels must be 25 or 49")

    def get_data_channel_extra_delay_skew_array(self):
        return np.array(
            self.table_skew.get_data()[
                self.DATA_CHANNELS_49 : self.DATA_CHANNELS_49 + self.EXTRA_CHANNELS,
                2,
            ],
            dtype=float,
        )

    def get_data_channel_extra_delay_skew_error_array(self):
        return np.array(
            self.table_skew.get_data()[
                self.DATA_CHANNELS_49 : self.DATA_CHANNELS_49 + self.EXTRA_CHANNELS,
                3,
            ],
            dtype=float,
        )

    def get_reference_channel_used_for_time_skew(self, channels=None):
        if channels is None:
            channels = self.get_current_channel_count()

        if self.reference_source == "data":
            if int(channels) == self.DATA_CHANNELS_49:
                return {"source": "data", "index": int(self.reference_data_index_49)}
            if int(channels) == self.DATA_CHANNELS_25:
                channel_25 = self.map_49_to_25(self.reference_data_index_49)
                if channel_25 is None:
                    raise ValueError(
                        "The selected reference data channel is not available in 25-channel mode."
                    )
                return {"source": "data", "index": int(channel_25)}
            raise ValueError("channels must be 25 or 49")

        return {
            "source": "data_channel_extra",
            "index": int(self.reference_data_channel_extra_index),
        }
    
    def acquisitionDone(self,t):
        self.lineEdit_data_file.setText(t)
        

class SkewTableModel(QAbstractTableModel):
    def __init__(self, data):
        super().__init__()
        self._data = np.asarray(data, dtype=float)
        self.data_changed_call = None

    def rowCount(self, index):
        return self._data.shape[0]

    def columnCount(self, index):
        return self._data.shape[1]

    def data(self, index, role=Qt.DisplayRole):
        if index.isValid():
            if role == Qt.DisplayRole or role == Qt.EditRole:
                value = self._data[index.row(), index.column()]

                if np.isnan(value):
                    return ""
                if index.column() < 2:
                    return str(int(value))
                return "%.6e" % value

    def get_data(self):
        return self._data

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return super().headerData(section, orientation, role)

        if orientation == Qt.Horizontal:
            if section == 0:
                return "49-ch index"
            if section == 1:
                return "25-ch index"
            if section == 2:
                return "Delay skew"
            if section == 3:
                return "Error"

        if orientation == Qt.Vertical:
            if section < 49:
                return "data[%d]" % section
            return "data_channel_extra[%d]" % (section - 49)

        return super().headerData(section, orientation, role)

    def setData(self, index, value, role):
        if role == Qt.EditRole and index.column() in (2, 3):
            try:
                value = float(value)
            except ValueError:
                return False

            self._data[index.row(), index.column()] = value
            if self.data_changed_call is not None:
                self.data_changed_call()
            self.dataChanged.emit(index, index, [role])
            return True
        return False

    def set_data(self, data):
        self.beginResetModel()
        self._data = np.asarray(data, dtype=float)
        self.endResetModel()
        if self.data_changed_call is not None:
            self.data_changed_call()
        return True

    def flags(self, index):
        if index.column() in (2, 3):
            return Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable
        return Qt.ItemIsSelectable | Qt.ItemIsEnabled


class ChannelDelaySkewAnalysisWorkerSignals(QObject):
    result = Signal(object)
    error = Signal(str)
    finished = Signal()


class ChannelDelaySkewAnalysisWorker(QRunnable):
    def __init__(self, fn, *args):
        super().__init__()
        self.fn = fn
        self.args = args
        self.signals = ChannelDelaySkewAnalysisWorkerSignals()

    @Slot()
    def run(self):
        try:
            result = self.fn(*self.args)
            self.signals.result.emit(result)
        except Exception:
            self.signals.error.emit(traceback.format_exc())
        finally:
            self.signals.finished.emit()
