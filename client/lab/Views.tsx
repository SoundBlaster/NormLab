import { useEffect, useState } from 'react';
import type { LabAnalysisView, LabBootstrap } from '../../shared/reform-lab.js';
import type { ReformExplanation } from '../../shared/reform-explanations.js';
import type { ReformMetrics } from '../../shared/reform-metrics.js';
import type { FindingState } from '../../shared/domain.js';

export const findingNames: Record<FindingState, string> = {
  established: 'Установлено',
  refuted: 'Опровергнуто',
  unreviewed: 'Не рассмотрено',
  'not-established': 'Не установлено',
};
export const formatNumber = (value: number) => new Intl.NumberFormat('ru-RU').format(value);
const ledgerNames = {
  applied: 'Применено',
  inapplicable: 'Неприменимо',
  excluded: 'Исключено',
  unresolved: 'Открыто',
};
const reasons = {
  'outside-group': 'Другая группа',
  'baseline-selected': 'База выбрана по группе',
  'trigger-false': 'Условие опровергнуто',
  'scale-applied': 'Обязательное уменьшение',
  'excluded-by-E': 'N исключено при E',
  'exclusion-applied': 'Исключение блокирует N',
  'exclusion-inactive': 'N и E не установлены одновременно',
};
const inputLabel = (x: ReformExplanation['cases'][number]['traces'][number]['input']) =>
  `${x.group} · M=${x.M ? 'да' : 'нет'} · N=${x.N ? 'да' : 'нет'} · E=${x.E ? 'да' : 'нет'}`;
