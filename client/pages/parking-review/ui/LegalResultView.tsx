import { Disclosure, Notice, Status } from '@/shared/ui';
import {
  legalOutcomeLabels,
  legalStateLabels,
  type LegalAssessment,
  type LegalWorkspace,
} from '../model/contracts.js';

const coordinateLabels: Record<string, string> = {
  participant: 'Участник',
  vehicle: 'Транспортное средство',
  location: 'Место события',
  eventDate: 'Дата события',
  timeInterval: 'Интервал размещения',
};
export function LegalResultView({
  record,
  workspace,
  stale,
}: {
  record?: LegalAssessment;
  workspace: LegalWorkspace;
  stale: boolean;
}) {
  const result = record?.result;
  const rejected = record?.verification?.status === 'rejected';
  const previousProfile = record?.verifiedByPreviousProfile === true;
  return (
    <div aria-live="polite" className="parking-legal-result">
      {record && !stale && (
        <Status>
          {record.result ? 'Расчёт сохранён' : 'Обстоятельства сохранены'} · № {record.sequence}
        </Status>
      )}
      {stale && record && (
        <Notice tone="warning">
          Текущие изменения ещё не рассчитаны. Ниже сохранённый результат прежних входов.
        </Notice>
      )}
      {result && (
        <>
          <h3>
            {rejected ? 'Расчёт отклонён проверкой Lean' : legalOutcomeLabels[result.outcome]}
          </h3>
          <Notice
            tone={
              rejected
                ? 'danger'
                : !stale && !previousProfile && record.verification?.status === 'verified'
                  ? 'success'
                  : 'warning'
            }
          >
            <strong>
              {stale && record.verification
                ? 'Проверка Lean относится к прежним входам'
                : previousProfile
                  ? 'Проверено прежней моделью PoC'
                  : record.verification?.status === 'verified'
                    ? 'Lean проверил правила модели PoC'
                    : record.verification?.status === 'rejected'
                      ? 'Lean обнаружил несоответствие модели'
                      : 'Проверка модели в Lean не выполнена'}
            </strong>
            {' · '}
            {previousProfile
              ? 'Профиль модели изменился. Выполните новый расчёт для проверки текущей моделью.'
              : (record.verification?.reason ??
                'У этого сохранённого расчёта ещё нет проверки Lean. Выполните новый расчёт.')}
          </Notice>
          {record.verification && (
            <Disclosure summary="Что именно проверено">
              <p>
                Результат, списки причин, санкция-кандидат и условные ветви для сохранённых решений
                человека. Профиль: {record.verification.profile}.
              </p>
              <p>
                Lean: {record.verification.version ?? 'недоступен'}. Проверка относится к
                сохранённым входам{stale ? ', а не к текущим изменениям' : ''}.
              </p>
              <p>Модель получает состояния обстоятельств; достоверность фабулы не проверяется.</p>
              {previousProfile && (
                <p>Сохранённое обоснование прежней модели: {record.verification.reason}</p>
              )}
            </Disclosure>
          )}
          {rejected ? (
            <Disclosure summary="Показать отвергнутый draft-расчёт">
              <h4>{legalOutcomeLabels[result.outcome]}</h4>
              <LegalResultDetails record={record} result={result} workspace={workspace} />
            </Disclosure>
          ) : (
            <LegalResultDetails record={record} result={result} workspace={workspace} />
          )}
        </>
      )}
    </div>
  );
}

function LegalResultDetails({
  record,
  result,
  workspace,
}: {
  record: LegalAssessment;
  result: NonNullable<LegalAssessment['result']>;
  workspace: LegalWorkspace;
}) {
  const label = (id: string) =>
    workspace.package.conditions.find((c) => c.id === id)?.label ?? coordinateLabels[id] ?? id;
  return (
    <>
      <p>Результат упрощённой модели по выбранным человеком обстоятельствам.</p>
      {(['conflicts', 'unsupported', 'refuted', 'missing'] as const).map(
        (key) =>
          result[key].length > 0 && (
            <div key={key}>
              <h4>
                {
                  {
                    conflicts: 'Противоречия',
                    unsupported: 'За границами поддержки',
                    refuted: 'Опровергнутые условия',
                    missing: 'Нужно уточнить',
                  }[key]
                }
              </h4>
              <ul>
                {result[key].map((id) => (
                  <li key={id}>{label(id)}</li>
                ))}
              </ul>
            </div>
          ),
      )}
      {result.candidateFine !== null && (
        <Notice tone="warning">
          Санкция-кандидат из исследованной редакции: {result.candidateFine.toLocaleString('ru-RU')}{' '}
          ₽. Это не назначенный и не подтверждённый для вашего дела штраф.
        </Notice>
      )}
      {record.input.claimedFine !== null && (
        <p>
          Упомянутый штраф {record.input.claimedFine} ₽:{' '}
          {
            {
              'not-mentioned': 'не указан',
              'not-computable': 'сравнение пока невозможно',
              'draft-match': 'совпадает только с draft-кандидатом',
              'draft-difference': 'отличается от draft-кандидата',
            }[result.sanctionComparison]
          }
          .
        </p>
      )}
      {result.branches.length > 0 && (
        <Disclosure summary="Что изменится после одного уточнения">
          <ul>
            {result.branches.map((branch) => (
              <li key={branch.assumedState}>
                Если «{label(branch.conditionId)}» —{' '}
                {legalStateLabels[branch.assumedState].toLowerCase()}:{' '}
                {legalOutcomeLabels[branch.outcome].toLowerCase()}.
              </li>
            ))}
          </ul>
          <p>Гипотезы не меняют ваши установленные обстоятельства.</p>
        </Disclosure>
      )}
    </>
  );
}
