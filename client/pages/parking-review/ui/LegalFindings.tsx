import { useEffect, useRef, useState } from 'react';
import { apiUrl } from '@/shared/api';
import { Actions, Button, Disclosure, Notice, Panel, SectionHeading } from '@/shared/ui';
import {
  emptyLegalFindings,
  legalInputSchema,
  legalCoordinateKeys,
  type SavedLegalProposal,
  legalOutcomeLabels,
  type LegalAssessment,
  type LegalFinding,
  type LegalInput,
  type LegalWorkspace,
  type ReviewDraft,
} from '../model/contracts.js';
import { legalValidationIssues } from '../model/legal-validation.js';

import { LegalClarifications } from './LegalClarifications.js';
import type { ClarificationPreview } from '../model/legal-clarifications.js';
import { LegalActionFeedback } from './LegalActionFeedback.js';
import { LegalProposals } from './LegalProposals.js';
import { LegalCandidate } from './LegalCandidate.js';
import { LegalFindingEditor } from './LegalFindingEditor.js';
import { LegalResultView } from './LegalResultView.js';

import { LegalScopeEditor, type LegalCoordinates } from './LegalScopeEditor.js';

const emptyCoordinates: LegalCoordinates = {
  episode: '',
  vehicle: '',
  participant: '',
  eventDate: '',
  location: '',
  timeInterval: '',
};

