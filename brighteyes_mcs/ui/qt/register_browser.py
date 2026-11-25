"""Searchable register trees with typed edits and stable live refreshes."""

from copy import deepcopy
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal
import math
import numbers
import re

import numpy as np
from PySide6.QtCore import QModelIndex, QSignalBlocker, QSortFilterProxyModel, Qt, QTimer, Signal
from PySide6.QtGui import QFontDatabase, QKeySequence, QShortcut, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QHeaderView, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QStyledItemDelegate,
    QVBoxLayout, QWidget,
)


PATH_ROLE = Qt.ItemDataRole.UserRole + 1
VALUE_ROLE = Qt.ItemDataRole.UserRole + 2
GROUP_ROLE = Qt.ItemDataRole.UserRole + 3


@dataclass
class RegisterValue:
    # Keep U64 values in Python; QVariant's signed integer conversion overflows.
    value: object


def parse_value(text, current):
    """Parse without evaluating code or silently changing a value's type."""
    if isinstance(current, (bool, np.bool_)):
        if text.strip().lower() not in ("true", "false", "1", "0"):
            raise ValueError("Use True or False for a boolean value.")
        return text.strip().lower() in ("true", "1")
    if isinstance(current, numbers.Integral):
        value = text.strip()
        return int(value, 0) if value.lower().lstrip("+-").startswith(("0x", "0o", "0b")) else int(value)
    if isinstance(current, (numbers.Real, Decimal)):
        value = Decimal(text) if isinstance(current, Decimal) else float(text)
        if not math.isfinite(value):
            raise ValueError("Enter a finite number.")
        return value
    if isinstance(current, str):
        return text
    raise ValueError("This value cannot be edited.")


def children(value):
    if isinstance(value, dict):
        return value.items()
    if isinstance(value, (list, tuple)) or isinstance(value, np.ndarray) and value.ndim > 0:
        return enumerate(value)
    return ()


def value_text(value):
    if isinstance(value, dict):
        return f"{len(value)} items"
    if isinstance(value, (list, tuple)) or isinstance(value, np.ndarray) and value.ndim > 0:
        return f"{len(value)} items"
    return str(value)


def same_value(left, right):
    if type(left) is not type(right):
        return False
    if left is right:
        return True
    if isinstance(left, np.ndarray):
        return np.array_equal(left, right)
    try:
        return bool(left == right)
    except (TypeError, ValueError):
        return False


def prefix_groups(names):
    """Plan shared underscore prefixes, compressing single-child branches."""
    tokens = {name: tuple(name.split("_")) for name in names
              if isinstance(name, str) and all(name.split("_"))}
    counts = Counter(parts[:depth] for parts in tokens.values() for depth in range(1, len(parts) + 1))
    redundant = {prefix[:-1] for prefix, count in counts.items()
                 if len(prefix) > 1 and counts.get(prefix[:-1]) == count}
    groups = {prefix for prefix, count in counts.items() if count > 1 and prefix not in redundant}
    membership = {}
    for name, parts in tokens.items():
        shared = [parts[:depth] for depth in range(1, len(parts) + 1) if parts[:depth] in groups]
        if shared:
            membership[name] = max(shared, key=len)
    return counts, groups, membership


def natural_key(text):
    return tuple((1, int(part)) if part.isdigit() else (0, part)
                 for part in re.split(r"(\d+)", str(text).casefold()))


