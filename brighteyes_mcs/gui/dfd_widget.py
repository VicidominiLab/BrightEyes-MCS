from PySide2.QtWidgets import (
    QWidget,
    QFileDialog,
)  # QDoubleSpinBox, QComboBox, QCheckBox,

import shutil
import h5py

from ..libs.multithread_caller_helper import pushButton_multithread_call

from PySide2.QtCore import (
    QThreadPool,
)  # , Slot, Signal, SIGNAL, QTimer, Qt, QDir, QFile, QCoreApplication, QTime, QRunnable

from PySide2.QtCore import Slot, Qt, QAbstractTableModel  # , QUrl, QObject,
from PySide2.QtGui import QFont

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import hsv_to_rgb

from matplotlib.backends.backend_qtagg import (
    FigureCanvas,
)
from matplotlib.figure import Figure

from brighteyes_mcs.gui import dfd_widget_design


try:
    import brighteyes_flim

    print(brighteyes_flim.__path__)
except Exception as e:
    print(
        e,
        "brighteyes_flim NOT INSTALLED! DFD Widget for the FLIM Preview will not work.",
    )


class DfdWidget(QWidget, dfd_widget_design.Ui_Form):
    def __init__(self, main_window=None, channels=25):
        super().__init__()
        self.setupUi(self)

        self.channels = channels

        conf = {}

        self.worker = {}

        self.threadpool = QThreadPool()

        self.main_window = main_window

        try:
            self.default_folder = main_window.ui.lineEdit_destinationfolder.text()
            print("default_folder", self.default_folder)
        except:
            self.default_folder = ""
            print("")

        try:
            conf["table_corr"] = np.array(
                self.main_window.plugin_configuration["dfd"]["table_corr"]
            )
            conf["table_meas"] = np.array(
                self.main_window.plugin_configuration["dfd"]["table_meas"]
            )
        except:
            conf["table_corr"] = np.array([[[1.0, 0.0]] * self.channels]).T.squeeze()
            conf["table_meas"] = np.array([[[1.0, 0.0, 0.0, 0.0]] * self.channels]).T.squeeze()

        self.pushButton_meas_file.clicked.connect(self.pushButton_meas_file_clicked)
        self.pushButton_ref_file.clicked.connect(self.pushButton_ref_file_clicked)

        self.pushButton_meas_load.clicked.connect(self.pushButton_meas_load_clicked)
        self.pushButton_ref_load.clicked.connect(self.pushButton_ref_load_clicked)

        self.pushButton_ref_last_acq.clicked.connect(
            self.pushButton_meas_last_acq_clicked
        )
        self.pushButton_meas_last_acq.clicked.connect(
            self.pushButton_meas_last_acq_clicked
        )

        self.pushButton_export_h5.clicked.connect(self.pushButton_export_h5_clicked)

        self.doubleSpinBox_dfd_freq.valueChanged.connect(self.dfd_freq_changed)

        self.pushButton_file_h5_input.clicked.connect(
            self.pushButton_file_h5_input_clicked
        )
        self.pushButton_show_flim_hist.clicked.connect(
            self.pushButton_show_flim_hist_clicked
        )
        self.pushButton_show_flim_img.clicked.connect(
            self.pushButton_show_flim_img_clicked
        )

        self.pushButton_flim_plot_phasors.clicked.connect(
            self.pushButton_flim_plot_phasors_clicked
        )

        self.dfd_freq = self.doubleSpinBox_dfd_freq.value() * 1e6

        self.canvas_hist = FigureCanvas(Figure(figsize=(5, 7)))
        self.tab_hist = self.gridLayout_hist.addWidget(self.canvas_hist)
        self.multi_ax_hist = self.canvas_hist.figure.subplots(2, 2)
        self.ax_hist = self.multi_ax_hist[0, 0]
        self.canvas_hist.draw()

        self.canvas_flim = FigureCanvas(Figure(figsize=(7, 7)))
        self.tab_flim = self.gridLayout_flim.addWidget(self.canvas_flim)
        self.canvas_flim.mpl_connect("motion_notify_event", self.canvas_flim_mouse_over)
        # self.multi_ax_flim = self.canvas_flim.figure.subplots(2, 2)
        # self.ax_flim = self.multi_ax_flim[0, 0]
        self.canvas_flim.draw()

        self.canvas_polar = FigureCanvas(Figure(figsize=(7, 7)))
        self.canvas_polar.mpl_connect(
            "motion_notify_event", self.canvas_polar_mouse_over
        )
        self.tab_polar = self.gridLayout_phasor.addWidget(self.canvas_polar)
        self.ax_polar = self.canvas_polar.figure.subplots(1, 1)
        self.ax_polar.set_aspect("equal")
        # self.multi_ax_polar = self.canvas_polar.figure.subplots(1, 1)
        # self.ax_polar = self.multi_ax_polar[0, 0]
        self.canvas_polar.draw()

        self.table_corr = PandasModel(data=conf["table_corr"])
        self.table_meas = PandasModel(data=conf["table_meas"], editable=False)

        self.table_corr.data_changed_call = self.UpdateConf
        self.table_meas.data_changed_call = self.UpdateConf

        self.tableView_meas.setModel(self.table_meas)

        self.tableView_meas.horizontalHeader().setFont(QFont("Helvetica", 8))
        self.tableView_meas.verticalHeader().setFont(QFont("Helvetica", 8))
        self.tableView_meas.setFont(QFont("Helvetica", 8))
        self.tableView_meas.resizeColumnsToContents()
        self.tableView_meas.resizeRowsToContents()

        self.tableView_corr.setModel(self.table_corr)

        self.tableView_corr.horizontalHeader().setFont(QFont("Helvetica", 8))
        self.tableView_corr.verticalHeader().setFont(QFont("Helvetica", 8))
        self.tableView_corr.setFont(QFont("Helvetica", 8))
        self.tableView_corr.resizeColumnsToContents()
        self.tableView_corr.resizeRowsToContents()

    def canvas_flim_mouse_over(self, event):
        x, y = event.xdata, event.ydata
        if event.xdata is None or event.ydata is None:
            return

        if self.canvas_flim_last == "img":
            img = self.img
            tau = self.tau

            self.label_over.setText(
                "x=%d y=%d ph=%d tau=%.3f ns"
                % (x, y, img[int(x), int(y)], tau[int(x), int(y)] * 1e9)
            )

    def canvas_polar_mouse_over(self, event):
        x, y = event.xdata, event.ydata
        if event.xdata is None or event.ydata is None:
            return

        m, phi, tau1, tau2 = brighteyes_flim.calculate_m_phi_tau_phi_tau_m(
            x, y, dfd_freq=21e6
        )
        self.label_over.setText(
            "g=%f s=%f   m=%f phi=%f    tau_phi=%f ns tau_m=%f ns"
            % (x, y, m, phi, tau1 * 1e9, tau2 * 1e9)
        )

    def UpdateConf(self):
        table_corr = self.table_corr.get_data()
        table_meas = self.table_meas.get_data()
        print(table_corr)
        print(table_meas)
        if self.main_window is not None:
            if "dfd" not in self.main_window.plugin_configuration.keys():
                self.main_window.plugin_configuration["dfd"] = {}
            self.main_window.plugin_configuration["dfd"] = {
                "table_corr": table_corr,
                "table_meas": table_meas,
            }
            print(self.main_window.plugin_configuration)

    def UpdateTable(self):
        self.table_corr.set_data(
            self.main_window.plugin_configuration["dfd"]["table_corr"]
        )
        self.tableView_corr.resizeColumnsToContents()
        self.tableView_corr.resizeRowsToContents()

    @Slot()
    def pushButton_flim_plot_phasors_clicked(self):
        print("pushButton_flim_plot_phasors_clicked(self):")
        filename_input = self.lineEdit_file_h5_input.text()

        with h5py.File(filename_input, "a") as f:
            # intensity = f["data_intensity"]
            phasors = f["data_phasors"][:]

            ax = self.ax_polar  # self.multi_ax_polar[0,0]
            ax.clear()

            brighteyes_flim.plot_tau(ax=ax, dfd_freq=self.dfd_freq)
            brighteyes_flim.plot_universal_circle(ax=ax)

            self.canvas_hist.draw()

            brighteyes_flim.plot_phasor(
                phasors,
                bins_2dplot=200,
                log_scale=False,
                ax=ax,
                dfd_freq=self.dfd_freq,
                cmap="inferno",
            )
            self.canvas_polar.draw()

            for i in range(0, self.channels):
                p = phasors[:, :, :, :, i].flatten()
                ax.plot(np.nanmean(np.real(p)), np.nanmean(np.imag(p)), ".r")

            self.canvas_polar.draw()
            self.tabWidget.setCurrentWidget(self.tabWidget_phasor)

    @Slot()
    def dfd_freq_changed(self):
        self.dfd_freq = self.doubleSpinBox_dfd_freq.value() * 1e6

    @Slot()
    def pushButton_meas_file_clicked(self):
        print("pushButton_meas_file_clicked")
        file_bit = QFileDialog.getOpenFileName(
            self,
            caption="Import h5 measurement",
            filter="HDF5 File (*.h5)",
            dir=self.default_folder,
        )[0]
        self.lineEdit_file_meas.setText(file_bit)
        print("file_bit", file_bit)

    @Slot()
    def pushButton_ref_file_clicked(self):
        print("pushButton_ref_file_clicked")
        file_bit = QFileDialog.getOpenFileName(
            self,
            caption="Import h5 measurement",
            filter="HDF5 File (*.h5)",
            dir=self.default_folder,
        )[0]
        self.lineEdit_file_ref.setText(file_bit)
        print("file_bit", file_bit)

    @Slot()
    def pushButton_file_h5_input_clicked(self):
        file_bit = QFileDialog.getOpenFileName(
            self,
            caption="Import h5-phasor FLIM",
            filter="HDF5 File (*.h5)",
            dir=self.default_folder,
        )[0]
        self.lineEdit_file_h5_input.setText(file_bit)
        print("file_bit", file_bit)

    @Slot()
    def pushButton_ref_load_clicked(self):
        pushButton_multithread_call(
            self.worker,
            self.threadpool,
            self.pushButton_ref_load,
            self._pushButton_ref_load_clicked,
        )

    @Slot()
    def _pushButton_ref_load_clicked(self):
        file = self.lineEdit_file_ref.text()
        print("pushButton_ref_load_clicked, file = ", file)

        if self.lineEdit_ref_irf_filter.text() == "":
            pre_filter = None
        else:
            try:
                pre_filter = float(self.lineEdit_ref_irf_filter.text())
            except:
                pre_filter = self.lineEdit_ref_irf_filter.text().lower()

        print("pre_filter", pre_filter, type(pre_filter))
        self.flim_ref = brighteyes_flim.FlimData(
            file, pre_filter=pre_filter
        )  # , pre_filter=0.1)

        tau = self.doubleSpinBox_ref_tau.value() * 1e-9
        tan_angle = 2 * np.pi * tau * self.dfd_freq
        angle_tau = np.arctan(tan_angle)
        abs_tau = 1 / np.sqrt(tan_angle**2 + 1)
        phasor_forced = abs_tau * np.exp(1j * angle_tau)

        phasor_ref = self.flim_ref.phasor_global_corrected() / phasor_forced

        print("phasor_ref", phasor_ref)

        t = np.array([[np.abs(phasor_ref)], [np.angle(phasor_ref)]]).squeeze()
        self.table_corr.set_data(t)

        self.tableView_corr.resizeColumnsToContents()
        self.tableView_corr.resizeRowsToContents()

        self.multi_ax_hist[0, 0].clear()
        self.multi_ax_hist[0, 0].plot(self.flim_ref.data_hist)

        ddd = 81 * (-np.angle(phasor_ref)) / (2 * np.pi)
        ggg = np.asarray(
            [
                brighteyes_flim.linear_shift(
                    self.flim_ref.data_hist[:, i] / max(self.flim_ref.data_hist[:, i]),
                    ddd[i],
                )
                for i in range(0, self.channels)
            ]
        ).T

        self.multi_ax_hist[0, 0].plot(self.flim_ref.data_hist)
        self.multi_ax_hist[0, 0].set_yscale("log")

        self.multi_ax_hist[0, 1].clear()
        self.multi_ax_hist[0, 1].plot(ggg)
        self.multi_ax_hist[0, 1].set_yscale("log")

        self.canvas_hist.draw()
        self.tabWidget.setCurrentWidget(self.tabWidget_hist)

    def pushButton_meas_load_clicked(self):
        pushButton_multithread_call(
            self.worker,
            self.threadpool,
            self.pushButton_meas_load,
            self._pushButton_meas_load_clicked,
        )

    def _pushButton_meas_load_clicked(self):
        print("_pushButton_meas_load_clicked")
        file = self.lineEdit_file_meas.text()
        phasor_table_polar_coord = self.table_corr.get_data()
        print("phasor_table_polar_coord", phasor_table_polar_coord.shape)
        phasor_table = phasor_table_polar_coord[0] * np.exp(
            1j * phasor_table_polar_coord[1]
        )
        print("phasor_table", phasor_table)
        print("phasor_table", phasor_table.shape)

        self.flim_meas = brighteyes_flim.FlimData(file)  # , pre_filter=0.1)
        phasor_global = self.flim_meas.phasor_global_corrected(1.0 / phasor_table)

        t = np.array(
            np.asarray(
                brighteyes_flim.calculate_m_phi_tau_phi_tau_m(
                    phasor_global, dfd_freq=self.dfd_freq
                )
            )
        ).squeeze()
        self.table_meas.set_data(t)

        self.tableView_meas.resizeColumnsToContents()
        self.tableView_meas.resizeRowsToContents()

        self.multi_ax_hist[1, 0].plot(self.flim_meas.data_hist)

        ddd = 81 * np.angle(1.0 / phasor_table / phasor_global) / (2 * np.pi)
        ggg = np.asarray(
            [
                brighteyes_flim.linear_shift(
                    self.flim_meas.data_hist[:, i]
                    / max(self.flim_meas.data_hist[:, i]),
                    ddd[i],
                )
                for i in range(0, self.channels)
            ]
        ).T

        self.multi_ax_hist[1, 0].clear()
        self.multi_ax_hist[1, 0].plot(self.flim_meas.data_hist)
        self.multi_ax_hist[1, 0].set_yscale("log")

        self.multi_ax_hist[1, 1].clear()
        self.multi_ax_hist[1, 1].plot(ggg)
        self.multi_ax_hist[1, 1].set_yscale("log")

        self.canvas_hist.draw()

        ax = self.ax_polar  # self.multi_ax_polar[0,0]
        ax.clear()
        ax.plot(np.real(phasor_global), np.imag(phasor_global), ".y")

        brighteyes_flim.plot_tau(ax=ax, dfd_freq=self.dfd_freq)
        brighteyes_flim.plot_universal_circle(ax=ax)

        brighteyes_flim.calculate_m_phi_tau_phi_tau_m(
            phasor_global, dfd_freq=self.dfd_freq
        )

        self.tabWidget.setCurrentWidget(self.tabWidget_hist)
        self.canvas_hist.draw()

        merge_pixels = self.spinBox_merge_pixel.value()
        self.flim_meas.calculate_phasor_on_img_ch(merge_pixels)
        phasors = self.flim_meas.phasors_corrected(1.0 / phasor_table)
        brighteyes_flim.plot_phasor(
            phasors,
            bins_2dplot=200,
            log_scale=False,
            ax=ax,
            dfd_freq=self.dfd_freq,
            cmap="inferno",
        )

        self.tabWidget.setCurrentWidget(self.tabWidget_phasor)
        self.canvas_polar.draw()

        gph = phasor_global

        for i in range(0, self.channels):
            ax.plot(np.nanmean(np.real(gph[i])), np.nanmean(np.imag(gph[i])), ".r")
            m, phi, tau, tau_m = brighteyes_flim.calculate_m_phi_tau_phi_tau_m(
                gph[i], dfd_freq=self.dfd_freq
            )
            print(
                "%d\tphi: %.2e\tm: %.2e\t\ttau_phi: %.2e \ttau_m: %.2e"
                % (i, phi, m, tau, tau_m)
            )

        self.canvas_polar.draw()

    # @Slot()
    # def pushButton_ref_last_acq_clicked(self):
    #     if self.main_window is not None:
    #         f = self.main_window.last_saved_filename
    #         if f is not None:
    #             self.lineEdit_file_ref.setText(f)
    #     print("pushButton_meas_last_acq_clicked")

    @Slot()
    def pushButton_meas_last_acq_clicked(self):
        if self.main_window is not None:
            f = self.main_window.last_saved_filename
            if f is not None:
                self.lineEdit_file_meas.setText(f)
        print("pushButton_meas_last_acq_clicked")

    @Slot()
    def pushButton_export_h5_clicked(self):
        phasor_table_polar_coord = self.table_corr.get_data()
        phasor_table = phasor_table_polar_coord[0] * np.exp(
            1j * phasor_table_polar_coord[1]
        )

        phasors = self.flim_meas.phasors_corrected(1.0 / phasor_table)
        print(phasors.shape)

        filename_original = self.lineEdit_file_meas.text()
        filename_destination = self.lineEdit_file_meas.text().replace(
            ".h5", "-phasors.h5"
        )

        self.lineEdit_file_h5_export.setText(filename_destination)
        self.lineEdit_file_h5_input.setText(filename_destination)

        shutil.copyfile(filename_original, filename_destination)

        with h5py.File(filename_destination, "a") as f:
            try:
                del f["data"]
                print("[data] deleted")
                del f["data_channels_extra"]
                print("[data_channels_extra] deleted")
            except:
                print("error in deletion of dataset")

            merge_pixels = self.spinBox_merge_pixel.value()

            f["data_intensity"] = brighteyes_flim.sum_adjacent_pixel(
                self.flim_meas.data, merge_pixels
            ).sum(axis=-2)
            print("[data_intensity] added ", f["data_intensity"].shape)

            f["data_phasors"] = phasors
            print("[data_phasors] added ", f["data_phasors"].shape)
        print("file_closed")

    def calculate_tau(self, phasors, intensity):
        if self.comboBox_flim_tau.currentText() == "Tau_phi":
            tau = brighteyes_flim.calculate_tau_phi(phasors)
        elif self.comboBox_flim_tau.currentText() == "Tau_m":
            tau = brighteyes_flim.calculate_tau_m(phasors)
        elif self.comboBox_flim_tau.currentText() == "Tau_avg":
            tau_m = brighteyes_flim.calculate_tau_m(phasors)
            tau_phi = brighteyes_flim.calculate_tau_phi(phasors)

            tau = (tau_m + tau_phi) * 0.5
        elif self.comboBox_flim_tau.currentText() == "Tau_diff":
            tau_m = brighteyes_flim.calculate_tau_m(phasors)
            tau_phi = brighteyes_flim.calculate_tau_phi(phasors)

            tau = tau_m - tau_phi
        elif self.comboBox_flim_tau.currentText() == "Tau_avg2":
            tau_m = brighteyes_flim.calculate_tau_m(phasors)
            tau_phi = brighteyes_flim.calculate_tau_phi(phasors)

            tau = np.sqrt((tau_m**2 + tau_phi**2) / 2)
        else:
            print("Wrong combo box value", self.comboBox_flim_tau.currentText())
            return None

        if self.comboBox_tau_channel.currentText() == "Mean":
            tau = np.nanmean(tau, axis=(0, 1, -1))
        elif self.comboBox_tau_channel.currentText().isnumeric():
            ch = int(self.comboBox_tau_channel.currentText())
            tau = np.nanmean(tau, axis=(0, 1))
            tau = tau[:, :, ch]
        else:
            ch = 12
            tau = np.nanmean(tau, axis=(0, 1))
            tau = tau[:, :, ch]

        return tau

    def calculate_img(self, intensity):
        if self.comboBox_flim_intensity.currentText() == "Sum":
            return np.nansum(intensity, axis=(0, 1, -1))
        elif self.comboBox_flim_intensity.currentText() == "Uniform":
            i = np.ones((intensity.shape[2], intensity.shape[3])) * 1.0
            i[0, 0] = 0.999
            return i
        elif self.comboBox_flim_intensity.currentText().isnumeric():
            ch = int(self.comboBox_flim_intensity.currentText())
            return np.nansum(intensity, axis=(0, 1))[:, :, ch]

    @Slot()
    def pushButton_show_flim_hist_clicked(self):
        print("pushButton_show_flim_hist_clicked")
        filename = self.lineEdit_file_h5_input.text()

        with h5py.File(filename) as f:
            intensity = f["data_intensity"]
            phasors = f["data_phasors"]

            tau = self.calculate_tau(phasors,intensity)
            img = self.calculate_img(intensity)

            if tau is None or img is None:
                return

            self.canvas_flim_last = "hist"

            self.img = img
            self.tau = tau

            print("intensity", intensity.shape)
            print("data_phasors", phasors.shape)
            print("tau", tau.shape)

            # self.TEST = tau

            self.label_suggest.setText(
                "Min: %.3f, Mean: %.3f Max: %.3f,    10%% Perc.: %.3f, 50%% Perc.: %.3f, 90%% Perc.: %.3f"
                % (
                    np.nanmin(tau) * 1e9,
                    np.nanmean(tau) * 1e9,
                    np.nanmax(tau) * 1e9,
                    np.nanpercentile(tau, 10) * 1e9,
                    np.nanpercentile(tau, 50) * 1e9,
                    np.nanpercentile(tau, 90) * 1e9,
                )
            )

            self.canvas_flim.figure.clear()
            ax_flim = self.canvas_flim.figure.subplots(1, 1)
            ax_flim.set_aspect("auto")

            if self.checkBox_hist_std_range.isChecked():
                hist_min = np.nanpercentile(tau, 1)
                hist_max = np.nanpercentile(tau, 99)
            else:
                hist_min = self.doubleSpinBox_min_tau.value() * 1e-9
                hist_max = self.doubleSpinBox_max_tau.value() * 1e-9

            ax_flim.hist(tau.flatten(), bins=100, range=[hist_min, hist_max])

            self.tabWidget.setCurrentWidget(self.tabWidget_flim)

            self.canvas_flim.draw()

    @Slot()
    def pushButton_show_flim_img_clicked(self):
        print("pushButton_show_flim_img_clicked")
        filename = self.lineEdit_file_h5_input.text()

        with h5py.File(filename) as f:
            intensity = f["data_intensity"]
            phasors = f["data_phasors"]

            tau = self.calculate_tau(phasors,intensity)
            img = self.calculate_img(intensity)

            if tau is None or img is None:
                return

            min_t = self.doubleSpinBox_min_tau.value() * 1e-9
            max_t = self.doubleSpinBox_max_tau.value() * 1e-9

            self.canvas_flim.figure.clear()

            self.canvas_flim_last = "img"

            self.img = img
            self.tau = tau

            showFLIM(
                img,
                tau,
                bounds_Tau={"minTau": min_t, "maxTau": max_t},
                fig=self.canvas_flim.figure,
                satFactor=self.doubleSpinBox_satFactor.value(),
                outOfBoundsHue=self.doubleSpinBox_outOfBoundsHue.value(),
                invertColormap=self.checkBox_flim_invertcolor.isChecked(),
            )

            self.tabWidget.setCurrentWidget(self.tabWidget_flim)

            self.canvas_flim.draw()


