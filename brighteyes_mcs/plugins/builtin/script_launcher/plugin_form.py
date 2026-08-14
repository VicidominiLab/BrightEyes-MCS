"""
    An example of implementation of the QWidget used by the plugin
    This script is can run also as stand-alone form.
"""


if __name__ == "__main__":
    from gui.plugin_gui import Ui_Form
else:
    from .gui.plugin_gui import Ui_Form

import os

from PySide6.QtCore import Slot, QDir
from PySide6.QtWidgets import QApplication, QFileDialog, QWidget
from ....application.paths import profile_directory, resource_path


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

        self.refresh_scripts()

    def refresh_scripts(self):
        """Merge bundled scripts with scripts from the active profile."""

        selected_script = self.comboBox_script.currentText()
        self.script_paths = {}
        # Bundled scripts are always available. A profile script with the same
        # filename intentionally overrides its bundled counterpart.
        for scripts_directory in (
            resource_path("scripts"),
            profile_directory("scripts"),
        ):
            if not scripts_directory.is_dir():
                continue
            for path in scripts_directory.iterdir():
                if path.is_file() and not path.name.startswith("__") and path.suffix == ".py":
                    self.script_paths[path.name] = path

        self.comboBox_script.clear()
        self.comboBox_script.addItems(sorted(self.script_paths))
        if selected_script in self.script_paths:
            self.comboBox_script.setCurrentText(selected_script)


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
        # self.console.execute_command("%maplotlib inline")
        self.console.push_vars({"filename": self.lineEdit.text()})
        self.console.execute_command("print('filename = ', filename)")
        script_path = self.script_paths.get("grid_calibration.py")
        if script_path is not None:
            self.console.run_script(str(script_path))

    @Slot()
    def cmd_load(self):
        self.refresh_scripts()
        scriptname = self.comboBox_script.currentText()
        if not scriptname:
            return
        script_path = self.script_paths.get(scriptname)
        if script_path is not None:
            self.console.run_script(str(script_path))

    def after_acquisition(self, txt):
        self.lineEdit.setText("%s" % os.path.abspath(txt))
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
