import { useEffect, useRef, useState } from 'react';
import {
  emptyReviewChecklist,
  emptyNarrativeContext,
  narrativeRoute,
  reviewDraftMetadata,
  reviewMetadataIssues,
  type NarrativeContext,
  type VehicleHypothesis,
  type ReviewDraft,
  type ReviewStatement,
} from '../model/contracts.js';
import {
  Actions,
  Button,
  CheckField,
  Disclosure,
  Field,
  Panel,
  Notice,
  SectionHeading,
  Select,
  Status,
  Textarea,
} from '@/shared/ui';
import { apiUrl } from '@/shared/api';
import { StatementEditor } from './StatementEditor.js';
import { ContextEditor } from './ContextEditor.js';
import { HypothesisEditor } from './HypothesisEditor.js';
import { NewStatementEditor, type StatementSource } from './NewStatementEditor.js';
import { reviewReferences, hasStatementChoices } from '../model/statement-fields.js';
import { canPersistReview, type ReviewContent } from '../model/review-persistence.js';
import './review.css';

const checklistNames = {
  negatives: 'Все явные отрицания сохранены.',
  conflicts: 'Противоречащие утверждения сохранены отдельно.',
  attribution: 'Участники, транспортные средства и эпизод различены правильно.',
  sourceSupport: 'Каждое утверждение поддержано своей цитатой; выдуманных фактов нет.',
  unknowns: 'Пробелы отмечены; отсутствие сведений не превращено в отрицание.',
};
type Bootstrap = {
  drafts: ReviewDraft[];
  extractorAvailable: boolean;
  externalInference: boolean;
  cases: { id: string; narrative: string }[];
};
export function ParkingReview({ token }: { token: string }) {
  const [data, setData] = useState<Bootstrap>();
  const [draft, setDraft] = useState<ReviewDraft>();
  const [history, setHistory] = useState<ReviewDraft[]>([]);
  const [narrative, setNarrative] = useState('');
  const [selection, setSelection] = useState<{ start: number; end: number }>();
  const [newStatement, setNewStatement] = useState<StatementSource>();
  const [statements, setStatements] = useState<ReviewStatement[]>([]);
  const [context, setContext] = useState(emptyNarrativeContext);
  const [hypotheses, setHypotheses] = useState<VehicleHypothesis[]>([]);
  const [metadataPendingSave, setMetadataPendingSave] = useState(false);
  const [checklist, setChecklist] = useState({ ...emptyReviewChecklist });
  const [busy, setBusy] = useState(false);
  const inFlight = useRef(false);
  const [saveState, setSaveState] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');
  const [dirty, setDirty] = useState(false);
  const [reviewDirty, setReviewDirty] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [newSourceApproved, setNewSourceApproved] = useState(false);
  const sourceRef = useRef<HTMLTextAreaElement>(null);
  async function request<T>(path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
    const response = await fetch(
      apiUrl(path),
      body === undefined
        ? { signal }
        : {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-NormLab-Token': token },
            body: JSON.stringify(body),
            signal,
          },
    );
    const result = await response.json();
    if (!response.ok) throw new Error(result.error ?? 'Ошибка парковочного пилота');
    return result as T;
  }
  async function load() {
    const result = await request<Bootstrap>('/api/parking/bootstrap');
    setData(result);
    return result;
  }
  function open(item: ReviewDraft) {
    setDraft(item);
    setStatements(item.statements);
    const metadata = reviewDraftMetadata(item);
    setContext(metadata.context);
    setHypotheses(metadata.hypotheses);
    setMetadataPendingSave(false);
    setChecklist(item.checklist);
    setNarrative(item.narrative);
    setSelection(undefined);
    setNewStatement(undefined);
    setDirty(false);
    setReviewDirty(false);
    setNewSourceApproved(false);
    setHistory([]);
    setError('');
    setNotice('');
    setSaveState('idle');
  }
  useEffect(() => {
    let active = true;
    request<Bootstrap>('/api/parking/bootstrap')
      .then((result) => {
        if (!active) return;
        setData(result);
        if (result.drafts[0]) open(result.drafts[0]);
        else setNarrative(result.cases[0]?.narrative ?? '');
      })
      .catch((e: unknown) => {
        if (active) setError(e instanceof Error ? e.message : String(e));
      });
    return () => {
      active = false;
    };
    // Session token is immutable for this mounted workbench.
  }, [token]);
  const historical =
    !!draft &&
    data?.drafts.find((d) => d.draftId === draft.draftId)?.revisionId !== draft.revisionId;
  async function act(action: () => Promise<void>) {
    if (inFlight.current) return;
    inFlight.current = true;
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await action();
    } catch (e) {
      setError(
        e instanceof Error && e.name === 'TimeoutError'
          ? 'Не удалось дождаться ответа сервера. Сохранение не подтверждено; ваши изменения остаются в форме.'
          : e instanceof Error
            ? e.message
            : String(e),
      );
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }
  function change(id: string, patch: Partial<ReviewStatement>) {
    if (inFlight.current) return;
    setStatements((items) =>
      items.map((s) =>
        s.id === id ? { ...s, ...patch, origin: 'human', decision: 'pending' } : s,
      ),
    );
    setChecklist({ ...emptyReviewChecklist });
    setDirty(true);
  }
  function invalidateMetadata(contentChanged: boolean) {
    setStatements((items) => items.map((s) => ({ ...s, decision: 'pending' })));
    setChecklist({ ...emptyReviewChecklist });
    setMetadataPendingSave(true);
    if (contentChanged) setDirty(true);
    else setReviewDirty(true);
  }
  function changeContext(patch: Partial<NarrativeContext>) {
    if (inFlight.current) return;
    setContext((value) => ({ ...value, ...patch, decision: 'pending' }));
    setHypotheses((items) => items.map((h) => ({ ...h, decision: 'pending' })));
    invalidateMetadata(true);
  }
  function changeHypothesis(id: string, patch: Partial<VehicleHypothesis>) {
    if (inFlight.current) return;
    setHypotheses((items) =>
      items.map((h) => (h.id === id ? { ...h, ...patch, decision: 'pending' } : h)),
    );
    invalidateMetadata(true);
  }
  function addHypothesis() {
    if (inFlight.current) return;
    if (!draft || !selection || selection.end <= selection.start) return;
    setHypotheses((items) => [
      ...items,
      {
        id: crypto.randomUUID(),
        kind: 'transport-vehicle',
        vehicleKind: 'unspecified',
        vehicleKindDetails: '',
        aboutEpisode: 'episode_1',
        quote: draft.narrative.slice(selection.start, selection.end),
        startOffset: selection.start,
        endOffset: selection.end,
        origin: 'human',
        decision: 'pending',
        rationale: '',
      },
    ]);
    invalidateMetadata(true);
    setNotice(
      'Гипотеза о ТС добавлена отдельно от утверждений. Дождитесь автосохранения, затем подтвердите или отклоните.',
    );
  }
  async function save(
    finishReview: boolean,
    content: ReviewContent = { statements, context, hypotheses, checklist },
  ) {
    if (!draft || historical || newStatement || !canPersistReview(draft, content)) return;
    setSaveState('saving');
    try {
      const result = await request<ReviewDraft>(
        '/api/parking/review',
        {
          draftId: draft.draftId,
          expectedRevisionId: draft.revisionId,
          ...content,
          finishReview,
        },
        // Aborting the wait does not prove that the server rejected the write.
        // Preserve local intent and require explicit retry against the same revision.
        AbortSignal.timeout(15_000),
      );
      // The POST response is the saved authority. Do not refresh bootstrap or
      // reopen the page: both would risk discarding a locally edited narrative.
      setDraft(result);
      setStatements(result.statements);
      const metadata = reviewDraftMetadata(result);
      setContext(metadata.context);
      setHypotheses(metadata.hypotheses);
      setChecklist(result.checklist);
      setMetadataPendingSave(false);
      setDirty(false);
      setReviewDirty(false);
      setHistory([]);
      setData(
        (current) =>
          current && {
            ...current,
            drafts: [result, ...current.drafts.filter((item) => item.draftId !== result.draftId)],
          },
      );
      setSaveState('saved');
      setNotice(
        finishReview
          ? 'Проверка человеком сохранена. Правовой расчёт ещё не выполнен.'
          : 'Ревизия сохранена. Каждое решение проверяющего сохраняется сразу.',
      );
    } catch (failure) {
      setSaveState('error');
      throw failure;
    }
  }
  function decide(content: ReviewContent) {
    if (
      !draft ||
      inFlight.current ||
      dirty ||
      reviewDirty ||
      metadataPendingSave ||
      newStatement ||
      historical ||
      saveState === 'error' ||
      !canPersistReview(draft, content)
    )
      return;
    void act(async () => {
      setStatements(content.statements);
      setContext(content.context);
      setHypotheses(content.hypotheses);
      setChecklist(content.checklist);
      setReviewDirty(true);
      if (
        JSON.stringify({ context, hypotheses }) !==
        JSON.stringify({ context: content.context, hypotheses: content.hypotheses })
      )
        setMetadataPendingSave(true);
      await save(false, content);
    });
  }
  const persistable =
    !!draft &&
    !newStatement &&
    canPersistReview(draft, {
      statements,
      context,
      hypotheses,
      checklist,
    });
  useEffect(() => {
    if (
      !draft ||
      historical ||
      busy ||
      !persistable ||
      (!dirty && !reviewDirty) ||
      saveState === 'error'
    )
      return;
    const timer = window.setTimeout(() => {
      void act(() => save(false));
    }, 700);
    return () => window.clearTimeout(timer);
  }, [
    draft,
    historical,
    busy,
    persistable,
    dirty,
    reviewDirty,
    saveState,
    statements,
    context,
    hypotheses,
    checklist,
    newStatement,
  ]);
  function addSelection() {
    if (inFlight.current) return;
    if (!draft || !selection || selection.end <= selection.start) return;
    setNewStatement({
      quote: draft.narrative.slice(selection.start, selection.end),
      startOffset: selection.start,
      endOffset: selection.end,
    });
    setNotice('Цитата выбрана. Задайте смысл нового утверждения перед добавлением к проверке.');
  }

  function exportDraft() {
    if (!draft) return;
    const blob = new Blob([JSON.stringify(draft, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob),
      link = document.createElement('a');
    link.href = url;
    link.download = `parking-review-${draft.draftId}-r${draft.revision}.json`;
    link.click();
    URL.revokeObjectURL(url);
  }
  const references = reviewReferences(draft?.originalExtraction, statements, hypotheses);
  const incompleteStatements = statements.some((statement) => !hasStatementChoices(statement));
  const incompleteHypotheses = hypotheses.some((hypothesis) => !hypothesis.aboutEpisode.trim());
  const metadataIssues = reviewMetadataIssues(context, hypotheses);
  const savedMetadata = draft ? reviewDraftMetadata(draft) : undefined;
  const contextPendingSave =
    !!savedMetadata && JSON.stringify(context) !== JSON.stringify(savedMetadata.context);
  return (
    <section className="parking-review" aria-label="Проверка утверждений парковочного пилота">
      <Notice className="stale-note" tone="warning">
        Эксперимент извлечения. Утверждения требуют проверки человеком. Решение по КоАП здесь не
        рассчитывается.
      </Notice>
      {error && (
        <Notice tone="danger" role="alert">
          {error}
        </Notice>
      )}
      <Notice tone="success" role="status" aria-live="polite">
        {notice}
      </Notice>
      {draft && (
        <Notice
          role="status"
          aria-live="polite"
          tone={
            saveState === 'error'
              ? 'danger'
              : dirty || reviewDirty
                ? 'warning'
                : saveState === 'saved'
                  ? 'success'
                  : 'neutral'
          }
        >
          {saveState === 'saving'
            ? 'Сохранение ревизии…'
            : saveState === 'error'
              ? 'Сохранение не подтверждено. Локальные изменения сохранены в форме. Автосохранение остановлено; повторите сохранение вручную. При конфликте ревизий требуется сверка с сервером.'
              : dirty || reviewDirty
                ? persistable
                  ? 'Есть изменения · автосохранение через короткую паузу.'
                  : 'Есть изменения · заполните корректные значения для автосохранения.'
                : `Сохранена ревизия ${draft.revision}.`}
        </Notice>
      )}
      <Panel>
        <SectionHeading
          step="01"
          title="Описание события"
          description="Начните с фабулы или вернитесь к сохранённому разбору."
        />
        <Field label="Открыть сохранённый черновик">
          <Select
            value={draft?.draftId ?? ''}
            disabled={busy || dirty || reviewDirty || !!newStatement}
            onChange={(e) => {
              const item = data?.drafts.find((d) => d.draftId === e.target.value);
              if (item) open(item);
            }}
          >
            <option value="">Новый черновик</option>
            {data?.drafts.map((d) => (
              <option key={d.draftId} value={d.draftId}>
                {new Date(d.createdAt).toLocaleString('ru-RU')} · ревизия {d.revision}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Описание события">
          <Textarea
            rows={5}
            value={narrative}
            disabled={busy}
            onChange={(e) => {
              setNarrative(e.target.value);
              setNewSourceApproved(false);
            }}
          />
        </Field>
        {!draft && (
          <Field label="Учебный пример">
            <Select
              disabled={busy}
              value=""
              onChange={(e) => {
                setNarrative(
                  data?.cases.find((c) => c.id === e.target.value)?.narrative ?? narrative,
                );
              }}
            >
              <option value="">Выбрать пример</option>
              {data?.cases.map((c) => (
                <option key={c.id}>{c.id}</option>
              ))}
            </Select>
          </Field>
        )}
        {draft && (
          <CheckField
            checked={newSourceApproved}
            disabled={busy}
            onChange={(e) => setNewSourceApproved(e.target.checked)}
          >
            Создать новый черновик: сохранить прежний разбор и начать с пустыми подтверждениями.
          </CheckField>
        )}
        <Button
          disabled={
            busy ||
            dirty ||
            reviewDirty ||
            !!newStatement ||
            !narrative.trim() ||
            (!!draft && !newSourceApproved)
          }
          onClick={() =>
            void act(async () => {
              const result = await request<ReviewDraft>('/api/parking/drafts', {
                narrative,
                ...(draft ? { previousDraftId: draft.draftId } : {}),
              });
              await load();
              open(result);
            })
          }
        >
          Создать черновик
        </Button>
      </Panel>
      {draft && (
        <>
          <Panel>
            <SectionHeading
              step="02"
              title="Контекст обращения"
              description="Выберите тему всего текста. Контекст направляет разбор, но не устанавливает обстоятельства события."
            />
            {draft.schema === 'normlab.parking-review/v1' && (
              <Notice tone="warning">
                В этой ревизии контекст и гипотезы ещё не проверялись. Исходная ревизия сохранена в
                истории.
              </Notice>
            )}
            {metadataPendingSave && (
              <Notice tone="warning">
                Контекст или гипотезы изменены. Сохраните ревизию; подтверждения утверждений
                сброшены.
              </Notice>
            )}
            <ContextEditor
              context={context}
              disabled={
                busy || historical || !!newStatement || incompleteStatements || incompleteHypotheses
              }
              canConfirm={
                !dirty &&
                !reviewDirty &&
                !metadataPendingSave &&
                !newStatement &&
                saveState !== 'error' &&
                persistable
              }
              canSave={persistable && (dirty || reviewDirty || saveState === 'error')}
              pendingSave={contextPendingSave}
              onChange={changeContext}
              onSave={() => void act(() => save(false))}
              onConfirm={() => {
                if (context.decision === 'confirmed') return;
                decide({
                  context: { ...context, decision: 'confirmed' },
                  hypotheses,
                  statements: statements.map((statement) => ({
                    ...statement,
                    decision: 'pending',
                  })),
                  checklist: { ...emptyReviewChecklist },
                });
              }}
            />
          </Panel>
          <Panel>
            <SectionHeading
              step="03"
              title={`Источник · ревизия ${draft.revision}`}
              description="Получите предложения модели или выделите цитату и добавьте утверждение вручную."
            />
            <Status
              className="parking-review-state"
              tone={
                draft.status === 'reviewed' && !metadataIssues.length && !dirty && !reviewDirty
                  ? 'success'
                  : 'warning'
              }
            >
              {draft.status === 'reviewed' && !metadataIssues.length && !dirty && !reviewDirty
                ? 'Проверено человеком'
                : 'Проверка не завершена'}
              {historical ? ' · историческая ревизия, только чтение' : ''}
            </Status>
            {historical && (
              <Button
                variant="secondary"
                disabled={busy}
                onClick={() => {
                  const latest = data?.drafts.find((d) => d.draftId === draft.draftId);
                  if (latest) open(latest);
                }}
              >
                Открыть актуальную ревизию
              </Button>
            )}
            {narrative !== draft.narrative && (
              <Notice className="stale-note" tone="warning">
                Вы изменили фабулу выше. Для её разбора создайте новый черновик. Ниже показан
                сохранённый источник.
              </Notice>
            )}
            <Field label="Выделите фрагмент для нового утверждения">
              <Textarea
                ref={sourceRef}
                readOnly
                disabled={busy}
                rows={4}
                value={draft.narrative}
                onSelect={() => {
                  const input = sourceRef.current;
                  if (input) setSelection({ start: input.selectionStart, end: input.selectionEnd });
                }}
              />
            </Field>
            <Actions>
              <Button
                variant="secondary"
                disabled={
                  busy ||
                  historical ||
                  !selection ||
                  selection.end <= selection.start ||
                  !!newStatement ||
                  statements.length >= 256 ||
                  selection.end - selection.start > 4096
                }
                onClick={addSelection}
              >
                Добавить выделенное утверждение
              </Button>
              <Button
                variant="secondary"
                disabled={
                  busy ||
                  historical ||
                  !selection ||
                  selection.end <= selection.start ||
                  hypotheses.length >= 64 ||
                  selection.end - selection.start > 4096
                }
                onClick={addHypothesis}
              >
                Предложить гипотезу о ТС из выделенного
              </Button>
              <Button
                disabled={
                  busy ||
                  dirty ||
                  reviewDirty ||
                  historical ||
                  narrative !== draft.narrative ||
                  !!newStatement ||
                  !data?.extractorAvailable ||
                  context.decision !== 'confirmed' ||
                  narrativeRoute(context) !== 'parking-review'
                }
                onClick={() =>
                  void act(async () => {
                    const result = await request<ReviewDraft>('/api/parking/extract', {
                      draftId: draft.draftId,
                      expectedRevisionId: draft.revisionId,
                    });
                    await load();
                    open(result);
                    setNotice(
                      'Предложение модели сохранено. Проверьте все утверждения и пропуски.',
                    );
                  })
                }
              >
                {busy ? 'Выполняется…' : 'Выделить и классифицировать утверждения'}
              </Button>
              <Button
                variant="secondary"
                disabled={dirty || reviewDirty || busy}
                onClick={exportDraft}
              >
                Скачать сохранённую ревизию
              </Button>
            </Actions>
            {newStatement && (
              <NewStatementEditor
                source={newStatement}
                references={references}
                disabled={busy || historical}
                onCancel={() => setNewStatement(undefined)}
                onCreate={(statement) => {
                  setStatements((items) => [...items, statement]);
                  setNewStatement(undefined);
                  setChecklist({ ...emptyReviewChecklist });
                  setDirty(true);
                  setNotice(
                    'Утверждение добавлено. Дождитесь автосохранения, затем подтвердите его отдельно.',
                  );
                }}
              />
            )}
            {!data?.extractorAvailable && (
              <p>Автоматическое извлечение не настроено. Ручная разметка доступна.</p>
            )}
            {data?.externalInference && (
              <p className="parking-help">
                При извлечении фабула отправляется внешнему AI-провайдеру. Используйте синтетические
                примеры. Каждое предложение требует вашего подтверждения.
              </p>
            )}
            {hypotheses.length > 0 && (
              <>
                <h3>Гипотезы · {hypotheses.length}</h3>
                <p className="parking-help">
                  Гипотезы не добавляют утверждения и не передаются в правовой расчёт. Наличие ТС не
                  устанавливает его вид, водителя или собственника.
                </p>
                {metadataPendingSave && (
                  <Notice tone="warning">
                    Изменения гипотез ещё не сохранены. После сохранения проверьте утверждения
                    заново.
                  </Notice>
                )}
                <div className="parking-statement-list">
                  {hypotheses.map((hypothesis) => (
                    <HypothesisEditor
                      key={hypothesis.id}
                      hypothesis={hypothesis}
                      references={references}
                      narrative={draft.narrative}
                      disabled={busy || historical}
                      dirty={
                        dirty ||
                        reviewDirty ||
                        metadataPendingSave ||
                        !!newStatement ||
                        saveState === 'error'
                      }
                      pendingSave={
                        JSON.stringify(hypothesis) !==
                        JSON.stringify(
                          savedMetadata?.hypotheses.find((item) => item.id === hypothesis.id),
                        )
                      }
                      canReplaceQuote={
                        !!selection &&
                        selection.end > selection.start &&
                        selection.end - selection.start <= 4096
                      }
                      onChange={(patch) => changeHypothesis(hypothesis.id, patch)}
                      onDecision={(decision) => {
                        if (hypothesis.decision === decision) return;
                        decide({
                          context,
                          hypotheses: hypotheses.map((item) =>
                            item.id === hypothesis.id ? { ...item, decision } : item,
                          ),
                          statements: statements.map((statement) => ({
                            ...statement,
                            decision: 'pending',
                          })),
                          checklist: { ...emptyReviewChecklist },
                        });
                      }}
                      onReplaceQuote={() => {
                        if (selection)
                          changeHypothesis(hypothesis.id, {
                            quote: draft.narrative.slice(selection.start, selection.end),
                            startOffset: selection.start,
                            endOffset: selection.end,
                          });
                      }}
                    />
                  ))}
                </div>
              </>
            )}
            {draft.originalExtraction !== null && (
              <Disclosure summary="Исходное предложение модели">
                <pre>{JSON.stringify(draft.originalExtraction, null, 2)}</pre>
              </Disclosure>
            )}
          </Panel>
          <Panel>
            <SectionHeading
              step="04"
              title={`Проверка утверждений · ${statements.length}`}
              description="Сопоставьте каждое утверждение с цитатой. Исправьте смысл, дождитесь автосохранения и подтвердите."
            />
            <p className="parking-help">
              Проверьте полноту: время и место, автомобиль и участник, размещение, платный режим,
              оплата и её время, отъезд, ошибки оплаты и разрешения. Если сведений нет, это пробел
              для уточнения, а не отрицание. Эти пункты не заменяют проверку состава.
            </p>
            <p className="parking-help">
              «Отрицается» сохраняет отрицательное утверждение. «Отклонить» исключает ошибочное
              предложение модели. Это разные действия.
            </p>
            {newStatement && (
              <Notice tone="warning">
                Завершите или отмените создание нового утверждения перед сохранением ревизии.
              </Notice>
            )}
            {incompleteStatements && (
              <Notice tone="warning">
                Заполните обстоятельство, предмет и эпизод каждого утверждения.
              </Notice>
            )}
            {incompleteHypotheses && (
              <Notice tone="warning">Выберите эпизод каждой гипотезы перед сохранением.</Notice>
            )}
            {dirty && (
              <Notice className="stale-note" tone="warning">
                Есть несохранённые изменения. Корректная правка сохранится автоматически перед
                подтверждением.
              </Notice>
            )}
            {reviewDirty && (
              <Notice className="stale-note" tone="warning">
                Решения или checklist ожидают сохранения.
              </Notice>
            )}
            {!statements.length && (
              <p>Предложите утверждения автоматически или выделите текст источника.</p>
            )}
            <div className="parking-statement-list">
              {statements.map((statement, index) => (
                <StatementEditor
                  key={statement.id}
                  statement={statement}
                  pendingSave={
                    JSON.stringify(statement) !==
                    JSON.stringify(draft.statements.find((item) => item.id === statement.id))
                  }
                  references={references}
                  index={index}
                  narrative={draft.narrative}
                  disabled={busy || historical}
                  dirty={
                    dirty ||
                    reviewDirty ||
                    metadataPendingSave ||
                    !!newStatement ||
                    saveState === 'error'
                  }
                  canReplaceQuote={!!selection && selection.end > selection.start}
                  onChange={(patch) => change(statement.id, patch)}
                  onRationaleChange={(rationale) => change(statement.id, { rationale })}
                  onReplaceQuote={() => {
                    if (selection)
                      change(statement.id, {
                        quote: draft.narrative.slice(selection.start, selection.end),
                        startOffset: selection.start,
                        endOffset: selection.end,
                      });
                  }}
                  onDecision={(decision) => {
                    if (statement.decision === decision) return;
                    decide({
                      context,
                      hypotheses,
                      statements: statements.map((item) =>
                        item.id === statement.id ? { ...item, decision } : item,
                      ),
                      checklist: { ...emptyReviewChecklist },
                    });
                  }}
                />
              ))}
            </div>
            <fieldset
              className="parking-checklist"
              disabled={
                busy ||
                historical ||
                dirty ||
                !!newStatement ||
                incompleteStatements ||
                statements.some((s) => s.decision === 'pending') ||
                metadataIssues.length > 0 ||
                metadataPendingSave
              }
            >
              <legend>Проверка полноты всего эпизода</legend>
              {Object.entries(checklistNames).map(([key, label]) => (
                <CheckField
                  key={key}
                  checked={checklist[key as keyof typeof checklist]}
                  onChange={(e) => {
                    if (inFlight.current) return;
                    setChecklist({ ...checklist, [key]: e.target.checked });
                    setReviewDirty(true);
                  }}
                >
                  {label}
                </CheckField>
              ))}
            </fieldset>
            {metadataIssues.length > 0 && (
              <Notice tone="warning">{metadataIssues.join(' ')}</Notice>
            )}
            <Actions className="parking-review-footer">
              <Button
                variant="secondary"
                disabled={
                  busy ||
                  historical ||
                  !!newStatement ||
                  incompleteStatements ||
                  incompleteHypotheses ||
                  !persistable ||
                  (!dirty && !reviewDirty && saveState !== 'error')
                }
                onClick={() => void act(() => save(false))}
              >
                {saveState === 'error' ? 'Повторить сохранение' : 'Сохранить сейчас'}
              </Button>
              <Button
                disabled={
                  busy ||
                  historical ||
                  dirty ||
                  reviewDirty ||
                  saveState === 'error' ||
                  !persistable ||
                  !statements.length ||
                  !!newStatement ||
                  incompleteStatements ||
                  statements.some((s) => s.decision === 'pending') ||
                  !Object.values(checklist).every(Boolean) ||
                  metadataIssues.length > 0 ||
                  metadataPendingSave
                }
                onClick={() => void act(() => save(true))}
              >
                Завершить проверку
              </Button>
            </Actions>
          </Panel>
          <Panel>
            <SectionHeading
              step="05"
              title="История проверки"
              description="Каждая сохранённая ревизия остаётся доступна для просмотра."
            />
            <Button
              variant="secondary"
              disabled={busy || dirty || reviewDirty || !!newStatement}
              onClick={() =>
                void act(async () => {
                  setHistory(await request<ReviewDraft[]>(`/api/parking/history/${draft.draftId}`));
                })
              }
            >
              Показать ревизии
            </Button>
            <Actions>
              {history.map((item) => (
                <Button
                  variant="secondary"
                  key={item.revisionId}
                  disabled={busy || dirty || reviewDirty || !!newStatement}
                  onClick={() => open(item)}
                >
                  Ревизия {item.revision} ·{' '}
                  {item.status === 'reviewed' ? 'проверена человеком' : 'черновик'}
                </Button>
              ))}
            </Actions>
          </Panel>
        </>
      )}
    </section>
  );
}