class PandasModel(QAbstractTableModel):
    def __init__(self, data, editable=True):
        super().__init__()
        self._data = data
        self.editable = editable
        self.data_changed_call = None

    def rowCount(self, index):
        return self._data.shape[0]

    def columnCount(self, index):
        return self._data.shape[1]

    def data(self, index, role=Qt.DisplayRole):
        if index.isValid():
            if role == Qt.DisplayRole or role == Qt.EditRole:
                value = self._data[index.row(), index.column()]
                return "%.3e" % (value)

    def get_data(self):
        return self._data

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return "CH {}".format(section)
        if orientation == Qt.Vertical and role == Qt.DisplayRole:
            if section == 0:
                return "Magnitude"
            if section == 1:
                return "Phase"
            if section == 2:
                return "Tau_phi"
            if section == 3:
                return "Tau_m"
        return super().headerData(section, orientation, role)

    def setData(self, index, value, role):
        if role == Qt.EditRole and self.editable:
            try:
                value = float(value)
            except ValueError:
                return False
            self._data[index.row(), index.column()] = value
            if self.data_changed_call is not None:
                self.data_changed_call()
            return True
        return False

    def set_data(self, data):
        self._data = np.asarray(data)
        if self.data_changed_call is not None:
            self.data_changed_call()
        return True

    def flags(self, index):
        if self.editable:
            return Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable
        return Qt.ItemIsSelectable | Qt.ItemIsEnabled


