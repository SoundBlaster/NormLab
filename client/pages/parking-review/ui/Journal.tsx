import { useEffect, useState } from 'react';
import { apiUrl } from '@/shared/api';
import { Button, Disclosure, Notice, Panel, SectionHeading, Status } from '@/shared/ui';
import {
  inferenceFailureMessage,
  parkingJournalSchema,
  type ParkingJournal,
  type ParkingJournalEvent,
} from '../model/contracts.js';

export function journalMessage(event: ParkingJournalEvent): string {
  switch (event.kind) {
    case 'actor-interpretation':
      return event.decision === 'confirmed'
        ? 'Подтверждена роль актора по фабуле. Расчёт нормы не изменён.'
        : 'Отклонён кандидат актора по фабуле. Расчёт нормы не изменён.';
    case 'legal-proposal': {
      const labels = {
        started: 'Запрошены кандидаты юридических обстоятельств.',
        running: 'Модель связывает проверенные утверждения с условиями нормы.',
        completed: 'Кандидаты подготовлены. Каждое решение требует одобрения человеком.',
        conflict: 'Разбор или решения изменились во время запроса. Кандидаты не применены.',
        interrupted:
          'Подготовка кандидатов не завершена. Возможна оплата без ответа; автоматического повтора нет.',
        failed: 'Не удалось подготовить кандидатов. Можно заполнить обстоятельства вручную.',
      };
      return (
        labels[event.action] + (event.failure ? ` ${inferenceFailureMessage(event.failure)}` : '')
      );
    }
    case 'context-proposal': {
      const labels = {
        started: 'Запрошено предложение контекста по тексту.',
        running: 'Модель определяет тему и характер обращения.',
        completed: 'Получено предложение контекста. Требуется подтверждение человеком.',
        conflict: 'Контекст или разметка изменились во время запроса. Предложение не применено.',
        interrupted:
          'Нет подтверждённого завершения определения контекста. Возможна оплата без ответа; автоматического повтора нет.',
        failed: 'Не удалось получить предложение контекста. Можно выбрать его вручную.',
      };
      return (
        labels[event.action] + (event.failure ? ` ${inferenceFailureMessage(event.failure)}` : '')
      );
    }
    case 'legal-assessment':
      return event.action === 'calculated'
        ? 'Сохранены юридические обстоятельства и draft-расчёт фрагмента нормы. Ответственность не установлена.'
        : 'Сохранены отдельные решения человека по юридическим обстоятельствам.';
    case 'job-progress': {
      const labels = {
        started: 'Запущен поэтапный разбор.',
        resumed: 'Разбор продолжен с сохранённых этапов.',
        checkpoint: 'Результат этапа сохранён.',
        paused: 'Разбор приостановлен. Продолжение — по кнопке.',
        conflict: 'Обнаружены ручные правки. Предложения не заменили новую ревизию.',
        completed: 'Все этапы завершены. Предложения требуют проверки человеком.',
      };
      return `${labels[event.action]} Сохранено batch: ${event.completedBatches}.${event.unknowns ? ` Исход ${event.unknowns} попыток неизвестен; возможна оплата без полученного ответа.` : ''}${event.failure ? ` ${inferenceFailureMessage(event.failure)}` : ''}`;
    }
    case 'draft-created':
      return 'Текст сохранён в черновике. Модель ещё не запускалась.';
    case 'review-saved':
      return 'Сохранены изменения разметки или решения проверяющего.';
    case 'review-completed':
      return 'Завершена проверка человеком.';
    case 'model-applied':
      return 'Предложения модели сохранены в новой ревизии. Требуется ручная проверка.';
    case 'extraction-started':
      return 'Запущен полный автоматический разбор.';
    case 'extraction-running':
      return 'Разбор выполняется на сервере.';
    case 'extraction-completed':
      return `Разбор завершён: ${event.statementCount} предложений для проверки.`;
    case 'extraction-conflict':
      return 'Черновик изменился во время разбора. Ответ модели не заменил ваши правки.';
    case 'extraction-interrupted':
      return 'Нет подтверждённой записи о завершении запуска. Он мог выполнить запросы и списать средства; автоматического повтора не будет.';
    case 'extraction-failed':
      return `${inferenceFailureMessage(event.failure)} Прежняя ревизия доступна для ручной работы.`;
  }
}

