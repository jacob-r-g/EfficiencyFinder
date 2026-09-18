"""Nuclease-specific PAM / cut / WT-window geometry."""

from __future__ import annotations

NUCLEASE_CAS9 = "cas9"
NUCLEASE_CAS12 = "cas12"
VALID_NUCLEASES = frozenset({NUCLEASE_CAS9, NUCLEASE_CAS12})


def normalize_nuclease(value: str | None) -> str:
    name = (value or NUCLEASE_CAS9).strip().lower().replace(" ", "")
    if name in {"cas9", "spcas9", "cas-9"}:
        return NUCLEASE_CAS9
    if name in {"cas12", "cas12a", "cpf1", "cas-12"}:
        return NUCLEASE_CAS12
    raise ValueError(f"unknown nuclease: {value!r} (expected cas9 or cas12)")


def guide_geometry(
    *,
    nuclease: str,
    pos: int,
    guide_len: int,
    strand: str,
) -> tuple[int, int, int]:
    """Return (cut_pos, wt_start, wt_end) in amplicon forward coordinates.

    cut_pos: 0-based index such that the guide-strand cut lies between
    cut_pos-1 and cut_pos (used for paired-excision distances).

    wt_start:wt_end: half-open window that must match reference for WT.
    """
    nuclease = normalize_nuclease(nuclease)
    if nuclease == NUCLEASE_CAS9:
        pam_len = 3
        spacer_len = max(0, guide_len - pam_len)
        if strand == "+":
            # Guide = spacer + NGG; cut 3 bp upstream of PAM (spacer 17–18).
            cut_pos = pos + max(0, spacer_len - pam_len)
        else:
            # RC match: PAM at 5' of forward window; cut offset mirrored.
            cut_pos = pos + guide_len - max(0, spacer_len - pam_len)
        return cut_pos, cut_pos - 3, cut_pos + 3

    # Cas12a: guide FASTA = 4 bp PAM (as written; not a fixed TTTV motif) + spacer.
    # Guide-strand cut between spacer 17–18; WT window = spacer 16–23.
    pam_len = 4
    spacer_len = max(0, guide_len - pam_len)
    if spacer_len < 23:
        # Degenerate short guides: fall back to whole spacer after PAM.
        if strand == "+":
            cut_pos = pos + pam_len + min(17, max(0, spacer_len))
            wt_start = pos + pam_len
            wt_end = pos + guide_len
        else:
            cut_pos = pos + max(0, spacer_len - 17)
            wt_start = pos
            wt_end = pos + spacer_len
        return cut_pos, wt_start, wt_end

    if strand == "+":
        # PAM at 5' (low coordinate).
        cut_pos = pos + pam_len + 17
        wt_start = pos + pam_len + 15  # spacer 16
        wt_end = pos + pam_len + 23  # exclusive after spacer 23
    else:
        # amp = RC(spacer)+RC(PAM); spacer pos k at pos + spacer_len - k.
        cut_pos = pos + spacer_len - 17
        wt_start = pos + spacer_len - 23  # spacer 23 .. 16 on forward
        wt_end = pos + spacer_len - 15
    return cut_pos, wt_start, wt_end
