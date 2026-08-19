"""QAbstractTableModel wrappers around pipeline row dicts."""

from __future__ import annotations

import csv
import math
from pathlib import Path

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtWidgets import QFileDialog, QTableView, QWidget


class DictTableModel(QAbstractTableModel):
    """Simple table model over a list of dicts with a fixed column order."""

    def __init__(self, columns: list[tuple[str, str]], parent=None):
        super().__init__(parent)
        self._columns = columns  # (key, header)
        self._rows: list[dict] = []

    def rowCount(self, parent=QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._rows)

    def columnCount(self, parent=QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._columns)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return self._columns[section][1]
        return section + 1

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        key = self._columns[index.column()][0]
        value = self._rows[index.row()].get(key)
        if role == Qt.ItemDataRole.DisplayRole:
            return _fmt(value)
        if role == Qt.ItemDataRole.UserRole:
            return value
        if role == Qt.ItemDataRole.TextAlignmentRole:
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return None

    def set_rows(self, rows: list[dict]) -> None:
        self.beginResetModel()
        self._rows = list(rows)
        self.endResetModel()

    def append_rows(self, rows: list[dict]) -> None:
        if not rows:
            return
        start = len(self._rows)
        self.beginInsertRows(QModelIndex(), start, start + len(rows) - 1)
        self._rows.extend(rows)
        self.endInsertRows()

    def rows(self) -> list[dict]:
        return list(self._rows)


def _fmt(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return "NA"
        if value == int(value) and abs(value) >= 10:
            return str(int(value))
        return f"{value:.1f}"
    return str(value)


def export_view_csv(view: QTableView, parent: QWidget | None = None, default_name: str = "export.csv") -> None:
    """Export currently visible (filtered/sorted) table rows to a user-chosen CSV."""
    path, _ = QFileDialog.getSaveFileName(
        parent,
        "Export CSV",
        default_name,
        "CSV files (*.csv);;All files (*)",
    )
    if not path:
        return
    if not path.lower().endswith(".csv"):
        path += ".csv"
    model = view.model()
    if model is None:
        return
    n_cols = model.columnCount()
    headers = [
        str(model.headerData(c, Qt.Orientation.Horizontal) or "")
        for c in range(n_cols)
    ]
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for r in range(model.rowCount()):
            writer.writerow(
                [
                    "" if model.index(r, c).data() is None else str(model.index(r, c).data())
                    for c in range(n_cols)
                ]
            )
