"""Orchestrates one sample end-to-end and batch runs across FASTQ files."""

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from math import nan

from .alleles import call_alleles_for_sample
from .classify import classify_reads
from .editing import GuideEfficiency, call_editing_status, summarize_efficiency
from .excision import ExcisionSizeRow, ExcisionSummary, call_paired_excisions
from .indel_frame import classify_frame, extract_allele
from .parsing import ReferenceSet, parse_fastq, sample_name_from_path
from .settings import PipelineSettings


def _pct(numer: int, denom: int) -> float:
    return round(100.0 * numer / denom, 1) if denom else nan


# Ordered stages inside one sample; used for determinate progress bars.
SAMPLE_STAGES = (
    "Reading FASTQ",
    "Classifying reads",
    "Calling editing",
    "Measuring indels & alleles",
    "Calling paired excision",
)


def _emit_progress(
    callback,
    sample_i: int,
    sample_n: int,
    sample: str,
    *,
    stage: str,
    stage_i: int,
    stage_n: int,
) -> None:
    if callback is None:
        return
    callback(
        sample_i,
        sample_n,
        sample,
        stage=stage,
        stage_i=stage_i,
        stage_n=stage_n,
    )


@dataclass
class IndelSummary:
    sample: str
    guide: str
    amplicon: str
    n_reads_with_size_call: int
    wt: int
    edited: int
    pct_editing: float
    insertions: int
    deletions: int
    in_frame: int
    frameshift: int
    pct_in_frame_of_edited: float


@dataclass
class IndelSizeObservation:
    """One size-callable read, keyed for per-sample / per-guide histograms."""

    sample: str
    guide: str
    indel_size_bp: int


@dataclass
class AlleleSummary:
    sample: str
    guide: str
    total_reads: int
    wt_reads: int
    edited_reads: int
    raw_unique_sequences: int
    distinct_alleles_called: int
    confident_alleles: int
    low_freq_alleles: int
    reads_merged_as_noise: int
    singleton_reads_excluded: int


@dataclass
class AlleleDetail:
    sample: str
    guide: str
    allele_rank: int
    n_reads: int
    pct_of_edited: float
    indel_size_bp: int
    allele_seq: str
    confident: bool


@dataclass
class SharedAllele:
    guide: str
    allele_seq: str
    indel_size_bp: int
    n_samples: int
    samples: str


@dataclass
class AmpliconAssignment:
    sample: str
    amplicon: str
    n_reads: int
    pct_of_sample: float


@dataclass
class SampleResult:
    sample_name: str
    fastq_path: str
    n_reads: int
    n_assigned: int
    n_unassigned: int
    amp_read_counts: dict[str, int]
    unassigned_reads: list[tuple[str, str]]
    efficiencies: list[GuideEfficiency]
    indel_summaries: list[IndelSummary]
    allele_summaries: list[AlleleSummary]
    allele_details: list[AlleleDetail]
    indel_size_obs: list[IndelSizeObservation]
    indel_sizes: list[int]  # flat sizes for PNG export (includes WT 0)
    excision_summaries: list[ExcisionSummary]
    excision_sizes: list[ExcisionSizeRow]


@dataclass
class BatchResult:
    samples: list[SampleResult]
    efficiencies: list[GuideEfficiency] = field(default_factory=list)
    indel_summaries: list[IndelSummary] = field(default_factory=list)
    allele_summaries: list[AlleleSummary] = field(default_factory=list)
    allele_details: list[AlleleDetail] = field(default_factory=list)
    shared_alleles: list[SharedAllele] = field(default_factory=list)
    indel_size_obs: list[IndelSizeObservation] = field(default_factory=list)
    indel_sizes: list[int] = field(default_factory=list)
    excision_summaries: list[ExcisionSummary] = field(default_factory=list)
    excision_sizes: list[ExcisionSizeRow] = field(default_factory=list)
    amplicon_assignments: list[AmpliconAssignment] = field(default_factory=list)
    n_reads: int = 0
    n_assigned: int = 0
    n_unassigned: int = 0


def _amplicon_assignments(samples: list[SampleResult]) -> list[AmpliconAssignment]:
    rows: list[AmpliconAssignment] = []
    for s in samples:
        for amp, count in sorted(s.amp_read_counts.items()):
            rows.append(
                AmpliconAssignment(
                    sample=s.sample_name,
                    amplicon=amp,
                    n_reads=count,
                    pct_of_sample=_pct(count, s.n_reads),
                )
            )
    return rows


