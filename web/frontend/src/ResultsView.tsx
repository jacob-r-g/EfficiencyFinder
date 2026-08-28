import { useState } from "react";
import DataTable from "./DataTable";
import IndelHistogram from "./IndelHistogram";
import { unassignedDownloadUrl } from "./api";
import type { BatchResult } from "./types";

const ASSIGNMENT_SAMPLE = [
  "sample_name", "n_reads", "n_assigned", "n_unassigned", "pct_assigned",
];
const ASSIGNMENT_AMP = ["sample", "amplicon", "n_reads", "pct_of_sample"];
const EFFICIENCY = [
  "sample", "guide", "amplicon", "total_amplicon_reads", "reads_spanning_target",
  "not_sequenced", "wt_unedited", "edited", "edited_insertion", "edited_deletion_small",
  "edited_deletion_large", "edited_substitution", "pct_editing",
];
const INDEL = [
  "sample", "guide", "amplicon", "n_reads_with_size_call", "wt", "edited", "pct_editing",
  "insertions", "deletions", "in_frame", "frameshift", "pct_in_frame_of_edited",
];
const ALLELE_SUMMARY = [
  "sample", "guide", "total_reads", "wt_reads", "edited_reads", "raw_unique_sequences",
  "distinct_alleles_called", "confident_alleles", "low_freq_alleles",
  "reads_merged_as_noise", "singleton_reads_excluded",
];
const ALLELE_DETAIL = [
  "sample", "guide", "allele_rank", "n_reads", "pct_of_edited", "indel_size_bp",
  "allele_seq", "confident",
];
const SHARED = ["guide", "n_samples", "samples", "indel_size_bp", "allele_seq"];
const EXCISION = [
  "sample", "amplicon", "guides", "n_guides", "expected_dropout_bp", "n_spanning_reads",
  "n_simultaneous_large_del", "pct_simultaneous_large_del", "n_confirmed_excision",
  "pct_confirmed_excision", "median_excision_bp",
];
const EXCISION_SIZE = ["sample", "amplicon", "excision_size_bp", "n_reads", "pct_of_confirmed"];

const TABS = ["Assignment", "Efficiency", "Indel & Frame", "Alleles", "Paired excision"] as const;

function hasReads(row: Record<string, unknown>, key: string): boolean {
  const n = row[key];
  return typeof n === "number" ? n > 0 : Number(n) > 0;
}

type Props = { result: BatchResult | null; jobId: string | null };

