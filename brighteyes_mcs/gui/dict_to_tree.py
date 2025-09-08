from PySide6.QtCore import Qt, QModelIndex, QAbstractItemModel
from ..libs.print_dec import print_dec, set_debug




class TreeModel(QAbstractItemModel):
    def __init__(self, headers, data, parent=None,
                 debug=False, sort_first_column=False, view=None):
        super(TreeModel, self).__init__(parent)
        self.rootItem = TreeNode(headers)
        self.parents = [self.rootItem]
        self.indentations = [0]
        self.debug = debug
        self.sort_first_column = sort_first_column
        self.view = view                # reference to the tree view
        self.first_build = True
        self.expand_indexes = []
        if data=={}:
            data={"None":""}
        self.createData(data, -1)

        # expand lists only on first build
        if self.view and self.expand_indexes:
            for idx in self.expand_indexes:
                self.view.expand(idx)
        self.first_build = False

    # --------------------------
    # Refresh with new data
    # --------------------------
    def updateData(self, new_data):
        expanded = set()
        if self.view:
            expanded = self._get_expanded_keys()

        self.beginResetModel()
        self.rootItem = TreeNode(self.rootItem.itemData)  # keep headers
        self.parents = [self.rootItem]
        self.indentations = [0]
        self.expand_indexes = []
        if new_data=={}:
            new_data={"None":""}
        self.createData(new_data, -1)
        self.endResetModel()

        if self.view:
            self._restore_expanded_keys(expanded)

    # --------------------------
    # Expansion helpers
    # --------------------------
    def _get_expanded_keys(self):
        expanded = set()

        def recurse(parent_index=QModelIndex()):
            for row in range(self.rowCount(parent_index)):
                idx = self.index(row, 0, parent_index)
                if self.view.isExpanded(idx):
                    expanded.add(self.data(idx, Qt.DisplayRole))
                recurse(idx)
        recurse()
        return expanded

    def _restore_expanded_keys(self, expanded):
        def recurse(parent_index=QModelIndex()):
            for row in range(self.rowCount(parent_index)):
                idx = self.index(row, 0, parent_index)
                if self.data(idx, Qt.DisplayRole) in expanded:
                    self.view.expand(idx)
                recurse(idx)
        recurse()

    # --------------------------
    # Data creation
    # --------------------------
    def createData(self, data, indent):
        if isinstance(data, dict):
            indent += 1
            position = 4 * indent
            for dict_keys, dict_values in data.items():
                if position > self.indentations[-1]:
                    if self.parents[-1].childCount() > 0:
                        self.parents.append(
                            self.parents[-1].child(self.parents[-1].childCount() - 1)
                        )
                        self.indentations.append(position)
                else:
                    while position < self.indentations[-1] and len(self.parents) > 0:
                        self.parents.pop()
                        self.indentations.pop()

                parent = self.parents[-1]
                parent.insertChildren(parent.childCount(), 1, parent.columnCount())
                new_item = parent.child(parent.childCount() - 1)
                new_item.setData(0, dict_keys)

                if isinstance(dict_values, dict):
                    new_item.setData(1, "{dict}")
                    self.createData(dict_values, indent)

                elif isinstance(dict_values, (list, tuple)):
                    new_item.setData(1, f"list[{len(dict_values)}]")
                    for i, val in enumerate(dict_values):
                        new_item.insertChildren(new_item.childCount(), 1, new_item.columnCount())
                        child_item = new_item.child(new_item.childCount() - 1)
                        child_item.setData(0, f"[{i}]")
                        child_item.setData(1, str(val))

                    # mark for expansion on very first build
                    if self.first_build and self.view:
                        parent_idx = (
                            QModelIndex()
                            if parent == self.rootItem else
                            self.index(parent.childNumber(), 0)
                        )
                        idx = self.index(new_item.childNumber(), 0, parent_idx)
                        if idx.isValid():
                            self.expand_indexes.append(idx)

                else:
                    new_item.setData(1, str(dict_values))

            if self.sort_first_column:
                parent.sortChildren()

    # --------------------------
    # Required model methods
    # --------------------------
    def index(self, row, column, index=QModelIndex()):
        if not self.hasIndex(row, column, index):
            return QModelIndex()
        parent_item = index.internalPointer() if index.isValid() else self.rootItem
        child = parent_item.child(row)
        if child:
            return self.createIndex(row, column, child)
        return QModelIndex()

    def parent(self, index):
        if not index.isValid():
            return QModelIndex()
        item = index.internalPointer()
        if not item:
            return QModelIndex()
        parent = item.parentItem
        if parent == self.rootItem:
            return QModelIndex()
        return self.createIndex(parent.childNumber(), 0, parent)

    def rowCount(self, index=QModelIndex()):
        parent = index.internalPointer() if index.isValid() else self.rootItem
        return parent.childCount()

    def columnCount(self, index=QModelIndex()):
        return self.rootItem.columnCount()

    def data(self, index, role=Qt.DisplayRole):
        if index.isValid() and role == Qt.DisplayRole:
            return index.internalPointer().data(index.column())
        elif not index.isValid():
            return self.rootItem.data(index.column())

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.rootItem.data(section)


class TreeNode:
    def __init__(self, data, parent=None):
        self.parentItem = parent
        self.itemData = list(data)
        self.children = []

    def child(self, row):
        return self.children[row]

    def childCount(self):
        return len(self.children)

    def childNumber(self):
        if self.parentItem is not None:
            return self.parentItem.children.index(self)

    def columnCount(self):
        return len(self.itemData)

    def data(self, column):
        return self.itemData[column]

    def insertChildren(self, position, count, columns):
        if position < 0 or position > len(self.children):
            return False
        for _ in range(count):
            data = ["" for _ in range(columns)]
            item = TreeNode(data, self)
            self.children.insert(position, item)
        return True

    def parent(self):
        return self.parentItem

    def setData(self, column, value):
        if 0 <= column < len(self.itemData):
            self.itemData[column] = value
            return True
        return False

    def sortChildren(self):
        self.children.sort(key=lambda c: str(c.itemData[0]).lower())
