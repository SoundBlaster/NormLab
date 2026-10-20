import { reviewPredicates, type ReviewStatement, type VehicleHypothesis } from './contracts.js';

export const predicateNames: Record<string, string> = {
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

export type StatementFieldsValue = Pick<
  ReviewStatement,
  'predicate' | 'subject' | 'speaker' | 'aboutEpisode'
> & { stance: ReviewStatement['stance'] | '' };

export function hasStatementChoices(value: StatementFieldsValue) {
  return (
    reviewPredicates.includes(value.predicate) &&
    ['asserted', 'denied', 'unknown'].includes(value.stance) &&
    value.subject.trim().length > 0 &&
    value.subject.trim().length <= 128 &&
    value.aboutEpisode.trim().length > 0 &&
    value.aboutEpisode.trim().length <= 128 &&
    (value.speaker === undefined ||
      (value.speaker.trim().length > 0 && value.speaker.trim().length <= 128))
  );
}

export type ReferenceOption = { value: string; label: string };
export type ReviewReferences = {
  subjects: ReferenceOption[];
  speakers: ReferenceOption[];
  episodes: ReferenceOption[];
};

// Display source labels only when supplied by the extraction. A reference alone
// does not establish a participant's role or the kind/ownership of a vehicle.
export function reviewReferences(
  extraction: unknown,
  statements: ReviewStatement[],
  hypotheses: VehicleHypothesis[],
): ReviewReferences {
  const result: ReviewReferences = { subjects: [], speakers: [], episodes: [] };
  const addSaved = (items: ReferenceOption[], value: string | undefined, name: string) => {
    if (value && value !== 'Не установлено' && !items.some((item) => item.value === value))
      items.push({ value, label: `${name} ${items.length + 1}` });
  };
  if (
    extraction &&
    typeof extraction === 'object' &&
    'entities' in extraction &&
    Array.isArray(extraction.entities)
  ) {
    for (const entity of extraction.entities) {
      if (!entity || typeof entity !== 'object' || typeof entity.id !== 'string') continue;
      const text = typeof entity.alias === 'string' ? entity.alias : entity.label;
      if (typeof text !== 'string' || !text.trim()) continue;
      const option = { value: entity.id, label: `Из предложения модели: ${text}` };
      result.subjects.push(option);
      if (entity.concept === 'nlcase:Participant') result.speakers.push(option);
      if (entity.concept === 'nlcase:Episode') result.episodes.push(option);
    }
  }
  for (const statement of statements) {
    addSaved(result.subjects, statement.subject, 'Объект');
    addSaved(result.speakers, statement.speaker, 'Источник');
    addSaved(result.episodes, statement.aboutEpisode, 'Эпизод');
  }
  for (const hypothesis of hypotheses) addSaved(result.episodes, hypothesis.aboutEpisode, 'Эпизод');
  return result;
}
