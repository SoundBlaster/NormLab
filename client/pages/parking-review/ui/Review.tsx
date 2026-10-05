import { useEffect, useRef, useState } from 'react';
import {
  emptyReviewChecklist,
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
import { StatementEditor } from './StatementEditor.js';
import './review.css';

const checklistNames = {
  negatives: 'Все явные отрицания сохранены.',
  conflicts: 'Противоречащие утверждения сохранены отдельно.',
  attribution: 'Участники, автомобили и эпизод различены правильно.',
  sourceSupport: 'Каждое утверждение поддержано своей цитатой; выдуманных фактов нет.',
  unknowns: 'Пробелы отмечены; отсутствие сведений не превращено в отрицание.',
};
type Bootstrap = {
  drafts: ReviewDraft[];
  extractorAvailable: boolean;
  cases: { id: string; narrative: string }[];
};
export function ParkingReview({ token }: { token: string }) {
  const [data, setData] = useState<Bootstrap>();
  const [draft, setDraft] = useState<ReviewDraft>();
  const [history, setHistory] = useState<ReviewDraft[]>([]);
  const [narrative, setNarrative] = useState('');
  const [selection, setSelection] = useState<{ start: number; end: number }>();
  const [statements, setStatements] = useState<ReviewStatement[]>([]);
  const [checklist, setChecklist] = useState({ ...emptyReviewChecklist });
  const [busy, setBusy] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [reviewDirty, setReviewDirty] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [newSourceApproved, setNewSourceApproved] = useState(false);
  const sourceRef = useRef<HTMLTextAreaElement>(null);
  async function request<T>(path: string, body?: unknown): Promise<T> {
    const response = await fetch(
      path,
      body === undefined
        ? {}
        : {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-NormLab-Token': token },
            body: JSON.stringify(body),
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
    setChecklist(item.checklist);
    setNarrative(item.narrative);
    setSelection(undefined);
    setDirty(false);
    setReviewDirty(false);
    setNewSourceApproved(false);
    setHistory([]);
    setError('');
    setNotice('');
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
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await action();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }
  function change(id: string, patch: Partial<ReviewStatement>) {
    setStatements((items) =>
      items.map((s) =>
        s.id === id ? { ...s, ...patch, origin: 'human', decision: 'pending' } : s,
      ),
    );
    setChecklist({ ...emptyReviewChecklist });
    setDirty(true);
  }
  async function save(finishReview: boolean) {
    if (!draft) return;
    const result = await request<ReviewDraft>('/api/parking/review', {
      draftId: draft.draftId,
      expectedRevisionId: draft.revisionId,
      statements,
      checklist,
      finishReview,
    });
    await load();
    open(result);
    setNotice(
      finishReview
        ? 'Проверка человеком сохранена. Правовой расчёт ещё не выполнен.'
        : 'Ревизия сохранена. Изменённые утверждения теперь можно подтвердить.',
    );
  }
  function addSelection() {
    if (!draft || !selection || selection.end <= selection.start) return;
    const quote = draft.narrative.slice(selection.start, selection.end);
    setStatements((items) => [
      ...items,
      {
        id: crypto.randomUUID(),
        predicate: 'nlinput:payment',
        stance: 'asserted',
        subject: 'vehicle_1',
        aboutEpisode: 'episode_1',
        valueText: quote,
        quote,
        startOffset: selection.start,
        endOffset: selection.end,
        origin: 'human',
        decision: 'pending',
        rationale: '',
      },
    ]);
    setChecklist({ ...emptyReviewChecklist });
    setDirty(true);
    setNotice('Утверждение добавлено из выделенного текста. Выберите его смысл и сохраните.');
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
      <Panel>
        <SectionHeading
          step="01"
          title="Описание события"
          description="Начните с фабулы или вернитесь к сохранённому разбору."
        />
        <Field label="Открыть сохранённый черновик">
          <Select
            value={draft?.draftId ?? ''}
            disabled={busy || dirty || reviewDirty}
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
            busy || dirty || reviewDirty || !narrative.trim() || (!!draft && !newSourceApproved)
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
              title={`Источник · ревизия ${draft.revision}`}
              description="Получите предложения модели или выделите цитату и добавьте утверждение вручную."
            />
            <Status
              className="parking-review-state"
              tone={draft.status === 'reviewed' && !dirty && !reviewDirty ? 'success' : 'warning'}
            >
              {draft.status === 'reviewed' && !dirty && !reviewDirty
                ? 'Проверено человеком'
                : 'Проверка не завершена'}
              {historical ? ' · историческая ревизия, только чтение' : ''}
            </Status>
            {historical && (
              <Button
                variant="secondary"
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
                  statements.length >= 256
                }
                onClick={addSelection}
              >
                Добавить выделенное утверждение
              </Button>
              <Button
                disabled={
                  busy ||
                  dirty ||
                  reviewDirty ||
                  historical ||
                  narrative !== draft.narrative ||
                  !data?.extractorAvailable
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
            {!data?.extractorAvailable && (
              <p>
                Для автоматического извлечения требуется локальное evaluation environment. Ручная
                разметка доступна.
              </p>
            )}
            {draft.originalExtraction !== null && (
              <Disclosure summary="Исходное предложение модели">
                <pre>{JSON.stringify(draft.originalExtraction, null, 2)}</pre>
              </Disclosure>
            )}
          </Panel>
          <Panel>
            <SectionHeading
              step="03"
              title={`Проверка утверждений · ${statements.length}`}
              description="Сопоставьте каждое утверждение с цитатой. Исправьте смысл, затем сохраните и подтвердите."
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
            {dirty && (
              <Notice className="stale-note" tone="warning">
                Есть несохранённые изменения. Сохраните ревизию перед подтверждением.
              </Notice>
            )}
            {reviewDirty && (
              <Notice className="stale-note" tone="warning">
                Подтверждения и checklist ещё не сохранены.
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
                  index={index}
                  narrative={draft.narrative}
                  disabled={busy || historical}
                  dirty={dirty}
                  canReplaceQuote={!!selection && selection.end > selection.start}
                  onChange={(patch) => change(statement.id, patch)}
                  onRationaleChange={(rationale) => {
                    setStatements((items) =>
                      items.map((s) => (s.id === statement.id ? { ...s, rationale } : s)),
                    );
                    setDirty(true);
                  }}
                  onReplaceQuote={() => {
                    if (selection)
                      change(statement.id, {
                        quote: draft.narrative.slice(selection.start, selection.end),
                        startOffset: selection.start,
                        endOffset: selection.end,
                      });
                  }}
                  onDecision={(decision) => {
                    setStatements((items) =>
                      items.map((s) => (s.id === statement.id ? { ...s, decision } : s)),
                    );
                    setChecklist({ ...emptyReviewChecklist });
                    setReviewDirty(true);
                  }}
                />
              ))}
            </div>
            <fieldset
              className="parking-checklist"
              disabled={
                busy || historical || dirty || statements.some((s) => s.decision === 'pending')
              }
            >
              <legend>Проверка полноты всего эпизода</legend>
              {Object.entries(checklistNames).map(([key, label]) => (
                <CheckField
                  key={key}
                  checked={checklist[key as keyof typeof checklist]}
                  onChange={(e) => {
                    setChecklist({ ...checklist, [key]: e.target.checked });
                    setReviewDirty(true);
                  }}
                >
                  {label}
                </CheckField>
              ))}
            </fieldset>
            <Actions className="parking-review-footer">
              <Button
                variant="secondary"
                disabled={busy || historical}
                onClick={() => void act(() => save(false))}
              >
                Сохранить ревизию
              </Button>
              <Button
                disabled={
                  busy ||
                  historical ||
                  dirty ||
                  !statements.length ||
                  statements.some((s) => s.decision === 'pending') ||
                  !Object.values(checklist).every(Boolean)
                }
                onClick={() => void act(() => save(true))}
              >
                Завершить проверку
              </Button>
            </Actions>
          </Panel>
          <Panel>
            <SectionHeading
              step="04"
              title="История проверки"
              description="Каждая сохранённая ревизия остаётся доступна для просмотра."
            />
            <Button
              variant="secondary"
              disabled={busy || dirty || reviewDirty}
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
                <Button variant="secondary" key={item.revisionId} onClick={() => open(item)}>
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
