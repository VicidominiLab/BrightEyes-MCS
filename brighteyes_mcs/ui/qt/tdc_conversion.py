"""Batch pSPAD TDC RAW conversion with background work and per-file results."""
from pathlib import Path
import threading

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QDialog, QDoubleSpinBox,
    QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QSpinBox, QTableWidget,
    QTableWidgetItem, QVBoxLayout)

from ...storage.converters.pispad23 import (ConversionCancelled, convert_tdc_raw,
                                           tdc_output_paths)
from ...storage.tdc_metadata import ScanGeometry, find_metadata


class ConversionWorker(QThread):
    progress = Signal(int, str)
    result = Signal(int, bool, str)
    completed = Signal(object)

    def __init__(self, jobs, formats, directory=None, geometry=None, parent=None):
        super().__init__(parent)
        self.jobs, self.formats = jobs, tuple(formats)
        self.directory, self.geometry = directory, geometry
        self.cancel_event = threading.Event()

    def run(self):
        successes = failures = 0
        for index, (raw, metadata) in enumerate(self.jobs):
            if self.cancel_event.is_set():
                break
            paths = tdc_output_paths(raw, self.directory)
            self.progress.emit(int(100 * index / len(self.jobs)), f"Converting {Path(raw).name}")
            try:
                outputs = convert_tdc_raw(raw,
                    tdc_output=paths["tdc"] if "tdc" in self.formats else None,
                    intensity_output=paths["intensity"] if "intensity" in self.formats else None,
                    metadata=metadata, geometry=self.geometry, cancel_event=self.cancel_event,
                    progress_callback=lambda value, message: self.progress.emit(
                        int(100 * (index + value / 100) / len(self.jobs)), message))
                message = "Saved: " + ", ".join(str(p) for p in outputs)
                import h5py
                with h5py.File(outputs[0]) as file:
                    has_metadata = file["conversion"].attrs["acquisition_metadata_available"]
                if not has_metadata:
                    message += " (no acquisition metadata available)"
                if "intensity" in self.formats:
                    with h5py.File(paths["intensity"]) as file:
                        if not file["pispad23_microimages"].attrs["complete"]:
                            message += " — incomplete intensity frames; see validity flags"
                self.result.emit(index, True, message)
                successes += 1
            except ConversionCancelled:
                self.result.emit(index, False, "Cancelled; no output published for this file")
                break
            except Exception as error:
                failures += 1
                self.result.emit(index, False, str(error))
        self.completed.emit(dict(successes=successes, failures=failures,
                                 cancelled=self.cancel_event.is_set()))


