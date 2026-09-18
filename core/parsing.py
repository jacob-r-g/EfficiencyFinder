"""FASTA / FASTQ parsing and amplicon+guide FASTA validation."""

import gzip
from dataclasses import dataclass
from pathlib import Path


class FastaValidationError(ValueError):
    """Raised when the amplicon+guide FASTA doesn't match the expected convention."""

    pass


def revcomp(s: str) -> str:
    comp = {"A": "T", "T": "A", "G": "C", "C": "G", "N": "N"}
    return "".join(comp.get(c, "N") for c in reversed(s))


def parse_fasta(path: str) -> dict[str, str]:
    """Parse a FASTA file into {header: sequence}."""
    entries, name, buf = {}, None, []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith(">"):
                if name is not None:
                    entries[name] = "".join(buf)
                name, buf = line[1:], []
            else:
                buf.append(line.upper())
        if name is not None:
            entries[name] = "".join(buf)
    return entries


def _open_text(path: str):
    """Open a text file, transparently decompressing `.gz`."""
    if path.endswith(".gz"):
        return gzip.open(path, "rt")
    return open(path)


def sample_name_from_path(path: str) -> str:
    """Basename without FASTA/FASTQ (and optional `.gz`) suffixes."""
    name = Path(path).name
    lower = name.lower()
    for suffix in (
        ".fastq.gz",
        ".fq.gz",
        ".fasta.gz",
        ".fa.gz",
        ".fastq",
        ".fq",
        ".fasta",
        ".fa",
        ".fna",
        ".fas",
    ):
        if lower.endswith(suffix):
            return name[: -len(suffix)]
    return Path(path).stem


def parse_fastq(path: str) -> list[tuple[str, str]]:
    """Parse a FASTQ file into a list of (read_id, sequence). Quality lines discarded."""
    reads = []
    with _open_text(path) as f:
        while True:
            h = f.readline()
            if not h:
                break
            s = f.readline().strip().upper()
            f.readline()  # '+' line
            f.readline()  # quality line
            reads.append((h.strip()[1:], s))
    return reads


def write_fastq(path: str, reads: list[tuple[str, str]]) -> None:
    """Write reads as a minimal FASTQ (dummy quality)."""
    with open(path, "w", encoding="utf-8") as f:
        for read_id, seq in reads:
            f.write(f"@{read_id}\n{seq}\n+\n{'I' * len(seq)}\n")


# SpCas9: NGG PAM is 3 bp; cut is 3 bp upstream of the PAM (between spacer nt 17–18).
# Cas12a geometry lives in core.nuclease (PAM 4 bp + staggered cuts).
PAM_LEN = 3


@dataclass
class GuideInfo:
    name: str
    amplicon: str
    target: str  # forward-strand sequence at the target locus
    target_start: int
    target_end: int
    left_flank: str
    right_flank: str
    cut_pos: int  # 0-based amplicon index of the guide-strand cut (between cut_pos-1 and cut_pos)
    wt_start: int  # half-open [wt_start, wt_end) window that must match for WT
    wt_end: int
    strand: str  # "+" if guide matches the amplicon forward strand, else "-"


@dataclass
class ReferenceSet:
    amplicons: dict[str, str]
    guides: dict[str, GuideInfo]
    guides_by_amplicon: dict[str, list[str]]
    nuclease: str = "cas9"


def load_reference_set(
    fasta_path: str, flank: int = 25, nuclease: str = "cas9"
) -> ReferenceSet:
    """Parse and validate the combined amplicon+guide FASTA."""
    from .nuclease import guide_geometry, normalize_nuclease

    nuclease = normalize_nuclease(nuclease)
    entries = parse_fasta(fasta_path)
    if not entries:
        raise FastaValidationError(f"No FASTA records found in '{fasta_path}'.")

    amplicons = {k: v for k, v in entries.items() if "_G" not in k}
    guide_seqs = {k: v for k, v in entries.items() if "_G" in k and len(v) > 0}

    if not amplicons:
        raise FastaValidationError(
            "No amplicon entries found. Amplicon headers must NOT contain '_G' "
            "(that substring is reserved for guide entries, e.g. '>MyAmplicon_G1')."
        )

    guides: dict[str, GuideInfo] = {}
    guides_by_amplicon: dict[str, list[str]] = {a: [] for a in amplicons}

    for gname, gseq in guide_seqs.items():
        ampname = gname.split("_G")[0]
        if ampname not in amplicons:
            raise FastaValidationError(
                f"Guide '{gname}' implies amplicon '{ampname}', but no amplicon with "
                f"that exact name was found. Guide entries must be named "
                f"'<AmpliconName>_G<id>', matching the amplicon header exactly "
                f"(check for typos, extra spaces, or case differences)."
            )
        amp = amplicons[ampname]
        pos = amp.find(gseq)
        if pos >= 0:
            target_seq = gseq
            strand = "+"
        else:
            pos = amp.find(revcomp(gseq))
            if pos < 0:
                raise FastaValidationError(
                    f"Guide '{gname}' ({gseq}) was not found in amplicon '{ampname}' "
                    f"on either strand. Check that the guide sequence is an exact "
                    f"substring of the amplicon (Cas9: protospacer+PAM; "
                    f"Cas12: 4 bp PAM + spacer)."
                )
            target_seq = amp[pos : pos + len(gseq)]
            strand = "-"

        cut_pos, wt_start, wt_end = guide_geometry(
            nuclease=nuclease, pos=pos, guide_len=len(gseq), strand=strand
        )
        if wt_start < 0 or wt_end > len(amp) or wt_start >= wt_end:
            raise FastaValidationError(
                f"Guide '{gname}' WT window [{wt_start}, {wt_end}) is outside "
                f"amplicon '{ampname}' (len {len(amp)}) for nuclease={nuclease}."
            )

        gi = GuideInfo(
            name=gname,
            amplicon=ampname,
            target=target_seq,
            target_start=pos,
            target_end=pos + len(target_seq),
            left_flank=amp[max(0, pos - flank) : pos],
            right_flank=amp[pos + len(target_seq) : pos + len(target_seq) + flank],
            cut_pos=cut_pos,
            wt_start=wt_start,
            wt_end=wt_end,
            strand=strand,
        )
        guides[gname] = gi
        guides_by_amplicon[ampname].append(gname)

    return ReferenceSet(
        amplicons=amplicons,
        guides=guides,
        guides_by_amplicon=guides_by_amplicon,
        nuclease=nuclease,
    )
