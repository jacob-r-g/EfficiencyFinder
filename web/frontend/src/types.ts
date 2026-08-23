export type PipelineSettings = {
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

export type JobProgress = { i: number; n: number; sample: string };

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
};

export type IndelSizeObservation = {
  sample: string;
  guide: string;
  indel_size_bp: number;
};

export type BatchResult = {
  samples: SampleCounts[];
  efficiencies: Record<string, unknown>[];
  indel_summaries: Record<string, unknown>[];
  allele_summaries: Record<string, unknown>[];
  allele_details: Record<string, unknown>[];
  shared_alleles: Record<string, unknown>[];
  indel_size_obs: IndelSizeObservation[];
  indel_sizes: number[];
  excision_summaries: Record<string, unknown>[];
  excision_sizes: Record<string, unknown>[];
  n_reads: number;
  n_assigned: number;
  n_unassigned: number;
};
