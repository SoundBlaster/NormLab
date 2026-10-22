import { Field, Input, Select } from '@/shared/ui';
import type { LegalInput } from '../model/contracts.js';
export type LegalCoordinates = Pick<
  LegalInput,
  'episode' | 'vehicle' | 'participant' | 'eventDate' | 'location' | 'timeInterval'
>;

export function LegalScopeEditor({
  coordinates,
  episodes,
  claimedFine,
  disabled,
  onChange,
  onFineChange,
}: {
  coordinates: LegalCoordinates;
  episodes: string[];
  claimedFine: string;
  disabled: boolean;
  onChange: (next: LegalCoordinates) => void;
  onFineChange: (next: string) => void;
}) {
  return (
    <fieldset className="parking-legal-fields" disabled={disabled}>
      <legend>Один эпизод, участник и ТС</legend>
      <Field label="Эпизод">
        <Select
          value={coordinates.episode}
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
      {(['participant', 'vehicle', 'location', 'eventDate', 'timeInterval'] as const).map((key) => (
        <Field
          key={key}
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
            type={key === 'eventDate' ? 'date' : 'text'}
            value={coordinates[key]}
            maxLength={['location', 'timeInterval'].includes(key) ? 512 : 256}
            onChange={(e) => onChange({ ...coordinates, [key]: e.target.value })}
          />
        </Field>
      ))}
      <Field label="Упомянутый штраф, ₽ — необязательно">
        <Input
          type="number"
          min={0}
          max={1000000}
          step={1}
          value={claimedFine}
          onChange={(e) => onFineChange(e.target.value)}
        />
      </Field>
    </fieldset>
  );
}
