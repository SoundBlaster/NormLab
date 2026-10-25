import { Fragment } from 'react';
import { Disclosure, Notice, Status } from '@/shared/ui';
import {
  isUncitedLegalFinding,
  legalOutcomeLabels,
  legalStateLabels,
  type LegalAssessment,
  type LegalWorkspace,
} from '../model/contracts.js';

/** An explicitly tentative reading of saved findings; not a new legal/Lean inference. */
export function LegalFabulaView({
  record,
  workspace,
  stale,
}: {
  record: LegalAssessment;
  workspace: LegalWorkspace;
  stale: boolean;
}) {
  const finding = (id: string) => record.input.findings.find((value) => value.conditionId === id);
  const state = (id: string) => legalStateLabels[finding(id)?.state ?? 'unreviewed'];
  const label = (id: string) =>
    workspace.package.conditions.find((condition) => condition.id === id)?.label ?? id;
  const payment = finding('noPayment');
  return (
    <div className="parking-ontology">
      <Status tone={stale ? 'warning' : 'neutral'}>
        {stale ? 'Схема сохранённого расчёта до текущих правок' : 'Фабула · кандидат интерпретации'}
      </Status>
      <p>
        Схема читает выбранные человеком обстоятельства эпизода. Связи между ними показаны как
        интерпретация; текущая проверка Lean не доказывает эту сюжетную цепочку.
      </p>
      <h4>Сущности эпизода</h4>
      <dl className="parking-ontology-roles">
        <dt>Участник</dt>
        <dd>{record.input.participant || 'Требует уточнения'}</dd>
        <dt>Транспортное средство</dt>
        <dd>{record.input.vehicle || 'Требует уточнения'}</dd>
        <dt>Парковочное место</dt>
        <dd>{record.input.location || 'Требует уточнения'}</dd>
        <dt>Эпизод / интервал</dt>
        <dd>
          {[record.input.episode, record.input.eventDate, record.input.timeInterval]
            .filter(Boolean)
            .join(' · ')}
        </dd>
        <dt>Актор размещения</dt>
        <dd>Не установлен: роль выбранного участника отдельно не подтверждена.</dd>
      </dl>
      <h4>Предполагаемый переход по фабуле</h4>
      <ol
        className="parking-ontology-flow"
        data-hypothesis="true"
        aria-label="Предполагаемая сюжетная связь, не доказанная причинная цепочка"
      >
        <li>
          <strong>State до · неизвестен</strong>
          <p>Исходное положение ТС в данных этого шага не описано.</p>
        </li>
        <li>
          <strong>Событие · размещение ТС</strong>
          <p>Решение человека: {state('placement')}.</p>
          <small>Кто или что привело ТС в это состояние — требуется уточнить.</small>
        </li>
        <li>
          <strong>Кандидат State в эпизоде</strong>
          <p>«ТС размещалось на выбранном месте» — {state('placement').toLowerCase()}.</p>
        </li>
      </ol>
      <Notice>
        Физический diff пока не вычислен: двух описанных состояний мира нет. Неизвестное состояние
        до события не заменяется утверждением «ТС не было на парковке».
      </Notice>
      <h4>Возможное ответственное отношение</h4>
      <Status tone="warning">Шаблон пилота · гипотеза</Status>
      <p>
        Для размещения на платном городском месте возможная интерпретация — отношение оплаты между
        ответственной сущностью и муниципалитетом. Муниципалитет здесь — модельная сторона;
        конкретная организация и субъект обязанности по этой схеме не установлены.
      </p>
      <Disclosure summary="Какие выбранные обстоятельства относятся к этому шаблону">
        <dl className="parking-ontology-roles">
          {['placement', 'inMoscow', 'cityParking', 'paidRegime'].map((id) => (
            <Fragment key={id}>
              <dt>{label(id)}</dt>
              <dd>{state(id)}</dd>
            </Fragment>
          ))}
        </dl>
        <p className="parking-help">
          Опровергнутые, неизвестные и противоречивые условия сохраняют свой статус. Шаблон сам по
          себе не устанавливает обязанность.
        </p>
      </Disclosure>
      <h4>Оплата и возможное нормативное последствие</h4>
      <p>
        <strong>{label('noPayment')}:</strong> {state('noPayment')}.
      </p>
      <p className="parking-help">
        {payment && isUncitedLegalFinding(payment)
          ? 'Это решение оператора без ссылки на источник.'
          : `Ссылок на утверждения: ${finding('noPayment')?.statementIds.length ?? 0}. Их смысловая достаточность автоматически не проверяется.`}
      </p>
      {record.result && (
        <p>
          <strong>
            {record.verification?.status === 'rejected'
              ? 'Отклонённый draft нормы'
              : 'Текущий результат пилотной нормы'}
            :
          </strong>{' '}
          {legalOutcomeLabels[record.result.outcome]}. Ответственность участника остаётся отдельным
          вопросом.
        </p>
      )}
    </div>
  );
}
