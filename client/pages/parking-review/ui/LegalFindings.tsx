import { useEffect, useRef, useState } from 'react';
import { apiUrl } from '@/shared/api';
import { Actions, Button, Disclosure, Notice, Panel, SectionHeading } from '@/shared/ui';
import {
  emptyLegalFindings,
  legalInputSchema,
  legalOutcomeLabels,
  type LegalAssessment,
  type LegalFinding,
  type LegalInput,
  type LegalWorkspace,
  type ReviewDraft,
} from '../model/contracts.js';
import { legalValidationIssues } from '../model/legal-validation.js';

import { LegalActionFeedback } from './LegalActionFeedback.js';
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
    if (!feedbackVersion || !feedbackRef.current) return;
    const feedback = feedbackRef.current;
    feedback.focus({ preventScroll: true });
    const bounds = feedback.getBoundingClientRect();
    if (bounds.top < 0 || bounds.bottom > window.innerHeight)
      feedback.scrollIntoView({ block: 'start' });
  }, [feedbackVersion]);
  useEffect(() => {
    onUnsavedChange(dirty || busy || !!pending);
  }, [dirty, busy, pending, onUnsavedChange]);
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
  const disabled = blocked || busy || loading || !!pending || !workspace;
  function makeInput(attempt: Pick<LegalInput, 'action' | 'requestId'>): LegalInput {
    return {
      ...coordinates,
      findings,
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
      return;
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
      return;
    setCoordinates(next);
    setFindings(emptyLegalFindings());
    setDirty(true);
    setValidationAttempt(undefined);
    setError('');
    if (hasDecisions)
      setResetNotice('Координаты изменены. Укажите решения, основания и ссылки заново.');
  }
  async function submit(action: LegalInput['action']) {
    if (inFlight.current || blocked || loading || !workspace) return;
    let input: LegalInput;
    try {
      if (pending) input = pending;
      else {
        const attempt = { action, requestId: crypto.randomUUID() };
        const parsed = legalInputSchema.safeParse(makeInput(attempt));
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
        description="После проверки текста отдельно установите обстоятельства одного эпизода — модель не принимает эти решения за вас."
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
                episodes={episodes}
                claimedFine={claimedFine}
                disabled={disabled}
                issues={issues}
                onChange={changeCoordinates}
                onFineChange={(next) => {
                  setClaimedFine(next);
                  setDirty(true);
                  setError('');
                }}
              />
              {resetNotice && <Notice tone="warning">{resetNotice}</Notice>}
              <div className="parking-statement-list">
                {workspace.package.conditions.map((condition) => (
                  <LegalFindingEditor
                    key={condition.id}
                    condition={condition}
                    finding={findings.find((f) => f.conditionId === condition.id)!}
                    statements={confirmed.filter(
                      (item) => item.aboutEpisode === coordinates.episode,
                    )}
                    disabled={disabled || !coordinates.episode}
                    issues={issues}
                    onChange={(patch) => change(condition.id, patch)}
                  />
                ))}
              </div>
              <Actions>
                <Button variant="secondary" disabled={disabled} onClick={() => void submit('save')}>
                  {busy && pending?.action === 'save' ? 'Сохраняем…' : 'Сохранить обстоятельства'}
                </Button>
                <Button
                  disabled={disabled}
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
                  <Button disabled={blocked} onClick={() => void submit(pending.action)}>
                    Повторить тот же запрос
                  </Button>
                )}
              </Actions>
              <LegalActionFeedback
                error={error}
                issues={issues}
                validationAttempted={!!validationAttempt}
                busy={busy}
                action={pending?.action ?? validationAttempt?.action}
                record={!dirty && !pending ? record : undefined}
                feedbackRef={feedbackRef}
              />
              {pending && !busy && (
                <Notice tone="warning">
                  Ответ не получен. Сохранение могло выполниться. Повтор использует прежний ID и не
                  создаст вторую запись.
                </Notice>
              )}
            </>
          )}
          <Actions>
            {!pending && !busy && !loading && (
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
            record={record}
            workspace={workspace}
            stale={dirty || blocked || !!pending}
          />
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
