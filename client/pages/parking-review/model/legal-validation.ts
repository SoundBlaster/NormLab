import type { LegalFinding, LegalWorkspace } from './contracts.js';

export type LegalValidationIssue = {
  key: string;
  targetId?: string;
  message: string;
};

export function legalFieldId(key: string): string {
  return `parking-legal-${key.replace(/[^a-zA-Z0-9_-]/g, '-')}`;
}

const scopeMessages: Record<string, string> = {
  episode: 'Выберите эпизод из списка подтверждённых утверждений.',
  participant: 'Сократите описание участника до 256 символов.',
  vehicle: 'Сократите описание транспортного средства до 256 символов.',
  location: 'Сократите описание места события до 512 символов.',
  eventDate: 'Укажите действительную дату события или оставьте поле пустым, если дата неизвестна.',
  timeInterval: 'Сократите описание интервала размещения ТС до 512 символов.',
  claimedFine: 'Укажите штраф целым числом от 0 до 1 000 000 ₽ или оставьте поле пустым.',
};

export function legalValidationIssues(
  issues: readonly { path: readonly PropertyKey[]; message: string }[],
  findings: readonly LegalFinding[],
  conditions: LegalWorkspace['package']['conditions'],
): LegalValidationIssue[] {
  const result: LegalValidationIssue[] = [];
  for (const issue of issues) {
    const [root, index, field] = issue.path;
    let mapped: LegalValidationIssue;
    if (typeof root === 'string' && Object.hasOwn(scopeMessages, root)) {
      mapped = { key: root, targetId: legalFieldId(root), message: scopeMessages[root] };
    } else if (root === 'findings' && typeof index === 'number') {
      const finding = findings[index];
      const condition = conditions.find((item) => item.id === finding?.conditionId);
      const unique =
        findings.filter((item) => item.conditionId === finding?.conditionId).length === 1;
      const findingField =
        field === undefined && issue.message === 'Повторяются ссылки на утверждения.'
          ? 'statementIds'
          : field;
      if (
        condition &&
        unique &&
        (findingField === 'rationale' ||
          findingField === 'state' ||
          findingField === 'statementIds')
      ) {
        const key = `${condition.id}.${findingField}`;
        const messages = {
          rationale:
            finding.state === 'unreviewed'
              ? 'Сократите основание до 2048 символов или оставьте его пустым для решения «Не рассмотрено».'
              : 'Укажите непустое основание решения длиной до 2048 символов. Ссылки на утверждения не заменяют основание.',
          state: 'Выберите решение из списка.',
          statementIds:
            'Проверьте ссылки на утверждения: выбирайте каждое не более одного раза, до 256 ссылок.',
        };
        mapped = {
          key,
          targetId: legalFieldId(key),
          message: `«${condition.label}»: ${messages[findingField]}`,
        };
      } else {
        mapped = {
          key: 'findings',
          message: condition
            ? `«${condition.label}»: проверьте решение, основание и ссылки на утверждения. Если ошибка повторяется, сохраните введённые сведения отдельно перед обновлением страницы.`
            : 'Проверьте список обстоятельств. Если ошибка повторяется, сохраните введённые сведения отдельно перед обновлением страницы.',
        };
      }
    } else {
      mapped = {
        key: root === 'findings' ? 'findings' : 'form',
        message:
          'Не удалось проверить данные расчёта. Повторите попытку; если ошибка сохраняется, скопируйте введённые сведения перед обновлением страницы.',
      };
    }
    if (!result.some((item) => item.key === mapped.key && item.message === mapped.message)) {
      result.push(mapped);
    }
  }
  return result;
}
