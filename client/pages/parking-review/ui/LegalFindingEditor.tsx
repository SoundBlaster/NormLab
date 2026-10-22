import { CheckField, Disclosure, Field, Select, Textarea } from '@/shared/ui';
import {
  legalStates,
  legalStateLabels,
  type LegalFinding,
  type LegalWorkspace,
  type ReviewStatement,
} from '../model/contracts.js';

export function LegalFindingEditor({
  condition,
  finding,
  statements,
  disabled,
  onChange,
}: {
  condition: LegalWorkspace['package']['conditions'][number];
  finding: LegalFinding;
  statements: ReviewStatement[];
  disabled: boolean;
  onChange: (patch: Partial<LegalFinding>) => void;
}) {
  return (
    <fieldset className="parking-legal-fields" disabled={disabled}>
      <legend>{condition.label}</legend>
      <p className="parking-help">{condition.hint}</p>
      <Field label="Решение человека">
        <Select
          value={finding.state}
          onChange={(e) => onChange({ state: e.target.value as LegalFinding['state'] })}
        >
          {legalStates.map((state) => (
            <option key={state} value={state}>
              {legalStateLabels[state]}
            </option>
          ))}
        </Select>
      </Field>
      <Field label="Основание решения или вопрос для уточнения">
        <Textarea
          rows={2}
          maxLength={2048}
          value={finding.rationale}
          onChange={(e) => onChange({ rationale: e.target.value })}
        />
      </Field>
      <Disclosure summary={`Ссылки на проверенные утверждения · ${finding.statementIds.length}`}>
        <p className="parking-help">
          Это ссылки на слова в тексте, а не автоматическое доказательство обстоятельства. Решение
          может опираться на ваше дополнение, записанное в основании.
        </p>
        {statements.map((s) => (
          <CheckField
            key={s.id}
            checked={finding.statementIds.includes(s.id)}
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
    </fieldset>
  );
}
