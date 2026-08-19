"""FASTQ batch (multi-select / drag-drop) + FASTA picker."""

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

FASTA_FILTER = "FASTA files (*.fasta *.fa *.fna *.fas);;All files (*)"
FASTQ_FILTER = "FASTQ files (*.fastq *.fq);;All files (*)"
FASTA_SUFFIXES = {".fasta", ".fa", ".fna", ".fas"}
FASTQ_SUFFIXES = {".fastq", ".fq"}


class FilePanel(QWidget):
    run_requested = Signal()
    selection_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

        self._fasta_edit = QLineEdit()
        self._fasta_edit.setPlaceholderText("Amplicon + guide FASTA…")
        self._fasta_edit.setReadOnly(True)

        fasta_browse = QPushButton("Browse…")
        fasta_browse.clicked.connect(self._pick_fasta)

        fasta_row = QHBoxLayout()
        fasta_row.addWidget(QLabel("Reference FASTA"))
        fasta_row.addWidget(self._fasta_edit, 1)
        fasta_row.addWidget(fasta_browse)

        self._fastq_list = QListWidget()
        self._fastq_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self._fastq_list.setMinimumHeight(90)
        self._fastq_list.setAlternatingRowColors(True)

        add_btn = QPushButton("Add FASTQ…")
        add_btn.clicked.connect(self._pick_fastq)
        self._remove_btn = QPushButton("Remove selected")
        self._remove_btn.clicked.connect(self._remove_selected)
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._clear_fastq)

        list_btns = QHBoxLayout()
        list_btns.addWidget(add_btn)
        list_btns.addWidget(self._remove_btn)
        list_btns.addWidget(clear_btn)
        list_btns.addStretch(1)

        self.run_btn = QPushButton("Run analysis")
        self.run_btn.setObjectName("runButton")
        self.run_btn.setEnabled(False)
        self.run_btn.setDefault(True)
        self.run_btn.clicked.connect(self.run_requested.emit)

        hint = QLabel("Tip: drop FASTA/FASTQ files onto this panel. Select multiple FASTQ files for a batch run.")
        hint.setObjectName("hintLabel")
        hint.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(fasta_row)
        layout.addWidget(QLabel("FASTQ samples"))
        layout.addWidget(self._fastq_list)
        layout.addLayout(list_btns)
        layout.addWidget(hint)
        run_row = QHBoxLayout()
        run_row.addStretch(1)
        run_row.addWidget(self.run_btn)
        layout.addLayout(run_row)

        self._fasta_edit.textChanged.connect(lambda _: self._refresh_run())
        self._fastq_list.model().rowsInserted.connect(lambda *_: self._refresh_run())
        self._fastq_list.model().rowsRemoved.connect(lambda *_: self._refresh_run())

    def fasta_path(self) -> str:
        return self._fasta_edit.text().strip()

    def fastq_paths(self) -> list[str]:
        return [
            self._fastq_list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self._fastq_list.count())
        ]

    def set_running(self, running: bool) -> None:
        self.setEnabled(not running)
        if not running:
            self.run_btn.setEnabled(self._can_run())

    def _can_run(self) -> bool:
        return bool(self.fasta_path()) and self._fastq_list.count() > 0

    def _refresh_run(self) -> None:
        self.run_btn.setEnabled(self._can_run())
        self.selection_changed.emit()

    def _pick_fasta(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select amplicon + guide FASTA", "", FASTA_FILTER)
        if path:
            self._fasta_edit.setText(path)

    def _pick_fastq(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Select FASTQ files", "", FASTQ_FILTER)
        self._add_fastqs(paths)

    def _add_fastqs(self, paths: list[str]) -> None:
        existing = set(self.fastq_paths())
        for path in paths:
            if not path or path in existing:
                continue
            item = QListWidgetItem(Path(path).name)
            item.setData(Qt.ItemDataRole.UserRole, path)
            item.setToolTip(path)
            self._fastq_list.addItem(item)
            existing.add(path)
        self._refresh_run()

    def _remove_selected(self) -> None:
        for item in self._fastq_list.selectedItems():
            self._fastq_list.takeItem(self._fastq_list.row(item))
        self._refresh_run()

    def _clear_fastq(self) -> None:
        self._fastq_list.clear()
        self._refresh_run()

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        urls = event.mimeData().urls()
        fastqs = []
        for url in urls:
            path = url.toLocalFile()
            suffix = Path(path).suffix.lower()
            if suffix in FASTA_SUFFIXES:
                self._fasta_edit.setText(path)
            elif suffix in FASTQ_SUFFIXES:
                fastqs.append(path)
        if fastqs:
            self._add_fastqs(fastqs)
        event.acceptProposedAction()
