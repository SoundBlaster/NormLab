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
  const inFlight = useRef(false);
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
  const change = (conditionId: string, patch: Partial<LegalFinding>) => {
    setFindings((items) =>
      items.map((item) => (item.conditionId === conditionId ? { ...item, ...patch } : item)),
    );
    setDirty(true);
  };
  async function submit(action: LegalInput['action']) {
    if (inFlight.current || blocked || loading || !workspace) return;
    let input: LegalInput;
    try {
      input =
        pending ??
        legalInputSchema.parse({
          ...coordinates,
          findings,
          claimedFine: claimedFine === '' ? null : Number(claimedFine),
          draftId: draft.draftId,
          expectedRevisionId: draft.revisionId,
          expectedAssessmentId: workspace.assessments[0]?.id ?? null,
          requestId: crypto.randomUUID(),
          packageDigest: workspace.packageDigest,
          action,
        });
    } catch {
      setError(
        'Выберите эпизод. Пустые сведения сохраняются как пробелы. Каждое рассмотренное обстоятельство требует основания; сумма должна быть целым неотрицательным числом.',
      );
      return;
    }
    inFlight.current = true;
    setBusy(true);
    setError('');
    setPending(input);
    try {
      const response = await fetch(apiUrl('/api/parking/legal'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-NormLab-Token': token },
        body: JSON.stringify(input),
        signal: AbortSignal.timeout(15000),
      });
      const body = await response.json();
      if (!response.ok) {
        // A known rejection did not publish a record. Unknown transport outcomes keep the ID.
        if (response.status >= 400 && response.status < 500) setPending(undefined);
        throw new Error(body.error ?? 'Сохранение не подтверждено.');
      }
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
    }
  }
  return (
    <Panel aria-label="Юридические обстоятельства и расчёт">
      <SectionHeading
        step="05"
        title="Юридические обстоятельства и расчёт"
        description="После проверки текста отдельно установите обстоятельства одного эпизода — модель не принимает эти решения за вас."
      />
      <Notice tone="warning">
        Исследовательский пакет: ч. 2 ст. 8.14 КоАП города Москвы. Применимая редакция и общие
        условия ответственности ещё не зафиксированы. Вычисляется только draft-фрагмент; это не
        установленная ответственность и не проверка Lean.
      </Notice>
      {blocked && (
        <Notice tone="warning">
          Сначала завершите проверку текущего текста и сохраните правки. Старые расчёты остаются в
          истории и не переносятся на новую ревизию.
        </Notice>
      )}
      {error && (
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
                onChange={(next) => {
                  setCoordinates(next);
                  setFindings(emptyLegalFindings());
                  setDirty(true);
                }}
                onFineChange={(next) => {
                  setClaimedFine(next);
                  setDirty(true);
                }}
              />
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
                    onChange={(patch) => change(condition.id, patch)}
                  />
                ))}
              </div>
              <Actions>
                <Button variant="secondary" disabled={disabled} onClick={() => void submit('save')}>
                  Сохранить обстоятельства
                </Button>
                <Button
                  disabled={disabled}
                  aria-busy={busy}
                  onClick={() => void submit('calculate')}
                >
                  {busy ? 'Сохраняем…' : 'Рассчитать фрагмент нормы'}
                </Button>
                {pending && !busy && (
                  <Button disabled={blocked} onClick={() => void submit(pending.action)}>
                    Повторить тот же запрос
                  </Button>
                )}
              </Actions>
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