class RegisterModel(QStandardItemModel):
    editResult = Signal(bool, str)

    def __init__(self, access, write, parent=None):
        super().__init__(parent)
        self.setHorizontalHeaderLabels(["Parameter", "Current value", "Type", "Access"])
        self.access = access
        self.write = write
        self.rows = {}
        self.groups = {}
        self.group_prefixes = True
        self._membership = {}
        self._row_metadata = {}
        self._values = {}

    def _build_groups(self, names):
        self.groups.clear()
        self._membership = {}
        if not self.group_prefixes:
            return
        counts, groups, self._membership = prefix_groups(names)
        for prefix in sorted(groups, key=lambda key: (len(key), key)):
            ancestor = next((prefix[:depth] for depth in range(len(prefix) - 1, 0, -1)
                             if prefix[:depth] in self.groups), ())
            parent = self.groups[ancestor] if ancestor else self.invisibleRootItem()
            caption = "_".join(prefix[len(ancestor):])
            row = [QStandardItem(caption), QStandardItem(f"{counts[prefix]} registers"),
                   QStandardItem("group"), QStandardItem()]
            for item in row:
                item.setEditable(False)
                item.setData(prefix, GROUP_ROLE)
                item.setToolTip("_".join(prefix) + "_*\nExpand to browse related registers.")
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            parent.appendRow(row)
            self.groups[prefix] = row[0]

    def _root_parent(self, name):
        group = self._membership.get(name)
        return self.groups[group] if group is not None else self.invisibleRootItem()

    def _root_caption(self, name):
        group = self._membership.get(name)
        if group is None:
            return str(name)
        suffix = str(name).split("_")[len(group):]
        return "_".join(suffix) if suffix else str(name)

    def set_grouped(self, enabled):
        """Reparent existing register items without changing values or paths."""
        if self.group_prefixes == enabled:
            return
        self.group_prefixes = enabled
        roots = {}
        for path, row in self.rows.items():
            if len(path) == 1:
                parent = row[0].parent() or self.invisibleRootItem()
                roots[path] = parent.takeRow(row[0].row())
        self.removeRows(0, self.rowCount())
        self._build_groups(path[0] for path in roots)
        for path, row in roots.items():
            row[0].setText(self._root_caption(path[0]))
            self._root_parent(path[0]).appendRow(row)

    def updateData(self, data):
        entries = {}

        def visit(value, path):
            entries[path] = value
            for key, child in children(value):
                visit(child, path + (key,))

        for key, value in data.items():
            visit(value, (key,))
        # Value-only refreshes keep indexes, scroll, selection and expansion intact.
        if entries.keys() != self.rows.keys():
            self.removeRows(0, self.rowCount())
            self.rows.clear()
            self._row_metadata.clear()
            self._values.clear()
            self._build_groups(data)
            for path in entries:
                row = [QStandardItem() for _ in range(4)]
                parent = self.rows[path[:-1]][0] if len(path) > 1 else self._root_parent(path[0])
                parent.appendRow(row)
                self.rows[path] = row
                for item in row:
                    item.setEditable(False)
                    item.setData(path, PATH_ROLE)
                row[0].setText(self._root_caption(path[0]) if len(path) == 1 else
                               str(path[-1]) if isinstance(path[-1], str) else f"[{path[-1]}]")
                row[1].setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))

        for path, value in entries.items():
            row = self.rows[path]
            editable, access_text = self.access(path, value)
            scalar = isinstance(value, (str, numbers.Real, Decimal, np.bool_))
            text = value_text(value)
            full_text = str(value)
            metadata = (type(value), text, full_text, editable and scalar, access_text)
            if (self._row_metadata.get(path) == metadata and path in self._values
                    and same_value(self._values[path], value)):
                continue
            self._row_metadata[path] = metadata
            self._values[path] = value
            row[1].setEditable(editable and scalar)
            row[1].setData(RegisterValue(value), VALUE_ROLE)
            row[1].setText(text)
            row[2].setText(type(value).__name__)
            row[3].setText(access_text)
            tooltip = " / ".join(map(str, path)) + "\n" + full_text + "\n" + access_text
            for item in row:
                item.setToolTip(tooltip)

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if role != Qt.ItemDataRole.EditRole:
            return super().setData(index, value, role)
        if index.column() != 1 or not self.flags(index) & Qt.ItemFlag.ItemIsEditable:
            return False
        path = index.data(PATH_ROLE)
        try:
            parsed = parse_value(str(value), index.data(VALUE_ROLE).value)
            accepted = self.write(path, parsed)
        except Exception as error:
            self.editResult.emit(False, f"Could not update {' / '.join(map(str, path))}: {error}")
            return False
        self.rows[path][1].setData(RegisterValue(accepted), VALUE_ROLE)
        self.rows[path][1].setText(value_text(accepted))
        self._row_metadata.pop(path, None)
        self.editResult.emit(True, f"Updated {' / '.join(map(str, path))} = {accepted}")
        return True


