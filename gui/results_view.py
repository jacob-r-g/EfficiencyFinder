"""Tabbed results: Efficiency / Indel & Frame / Alleles."""

from __future__ import annotations

from dataclasses import asdict

from PySide6.QtCore import QSortFilterProxyModel, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from core.indel_frame import export_indel_histogram
from core.pipeline import BatchResult, SampleResult
from .models import DictTableModel, export_view_csv

EFFICIENCY_COLS = [
    ("sample", "sample"),
    ("guide", "guide"),
    ("amplicon", "amplicon"),
    ("total_amplicon_reads", "total_amplicon_reads"),
    ("reads_spanning_target", "reads_spanning_target"),
    ("not_sequenced", "not_sequenced"),
    ("wt_unedited", "wt_unedited"),
    ("edited", "edited"),
    ("edited_insertion", "edited_insertion"),
    ("edited_deletion_small", "edited_deletion_small"),
    ("edited_deletion_large", "edited_deletion_large"),
    ("edited_substitution", "edited_substitution"),
    ("pct_editing", "pct_editing"),
]

INDEL_COLS = [
    ("sample", "sample"),
    ("guide", "guide"),
    ("amplicon", "amplicon"),
    ("n_reads_with_size_call", "n_reads_with_size_call"),
    ("wt", "wt"),
    ("edited", "edited"),
    ("pct_editing", "pct_editing"),
    ("insertions", "insertions"),
    ("deletions", "deletions"),
    ("in_frame", "in_frame"),
    ("frameshift", "frameshift"),
    ("pct_in_frame_of_edited", "pct_in_frame_of_edited"),
]

ALLELE_SUMMARY_COLS = [
    ("sample", "sample"),
    ("guide", "guide"),
    ("total_reads", "total_reads"),
    ("wt_reads", "wt_reads"),
    ("edited_reads", "edited_reads"),
    ("raw_unique_sequences", "raw_unique_sequences"),
    ("distinct_alleles_called", "distinct_alleles_called"),
    ("confident_alleles", "confident_alleles"),
    ("low_freq_alleles", "low_freq_alleles"),
    ("reads_merged_as_noise", "reads_merged_as_noise"),
    ("singleton_reads_excluded", "singleton_reads_excluded"),
]

ALLELE_DETAIL_COLS = [
    ("sample", "sample"),
    ("guide", "guide"),
    ("allele_rank", "allele_rank"),
    ("n_reads", "n_reads"),
    ("pct_of_edited", "pct_of_edited"),
    ("indel_size_bp", "indel_size_bp"),
    ("allele_seq", "allele_seq"),
    ("confident", "confident"),
]

SHARED_ALLELE_COLS = [
    ("guide", "guide"),
    ("n_samples", "n_samples"),
    ("samples", "samples"),
    ("indel_size_bp", "indel_size_bp"),
    ("allele_seq", "allele_seq"),
]

EXCISION_COLS = [
    ("sample", "sample"),
    ("amplicon", "amplicon"),
    ("guides", "guides"),
    ("n_guides", "n_guides"),
    ("expected_dropout_bp", "expected_dropout_bp"),
    ("n_spanning_reads", "n_spanning_reads"),
    ("n_simultaneous_large_del", "n_simultaneous_large_del"),
    ("pct_simultaneous_large_del", "pct_simultaneous_large_del"),
    ("n_confirmed_excision", "n_confirmed_excision"),
    ("pct_confirmed_excision", "pct_confirmed_excision"),
    ("median_excision_bp", "median_excision_bp"),
]

EXCISION_SIZE_COLS = [
    ("sample", "sample"),
    ("amplicon", "amplicon"),
    ("excision_size_bp", "excision_size_bp"),
    ("n_reads", "n_reads"),
    ("pct_of_confirmed", "pct_of_confirmed"),
]


class _FilterProxy(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._needle = ""
        self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setFilterKeyColumn(-1)
        self.setSortCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

    def setFilterFixedString(self, pattern: str) -> None:
        self._needle = (pattern or "").casefold()
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent) -> bool:
        if not self._needle:
            return True
        model = self.sourceModel()
        for col in range(model.columnCount()):
            text = str(model.index(source_row, col, source_parent).data() or "").casefold()
            if self._needle in text:
                return True
        return False


