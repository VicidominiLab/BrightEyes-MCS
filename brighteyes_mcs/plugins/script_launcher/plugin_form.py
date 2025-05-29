"""
    An example of implementation of the QWidget used by the plugin
    This script is can run also as stand-alone form.
"""


if __name__ == "__main__":
    from gui.plugin_gui import Ui_Form
else:
    from .gui.plugin_gui import Ui_Form

import os
from os.path import isfile, join, isdir

import pyqtgraph as pg
from PySide6.QtCore import Slot, QDir
from PySide6.QtWidgets import QApplication, QFileDialog, QWidget
from ...gui.console_widget import ConsoleWidget


class myForm(Ui_Form, QWidget):
    """
        An example of implementation of the QWidget used by the plugin
    """

    def __init__(self):
        super().__init__()

    def setupUi(self, form):
        super().setupUi(form)
        self.pushButton_fileBrowser.clicked.connect(self.file_browser)
        self.pushButton_cmdLoad.clicked.connect(self.cmd_load)
        self.pushButton_cmd1.clicked.connect(self.cmd_1)

        # self.im_widget_plot_item = pg.PlotItem()
        # self.im_widget_plot_item.setLabel("left", "y (um)")
        # self.im_widget_plot_item.setLabel("bottom", "x (um)")
        #
        # self.im_scatter = pg.ScatterPlotItem()
        #
        # self.im_widget = pg.ImageView(self, view=self.im_widget_plot_item)
        # self.im_widget.addItem(self.im_scatter)
        # self.gridLayout_placeholder.addWidget(self.im_widget)
        # self.im_widget.show()
        # self.im_widget.getView().showGrid

        self.pushButton_cmd1.setText("Grid Calibration")

        mypath = (
            os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
            + "/../../../scripts"
        )
        l = [f for f in os.listdir(mypath) if isfile(join(mypath, f))]
        list_dir = []
        for i in l:
            if not i.startswith("__") and i.endswith(".py"):
                list_dir.append(i)

        self.comboBox_script.addItems(list_dir)


    @Slot()
    def file_browser(self):
        filename = QFileDialog.getOpenFileName(
            self, caption="Load HDF5", filter="HDF5 (*.h5 *.hdf *.hdf5)", dir="."
        )[0]
        current_folder = QDir.fromNativeSeparators(os.getcwd()) + "/"
        if filename != "":
            print(filename)
            print(current_folder)
            filename_nicer = filename.replace(current_folder, "")
            self.lineEdit.setText(filename_nicer)

            self.console.push_vars({"filename": self.lineEdit.text()})
            self.console.execute_command("print('filename = ', filename)")

    @Slot()
    def cmd_1(self):
        print("cmd_1")
        filename = self.lineEdit.text()
        # self.console.execute_command("%maplotlib inline")
        self.console.push_vars({"filename": self.lineEdit.text()})
        self.console.execute_command("print('filename = ', filename)")
        self.console.run_script(
            os.path.dirname(os.path.abspath(__file__))
            + "/../../../scripts/grid_calibration.py"
        )

    @Slot()
    def cmd_load(self):
        scriptname = self.comboBox_script.currentText()
        self.console.run_script(
            os.path.dirname(os.path.abspath(__file__))
            + "/../../../scripts/"
            + scriptname
        )

    def after_acquisition(self, txt):
        self.lineEdit.setText("%s" % os.path.abspath(txt))
        filename = self.lineEdit.text()
        # self.console.execute_command("%maplotlib inline")
        self.console.push_vars({"filename": self.lineEdit.text()})
        self.console.execute_command("print('filename = ', filename)")
        if self.checkBox_autorun.isChecked():
            self.cmd_load()


# This is needed to run this plugin in stand-alone mode
if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)
    widget = QWidget()
    main = myForm()
    main.setupUi(widget)
    widget.show()
    sys.exit(app.exec_())