export function downloadData(filename: string, value: unknown, text = false) {
  const url = URL.createObjectURL(
    new Blob([text ? String(value) : `${JSON.stringify(value, null, 2)}\n`], {
      type: text ? 'text/plain;charset=utf-8' : 'application/json',
    }),
  );
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export function Evidence({ view }: { view: LabAnalysisView }) {
  const evidence = view.metricsReport?.evidence;
  return (
    <div
      className={`lab-evidence ${evidence?.current ? 'confirmed' : 'unconfirmed'}`}
      role="status"
    >
      <strong>
        {evidence?.current
          ? 'Проверено в Lean'
          : evidence?.proofStatus === 'rejected'
            ? 'Проверка отклонена'
            : view.analysis.receipt
              ? 'Историческая или незавершённая проверка'
              : 'Candidate · без подписанной квитанции'}
      </strong>
      <span>
        {evidence?.current
          ? `Подпись и входы подтверждены · ${view.explanation.coverage.coveredCardinality}/${view.explanation.coverage.declaredCardinality} ${view.explanation.coverage.kind === 'snapshot-completions' ? 'completions' : 'наблюдений'}`
          : (evidence?.reason ?? view.analysis.verification.reason)}
      </span>
      <small>
        Coverage: {view.explanation.coverage.status}; scope: {view.explanation.scope.domain.id} /{' '}
        {view.explanation.scope.kind}
        {view.explanation.scope.condition ? ` / M=${view.explanation.scope.condition.M}` : ''}.
      </small>
      {!view.registryCurrent && (
        <small>Использована историческая редакция модели. Текущий реестр отличается.</small>
      )}
    </div>
  );
}
export function ArtifactActions({ view, issuerKey }: { view: LabAnalysisView; issuerKey: string }) {
  const current = view.metricsReport?.evidence.current;
  return (
    <div className="lab-artifact-actions">
      {view.analysis.receipt && (
        <a className="secondary" href={`/api/reform/analyses/${view.analysis.id}/export`} download>
          Export и receipt ↓
        </a>
      )}
      {current && (
        <>
          <button
            className="secondary"
            onClick={() =>
              downloadData(`${view.analysis.id}.explanation.json`, view.explanationReport)
            }
          >
            Explanation ↓
          </button>
          <button
            className="secondary"
            onClick={() => downloadData(`${view.analysis.id}.metrics.json`, view.metricsReport)}
          >
            Metrics ↓
          </button>
        </>
      )}
      {view.analysis.annotations && (
        <button
          className="text-button"
          onClick={() => downloadData('source-annotations.json', view.analysis.annotations)}
        >
          Source annotations ↓
        </button>
      )}
      <button
        className="text-button"
        onClick={() => downloadData('issuer-public.pem', issuerKey, true)}
      >
        Public key ↓
      </button>
    </div>
  );
}
export function ExplanationPanel({ view }: { view: LabAnalysisView }) {
  const e = view.explanation;
  const [index, setIndex] = useState(e.counterexampleCase ?? 0);
  useEffect(() => setIndex(e.counterexampleCase ?? 0), [view.analysis.id, e.counterexampleCase]);
  const row = e.cases[index] ?? e.cases[0];
  return (
    <section className="lab-panel" aria-label="Объяснение результата">
      <div className="lab-panel-heading">
        <div>
          <span className="eyebrow">ОТ ПРАВИЛА К ПОСЛЕДСТВИЮ</span>
          <h2>Разобрать вывод</h2>
        </div>
        <label>
          Ветвь / наблюдение
          <select value={row.index} onChange={(event) => setIndex(Number(event.target.value))}>
            {e.cases.map((c) => (
              <option key={c.index} value={c.index}>
                {inputLabel(c.traces[0].input)}
                {e.counterexampleCase === c.index ? ' · counterexample' : ''}
              </option>
            ))}
          </select>
        </label>
      </div>
      <p className="lab-note">
        Ledger и source excerpts — deterministic explanation. Formal status относится к исходному
        certificate.
      </p>
      {e.findings && (
        <details className="lab-details">
          <summary>Findings и assumptions</summary>
          {(['M', 'N', 'E'] as const).map((p) => (
            <p key={p}>
              <strong>
                {p}: {findingNames[e.findings![p].state]}
              </strong>{' '}
              — {e.findings![p].rationale || 'Без установления'}
            </p>
          ))}
          {e.assumptions.map((a) => (
            <p key={a}>{a}</p>
          ))}
        </details>
      )}
      <div className="lab-traces">
        {row.traces.map((trace) => (
          <Trace
            key={`${trace.role}/${trace.bundleId}`}
            trace={trace}
            source={e.sources.find((s) => s.bundleId === trace.bundleId)!}
          />
        ))}
      </div>
      {row.components.length > 0 && (
        <p className="lab-note">
          {row.components
            .map(
              (c) =>
                `${c.component}: ${c.changed ? `${c.baseline} → ${c.candidate}` : 'сохранено'}`,
            )
            .join(' · ')}
        </p>
      )}
    </section>
  );
}
function Trace({
  trace,
  source,
}: {
  trace: ReformExplanation['cases'][number]['traces'][number];
  source: ReformExplanation['sources'][number];
}) {
  return (
    <div className="lab-trace">
      <h3>
        {trace.role === 'model' ? 'Модель' : trace.role === 'baseline' ? 'Baseline' : 'Candidate'} ·{' '}
        {trace.bundleId}
      </h3>
      <p className="lab-outcome-line">
        <strong>{trace.outcome.prisonMonths} месяцев</strong>
        <span>
          + {formatNumber(trace.outcome.fineAmount)} {trace.outcome.currency} ·{' '}
          {trace.outcome.qualification}
        </span>
      </p>
      <p className="lab-timeline">{trace.timeline.join(' → ')}</p>
      {trace.events.map((event) => {
        const mapping = source.rules.find((s) => s.rule.id === event.ruleId)!;
        const op = mapping.rule.operation;
        return (
          <details className="lab-ledger-entry" key={event.ruleId}>
            <summary>
              <span>
                <strong>{event.ruleId}</strong>
                <small>{reasons[event.reason]}</small>
              </span>
              <span className={`lab-status ${event.status}`}>{ledgerNames[event.status]}</span>
            </summary>
            <div>
              {event.conditions.map((c) => (
                <p key={c.predicate}>
                  {c.predicate}={String(c.value)} ·{' '}
                  {c.origin === 'finding'
                    ? 'установление'
                    : c.origin === 'completion'
                      ? 'предположение ветви'
                      : 'domain input'}
                </p>
              ))}
              {event.excludedBy && <p>Основание исключения: {event.excludedBy}.</p>}
              {event.step && (
                <p className="lab-step">
                  {event.step.beforeMonths}
                  {op.kind === 'scale' ? ` × ${op.numerator}/${op.denominator}` : ''} ={' '}
                  <strong>{event.step.afterMonths} месяцев</strong>
                </p>
              )}
              <p>
                Source: {source.sourceId}#{mapping.anchor}, строки {mapping.startLine}–
                {mapping.endLine}.
              </p>
              <pre className="lab-source-text">{mapping.text}</pre>
              {mapping.originRuleIds.length > 0 && (
                <p>Происхождение: {mapping.originRuleIds.join(', ')}.</p>
              )}
            </div>
          </details>
        );
      })}
    </div>
  );
}
export function ModelCards({
  views,
  active,
  onSelect,
}: {
  views: LabAnalysisView[];
  active: string;
  onSelect: (role: string) => void;
}) {
  return (
    <div className="lab-model-grid">
      {(['A', 'B', 'C'] as const).map((role) => {
        const view = views.find((v) => v.analysis.modelRole === role);
        const certificate = view?.analysis.certificate;
        const branches = certificate?.kind === 'decision' ? certificate.result.branches : [];
        const values = [...new Set(branches.map((b) => b.outcome.prisonMonths))];
        return (
          <section className={`lab-model-card ${active === role ? 'selected' : ''}`} key={role}>
            <div className="lab-model-heading">
              <span className="lab-model-letter">{role}</span>
              <h2>{{ A: 'Исходная', B: 'Упрощённая', C: 'Реформа' }[role]}</h2>
            </div>
            <p>
              {
                {
                  A: '7 положений · отдельные M/N',
                  B: '5 положений · общие M/N',
                  C: '5 положений · M × 1/2',
                }[role]
              }
            </p>
            {view && branches.length ? (
              <>
                <div className="lab-term">
                  {values.join(' / ')}
                  <span>месяцев</span>
                </div>
                <p>{formatNumber(branches[0].outcome.fineAmount)} DEMO · штраф</p>
                <p>
                  {branches.length} {branches.length === 1 ? 'completion' : 'completions'} ·{' '}
                  {certificate?.kind === 'decision' && certificate.result.status === 'conditional'
                    ? 'условный результат'
                    : 'завершённый результат'}
                </p>
                <Evidence view={view} />
                <button
                  className="secondary"
                  aria-pressed={active === role}
                  onClick={() => onSelect(role)}
                >
                  Разобрать {role}
                </button>
              </>
            ) : (
              <div className="lab-card-empty">Запустите общий анализ сохранённого snapshot.</div>
            )}
          </section>
        );
      })}
    </div>
  );
}
export function StructureTable({ models }: { models: ReformMetrics['models'] }) {
  return (
    <div
      className="lab-table-scroll"
      tabIndex={0}
      role="region"
      aria-label="Метрики структуры и решения"
    >
      <table className="lab-metrics-table">
        <caption>Отдельные единицы подсчёта по source и Legal IR</caption>
        <thead>
          <tr>
            <th>Метрика</th>
            {models.map((m) => (
              <th key={`${m.role}/${m.bundle.id}`}>
                {m.bundle.id.replace('reform-', '').replace('-0_1_0', '')}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {(
            [
              ['Именованные положения source', (m) => m.structure.provisionCount],
              ['Group-expanded rules', (m) => m.structure.groupExpandedRuleCount],
              ['Operation templates', (m) => m.structure.operationTemplateCount],
              ['Дополнительные повторы operations', (m) => m.structure.repeatedOperationCount],
              ['Определения M/N/E в source', (m) => m.structure.definitionCount ?? 'unavailable'],
              [
                'Нормативные текстовые отсылки',
                (m) => m.structure.normativeTextReferenceCount ?? 'unavailable',
              ],
              ['Exclusion edges в IR', (m) => m.structure.exclusionReferenceCount],
              ['Независимые условия', (m) => m.decision.independentConditionCount],
              ['Explicit trigger occurrences', (m) => m.decision.explicitConditionOccurrenceCount],
              ['Правила исключения', (m) => m.decision.exceptionCount],
              ['Human judgment points', (m) => m.decision.humanJudgmentCount],
            ] satisfies [string, (m: ReformMetrics['models'][number]) => number | string][]
          ).map(([name, value]) => (
            <tr key={name}>
              <th scope="row">{name}</th>
              {models.map((m) => (
                <td key={`${m.role}/${m.bundle.id}`}>{value(m)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
export function ConsequenceMetrics({ view }: { view: LabAnalysisView }) {
  const c = view.metrics.consequences;
  return (
    <section className="lab-panel">
      <div className="lab-panel-heading">
        <div>
          <span className="eyebrow">КОМПОНЕНТЫ И COVERED SCOPE</span>
          <h2>Изменения последствий</h2>
          <p>{view.analysis.title}</p>
        </div>
      </div>
      <Evidence view={view} />
      <p className="lab-note">
        Метрики рассчитаны детерминированно, без отдельного Lean proof. Они не образуют общего
        индекса гуманности.
      </p>
      {c.kind === 'decision' ? (
        <div className="lab-stat-grid">
          <div>
            <strong>{c.completionCount}</strong>
            <span>completions</span>
          </div>
          <div>
            <strong>{c.distinctOutcomeCount}</strong>
            <span>полных outcomes</span>
          </div>
          <div>
            <strong>{c.openHumanJudgmentCount}</strong>
            <span>открытых findings</span>
          </div>
        </div>
      ) : (
        <>
          <p className="lab-change-summary">
            <strong>
              {c.changedCount}/{c.observedCount}
            </strong>{' '}
            изменённых {c.unit === 'mitigation-pair' ? 'mitigation pairs' : 'completed inputs'} ·{' '}
            {c.unchangedCount} сохранено
          </p>
          <div
            className="lab-table-scroll"
            tabIndex={0}
            role="region"
            aria-label="Изменения компонентов"
          >
            <table>
              <thead>
                <tr>
                  <th>Компонент / единица</th>
                  <th>Изменено</th>
                  <th>Уменьшено</th>
                  <th>Увеличено</th>
                  <th>Delta min…max</th>
                </tr>
              </thead>
              <tbody>
                {c.components.map((x) => (
                  <tr key={x.component}>
                    <th scope="row">
                      {x.component}
                      <small>{x.unit}</small>
                    </th>
                    <td>{x.changed}</td>
                    <td>{'decreased' in x ? x.decreased : 'n/a'}</td>
                    <td>{'increased' in x ? x.increased : 'n/a'}</td>
                    <td>{'minDelta' in x ? `${x.minDelta}…${x.maxDelta}` : 'n/a'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="lab-note">
            Delta = candidate − baseline. Диапазон включает сохранённые наблюдения. Категории ниже
            описывают покрытую область.
          </p>
          <div
            className="lab-table-scroll"
            tabIndex={0}
            role="region"
            aria-label="Категории изменённых случаев"
          >
            <table>
              <thead>
                <tr>
                  <th>Категория</th>
                  <th>Наблюдений</th>
                  <th>Изменено</th>
                  <th>Компоненты</th>
                </tr>
              </thead>
              <tbody>
                {c.categories.map((x) => (
                  <tr key={`${x.group}/${x.baselineM}`}>
                    <th scope="row">
                      {x.group} · M={x.baselineM ? 'да' : 'нет'}
                    </th>
                    <td>{x.observedCount}</td>
                    <td>{x.changedCount}</td>
                    <td>{x.changedComponents.join(', ') || 'Нет изменений'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}
export function QueryResult({
  view,
  issuerKey,
  onExplore,
  exploreDisabled,
}: {
  view: LabAnalysisView;
  issuerKey: string;
  onExplore: (input: ReformExplanation['cases'][number]['traces'][number]['input']) => void;
  exploreDisabled: boolean;
}) {
  const e = view.explanation;
  const witness = e.counterexampleCase === null ? null : e.cases[e.counterexampleCase];
  return (
    <>
      <section className="lab-panel">
        <div className="lab-panel-heading">
          <div>
            <span className="eyebrow">ОТДЕЛЬНО ОТ SNAPSHOT ДЕЛА</span>
            <h2>{view.analysis.title}</h2>
          </div>
          <span className={`lab-status ${witness ? 'excluded' : 'applied'}`}>
            {!view.metricsReport?.evidence.current
              ? 'Candidate verdict'
              : witness
                ? 'Counterexample'
                : 'Свойство выполняется'}
          </span>
        </div>
        <Evidence view={view} />
        {witness && (
          <div className="lab-witness">
            <h3>
              {view.metricsReport?.evidence.current
                ? 'Свидетель нарушения'
                : 'Вычисленный candidate witness'}
            </h3>
            <p>{inputLabel(witness.traces[0].input)}</p>
            <div className="lab-witness-values">
              {witness.traces[0].outcome.prisonMonths} <span>→</span>{' '}
              {witness.traces[1].outcome.prisonMonths}
              <small>месяцев; штраф сохранён</small>
            </div>
            <p>
              D сохраняет M из C, но дополнительно меняет N с 3/4 на 2/3. Найдено изменение вне
              заявленной категории M.
            </p>
            <button
              className="secondary"
              disabled={exploreDisabled}
              onClick={() => onExplore(witness.traces[0].input)}
            >
              Перенести условия в рабочую область
            </button>
            {exploreDisabled && (
              <p className="lab-note">
                Завершите проверку либо сохраните/сбросьте draft перед переносом.
              </p>
            )}
          </div>
        )}
        <ArtifactActions view={view} issuerKey={issuerKey} />
      </section>
      <ConsequenceMetrics view={view} />
      <ExplanationPanel view={view} />
    </>
  );
}
export function Sources({ data }: { data: LabBootstrap }) {
  const [role, setRole] = useState('C');
  const model = data.models.find((m) => m.role === role)!;
  return (
    <section className="lab-panel">
      <div className="lab-panel-heading">
        <div>
          <span className="eyebrow">LOCKED SYNTHETIC MODELS</span>
          <h2>Текст, правила и происхождение</h2>
        </div>
        <label>
          Модель
          <select value={role} onChange={(e) => setRole(e.target.value)}>
            {data.models.map((m) => (
              <option key={m.role}>{m.role}</option>
            ))}
          </select>
        </label>
      </div>
      <p className="lab-note">
        {model.description} Истинность findings и fidelity перевода текста требуют human review.
      </p>
      <div className="lab-rule-list">
        {model.bundle.package.ir.rules.map((rule) => (
          <section key={rule.id}>
            <h3>{rule.id}</h3>
            <p>Groups: {rule.groups.join(', ')} · обязательное применение ровно один раз.</p>
            <p className="lab-step">
              {rule.operation.kind === 'baseline'
                ? `${rule.operation.prisonMonths} месяцев + ${formatNumber(rule.operation.fineAmount)} DEMO`
                : rule.operation.kind === 'scale'
                  ? `${rule.operation.trigger}: срок × ${rule.operation.numerator}/${rule.operation.denominator}; штраф сохранён`
                  : 'E блокирует N, сохраняя обязательность M'}
            </p>
          </section>
        ))}
      </div>
      <details className="lab-details">
        <summary>Полный синтетический источник A/B/C</summary>
        <pre className="lab-source-text">{model.bundle.package.source.content}</pre>
      </details>
      <details className="lab-details">
        <summary>Semantic/provenance digests и Legal IR</summary>
        <pre className="lab-source-text">
          {JSON.stringify(
            {
              bundleId: model.bundle.id,
              semanticDigest: model.bundle.semanticDigest,
              provenanceDigest: model.bundle.provenanceDigest,
              sourceMappings: model.bundle.package.sourceMappings,
              ir: model.bundle.package.ir,
            },
            null,
            2,
          )}
        </pre>
      </details>
    </section>
  );
}