def cmap2d(intensity, lifetime, params):
    sz = intensity.shape

    Hp = np.minimum(np.maximum(lifetime, params["minTau"]), params["maxTau"])

    # the HSV representation
    Hn = ((Hp - params["minTau"]) / (params["maxTau"] - params["minTau"])) * params[
        "satFactor"
    ]
    Sn = np.ones(Hp.shape)
    Vn = (intensity - params["minInt"]) / (params["maxInt"] - params["minInt"])

    HSV = np.empty((sz[0], sz[1], 3))

    if params["invertColormap"] == True:
        Hn = params["satFactor"] - Hn

    # set to violet color of pixels outside lifetime bounds
    # BG = intensity < ( np.max(intensity * params.bgIntPerc )
    Hn[np.not_equal(lifetime, Hp)] = params["outOfBoundsHue"]

    HSV[:, :, 0] = Hn.astype("float64")
    HSV[:, :, 1] = Sn.astype("float64")
    HSV[:, :, 2] = Vn.astype("float64")

    # convert to RGB
    RGB = hsv_to_rgb(HSV)

    return RGB


def showFLIM(
    intensity,
    lifetime,
    bounds_Tau=None,
    bounds_Int=None,
    satFactor=0.657,
    outOfBoundsHue=0.8,
    invertColormap=False,
    fig=None,
):
    """
    Display together the lifetime and intensity images with a proper colormap.
    Referring to the HSV color model:
    Intensity values are mapped in Value
    Lifetime values are mapped in Hue
    If the lifetime of a pixel is outside the interval [minInt, maxInt],
    that pixel is rendered with Hue outOfBoundsHue (default: violet)

    Input parameters
    intensityIm:        Pixel values are photon counts.
    lifetimeIm:         Pixel values are lifetime values.

    bounds_Tau
        minTau:             minimum lifetime value of the colorbar
        maxTau:             maximum lifetime value of the colorbar
    bounds_Int
        minInt:             minimum intensity value of the colorbar
        maxInt:             maximum intensity value of the colorbar
    invertColormap:     (False)
    outOfBoundsHue:      Hue to render the out of bounds pixels (0.8)
    satFactor:           The span of the Hue space (0.657)

    Last Modified May 2022 by Alessandro Zunino
    Based on the MATLAB function written by Giorgio Tortarolo
    """

    if bounds_Tau is None:
        bounds_Tau = {
            "minTau": np.min(lifetime),
            "maxTau": np.max(lifetime),
        }

    if bounds_Int is None:
        bounds_Int = {"minInt": np.min(intensity), "maxInt": np.max(intensity)}

    params = bounds_Tau.copy()
    params.update(bounds_Int)

    params["invertColormap"] = invertColormap
    params["satFactor"] = satFactor
    params["outOfBoundsHue"] = outOfBoundsHue

    sz = intensity.shape
    N = sz[0]

    # Image

    RGB = cmap2d(intensity, lifetime, params)

    # Colorbar

    LG = np.linspace(params["minTau"], params["maxTau"], num=sz[0])
    LifeTimeGradient = np.tile(LG, (N, 1))

    IG = np.linspace(params["minInt"], params["maxInt"], num=N)
    IntensityGradient = np.transpose(np.tile(IG, (sz[0], 1)))

    RGB_colormap = cmap2d(IntensityGradient, LifeTimeGradient, params)
    RGB_colormap = np.moveaxis(RGB_colormap, 0, 1)

    # Show combined image with colorbar

    extent = (params["minInt"], params["maxInt"], params["minTau"], params["maxTau"])

    if fig is None:
        fig = plt.figure(figsize=(9, 8))

    widths = [0.05, 1]
    heights = [1]
    spec = fig.add_gridspec(
        ncols=2, nrows=1, width_ratios=widths, height_ratios=heights
    )

    ax = fig.add_subplot(spec[0, 1])

    ax.imshow(RGB)
    ax.axis("off")

    ax = fig.add_subplot(spec[0, 0])

    ax.imshow(RGB_colormap, origin="lower", aspect="auto", extent=extent)
    ax.set_xticks([params["minInt"], params["maxInt"]])
    ax.set_xlabel("Counts")
    ax.set_ylabel("Lifetime")

    if fig is None:
        plt.tight_layout()

    return RGB, RGB_colormap