def _analyze_guide_indels_and_alleles(
    classified,
    ref_set: ReferenceSet,
    settings: PipelineSettings,
    sample_name: str,
) -> tuple[
    list[IndelSummary],
    list[AlleleSummary],
    list[AlleleDetail],
    list[IndelSizeObservation],
]:
    indel_summaries: list[IndelSummary] = []
    allele_summaries: list[AlleleSummary] = []
    allele_details: list[AlleleDetail] = []
    hist_obs: list[IndelSizeObservation] = []

    for gname, gi in ref_set.guides.items():
        amp_seq = ref_set.amplicons[gi.amplicon]
        expected = gi.target_end - gi.target_start
        size_calls: list[tuple[str, int, str]] = []
        for cr in classified:
            if cr.amplicon != gi.amplicon:
                continue
            size, seq = extract_allele(
                cr.oriented_seq,
                amp_seq,
                gi.target_start,
                gi.target_end,
                mismatch_fraction=settings.mismatch_fraction,
                max_extra=settings.max_extra,
            )
            if size is None or seq is None:
                continue
            if abs(size) > settings.artifact_size_threshold:
                continue
            size_calls.append((cr.read_id, size, seq))
            hist_obs.append(
                IndelSizeObservation(
                    sample=sample_name, guide=gname, indel_size_bp=size
                )
            )

        n = len(size_calls)
        wt = sum(1 for _rid, z, _seq in size_calls if z == 0)
        edited = n - wt
        insertions = sum(1 for _rid, z, _seq in size_calls if z > 0)
        deletions = sum(1 for _rid, z, _seq in size_calls if z < 0)
        in_frame = sum(
            1 for _rid, z, _seq in size_calls if classify_frame(z) == "in_frame"
        )
        frameshift = sum(
            1 for _rid, z, _seq in size_calls if classify_frame(z) == "frameshift"
        )
        indel_summaries.append(
            IndelSummary(
                sample=sample_name,
                guide=gname,
                amplicon=gi.amplicon,
                n_reads_with_size_call=n,
                wt=wt,
                edited=edited,
                pct_editing=_pct(edited, n),
                insertions=insertions,
                deletions=deletions,
                in_frame=in_frame,
                frameshift=frameshift,
                pct_in_frame_of_edited=_pct(in_frame, edited),
            )
        )

        edited_reads = [(rid, seq) for rid, z, seq in size_calls if z != 0]
        raw_unique = len({seq for _rid, seq in edited_reads})
        confident, extra, merged, singles = call_alleles_for_sample(
            edited_reads,
            min_allele_reads=settings.min_allele_reads,
            merge_edit_dist=settings.merge_edit_dist,
        )
        allele_summaries.append(
            AlleleSummary(
                sample=sample_name,
                guide=gname,
                total_reads=n,
                wt_reads=wt,
                edited_reads=edited,
                raw_unique_sequences=raw_unique,
                distinct_alleles_called=len(confident) + len(extra),
                confident_alleles=len(confident),
                low_freq_alleles=len(extra),
                reads_merged_as_noise=merged,
                singleton_reads_excluded=singles,
            )
        )

        ranked = [(seq, count, True) for seq, count in confident] + [
            (seq, count, False) for seq, count in extra
        ]
        ranked.sort(key=lambda x: -x[1])
        for rank, (seq, count, is_conf) in enumerate(ranked, start=1):
            allele_details.append(
                AlleleDetail(
                    sample=sample_name,
                    guide=gname,
                    allele_rank=rank,
                    n_reads=count,
                    pct_of_edited=_pct(count, edited),
                    indel_size_bp=len(seq) - expected,
                    allele_seq=seq,
                    confident=is_conf,
                )
            )

    return indel_summaries, allele_summaries, allele_details, hist_obs


