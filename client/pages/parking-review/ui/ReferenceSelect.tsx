import { useState } from 'react';
import { Disclosure, Field, Input, Select } from '@/shared/ui';
import type { ReferenceOption } from '../model/statement-fields.js';

type Props = {
  label: string;
  value: string;
  kind: 'subject' | 'speaker' | 'episode';
  options: ReferenceOption[];
  onChange: (value: string) => void;
};

const choices: Record<Props['kind'], ReferenceOption[]> = {
  subject: [{ value: 'Не установлено', label: 'К кому или чему относится — не установлено' }],
  speaker: [{ value: 'Не установлено', label: 'Кто сообщил — не установлено' }],
  episode: [{ value: 'Не установлено', label: 'Эпизод не установлен' }],
};

export function ReferenceSelect({ label, value, kind, options, onChange }: Props) {
  const [custom, setCustom] = useState(false);
  const combined = [...choices[kind], ...options].filter(
    (option, index, all) => all.findIndex((item) => item.value === option.value) === index,
  );
  if (value && !combined.some((option) => option.value === value)) {
    const names = {
      subject: 'Другой объект',
      speaker: 'Другой источник',
      episode: 'Другой эпизод',
    };
    combined.push({ value, label: names[kind] });
  }
  const selected = combined.findIndex((option) => option.value === value);
  return (
    <div className="parking-reference">
      <Field label={label}>
        <Select
          value={custom ? 'custom' : value ? `option:${selected}` : ''}
          onChange={(event) => {
            const next = event.target.value;
            setCustom(next === 'custom');
            onChange(next.startsWith('option:') ? combined[Number(next.slice(7))].value : '');
          }}
        >
          <option value="">{kind === 'speaker' ? 'Не указан в разметке' : 'Выберите…'}</option>
          {combined.map((option, index) => (
            <option key={option.value} value={`option:${index}`}>
              {option.label}
            </option>
          ))}
          <option value="custom">Другая ссылка или описание…</option>
        </Select>
      </Field>
      {custom && (
        <Field label={`${label}: описание или ваша ссылка`}>
          <Input
            value={value}
            maxLength={128}
            placeholder={
              kind === 'episode'
                ? 'Например: остановка у магазина'
                : 'Например: участник, который пытался оплатить'
            }
            onChange={(event) => onChange(event.target.value)}
          />
        </Field>
      )}
      {!!value && (
        <Disclosure summary="Точное значение ссылки">
          <code className="parking-reference-value">{value}</code>
        </Disclosure>
      )}
    </div>
  );
}