class TdcConversionDialog(QDialog):
    def __init__(self, parent=None, *, initial_folder="", geometry=None):
        super().__init__(parent)
        self.setWindowTitle("Convert pSPAD TDC RAW files")
        self.resize(850, 650)
        self.initial_folder = initial_folder
        self.jobs = []
        self.worker = None
        layout = QVBoxLayout(self)
        introduction = QLabel("Convert one or more pSPAD TDC RAW recordings. Existing files are never overwritten.")
        introduction.setWordWrap(True)
        layout.addWidget(introduction)
        self.table = QTableWidget(0, 3, self)
        self.table.setHorizontalHeaderLabels(["TDC RAW file", "Acquisition metadata", "Result"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)
        buttons = QHBoxLayout()
        self.add_button = QPushButton("Add RAW files…")
        self.remove_button = QPushButton("Remove selected")
        self.metadata_button = QPushButton("Choose metadata for selected…")
        for button in (self.add_button, self.remove_button, self.metadata_button):
            buttons.addWidget(button)
        layout.addLayout(buttons)
        self.add_button.clicked.connect(self.select_files)
        self.remove_button.clicked.connect(self.remove_selected)
        self.metadata_button.clicked.connect(self.select_metadata)
        options = QHBoxLayout()
        self.tdc = QCheckBox("TDC HDF5 (events)")
        self.intensity = QCheckBox("Intensity HDF5 (MCS)")
        self.tdc.setChecked(True)
        self.intensity.setChecked(True)
        options.addWidget(self.tdc)
        options.addWidget(self.intensity)
        layout.addLayout(options)
        output = QHBoxLayout()
        output.addWidget(QLabel("Output folder"))
        self.directory = QLineEdit()
        self.directory.setPlaceholderText("Empty: next to each RAW file")
        self.folder_button = QPushButton("Browse…")
        self.folder_button.clicked.connect(self.select_directory)
        output.addWidget(self.directory)
        output.addWidget(self.folder_button)
        layout.addLayout(output)
        metadata_help = QLabel("Metadata is detected per file. Choose a companion HDF5 file if it is stored elsewhere.\n"
            "Intensity reconstruction needs the original scan settings; fallback values are used only when enabled below.")
        metadata_help.setWordWrap(True)
        layout.addWidget(metadata_help)
        self.fallback = QGroupBox("Use fallback scan settings when metadata lacks them")
        self.fallback.setCheckable(True)
        form = QFormLayout(self.fallback)
        geometry = geometry or ScanGeometry(200, 200, 1, 1, 1e-6)
        self.fields = {}
        for fields in ((("width", "Width"), ("height", "Height")),
                       (("frames", "Frames / repetition"), ("repetitions", "Repetitions"))):
            row = QHBoxLayout()
            for name, label in fields:
                field = QSpinBox()
                field.setRange(1, 1_000_000)
                field.setValue(getattr(geometry, name))
                self.fields[name] = field
                row.addWidget(QLabel(label))
                row.addWidget(field)
            form.addRow(row)
        timing = QHBoxLayout()
        self.dwell = QDoubleSpinBox()
        self.dwell.setDecimals(6)
        self.dwell.setRange(0.000001, 1e12)
        self.dwell.setValue(geometry.dwell_seconds * 1e6)
        self.dwell.setSuffix(" µs / dwell")
        self.snake = QCheckBox("XY snake")
        self.snake_z = QCheckBox("Z snake")
        self.snake.setChecked(geometry.snake)
        self.snake_z.setChecked(geometry.snake_z)
        for widget in (self.dwell, self.snake, self.snake_z):
            timing.addWidget(widget)
        form.addRow(timing)
        self.fallback.setChecked(False)
        layout.addWidget(self.fallback)
        self.progress = QProgressBar()
        self.status = QLabel("Select TDC RAW files to begin.")
        self.status.setWordWrap(True)
        layout.addWidget(self.progress)
        layout.addWidget(self.status)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(2000)
        layout.addWidget(self.log)
        actions = QHBoxLayout()
        self.start_button = QPushButton("Convert selected formats")
        self.cancel_button = QPushButton("Cancel conversion")
        self.cancel_button.setEnabled(False)
        self.close_button = QPushButton("Close")
        self.start_button.clicked.connect(self.start_conversion)
        self.cancel_button.clicked.connect(self.cancel_conversion)
        self.close_button.clicked.connect(self.reject)
        for button in (self.start_button, self.cancel_button, self.close_button):
            actions.addWidget(button)
        layout.addLayout(actions)

    def add_files(self, paths):
        for path in paths:
            raw = Path(path).resolve()
            if any(raw == job[0] for job in self.jobs):
                continue
            metadata = find_metadata(raw)
            self.jobs.append((raw, metadata))
            row = self.table.rowCount()
            self.table.insertRow(row)
            for column, text in enumerate((raw.name, metadata.name if metadata else "Not found", "Ready")):
                self.table.setItem(row, column, QTableWidgetItem(text))
            self.table.item(row, 0).setToolTip(str(raw))
            self.table.item(row, 1).setToolTip(str(metadata) if metadata else "Choose metadata or explicitly enable fallback scan settings")

    def select_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Select pSPAD TDC RAW recordings",
                                               self.initial_folder, "pSPAD TDC RAW (*.raw)")
        self.add_files(paths)

    def remove_selected(self):
        for row in sorted({item.row() for item in self.table.selectedItems()}, reverse=True):
            self.table.removeRow(row)
            del self.jobs[row]

    def select_metadata(self):
        rows = sorted({item.row() for item in self.table.selectedItems()})
        if not rows:
            return
        path, _ = QFileDialog.getOpenFileName(self, "Select companion acquisition metadata",
                                             str(self.jobs[rows[0]][0].parent), "HDF5 metadata (*.h5 *.hdf5)")
        if path:
            for row in rows:
                self.jobs[row] = (self.jobs[row][0], Path(path).resolve())
                self.table.item(row, 1).setText(Path(path).name)
                self.table.item(row, 1).setToolTip(path)

    def select_directory(self):
        path = QFileDialog.getExistingDirectory(self, "Output folder", self.initial_folder)
        if path:
            self.directory.setText(path)

    def start_conversion(self):
        if self.worker is not None:
            return
        formats = [kind for kind, field in (("tdc", self.tdc), ("intensity", self.intensity)) if field.isChecked()]
        if not self.jobs or not formats:
            QMessageBox.warning(self, "Conversion", "Add RAW files and select at least one output format.")
            return
        try:
            geometry = ScanGeometry(**{name: field.value() for name, field in self.fields.items()},
                dwell_seconds=self.dwell.value() * 1e-6, snake=self.snake.isChecked(),
                snake_z=self.snake_z.isChecked()) if self.fallback.isChecked() else None
            directory = Path(self.directory.text()).resolve() if self.directory.text().strip() else None
            if directory is not None:
                directory.mkdir(parents=True, exist_ok=True)
        except (ValueError, OSError) as error:
            QMessageBox.warning(self, "Conversion settings", str(error))
            return
        self._enable_inputs(False)
        self.worker = ConversionWorker(list(self.jobs), formats, directory, geometry, self)
        self.worker.progress.connect(self._progress)
        self.worker.result.connect(self._result)
        self.worker.completed.connect(self._completed)
        self.worker.finished.connect(self._finished)
        self.worker.start()

    def _enable_inputs(self, enabled):
        for widget in (self.add_button, self.remove_button, self.metadata_button, self.directory,
                       self.folder_button, self.tdc, self.intensity, self.fallback, self.start_button,
                       self.close_button):
            widget.setEnabled(enabled)
        self.cancel_button.setEnabled(not enabled)

    def _progress(self, value, message):
        self.progress.setValue(value)
        self.status.setText(message)

    def _result(self, index, success, message):
        self.table.item(index, 2).setText(message if success else f"Failed: {message}")
        self.log.appendPlainText(f"{self.jobs[index][0].name}: {message}")

    def _completed(self, result):
        self.status.setText(f"{result['successes']} file(s) converted; {result['failures']} failed"
                            + ("; cancelled" if result["cancelled"] else ""))
        if not result["cancelled"]:
            self.progress.setValue(100)

    def _finished(self):
        self.worker.deleteLater()
        self.worker = None
        self._enable_inputs(True)

    def cancel_conversion(self):
        if self.worker is not None:
            self.worker.cancel_event.set()
            self.cancel_button.setEnabled(False)
            self.status.setText("Cancellation requested; finishing the current conversion step…")

    def reject(self):
        if self.worker is not None:
            self.cancel_conversion()
            return
        super().reject()

    def closeEvent(self, event):
        if self.worker is not None:
            self.cancel_conversion()
            event.ignore()
            return
        super().closeEvent(event)
