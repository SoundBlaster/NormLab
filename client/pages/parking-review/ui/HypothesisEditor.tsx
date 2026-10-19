import { type VehicleHypothesis, vehicleHypothesisIssues } from '../model/contracts.js';
import {
  Actions,
  Button,
  Field,
  Input,
  Notice,
  Quote,
  Select,
  Status,
  Textarea,
} from '@/shared/ui';

import type { ReviewReferences } from '../model/statement-fields.js';
import { ReferenceSelect } from './ReferenceSelect.js';

type Props = {
  hypothesis: VehicleHypothesis;
  references: ReviewReferences;
  narrative: string;
  disabled: boolean;
  dirty: boolean;
  pendingSave: boolean;
  canReplaceQuote: boolean;
  onChange: (patch: Partial<VehicleHypothesis>) => void;
  onDecision: (decision: 'confirmed' | 'rejected') => void;
  onReplaceQuote: () => void;
};
export function HypothesisEditor({
  hypothesis,
  references,
  narrative,
  disabled,
  dirty,
  pendingSave,
  canReplaceQuote,
  onChange,
  onDecision,
  onReplaceQuote,
}: Props) {
  return (
    <fieldset className="parking-statement" disabled={disabled}>
      <legend>
        Гипотеза о транспортном средстве{' '}
        <Status
          tone={
            pendingSave
              ? 'warning'
              : hypothesis.decision === 'confirmed'
                ? 'success'
                : hypothesis.decision === 'rejected'
                  ? 'neutral'
                  : 'warning'
          }
        >
          {pendingSave
            ? 'изменения не сохранены'
            : { pending: 'не проверена', confirmed: 'подтверждена', rejected: 'отклонена' }[
                hypothesis.decision
              ]}
        </Status>
      </legend>
      <p>
        В этом эпизоде речь о транспортном средстве. Это отдельная гипотеза, а не утверждение из
        цитаты.
      </p>
      <Quote>{hypothesis.quote}</Quote>
      <div className="parking-fields">
        <Field label="Вид транспортного средства">
          <Select
            value={hypothesis.vehicleKind}
            onChange={(e) =>
              onChange({ vehicleKind: e.target.value as VehicleHypothesis['vehicleKind'] })
            }
          >
            <option value="unspecified">Не установлен</option>
            <option value="car">Автомобиль</option>
            <option value="motorcycle">Мотоцикл</option>
            <option value="bicycle">Велосипед</option>
            <option value="other">Другое транспортное средство</option>
          </Select>
        </Field>
        <ReferenceSelect
          label="Эпизод гипотезы"
          kind="episode"
          value={hypothesis.aboutEpisode}
          options={references.episodes}
          onChange={(aboutEpisode) => onChange({ aboutEpisode })}
        />
      </div>
      {hypothesis.vehicleKind === 'other' && (
        <Field label="Уточнение вида ТС">
          <Input
            value={hypothesis.vehicleKindDetails}
            onChange={(e) => onChange({ vehicleKindDetails: e.target.value })}
          />
        </Field>
      )}
      {hypothesis.decision !== 'rejected' && hypothesis.vehicleKind === 'unspecified' && (
        <Notice tone="warning">
          Вид ТС не установлен. Уточните его перед завершением проверки. Автомобильные условия не
          применяются автоматически.
        </Notice>
      )}
      <Field label="Основание гипотезы или причина отклонения">
        <Textarea
          rows={2}
          value={hypothesis.rationale}
          onChange={(e) => onChange({ rationale: e.target.value })}
        />
      </Field>
      <Actions>
        <Button variant="secondary" disabled={!canReplaceQuote} onClick={onReplaceQuote}>
          Заменить основание выделенной цитатой
        </Button>
        <Button
          variant="secondary"
          disabled={
            dirty ||
            !hypothesis.aboutEpisode.trim() ||
            vehicleHypothesisIssues({ ...hypothesis, decision: 'confirmed' }, narrative).length > 0
          }
          onClick={() => onDecision('confirmed')}
        >
          Подтвердить гипотезу
        </Button>
        <Button
          variant="secondary"
          disabled={dirty || !hypothesis.rationale.trim()}
          onClick={() => onDecision('rejected')}
        >
          Отклонить гипотезу с причиной
        </Button>
      </Actions>
    </fieldset>
  );
}
