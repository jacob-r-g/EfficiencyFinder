"""Collapsible Advanced settings panel bound to PipelineSettings."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from core.settings import PipelineSettings

_FIELDS = [
    # (attr, label, tooltip, kind, min, max, step)
    (
        "k_classify",
        "Classification k-mer",
        "k-mer length for read-to-amplicon classification.",
        "int",
        5,
        51,
        1,
    ),
    (
        "min_classify_score",
        "Min classify score",
        "Minimum shared k-mers to confidently assign a read to an amplicon.",
        "int",
        1,
        500,
        1,
    ),
    (
        "flank",
        "Flank (bp)",
        "Flank length on each side of the guide used for WT/edited calling.",
        "int",
        5,
        200,
        1,
    ),
    (
        "mismatch_thresh_flank",
        "Flank mismatch max",
        "Max mismatches allowed when matching a flank sequence.",
        "int",
        0,
        20,
        1,
    ),
    (
        "mismatch_thresh_target",
        "Target mismatch max",
        "Max mismatches allowed in the target sequence for a WT call.",
        "int",
        0,
        20,
        1,
    ),
    (
        "k_span",
        "Coverage k-mer",
        "k-mer length for presence-based coverage checks around the guide bracket.",
        "int",
        5,
        51,
        1,
    ),
    (
        "coverage_margin",
        "Coverage margin (bp)",
        "Extra bp beyond the flanks of all guides for the outer coverage bracket.",
        "int",
        0,
        200,
        1,
    ),
    (
        "mismatch_fraction",
        "Anchor mismatch fraction",
        "Max fraction of indel-sizing anchor length allowed to mismatch.",
        "float",
        0.0,
        1.0,
        0.01,
    ),
    (
        "max_extra",
        "Max anchor extra (bp)",
        "Cap on how far the indel-sizing anchor search will extend.",
        "int",
        25,
        2000,
        25,
    ),
    (
        "artifact_size_threshold",
        "Artifact size threshold (bp)",
        "Net indel sizes beyond this are treated as nanopore concatemer artifacts, not real edits.",
        "int",
        10,
        5000,
        10,
    ),
    (
        "min_allele_reads",
        "Min allele reads",
        "Minimum read count for a confident allele call.",
        "int",
        1,
        100,
        1,
    ),
    (
        "merge_edit_dist",
        "Allele merge distance",
        "Max Levenshtein distance to merge a noisy read into a confident allele.",
        "int",
        0,
        10,
        1,
    ),
    (
        "min_excision_bp",
        "Min paired excision (bp)",
        "Minimum outer-flank dropout (bp) to confirm a paired-guide excision size.",
        "int",
        1,
        2000,
        5,
    ),
    (
        "min_excision_fraction",
        "Min excision fraction",
        "Confirmed paired excision must drop at least this fraction of the expected intervening span.",
        "float",
        0.0,
        1.0,
        0.05,
    ),
]


class SettingsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._widgets: dict[str, QSpinBox | QDoubleSpinBox] = {}

        self._toggle = QToolButton()
        self._toggle.setText("Advanced settings")
        self._toggle.setCheckable(True)
        self._toggle.setChecked(False)
        self._toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._toggle.setArrowType(Qt.ArrowType.RightArrow)
        self._toggle.setStyleSheet("QToolButton { border: none; font-weight: 600; }")
        self._toggle.toggled.connect(self._on_toggled)

        self._body = QFrame()
        self._body.setVisible(False)
        self._body.setFrameShape(QFrame.Shape.StyledPanel)

        left = QFormLayout()
        right = QFormLayout()
        defaults = PipelineSettings()
        for i, spec in enumerate(_FIELDS):
            attr, label, tip, kind, lo, hi, step = spec
            if kind == "float":
                w = QDoubleSpinBox()
                w.setDecimals(2)
                w.setRange(lo, hi)
                w.setSingleStep(step)
                w.setValue(getattr(defaults, attr))
            else:
                w = QSpinBox()
                w.setRange(int(lo), int(hi))
                w.setSingleStep(int(step))
                w.setValue(int(getattr(defaults, attr)))
            w.setToolTip(tip)
            w.setKeyboardTracking(False)
            self._widgets[attr] = w
            (left if i < (len(_FIELDS) + 1) // 2 else right).addRow(label, w)

        body_layout = QHBoxLayout(self._body)
        body_layout.addLayout(left, 1)
        body_layout.addLayout(right, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._toggle)
        layout.addWidget(self._body)

    def _on_toggled(self, checked: bool) -> None:
        self._body.setVisible(checked)
        self._toggle.setArrowType(
            Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow
        )

    def settings(self) -> PipelineSettings:
        vals = {}
        for attr, w in self._widgets.items():
            vals[attr] = w.value()
        return PipelineSettings(**vals)