export function Journal({
  draftId,
  revisionId,
  busy,
}: {
  draftId: string;
  revisionId: string;
  busy: boolean;
}) {
  const [saved, setSaved] = useState<{ draftId: string; journal: ParkingJournal }>();
  const [error, setError] = useState('');
  const [refresh, setRefresh] = useState(0);
  const [loading, setLoading] = useState(false);
  const journal = saved?.draftId === draftId ? saved.journal : undefined;
  const running =
    journal?.events.some(
      (event) =>
        event.kind === 'extraction-running' ||
        (['context-proposal', 'legal-proposal'].includes(event.kind) &&
          'action' in event &&
          event.action === 'running'),
    ) ?? false;
  useEffect(() => {
    const controller = new AbortController();
    let requesting = false;
    const load = async () => {
      if (requesting) return;
      requesting = true;
      setLoading(true);
      try {
        const response = await fetch(apiUrl(`/api/parking/journal/${draftId}`), {
          signal: AbortSignal.any([controller.signal, AbortSignal.timeout(10_000)]),
        });
        if (!response.ok) throw new Error('Journal unavailable');
        const result = parkingJournalSchema.parse(await response.json());
        if (!controller.signal.aborted) {
          setSaved({ draftId, journal: result });
          setError('');
        }
      } catch {
        if (!controller.signal.aborted)
          setError(
            'Журнал временно недоступен. Сохранённая разметка остаётся доступна; обновите журнал позже.',
          );
      } finally {
        requesting = false;
        if (!controller.signal.aborted) setLoading(false);
      }
    };
    void load();
    const timer = busy || running ? window.setInterval(() => void load(), 5000) : undefined;
    return () => {
      controller.abort();
      window.clearInterval(timer);
    };
  }, [draftId, revisionId, busy, running, refresh]);

  return (
    <Panel aria-label="Журнал действий и ошибок">
      <SectionHeading
        step="07"
        title="Журнал действий и ошибок"
        description="Запуски, изменения разметки и сбои сохраняются вместе с разбором."
      />
      <Button variant="secondary" disabled={loading} onClick={() => setRefresh((n) => n + 1)}>
        {loading ? 'Загрузка журнала…' : 'Обновить журнал'}
      </Button>
      {error && (
        <Notice tone="warning" role="alert">
          {error}
        </Notice>
      )}
      {journal && (
        <>
          <p className="parking-help" role="status">
            {journal.total > journal.events.length
              ? `Показаны последние ${journal.events.length} из ${journal.total} событий. Полная история хранится на сервере.`
              : `Событий: ${journal.total}. Новые записи сверху.`}
          </p>
          <ol className="parking-journal">
            {journal.events.map((event) => (
              <li key={event.id}>
                <time dateTime={event.at}>{new Date(event.at).toLocaleString('ru-RU')}</time>
                <div>
                  {event.runId && <Status>Запуск {event.runId.slice(0, 8)}</Status>}
                  <p>{journalMessage(event)}</p>
                  {event.kind === 'extraction-failed' &&
                    ['network', 'timeout', 'unavailable'].includes(event.failure.code) && (
                      <Notice tone="warning">
                        Ответ не получен. Запрос мог быть обработан и оплачен. Новый запуск повторит
                        все этапы.
                      </Notice>
                    )}
                  <Disclosure summary="Технические сведения">
                    <dl className="parking-journal-details">
                      <dt>Ревизия</dt>
                      <dd>{event.revision ?? event.revisionId}</dd>
                      {event.runId && (
                        <>
                          <dt>Запуск</dt>
                          <dd>{event.runId}</dd>
                        </>
                      )}
                      {'durationMs' in event && event.durationMs !== undefined && (
                        <>
                          <dt>Длительность</dt>
                          <dd>{(event.durationMs / 1000).toFixed(1)} с</dd>
                        </>
                      )}
                      {'statementCount' in event && (
                        <>
                          <dt>Утверждения</dt>
                          <dd>{event.statementCount}</dd>
                        </>
                      )}
                      {'confirmed' in event && (
                        <>
                          <dt>Подтверждено / отклонено</dt>
                          <dd>
                            {event.confirmed} / {event.rejected}
                          </dd>
                        </>
                      )}
                      {event.kind === 'extraction-failed' && (
                        <>
                          <dt>API / этап</dt>
                          <dd>
                            {event.failure.provider} / {event.failure.stage}
                          </dd>
                          <dt>Причина</dt>
                          <dd>
                            {event.failure.code}
                            {event.failure.httpStatus ? ` · HTTP ${event.failure.httpStatus}` : ''}
                          </dd>
                        </>
                      )}
                    </dl>
                  </Disclosure>
                </div>
              </li>
            ))}
          </ol>
        </>
      )}
    </Panel>
  );
}
