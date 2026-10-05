import {
  reviewPredicates,
  reviewStatementIssues,
  type ReviewStatement,
} from '../model/contracts.js';
import { Actions, Button, Field, Input, Quote, Select, Status, Textarea } from '@/shared/ui';

const predicateNames: Record<string, string> = {
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

type Props = {
  statement: ReviewStatement;
  index: number;
  narrative: string;
  disabled: boolean;
  dirty: boolean;
  canReplaceQuote: boolean;
  onChange: (patch: Partial<ReviewStatement>) => void;
  onRationaleChange: (value: string) => void;
  onReplaceQuote: () => void;
  onDecision: (decision: 'confirmed' | 'rejected') => void;
};

function StatementFields({ statement, onChange }: Pick<Props, 'statement' | 'onChange'>) {
  return (
    <div className="parking-fields">
      <Field label="Обстоятельство">
        <Select
          value={statement.predicate}
          onChange={(e) => onChange({ predicate: e.target.value })}
        >
          {reviewPredicates.map((p) => (
            <option key={p} value={p}>
              {predicateNames[p.split(':')[1]] ?? p}
            </option>
          ))}
        </Select>
      </Field>
      <Field label="Состояние утверждения">
        <Select
          value={statement.stance}
          onChange={(e) => onChange({ stance: e.target.value as ReviewStatement['stance'] })}
        >
          <option value="asserted">Утверждается</option>
          <option value="denied">Отрицается</option>
          <option value="unknown">Неизвестно</option>
        </Select>
      </Field>
      {(
        [
          ['subject', 'К кому или чему относится'],
          ['speaker', 'Источник утверждения'],
          ['aboutEpisode', 'Эпизод'],
        ] as const
      ).map(([key, label]) => (
        <Field key={key} label={label}>
          <Input
            value={statement[key] ?? ''}
            placeholder={key === 'speaker' ? 'Не указан' : undefined}
            onChange={(e) =>
              onChange({ [key]: key === 'speaker' ? e.target.value || undefined : e.target.value })
            }
          />
        </Field>
      ))}
    </div>
  );
}

export function StatementEditor({
  statement,
  index,
  narrative,
  disabled,
  dirty,
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
            statement.decision === 'confirmed'
              ? 'success'
              : statement.decision === 'rejected'
                ? 'danger'
                : 'warning'
          }
        >
          {
            { pending: 'не проверено', confirmed: 'подтверждено', rejected: 'отклонено' }[
              statement.decision
            ]
          }
        </Status>
      </legend>
      <Quote>{statement.quote}</Quote>
      <StatementFields statement={statement} onChange={onChange} />
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
          disabled={dirty || reviewStatementIssues(statement, narrative).length > 0}
          onClick={() => onDecision('confirmed')}
        >
          Подтвердить
        </Button>
        <Button
          variant="secondary"
          disabled={!statement.rationale.trim() || dirty}
          onClick={() => onDecision('rejected')}
        >
          Отклонить с причиной
        </Button>
      </Actions>
    </fieldset>
  );
}
