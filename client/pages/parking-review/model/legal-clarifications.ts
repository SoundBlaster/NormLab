import {
  emptyLegalFindings,
  legalCoordinateKeys,
  type LegalCoordinateKey,
  type LegalFinding,
  type LegalInput,
  type LegalWorkspace,
} from './contracts.js';

export type ClarificationValues = Pick<
  LegalInput,
  'episode' | 'participant' | 'vehicle' | 'location' | 'eventDate' | 'timeInterval' | 'findings'
>;
export type ClarificationAnswer = { value: string; explanation: string };
export type ClarificationAnswers = Record<string, ClarificationAnswer>;
type Option = { value: string; label: string; state: LegalFinding['state'] };
type Definition = { prompt: string; hint?: string; options: Option[] };
export type ClarificationQuestion =
  | { id: string; kind: 'coordinate'; key: LegalCoordinateKey; prompt: string; label: string }
  | {
      id: string;
      kind: 'finding';
      conditionId: string;
      label: string;
      prompt: string;
      hint?: string;
      options: Option[];
      finding: LegalFinding;
    };

const binary = (prompt: string, positive = true, hint?: string): Definition => ({
  prompt,
  hint,
  options: [
    { value: 'yes', label: 'Да', state: positive ? 'established' : 'refuted' },
    { value: 'no', label: 'Нет', state: positive ? 'refuted' : 'established' },
    { value: 'unknown', label: 'Не знаю', state: 'not-established' },
  ],
});
// Each question names the existing PoC condition. No interpretation of free text or new rules.
const definitions: Record<string, Definition> = {
  inMoscow: binary('Место этого эпизода находится в Москве?'),
  cityParking: binary('Это обычная городская уличная парковка без шлагбаума?'),
  placement: binary('Выбранное ТС было размещено на этом парковочном месте?'),
  paidRegime: binary('Для этого места и всего указанного интервала действовал платный режим?'),
  personalCar: binary(
    'Участник — физическое лицо, а выбранное ТС — его личный легковой автомобиль?',
    true,
    'Если роль участника или вид ТС неизвестны, выберите «Не знаю».',
  ),
  simplePayment: binary(
    'Были ли поздняя оплата, ошибка реквизитов, исправление или спорное продление?',
    false,
  ),
  noPrivilege: binary(
    'Были ли заявлены разрешение, льгота, абонемент или специальный тариф?',
    false,
  ),
  noSpecialCircumstances: binary(
    'Были ли технический сбой, вынужденная остановка или спор об ответственности за ТС?',
    false,
  ),
  noPayment: {
    prompt: 'Что известно об оплате выбранного ТС, места и интервала?',
    hint: 'Успешная оплата должна относиться к правильному ТС, месту и всему интервалу. Пополнение баланса и попытка оплаты этого не подтверждают.',
    options: [
      { value: 'absent', label: 'Оплаты не было', state: 'established' },
      {
        value: 'paid',
        label: 'Успешно оплачено вовремя за весь интервал',
        state: 'refuted',
      },
      {
        value: 'unclear',
        label: 'Была попытка оплаты или неоднозначный результат',
        state: 'not-established',
      },
      { value: 'unknown', label: 'Не знаю', state: 'not-established' },
    ],
  },
};
const coordinates: Record<LegalCoordinateKey, { label: string; prompt: string }> = {
  participant: {
    label: 'Участник',
    prompt: 'К какому участнику относятся обстоятельства этого эпизода?',
  },
  vehicle: { label: 'Транспортное средство', prompt: 'О каком транспортном средстве идёт речь?' },
  location: { label: 'Место события', prompt: 'Где именно находилось транспортное средство?' },
  eventDate: { label: 'Дата события', prompt: 'В какую дату произошёл этот эпизод?' },
  timeInterval: {
    label: 'Интервал размещения',
    prompt: 'В течение какого интервала ТС находилось на парковке?',
  },
};

