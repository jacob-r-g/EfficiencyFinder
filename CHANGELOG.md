# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2026-09

### Removed

- macOS desktop distribution (PySide6 `gui/`, `main.py`, `EfficiencyFinder.app`, setup scripts, and `START HERE.txt`). The web app is the supported interface.

## [1.5.1] - 2026-09

### Changed

- Alleles tab shows deletions as `N` versus WT for clearer chimerism views.

## [1.5.0] - 2026-09

### Added

- Efficiency Inspect panel: annotated reference and capped WT/edited example reads for a selected efficiency row.

## [1.4.1] - 2026-09

### Fixed

- Cas12 job start accepts string-valued settings from the web UI.

## [1.4.0] - 2026-09

### Added

- SpCas9 / Cas12a nuclease selector in desktop and web UIs.
- Cas12 FASTA conventions and spacer-local WT windows (positions 16–23).

## [1.3.0] - 2026-08

### Changed

- Efficiency uses a cut-local WT window (Cas9: 3 bp up + 3 bp down) instead of a wider hard-coded span.

## [1.2.1] - 2026-08

### Added

- Export unassigned reads as FASTQ for BLAST / QC.

## [1.2.0] - 2026-08

### Added

- Assignment tab: assigned vs unassigned counts per sample and amplicon.

## [1.0.0] - 2026-08

### Added

- Desktop PySide6 app and shared `core/` analysis engine.
- Web app (FastAPI + React) with chunked uploads, Docker image, and deploy script.
- Tabs for efficiency, indel & frame, alleles, and paired-guide excision.