class RegisterFilter(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.query = ""
        self.field = 0
        self.filter_enabled = True
        self.setRecursiveFilteringEnabled(True)
        self.setAutoAcceptChildRows(True)
        self.setSortCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

    def matches(self, index):
        prefix = index.siblingAtColumn(0).data(GROUP_ROLE)
        if prefix is not None:
            return self.field != 2 and self.query in "_".join(prefix).casefold()
        columns = (0, 1) if self.field == 0 else (self.field - 1,)
        path = index.siblingAtColumn(0).data(PATH_ROLE)
        full_name_matches = self.field != 2 and path and len(path) == 1 and self.query in str(path[0]).casefold()
        return bool(full_name_matches) or any(self.query in str(index.siblingAtColumn(column).data() or "").casefold() for column in columns)

    def filterAcceptsRow(self, row, parent):
        return not self.filter_enabled or not self.query or self.matches(self.sourceModel().index(row, 0, parent))

    def lessThan(self, left, right):
        left_path, right_path = left.data(PATH_ROLE), right.data(PATH_ROLE)
        if (left.column() == 0 and left_path and right_path
                and isinstance(left_path[-1], int) and isinstance(right_path[-1], int)):
            return left_path[-1] < right_path[-1]
        if left.column() == 1:
            left_value, right_value = left.data(VALUE_ROLE), right.data(VALUE_ROLE)
            if (left_value is not None and right_value is not None
                    and isinstance(left_value.value, (numbers.Real, Decimal, np.bool_))
                    and isinstance(right_value.value, (numbers.Real, Decimal, np.bool_))):
                return left_value.value < right_value.value
        if left.column() == 0:
            return natural_key(left.data() or "") < natural_key(right.data() or "")
        return super().lessThan(left, right)


class RegisterDelegate(QStyledItemDelegate):
    """Use text editors so FPGA-sized integers never pass through a Qt int."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.editing = False

    def createEditor(self, parent, option, index):
        self.editing = True
        if isinstance(index.data(VALUE_ROLE).value, (bool, np.bool_)):
            editor = QComboBox(parent)
            editor.addItems(["False", "True"])
            return editor
        return QLineEdit(parent)

    def setEditorData(self, editor, index):
        text = str(index.data(VALUE_ROLE).value)
        if isinstance(editor, QComboBox):
            editor.setCurrentText(text)
        else:
            editor.setText(text)
            editor.selectAll()

    def setModelData(self, editor, model, index):
        text = editor.currentText() if isinstance(editor, QComboBox) else editor.text()
        model.setData(index, text, Qt.ItemDataRole.EditRole)


class RegisterBrowser(QWidget):
    def __init__(self, tree, access, write, refresh, parent=None):
        super().__init__(parent)
        self.tree = tree
        self.pending = None
        self.model = RegisterModel(access, write, self)
        self.proxy = RegisterFilter(self)
        self.proxy.setSourceModel(self.model)
        tree.setModel(self.proxy)
        self.delegate = RegisterDelegate(tree)
        tree.setItemDelegate(self.delegate)
        self.delegate.closeEditor.connect(self._editor_closed)
        self.model.editResult.connect(self._edit_result)
        tree.setAlternatingRowColors(True)
        tree.setUniformRowHeights(True)
        tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        tree.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.EditKeyPressed)
        tree.setSortingEnabled(True)
        tree.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        tree.setColumnWidth(0, 300)
        tree.setColumnWidth(2, 90)
        tree.setColumnWidth(3, 135)
        tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        tree.header().setStretchLastSection(False)

        self.search = QLineEdit(self)
        self.search.setPlaceholderText("Find a parameter or value… (Ctrl+F)")
        self.search.setClearButtonEnabled(True)
        self.search.setAccessibleName("Find registers")
        self.field = QComboBox(self)
        self.field.addItems(["Name or value", "Name", "Value"])
        self.filter = QCheckBox("Filter", self)
        self.filter.setChecked(True)
        self.filter.setToolTip("Show matching items and their parents. Clear to find without hiding rows.")
        find = QPushButton("Find next", self)
        find.setToolTip("Find the next matching item (Enter / F3)")
        search_row = QHBoxLayout()
        for widget in (self.search, self.field, self.filter, find):
            search_row.addWidget(widget, 1 if widget is self.search else 0)

        self.edit_button = QPushButton("Edit value", self)
        self.edit_button.setEnabled(False)
        expand = QPushButton("Expand all", self)
        collapse = QPushButton("Collapse all", self)
        refresh_button = QPushButton("Refresh", self)
        self.group_prefixes = QCheckBox("Group prefixes", self)
        self.group_prefixes.setChecked(True)
        self.group_prefixes.setToolTip("Group shared underscore prefixes. Full register names remain searchable and available in tooltips and Copy parameter path.")
        self.count = QLabel(self)
        actions = QHBoxLayout()
        for widget in (self.edit_button, expand, collapse, refresh_button):
            actions.addWidget(widget)
        actions.addWidget(self.group_prefixes)
        actions.addStretch()
        actions.addWidget(self.count)
        self.message = QLabel("Double-click a writable value or select it and press F2. Enter applies; Esc cancels.", self)
        self.message.setWordWrap(True)
        self.message.setTextFormat(Qt.TextFormat.PlainText)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(search_row)
        layout.addLayout(actions)
        layout.addWidget(tree, 1)
        layout.addWidget(self.message)
        self.search.textChanged.connect(self._search_changed)
        self.field.currentIndexChanged.connect(self._search_changed)
        self.filter.toggled.connect(self._search_changed)
        self.search.returnPressed.connect(self.find_next)
        find.clicked.connect(self.find_next)
        self.edit_button.clicked.connect(self.edit_current)
        expand.clicked.connect(tree.expandAll)
        collapse.clicked.connect(tree.collapseAll)
        refresh_button.clicked.connect(refresh)
        self.group_prefixes.toggled.connect(self._grouping_changed)
        tree.selectionModel().currentChanged.connect(self._selection_changed)
        self.focus_shortcut = QShortcut(QKeySequence.StandardKey.Find, self)
        self.focus_shortcut.activated.connect(self.focus_search)
        self.next_shortcut = QShortcut(QKeySequence("F3"), self)
        self.next_shortcut.activated.connect(self.find_next)
        self.edit_shortcut = QShortcut(QKeySequence("F2"), self)
        self.edit_shortcut.activated.connect(self.edit_current)
        for shortcut in (self.focus_shortcut, self.next_shortcut, self.edit_shortcut):
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)

    def focus_search(self):
        self.search.setFocus()
        self.search.selectAll()

    def _selection_changed(self, *args):
        index = self.tree.currentIndex().siblingAtColumn(1)
        self.edit_button.setEnabled(bool(index.flags() & Qt.ItemFlag.ItemIsEditable))

    def edit_current(self):
        index = self.tree.currentIndex().siblingAtColumn(1)
        if index.flags() & Qt.ItemFlag.ItemIsEditable:
            self.tree.setCurrentIndex(index)
            self.tree.edit(index)

    def _grouping_changed(self, enabled):
        if self.delegate.editing:
            blocker = QSignalBlocker(self.group_prefixes)
            self.group_prefixes.setChecked(self.model.group_prefixes)
            del blocker
            self.message.setText("Finish or cancel the current edit before changing grouping.")
            return
        state = self._view_state()
        self.model.set_grouped(enabled)
        self._restore_view_state(state)
        self._update_count()

    def _search_changed(self, *args):
        self.proxy.beginFilterChange()
        self.proxy.query = self.search.text().strip().casefold()
        self.proxy.field = self.field.currentIndex()
        self.proxy.filter_enabled = self.filter.isChecked()
        self.proxy.endFilterChange(QSortFilterProxyModel.Direction.Rows)
        if self.proxy.query and self.proxy.filter_enabled:
            self.tree.expandAll()
        self._update_count()

    def _update_count(self):
        parameters = [row[0].index() for path, row in self.model.rows.items() if len(path) == 1]
        visible = sum(self.proxy.mapFromSource(index).isValid() for index in parameters)
        self.count.setText(f"{visible} / {len(parameters)} parameters")
        self._selection_changed()

    def find_next(self):
        if not self.proxy.query:
            return
        indexes = []

        def visit(parent):
            for row in range(self.proxy.rowCount(parent)):
                index = self.proxy.index(row, 0, parent)
                indexes.append(index)
                visit(index)

        visit(QModelIndex())
        current = self.tree.currentIndex().siblingAtColumn(0)
        start = indexes.index(current) + 1 if current in indexes else 0
        for index in indexes[start:] + indexes[:start]:
            if index.data(PATH_ROLE) and self.proxy.matches(index):
                self.tree.setCurrentIndex(index)
                self.tree.scrollTo(index)
                return
        self.message.setText("No matching items.")

    def _view_state(self):
        selected = self.tree.currentIndex().data(PATH_ROLE)
        selected_column = self.tree.currentIndex().column()
        expanded = {path for path, row in self.model.rows.items()
                    if self.tree.isExpanded(self.proxy.mapFromSource(row[0].index()))}
        expanded_groups = {prefix for prefix, item in self.model.groups.items()
                           if self.tree.isExpanded(self.proxy.mapFromSource(item.index()))}
        return selected, selected_column, expanded, expanded_groups, set(self.model.groups), self.tree.currentIndex().data(GROUP_ROLE)

    def _restore_view_state(self, state):
        selected, selected_column, expanded, expanded_groups, old_groups, selected_group = state
        for prefix, item in self.model.groups.items():
            if prefix in expanded_groups or prefix not in old_groups and item.parent() is None:
                self.tree.expand(self.proxy.mapFromSource(item.index()))
        for path in expanded:
            if path in self.model.rows:
                self.tree.expand(self.proxy.mapFromSource(self.model.rows[path][0].index()))
        if selected in self.model.rows and self.tree.currentIndex().data(PATH_ROLE) != selected:
            index = self.proxy.mapFromSource(self.model.rows[selected][selected_column].index())
            self.tree.setCurrentIndex(index)
            parent = index.parent()
            while parent.isValid():
                self.tree.expand(parent)
                parent = parent.parent()
        elif selected_group in self.model.groups:
            self.tree.setCurrentIndex(self.proxy.mapFromSource(self.model.groups[selected_group].index()))
        if self.proxy.query and self.proxy.filter_enabled:
            self.tree.expandAll()

    def update_data(self, data):
        if self.delegate.editing:
            self.pending = deepcopy(data)
            return
        state = self._view_state()
        self.model.updateData(data)
        self._restore_view_state(state)
        self._update_count()

    def _edit_result(self, success, message):
        # A queued pre-edit sample must never overwrite an accepted edit.
        if success:
            self.pending = None
        self.message.setText(message)
        self.message.setStyleSheet("" if success else "color: #c62828;")

    def _editor_closed(self, *args):
        self.delegate.editing = False
        if self.pending is not None:
            data, self.pending = self.pending, None
            QTimer.singleShot(0, lambda: self.update_data(data))
