'''Custom Widgets
'''
from typing import Dict, List

from PyQt5 import  QtWidgets, QtCore


class IntArrayEdit(QtWidgets.QWidget):
    """Integer Array Editor

    """
    onModified = QtCore.pyqtSignal()

    def __init__(self,
                 parent: QtWidgets.QWidget) -> None:
        super().__init__(parent)

        self.__frame = QtWidgets.QGridLayout(self)

        self.__scroll_area = QtWidgets.QScrollArea(self, widgetResizable=True)
        self.__frame.addWidget(self.__scroll_area,
                               0,   # row
                               0,   # column
                               1,   # rowSpan
                               2)   # columnSpan

        self.__entry_holder_widget = QtWidgets.QWidget(self)
        self.__entry_layout = QtWidgets.QFormLayout(self.__entry_holder_widget)
        self.__entry_holder_widget.setLayout(self.__entry_layout)
        self.__scroll_area.setWidget(self.__entry_holder_widget)

        self.__add_btn = QtWidgets.QPushButton('Add Entry', self)
        self.__add_btn.clicked.connect(self.add_entry)
        # self.__add_btn.setEnabled(False)
        self.__frame.addWidget(self.__add_btn,
                               1,
                               0,
                               1,
                               1)

        self.__clear_btn = QtWidgets.QPushButton('Clear Entries', self)
        self.__clear_btn.clicked.connect(self.clear_entries)
        # self.__clear_btn.setEnabled(False)
        self.__frame.addWidget(self.__clear_btn,
                               1,
                               1,
                               1,
                               1)

        self.__entries: Dict[int, QtWidgets.QLineEdit] = {}

    def set_values(self, values: List[int]) -> None:
        """Sets the current values

        Args:
            values (List[int]): List of values to set
        """
        for row_idx, value in enumerate(values):
            self.__create_new_entry(row_idx, value)

    def __create_new_entry(self, row_idx: int, value: int):
        entry_label = QtWidgets.QLabel(f'Entry {row_idx + 1}')
        entry = QtWidgets.QLineEdit()
        entry.setText(str(value))

        row_layout = QtWidgets.QHBoxLayout()
        row_layout.addWidget(entry_label)
        row_layout.addWidget(entry)
        new_row = QtWidgets.QWidget()
        new_row.setLayout(row_layout)
        self.__entry_layout.addRow(new_row)

        self.__entries[row_idx] = entry
        entry.textChanged.connect(self.onModified.emit)

    def get_values(self) -> List[int]:
        """Get current values

        Returns:
            List[int]: List of current values
        """
        value_map: Dict[int, int] = {}
        for idx, entry in self.__entries.items():
            try:
                value = int(entry.text())
            except ValueError:
                continue
            value_map[idx] = value
        keys = sorted(list(self.__entries.keys()))
        return [value_map[key] for key in keys]

    def add_entry(self) -> None:
        """Adds a new entry via dialog
        """
        new_value, dialog_result = QtWidgets.QInputDialog.getInt(self,
                                                                 'Add Entry',
                                                                 'Entry')
        if not dialog_result:
            return

        new_idx = len(self.__entries)
        self.__create_new_entry(new_idx, new_value)
        self.onModified.emit()

    def clear_entries(self) -> None:
        """Clears all entries
        """
        while self.__entry_layout.count() > 0:
            child = self.__entry_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.__entries = {}
        self.onModified.emit()
