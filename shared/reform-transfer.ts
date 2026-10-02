import type { LabAnalysisView } from './reform-lab.js';

export const MAX_EXPERIMENT_BYTES = 2 * 1024 * 1024;
export const MAX_EXPERIMENT_ITEMS = 12;
export type ImportedExperimentSummary = {
  id: string;
  importedAt: string;
  exportedAt: string;
  issuer: string;
  itemCount: number;
};
export type ImportedExperimentView = {
  experiment: ImportedExperimentSummary;
  views: LabAnalysisView[];
  trustedPublicKey: string;
};
