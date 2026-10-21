import { useEffect, useRef, useState } from 'react';
import { apiUrl } from '@/shared/api';
import { Actions, Button, CheckField, Disclosure, Notice, Status } from '@/shared/ui';
import {
  inferenceFailureMessage,
  parkingJobSchema,
  reviewDraftSchema,
  type ParkingJob,
  type ReviewDraft,
} from '../model/contracts.js';

const reasonMessages = {
  failure: 'Проверьте доступ к API или баланс, затем продолжите разбор.',
  restart: 'Сервер перезапускался. Сохранённые этапы доступны; автоматического повтора не было.',
  configuration:
    'Модель или настройки изменились. Для новой конфигурации запустите разбор с начала.',
  revision:
    'Разметка изменена вручную. Для продолжения подтвердите её замену предложениями задания.',
  limit: 'Достигнут лимит времени или попыток. Продолжение не увеличивает общий лимит запросов.',
  'attempt-limit':
    'Лимит попыток этого этапа или задания исчерпан. Для новой серии нужен явный запуск с начала; сохранённая разметка доступна.',
  storage:
    'Не удалось подтвердить сохранность этапов. Продолжение заблокировано до проверки данных.',
};
type Snapshot = { job: unknown; draft: unknown };
export function Job({
  draft,
  token,
  blocked,
  refresh,
  onDraft,
  onRunning,
}: {
  draft: ReviewDraft;
  token: string;
  blocked: boolean;
  refresh: number;
  onDraft: (draft: ReviewDraft) => void;
  onRunning: (running: boolean) => void;
}) {
  const [saved, setSaved] = useState<ParkingJob>();
  const [error, setError] = useState('');
  const [sending, setSending] = useState(false);
  const [acknowledge, setAcknowledge] = useState(false);
  const [replace, setReplace] = useState(false);
  const onDraftRef = useRef(onDraft);
  onDraftRef.current = onDraft;
  const onRunningRef = useRef(onRunning);
  onRunningRef.current = onRunning;
  const job = saved?.draftId === draft.draftId ? saved : undefined;
  const running = job?.status === 'running';
  useEffect(() => {
    setAcknowledge(false);
    setReplace(false);
  }, [job?.jobId, job?.updatedAt]);
  const [reload, setReload] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    let requesting = false;
    const load = async () => {
      if (requesting) return;
      requesting = true;
      try {
        const response = await fetch(apiUrl(`/api/parking/job/${draft.draftId}`), {
          signal: AbortSignal.any([controller.signal, AbortSignal.timeout(10000)]),
        });
        if (!response.ok) throw new Error('Job unavailable');
        const result = (await response.json()) as Snapshot;
        const current = result.job === null ? undefined : parkingJobSchema.parse(result.job);
        const latest = reviewDraftSchema.parse(result.draft);
        if (!controller.signal.aborted) {
          setSaved(current);
          onRunningRef.current(current?.status === 'running');
          setError('');
          onDraftRef.current(latest);
        }
      } catch {
        if (!controller.signal.aborted)
          setError(
            'Не удалось обновить состояние задания. Закрытие вкладки не останавливает сервер; обновите состояние позже.',
          );
      } finally {
        requesting = false;
      }
    };
    void load();
    const timer = running ? window.setInterval(() => void load(), 2000) : undefined;
    return () => {
      controller.abort();
      window.clearInterval(timer);
    };
  }, [draft.draftId, draft.revisionId, running, refresh, reload]);

  async function resume() {
    if (!job || sending) return;
    setSending(true);
    setError('');
    try {
      const response = await fetch(apiUrl('/api/parking/jobs'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-NormLab-Token': token },
        body: JSON.stringify({
          draftId: draft.draftId,
          expectedRevisionId: draft.revisionId,
          jobId: job.jobId,
          acknowledgeUnknown: acknowledge,
          replaceStatements: replace,
        }),
        signal: AbortSignal.timeout(15000),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error ?? 'Не удалось продолжить разбор.');
      setSaved(parkingJobSchema.parse(result));
      setAcknowledge(false);
      setReplace(false);
    } catch (failure) {
      setError(
        failure instanceof Error
          ? failure.message
          : 'Продолжение не подтверждено. Обновите состояние перед повтором.',
      );
    } finally {
      setSending(false);
      setReload((n) => n + 1);
    }
  }
  const revisionConflict = !!job && job.revisionId !== draft.revisionId;
  return (
    <section className="parking-job" aria-label="Состояние авторазбора">
      {error && (
        <Notice tone="warning" role="alert">
          {error}
        </Notice>
      )}
      {job && (
        <>
          <Status tone={running ? 'neutral' : job.status === 'completed' ? 'success' : 'warning'}>
            {running
              ? 'Разбор выполняется'
              : job.status === 'completed'
                ? 'Этапы завершены · нужна проверка человеком'
                : 'Разбор приостановлен'}
          </Status>
          <p role="status" aria-live="polite">
            Цитат: {job.fragments.length} · Batch классификации: {job.completedBatches}/
            {job.totalBatches} · Попыток: {job.attempts}/99.
          </p>
          {job.profile && (
            <p className="parking-help">
              Discovery: {job.profile.discoveryModel}. Классификация:{' '}
              {job.profile.classificationModel}.
            </p>
          )}
          {running && (
            <p className="parking-help">
              Можно закрыть вкладку: сервер продолжит работу в пределах лимитов. Сохранённые
              предложения ниже ещё не проверены.
            </p>
          )}
          {job.failure && <Notice tone="danger">{inferenceFailureMessage(job.failure)}</Notice>}
          {job.reason && <Notice tone="warning">{reasonMessages[job.reason]}</Notice>}
          {job.status !== 'completed' && job.fragments.length > 0 && (
            <Notice tone="warning">
              Частичный разбор. Не все найденные цитаты классифицированы; отсутствие предложения
              пока не означает отсутствие обстоятельства.
            </Notice>
          )}
          {job.fragments.length > 0 && (
            <Disclosure summary={`Найденные дословные цитаты · ${job.fragments.length}`}>
              <ol className="parking-job-fragments">
                {job.fragments.map((fragment) => (
                  <li key={fragment.fragmentId}>
                    <blockquote>{fragment.quote}</blockquote>
                    <small>
                      {fragment.fragmentId} · {fragment.attributes.subject} ·{' '}
                      {fragment.attributes.aboutEpisode}
                    </small>
                  </li>
                ))}
              </ol>
            </Disclosure>
          )}
          {job.status !== 'running' && job.status !== 'completed' && (
            <>
              {job.unknowns > 0 && (
                <CheckField
                  checked={acknowledge}
                  onChange={(e) => setAcknowledge(e.target.checked)}
                >
                  Исход {job.unknowns} попыток неизвестен: запросы могли быть оплачены. Разрешаю
                  повтор недостающего этапа с возможной повторной оплатой.
                </CheckField>
              )}
              {revisionConflict && (
                <CheckField checked={replace} onChange={(e) => setReplace(e.target.checked)}>
                  Разрешаю заменить текущую разметку предложениями задания. Ручная ревизия
                  сохранится в истории.
                </CheckField>
              )}
              <Button
                disabled={
                  blocked ||
                  sending ||
                  job.reason === 'configuration' ||
                  job.reason === 'storage' ||
                  job.reason === 'attempt-limit' ||
                  (job.unknowns > 0 && !acknowledge) ||
                  (revisionConflict && !replace)
                }
                onClick={() => void resume()}
              >
                {sending ? 'Запускаем продолжение…' : 'Продолжить с сохранённых этапов'}
              </Button>
            </>
          )}
        </>
      )}
      <Actions>
        <Button variant="secondary" disabled={sending} onClick={() => setReload((n) => n + 1)}>
          Обновить состояние авторазбора
        </Button>
      </Actions>
    </section>
  );
}
