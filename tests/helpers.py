"""Shared synthetic sequences for unit tests."""

from __future__ import annotations

import random
from pathlib import Path


def random_dna(n: int, seed: int) -> str:
    rng = random.Random(seed)
    return "".join(rng.choice("ACGT") for _ in range(n))


# 23 bp protospacer+PAM (example from the build spec)
GUIDE1 = "CCACTTCGGCTAGCCGAATGGGA"
GUIDE2 = "GATTACAACGTACGTACGTACGG"

LEFT = random_dna(200, seed=1)
MID = random_dna(80, seed=2)
RIGHT = random_dna(200, seed=3)

# Amp1: single guide at offset 200
AMP1 = LEFT + GUIDE1 + RIGHT
AMP1_NAME = "Amp1"
GUIDE1_NAME = "Amp1_G1"
GUIDE1_START = 200
GUIDE1_END = 223

# Amp2: two guides, used for paired-guide / N-guide tests
AMP2 = LEFT + GUIDE1 + MID + GUIDE2 + RIGHT
AMP2_NAME = "Line26"
GUIDE2A_NAME = "Line26_G1"
GUIDE2B_NAME = "Line26_G2"


def write_fasta(path: Path, entries: dict[str, str]) -> Path:
    with open(path, "w") as f:
        for name, seq in entries.items():
            f.write(f">{name}\n")
            if seq:
                for i in range(0, len(seq), 80):
                    f.write(seq[i : i + 80] + "\n")
            # empty sequence: header only, no sequence lines
    return path


def write_fastq(path: Path, reads: list[tuple[str, str]]) -> Path:
    with open(path, "w") as f:
        for read_id, seq in reads:
            f.write(f"@{read_id}\n{seq}\n+\n{'I' * len(seq)}\n")
    return path


def valid_single_guide_fasta(path: Path) -> Path:
    return write_fasta(path, {AMP1_NAME: AMP1, GUIDE1_NAME: GUIDE1})


def valid_two_guide_fasta(path: Path) -> Path:
    return write_fasta(
        path,
        {
            AMP2_NAME: AMP2,
            GUIDE2A_NAME: GUIDE1,
            GUIDE2B_NAME: GUIDE2,
        },
    )
