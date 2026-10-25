import { CheckField, Disclosure, Field, Notice, Select, Textarea } from '@/shared/ui';
import {
  legalStates,
  legalStateLabels,
  isUncitedLegalFinding,
  type LegalFinding,
  type LegalWorkspace,
  type ReviewStatement,
} from '../model/contracts.js';
import { legalFieldId, type LegalValidationIssue } from '../model/legal-validation.js';

export function LegalFindingEditor({
  condition,
  finding,
  statements,
  disabled,
  issues = [],
  onChange,
}: {
  condition: LegalWorkspace['package']['conditions'][number];
  finding: LegalFinding;
  statements: ReviewStatement[];
  disabled: boolean;
  issues?: LegalValidationIssue[];
  onChange: (patch: Partial<LegalFinding>) => void;
}) {
  const fieldId = (field: string) => legalFieldId(`${condition.id}.${field}`);
  const fieldError = (field: string) =>
    issues
      .filter((issue) => issue.key === `${condition.id}.${field}`)
      .map((issue) => issue.message)
      .join(' ');
  const stateError = fieldError('state');
  const rationaleError = fieldError('rationale');
  const statementsError = fieldError('statementIds');
  const rationaleRequired = finding.state !== 'unreviewed';
  return (
    <fieldset className="parking-legal-fields" disabled={disabled}>
      <legend>{condition.label}</legend>
      <p className="parking-help">{condition.hint}</p>
      <Field label="Решение человека">
        <Select
          id={fieldId('state')}
          value={finding.state}
          aria-invalid={!!stateError}
          aria-describedby={stateError ? `${fieldId('state')}-error` : undefined}
          onChange={(e) => onChange({ state: e.target.value as LegalFinding['state'] })}
        >
          {legalStates.map((state) => (
            <option key={state} value={state}>
              {legalStateLabels[state]}
            </option>
          ))}
        </Select>
      </Field>
      {stateError && (
        <Notice tone="danger" id={`${fieldId('state')}-error`}>
          {stateError}
        </Notice>
      )}
      {isUncitedLegalFinding(finding) && (
        <Notice tone="warning">
          Решение оператора без ссылки на источник. Запишите своё основание ниже.
        </Notice>
      )}
      <Field
        label={`Основание решения или вопрос для уточнения${rationaleRequired ? ' — обязательно' : ''}`}
      >
        <Textarea
          id={fieldId('rationale')}
          rows={2}
          maxLength={2048}
          value={finding.rationale}
          aria-required={rationaleRequired}
          aria-invalid={!!rationaleError}
          aria-describedby={[
            `${fieldId('rationale')}-help`,
            ...(rationaleError ? [`${fieldId('rationale')}-error`] : []),
          ].join(' ')}
          onChange={(e) => onChange({ rationale: e.target.value })}
        />
      </Field>
      <p className="parking-help" id={`${fieldId('rationale')}-help`}>
        Для любого решения, кроме «Не рассмотрено», запишите основание. Ссылки на утверждения не
        заменяют основание решения.
      </p>
      {rationaleError && (
        <Notice tone="danger" id={`${fieldId('rationale')}-error`}>
          {rationaleError}
        </Notice>
      )}
      <Disclosure
        id={fieldId('statementIds')}
        tabIndex={-1}
        aria-invalid={!!statementsError}
        aria-describedby={statementsError ? `${fieldId('statementIds')}-error` : undefined}
        summary={`Ссылки на проверенные утверждения · ${finding.statementIds.length}`}
      >
        <p className="parking-help">
          Это ссылки на слова в тексте, а не автоматическое доказательство обстоятельства. Решение
          может опираться на ваше дополнение, записанное в основании.
        </p>
        {statements.map((s) => (
          <CheckField
            key={s.id}
            id={fieldId(`statementIds.${s.id}`)}
            checked={finding.statementIds.includes(s.id)}
            aria-invalid={!!statementsError}
            aria-describedby={statementsError ? `${fieldId('statementIds')}-error` : undefined}
            onChange={(e) =>
              onChange({
                statementIds: e.target.checked
                  ? [...finding.statementIds, s.id]
                  : finding.statementIds.filter((id) => id !== s.id),
              })
            }
          >
            «{s.quote}» — {s.valueText}
          </CheckField>
        ))}
      </Disclosure>
      {statementsError && (
        <Notice tone="danger" id={`${fieldId('statementIds')}-error`}>
          {statementsError}
        </Notice>
      )}
    </fieldset>
  );
}