export default function ResultsView({ result, jobId }: Props) {
  const [tab, setTab] = useState<(typeof TABS)[number]>("Assignment");
  const [alleleTab, setAlleleTab] = useState<"sample" | "shared">("sample");
  const [hideZeros, setHideZeros] = useState(true);
  const [detailFilter, setDetailFilter] = useState<Record<string, unknown> | null>(null);
  const [indelFilter, setIndelFilter] = useState<Record<string, unknown> | null>(null);
  const [excisionFilter, setExcisionFilter] = useState<Record<string, unknown> | null>(null);

  if (!result) {
    return <section className="results">Run an analysis to see results.</section>;
  }

  const efficiencies = hideZeros
    ? result.efficiencies.filter((r) => hasReads(r, "total_amplicon_reads"))
    : result.efficiencies;
  const indelRows = hideZeros
    ? result.indel_summaries.filter((r) => hasReads(r, "n_reads_with_size_call"))
    : result.indel_summaries;
  const alleleSummaries = hideZeros
    ? result.allele_summaries.filter((r) => hasReads(r, "total_reads"))
    : result.allele_summaries;
  const excisionRows = hideZeros
    ? result.excision_summaries.filter((r) => hasReads(r, "n_spanning_reads"))
    : result.excision_summaries;
  const ampAssignments = hideZeros
    ? (result.amplicon_assignments ?? []).filter((r) => hasReads(r, "n_reads"))
    : result.amplicon_assignments ?? [];
  const sampleRows = result.samples.map((s) => ({ ...s, sample: s.sample_name }));
  const anyUnassigned = result.samples.some((s) => s.n_unassigned > 0);
  const unassignedExports = result.unassigned_exports ?? [];

  const details = result.allele_details.filter(
    (d) =>
      !detailFilter ||
      (d.sample === detailFilter.sample && d.guide === detailFilter.guide),
  );
  const sizes = result.excision_sizes.filter(
    (d) =>
      !excisionFilter ||
      (d.sample === excisionFilter.sample && d.amplicon === excisionFilter.amplicon),
  );
  const indelObs = result.indel_size_obs ?? [];
  const histSizes = indelFilter
    ? indelObs
        .filter(
          (o) =>
            o.sample === indelFilter.sample && o.guide === indelFilter.guide,
        )
        .map((o) => o.indel_size_bp)
    : [];
  const histTitle = indelFilter
    ? `Indel size distribution — ${String(indelFilter.sample)} / ${String(indelFilter.guide)}`
    : "Indel size distribution (select a summary row)";

  return (
    <section className="results">
      <div className="results-toolbar">
        <div className="tabs">
          {TABS.map((name) => (
            <button
              key={name}
              type="button"
              className={tab === name ? "active" : ""}
              onClick={() => setTab(name)}
            >
              {name}
            </button>
          ))}
        </div>
        <label className="checkbox-row" title="Hide amplicons/guides with zero reads in this sample (e.g. other PCR reactions).">
          <input
            type="checkbox"
            checked={hideZeros}
            onChange={(e) => setHideZeros(e.target.checked)}
          />
          Hide zero-read rows
        </label>
      </div>
      {tab === "Assignment" && (
        <>
          <p className="hint">
            How reads were classified to reference amplicons. Unassigned reads did not
            match any amplicon well enough — they may be off-target PCR products or
            chimeras.
          </p>
          {anyUnassigned && (
            <p className="hint hint-warn">
              Some reads are unassigned. If an amplicon has very few assigned reads but
              you see a gel band, check for non-specific amplification in the unassigned
              pool.
            </p>
          )}
          {jobId && unassignedExports.length > 0 && (
            <div className="export-row">
              {unassignedExports.map((exp) => (
                <a
                  key={exp.sample_name}
                  className="button-link"
                  href={unassignedDownloadUrl(jobId, exp.sample_name)}
                  download={exp.filename}
                >
                  Download unassigned FASTQ — {exp.sample_name} ({exp.n_reads.toLocaleString()} reads)
                </a>
              ))}
            </div>
          )}
          <DataTable
            columns={ASSIGNMENT_SAMPLE}
            rows={sampleRows}
            filename="assignment_by_sample.csv"
          />
          <DataTable
            columns={ASSIGNMENT_AMP}
            rows={ampAssignments}
            filename="assignment_by_amplicon.csv"
          />
        </>
      )}
      {tab === "Efficiency" && (
        <DataTable columns={EFFICIENCY} rows={efficiencies} filename="efficiency.csv" />
      )}
      {tab === "Indel & Frame" && (
        <>
          <DataTable
            columns={INDEL}
            rows={indelRows}
            filename="indel_frame.csv"
            onSelect={setIndelFilter}
          />
          <IndelHistogram sizes={histSizes} title={histTitle} />
        </>
      )}
      {tab === "Alleles" && (
        <>
          <div className="tabs">
            <button type="button" className={alleleTab === "sample" ? "active" : ""} onClick={() => setAlleleTab("sample")}>
              Per sample
            </button>
            <button type="button" className={alleleTab === "shared" ? "active" : ""} onClick={() => setAlleleTab("shared")}>
              Shared across samples
            </button>
          </div>
          {alleleTab === "shared" ? (
            <DataTable columns={SHARED} rows={result.shared_alleles} filename="shared_alleles.csv" />
          ) : (
            <>
              <DataTable
                columns={ALLELE_SUMMARY}
                rows={alleleSummaries}
                filename="alleles_summary.csv"
                onSelect={setDetailFilter}
              />
              <p className="hint">
                {detailFilter
                  ? `Allele details — ${String(detailFilter.sample)} / ${String(detailFilter.guide)}`
                  : "Allele details (select a summary row)"}
              </p>
              <DataTable columns={ALLELE_DETAIL} rows={details} filename="alleles_details.csv" />
            </>
          )}
        </>
      )}
      {tab === "Paired excision" && (
        <>
          <DataTable
            columns={EXCISION}
            rows={excisionRows}
            filename="paired_excision.csv"
            onSelect={setExcisionFilter}
          />
          <p className="hint">
            {excisionFilter
              ? `Confirmed excision sizes — ${String(excisionFilter.sample)} / ${String(excisionFilter.amplicon)}`
              : "Confirmed excision sizes (select a summary row)"}
          </p>
          <DataTable columns={EXCISION_SIZE} rows={sizes} filename="paired_excision_sizes.csv" />
        </>
      )}
    </section>
  );
}
