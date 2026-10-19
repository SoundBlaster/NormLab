import { useState } from 'react';
import type { ReviewStatement } from '../model/contracts.js';
import {
  hasStatementChoices,
  type ReviewReferences,
  type StatementFieldsValue,
} from '../model/statement-fields.js';
import { Actions, Button, Field, Notice, Quote, Textarea } from '@/shared/ui';
import { StatementFields } from './StatementFields.js';

export type StatementSource = { quote: string; startOffset: number; endOffset: number };

export function NewStatementEditor({
  source,
  references,
  disabled,
  onCreate,
  onCancel,
}: {
  source: StatementSource;
  references: ReviewReferences;
  disabled: boolean;
  onCreate: (statement: ReviewStatement) => void;
  onCancel: () => void;
}) {
  const [fields, setFields] = useState<StatementFieldsValue>({
    predicate: '',
    stance: '',
    subject: '',
    speaker: undefined,
    aboutEpisode: '',
  });
  const [valueText, setValueText] = useState(source.quote);
  const ready =
    hasStatementChoices(fields) && !!valueText.trim() && valueText.trim().length <= 2048;
  return (
    <fieldset className="parking-statement" disabled={disabled}>
      <legend>Новое утверждение · выбор смысла</legend>
      <Quote>{source.quote}</Quote>
      <Notice>
        Цитата зафиксирована. Выберите обстоятельство, состояние, предмет и эпизод явно. «Выберите…»
        означает, что выбор ещё не сделан; «Неизвестно» — смысл утверждения.
      </Notice>
      <StatementFields
        value={fields}
        references={references}
        onChange={(patch) => setFields((current) => ({ ...current, ...patch }))}
      />
      <Field label="Содержание утверждения">
        <Textarea
          rows={2}
          value={valueText}
          maxLength={2048}
          onChange={(event) => setValueText(event.target.value)}
        />
      </Field>
      <p className="parking-help">
        Неудача попытки оплатить сама по себе не устанавливает отсутствие оплаты вообще. Сохраните
        смысл и участника исходной цитаты. Выбор ссылки не устанавливает водителя, собственника или
        вид ТС.
      </p>
      <Actions>
        <Button
          disabled={!ready}
          onClick={() => {
            if (!ready || fields.stance === '') return;
            onCreate({
              ...fields,
              stance: fields.stance,
              ...source,
              valueText,
              id: crypto.randomUUID(),
              origin: 'human',
              decision: 'pending',
              rationale: '',
            });
          }}
        >
          Добавить к проверке
        </Button>
        <Button variant="secondary" onClick={onCancel}>
          Отменить создание
        </Button>
      </Actions>
    </fieldset>
  );
}
