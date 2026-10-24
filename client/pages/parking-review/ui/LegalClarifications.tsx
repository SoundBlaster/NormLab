import { useEffect, useRef, useState } from 'react';
import { Actions, Button, Field, Input, Notice, Quote, Select, Textarea } from '@/shared/ui';
import { legalStateLabels, type ReviewStatement, type LegalWorkspace } from '../model/contracts.js';
import {
  clarificationQuestions,
  prepareClarifications,
  type ClarificationAnswers,
  type ClarificationPreview,
  type ClarificationValues,
} from '../model/legal-clarifications.js';

export function LegalClarifications({
  values,
  conditions,
  statements,
  disabled,
  onDirty,
  onConfirm,
}: {
  values: ClarificationValues;
  conditions: LegalWorkspace['package']['conditions'];
  statements: ReviewStatement[];
  disabled: boolean;
  onDirty: (dirty: boolean) => void;
  onConfirm: (preview: ClarificationPreview) => void;
}) {
  const [answers, setAnswers] = useState<ClarificationAnswers>({});
  const [preview, setPreview] = useState<{ baseline: string; value: ClarificationPreview }>();
  const [error, setError] = useState('');
  const previewRef = useRef<HTMLElement>(null);
  const questions = clarificationQuestions(values, conditions);
  const baseline = JSON.stringify(values);
  const entered = questions.filter((question) => answers[question.id]?.value.trim()).length;
  const dirty = Object.values(answers).some((answer) => answer.value || answer.explanation);
  useEffect(() => {
    onDirty(dirty);
    return () => onDirty(false);
  }, [dirty, onDirty]);
  const stale = !!preview && preview.baseline !== baseline;
  useEffect(() => {
    if (!preview || stale || !previewRef.current) return;
    const section = previewRef.current;
    section.focus({ preventScroll: true });
    const bounds = section.getBoundingClientRect();
    if (bounds.top < 0 || bounds.top > window.innerHeight - 120)
      section.scrollIntoView({ block: 'start' });
  }, [preview, stale]);
  const update = (id: string, patch: Partial<{ value: string; explanation: string }>) => {
    setAnswers((current) => ({
      ...current,
      [id]: { ...(current[id] ?? { value: '', explanation: '' }), ...patch },
    }));
    setPreview(undefined);
    setError('');
  };
  function prepare() {
    try {
      const value = prepareClarifications(values, questions, answers);
      if (!value.changes.length)
        throw new Error(
          entered
            ? 'Эти ответы уже отражены в текущих обстоятельствах. Можно ответить на другие вопросы или вернуться позже.'
            : 'Ответьте хотя бы на один вопрос. Неизвестное поле можно оставить пустым.',
        );
      setPreview({ baseline, value });
      setError('');
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'Проверьте ответы.');
    }
  }
  if (!values.episode) return null;
  return (
    <section
      id="parking-legal-clarifications"
      className="parking-auto-analysis"
      aria-label="Уточняющие вопросы"
    >
      <h3>Уточняющие вопросы · {questions.length}</h3>
      <p className="parking-help">
        {[
          values.participant || 'Участник не указан',
          values.vehicle || 'ТС не указано',
          values.location || 'Место не указано',
          values.eventDate || 'Дата не указана',
          values.timeInterval || 'Интервал не указан',
        ].join(' · ')}
      </p>
      {questions.length === 0 ? (
        <Notice tone="success">
          Открытых вопросов по текущим обстоятельствам нет. Можно выполнить расчёт и проверку Lean.
        </Notice>
      ) : (
        <>
          <p>
            Ответьте на известные вопросы. Затем проверьте и подтвердите изменения. Сохранённые
            частичные ответы останутся в истории; к остальным можно вернуться позже.
          </p>
          <p className="parking-help">
            Вопросы относятся к текущему эпизоду. «Не знаю» сохраняет неопределённость. Ответы не
            вызывают модель.
          </p>
          <fieldset className="parking-legal-fields" disabled={disabled}>
            <legend>
              Подготовка ответов · заполнено {entered} из {questions.length}
            </legend>
            {questions.map((question, index) => {
              const answer = answers[question.id] ?? { value: '', explanation: '' };
              const conflict = question.kind === 'finding' && question.finding.state === 'conflict';
              const resolving =
                question.kind === 'finding' &&
                conflict &&
                question.options.some(
                  (option) =>
                    option.value === answer.value &&
                    ['established', 'refuted'].includes(option.state),
                );
              return (
                <div key={question.id} className="parking-statement-list">
                  <Field label={`${index + 1}. ${question.prompt}`}>
                    {question.kind === 'coordinate' ? (
                      <Input
                        type={question.key === 'eventDate' ? 'date' : 'text'}
                        value={answer.value}
                        maxLength={['location', 'timeInterval'].includes(question.key) ? 512 : 256}
                        onChange={(event) => update(question.id, { value: event.target.value })}
                      />
                    ) : (
                      <Select
                        value={answer.value}
                        onChange={(event) => update(question.id, { value: event.target.value })}
                      >
                        <option value="">Пока не отвечено</option>
                        {question.options.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </Select>
                    )}
                  </Field>
                  {question.kind === 'coordinate' && (
                    <p className="parking-help">
                      Если неизвестно, оставьте поле пустым — пробел сохранится.
                    </p>
                  )}
                  {question.kind === 'finding' && (
                    <>
                      <p className="parking-help">
                        Сейчас: {legalStateLabels[question.finding.state]}.{' '}
                        {question.finding.rationale}
                      </p>
                      {question.hint && <p className="parking-help">{question.hint}</p>}
                      {conflict && (
                        <Notice tone="warning">
                          Обстоятельство отмечено как противоречивое. Для выбора версии объясните
                          решение. Исходные утверждения сохранятся в разборе. «Не знаю» не снимает
                          противоречие.
                        </Notice>
                      )}
                      {statements
                        .filter((statement) => question.finding.statementIds.includes(statement.id))
                        .map((statement) => (
                          <Quote key={statement.id}>«{statement.quote}»</Quote>
                        ))}
                      <Field
                        label={`Пояснение${resolving ? ' — обязательно для разрешения противоречия' : ' — необязательно'}`}
                      >
                        <Textarea
                          rows={2}
                          maxLength={1200}
                          aria-required={resolving}
                          value={answer.explanation}
                          onChange={(event) =>
                            update(question.id, { explanation: event.target.value })
                          }
                        />
                      </Field>
                    </>
                  )}
                </div>
              );
            })}
            <Actions>
              <Button disabled={!entered} onClick={prepare}>
                Проверить подготовленные изменения · {entered}
              </Button>
              {dirty && (
                <Button
                  variant="quiet"
                  onClick={() => {
                    setAnswers({});
                    setPreview(undefined);
                    setError('');
                  }}
                >
                  Отменить ответы
                </Button>
              )}
            </Actions>
          </fieldset>
          {error && (
            <Notice tone="danger" role="alert">
              {error}
            </Notice>
          )}
          {stale && (
            <Notice tone="warning">
              Обстоятельства изменились. Заново подготовьте изменения по текущим вопросам.
            </Notice>
          )}
          {preview && !stale && (
            <section ref={previewRef} tabIndex={-1} aria-label="Подготовленные изменения">
              <h4>Проверьте изменения перед сохранением</h4>
              <Notice>
                Ответы станут вашими решениями после подтверждения. Расчёт и Lean запускаются
                отдельно.
              </Notice>
              {preview.value.resetConditionIds.length > 0 && (
                <Notice tone="warning">
                  Уточнение координат меняет область решений. Прежние решения будут сброшены до «Не
                  рассмотрено»:{' '}
                  {preview.value.resetConditionIds
                    .map((id) => conditions.find((condition) => condition.id === id)?.label ?? id)
                    .join('; ')}
                  . Ответы из этого списка будут применены уже к уточнённым координатам; ссылки на
                  прежнюю область не переносятся.
                </Notice>
              )}
              <ul>
                {preview.value.changes.map((change) => (
                  <li key={change.id}>
                    <strong>{change.label}</strong>:{' '}
                    {change.id.startsWith('finding:')
                      ? `${legalStateLabels[change.before as keyof typeof legalStateLabels]} → ${legalStateLabels[change.after as keyof typeof legalStateLabels]}`
                      : `${change.before || 'не указано'} → ${change.after}`}
                    .<p>{change.rationale}</p>
                  </li>
                ))}
              </ul>
              <Button disabled={disabled} onClick={() => onConfirm(preview.value)}>
                Подтвердить и сохранить ответы · {preview.value.changes.length}
              </Button>
            </section>
          )}
        </>
      )}
    </section>
  );
}
