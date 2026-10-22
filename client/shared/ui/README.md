# NormLab UI

Общая основа форм и рабочих панелей. Используется парковочным review и A/B/C.

- `tokens.css` — semantic colors, spacing scale, typography sizes, radii, control heights, motion и ширина формы.
- `components.tsx` — небольшие React primitives с обычными HTML props. React 19 `ref` передаётся в native control.
- `ui.css` — единые normal, hover, focus, disabled, read-only, mobile и reduced-motion состояния.

`Logo` — SVG wordmark с `alt="NormLab"`; исходная формула и воспроизведение находятся в `design/branding`.

## Компоненты

| Компонент                     | Назначение                                                                     |
| ----------------------------- | ------------------------------------------------------------------------------ |
| `Panel`, `SectionHeading`     | Панель, заголовок и необязательный номер этапа                                 |
| `Field`                       | Подпись и native control внутри семантического label                           |
| `Input`, `Select`, `Textarea` | Контролируемые поля; value, события, ref и aria props передаются без изменения |
| `CheckField`                  | Checkbox с подписью и стандартными размерами                                   |
| `Button`                      | primary, secondary, quiet, success; type=button по умолчанию                   |
| `Status`                      | neutral, success, warning, danger; цвет дополняет текст статуса                |
| `Actions`, `Quote`            | Группа действий и цитата источника                                             |
| `Notice`, `Disclosure`        | Сообщение с тоном и раскрываемый блок с общей индикацией состояния             |

```tsx
import { Actions, Button, Field, Panel, SectionHeading, Select } from '@/shared/ui';

<Panel>
  <SectionHeading step="01" title="Уточнение обстоятельства" />
  <Field label="Состояние">
    <Select value={state} onChange={(event) => setState(event.target.value)}>
      <option value="unknown">Неизвестно</option>
      <option value="asserted">Утверждается</option>
    </Select>
  </Field>
  <Actions>
    <Button variant="secondary" onClick={save}>
      Сохранить
    </Button>
  </Actions>
</Panel>;
```

## Правила развития

1. Новые формы собираются из primitives. Цвета, размеры control и общие отступы берутся из токенов. Не копировать базовые button/input/label стили в CSS экрана.
2. CSS экрана задаёт domain layout: колонки, порядок секций, расположение специфических действий. Размеры breakpoint и особенности диаграмм могут оставаться локальными.
3. Бизнес-решения, сохранение, инвалидация и модельные вызовы живут в screen/domain layer. Primitives не знают о parking или Lean.
4. Повторяющуюся domain композицию выделять отдельно, когда есть понятная ответственность. Пример: `pages/parking-review/ui/StatementEditor.tsx` отделяет редактор одного утверждения от состояния всего review.
5. Новый variant добавляется в общий компонент и его CSS. Проверять оба потребителя, desktop и узкую ширину, focus, disabled/read-only и отсутствие horizontal overflow.

В `ui.css` пока есть compatibility selectors для `.lab-panel`, `.lab label`, `.lab select`, `.lab textarea`, `.lab .primary/.secondary`, `.lab summary`: они дают оставшимся native элементам Views/Transfer ту же основу. Главная форма A/B/C уже использует React primitives. M0 и специфические таблицы/визуализации сохраняют legacy CSS; их дальнейшая миграция выполняется отдельными изменениями.
