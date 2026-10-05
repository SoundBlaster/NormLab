import { useEffect, useState, type ReactNode } from 'react';
import { isCurrentAnalysis } from '../shared/current.js';
import { Lab } from './lab/Lab.js';
import { ParkingReview } from './parking/Review.js';
import type {
  Analysis,
  Bootstrap,
  Bundle,
  FindingState,
  Snapshot,
  SnapshotInput,
  Workspace,
} from '../shared/domain.js';

const states: { id: FindingState; name: string; detail: string; mark: string }[] = [
  { id: 'established', name: 'Установлено', detail: 'Есть основание принять A', mark: '✓' },
  { id: 'refuted', name: 'Опровергнуто', detail: 'Есть основание отвергнуть A', mark: '×' },
  { id: 'unreviewed', name: 'Не рассмотрено', detail: 'Вопрос остаётся открытым', mark: '?' },
  { id: 'not-established', name: 'Не установлено', detail: 'Данных недостаточно', mark: '−' },
];
const stateName = (id: FindingState) => states.find((state) => state.id === id)!.name;
const number = (value: number) => new Intl.NumberFormat('ru-RU').format(value);
const time = (value: string) =>
  new Date(value).toLocaleString('ru-RU', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  });
const initial: SnapshotInput = { narrative: '', finding: 'unreviewed', rationale: '' };
type Tab = 'lab' | 'parking' | 'workspace' | 'bundles' | 'comparison' | 'history';
const tabs: { id: Tab; label: string; symbol: string }[] = [
  { id: 'lab', label: 'Реформа A/B/C', symbol: '⇄' },
  { id: 'parking', label: 'Парковка · Разбор текста', symbol: '◫' },
  { id: 'workspace', label: 'M0 · Решение', symbol: '◫' },
  { id: 'bundles', label: 'M0 · Пакеты норм', symbol: '▤' },
  { id: 'comparison', label: 'M0 · Сравнение', symbol: '⇄' },
  { id: 'history', label: 'M0 · История', symbol: '◷' },
];

async function request<T>(path: string, token?: string, body?: unknown): Promise<T> {
  const response = await fetch(
    path,
    body === undefined
      ? {}
      : {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-NormLab-Token': token ?? '' },
          body: JSON.stringify(body),
        },
  );
  const result = await response.json();
  if (!response.ok) throw new Error(result.error ?? 'Не удалось связаться с сервером.');
  return result as T;
}
function Chip({ children, tone = '' }: { children: ReactNode; tone?: string }) {
  return <span className={`chip ${tone}`}>{children}</span>;
}
function Hash({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="hash">
      <span>{label}</span>
      <code title={value ?? undefined}>{value ?? 'Не выполнено'}</code>
    </div>
  );
}

