import { Disclosure, Notice, Status } from '@/shared/ui';
import {
  isUncitedLegalFinding,
  legalOutcomeLabels,
  legalStateLabels,
  type LegalAssessment,
  type LegalWorkspace,
} from '../model/contracts.js';

/** Read-only explanation of the record-reviewed-findings projection, not a new inference. */
export function LegalOntologyView({
  record,
  workspace,
  stale,
}: {
  record: LegalAssessment;
  workspace: LegalWorkspace;
  stale: boolean;
}) {
  const verification = record.verification;
  const binding = verification?.binding;
  const label = (id: string) =>
    workspace.package.conditions.find((condition) => condition.id === id)?.label ?? id;
  const supports = new Set(
    record.input.findings.flatMap((finding) =>
      finding.statementIds.map((id) => `${finding.conditionId}:${id}`),
    ),
  );
  const states = new Set(record.input.findings.map((finding) => finding.conditionId)).size;
  const added = 1 + states + supports.size;
  const verified = verification?.status === 'verified';
  return (
    <Disclosure summary="Как этот расчёт представлен в онтологии">
      {!binding ? (
        <Notice tone="neutral">
          В этой квитанции онтологическая привязка не сохранена. Новый расчёт текущей моделью
          сохранит её; прежний результат остаётся в истории.
        </Notice>
      ) : (
        <div className="parking-ontology">
          <Status
            tone={verified && !stale && !record.verifiedByPreviousProfile ? 'success' : 'warning'}
          >
            {stale
              ? 'Проекция сохранённого расчёта до текущих правок'
              : record.verifiedByPreviousProfile
                ? 'Проверено прежним профилем Lean'
                : verified
                  ? 'Проекция проверена Lean'
                  : 'Проекция входов · Lean не подтвердил проверку'}
          </Status>
          <p>
            Здесь показан шаг фиксации обстоятельств оператором. Дорожное событие остаётся
            содержанием проверенной человеком разметки.
          </p>
          <h4>Сущности и роли в этой интерпретации</h4>
          <dl className="parking-ontology-roles">
            <dt>actor / humanAnchor</dt>
            <dd>Оператор проверки</dd>
            <dt>target</dt>
            <dd>Выбранный участник: {binding.scope.participant || 'не указан'}</dd>
            <dt>instrument</dt>
            <dd>Выбранное ТС: {binding.scope.vehicle || 'не указано'}</dd>
            <dt>episode</dt>
            <dd>{binding.scope.episode}</dd>
          </dl>
          <p className="parking-help">
            Это имена слотов модели. Они сохраняют выбранный контекст и не устанавливают, кто был
            водителем, собственником или орудием реального дорожного действия.
          </p>
          <h4>Действие меняет формальное состояние</h4>
          <ol
            className="parking-ontology-flow"
            aria-label="Переход: состояние до, действие, состояние после"
          >
            <li>
              <strong>State до · ∅</strong>
              <p>Пустой начальный снимок этого события фиксации.</p>
            </li>
            <li>
              <strong>Action</strong>
              <p>Оператор фиксирует проверенные обстоятельства.</p>
              <code>record-reviewed-findings</code>
            </li>
            <li>
              <strong>State после</strong>
              <p>
                Один scope, состояний условий: {states}, связей с источниками: {supports.size}.
              </p>
            </li>
          </ol>
          <p>
            <strong>Последствие фиксации — diff двух State:</strong> добавлено {added} фактов,
            удалено 0. Начальный снимок пуст только в этом формальном переходе; состояние мира до
            парковки здесь не моделируется.
          </p>
          <Disclosure summary={`Что вошло в State после · ${states} условий`}>
            <ul className="parking-ontology-findings">
              {record.input.findings.map((finding) => (
                <li key={finding.conditionId}>
                  <strong>{label(finding.conditionId)}</strong>
                  <span>{legalStateLabels[finding.state]}</span>
                  <small className="parking-help">
                    {isUncitedLegalFinding(finding)
                      ? 'Решение оператора без ссылки на источник'
                      : `Ссылок: ${finding.statementIds.length}`}
                  </small>
                </li>
              ))}
            </ul>
          </Disclosure>
          {record.result && (
            <p>
              <strong>
                {verification?.status === 'rejected'
                  ? 'Отклонённый draft нормы'
                  : 'Отдельный расчёт нормы'}
                :
              </strong>{' '}
              {legalOutcomeLabels[record.result.outcome]}. Он вычисляется по этим состояниям;
              санкция-кандидат не является изменением состояния в показанном diff.
            </p>
          )}
          <Notice tone="neutral">
            Действия и бездействие водителя, причинная цепочка и ответственность требуют отдельной
            интерпретации. Этот переход их не устанавливает.
          </Notice>
          <Disclosure summary="Идентификаторы сохранённого события">
            <dl className="parking-ontology-roles">
              <dt>Событие / assessment</dt>
              <dd>
                <code>{binding.assessmentId}</code>
              </dd>
              <dt>Ревизия / interpretation</dt>
              <dd>
                <code>{binding.revisionId}</code>
              </dd>
              <dt>Draft</dt>
              <dd>
                <code>{binding.draftId}</code>
              </dd>
            </dl>
          </Disclosure>
        </div>
      )}
    </Disclosure>
  );
}
