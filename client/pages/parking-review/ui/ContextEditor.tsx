import {
  narrativeContextIssues,
  narrativeRoute,
  type NarrativeContext,
} from '../model/contracts.js';
import { Actions, Button, Disclosure, Field, Select, Status, Textarea } from '@/shared/ui';

const routes = {
  'parking-review': 'Можно перейти к разбору парковочного эпизода.',
  clarify: 'Уточните тему и характер обращения.',
  'other-topic': 'Тема находится за пределами парковочного пилота.',
  'not-a-case': 'Тема определена, но конкретный эпизод не описан.',
  'choose-episode': 'Отделите один эпизод в новый черновик перед разбором.',
};

type Props = {
  context: NarrativeContext;
  disabled: boolean;
  canConfirm: boolean;
  canSave: boolean;
  pendingSave: boolean;
  onChange: (patch: Partial<NarrativeContext>) => void;
  onConfirm: () => void;
  onSave: () => void;
};
export function ContextEditor({
  context,
  disabled,
  canConfirm,
  canSave,
  pendingSave,
  onChange,
  onConfirm,
  onSave,
}: Props) {
  return (
    <fieldset className="parking-context" disabled={disabled}>
      <legend>Классификация вручную</legend>
      <div className="parking-fields">
        <Field label="Тема обращения">
          <Select
            value={context.topic}
            onChange={(e) => {
              const topic = e.target.value as NarrativeContext['topic'];
              onChange({
                topic,
                ...(['other', 'unclear'].includes(topic)
                  ? { parkingContext: 'not-established' as const }
                  : {}),
              });
            }}
          >
            <option value="unclear">Требуется уточнение</option>
            <option value="parking">Парковка</option>
            <option value="other">Другая тема</option>
            <option value="mixed">Несколько разных эпизодов</option>
          </Select>
        </Field>
        <Field label="Парковочный контекст">
          <Select
            value={context.parkingContext}
            disabled={['other', 'unclear'].includes(context.topic)}
            onChange={(e) =>
              onChange({ parkingContext: e.target.value as NarrativeContext['parkingContext'] })
            }
          >
            <option value="not-established">Не установлен</option>
            <option value="parking-unspecified">Парковка без сведений об оплате</option>
            <option value="parking-payment-topic">Вопрос об оплате парковки</option>
            <option value="paid-parking-topic">Тема платной парковки</option>
          </Select>
        </Field>
        <Field label="Характер обращения">
          <Select
            value={context.intent}
            onChange={(e) => onChange({ intent: e.target.value as NarrativeContext['intent'] })}
          >
            <option value="unclear">Требуется уточнение</option>
            <option value="incident">Конкретный эпизод</option>
            <option value="information">Информация или новость</option>
          </Select>
        </Field>
      </div>
      <p className="parking-help">
        {routes[narrativeRoute(context)]} Тема платной парковки сама по себе не подтверждает платный
        режим в эпизоде.
      </p>
      <Disclosure summary="Комментарий к контексту">
        <Field label="Основание классификации">
          <Textarea
            rows={2}
            value={context.rationale}
            onChange={(e) => onChange({ rationale: e.target.value })}
          />
        </Field>
      </Disclosure>
      <Actions>
        <Status tone={!pendingSave && context.decision === 'confirmed' ? 'success' : 'warning'}>
          {pendingSave
            ? 'Изменения не сохранены'
            : context.decision === 'confirmed'
              ? 'Контекст подтверждён'
              : 'Контекст не подтверждён'}
        </Status>
        <Button variant="secondary" disabled={!canSave} onClick={onSave}>
          Сохранить сейчас
        </Button>
        <Button
          variant="secondary"
          disabled={
            !canConfirm ||
            narrativeContextIssues(context).length > 0 ||
            context.decision === 'confirmed'
          }
          onClick={onConfirm}
        >
          Подтвердить контекст
        </Button>
      </Actions>
    </fieldset>
  );
}
