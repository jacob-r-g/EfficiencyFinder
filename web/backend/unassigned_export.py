"""Write unassigned read FASTQs for BLAST / off-target inspection."""

from __future__ import annotations

import re
from pathlib import Path

from core.parsing import write_fastq
from core.pipeline import SampleResult

_SAFE_SAMPLE = re.compile(r"[^A-Za-z0-9._-]+")


def safe_sample_slug(sample_name: str) -> str:
    slug = _SAFE_SAMPLE.sub("_", sample_name.strip())
    return slug[:80] or "sample"


def write_unassigned_exports(
    samples: list[SampleResult], export_dir: Path
) -> list[dict]:
    """Write one FASTQ per sample with unassigned reads. Returns download metadata."""
    export_dir.mkdir(parents=True, exist_ok=True)
    out: list[dict] = []
    used: set[str] = set()
    for s in samples:
        if not s.unassigned_reads:
            continue
        slug = safe_sample_slug(s.sample_name)
        base = f"unassigned_{slug}.fastq"
        fname = base
        n = 2
        while fname in used:
            fname = f"unassigned_{slug}_{n}.fastq"
            n += 1
        used.add(fname)
        write_fastq(str(export_dir / fname), s.unassigned_reads)
        out.append(
            {
                "sample_name": s.sample_name,
                "n_reads": len(s.unassigned_reads),
                "filename": fname,
            }
        )
    return out
