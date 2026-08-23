"""Top-level window: file panel, settings, results, progress."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from .file_panel import FilePanel
from .results_view import ResultsView
from .run_worker import RunWorker
from .settings_panel import SettingsPanel


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CRISPR Amplicon Editing Efficiency")
        self.resize(1280, 820)
        self._worker: RunWorker | None = None

        self.file_panel = FilePanel()
        self.settings_panel = SettingsPanel()
        self.results = ResultsView()

        top = QWidget()
        top_layout = QVBoxLayout(top)
        top_layout.addWidget(self.file_panel)
        top_layout.addWidget(self.settings_panel)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(top)
        splitter.addWidget(self.results)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([280, 540])

        self.setCentralWidget(splitter)

        self._progress = QProgressBar()
        self._progress.setMinimumWidth(180)
        self._progress.setMaximumHeight(16)
        self._progress.setTextVisible(False)
        self._progress.setVisible(False)
        self._status_label = QLabel("Select a reference FASTA and one or more FASTQ files, then click Run analysis.")

        status = QStatusBar()
        status.addWidget(self._status_label, 1)
        status.addPermanentWidget(self._progress)
        self.setStatusBar(status)

        self.file_panel.run_requested.connect(self._start_run)
        self._build_menu()
        self.setStyleSheet(
            """
            QLabel#hintLabel { color: #666; font-size: 11px; }
            QPushButton#runButton { font-weight: 600; padding: 6px 18px; }
            """
        )

    def _build_menu(self) -> None:
        quit_action = QAction("Quit", self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self.close)
        self.menuBar().addMenu("&File").addAction(quit_action)

    def _start_run(self) -> None:
        fasta = self.file_panel.fasta_path()
        fastqs = self.file_panel.fastq_paths()
        if not fasta or not fastqs:
            QMessageBox.warning(
                self,
                "Missing files",
                "Choose a reference FASTA and at least one FASTQ file.",
            )
            return
        if self._worker is not None and self._worker.isRunning():
            return

        self.results.clear()
        self.file_panel.set_running(True)
        self.settings_panel.setEnabled(False)
        self._progress.setVisible(True)
        self._progress.setRange(0, len(fastqs))
        self._progress.setValue(0)
        self._status_label.setText("Loading reference FASTA…")

        worker = RunWorker(fasta, fastqs, self.settings_panel.settings(), parent=self)
        worker.progress.connect(self._on_progress)
        worker.sample_finished.connect(self.results.append_sample)
        worker.batch_finished.connect(self._on_batch_finished)
        worker.failed.connect(self._on_failed)
        self._worker = worker
        worker.start()

    def _on_progress(
        self,
        i: int,
        n: int,
        sample_name: str,
        stage: str = "",
        stage_i: int = 0,
        stage_n: int = 0,
    ) -> None:
        if stage_n > 0:
            self._progress.setRange(0, n * stage_n)
            self._progress.setValue((i - 1) * stage_n + max(stage_i, 1))
        else:
            self._progress.setRange(0, n)
            self._progress.setValue(i - 1)
        label = f"Processing sample {i} of {n}: {sample_name}"
        if stage:
            label = f"{label} — {stage}"
        self._status_label.setText(label)

    def _on_batch_finished(self, batch) -> None:
        self.results.set_batch(batch)
        self._progress.setValue(self._progress.maximum())
        self._status_label.setText(
            f"Done. {len(batch.samples)} sample(s) · {batch.n_assigned:,} assigned reads · "
            f"{batch.n_unassigned:,} unassigned"
        )
        self._finish_run_ui()

    def _on_failed(self, message: str, tb: str, is_validation: bool) -> None:
        self._finish_run_ui()
        self._progress.setVisible(False)
        if is_validation:
            QMessageBox.critical(self, "FASTA validation error", message)
            self._status_label.setText("FASTA validation failed.")
            return
        self._status_label.setText("Run failed.")
        dlg = QDialog(self)
        dlg.setWindowTitle("Analysis error")
        dlg.resize(640, 420)
        layout = QVBoxLayout(dlg)
        layout.addWidget(QLabel(message))
        if tb:
            details = QPlainTextEdit()
            details.setReadOnly(True)
            details.setPlainText(tb)
            details.setVisible(False)
            toggle = QLabel('<a href="#">Show details</a>')
            toggle.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)

            def _toggle(_url=None):
                visible = not details.isVisible()
                details.setVisible(visible)
                toggle.setText('<a href="#">Hide details</a>' if visible else '<a href="#">Show details</a>')

            toggle.linkActivated.connect(_toggle)
            layout.addWidget(toggle)
            layout.addWidget(details, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(dlg.accept)
        layout.addWidget(buttons)
        dlg.exec()

    def _finish_run_ui(self) -> None:
        self.file_panel.set_running(False)
        self.settings_panel.setEnabled(True)
        self._progress.setVisible(False)

    def closeEvent(self, event) -> None:
        if self._worker is not None and self._worker.isRunning():
            answer = QMessageBox.question(
                self,
                "Analysis running",
                "An analysis is still running. Quit anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self._worker.terminate()
            self._worker.wait(2000)
        event.accept()
