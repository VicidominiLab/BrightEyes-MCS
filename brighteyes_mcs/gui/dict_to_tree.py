# TreeModel inspired by
# https://stackoverflow.com/questions/60443167/qt-for-python-qtreeview-from-a-dictionary

from PySide6.QtCore import Qt, QAbstractItemModel, QModelIndex

class TreeModel(QAbstractItemModel):
    def __init__(self, headers, data, parent=None, debug=False):
        super(TreeModel, self).__init__(parent)
        """ subclassing the standard interface item models must use and 
                implementing index(), parent(), rowCount(), columnCount(), and data()."""

        rootData = [header for header in headers]
        self.rootItem = TreeNode(rootData)
        indent = -1
        self.parents = [self.rootItem]
        self.indentations = [0]
        self.createData(data, indent)
        self.debug = debug

    def createData(self, data, indent):
        if type(data) == dict:
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
                parent.child(parent.childCount() - 1).setData(0, dict_keys)

                if type(dict_values) != dict:
                    if type(dict_values) == list or type(dict_values) == tuple:  # ADDED
                        list_dict_values = dict_values
                    else:
                        list_dict_values = list(
                            (str(dict_values),),
                        )

                    for col, values in enumerate(list_dict_values):
                        parent.child(parent.childCount() - 1).setData(col + 1, values)
                    if len(list_dict_values) < self.columnCount():
                        for col in range(len(list_dict_values), self.columnCount()):
                            parent.child(parent.childCount() - 1).setData(col + 1, "")

                else:
                    parent.child(parent.childCount() - 1).setData(1, str(dict_values))
                self.createData(dict_values, indent)

    def index(self, row, column, index=QModelIndex()):
        """Returns the index of the item in the model specified by the given row, column and parent index"""

        if not self.hasIndex(row, column, index):
            return QModelIndex()
        if not index.isValid():
            item = self.rootItem
        else:
            item = index.internalPointer()

        child = item.child(row)
        if child:
            return self.createIndex(row, column, child)
        return QModelIndex()

    def parent(self, index):
        """Returns the parent of the model item with the given index
        If the item has no parent, an invalid QModelIndex is returned"""

        if not index.isValid():
            return QModelIndex()
        item = index.internalPointer()
        if not item:
            return QModelIndex()

        parent = item.parentItem
        if parent == self.rootItem:
            return QModelIndex()
        else:
            return self.createIndex(parent.childNumber(), 0, parent)

    def rowCount(self, index=QModelIndex()):
        """Returns the number of rows under the given parent
        When the parent is valid it means that rowCount is returning the number of children of parent
        """

        if index.isValid():
            parent = index.internalPointer()
        else:
            parent = self.rootItem
        return parent.childCount()

    def columnCount(self, index=QModelIndex()):
        """Returns the number of columns for the children of the given parent"""

        return self.rootItem.columnCount()

    def data(self, index, role=Qt.DisplayRole):
        """Returns the data stored under the given role for the item referred to by the index"""

        if index.isValid() and role == Qt.DisplayRole:
            return index.internalPointer().data(index.column())
        elif not index.isValid():
            return self.rootItem.data(index.column())

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        """Returns the data for the given role and section in the header with the specified orientation"""

        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.rootItem.data(section)


class TreeNode(object):
    def __init__(self, data, parent=None):
        self.parentItem = parent
        self.itemData = data
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
        for row in range(count):
            data = [v for v in range(columns)]
            item = TreeNode(data, self)
            self.children.insert(position, item)

    def parent(self):
        return self.parentItem

    def setData(self, column, value):
        if column < 0 or column >= len(self.itemData):
            return False
        self.itemData[column] = value
