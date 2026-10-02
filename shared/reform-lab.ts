import type {
  ReformBundle,
  ReformCertificate,
  ReformQuery,
  ReformReceipt,
  ReformSnapshot,
} from './reform-contracts.js';
import type { ReformExplanation, ReformExplanationReport } from './reform-explanations.js';
import type {
  ReformMetricAnnotations,
  ReformMetrics,
  ReformMetricsReport,
} from './reform-metrics.js';

export const labModelRoles = ['A', 'B', 'C'] as const;
export type LabModelRole = (typeof labModelRoles)[number];
export const labQueries = [
  {
    id: 'AB-equivalence',
    title: 'A → B: сохранение последствий',
    detail: 'Все 16 завершённых входов; полные последствия должны совпадать.',
  },
  {
    id: 'AC-component-no-increase',
    title: 'A → C: срок не увеличивается',
    detail: 'Все 16 входов; штраф, квалификация и валюта сохраняются.',
  },
  {
    id: 'AC-strict-reduction',
    title: 'A → C: строгое уменьшение при M',
    detail: 'Восемь входов с установленным M.',
  },
  {
    id: 'AC-preserved-outside',
    title: 'A → C: сохранение вне M',
    detail: 'Восемь входов с опровергнутым M.',
  },
  {
    id: 'A-strict-M-mitigation',
    title: 'Модель A: обязательное смягчение M',
    detail: 'Восемь пар; меняется только M=false → true.',
  },
  {
    id: 'B-strict-M-mitigation',
    title: 'Модель B: обязательное смягчение M',
    detail: 'Восемь пар; меняется только M=false → true.',
  },
  {
    id: 'C-strict-M-mitigation',
    title: 'Модель C: обязательное смягчение M',
    detail: 'Восемь пар; меняется только M=false → true.',
  },
  {
    id: 'AD-preserved-outside-counterexample',
    title: 'A → D: исследовать ошибочную поправку',
    detail: 'D дополнительно меняет N. Проверяем сохранение последствий вне M.',
  },
] as const;
export type LabQueryId = (typeof labQueries)[number]['id'];
export type LabVerification = ReformReceipt['payload']['verification'] & {
  queryDigest: string;
  certificateDigest: string | null;
  statementDigest: string;
  durationMs: number;
};
export type LabAnalysis = {
  schema: 'normlab.lab-analysis/v1';
  id: string;
  createdAt: string;
  snapshotId: string | null;
  modelRole: LabModelRole | null;
  queryId: LabQueryId | null;
  title: string;
  query: ReformQuery;
  bundles: ReformBundle[];
  snapshot: ReformSnapshot | null;
  certificate: ReformCertificate;
  receipt: ReformReceipt | null;
  verification: LabVerification;
  annotations: ReformMetricAnnotations | null;
};
export type LabAnalysisSummary = Pick<
  LabAnalysis,
  'id' | 'createdAt' | 'snapshotId' | 'modelRole' | 'queryId' | 'title'
> & {
  proofStatus: LabVerification['status'];
  resultStatus: 'complete' | 'conditional' | 'holds' | 'counterexample';
};
export type LabWorkspace = {
  snapshots: ReformSnapshot[];
  analyses: LabAnalysisSummary[];
};
export type LabModel = {
  role: LabModelRole;
  title: string;
  description: string;
  bundle: ReformBundle;
};
export type LabBootstrap = {
  csrfToken: string;
  workspace: LabWorkspace;
  models: LabModel[];
  modelMetrics: ReformMetrics['models'];
  issuerPublicKey: string;
  verifier: { available: boolean; version: string | null };
};
export type LabAnalysisView = {
  analysis: LabAnalysis;
  registryCurrent: boolean;
  explanation: ReformExplanation;
  metrics: ReformMetrics;
  explanationReport: ReformExplanationReport | null;
  metricsReport: ReformMetricsReport | null;
};
