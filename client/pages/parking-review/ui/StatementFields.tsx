import { reviewPredicates } from '../model/contracts.js';
import {
  predicateNames,
  type ReviewReferences,
  type StatementFieldsValue,
} from '../model/statement-fields.js';
import { Field, Select } from '@/shared/ui';
import { ReferenceSelect } from './ReferenceSelect.js';

export function StatementFields({
  value,
  references,
  onChange,
}: {
  value: StatementFieldsValue;
  references: ReviewReferences;
  onChange: (patch: Partial<StatementFieldsValue>) => void;
}) {
  return (
    <div className="parking-fields">
      <Field label="Обстоятельство">
        <Select value={value.predicate} onChange={(e) => onChange({ predicate: e.target.value })}>
          <option value="" disabled={value.predicate !== ''}>
            Выберите обстоятельство…
          </option>
          {reviewPredicates.map((predicate) => (
            <option key={predicate} value={predicate}>
              {predicateNames[predicate.split(':')[1]] ?? predicate}
            </option>
          ))}
        </Select>
      </Field>
      <Field label="Состояние утверждения">
        <Select
          value={value.stance}
          onChange={(e) => onChange({ stance: e.target.value as StatementFieldsValue['stance'] })}
        >
          <option value="" disabled={value.stance !== ''}>
            Выберите состояние…
          </option>
          <option value="asserted">Утверждается</option>
          <option value="denied">Отрицается</option>
          <option value="unknown">Неизвестно · явная неопределённость</option>
        </Select>
      </Field>
      <ReferenceSelect
        label="К кому или чему относится"
        kind="subject"
        value={value.subject}
        options={references.subjects}
        onChange={(subject) => onChange({ subject })}
      />
      <ReferenceSelect
        label="Кто сообщил"
        kind="speaker"
        value={value.speaker ?? ''}
        options={references.speakers}
        onChange={(speaker) => onChange({ speaker: speaker || undefined })}
      />
      <ReferenceSelect
        label="Эпизод"
        kind="episode"
        value={value.aboutEpisode}
        options={references.episodes}
        onChange={(aboutEpisode) => onChange({ aboutEpisode })}
      />
    </div>
  );
}
