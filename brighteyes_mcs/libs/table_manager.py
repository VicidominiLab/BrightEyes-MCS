from PySide2.QtWidgets import QTableWidgetItem
from PySide2.QtCore import Qt, SIGNAL, Slot
from .print_dec import print_dec


class TableManager(object):
    def __init__(self, table_widget, configuration_helper):
        self.table_lock = True

        self.table_widget = table_widget

        self.table_widget.connect(
            SIGNAL("itemChanged(QTableWidgetItem *)"), self.item_changed
        )

        self.table_header = (("Active", bool, True),)
        # "FCS"]

        self.table_footer = (
            ("Pixel Dwell Time (um)", float, 0.0),
            ("Time Single Frame (um)", float, 0.0),
            ("Total Acquisition Time (um)", float, 0.0),
            ("Delay Software (s)", float, 0.0),
        )

        # dictionary as configuration_helper but only "visible" are included.
        self.table_configuration = {}

        for n, (name, (caption, mtype, obj, visible)) in enumerate(
            configuration_helper.items()
        ):
            if visible:
                self.table_configuration[name] = (caption, mtype, obj, visible)

        self.table_len_header = len(self.table_header)
        self.table_len_footer = len(self.table_footer)
        self.table_len_middle = len(self.table_configuration)

        self.table_widget.setRowCount(
            self.table_len_header
            + len(self.table_configuration)
            + self.table_len_footer
        )

        self.table_widget.setColumnCount(0)

        for n, (i, mtype, default) in enumerate(self.table_header):
            self.table_widget.setVerticalHeaderItem(n, QTableWidgetItem(i))

        for n, (name, (caption, mtype, obj, visible)) in enumerate(
            self.table_configuration.items()
        ):
            self.table_widget.setVerticalHeaderItem(
                n + self.table_len_header, QTableWidgetItem(str(caption))
            )

        for n, (i, mtype, default) in enumerate(self.table_footer):
            self.table_widget.setVerticalHeaderItem(
                n + self.table_len_middle + self.table_len_header, QTableWidgetItem(i)
            )

        self.table_lock = False

    def add_dict(self, gui_configuration, active=True, fcs=False):
        self.table_lock = True

        k = self.table_widget.columnCount()
        self.table_widget.setColumnCount(k + 1)

        # HEADER
        chk_box_item = QTableWidgetItem()
        chk_box_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
        if active:
            chk_box_item.setCheckState(Qt.Checked)
        else:
            chk_box_item.setCheckState(Qt.Unchecked)
        self.table_widget.setItem(0, k, chk_box_item)

        chk_box_item = QTableWidgetItem()
        chk_box_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
        if fcs:
            chk_box_item.setCheckState(Qt.Checked)
        else:
            chk_box_item.setCheckState(Qt.Unchecked)
        self.table_widget.setItem(1, k, chk_box_item)

        # MIDDLE
        for n, (name, (caption, mtype, obj, visible)) in enumerate(
            self.table_configuration.items()
        ):
            value = gui_configuration[name]
            if mtype is bool:
                chk_box_item = QTableWidgetItem()
                chk_box_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
                if value:
                    chk_box_item.setCheckState(Qt.Checked)
                else:
                    chk_box_item.setCheckState(Qt.Unchecked)

                self.table_widget.setItem(n + self.table_len_header, k, chk_box_item)

            else:
                self.table_widget.setItem(
                    n + self.table_len_header, k, QTableWidgetItem(str(value))
                )

        row_headers = {}
        for row in range(
            self.table_len_header + self.table_len_middle + self.table_len_footer
        ):
            row_headers[self.table_widget.verticalHeaderItem(row).text()] = row
        self.table_widget.setItem(
            row_headers["Delay Software (s)"], k, QTableWidgetItem(str(0.0))
        )

        self.table_lock = False

        self.item_changed(self.table_widget.item(0, k))

    def add_list_of_dict(self, markers_list):
        print_dec("copyPositionMarkers")
        self.table_lock = True

        for selected_configuration in markers_list:
            self.add_dict(selected_configuration)

        self.table_lock = False

    @Slot()
    def item_changed(self, item):
        if self.table_lock:
            return
        self.table_lock = True

        row_modified = item.row()
        column_modified = item.column()
        row_count = self.table_widget.rowCount()

        row_headers = {}

        for row in range(row_count):
            row_headers[self.table_widget.verticalHeaderItem(row).text()] = row

        time_res = float(
            self.table_widget.item(
                row_headers["Time Resolution (um)"], column_modified
            ).text()
        )
        time_bin = float(
            self.table_widget.item(
                row_headers["Time Bin per Pixel"], column_modified
            ).text()
        )
        nx = int(self.table_widget.item(row_headers["#x"], column_modified).text())
        ny = int(self.table_widget.item(row_headers["#y"], column_modified).text())
        nframe = int(
            self.table_widget.item(row_headers["#frame"], column_modified).text()
        )
        nrep = int(
            self.table_widget.item(row_headers["#repetition"], column_modified).text()
        )

        a = time_res * time_bin
        print_dec(row_headers["Pixel Dwell Time (um)"], column_modified)

        c = QTableWidgetItem(str(a))
        c.setFlags(c.flags() & ~Qt.ItemIsEditable & ~Qt.ItemIsEnabled)
        self.table_widget.setItem(
            row_headers["Pixel Dwell Time (um)"], column_modified, c
        )

        a = time_res * time_bin * nx * ny * 1e-6
        c = QTableWidgetItem(str(a))
        c.setFlags(c.flags() & ~Qt.ItemIsEditable & ~Qt.ItemIsEnabled)
        self.table_widget.setItem(
            row_headers["Time Single Frame (um)"], column_modified, c
        )

        a = time_res * time_bin * nx * ny * nframe * 1e-6
        c = QTableWidgetItem(str(a))
        c.setFlags(c.flags() & ~Qt.ItemIsEditable & ~Qt.ItemIsEnabled)
        self.table_widget.setItem(
            row_headers["Total Acquisition Time (um)"], column_modified, c
        )

        self.table_lock = False

    def get_value(self, row_caption, column):
        row_headers = {}
        row_count = self.table_widget.rowCount()

        for row in range(row_count):
            row_headers[self.table_widget.verticalHeaderItem(row).text()] = row
        value_string = self.table_widget.item(row_headers[row_caption], column).text()
        if value_string == "":
            value = (
                self.table_widget.item(row_headers[row_caption], column).checkState()
                == Qt.Checked
            )
        else:
            value = value_string
        return value
