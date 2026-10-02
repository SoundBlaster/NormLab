import { useEffect, useState } from 'react';
import {
  labModelRoles,
  labQueries,
  type LabAnalysisView,
  type LabBootstrap,
  type LabQueryId,
  type LabWorkspace,
} from '../../shared/reform-lab.js';
import type {
  ReformSnapshot,
  ReformSnapshotInput,
  ReformCompletedInput,
} from '../../shared/reform-contracts.js';
import type { FindingState } from '../../shared/domain.js';
import {
  ArtifactActions,
  ConsequenceMetrics,
  ExplanationPanel,
  ModelCards,
  QueryResult,
  Sources,
  StructureTable,
  findingNames,
} from './Views.js';
import './lab.css';

type Tab = 'experiment' | 'properties' | 'metrics' | 'sources' | 'history';
const tabs: { id: Tab; label: string }[] = [
  { id: 'experiment', label: 'Рабочая область' },
  { id: 'properties', label: 'Свойства и counterexamples' },
  { id: 'metrics', label: 'Метрики' },
  { id: 'sources', label: 'Источники' },
  { id: 'history', label: 'История' },
];
const inputFrom = (s: ReformSnapshot): ReformSnapshotInput => ({
  narrative: s.narrative,
  group: s.group,
  findings: structuredClone(s.findings),
});
const normalized = (input: ReformSnapshotInput) => ({
  ...input,
  narrative: input.narrative.trim(),
  findings: Object.fromEntries(
    (['M', 'N', 'E'] as const).map((p) => [
      p,
      { ...input.findings[p], rationale: input.findings[p].rationale.trim() },
    ]),
  ),
});
const emptyInput: ReformSnapshotInput = {
  narrative: '',
  group: 'K1',
  findings: {
    M: { state: 'unreviewed', rationale: '' },
    N: { state: 'unreviewed', rationale: '' },
    E: { state: 'unreviewed', rationale: '' },
  },
};
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
export function Lab() {
  const [data, setData] = useState<LabBootstrap | null>(null);
  const [tab, setTab] = useState<Tab>('experiment');
  const [selectedId, setSelectedId] = useState('');
  const [form, setForm] = useState<ReformSnapshotInput>(emptyInput);
  const [caseViews, setCaseViews] = useState<LabAnalysisView[]>([]);
  const [queryView, setQueryView] = useState<LabAnalysisView | null>(null);
  const [queryId, setQueryId] = useState<LabQueryId>('AB-equivalence');
  const [activeRole, setActiveRole] = useState('C');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  async function savedViews(snapshot: ReformSnapshot, bootstrap: LabBootstrap) {
    const result: LabAnalysisView[] = [];
    for (const role of labModelRoles) {
      const prior = bootstrap.workspace.analyses.find(
        (a) => a.snapshotId === snapshot.id && a.modelRole === role,
      );
      if (prior)
        result.push(
          await request<LabAnalysisView>(
            `/api/reform/analyses/${prior.id}/replay`,
            bootstrap.csrfToken,
            {},
          ),
        );
    }
    return result;
  }
  useEffect(() => {
    let active = true;
    request<LabBootstrap>('/api/reform/bootstrap')
      .then(async (result) => {
        if (!active) return;
        const snapshot = result.workspace.snapshots[0];
        setData(result);
        setSelectedId(snapshot.id);
        setForm(inputFrom(snapshot));
        if (result.workspace.analyses.some((a) => a.snapshotId === snapshot.id)) {
          setBusy(true);
          const views = await savedViews(snapshot, result);
          if (active) setCaseViews(views);
        }
      })
      .catch((e) => {
        if (active) setError(e instanceof Error ? e.message : 'Ошибка загрузки A/B/C.');
      })
      .finally(() => {
        if (active) setBusy(false);
      });
    return () => {
      active = false;
    };
  }, []);
  const selected = data?.workspace.snapshots.find((s) => s.id === selectedId);
  const latest = data?.workspace.snapshots[0];
  const historical = !!selected && selected.id !== latest?.id;
  const dirty =
    !!selected &&
    JSON.stringify(normalized(form)) !== JSON.stringify(normalized(inputFrom(selected)));
  const activeView = caseViews.find((v) => v.analysis.modelRole === activeRole);
  async function runCase(analyze: boolean) {
    if (!data || !selected || historical) return;
    setBusy(true);
    setError('');
    setNotice('');
    try {
      let snapshot = selected,
        workspace = data.workspace;
      if (dirty) {
        const saved = await request<{ snapshot: ReformSnapshot; workspace: LabWorkspace }>(
          '/api/reform/snapshots',
          data.csrfToken,
          { input: form, expectedSnapshotId: selected.id },
        );
        snapshot = saved.snapshot;
        workspace = saved.workspace;
        setSelectedId(snapshot.id);
        setForm(inputFrom(snapshot));
        setCaseViews([]);
        setData({ ...data, workspace });
      }
      if (analyze) {
        const result = await request<{ views: LabAnalysisView[]; workspace: LabWorkspace }>(
          '/api/reform/analyze',
          data.csrfToken,
          { snapshotId: snapshot.id },
        );
        setCaseViews(result.views);
        setData({ ...data, workspace: result.workspace });
        setNotice(
          result.views.every((v) => v.metricsReport?.evidence.current)
            ? `Snapshot ${snapshot.revision}: A/B/C проверены, receipts сохранены.`
            : 'Candidates сохранены. Формальная проверка доступна не для всех результатов.',
        );
      } else setNotice(`Snapshot ${snapshot.revision} сохранён. Его можно анализировать в A/B/C.`);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Не удалось выполнить анализ.');
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = '';
    };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [dirty]);
  async function runQuery(id: LabQueryId = queryId, target: Tab = 'properties') {
    if (!data) return;
    setBusy(true);
    setError('');
    setNotice('');
    try {
      const result = await request<{ view: LabAnalysisView; workspace: LabWorkspace }>(
        '/api/reform/queries',
        data.csrfToken,
        { queryId: id },
      );
      setQueryView(result.view);
      setQueryId(id);
      setData({ ...data, workspace: result.workspace });
      setTab(target);
      setNotice(
        result.view.metricsReport?.evidence.current
          ? 'Общий query проверен; scope и receipt сохранены.'
          : 'Общий query вычислен; формальная проверка не завершена.',
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Не удалось проверить query.');
    } finally {
      setBusy(false);
    }
  }
  async function selectSnapshot(snapshot: ReformSnapshot) {
    if (!data || busy || dirty) return;
    setBusy(true);
    setError('');
    setNotice('');
    setSelectedId(snapshot.id);
    setForm(inputFrom(snapshot));
    setCaseViews([]);
    setTab('experiment');
    try {
      setCaseViews(await savedViews(snapshot, data));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Replay не выполнен.');
    } finally {
      setBusy(false);
    }
  }
  async function openQuery(id: string) {
    if (!data) return;
    setBusy(true);
    setError('');
    try {
      const view = await request<LabAnalysisView>(
        `/api/reform/analyses/${id}/replay`,
        data.csrfToken,
        {},
      );
      setQueryView(view);
      if (view.analysis.queryId) setQueryId(view.analysis.queryId);
      setTab('properties');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Replay не выполнен.');
    } finally {
      setBusy(false);
    }
  }
  function explore(input: ReformCompletedInput) {
    if (!latest || busy || dirty) return;
    setSelectedId(latest.id);
    setCaseViews([]);
    setForm({
      ...inputFrom(latest),
      group: input.group,
      findings: Object.fromEntries(
        (['M', 'N', 'E'] as const).map((p) => [
          p,
          {
            state: input[p] ? 'established' : 'refuted',
            rationale: `Перенесено из synthetic counterexample: ${p}=${input[p]}.`,
          },
        ]),
      ) as ReformSnapshotInput['findings'],
    });
    setTab('experiment');
    setNotice(
      'Условия counterexample перенесены в draft. Сохраните новую ревизию и сравните A/B/C.',
    );
  }
  function editForm(next: ReformSnapshotInput) {
    setForm(next);
    setNotice('');
  }
  if (!data || !selected)
    return (
      <section className="lab-panel" role="status">
        <h2>{error ? 'Не удалось открыть A/B/C' : 'Загружаем A/B/C…'}</h2>
        {error && <p role="alert">{error}</p>}
      </section>
    );
  const changeFinding = (
    predicate: 'M' | 'N' | 'E',
    patch: Partial<ReformSnapshotInput['findings']['M']>,
  ) =>
    editForm({
      ...form,
      findings: { ...form.findings, [predicate]: { ...form.findings[predicate], ...patch } },
    });
  return (
    <div className="lab" aria-busy={busy}>
      <nav className="lab-tabs" aria-label="Разделы A/B/C">
        {tabs.map((t) => (
          <button key={t.id} aria-pressed={tab === t.id} onClick={() => setTab(t.id)}>
            {t.label}
          </button>
        ))}
      </nav>
      {error && (
        <div className="message error" role="alert">
          {error}{' '}
          <button className="text-button" onClick={() => location.reload()}>
            Перезагрузить рабочую область
          </button>
        </div>
      )}
      <div className="lab-live" role="status" aria-live="polite">
        {busy ? (
          <p className="message">
            Выполняется проверка точных входов. Результаты появятся после завершения Lean.
          </p>
        ) : (
          notice && <p className="message">{notice}</p>
        )}
      </div>
      {tab === 'experiment' && (
        <>
          <div className="lab-context">
            <span>
              Snapshot <strong>#{selected.revision}</strong> ·{' '}
              {historical ? 'историческая ревизия' : 'последняя ревизия'}
            </span>
            <span>
              {data.verifier.available
                ? 'Lean 4.30.0 доступен'
                : 'Lean недоступен · возможен только candidate'}
            </span>
          </div>
          {historical && (
            <div className="message historical">
              Просмотр исходных входов и результатов. Эта ревизия не изменяется.
              <button onClick={() => selectSnapshot(latest!)} disabled={busy}>
                К последней ревизии →
              </button>
            </div>
          )}
          <section className="lab-panel lab-comparison" aria-labelledby="lab-comparison-title">
            <div className="lab-panel-heading">
              <div>
                <h2 id="lab-comparison-title">Сравнение A/B/C</h2>
                <p className="lab-saved-inputs">
                  Snapshot #{selected.revision} · {selected.group} ·{' '}
                  {(['M', 'N', 'E'] as const)
                    .map((p) => `${p}: ${findingNames[selected.findings[p].state]}`)
                    .join(' · ')}
                </p>
              </div>
            </div>
            <div
              className={`lab-result-context ${dirty ? 'draft' : ''}`}
              role="status"
              aria-live="polite"
            >
              {dirty ? (
                <>
                  <strong>Изменения ещё не рассчитаны.</strong>
                  <span>Ниже — результаты сохранённого snapshot #{selected.revision}.</span>
                  <button
                    className="primary"
                    disabled={busy || historical}
                    onClick={() => runCase(true)}
                  >
                    Сохранить и пересчитать A/B/C
                  </button>
                </>
              ) : caseViews.length ? (
                <span>
                  Результаты snapshot #{selected.revision}. Проверка относится к сохранённым входам.
                </span>
              ) : (
                <>
                  <span>Для snapshot #{selected.revision} пока нет результатов.</span>
                  <button
                    className="primary"
                    disabled={busy || historical}
                    onClick={() => runCase(true)}
                  >
                    Сравнить A/B/C
                  </button>
                </>
              )}
            </div>
            <ModelCards views={caseViews} active={activeRole} onSelect={setActiveRole} />
          </section>
          <section className="lab-panel lab-editor">
            <div className="lab-panel-heading">
              <div>
                <span className="eyebrow">ОДИН СУБЪЕКТ · ОДИН ЭПИЗОД</span>
                <h2>Обстоятельства и мотивированные findings</h2>
              </div>
              <span className="lab-status">Simulated reviewer</span>
            </div>
            <form
              onSubmit={(event) => {
                event.preventDefault();
                void runCase(true);
              }}
            >
              <div className="lab-case-input">
                <label>
                  Описание сценария
                  <textarea
                    value={form.narrative}
                    maxLength={6000}
                    rows={3}
                    disabled={busy || historical}
                    onChange={(e) => editForm({ ...form, narrative: e.target.value })}
                  />
                </label>
                <label>
                  Группа
                  <select
                    value={form.group}
                    disabled={busy || historical}
                    onChange={(e) => editForm({ ...form, group: e.target.value as 'K1' | 'K2' })}
                  >
                    <option>K1</option>
                    <option>K2</option>
                  </select>
                  <small>Выбор группы задан извне; основания ответственности вне scope.</small>
                </label>
              </div>
              <div className="lab-finding-grid">
                {(['M', 'N', 'E'] as const).map((p) => (
                  <fieldset key={p} disabled={busy || historical}>
                    <legend>
                      {p} ·{' '}
                      {{ M: 'Возмещение', N: 'Самостоятельное сообщение', E: 'Повторность' }[p]}
                    </legend>
                    <label>
                      Состояние {p}
                      <select
                        value={form.findings[p].state}
                        onChange={(e) =>
                          changeFinding(p, { state: e.target.value as FindingState })
                        }
                      >
                        {Object.entries(findingNames).map(([id, name]) => (
                          <option key={id} value={id}>
                            {name}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      Основание {p}
                      <textarea
                        rows={2}
                        maxLength={2000}
                        value={form.findings[p].rationale}
                        onChange={(e) => changeFinding(p, { rationale: e.target.value })}
                        placeholder="Мотивировка simulated finding"
                      />
                    </label>
                  </fieldset>
                ))}
              </div>
              <p className="lab-note">
                «Не рассмотрено» и «Не установлено» сохраняют обе completion-возможности. При N и E
                исключается только N; M остаётся обязательным.
              </p>
              <div className="lab-form-actions">
                <button className="primary" type="submit" disabled={busy || historical}>
                  {dirty ? 'Сохранить и сравнить A/B/C' : 'Сравнить A/B/C'}
                </button>
                <button
                  className="secondary"
                  type="button"
                  disabled={busy || historical || !dirty}
                  onClick={() => runCase(false)}
                >
                  Сохранить snapshot
                </button>
                {dirty && (
                  <button
                    className="text-button"
                    type="button"
                    disabled={busy}
                    onClick={() => setForm(inputFrom(selected))}
                  >
                    Сбросить draft
                  </button>
                )}
              </div>
            </form>
          </section>
          {activeView && (
            <>
              <ExplanationPanel view={activeView} />
              <ArtifactActions view={activeView} issuerKey={data.issuerPublicKey} />
            </>
          )}
        </>
      )}
      {tab === 'properties' && (
        <>
          <section className="lab-panel">
            <div className="lab-panel-heading">
              <div>
                <span className="eyebrow">ОБЩИЕ УТВЕРЖДЕНИЯ · D16</span>
                <h2>Проверить границы изменения</h2>
              </div>
            </div>
            <p className="lab-note">
              Эти queries исследуют объявленный domain. Findings выбранного snapshot не сужают их
              область.
            </p>
            <label className="lab-query-select">
              Утверждение
              <select
                value={queryId}
                disabled={busy}
                onChange={(e) => setQueryId(e.target.value as LabQueryId)}
              >
                {labQueries.map((q) => (
                  <option key={q.id} value={q.id}>
                    {q.title}
                  </option>
                ))}
              </select>
            </label>
            <p className="lab-query-description">
              {labQueries.find((q) => q.id === queryId)!.detail}
            </p>
            <button className="primary" disabled={busy} onClick={() => runQuery()}>
              Проверить свойство в Lean
            </button>
          </section>
          {queryView && (
            <QueryResult
              view={queryView}
              issuerKey={data.issuerPublicKey}
              onExplore={explore}
              exploreDisabled={busy || dirty}
            />
          )}
        </>
      )}
      {tab === 'metrics' && (
        <>
          <section className="lab-panel">
            <div className="lab-panel-heading">
              <div>
                <span className="eyebrow">СТРУКТУРА ≠ СЛОЖНОСТЬ FINDINGS</span>
                <h2>Что упрощается в модели?</h2>
              </div>
            </div>
            <StructureTable models={data.modelMetrics} />
            <p className="lab-note">
              Повторы — дополнительные экземпляры typed operations без group scope. Definitions и
              текстовые отсылки подсчитаны по reviewed source annotations. Сокращение положений не
              измеряет труд reviewer.
            </p>
            <button
              className="secondary"
              disabled={busy}
              onClick={() => runQuery('AC-component-no-increase', 'metrics')}
            >
              Исследовать изменения A → C на D16
            </button>
          </section>
          {queryView ? (
            <>
              <ConsequenceMetrics view={queryView} />
              <ArtifactActions view={queryView} issuerKey={data.issuerPublicKey} />
            </>
          ) : (
            activeView && (
              <>
                <ConsequenceMetrics view={activeView} />
                <ArtifactActions view={activeView} issuerKey={data.issuerPublicKey} />
              </>
            )
          )}
        </>
      )}
      {tab === 'sources' && <Sources data={data} />}
      {tab === 'history' && (
        <>
          {dirty && (
            <p className="message historical">
              Сохраните или сбросьте draft в рабочей области перед выбором другой ревизии.
            </p>
          )}
          <section className="lab-panel">
            <div className="lab-panel-heading">
              <div>
                <span className="eyebrow">IMMUTABLE SNAPSHOTS</span>
                <h2>История установлений</h2>
              </div>
            </div>
            <div className="lab-history">
              {data.workspace.snapshots.map((snapshot) => (
                <button
                  key={snapshot.id}
                  disabled={busy || dirty}
                  className="lab-history-row"
                  onClick={() => selectSnapshot(snapshot)}
                >
                  <span className="lab-revision">#{snapshot.revision}</span>
                  <span>
                    <strong>
                      {snapshot.group}
                      {snapshot.id === latest?.id ? ' · последняя ревизия' : ''}
                    </strong>
                    <small>
                      {(['M', 'N', 'E'] as const)
                        .map((p) => `${p}: ${findingNames[snapshot.findings[p].state]}`)
                        .join(' · ')}
                    </small>
                  </span>
                  <time>{new Date(snapshot.createdAt).toLocaleString('ru-RU')}</time>
                  <span aria-hidden="true">→</span>
                </button>
              ))}
            </div>
          </section>
          <section className="lab-panel">
            <div className="lab-panel-heading">
              <div>
                <span className="eyebrow">GENERAL QUERIES</span>
                <h2>Сохранённые свойства и witnesses</h2>
              </div>
            </div>
            <p className="lab-note">
              Статусы в списке относятся к моменту выпуска. Открытие выполняет fresh replay;
              исходные records не перезаписываются.
            </p>
            {data.workspace.analyses
              .filter((a) => a.queryId !== null)
              .map((a) => (
                <button
                  className="lab-history-row"
                  key={a.id}
                  disabled={busy}
                  onClick={() => openQuery(a.id)}
                >
                  <span>
                    <strong>{a.title}</strong>
                    <small>
                      {a.resultStatus} · issued proof: {a.proofStatus}
                    </small>
                  </span>
                  <time>{new Date(a.createdAt).toLocaleString('ru-RU')}</time>
                  <span aria-hidden="true">→</span>
                </button>
              ))}
            {!data.workspace.analyses.some((a) => a.queryId !== null) && (
              <p className="lab-note">Общие queries ещё не выполнялись.</p>
            )}
          </section>
        </>
      )}
      <p className="lab-boundary">
        Синтетическая исследовательская модель. Lean проверяет допустимость относительно locked IR и
        findings; реальное право, истинность обстоятельств и социальный эффект вне scope.
      </p>
    </div>
  );
}