def _make_table(model: DictTableModel) -> tuple[QTableView, _FilterProxy]:
    proxy = _FilterProxy()
    proxy.setSourceModel(model)
    view = QTableView()
    view.setModel(proxy)
    view.setSortingEnabled(True)
    view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    view.setAlternatingRowColors(True)
    view.setWordWrap(False)
    view.horizontalHeader().setStretchLastSection(True)
    view.verticalHeader().setVisible(False)
    return view, proxy


class _TableTab(QWidget):
    def __init__(self, columns, export_name: str, extra_buttons=None, parent=None):
        super().__init__(parent)
        self.model = DictTableModel(columns)
        self.view, self.proxy = _make_table(self.model)
        self._export_name = export_name

        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Filter…")
        self.filter_edit.setClearButtonEnabled(True)
        self.filter_edit.textChanged.connect(self.proxy.setFilterFixedString)

        export_btn = QPushButton("Export CSV")
        export_btn.clicked.connect(self._export)

        top = QHBoxLayout()
        top.addWidget(QLabel("Filter"))
        top.addWidget(self.filter_edit, 1)
        if extra_buttons:
            for b in extra_buttons:
                top.addWidget(b)
        top.addWidget(export_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(top)
        layout.addWidget(self.view)

    def _export(self) -> None:
        export_view_csv(self.view, self, self._export_name)


class ResultsView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._batch: BatchResult | None = None
        self._all_details: list[dict] = []
        self._all_excision_sizes: list[dict] = []

        hist_btn = QPushButton("Export indel size histogram (PNG)")
        hist_btn.clicked.connect(self._export_histogram)
        self._hist_btn = hist_btn
        hist_btn.setEnabled(False)

        self.efficiency = _TableTab(EFFICIENCY_COLS, "efficiency.csv")
        self.indel = _TableTab(
            INDEL_COLS, "indel_frame.csv", extra_buttons=[hist_btn]
        )

        self.allele_summary = _TableTab(ALLELE_SUMMARY_COLS, "alleles_summary.csv")
        self.allele_detail_model = DictTableModel(ALLELE_DETAIL_COLS)
        self.allele_detail_view, self.allele_detail_proxy = _make_table(
            self.allele_detail_model
        )
        detail_filter = QLineEdit()
        detail_filter.setPlaceholderText("Filter allele details…")
        detail_filter.setClearButtonEnabled(True)
        detail_filter.textChanged.connect(self.allele_detail_proxy.setFilterFixedString)
        detail_export = QPushButton("Export details CSV")
        detail_export.clicked.connect(
            lambda: export_view_csv(
                self.allele_detail_view, self, "alleles_details.csv"
            )
        )
        detail_top = QHBoxLayout()
        self._detail_label = QLabel("Allele details (select a summary row)")
        detail_top.addWidget(self._detail_label, 1)
        detail_top.addWidget(detail_filter, 1)
        detail_top.addWidget(detail_export)
        detail_wrap = QWidget()
        detail_layout = QVBoxLayout(detail_wrap)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.addLayout(detail_top)
        detail_layout.addWidget(self.allele_detail_view)

        allele_split = QSplitter(Qt.Orientation.Vertical)
        allele_split.addWidget(self.allele_summary)
        allele_split.addWidget(detail_wrap)
        allele_split.setStretchFactor(0, 1)
        allele_split.setStretchFactor(1, 1)

        self.shared = _TableTab(SHARED_ALLELE_COLS, "shared_alleles.csv")

        self.excision = _TableTab(EXCISION_COLS, "paired_excision.csv")
        self.excision_size_model = DictTableModel(EXCISION_SIZE_COLS)
        self.excision_size_view, self.excision_size_proxy = _make_table(
            self.excision_size_model
        )
        size_filter = QLineEdit()
        size_filter.setPlaceholderText("Filter excision sizes…")
        size_filter.setClearButtonEnabled(True)
        size_filter.textChanged.connect(self.excision_size_proxy.setFilterFixedString)
        size_export = QPushButton("Export sizes CSV")
        size_export.clicked.connect(
            lambda: export_view_csv(
                self.excision_size_view, self, "paired_excision_sizes.csv"
            )
        )
        size_top = QHBoxLayout()
        self._excision_size_label = QLabel(
            "Confirmed excision sizes (select a summary row)"
        )
        size_top.addWidget(self._excision_size_label, 1)
        size_top.addWidget(size_filter, 1)
        size_top.addWidget(size_export)
        size_wrap = QWidget()
        size_layout = QVBoxLayout(size_wrap)
        size_layout.setContentsMargins(0, 0, 0, 0)
        size_layout.addLayout(size_top)
        size_layout.addWidget(self.excision_size_view)
        excision_split = QSplitter(Qt.Orientation.Vertical)
        excision_split.addWidget(self.excision)
        excision_split.addWidget(size_wrap)
        excision_split.setStretchFactor(0, 1)
        excision_split.setStretchFactor(1, 1)

        allele_tabs = QTabWidget()
        allele_tabs.addTab(allele_split, "Per sample")
        allele_tabs.addTab(self.shared, "Shared across samples")

        self.tabs = QTabWidget()
        self.tabs.addTab(self.efficiency, "Efficiency")
        self.tabs.addTab(self.indel, "Indel & Frame")
        self.tabs.addTab(allele_tabs, "Alleles")
        self.tabs.addTab(excision_split, "Paired excision")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.tabs)

        sel = self.allele_summary.view.selectionModel()
        sel.selectionChanged.connect(self._on_allele_summary_selected)
        ex_sel = self.excision.view.selectionModel()
        ex_sel.selectionChanged.connect(self._on_excision_selected)

    def clear(self) -> None:
        self._batch = None
        self._all_details = []
        self._all_excision_sizes = []
        self.efficiency.model.set_rows([])
        self.indel.model.set_rows([])
        self.allele_summary.model.set_rows([])
        self.allele_detail_model.set_rows([])
        self.shared.model.set_rows([])
        self.excision.model.set_rows([])
        self.excision_size_model.set_rows([])
        self._hist_btn.setEnabled(False)
        self._detail_label.setText("Allele details (select a summary row)")
        self._excision_size_label.setText(
            "Confirmed excision sizes (select a summary row)"
        )

    def append_sample(self, sample: SampleResult) -> None:
        self.efficiency.model.append_rows([asdict(r) for r in sample.efficiencies])
        self.indel.model.append_rows([asdict(r) for r in sample.indel_summaries])
        self.allele_summary.model.append_rows(
            [asdict(r) for r in sample.allele_summaries]
        )
        self._all_details.extend(asdict(r) for r in sample.allele_details)
        self.excision.model.append_rows([asdict(r) for r in sample.excision_summaries])
        self._all_excision_sizes.extend(asdict(r) for r in sample.excision_sizes)

    def set_batch(self, batch: BatchResult) -> None:
        self._batch = batch
        self.shared.model.set_rows([asdict(r) for r in batch.shared_alleles])
        self._hist_btn.setEnabled(True)

    def _on_allele_summary_selected(self) -> None:
        indexes = self.allele_summary.view.selectionModel().selectedRows()
        if not indexes:
            self.allele_detail_model.set_rows([])
            return
        src = self.allele_summary.proxy.mapToSource(indexes[0])
        row = self.allele_summary.model.rows()[src.row()]
        sample = row.get("sample")
        guide = row.get("guide")
        details = [
            d
            for d in self._all_details
            if d.get("sample") == sample and d.get("guide") == guide
        ]
        self.allele_detail_model.set_rows(details)
        self._detail_label.setText(f"Allele details — {sample} / {guide}")

    def _on_excision_selected(self) -> None:
        indexes = self.excision.view.selectionModel().selectedRows()
        if not indexes:
            self.excision_size_model.set_rows([])
            return
        src = self.excision.proxy.mapToSource(indexes[0])
        row = self.excision.model.rows()[src.row()]
        sample = row.get("sample")
        amplicon = row.get("amplicon")
        sizes = [
            d
            for d in self._all_excision_sizes
            if d.get("sample") == sample and d.get("amplicon") == amplicon
        ]
        self.excision_size_model.set_rows(sizes)
        self._excision_size_label.setText(
            f"Confirmed excision sizes — {sample} / {amplicon}"
        )

    def _export_histogram(self) -> None:
        if self._batch is None:
            QMessageBox.information(self, "No results", "Run an analysis first.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export indel size histogram",
            "indel_size_histogram.png",
            "PNG images (*.png);;All files (*)",
        )
        if not path:
            return
        if not path.lower().endswith(".png"):
            path += ".png"
        try:
            export_indel_histogram(self._batch.indel_sizes, path)
        except Exception as exc:
            QMessageBox.critical(self, "Export failed", str(exc))
            return
        QMessageBox.information(self, "Saved", f"Histogram saved to:\n{path}")
