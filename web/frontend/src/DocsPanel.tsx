import { DEFAULT_SETTINGS } from "./types";
import { APP_VERSION } from "./version";

type TermProps = { name: string; children: React.ReactNode };

function Term({ name, children }: TermProps) {
  return (
    <div className="docs-term">
      <dt>
        <code>{name}</code>
      </dt>
      <dd>{children}</dd>
    </div>
  );
}

export default function DocsPanel() {
  const d = DEFAULT_SETTINGS;
  return (
    <article className="docs panel">
      <h2>How analysis works</h2>
      <p>
        EfficiencyFinder estimates CRISPR editing outcomes from nanopore amplicon
        sequencing. Upload a reference FASTA (WT amplicons + guide sequences) and one
        or more FASTQ files. Each FASTQ is normally one sample; optionally combine
        several FASTQs into a single sample when one experiment was split across PCR
        reactions.
      </p>
      <p>
        Pipeline per sample: assign reads to amplicons → call WT vs edited at each
        guide → size indels / frame → cluster alleles → detect paired-guide excision
        when an amplicon has two or more guides.
      </p>

      <h2>Inputs</h2>
      <h3>Reference FASTA</h3>
      <p>One file with amplicons and guides interleaved by naming:</p>
      <ul>
        <li>
          <strong>Amplicon</strong> headers must <em>not</em> contain <code>_G</code>.
          Sequence = full WT amplicon.
        </li>
        <li>
          <strong>Guide</strong> headers must contain <code>_G</code>, and the text
          before the first <code>_G</code> must match the amplicon name exactly (case
          and spaces). Sequence = protospacer+PAM; must be an exact substring of that
          amplicon on either strand.
        </li>
        <li>An amplicon may have 0, 1, or several guides. Empty guide sequences are skipped.</li>
      </ul>
      <h3>FASTQ</h3>
      <p>
        Standard 4-line FASTQ; <code>.gz</code> allowed. Quality scores are ignored.
        Only base sequence is used.
      </p>

      <h2>Assignment tab</h2>
      <p>
        Shows how each FASTQ’s reads were classified before editing analysis. Use this
        to spot off-target amplification or reads that never map to your reference
        amplicons.
      </p>
      <dl>
        <Term name="n_reads">
          Total reads in the FASTQ for this sample.
        </Term>
        <Term name="n_assigned">
          Reads assigned to a reference amplicon (k-mer classification score above the
          threshold).
        </Term>
        <Term name="n_unassigned">
          Reads that did not match any amplicon. These are excluded from editing
          efficiency and indel tables.
        </Term>
        <Term name="pct_assigned">
          <code>100 × n_assigned / n_reads</code>.
        </Term>
        <Term name="amplicon / n_reads / pct_of_sample">
          Per-amplicon breakdown: how many assigned reads went to each amplicon, and
          what fraction of the sample’s total reads that is.
        </Term>
      </dl>

      <h2>Efficiency tab</h2>
      <p>
        One row per guide × sample. Editing status is called independently for each
        guide on each read assigned to that amplicon.
      </p>
      <p>
        <strong>Coverage (per guide).</strong> A read contributes to a guide only if it
        overlaps that guide’s local window (flanks ± coverage margin). Reads that never
        reach a cut are <code>not_sequenced</code> for that guide only. Missing flanks
        still produce an edit call (usually a large deletion), so a large dropout
        between two guides is not discarded from efficiency.
      </p>
      <p>
        <strong>Call rules.</strong> Match left and right flanks around the guide. If
        both match: compare observed gap to WT target length → WT, substitution,
        insertion, or small deletion. If either flank fails → large deletion.
      </p>
      <dl>
        <Term name="total_amplicon_reads">
          Reads assigned to this amplicon (any guide on that amplicon shares this
          denominator).
        </Term>
        <Term name="reads_spanning_target">
          Reads that overlap this guide’s window enough to attempt a call
          (= total − not_sequenced for this guide).
        </Term>
        <Term name="not_sequenced">
          Assigned to the amplicon but does not overlap this guide’s local window.
          Excluded from <code>pct_editing</code>.
        </Term>
        <Term name="wt_unedited">
          Both flanks match and the target sequence matches WT within the substitution
          mismatch tolerance.
        </Term>
        <Term name="edited">
          Spanning reads that are not WT. Includes insertions, small/large deletions,
          and substitutions.
        </Term>
        <Term name="edited_insertion">
          Both flanks match; observed gap longer than the WT target.
        </Term>
        <Term name="edited_deletion_small">
          Both flanks match; observed gap shorter than the WT target.
        </Term>
        <Term name="edited_deletion_large">
          One or both flanks fail to match — consistent with a deletion that removes
          flank sequence (including many paired-guide events).
        </Term>
        <Term name="edited_substitution">
          Both flanks match and gap length equals WT, but the target bases differ beyond
          the mismatch tolerance.
        </Term>
        <Term name="pct_editing">
          <code>100 × edited / reads_spanning_target</code>. Substitutions count as
          edited. Empty spanning set → blank/NA.
        </Term>
      </dl>

      <h2>Indel &amp; Frame tab</h2>
      <p>
        For spanning reads that yield a reliable size call, measures net indel size at
        the guide by growing sequence anchors outward from the cut until they match the
        read. Substitutions (length-neutral) are treated as WT (size 0) here, unlike the
        Efficiency tab.
      </p>
      <dl>
        <Term name="n_reads_with_size_call">
          Reads with a successful indel-size measurement after artifact filtering.
        </Term>
        <Term name="wt / edited / pct_editing">
          Size 0 = WT; nonzero = edited. Percent among size-callable reads.
        </Term>
        <Term name="insertions / deletions">
          Counts with net size &gt; 0 or &lt; 0.
        </Term>
        <Term name="in_frame / frameshift">
          Among edited size calls: indel length divisible by 3 vs not.
        </Term>
        <Term name="pct_in_frame_of_edited">
          <code>100 × in_frame / edited</code> (of size-callable edited reads).
        </Term>
      </dl>
      <p>
        Net indel sizes beyond <code>artifact_size_threshold</code> are dropped as likely
        nanopore concatemer artifacts (not used in these counts or the histogram).
        Select a summary row to plot the indel-size distribution for that sample and
        guide (not pooled across the whole batch).
      </p>

      <h2>Alleles tab</h2>
      <p>
        Clusters distinct edited sequences at each guide for chimerism / allele
        diversity. Built only from edited size-callable reads.
      </p>
      <dl>
        <Term name="raw_unique_sequences">
          Unique allele sequences before noise merging.
        </Term>
        <Term name="confident_alleles">
          Alleles seen in at least <code>min_allele_reads</code> reads.
        </Term>
        <Term name="low_freq_alleles">
          Alleles with ≥2 reads but below the confident threshold, after merging
          near-matches into confident alleles.
        </Term>
        <Term name="reads_merged_as_noise">
          Low-count sequences within <code>merge_edit_dist</code> (Levenshtein) of a
          confident allele — counted as sequencing noise, not new alleles.
        </Term>
        <Term name="singleton_reads_excluded">
          Sequences seen once that did not merge into a confident allele.
        </Term>
        <Term name="allele_seq / indel_size_bp">
          Observed sequence at the locus and its length minus WT target length.
        </Term>
        <Term name="Shared across samples">
          Confident alleles (same guide + sequence) appearing in more than one sample
          in the batch.
        </Term>
      </dl>

      <h2>Paired excision tab</h2>
      <p>
        For amplicons with ≥2 guides: detects reads consistent with simultaneous cutting
        at every guide and dropout of the intervening fragment (NHEJ joining outer ends).
      </p>
      <ul>
        <li>
          A read is a candidate when <em>every</em> guide on that amplicon is called
          large deletion (and none are not_sequenced).
        </li>
        <li>
          Confirmation matches the leftmost guide’s left flank to the rightmost guide’s
          right flank and requires dropout ≥{" "}
          <code>max(min_excision_bp, expected × min_excision_fraction)</code>.
        </li>
        <li>
          Confirmed excision sizes are <em>not</em> filtered by{" "}
          <code>artifact_size_threshold</code> — large dropouts here are expected biology.
        </li>
      </ul>
      <dl>
        <Term name="expected_dropout_bp">
          Distance between SpCas9 cut sites on the WT amplicon (each cut is 3 bp
          upstream of that guide’s NGG PAM), not the full guide-span.
        </Term>
        <Term name="n_spanning_reads">
          Reads with a call at every guide on the amplicon (no not_sequenced).
        </Term>
        <Term name="n_simultaneous_large_del / pct_…">
          Spanning reads where all guides are large deletions.
        </Term>
        <Term name="n_confirmed_excision / pct_… / median_excision_bp">
          Subset with confirmed outer-flank dropout; percent of spanning reads; median
          measured dropout.
        </Term>
      </dl>

      <h2>UI options</h2>
      <dl>
        <Term name="Combine FASTQs into one sample">
          Concatenate all uploaded FASTQs and analyze as a single sample (e.g. one plant
          split across multiplex reactions with one shared FASTA).
        </Term>
        <Term name="Hide zero-read rows">
          Hide guide/amplicon rows with no reads in that sample — useful when a full
          FASTA is scored against reaction-specific FASTQs without combining.
        </Term>
      </dl>

      <h2>Advanced parameters</h2>
      <p>Defaults match the validated analysis. Defaults shown in parentheses.</p>
      <dl>
        <Term name={`k_classify (${d.k_classify})`}>
          k-mer length for assigning reads to amplicons.
        </Term>
        <Term name={`min_classify_score (${d.min_classify_score})`}>
          Minimum shared k-mers to assign a read to an amplicon.
        </Term>
        <Term name={`flank (${d.flank})`}>
          Bases taken on each side of the guide for WT/edited flank matching.
        </Term>
        <Term name={`mismatch_thresh_flank (${d.mismatch_thresh_flank})`}>
          Max mismatches allowed when matching a flank.
        </Term>
        <Term name={`mismatch_thresh_target (${d.mismatch_thresh_target})`}>
          Max mismatches in the target for a WT (vs substitution) call when flanks match
          and gap length is WT.
        </Term>
        <Term name={`k_span (${d.k_span})`}>
          k-mer length for per-guide coverage overlap checks.
        </Term>
        <Term name={`coverage_margin (${d.coverage_margin})`}>
          Extra bp beyond each guide’s flanks defining that guide’s coverage window.
        </Term>
        <Term name={`mismatch_fraction (${d.mismatch_fraction})`}>
          Max mismatch fraction of the indel-sizing anchor length.
        </Term>
        <Term name={`max_extra (${d.max_extra})`}>
          Cap (bp) on how far indel-sizing anchors may extend.
        </Term>
        <Term name={`artifact_size_threshold (${d.artifact_size_threshold})`}>
          Net indel sizes beyond this (bp) are excluded from indel/allele stats as
          concatemer artifacts. Does not apply to confirmed paired excision sizes.
        </Term>
        <Term name={`min_allele_reads (${d.min_allele_reads})`}>
          Minimum reads for a confident allele.
        </Term>
        <Term name={`merge_edit_dist (${d.merge_edit_dist})`}>
          Max edit distance to merge a noisy allele sequence into a confident one.
        </Term>
        <Term name={`min_excision_bp (${d.min_excision_bp})`}>
          Absolute minimum confirmed paired-excision dropout (bp).
        </Term>
        <Term name={`min_excision_fraction (${d.min_excision_fraction})`}>
          Confirmed dropout must also be at least this fraction of the expected
          intervening span.
        </Term>
      </dl>

      <h2>Version</h2>
      <p className="docs-version">
        Deployed build: <strong>v{APP_VERSION}</strong>
      </p>
      <p>
        Bump the repo-root <code>VERSION</code> file before each deploy. After the
        site updates, confirm this page (or the <code>v…</code> label in the header)
        shows the new number. <code>/health</code> also returns{" "}
        <code>{`{"version": "${APP_VERSION}"}`}</code>.
      </p>
    </article>
  );
}
