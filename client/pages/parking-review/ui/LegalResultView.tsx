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
  const label = (id: string) =>
    workspace.package.conditions.find((c) => c.id === id)?.label ?? coordinateLabels[id] ?? id;
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
          <h3>{legalOutcomeLabels[result.outcome]}</h3>
          <p>
            Draft-расчёт по выбранным человеком входам. Ответственность не установлена; применимость
            редакции на дату события не подтверждена.
          </p>
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
              Санкция-кандидат из исследованной редакции:{' '}
              {result.candidateFine.toLocaleString('ru-RU')} ₽. Это не назначенный и не
              подтверждённый для вашего дела штраф.
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
      )}
    </div>
  );
}
