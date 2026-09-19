import { useMemo, useState, type ReactNode } from "react";
import type { GuideInspect, InspectExample } from "./types";

type Filter = "edited" | "WT_intact" | "inconclusive" | "all";

type Props = {
  panel: GuideInspect | null;
  onClose: () => void;
};

const EDITED = new Set([
  "edited_insertion",
  "edited_deletion_small",
  "edited_deletion_large",
  "edited_substitution",
]);

function matchesFilter(ex: InspectExample, filter: Filter): boolean {
  if (filter === "all") return true;
  if (filter === "edited") return EDITED.has(ex.status);
  return ex.status === filter;
}

function AnnotatedRef({ panel }: { panel: GuideInspect }) {
  const seq = panel.ref_local;
  const chars = [];
  for (let i = 0; i < seq.length; i++) {
    if (i === panel.cut_offset) {
      chars.push(
        <span key={`cut-${i}`} className="insp-cut-mark" title={`Cut between ${i - 1}|${i}`}>
          |
        </span>,
      );
    }
    const base = seq[i];
    let cls = "insp-base";
    if (i >= panel.pam_start && i < panel.pam_end) cls += " insp-pam";
    else if (i >= panel.wt_start && i < panel.wt_end) cls += " insp-wt";
    else if (i >= panel.spacer_start && i < panel.spacer_end) cls += " insp-spacer";
    else if (i < panel.left_flank_len || i >= seq.length - panel.right_flank_len) {
      cls += " insp-flank";
    }
    chars.push(
      <span key={i} className={cls} title={`pos ${i}`}>
        {base}
      </span>,
    );
  }
  return (
    <div className="insp-seq-wrap">
      <div className="insp-seq" aria-label="Reference local window">
        {chars}
      </div>
    </div>
  );
}

function highlightBetween(ex: InspectExample, refWt: string): ReactNode {
  if (!ex.between) {
    return <span className="insp-muted">(no between-flank sequence)</span>;
  }
  if (ex.wt_window_found && refWt) {
    const idx = ex.between.indexOf(refWt);
    if (idx >= 0) {
      return (
        <>
          <span>{ex.between.slice(0, idx)}</span>
          <span className="insp-wt-hit">{ex.between.slice(idx, idx + refWt.length)}</span>
          <span>{ex.between.slice(idx + refWt.length)}</span>
        </>
      );
    }
  }
  return <span className={EDITED.has(ex.status) ? "insp-edited-seq" : undefined}>{ex.between}</span>;
}

export default function InspectPanel({ panel, onClose }: Props) {
  const [filter, setFilter] = useState<Filter>("edited");

  const examples = useMemo(() => {
    if (!panel) return [];
    return panel.examples.filter((e) => matchesFilter(e, filter));
  }, [panel, filter]);

  if (!panel) {
    return (
      <div className="inspect-panel inspect-empty">
        <p className="hint">Select an Efficiency row to inspect WT / edited calls at that guide.</p>
      </div>
    );
  }

  return (
    <div className="inspect-panel">
      <div className="inspect-header">
        <div>
          <strong>Inspect</strong> — {panel.sample} / {panel.guide}{" "}
          <span className="insp-meta">
            ({panel.nuclease}, strand {panel.strand})
          </span>
        </div>
        <button type="button" onClick={onClose}>
          Close
        </button>
      </div>

      <p className="hint">
        Reference local window (flanks + target). Highlighted: flanks, spacer, PAM,{" "}
        <strong>WT window</strong> (the sequence that must match for WT_intact). Showing up to{" "}
        {panel.examples.length} example reads (edited {panel.n_edited_total} total · WT{" "}
        {panel.n_wt_total} · inconclusive {panel.n_inconclusive_total}).
      </p>

      <div className="insp-legend">
        <span className="insp-flank">flank</span>
        <span className="insp-spacer">spacer</span>
        <span className="insp-pam">PAM</span>
        <span className="insp-wt">WT window</span>
        <span className="insp-cut-legend">| cut</span>
      </div>

      <div className="insp-ref-block">
        <div className="insp-label">Reference</div>
        <AnnotatedRef panel={panel} />
        <div className="insp-label">
          WT window ({panel.ref_wt_window.length} bp):{" "}
          <code className="insp-wt-code">{panel.ref_wt_window}</code>
        </div>
      </div>

      <div className="insp-filters">
        {(
          [
            ["edited", `Edited (${panel.n_edited_total})`],
            ["WT_intact", `WT (${panel.n_wt_total})`],
            ["inconclusive", `Inconclusive (${panel.n_inconclusive_total})`],
            ["all", "All shown"],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            className={filter === key ? "active" : ""}
            onClick={() => setFilter(key)}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="insp-reads">
        {examples.length === 0 ? (
          <p className="hint">No example reads in this filter.</p>
        ) : (
          examples.map((ex) => (
            <div key={`${ex.read_id}-${ex.status}`} className="insp-read">
              <div className="insp-read-meta">
                <code>{ex.read_id}</code>
                <span className={`insp-status insp-status-${ex.status}`}>{ex.status}</span>
                <span className="insp-meta">
                  {ex.orientation} · gap {ex.observed_gap}/{ex.expected_gap} ·{" "}
                  {ex.note}
                </span>
              </div>
              {ex.between !== "" && (
                <div className="insp-seq-wrap">
                  <div className="insp-seq insp-read-seq">
                    {highlightBetween(ex, panel.ref_wt_window)}
                  </div>
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
