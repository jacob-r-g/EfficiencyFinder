import { useState } from "react";
import DataTable from "./DataTable";
import IndelHistogram from "./IndelHistogram";
import type { BatchResult } from "./types";

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

const TABS = ["Efficiency", "Indel & Frame", "Alleles", "Paired excision"] as const;

type Props = { result: BatchResult | null };

export default function ResultsView({ result }: Props) {
  const [tab, setTab] = useState<(typeof TABS)[number]>("Efficiency");
  const [alleleTab, setAlleleTab] = useState<"sample" | "shared">("sample");
  const [detailFilter, setDetailFilter] = useState<Record<string, unknown> | null>(null);
  const [excisionFilter, setExcisionFilter] = useState<Record<string, unknown> | null>(null);

  if (!result) {
    return <section className="results">Run an analysis to see results.</section>;
  }

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

  return (
    <section className="results">
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
      {tab === "Efficiency" && (
        <DataTable columns={EFFICIENCY} rows={result.efficiencies} filename="efficiency.csv" />
      )}
      {tab === "Indel & Frame" && (
        <>
          <IndelHistogram sizes={result.indel_sizes} />
          <DataTable columns={INDEL} rows={result.indel_summaries} filename="indel_frame.csv" />
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
                rows={result.allele_summaries}
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
            rows={result.excision_summaries}
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