def run_single_sample(
    fastq_path: str,
    ref_set: ReferenceSet,
    settings: PipelineSettings | None = None,
    sample_name: str | None = None,
    progress_callback=None,
    sample_i: int = 1,
    sample_n: int = 1,
) -> SampleResult:
    """Run parsing → classify → editing → indel/frame → alleles for one FASTQ.

    `progress_callback(i, n, sample_name, *, stage, stage_i, stage_n)` is invoked
    at the start of each pipeline stage (i is 1-based sample index).
    """
    settings = settings or PipelineSettings()
    name = sample_name if sample_name is not None else sample_name_from_path(fastq_path)
    stage_n = len(SAMPLE_STAGES)

    def stage(stage_i: int) -> None:
        _emit_progress(
            progress_callback,
            sample_i,
            sample_n,
            name,
            stage=SAMPLE_STAGES[stage_i - 1],
            stage_i=stage_i,
            stage_n=stage_n,
        )

    stage(1)
    reads = parse_fastq(fastq_path)
    stage(2)
    classified = classify_reads(
        reads,
        ref_set.amplicons,
        k=settings.k_classify,
        min_score=settings.min_classify_score,
    )
    amp_read_counts = Counter(cr.amplicon for cr in classified if cr.amplicon is not None)
    n_assigned = sum(amp_read_counts.values())
    n_unassigned = sum(1 for cr in classified if cr.amplicon is None)
    unassigned_reads = [
        (cr.read_id, cr.seq) for cr in classified if cr.amplicon is None
    ]

    stage(3)
    calls = call_editing_status(
        classified,
        ref_set.amplicons,
        ref_set.guides,
        ref_set.guides_by_amplicon,
        settings=settings,
    )
    efficiencies = summarize_efficiency(
        calls, ref_set.guides, amp_read_counts, sample=name
    )
    stage(4)
    indel_summaries, allele_summaries, allele_details, indel_size_obs = (
        _analyze_guide_indels_and_alleles(classified, ref_set, settings, name)
    )
    stage(5)
    excision_summaries, excision_sizes = call_paired_excisions(
        classified,
        calls,
        ref_set.guides,
        ref_set.guides_by_amplicon,
        settings=settings,
        sample=name,
    )
    return SampleResult(
        sample_name=name,
        fastq_path=fastq_path,
        n_reads=len(reads),
        n_assigned=n_assigned,
        n_unassigned=n_unassigned,
        amp_read_counts=dict(amp_read_counts),
        unassigned_reads=unassigned_reads,
        efficiencies=efficiencies,
        indel_summaries=indel_summaries,
        allele_summaries=allele_summaries,
        allele_details=allele_details,
        indel_size_obs=indel_size_obs,
        indel_sizes=[o.indel_size_bp for o in indel_size_obs],
        excision_summaries=excision_summaries,
        excision_sizes=excision_sizes,
    )


def _shared_alleles(details: list[AlleleDetail]) -> list[SharedAllele]:
    samples_by_allele: dict[tuple[str, str], set[str]] = defaultdict(set)
    size_by_allele: dict[tuple[str, str], int] = {}
    for d in details:
        if not d.confident:
            continue
        key = (d.guide, d.allele_seq)
        samples_by_allele[key].add(d.sample)
        size_by_allele[key] = d.indel_size_bp
    out = []
    for (guide, seq), samples in samples_by_allele.items():
        out.append(
            SharedAllele(
                guide=guide,
                allele_seq=seq,
                indel_size_bp=size_by_allele[(guide, seq)],
                n_samples=len(samples),
                samples=", ".join(sorted(samples)),
            )
        )
    out.sort(key=lambda x: (-x.n_samples, x.guide, x.allele_seq))
    return out


def run_batch(
    fastq_paths: list[str],
    ref_set: ReferenceSet,
    settings: PipelineSettings | None = None,
    progress_callback=None,
    sample_callback=None,
) -> BatchResult:
    """Run `run_single_sample` for each FASTQ.

    `progress_callback(i, n, sample_name, *, stage, stage_i, stage_n)` is invoked
    for each pipeline stage of each sample (i is 1-based).
    """
    settings = settings or PipelineSettings()
    n = len(fastq_paths)
    samples: list[SampleResult] = []
    for i, path in enumerate(fastq_paths):
        name = sample_name_from_path(path)
        result = run_single_sample(
            path,
            ref_set,
            settings,
            sample_name=name,
            progress_callback=progress_callback,
            sample_i=i + 1,
            sample_n=n,
        )
        samples.append(result)
        if sample_callback is not None:
            sample_callback(result)

    details = [d for s in samples for d in s.allele_details]
    indel_size_obs = [o for s in samples for o in s.indel_size_obs]
    batch = BatchResult(
        samples=samples,
        efficiencies=[e for s in samples for e in s.efficiencies],
        indel_summaries=[row for s in samples for row in s.indel_summaries],
        allele_summaries=[row for s in samples for row in s.allele_summaries],
        allele_details=details,
        shared_alleles=_shared_alleles(details),
        indel_size_obs=indel_size_obs,
        indel_sizes=[o.indel_size_bp for o in indel_size_obs],
        excision_summaries=[row for s in samples for row in s.excision_summaries],
        excision_sizes=[row for s in samples for row in s.excision_sizes],
        amplicon_assignments=_amplicon_assignments(samples),
        n_reads=sum(s.n_reads for s in samples),
        n_assigned=sum(s.n_assigned for s in samples),
        n_unassigned=sum(s.n_unassigned for s in samples),
    )
    return batch
