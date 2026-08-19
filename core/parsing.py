"""FASTA / FASTQ parsing and amplicon+guide FASTA validation."""

from dataclasses import dataclass


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


def parse_fastq(path: str) -> list[tuple[str, str]]:
    """Parse a FASTQ file into a list of (read_id, sequence). Quality lines discarded."""
    reads = []
    with open(path) as f:
        while True:
            h = f.readline()
            if not h:
                break
            s = f.readline().strip().upper()
            f.readline()  # '+' line
            f.readline()  # quality line
            reads.append((h.strip()[1:], s))
    return reads


@dataclass
class GuideInfo:
    name: str
    amplicon: str
    target: str  # forward-strand sequence at the target locus
    target_start: int
    target_end: int
    left_flank: str
    right_flank: str


@dataclass
class ReferenceSet:
    amplicons: dict[str, str]
    guides: dict[str, GuideInfo]
    guides_by_amplicon: dict[str, list[str]]


def load_reference_set(fasta_path: str, flank: int = 25) -> ReferenceSet:
    """Parse and validate the combined amplicon+guide FASTA."""
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
        else:
            pos = amp.find(revcomp(gseq))
            if pos < 0:
                raise FastaValidationError(
                    f"Guide '{gname}' ({gseq}) was not found in amplicon '{ampname}' "
                    f"on either strand. Check that the guide sequence is an exact "
                    f"substring of the amplicon (protospacer+PAM, typically 23bp)."
                )
            target_seq = amp[pos : pos + len(gseq)]

        gi = GuideInfo(
            name=gname,
            amplicon=ampname,
            target=target_seq,
            target_start=pos,
            target_end=pos + len(target_seq),
            left_flank=amp[max(0, pos - flank) : pos],
            right_flank=amp[pos + len(target_seq) : pos + len(target_seq) + flank],
        )
        guides[gname] = gi
        guides_by_amplicon[ampname].append(gname)

    return ReferenceSet(
        amplicons=amplicons, guides=guides, guides_by_amplicon=guides_by_amplicon
    )
