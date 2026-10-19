import { reviewStatementIssues, type ReviewStatement } from '../model/contracts.js';
import { Actions, Button, Field, Quote, Status, Textarea } from '@/shared/ui';

import { hasStatementChoices, type ReviewReferences } from '../model/statement-fields.js';
import { StatementFields } from './StatementFields.js';

type Props = {
  statement: ReviewStatement;
  references: ReviewReferences;
  index: number;
  narrative: string;
  disabled: boolean;
  dirty: boolean;
  pendingSave: boolean;
  canReplaceQuote: boolean;
  onChange: (patch: Partial<ReviewStatement>) => void;
  onRationaleChange: (value: string) => void;
  onReplaceQuote: () => void;
  onDecision: (decision: 'confirmed' | 'rejected') => void;
};

export function StatementEditor({
  statement,
  references,
  index,
  narrative,
  disabled,
  dirty,
  pendingSave,
  canReplaceQuote,
  onChange,
  onRationaleChange,
  onReplaceQuote,
  onDecision,
}: Props) {
  return (
    <fieldset className="parking-statement" disabled={disabled}>
      <legend>
        <span>Утверждение {index + 1}</span>{' '}
        <span className="parking-statement-meta">
          {statement.origin === 'model' ? 'Модель' : 'Ручная правка'}
        </span>{' '}
        <Status
          tone={
            pendingSave
              ? 'warning'
              : statement.decision === 'confirmed'
                ? 'success'
                : statement.decision === 'rejected'
                  ? 'danger'
                  : 'warning'
          }
        >
          {pendingSave
            ? 'изменения не сохранены'
            : { pending: 'не проверено', confirmed: 'подтверждено', rejected: 'отклонено' }[
                statement.decision
              ]}
        </Status>
      </legend>
      <Quote>{statement.quote}</Quote>
      <StatementFields
        value={statement}
        references={references}
        onChange={(patch) => {
          if (patch.stance === '') return;
          onChange(patch as Partial<ReviewStatement>);
        }}
      />
      <Field label="Содержание">
        <Textarea
          rows={2}
          value={statement.valueText}
          onChange={(e) => onChange({ valueText: e.target.value })}
        />
      </Field>
      <Field label="Основание проверки или причина отклонения">
        <Textarea
          rows={2}
          value={statement.rationale}
          onChange={(e) => onRationaleChange(e.target.value)}
        />
      </Field>
      <Actions>
        <Button
          variant="secondary"
          className="parking-replace-quote"
          disabled={!canReplaceQuote}
          onClick={onReplaceQuote}
        >
          Заменить цитату выделенным текстом
        </Button>
        <Button
          variant="secondary"
          disabled={
            dirty ||
            statement.decision === 'confirmed' ||
            !hasStatementChoices(statement) ||
            reviewStatementIssues(statement, narrative).length > 0
          }
          onClick={() => onDecision('confirmed')}
        >
          Подтвердить
        </Button>
        <Button
          variant="secondary"
          disabled={!statement.rationale.trim() || dirty || statement.decision === 'rejected'}
          onClick={() => onDecision('rejected')}
        >
          Отклонить с причиной
        </Button>
      </Actions>
    </fieldset>
  );
}
