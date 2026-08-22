"""Concatenate multiple FASTQ files into one sample for a combined analysis."""

from __future__ import annotations

import shutil
from pathlib import Path

from core.parsing import _open_text


def combine_fastq_files(paths: list[Path], dest: Path) -> Path:
    """Write a single FASTQ at `dest` containing every read from `paths` in order.

    Plain and `.gz` inputs are both accepted (reads are written uncompressed).
    """
    if not paths:
        raise ValueError("no FASTQ files to combine")
    if len(paths) == 1:
        shutil.copyfile(paths[0], dest)
        return dest

    with dest.open("w") as out:
        for path in paths:
            with _open_text(str(path)) as src:
                shutil.copyfileobj(src, out)
    return dest
