export type Nuclease = "cas9" | "cas12";

export type PipelineSettings = {
  nuclease: Nuclease;
  k_classify: number;
  min_classify_score: number;
  flank: number;
  mismatch_thresh_flank: number;
  mismatch_thresh_target: number;
  k_span: number;
  coverage_margin: number;
  mismatch_fraction: number;
  max_extra: number;
  artifact_size_threshold: number;
  min_allele_reads: number;
  merge_edit_dist: number;
  min_excision_bp: number;
  min_excision_fraction: number;
};

export const DEFAULT_SETTINGS: PipelineSettings = {
  nuclease: "cas9",
  k_classify: 17,
  min_classify_score: 15,
  flank: 25,
  mismatch_thresh_flank: 4,
  mismatch_thresh_target: 4,
  k_span: 15,
  coverage_margin: 40,
  mismatch_fraction: 0.18,
  max_extra: 400,
  artifact_size_threshold: 100,
  min_allele_reads: 3,
  merge_edit_dist: 2,
  min_excision_bp: 30,
  min_excision_fraction: 0.4,
};

export type JobProgress = {
  i: number;
  n: number;
  sample: string;
  stage?: string;
  stage_i?: number;
  stage_n?: number;
};

export type JobStatus = {
  id: string;
  status: "queued" | "running" | "done" | "failed";
  progress: JobProgress | null;
  error: string | null;
  is_validation: boolean;
};

export type SampleCounts = {
  sample_name: string;
  n_reads: number;
  n_assigned: number;
  n_unassigned: number;
  pct_assigned: number | null;
};

export type UnassignedExport = {
  sample_name: string;
  n_reads: number;
  filename: string;
};

export type IndelSizeObservation = {
  sample: string;
  guide: string;
  indel_size_bp: number;
};

export type InspectExample = {
  read_id: string;
  orientation: string;
  status: string;
  between: string;
  observed_gap: number;
  expected_gap: number;
  wt_window_found: boolean;
  note: string;
};

export type GuideInspect = {
  sample: string;
  guide: string;
  amplicon: string;
  nuclease: string;
  strand: string;
  ref_local: string;
  left_flank_len: number;
  right_flank_len: number;
  target_len: number;
  pam_start: number;
  pam_end: number;
  spacer_start: number;
  spacer_end: number;
  wt_start: number;
  wt_end: number;
  cut_offset: number;
  ref_wt_window: string;
  examples: InspectExample[];
  n_edited_total: number;
  n_wt_total: number;
  n_inconclusive_total: number;
};

export type BatchResult = {
  samples: SampleCounts[];
  unassigned_exports: UnassignedExport[];
  amplicon_assignments: Record<string, unknown>[];
  efficiencies: Record<string, unknown>[];
  indel_summaries: Record<string, unknown>[];
  allele_summaries: Record<string, unknown>[];
  allele_details: Record<string, unknown>[];
  shared_alleles: Record<string, unknown>[];
  indel_size_obs: IndelSizeObservation[];
  indel_sizes: number[];
  excision_summaries: Record<string, unknown>[];
  excision_sizes: Record<string, unknown>[];
  inspect?: GuideInspect[];
  n_reads: number;
  n_assigned: number;
  n_unassigned: number;
};