export function App() {
  const [data, setData] = useState<Bootstrap | null>(null);
  const [tab, setTab] = useState<Tab>('lab');
  const [selectedId, setSelectedId] = useState('');
  const [bundleId, setBundleId] = useState<Bundle['id']>('reduction-v1');
  const [form, setForm] = useState<SnapshotInput>(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  useEffect(() => {
    let active = true;
    request<Bootstrap>('/api/bootstrap')
      .then((result) => {
        if (!active) return;
        setData(result);
        setSelectedId(result.workspace.snapshots[0].id);
        const snapshot = result.workspace.snapshots[0];
        setForm({
          narrative: snapshot.narrative,
          finding: snapshot.finding,
          rationale: snapshot.rationale,
        });
      })
      .catch((e) => {
        if (active) setError(e instanceof Error ? e.message : 'Ошибка загрузки');
      });
    return () => {
      active = false;
    };
  }, []);

  const selected = data?.workspace.snapshots.find((snapshot) => snapshot.id === selectedId);
  const latest = data?.workspace.snapshots[0];
  const bundle = data?.bundles.find((item) => item.id === bundleId);
  const analysis = data?.workspace.analyses.find(
    (item) => item.snapshotId === selectedId && item.bundleId === bundleId,
  );
  const historical = selected && latest && selected.id !== latest.id;
  const dirty =
    !!selected &&
    (form.narrative.trim() !== selected.narrative ||
      form.finding !== selected.finding ||
      form.rationale.trim() !== selected.rationale);

  function selectSnapshot(snapshot: Snapshot) {
    setSelectedId(snapshot.id);
    setForm({
      narrative: snapshot.narrative,
      finding: snapshot.finding,
      rationale: snapshot.rationale,
    });
    setNotice('');
    setError('');
    setTab('workspace');
  }
  async function run(analyze: boolean) {
    if (!data || !selected) return;
    setBusy(true);
    setError('');
    setNotice('');
    try {
      let snapshot = selected;
      let workspace = data.workspace;
      if (dirty) {
        const saved = await request<{ snapshot: Snapshot; workspace: Workspace }>(
          '/api/snapshots',
          data.csrfToken,
          { input: form, expectedSnapshotId: selected.id },
        );
        snapshot = saved.snapshot;
        workspace = saved.workspace;
        setSelectedId(snapshot.id);
        setForm({
          narrative: snapshot.narrative,
          finding: snapshot.finding,
          rationale: snapshot.rationale,
        });
        setData({ ...data, workspace });
      }
      if (analyze) {
        const result = await request<Analysis>('/api/analyze', data.csrfToken, {
          snapshotId: snapshot.id,
          bundleId,
        });
        const fresh = await request<Bootstrap>('/api/bootstrap');
        setData(fresh);
        setNotice(
          result.receipt.payload.verification.status === 'verified'
            ? `Снимок ${snapshot.revision} проверен. Квитанция сохранена.`
            : result.receipt.payload.verification.reason,
        );
      } else setNotice(`Снимок ${snapshot.revision} сохранён. Теперь можно проверить решение.`);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Не удалось выполнить действие.');
    } finally {
      setBusy(false);
    }
  }
  async function checkSignature() {
    if (!analysis || !data) return;
    setBusy(true);
    setError('');
    try {
      const result = await request<{ valid: boolean }>(
        `/api/analyses/${analysis.id}/signature`,
        data.csrfToken,
        {},
      );
      setNotice(
        result.valid
          ? 'Подпись Ed25519 действительна. Содержимое квитанции не изменено.'
          : 'Подпись квитанции недействительна.',
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Ошибка проверки подписи.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="/" aria-label="NormLab — главная">
          <span className="brand-mark">
            N<span>·</span>
          </span>
          <span>
            NormLab<small>ЛАБОРАТОРИЯ НОРМ</small>
          </span>
        </a>
        <div className="sidebar-label">ИССЛЕДОВАНИЕ</div>
        <nav aria-label="Основная навигация">
          {tabs
            .filter((item) => item.id === 'lab' || item.id === 'parking')
            .map((item) => (
              <button
                key={item.id}
                type="button"
                className={tab === item.id ? 'nav-item active' : 'nav-item'}
                aria-current={tab === item.id ? 'page' : undefined}
                onClick={() => setTab(item.id)}
              >
                <span aria-hidden="true">{item.symbol}</span>
                {item.label}
                {item.id === 'workspace' && <i />}
              </button>
            ))}
          <details className="legacy-nav" open={tab !== 'lab'}>
            <summary>Пример M0</summary>
            <div>
              {tabs
                .filter((item) => item.id !== 'lab' && item.id !== 'parking')
                .map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    className={tab === item.id ? 'nav-item active' : 'nav-item'}
                    aria-current={tab === item.id ? 'page' : undefined}
                    onClick={() => setTab(item.id)}
                  >
                    <span aria-hidden="true">{item.symbol}</span>
                    {item.label}
                  </button>
                ))}
            </div>
          </details>
        </nav>
        <div className="sidebar-note">
          <span className="mini-orbit" aria-hidden="true">
            ◎
          </span>
          <strong>Проверяемая модель</strong>
          <p>Каждый вывод связан с конкретными входами и редакцией норм.</p>
          <span className="sidebar-version">
            LOCAL LAB <span>v0.1.0</span>
          </span>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div>
            <span className="breadcrumb">Лаборатория</span>
            <span className="slash">/</span>
            {tabs.find((item) => item.id === tab)!.label}
          </div>
          <Chip tone="amber">
            <span className="dot" />
            Синтетические данные
          </Chip>
        </header>
        <main id="main">
          {!data || !selected || !bundle ? (
            <section className="loading card" role="status">
              <span className="eyebrow">NORMLAB</span>
              <h1>{error ? 'Не удалось открыть лабораторию' : 'Загружаем рабочую область…'}</h1>
              {error && (
                <>
                  <p role="alert">{error}</p>
                  <button onClick={() => location.reload()}>Повторить</button>
                </>
              )}
            </section>
          ) : (
            <>
              <div className={`page-heading ${tab === 'lab' ? 'lab-page-heading' : ''}`}>
                <div>
                  <span className="eyebrow">
                    {tab === 'parking'
                      ? 'ЭКСПЕРИМЕНТ 003 / ПАРКОВОЧНЫЙ ПИЛОТ'
                      : tab === 'lab'
                        ? 'ЭКСПЕРИМЕНТ 002 / ОБЩИЕ ПРАВИЛА СМЯГЧЕНИЯ'
                        : tab === 'workspace'
                          ? 'ЭКСПЕРИМЕНТ 001 / УСЛОВНОЕ ПРЕОБРАЗОВАНИЕ'
                          : 'ИССЛЕДОВАТЕЛЬСКАЯ ЛАБОРАТОРИЯ'}
                  </span>
                  <h1>
                    {tab === 'parking'
                      ? 'Извлечь. Проверить. Исправить.'
                      : tab === 'lab'
                        ? 'Сравнивать правила. Проверять изменения.'
                        : tab === 'workspace'
                          ? 'От обстоятельств к выводу.'
                          : tab === 'bundles'
                            ? 'Нормы с явной семантикой.'
                            : tab === 'comparison'
                              ? 'Что меняет новая редакция?'
                              : 'Каждое изменение сохраняется.'}
                  </h1>
                  <p>
                    {tab === 'parking'
                      ? 'Фабула, цитаты и утверждения. Каждый шаг сохраняется.'
                      : tab === 'lab'
                        ? 'Один snapshot. Три модели. Явные последствия и границы проверки.'
                        : tab === 'workspace'
                          ? 'Установите условие, примените норму и проверьте результат.'
                          : tab === 'bundles'
                            ? 'Декларативные правила, точные версии и прослеживаемое происхождение.'
                            : tab === 'comparison'
                              ? 'Один домен случаев. Две модели. Наблюдаемые различия.'
                              : 'Выберите снимок, чтобы открыть его входы, результат и квитанцию.'}
                  </p>
                </div>
                <div className="hero-symbol" aria-hidden="true">
                  {tab === 'comparison' ? '⇄' : '∴'}
                </div>
              </div>
              {error && (
                <div className="message error" role="alert">
                  {error}
                </div>
              )}
              <div role="status" aria-live="polite">
                {notice && <div className="message">{notice}</div>}
              </div>
              <div hidden={tab !== 'lab'}>
                <Lab />
              </div>
              <div hidden={tab !== 'parking'}>
                <ParkingReview token={data.csrfToken} />
              </div>
              {tab === 'workspace' && (
                <>
                  <div className="context-strip">
                    <div>
                      <span className="tiny-label">СЦЕНАРИЙ</span>
                      <strong>
                        Условие A <span className="muted">/ учебная модель</span>
                      </strong>
                    </div>
                    <div>
                      <span className="tiny-label">РЕДАКЦИЯ НОРМ</span>
                      <select
                        aria-label="Редакция норм"
                        value={bundleId}
                        disabled={busy}
                        onChange={(e) => {
                          setBundleId(e.target.value as Bundle['id']);
                          setNotice('');
                        }}
                      >
                        {data.bundles.map((item) => (
                          <option key={item.id} value={item.id}>
                            {item.version} · {item.title}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="context-status">
                      <span className={`status-light ${data.verifier.available ? '' : 'off'}`} />
                      <span>
                        {data.verifier.available ? 'Lean готов к проверке' : 'Lean недоступен'}
                      </span>
                    </div>
                  </div>
                  {historical && (
                    <div className="message historical">
                      Открыт исторический снимок {selected.revision}. Его квитанция относится только
                      к сохранённым здесь входам.
                      <button onClick={() => selectSnapshot(latest!)}>К текущему снимку →</button>
                    </div>
                  )}
                  <div className="work-grid">
                    <section className="card input-card" aria-labelledby="input-title">
                      <div className="card-heading">
                        <div>
                          <span className="step">01</span>
                          <h2 id="input-title">Обстоятельства и установления</h2>
                        </div>
                        <Chip>{dirty ? 'Черновик' : `Снимок ${selected.revision}`}</Chip>
                      </div>
                      <fieldset disabled={busy || !!historical}>
                        <label className="field-label" htmlFor="narrative">
                          Описание сценария
                        </label>
                        <textarea
                          id="narrative"
                          value={form.narrative}
                          maxLength={6000}
                          rows={5}
                          onChange={(e) => setForm({ ...form, narrative: e.target.value })}
                        />
                        <p className="field-help">
                          Текст служит контекстом. Условие A фиксируется отдельно человеком.
                        </p>
                        <div className="question-heading">
                          <h3>Установлено ли условие A?</h3>
                          <span className="tiny-label">SIMULATED REVIEWER</span>
                        </div>
                        <div
                          className="state-grid"
                          role="radiogroup"
                          aria-label="Состояние условия A"
                        >
                          {states.map((state) => (
                            <label
                              key={state.id}
                              className={`state-option ${form.finding === state.id ? 'selected' : ''}`}
                            >
                              <input
                                type="radio"
                                name="finding"
                                value={state.id}
                                checked={form.finding === state.id}
                                onChange={() => setForm({ ...form, finding: state.id })}
                              />
                              <span className="state-icon" aria-hidden="true">
                                {state.mark}
                              </span>
                              <span>
                                <strong>{state.name}</strong>
                                <small>{state.detail}</small>
                              </span>
                            </label>
                          ))}
                        </div>
                        <label className="field-label" htmlFor="rationale">
                          Основание установления{' '}
                          <span className="muted">
                            {form.finding === 'unreviewed' ? '· необязательно' : '· обязательно'}
                          </span>
                        </label>
                        <textarea
                          id="rationale"
                          rows={2}
                          maxLength={2000}
                          placeholder="На каком основании выбран этот статус?"
                          value={form.rationale}
                          onChange={(e) => setForm({ ...form, rationale: e.target.value })}
                        />
                      </fieldset>
                      <div className="form-actions">
                        <button
                          className="primary"
                          disabled={
                            busy ||
                            !form.narrative.trim() ||
                            (form.finding !== 'unreviewed' && form.rationale.trim().length < 3)
                          }
                          onClick={() => run(true)}
                        >
                          {busy ? (
                            <>
                              <span className="spinner" />
                              Выполняется проверка…
                            </>
                          ) : (
                            <>
                              {dirty ? 'Зафиксировать и проверить' : 'Проверить решение'}
                              <span aria-hidden="true">↗</span>
                            </>
                          )}
                        </button>
                        <button
                          className="text-button"
                          disabled={
                            busy ||
                            !dirty ||
                            !!historical ||
                            !form.narrative.trim() ||
                            (form.finding !== 'unreviewed' && form.rationale.trim().length < 3)
                          }
                          onClick={() => run(false)}
                        >
                          Сохранить снимок
                        </button>
                      </div>
                      <p className="privacy-note">
                        Только синтетические сценарии. Ввод и проверка выполняются локально.
                      </p>
                    </section>
                    <div className="result-column">
                      <Result
                        current={
                          !!analysis &&
                          isCurrentAnalysis(
                            analysis,
                            selected,
                            bundle,
                            data.verifier.toolchainDigest,
                          )
                        }
                        analysis={analysis}
                        dirty={dirty}
                        busy={busy}
                        onSignature={checkSignature}
                      />
                      <section className="rule-card">
                        <span className="eyebrow">ПРИМЕНЯЕМАЯ НОРМА · {bundle.version}</span>
                        <h3>
                          Если A установлено → срок × {bundle.ir.adjustment.numerator}/
                          {bundle.ir.adjustment.denominator}
                        </h3>
                        <p>
                          Базовый срок — 120 месяцев. Штраф — 200 000 DEMO. Поправка обязательна и
                          применяется ровно один раз.
                        </p>
                        <button className="text-button" onClick={() => setTab('bundles')}>
                          Открыть пакет норм <span aria-hidden="true">→</span>
                        </button>
                      </section>
                    </div>
                  </div>
                  <section className="trace-strip" aria-label="Этапы исследования">
                    <div>
                      <span>01</span>
                      <strong>Установления</strong>
                      <small>Мотивированный ввод</small>
                    </div>
                    <b aria-hidden="true">→</b>
                    <div>
                      <span>02</span>
                      <strong>Применение норм</strong>
                      <small>Точная арифметика</small>
                    </div>
                    <b aria-hidden="true">→</b>
                    <div>
                      <span>03</span>
                      <strong>Проверка в Lean</strong>
                      <small>Независимое утверждение</small>
                    </div>
                    <b aria-hidden="true">→</b>
                    <div>
                      <span>04</span>
                      <strong>Квитанция</strong>
                      <small>Входы, scope и подпись</small>
                    </div>
                  </section>
                </>
              )}
              {tab === 'bundles' && (
                <div className="bundle-grid">
                  {data.bundles.map((item) => (
                    <section className="card package-card" key={item.id}>
                      <div className="card-heading">
                        <Chip tone={item.id === 'reduction-v1' ? 'green' : 'amber'}>
                          {item.id === 'reduction-v1' ? 'Исходная модель' : 'Эксперимент'}
                        </Chip>
                        <span className="mono">v{item.version}</span>
                      </div>
                      <h2>{item.title}</h2>
                      <p>{item.description}</p>
                      <div className="formula">
                        120{' '}
                        <span>
                          × {item.ir.adjustment.numerator}/{item.ir.adjustment.denominator} =
                        </span>{' '}
                        {(120 * item.ir.adjustment.numerator) / item.ir.adjustment.denominator}
                        <small>месяцев при установленном A</small>
                      </div>
                      <blockquote>{item.source}</blockquote>
                      <dl className="properties">
                        <div>
                          <dt>Область</dt>
                          <dd>Одно синтетическое преобразование</dd>
                        </div>
                        <div>
                          <dt>Открытый вопрос</dt>
                          <dd>Обе условные ветви сохраняются</dd>
                        </div>
                        <div>
                          <dt>Округление</dt>
                          <dd>Только целое число месяцев</dd>
                        </div>
                        <div>
                          <dt>Штраф</dt>
                          <dd>200 000 DEMO · без изменения</dd>
                        </div>
                      </dl>
                      <details>
                        <summary>Идентичность и Legal IR</summary>
                        <Hash label="Semantic digest" value={item.semanticDigest} />
                        <Hash label="Provenance digest" value={item.provenanceDigest} />
                        <pre>{JSON.stringify(item.ir, null, 2)}</pre>
                      </details>
                      <button
                        className="secondary"
                        onClick={() => {
                          setBundleId(item.id);
                          setTab('workspace');
                          setNotice('');
                        }}
                      >
                        Исследовать эту редакцию →
                      </button>
                    </section>
                  ))}
                </div>
              )}
              {tab === 'comparison' && (
                <>
                  <div className="comparison-banner">
                    <div>
                      <span className="eyebrow">ПОЛНЫЙ ПЕРЕБОР ЗАВЕРШЁННЫХ СОСТОЯНИЙ</span>
                      <h2>Редакции дают разные последствия</h2>
                      <p>
                        При установленном A экспериментальная редакция уменьшает срок ещё на 20
                        месяцев.
                      </p>
                    </div>
                    <div className="comparison-delta">
                      −20<small>месяцев при A</small>
                    </div>
                  </div>
                  <section className="card comparison-card">
                    <div className="card-heading">
                      <h2>Общий домен: 2 состояния</h2>
                      <Chip>Вычислено интерпретатором</Chip>
                    </div>
                    <div className="table-scroll">
                      <table>
                        <thead>
                          <tr>
                            <th>Условие A</th>
                            <th>Исходная · 0.1.0</th>
                            <th>Эксперимент · 0.2.0</th>
                            <th>Разница срока</th>
                          </tr>
                        </thead>
                        <tbody>
                          {data.comparison.rows.map((row) => (
                            <tr key={row.finding}>
                              <td>
                                <strong>{stateName(row.finding)}</strong>
                              </td>
                              <td>
                                {row.baseline.prisonMonths} месяцев
                                <small>+ {number(row.baseline.fineAmount)} DEMO</small>
                              </td>
                              <td>
                                {row.candidate.prisonMonths} месяцев
                                <small>+ {number(row.candidate.fineAmount)} DEMO</small>
                              </td>
                              <td>
                                <Chip tone={row.prisonDelta ? 'green' : ''}>
                                  {row.prisonDelta || 'Без изменений'}
                                  {row.prisonDelta ? ' месяцев' : ''}
                                </Chip>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    <p className="scope-note">
                      Домен состоит из established и refuted. Сравнение охватывает оба состояния
                      этого synthetic profile. Формальная квитанция сравнения в MVP не выпускается;
                      отдельные решения можно проверить в рабочей области.
                    </p>
                  </section>
                  <div className="comparison-notes">
                    <section>
                      <span className="step">01</span>
                      <h3>Что изменилось</h3>
                      <p>
                        Единственное изменение — множитель срока: 2/3 → 1/2. Базовое решение и штраф
                        совпадают.
                      </p>
                    </section>
                    <section>
                      <span className="step">02</span>
                      <h3>Что означает различие</h3>
                      <p>
                        Найден конкретный свидетель неэквивалентности: установленное A. Оценка
                        качества реального законодательства здесь не производится.
                      </p>
                    </section>
                  </div>
                </>
              )}
              {tab === 'history' && (
                <section className="card history-card">
                  <div className="card-heading">
                    <h2>Неизменяемая история</h2>
                    <Chip>{data.workspace.snapshots.length} снимков</Chip>
                  </div>
                  {data.workspace.snapshots.map((snapshot) => (
                    <button
                      key={snapshot.id}
                      className="history-row"
                      disabled={busy}
                      onClick={() => selectSnapshot(snapshot)}
                      aria-label={`Открыть снимок ${snapshot.revision}`}
                    >
                      <span className="revision-number">
                        {String(snapshot.revision).padStart(2, '0')}
                      </span>
                      <span className="history-content">
                        <strong>
                          {stateName(snapshot.finding)}{' '}
                          {snapshot.id === latest?.id && <Chip tone="green">Текущий</Chip>}
                        </strong>
                        <small>{snapshot.rationale || 'Условие ещё не рассмотрено'}</small>
                      </span>
                      <span className="history-date">
                        {time(snapshot.createdAt)}
                        <small>
                          {
                            data.workspace.analyses.filter(
                              (item) => item.snapshotId === snapshot.id,
                            ).length
                          }{' '}
                          результатов
                        </small>
                      </span>
                      <span aria-hidden="true">↗</span>
                    </button>
                  ))}
                </section>
              )}
              <footer>
                <span>
                  NormLab <span className="muted">/</span> исследовательский прототип
                </span>
                <span>Гарантия ограничена моделью, снимком и указанной областью.</span>
              </footer>
            </>
          )}
        </main>
      </div>
    </div>
  );
}

function Result({
  analysis,
  current,
  dirty,
  busy,
  onSignature,
}: {
  analysis?: Analysis;
  current: boolean;
  dirty: boolean;
  busy: boolean;
  onSignature: () => void;
}) {
  const verification = analysis?.receipt.payload.verification;
  const result = analysis?.certificate.result;
  return (
    <section className="card result-card" aria-labelledby="result-title">
      <div className="card-heading">
        <div>
          <span className="step">02</span>
          <h2 id="result-title">Проверяемый результат</h2>
        </div>
        {result && (
          <Chip tone={result.status === 'conditional' ? 'amber' : 'green'}>
            {result.status === 'conditional' ? 'Условный' : 'Завершённый'}
          </Chip>
        )}
      </div>
      {!analysis || !result ? (
        <div className="empty-result">
          <div className="empty-symbol" aria-hidden="true">
            ⊢
          </div>
          <h3>Вывод начинается с условия</h3>
          <p>
            Выберите состояние A и запустите проверку. Здесь появятся последствия, учёт нормы и
            квитанция.
          </p>
          <div className="empty-equation">
            120 <span>→</span> ? <small>месяцев</small>
          </div>
        </div>
      ) : (
        <>
          {dirty && (
            <p className="stale-note">
              Ниже результат сохранённого снимка. Изменённый черновик ещё не проверен.
            </p>
          )}
          {!current && verification?.status === 'verified' && (
            <p className="stale-note">
              Историческая проверка выполнена с другой моделью или средой. Запустите проверку для
              текущей версии.
            </p>
          )}
          <div
            className={`verification-line ${verification?.status === 'verified' ? 'verified' : 'pending'}`}
          >
            <span aria-hidden="true">{verification?.status === 'verified' ? '✓' : '◷'}</span>
            <div>
              <strong>
                {verification?.status === 'verified'
                  ? current
                    ? 'Проверено в Lean'
                    : 'Историческая проверка Lean'
                  : verification?.status === 'rejected'
                    ? 'Сертификат отклонён'
                    : 'Формальная проверка не завершена'}
              </strong>
              <small>
                {verification?.status === 'verified'
                  ? 'Результат связан с точными входами'
                  : verification?.reason}
              </small>
            </div>
          </div>
          <div className={`outcomes ${result.outcomes.length > 1 ? 'split' : ''}`}>
            {result.outcomes.map((outcome) => (
              <div className="outcome" key={outcome.when}>
                <span className="tiny-label">
                  {result.status === 'conditional' ? 'ЕСЛИ ' : ''}A{' '}
                  {outcome.when === 'established' ? 'УСТАНОВЛЕНО' : 'ОПРОВЕРГНУТО'}
                </span>
                <div className="result-number">
                  {outcome.prisonMonths}
                  <span>месяцев</span>
                </div>
                <p>
                  {number(outcome.fineAmount)} <span>DEMO · штраф</span>
                </p>
              </div>
            ))}
          </div>
          {result.status === 'conditional' && (
            <p className="conditional-note">
              Вопрос об A открыт. Показаны обе ветви; единственное итоговое решение пока не выбрано.
            </p>
          )}
          <div className="ledger">
            <div>
              <span className="tiny-label">УЧЁТ ОБЯЗАТЕЛЬНОЙ НОРМЫ</span>
              <strong>Уменьшение срока</strong>
            </div>
            <Chip tone={result.ledger[0].status === 'unresolved' ? 'amber' : ''}>
              {
                {
                  applied: 'Применена',
                  inapplicable: 'Неприменима',
                  unresolved: 'Ожидает установления',
                }[result.ledger[0].status]
              }
            </Chip>
          </div>
          <details className="receipt-details">
            <summary>
              Квитанция и область гарантии<span aria-hidden="true">+</span>
            </summary>
            <p>
              Область проверки — допустимость последствий и полнота ветвей в пределах одного
              синтетического правила. Статус выше показывает, завершена ли проверка. Истинность
              описания и соответствие реальному праву не устанавливаются.
            </p>
            <Hash label="Снимок" value={analysis.receipt.payload.snapshotDigest} />
            <Hash label="Модель" value={analysis.receipt.payload.bundleSemanticDigest} />
            <Hash label="Утверждение" value={verification!.statementDigest} />
            <Hash label="Toolchain" value={verification!.toolchainDigest} />
            <div className="hash">
              <span>Проверка аксиом</span>
              <code>
                {verification?.status === 'verified'
                  ? verification.axioms.join(', ') || 'Без аксиом'
                  : 'Не подтверждена'}
              </code>
            </div>
          </details>
          <div className="receipt-actions">
            <a className="secondary" href={`/api/analyses/${analysis.id}/export`} download>
              Скачать квитанцию <span aria-hidden="true">↓</span>
            </a>
            <button className="text-button" disabled={busy} onClick={onSignature}>
              Проверить подпись
            </button>
          </div>
        </>
      )}
    </section>
  );
}
