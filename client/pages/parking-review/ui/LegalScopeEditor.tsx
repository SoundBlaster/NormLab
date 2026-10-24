import { Fragment } from 'react';
import { Field, Input, Notice, Select } from '@/shared/ui';
import type { LegalInput } from '../model/contracts.js';
import { legalFieldId, type LegalValidationIssue } from '../model/legal-validation.js';
export type LegalCoordinates = Pick<
  LegalInput,
  'episode' | 'vehicle' | 'participant' | 'eventDate' | 'location' | 'timeInterval'
>;

export function LegalScopeEditor({
  coordinates,
  episodes,
  claimedFine,
  disabled,
  issues = [],
  onChange,
  onFineChange,
}: {
  coordinates: LegalCoordinates;
  episodes: string[];
  claimedFine: string;
  disabled: boolean;
  issues?: LegalValidationIssue[];
  onChange: (next: LegalCoordinates) => void;
  onFineChange: (next: string) => void;
}) {
  const fieldError = (key: string) =>
    issues
      .filter((issue) => issue.key === key)
      .map((issue) => issue.message)
      .join(' ');
  const episodeError = fieldError('episode');
  const fineError = fieldError('claimedFine');
  return (
    <fieldset className="parking-legal-fields" disabled={disabled}>
      <legend>Один эпизод, участник и ТС</legend>
      <Field label="Эпизод — обязательно">
        <Select
          id={legalFieldId('episode')}
          value={coordinates.episode}
          aria-required="true"
          aria-invalid={!!episodeError}
          aria-describedby={episodeError ? `${legalFieldId('episode')}-error` : undefined}
          onChange={(e) => onChange({ ...coordinates, episode: e.target.value })}
        >
          <option value="">Выберите эпизод</option>
          {episodes.map((episode, index) => (
            <option key={episode} value={episode}>
              Эпизод {index + 1} · {episode}
            </option>
          ))}
        </Select>
      </Field>
      {episodeError && (
        <Notice tone="danger" id={`${legalFieldId('episode')}-error`}>
          {episodeError}
        </Notice>
      )}
      <p className="parking-help">
        Если участник, ТС, место, дата или интервал неизвестны, оставьте соответствующее поле
        пустым. Расчёт отметит эти сведения как пробелы.
      </p>
      {(['participant', 'vehicle', 'location', 'eventDate', 'timeInterval'] as const).map((key) => (
        <Fragment key={key}>
          <Field
            label={
              {
                participant: 'К какому участнику относятся решения',
                vehicle: 'Выбранное транспортное средство',
                location: 'Место события',
                eventDate: 'Дата события',
                timeInterval: 'Интервал размещения ТС',
              }[key]
            }
          >
            <Input
              id={legalFieldId(key)}
              type={key === 'eventDate' ? 'date' : 'text'}
              value={coordinates[key]}
              maxLength={['location', 'timeInterval'].includes(key) ? 512 : 256}
              aria-invalid={!!fieldError(key)}
              aria-describedby={fieldError(key) ? `${legalFieldId(key)}-error` : undefined}
              onChange={(e) => onChange({ ...coordinates, [key]: e.target.value })}
            />
          </Field>
          {fieldError(key) && (
            <Notice tone="danger" id={`${legalFieldId(key)}-error`}>
              {fieldError(key)}
            </Notice>
          )}
        </Fragment>
      ))}
      <Field label="Упомянутый штраф, ₽ — необязательно">
        <Input
          id={legalFieldId('claimedFine')}
          type="number"
          min={0}
          max={1000000}
          step={1}
          value={claimedFine}
          aria-invalid={!!fineError}
          aria-describedby={fineError ? `${legalFieldId('claimedFine')}-error` : undefined}
          onChange={(e) => onFineChange(e.target.value)}
        />
      </Field>
      {fineError && (
        <Notice tone="danger" id={`${legalFieldId('claimedFine')}-error`}>
          {fineError}
        </Notice>
      )}
    </fieldset>
  );
}