export function LegalFindings({
  draft,
  token,
  blocked,
  onSaved,
  onUnsavedChange,
}: {
  draft: ReviewDraft;
  token: string;
  blocked: boolean;
  onSaved: () => void;
  onUnsavedChange: (unsaved: boolean) => void;
}) {
  const [workspace, setWorkspace] = useState<LegalWorkspace>();
  const [coordinates, setCoordinates] = useState(emptyCoordinates);
  const [findings, setFindings] = useState(emptyLegalFindings);
  const [proposal, setProposal] = useState<SavedLegalProposal>();
  const [coordinateProposalId, setCoordinateProposalId] = useState<string>();
  const [clarificationDirty, setClarificationDirty] = useState(false);
  const [clarificationEpoch, setClarificationEpoch] = useState(0);
  const [feedbackOrigin, setFeedbackOrigin] = useState<'actions' | 'clarifications'>('actions');
  const clarificationFeedbackRef = useRef<HTMLDivElement>(null);
  const [proposing, setProposing] = useState(false);
  const [claimedFine, setClaimedFine] = useState('');
  const [record, setRecord] = useState<LegalAssessment>();
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState<LegalInput>();
  const [error, setError] = useState('');
  const [refresh, setRefresh] = useState(0);
  const [loading, setLoading] = useState(true);
  const [validationAttempt, setValidationAttempt] =
    useState<Pick<LegalInput, 'action' | 'requestId'>>();
  const [resetNotice, setResetNotice] = useState('');
  const [feedbackVersion, setFeedbackVersion] = useState(0);
  const feedbackRef = useRef<HTMLDivElement>(null);
  const inFlight = useRef(false);
  useEffect(() => {
    const target = feedbackOrigin === 'clarifications' ? clarificationFeedbackRef : feedbackRef;
    if (!feedbackVersion || !target.current) return;
    const feedback = target.current;
    feedback.focus({ preventScroll: true });
    const bounds = feedback.getBoundingClientRect();
    if (bounds.top < 0 || bounds.bottom > window.innerHeight)
      feedback.scrollIntoView({ block: 'start' });
  }, [feedbackVersion, feedbackOrigin]);
  useEffect(() => {
    onUnsavedChange(dirty || busy || proposing || clarificationDirty || !!pending);
  }, [dirty, busy, proposing, clarificationDirty, pending, onUnsavedChange]);
  useEffect(() => {
    return () => onUnsavedChange(false);
  }, [onUnsavedChange]);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    fetch(apiUrl(`/api/parking/legal/${draft.draftId}`), {
      signal: AbortSignal.any([controller.signal, AbortSignal.timeout(10000)]),
    })
      .then(async (response) => {
        if (!response.ok) throw new Error('Не удалось загрузить юридические обстоятельства.');
        return (await response.json()) as LegalWorkspace;
      })
      .then((data) => {
        if (controller.signal.aborted) return;
        setWorkspace(data);
        const saved = data.assessments.find(
          (item) => item.input.expectedRevisionId === draft.revisionId,
        );
        setRecord(saved);
        setCoordinates(
          saved
            ? {
                episode: saved.input.episode,
                vehicle: saved.input.vehicle,
                participant: saved.input.participant,
                eventDate: saved.input.eventDate,
                location: saved.input.location,
                timeInterval: saved.input.timeInterval,
              }
            : emptyCoordinates,
        );
        setCoordinateProposalId(saved?.input.coordinateProposalId);
        setFindings(saved?.input.findings ?? emptyLegalFindings());
        setClaimedFine(saved?.input.claimedFine == null ? '' : String(saved.input.claimedFine));
        setDirty(false);
        setError('');
        setValidationAttempt(undefined);
        setResetNotice('');
      })
      .catch((e: unknown) => {
        if (!controller.signal.aborted) setError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [draft.draftId, draft.revisionId, refresh]);
  const confirmed = draft.statements.filter((s) => s.decision === 'confirmed');
  const episodes = [...new Set(confirmed.map((s) => s.aboutEpisode))];
  const disabled = blocked || busy || proposing || loading || !!pending || !workspace;
  const activeProposal =
    proposal?.revisionId === draft.revisionId &&
    proposal.episode === coordinates.episode &&
    proposal.packageDigest === workspace?.packageDigest
      ? proposal
      : undefined;
  const clarificationValues = { ...coordinates, findings };
  const editorDisabled = disabled || clarificationDirty;
  const scopeApproved = !!activeProposal && coordinateProposalId === activeProposal.proposalId;
  function makeInput(attempt: Pick<LegalInput, 'action' | 'requestId'>): LegalInput {
    return {
      ...coordinates,
      findings,
      ...(coordinateProposalId ? { coordinateProposalId } : {}),
      claimedFine: claimedFine === '' ? null : Number(claimedFine),
      draftId: draft.draftId,
      expectedRevisionId: draft.revisionId,
      expectedAssessmentId: workspace?.assessments[0]?.id ?? null,
      packageDigest: workspace?.packageDigest ?? '',
      ...attempt,
    };
  }
  // Revalidate the same local attempt as fields are corrected; no request is sent here.
  const validation = validationAttempt && legalInputSchema.safeParse(makeInput(validationAttempt));
  const issues =
    validation && !validation.success && workspace
      ? legalValidationIssues(validation.error.issues, findings, workspace.package.conditions)
      : [];
  const change = (conditionId: string, patch: Partial<LegalFinding>) => {
    setFindings((items) =>
      items.map((item) => (item.conditionId === conditionId ? { ...item, ...patch } : item)),
    );
    setDirty(true);
    setError('');
  };
  function changeCoordinates(next: LegalCoordinates) {
    if (
      Object.entries(next).every(
        ([key, value]) => coordinates[key as keyof LegalCoordinates] === value,
      )
    )
      return true;
    const hasDecisions = findings.some(
      (finding) =>
        finding.state !== 'unreviewed' || finding.rationale || finding.statementIds.length,
    );
    if (
      hasDecisions &&
      !window.confirm(
        'Изменение эпизода, участника, ТС, места или времени сбросит все введённые решения, основания и ссылки на утверждения. Продолжить?',
      )
    )
      return false;
    if (next.episode !== coordinates.episode) {
      setCoordinateProposalId(undefined);
      setProposal(undefined);
    }
    setCoordinates(next);
    setFindings(emptyLegalFindings());
    setDirty(true);
    setValidationAttempt(undefined);
    setError('');
    if (hasDecisions)
      setResetNotice('Координаты изменены. Проверьте решения, основания и ссылки заново.');
    return true;
  }
  function acceptCoordinates(candidate: SavedLegalProposal) {
    if (disabled || candidate !== activeProposal) return;
    const next = { ...coordinates };
    for (const key of legalCoordinateKeys) next[key] = candidate.suggestion.coordinates[key].value;
    if (changeCoordinates(next)) {
      setCoordinateProposalId(candidate.proposalId);
      setDirty(true);
      setError('');
    }
  }
  function confirmClarifications(preview: ClarificationPreview) {
    if (disabled || inFlight.current) return;
    if (preview.baseline !== JSON.stringify(clarificationValues)) {
      setError('Обстоятельства изменились. Заново подготовьте уточнения.');
      setFeedbackOrigin('clarifications');
      setFeedbackVersion((value) => value + 1);
      return;
    }
    const input = {
      ...makeInput({ action: 'save', requestId: crypto.randomUUID() }),
      ...preview.values,
    };
    const { findings: nextFindings, ...nextCoordinates } = preview.values;
    setCoordinates(nextCoordinates);
    setFindings(nextFindings);
    setDirty(true);
    setClarificationDirty(false);
    setClarificationEpoch((value) => value + 1);
    setResetNotice(
      preview.resetConditionIds.length
        ? 'Координаты уточнены. Прежние решения сброшены; сохранены только подтверждённые сейчас ответы.'
        : '',
    );
    void submit('save', input, 'clarifications');
  }
  async function submit(
    action: LegalInput['action'],
    replacement?: LegalInput,
    origin: 'actions' | 'clarifications' = 'actions',
  ) {
    if (inFlight.current || proposing || blocked || loading || !workspace) return;
    setFeedbackOrigin(origin);
    let input: LegalInput;
    try {
      if (pending) input = pending;
      else {
        const attempt = { action, requestId: replacement?.requestId ?? crypto.randomUUID() };
        const parsed = legalInputSchema.safeParse(replacement ?? makeInput(attempt));
        if (!parsed.success) {
          setValidationAttempt(attempt);
          setError('');
          setFeedbackVersion((value) => value + 1);
          return;
        }
        input = parsed.data;
      }
    } catch {
      setError(
        'Не удалось подготовить запрос. Введённые данные сохранены в форме; попробуйте ещё раз.',
      );
      setFeedbackVersion((value) => value + 1);
      return;
    }
    inFlight.current = true;
    setBusy(true);
    setError('');
    setValidationAttempt(undefined);
    setPending(input);
    setFeedbackVersion((value) => value + 1);
    try {
      const response = await fetch(apiUrl('/api/parking/legal'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-NormLab-Token': token },
        body: JSON.stringify(input),
        signal: AbortSignal.timeout(60000),
      });
      const body = await response.json().catch(() => null);
      if (!response.ok) {
        // A known rejection did not publish a record. Unknown transport outcomes keep the ID.
        if (response.status >= 400 && response.status < 500) setPending(undefined);
        throw new Error(body?.error ?? `Сервер отклонил запрос (HTTP ${response.status}).`);
      }
      if (!body) throw new Error('Сервер вернул нечитаемый ответ. Сохранение не подтверждено.');
      const saved = body as LegalAssessment;
      setRecord(saved);
      setDirty(false);
      setPending(undefined);
      setWorkspace({
        ...workspace,
        assessments: [saved, ...workspace.assessments.filter((r) => r.id !== saved.id)],
      });
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      inFlight.current = false;
      setBusy(false);
      setFeedbackVersion((value) => value + 1);
    }
  }
  return (
    <Panel aria-label="Юридические обстоятельства и расчёт">
      <SectionHeading
        step="05"
        title="Юридические обстоятельства и расчёт"
        description="Выберите эпизод и получите подготовленные кандидаты. Проверьте основания и одобрите каждое решение перед расчётом."
      />
      <Notice>
        PoC: упрощённая модель ч. 2 ст. 8.14 КоАП города Москвы. Вы подтверждаете обстоятельства,
        приложение рассчитывает результат, Lean проверяет соблюдение правил этой модели.
      </Notice>
      {blocked && (
        <Notice tone="warning">
          Сначала завершите проверку текущего текста и сохраните правки. Старые расчёты остаются в
          истории и не переносятся на новую ревизию.
        </Notice>
      )}
      {error && (!workspace || blocked) && (
        <Notice tone="danger" role="alert">
          {error}
        </Notice>
      )}
      {!workspace && (
        <Button variant="secondary" disabled={loading} onClick={() => setRefresh((v) => v + 1)}>
          {loading ? 'Загрузка обстоятельств…' : 'Загрузить обстоятельства'}
        </Button>
      )}
      {workspace && (
        <>
          <Disclosure summary="Что входит в пакет норм">
            <p>
              {workspace.package.title} · {workspace.package.version}.{' '}
              {workspace.package.editionLabel}
            </p>
            <p className="parking-help">
              Федеральный КоАП РФ — отдельная зависимость, а не название московской статьи. ID
              пакета: {workspace.package.id}. Digest: {workspace.packageDigest}
            </p>
            <ul>
              {workspace.package.sources.map((source) => (
                <li key={source.id}>
                  <a href={source.url} target="_blank" rel="noreferrer">
                    {source.id}: {source.locator}
                  </a>{' '}
                  — {source.evidence}
                </li>
              ))}
            </ul>
            <p>Открытые зависимости:</p>
            <ul>
              {workspace.package.openDependencies.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </Disclosure>
          {!blocked && (
            <>
              <LegalScopeEditor
                coordinates={coordinates}
                compact
                episodes={episodes}
                claimedFine={claimedFine}
                disabled={editorDisabled}
                issues={issues}
                onChange={changeCoordinates}
                onFineChange={(next) => {
                  setClaimedFine(next);
                  setDirty(true);
                  setError('');
                }}
              />
              <LegalProposals
                key={`${draft.draftId}:${draft.revisionId}:${coordinates.episode}`}
                draft={draft}
                token={token}
                episode={coordinates.episode}
                expectedAssessmentId={workspace.assessments[0]?.id ?? null}
                packageDigest={workspace.packageDigest}
                disabled={editorDisabled}
                statements={confirmed.filter((item) => item.aboutEpisode === coordinates.episode)}
                coordinateProposalId={coordinateProposalId}
                onAcceptCoordinates={acceptCoordinates}
                onProposal={setProposal}
                onWorking={setProposing}
                onRecorded={onSaved}
              />
              {activeProposal && !scopeApproved && (
                <Notice>
                  Сначала проверьте и примите предложенные координаты эпизода. Затем одобрите каждое
                  обстоятельство отдельно.
                </Notice>
              )}
              {resetNotice && <Notice tone="warning">{resetNotice}</Notice>}
              <div className="parking-statement-list">
                {workspace.package.conditions.map((condition) => {
                  const finding = findings.find((item) => item.conditionId === condition.id)!;
                  const candidate = activeProposal?.suggestion.findings.find(
                    (item) => item.conditionId === condition.id,
                  );
                  const statements = confirmed.filter(
                    (item) => item.aboutEpisode === coordinates.episode,
                  );
                  return candidate && activeProposal ? (
                    <LegalCandidate
                      key={condition.id}
                      condition={condition}
                      candidate={candidate}
                      finding={finding}
                      proposalId={activeProposal.proposalId}
                      statements={statements}
                      disabled={editorDisabled}
                      acceptDisabled={!scopeApproved}
                      issues={issues}
                      onAccept={() =>
                        change(condition.id, {
                          ...candidate,
                          proposalId: activeProposal.proposalId,
                        })
                      }
                      onChange={(patch) => change(condition.id, patch)}
                    />
                  ) : (
                    <LegalFindingEditor
                      key={condition.id}
                      condition={condition}
                      finding={finding}
                      statements={statements}
                      disabled={editorDisabled || !coordinates.episode}
                      issues={issues}
                      onChange={(patch) => change(condition.id, patch)}
                    />
                  );
                })}
              </div>
              {clarificationDirty && (
                <Notice>
                  Сначала проверьте и подтвердите{' '}
                  <a href="#parking-legal-clarifications">подготовленные ответы ниже</a> либо
                  отмените их, чтобы вернуться к редакторам.
                </Notice>
              )}
              <Actions>
                <Button
                  variant="secondary"
                  disabled={editorDisabled}
                  onClick={() => void submit('save')}
                >
                  {busy && pending?.action === 'save' ? 'Сохраняем…' : 'Сохранить обстоятельства'}
                </Button>
                <Button
                  disabled={editorDisabled}
                  aria-busy={busy}
                  onClick={() => void submit('calculate')}
                >
                  {busy
                    ? pending?.action === 'calculate'
                      ? 'Расчёт и проверка Lean…'
                      : 'Сохраняем…'
                    : 'Рассчитать и проверить в Lean'}
                </Button>
                {pending && !busy && (
                  <Button
                    disabled={blocked || clarificationDirty}
                    onClick={() => void submit(pending.action)}
                  >
                    Повторить тот же запрос
                  </Button>
                )}
              </Actions>
              {feedbackOrigin === 'actions' && (
                <LegalActionFeedback
                  error={error}
                  issues={issues}
                  validationAttempted={!!validationAttempt}
                  busy={busy}
                  action={pending?.action ?? validationAttempt?.action}
                  record={!dirty && !pending ? record : undefined}
                  feedbackRef={feedbackRef}
                />
              )}
              {pending && !busy && (
                <Notice tone="warning">
                  Ответ не получен. Сохранение могло выполниться. Повтор использует прежний ID и не
                  создаст вторую запись.
                </Notice>
              )}
            </>
          )}
          <Actions>
            {!pending && !busy && !proposing && !loading && !clarificationDirty && (
              <Button
                variant="quiet"
                onClick={() => {
                  if (
                    !dirty ||
                    window.confirm(
                      'Загрузить сохранённые решения и отменить локальные правки обстоятельств?',
                    )
                  )
                    setRefresh((v) => v + 1);
                }}
              >
                {dirty
                  ? 'Отменить несохранённые правки обстоятельств'
                  : 'Обновить сохранённые решения'}
              </Button>
            )}
          </Actions>
          <LegalResultView
            token={token}
            onRecorded={onSaved}
            record={record}
            workspace={workspace}
            stale={dirty || blocked || busy || proposing || clarificationDirty || !!pending}
          />
          {!blocked && (
            <>
              <LegalClarifications
                key={`${draft.revisionId}:${workspace.packageDigest}:${workspace.assessments[0]?.id ?? ''}:${clarificationEpoch}`}
                values={clarificationValues}
                conditions={workspace.package.conditions}
                statements={confirmed.filter((item) => item.aboutEpisode === coordinates.episode)}
                disabled={disabled}
                onDirty={setClarificationDirty}
                onConfirm={confirmClarifications}
              />
              {feedbackOrigin === 'clarifications' && (
                <>
                  <LegalActionFeedback
                    error={error}
                    issues={issues}
                    validationAttempted={!!validationAttempt}
                    busy={busy}
                    action={pending?.action ?? validationAttempt?.action}
                    record={!dirty && !pending ? record : undefined}
                    feedbackRef={clarificationFeedbackRef}
                  />
                  {pending && !busy && (
                    <>
                      <Notice tone="warning">
                        Сохранение могло выполниться. Повтор использует тот же ID; новые ответы пока
                        не применяйте.
                      </Notice>
                      <Button
                        onClick={() => void submit(pending.action, undefined, 'clarifications')}
                      >
                        Повторить сохранение с тем же ID
                      </Button>
                    </>
                  )}
                  {!dirty && !pending && !busy && record && !record.result && (
                    <Button
                      disabled={disabled || clarificationDirty}
                      onClick={() => void submit('calculate', undefined, 'clarifications')}
                    >
                      Пересчитать и проверить в Lean
                    </Button>
                  )}
                </>
              )}
            </>
          )}
          <Disclosure summary={`История юридических решений · ${workspace.assessments.length}`}>
            {workspace.assessments.map((item) => (
              <Disclosure
                key={item.id}
                summary={`№ ${item.sequence} · ${new Date(item.createdAt).toLocaleString('ru-RU')} · ${item.input.expectedRevisionId === draft.revisionId ? 'эта ревизия' : 'другая ревизия'} · ${item.result ? legalOutcomeLabels[item.result.outcome] : 'сохранение'}`}
              >
                <pre>{JSON.stringify(item, null, 2)}</pre>
              </Disclosure>
            ))}
          </Disclosure>
        </>
      )}
    </Panel>
  );
}
