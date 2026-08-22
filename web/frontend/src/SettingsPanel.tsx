import { useState } from "react";
import type { PipelineSettings } from "./types";

type Field = {
  key: keyof PipelineSettings;
  label: string;
  title: string;
  kind: "int" | "float";
  min: number;
  max: number;
  step: number;
};

const FIELDS: Field[] = [
  { key: "k_classify", label: "Classification k-mer", title: "k-mer length for read-to-amplicon classification.", kind: "int", min: 5, max: 51, step: 1 },
  { key: "min_classify_score", label: "Min classify score", title: "Minimum shared k-mers to confidently assign a read to an amplicon.", kind: "int", min: 1, max: 500, step: 1 },
  { key: "flank", label: "Flank (bp)", title: "Flank length on each side of the guide used for WT/edited calling.", kind: "int", min: 5, max: 200, step: 1 },
  { key: "mismatch_thresh_flank", label: "Flank mismatch max", title: "Max mismatches allowed when matching a flank sequence.", kind: "int", min: 0, max: 20, step: 1 },
  { key: "mismatch_thresh_target", label: "Target mismatch max", title: "Max mismatches allowed in the target sequence for a WT call.", kind: "int", min: 0, max: 20, step: 1 },
  { key: "k_span", label: "Coverage k-mer", title: "k-mer length for presence-based coverage checks around the guide bracket.", kind: "int", min: 5, max: 51, step: 1 },
  { key: "coverage_margin", label: "Coverage margin (bp)", title: "Extra bp beyond each guide's flanks defining that guide's coverage window.", kind: "int", min: 0, max: 200, step: 1 },
  { key: "mismatch_fraction", label: "Anchor mismatch fraction", title: "Max fraction of indel-sizing anchor length allowed to mismatch.", kind: "float", min: 0, max: 1, step: 0.01 },
  { key: "max_extra", label: "Max anchor extra (bp)", title: "Cap on how far the indel-sizing anchor search will extend.", kind: "int", min: 25, max: 2000, step: 25 },
  { key: "artifact_size_threshold", label: "Artifact size threshold (bp)", title: "Net indel sizes beyond this are treated as nanopore concatemer artifacts, not real edits.", kind: "int", min: 10, max: 5000, step: 10 },
  { key: "min_allele_reads", label: "Min allele reads", title: "Minimum read count for a confident allele call.", kind: "int", min: 1, max: 100, step: 1 },
  { key: "merge_edit_dist", label: "Allele merge distance", title: "Max Levenshtein distance to merge a noisy read into a confident allele.", kind: "int", min: 0, max: 10, step: 1 },
  { key: "min_excision_bp", label: "Min paired excision (bp)", title: "Minimum outer-flank dropout (bp) to confirm a paired-guide excision size.", kind: "int", min: 1, max: 2000, step: 5 },
  { key: "min_excision_fraction", label: "Min excision fraction", title: "Confirmed paired excision must drop at least this fraction of the expected intervening span.", kind: "float", min: 0, max: 1, step: 0.05 },
];

type Props = {
  value: PipelineSettings;
  disabled: boolean;
  onChange: (next: PipelineSettings) => void;
};

export default function SettingsPanel({ value, disabled, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const mid = Math.ceil(FIELDS.length / 2);

  return (
    <section className="panel">
      <button type="button" className="settings-toggle" onClick={() => setOpen((v) => !v)}>
        {open ? "▾" : "▸"} Advanced settings
      </button>
      {open && (
        <div className="settings-grid">
          {[FIELDS.slice(0, mid), FIELDS.slice(mid)].map((col, i) => (
            <div key={i}>
              {col.map((f) => (
                <label key={f.key} className="settings-row" title={f.title}>
                  <span>{f.label}</span>
                  <input
                    type="number"
                    disabled={disabled}
                    min={f.min}
                    max={f.max}
                    step={f.step}
                    value={value[f.key]}
                    onChange={(e) =>
                      onChange({
                        ...value,
                        [f.key]:
                          f.kind === "float"
                            ? Number(e.target.value)
                            : Math.round(Number(e.target.value)),
                      })
                    }
                  />
                </label>
              ))}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