export function clarificationQuestions(
  values: ClarificationValues,
  conditions: LegalWorkspace['package']['conditions'],
): ClarificationQuestion[] {
  if (!values.episode) return [];
  const result: ClarificationQuestion[] = legalCoordinateKeys
    .filter((key) => !values[key].trim())
    .map((key) => ({ id: `coordinate:${key}`, kind: 'coordinate', key, ...coordinates[key] }));
  for (const condition of conditions) {
    const finding = values.findings.find((item) => item.conditionId === condition.id);
    const definition = definitions[condition.id];
    if (
      finding &&
      definition &&
      ['unreviewed', 'not-established', 'conflict'].includes(finding.state)
    )
      result.push({
        id: `finding:${condition.id}`,
        kind: 'finding',
        conditionId: condition.id,
        label: condition.label,
        ...definition,
        finding,
      });
  }
  return result;
}

export type ClarificationChange = {
  id: string;
  label: string;
  before: string;
  after: string;
  rationale: string;
  statementIds: string[];
};
export type ClarificationPreview = {
  baseline: string;
  values: ClarificationValues;
  changes: ClarificationChange[];
  resetConditionIds: string[];
  answeredIds: string[];
};

export function prepareClarifications(
  values: ClarificationValues,
  questions: ClarificationQuestion[],
  answers: ClarificationAnswers,
): ClarificationPreview {
  const next: ClarificationValues = {
    ...values,
    findings: values.findings.map((item) => ({ ...item })),
  };
  const changes: ClarificationChange[] = [];
  const answeredIds: string[] = [];
  const answered = questions.filter((question) => answers[question.id]?.value.trim());
  for (const question of answered) {
    if (question.kind !== 'coordinate') continue;
    const value = answers[question.id].value.trim();
    next[question.key] = value;
    answeredIds.push(question.id);
    changes.push({
      id: question.id,
      label: question.label,
      before: values[question.key],
      after: value,
      rationale: 'Указано пользователем при уточнении эпизода.',
      statementIds: [],
    });
  }
  // Coordinate changes narrow the scope. The confirmation shows every reset explicitly.
  const scopeChanged = legalCoordinateKeys.some((key) => values[key] !== next[key]);
  const resetConditionIds = scopeChanged
    ? values.findings
        .filter((item) => item.state !== 'unreviewed' || item.rationale || item.statementIds.length)
        .map((item) => item.conditionId)
    : [];
  if (scopeChanged) next.findings = emptyLegalFindings();
  for (const question of answered) {
    if (question.kind !== 'finding') continue;
    const answer = answers[question.id];
    const option = question.options.find((item) => item.value === answer.value);
    if (!option) throw new Error('Выберите ответ из предложенных вариантов.');
    const explanation = answer.explanation.trim();
    const resolvingConflict =
      question.finding.state === 'conflict' && ['established', 'refuted'].includes(option.state);
    if (resolvingConflict && !explanation)
      throw new Error(`«${question.prompt}»: объясните, почему выбираете эту версию.`);
    const keepConflict =
      question.finding.state === 'conflict' && !['established', 'refuted'].includes(option.state);
    const state = keepConflict ? 'conflict' : option.state;
    const rationale = `${keepConflict ? 'Противоречие не разрешено. ' : ''}Уточнение пользователя: ${question.prompt} Ответ: ${option.label}.${explanation ? ` Основание: ${explanation}` : ''}`;
    if (rationale.length > 2048) throw new Error('Сократите пояснение к ответу.');
    const original = next.findings.find((item) => item.conditionId === question.conditionId)!;
    if (original.state === state && original.rationale === rationale) continue;
    const finding = { ...original, state, rationale };
    next.findings = next.findings.map((item) =>
      item.conditionId === finding.conditionId ? finding : item,
    );
    answeredIds.push(question.id);
    changes.push({
      id: question.id,
      label: question.label,
      before: question.finding.state,
      after: state,
      rationale,
      statementIds: finding.statementIds,
    });
  }
  return {
    baseline: JSON.stringify(values),
    values: next,
    changes,
    resetConditionIds,
    answeredIds,
  };
}
