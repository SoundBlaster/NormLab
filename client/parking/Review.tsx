import { useEffect, useRef, useState } from 'react';
import {
  emptyReviewChecklist,
  reviewPredicates,
  reviewStatementIssues,
  type ReviewDraft,
  type ReviewStatement,
} from '../../shared/parking-review.js';
import './review.css';

const predicateNames: Record<string, string> = {
  eventTime: 'Время события',
  inMoscow: 'Москва',
  cityParking: 'Городская парковка',
  placement: 'Размещение автомобиля',
  paidRegime: 'Платный режим',
  subjectScope: 'Участник и автомобиль',
  attribution: 'Кто сообщил',
  payment: 'Оплата',
  paymentStart: 'Начало оплаты',
  departure: 'Отъезд',
  paymentComplexity: 'Ошибки, исправления и сложность оплаты',
  permit: 'Разрешения и абонементы',
  disabilityConditions: 'Условия для инвалидов',
  specialTariff: 'Специальный тариф',
  faultAndExclusions: 'Вина и исключения',
};
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
        subject: 'episode_1',
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
      <p className="stale-note">
        Эксперимент извлечения. Утверждения требуют проверки человеком. Решение по КоАП здесь не
        рассчитывается.
      </p>
      {error && (
        <p className="message error" role="alert">
          {error}
        </p>
      )}
      <p role="status" aria-live="polite">
        {notice}
      </p>
      <section className="card">
        <h2>Фабула и черновики</h2>
        <label>
          Открыть сохранённый черновик
          <select
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
          </select>
        </label>
        <label>
          Описание события
          <textarea
            rows={6}
            value={narrative}
            disabled={busy}
            onChange={(e) => {
              setNarrative(e.target.value);
              setNewSourceApproved(false);
            }}
          />
        </label>
        {!draft && (
          <label>
            Учебный пример
            <select
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
            </select>
          </label>
        )}
        {draft && (
          <label className="parking-check">
            <input
              type="checkbox"
              checked={newSourceApproved}
              disabled={busy}
              onChange={(e) => setNewSourceApproved(e.target.checked)}
            />
            Создать новый черновик: сохранить прежний разбор и начать с пустыми подтверждениями.
          </label>
        )}
        <button
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
        </button>
      </section>
      {draft && (
        <>
          <section className="card">
            <h2>Источник · ревизия {draft.revision}</h2>
            <p>
              {draft.status === 'reviewed' && !dirty && !reviewDirty
                ? 'Проверено человеком'
                : 'Проверка не завершена'}
              {historical ? ' · историческая ревизия, только чтение' : ''}
            </p>
            {historical && (
              <button
                className="secondary"
                onClick={() => {
                  const latest = data?.drafts.find((d) => d.draftId === draft.draftId);
                  if (latest) open(latest);
                }}
              >
                Открыть актуальную ревизию
              </button>
            )}
            {narrative !== draft.narrative && (
              <p className="stale-note">
                Вы изменили фабулу выше. Для её разбора создайте новый черновик. Ниже показан
                сохранённый источник.
              </p>
            )}
            <label>
              Выделите фрагмент для нового утверждения
              <textarea
                ref={sourceRef}
                readOnly
                rows={6}
                value={draft.narrative}
                onSelect={() => {
                  const input = sourceRef.current;
                  if (input) setSelection({ start: input.selectionStart, end: input.selectionEnd });
                }}
              />
            </label>
            <div className="parking-actions">
              <button
                className="secondary"
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
              </button>
              <button
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
              </button>
              <button
                className="secondary"
                disabled={dirty || reviewDirty || busy}
                onClick={exportDraft}
              >
                Скачать сохранённую ревизию
              </button>
            </div>
            {!data?.extractorAvailable && (
              <p>
                Для автоматического извлечения требуется локальное evaluation environment. Ручная
                разметка доступна.
              </p>
            )}
            {draft.originalExtraction !== null && (
              <details>
                <summary>Исходное предложение модели</summary>
                <pre>{JSON.stringify(draft.originalExtraction, null, 2)}</pre>
              </details>
            )}
          </section>
          <section className="card">
            <h2>Утверждения · {statements.length}</h2>
            <p>
              Проверьте полноту: время и место, автомобиль и участник, размещение, платный режим,
              оплата и её время, отъезд, ошибки оплаты и разрешения. Если сведений нет, это пробел
              для уточнения, а не отрицание. Эти пункты не заменяют проверку состава.
            </p>
            <p>
              «Отрицается» сохраняет отрицательное утверждение. «Отклонить» исключает ошибочное
              предложение модели. Это разные действия.
            </p>
            {dirty && (
              <p className="stale-note">
                Есть несохранённые изменения. Сохраните ревизию перед подтверждением.
              </p>
            )}
            {reviewDirty && (
              <p className="stale-note">Подтверждения и checklist ещё не сохранены.</p>
            )}
            {!statements.length && (
              <p>Предложите утверждения автоматически или выделите текст источника.</p>
            )}
            {statements.map((statement, index) => (
              <fieldset
                className="parking-statement"
                key={statement.id}
                disabled={busy || historical}
              >
                <legend>
                  Утверждение {index + 1} · {statement.origin === 'model' ? 'модель' : 'человек'} ·{' '}
                  {
                    { pending: 'не проверено', confirmed: 'подтверждено', rejected: 'отклонено' }[
                      statement.decision
                    ]
                  }
                </legend>
                <blockquote>{statement.quote}</blockquote>
                <div className="parking-fields">
                  <label>
                    Обстоятельство
                    <select
                      value={statement.predicate}
                      onChange={(e) => change(statement.id, { predicate: e.target.value })}
                    >
                      {reviewPredicates.map((p) => (
                        <option key={p} value={p}>
                          {predicateNames[p.split(':')[1]] ?? p}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Состояние утверждения
                    <select
                      value={statement.stance}
                      onChange={(e) =>
                        change(statement.id, {
                          stance: e.target.value as ReviewStatement['stance'],
                        })
                      }
                    >
                      <option value="asserted">Утверждается</option>
                      <option value="denied">Отрицается</option>
                      <option value="unknown">Неизвестно</option>
                    </select>
                  </label>
                  <label>
                    К кому или чему относится
                    <input
                      value={statement.subject}
                      onChange={(e) => change(statement.id, { subject: e.target.value })}
                    />
                  </label>
                  <label>
                    Эпизод
                    <input
                      value={statement.aboutEpisode}
                      onChange={(e) => change(statement.id, { aboutEpisode: e.target.value })}
                    />
                  </label>
                </div>
                <label>
                  Содержание
                  <textarea
                    rows={2}
                    value={statement.valueText}
                    onChange={(e) => change(statement.id, { valueText: e.target.value })}
                  />
                </label>
                <label>
                  Основание проверки или причина отклонения
                  <textarea
                    rows={2}
                    value={statement.rationale}
                    onChange={(e) => {
                      setStatements((items) =>
                        items.map((s) =>
                          s.id === statement.id ? { ...s, rationale: e.target.value } : s,
                        ),
                      );
                      setDirty(true);
                    }}
                  />
                </label>
                <div className="parking-actions">
                  <button
                    className="secondary"
                    disabled={!selection || selection.end <= selection.start}
                    onClick={() => {
                      if (selection)
                        change(statement.id, {
                          quote: draft.narrative.slice(selection.start, selection.end),
                          startOffset: selection.start,
                          endOffset: selection.end,
                        });
                    }}
                  >
                    Заменить цитату выделенным текстом
                  </button>
                  <button
                    className="secondary"
                    disabled={dirty || reviewStatementIssues(statement, draft.narrative).length > 0}
                    onClick={() => {
                      setStatements((items) =>
                        items.map((s) =>
                          s.id === statement.id ? { ...s, decision: 'confirmed' } : s,
                        ),
                      );
                      setChecklist({ ...emptyReviewChecklist });
                      setReviewDirty(true);
                    }}
                  >
                    Подтвердить
                  </button>
                  <button
                    className="secondary"
                    disabled={!statement.rationale.trim() || dirty}
                    onClick={() => {
                      setStatements((items) =>
                        items.map((s) =>
                          s.id === statement.id ? { ...s, decision: 'rejected' } : s,
                        ),
                      );
                      setChecklist({ ...emptyReviewChecklist });
                      setReviewDirty(true);
                    }}
                  >
                    Отклонить с причиной
                  </button>
                </div>
              </fieldset>
            ))}
            <fieldset
              disabled={
                busy || historical || dirty || statements.some((s) => s.decision === 'pending')
              }
            >
              <legend>Проверка полноты всего эпизода</legend>
              {Object.entries(checklistNames).map(([key, label]) => (
                <label className="parking-check" key={key}>
                  <input
                    type="checkbox"
                    checked={checklist[key as keyof typeof checklist]}
                    onChange={(e) => {
                      setChecklist({ ...checklist, [key]: e.target.checked });
                      setReviewDirty(true);
                    }}
                  />
                  {label}
                </label>
              ))}
            </fieldset>
            <div className="parking-actions">
              <button
                className="secondary"
                disabled={busy || historical}
                onClick={() => void act(() => save(false))}
              >
                Сохранить ревизию
              </button>
              <button
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
              </button>
            </div>
          </section>
          <section className="card">
            <h2>История проверки</h2>
            <button
              className="secondary"
              disabled={busy || dirty || reviewDirty}
              onClick={() =>
                void act(async () => {
                  setHistory(await request<ReviewDraft[]>(`/api/parking/history/${draft.draftId}`));
                })
              }
            >
              Показать ревизии
            </button>
            <div className="parking-actions">
              {history.map((item) => (
                <button className="secondary" key={item.revisionId} onClick={() => open(item)}>
                  Ревизия {item.revision} ·{' '}
                  {item.status === 'reviewed' ? 'проверена человеком' : 'черновик'}
                </button>
              ))}
            </div>
          </section>
        </>
      )}
    </section>
  );
}
