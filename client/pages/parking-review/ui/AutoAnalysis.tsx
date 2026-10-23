import { Button, CheckField, Notice } from '@/shared/ui';
import type { AutoAnalysisBlocker } from '../model/auto-analysis.js';

export function AutoAnalysis({
  blocker,
  repeat,
  hasStatements,
  replaceApproved,
  replacementDisabled,
  working,
  staged,
  onReplace,
  onContext,
  onStart,
}: {
  blocker?: AutoAnalysisBlocker;
  repeat: boolean;
  hasStatements: boolean;
  replaceApproved: boolean;
  replacementDisabled: boolean;
  working: boolean;
  staged: boolean;
  onReplace: (approved: boolean) => void;
  onContext: () => void;
  onStart: () => void;
}) {
  return (
    <section className="parking-auto-analysis" aria-labelledby="parking-auto-title">
      <h3 id="parking-auto-title">Автоматический разбор текста</h3>
      <p className="parking-help">
        Подтвердите контекст → запустите разбор → проверьте предложения модели. Модель найдёт цитаты
        и предложит утверждения; вручную выделять текст для запуска не нужно.
      </p>
      <Notice id="parking-auto-readiness" tone={blocker ? 'warning' : 'neutral'} role="status">
        {blocker?.message ?? 'Всё готово. Нажмите кнопку ниже, чтобы получить предложения модели.'}
      </Notice>
      {blocker?.target === 'context' && (
        <Button variant="secondary" onClick={onContext}>
          Перейти к контексту обращения
        </Button>
      )}
      {hasStatements && (
        <CheckField
          checked={replaceApproved}
          disabled={replacementDisabled}
          onChange={(event) => onReplace(event.target.checked)}
        >
          Разрешаю новому авторазбору заменить текущую разметку. Прежняя ревизия останется в
          истории.
        </CheckField>
      )}
      <Button
        disabled={!!blocker}
        aria-describedby="parking-auto-readiness parking-auto-cost"
        onClick={onStart}
      >
        {working
          ? 'Выполняется…'
          : repeat
            ? 'Запустить разбор заново'
            : 'Запустить автоматический разбор'}
      </Button>
      <p className="parking-help" id="parking-auto-cost">
        Запуск отправляет текст модели и может потребовать оплаты.
        {staged
          ? ' При сбое можно продолжить с сохранённых этапов по отдельной кнопке.'
          : ' При сбое можно продолжить разметку вручную.'}
      </p>
    </section>
  );
}
