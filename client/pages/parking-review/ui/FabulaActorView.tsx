import { useEffect, useRef, useState } from 'react';
import { apiUrl } from '@/shared/api';
import { Actions, Button, Disclosure, Notice, Quote, Status } from '@/shared/ui';
import {
  fabulaSourceSchema,
  type FabulaActorInput,
  type FabulaSource,
  type LegalAssessment,
} from '../model/contracts.js';

/** Source-level role interpretation, deliberately independent of the norm/Lean receipt. */
export function FabulaActorView({
  record,
  stale,
  token,
  onRecorded,
}: {
  record: LegalAssessment;
  stale: boolean;
  token?: string;
  onRecorded?: () => void;
}) {
  const [source, setSource] = useState<FabulaSource>();
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [pending, setPending] = useState<FabulaActorInput>();
  const [refresh, setRefresh] = useState(0);
  const post = useRef<AbortController | undefined>(undefined);
  const recorded = useRef(onRecorded);
  recorded.current = onRecorded;
  const parse = (raw: unknown) => {
    const value = fabulaSourceSchema.parse(raw);
    if (
      value.draftId !== record.input.draftId ||
      value.revisionId !== record.input.expectedRevisionId ||
      value.assessmentId !== record.id ||
      value.sourceDigest !== record.sourceDigest
    )
      throw new Error('Источник не соответствует сохранённому расчёту.');
    return value;
  };
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError('');
    fetch(apiUrl(`/api/parking/fabula/${record.input.draftId}/${record.id}`), {
      signal: AbortSignal.any([controller.signal, AbortSignal.timeout(10000)]),
    })
      .then(async (response) => {
        if (!response.ok) throw new Error('Не удалось загрузить источник и интерпретации.');
        const value = parse(await response.json());
        if (controller.signal.aborted) return;
        setSource(value);
        setPending((previous) =>
          previous && value.decisions.some((decision) => decision.id === previous.requestId)
            ? undefined
            : previous,
        );
      })
      .catch((failure: unknown) => {
        if (!controller.signal.aborted)
          setError(failure instanceof Error ? failure.message : 'Источник недоступен.');
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [record.id, record.input.draftId, refresh]);
  useEffect(() => () => post.current?.abort(), []);

  async function submit(input: FabulaActorInput) {
    if (stale || !token || post.current || loading) return;
    const controller = new AbortController();
    post.current = controller;
    setSending(true);
    setPending(input);
    setError('');
    setNotice('');
    let rejected = false;
    try {
      const response = await fetch(apiUrl('/api/parking/fabula'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-NormLab-Token': token },
        body: JSON.stringify(input),
        signal: AbortSignal.any([controller.signal, AbortSignal.timeout(15000)]),
      });
      const raw: unknown = await response.json().catch(() => null);
      if (!response.ok) {
        rejected = response.status >= 400 && response.status < 500;
        throw new Error(
          typeof raw === 'object' && raw && 'error' in raw && typeof raw.error === 'string'
            ? raw.error
            : 'Не удалось сохранить решение.',
        );
      }
      const value = parse(raw);
      if (!value.decisions.some((decision) => decision.id === input.requestId))
        throw new Error('Сервер не подтвердил запись решения.');
      if (controller.signal.aborted) return;
      setSource(value);
      setPending(undefined);
      setNotice('Решение об акторе сохранено. Расчёт нормы и квитанция Lean не изменены.');
      recorded.current?.();
    } catch (failure) {
      if (!controller.signal.aborted) {
        if (rejected) setPending(undefined);
        setError(failure instanceof Error ? failure.message : 'Ответ сервера не получен.');
      }
    } finally {
      if (post.current === controller) post.current = undefined;
      if (!controller.signal.aborted) setSending(false);
    }
  }

  return (
    <section className="parking-fabula-actor" aria-label="Актор размещения по фабуле">
      <h4>Актор размещения по фабуле</h4>
      <p className="parking-help">
        Кандидат подготовлен по явной фразе проверенного текста. Роль требует отдельного решения
        человека; источник сообщения и выбранный участник не назначаются актором автоматически.
      </p>
      {loading && <p role="status">Загрузка источника и решений об акторе…</p>}
      {source && (
        <>
          <Disclosure summary="Полная исходная фабула этого расчёта">
            <Quote>{source.narrative}</Quote>
          </Disclosure>
          {!source.candidates.length && (
            <Notice tone="neutral">
              Кандидат роли пока не подготовлен. Это не означает, что в тексте нет исполнителя:
              правило распознаёт только явные формы «я, имя, оставил…» и «я припарковал…» в
              подтверждённых утверждениях, связанных с размещением. Проверьте полную фабулу выше.
            </Notice>
          )}
          {source.candidates.map((candidate) => {
            const decision = source.decisions.find((value) => value.candidate.id === candidate.id);
            const status = decision?.input.decision;
            const label = /^[Яя]$/.test(candidate.label) ? 'Рассказчик («я»)' : candidate.label;
            return (
              <div key={candidate.id} className="parking-fabula-candidate">
                <p>
                  <strong>{label}</strong>
                </p>
                <Status
                  tone={
                    status === 'confirmed'
                      ? 'success'
                      : status === 'rejected'
                        ? 'danger'
                        : 'warning'
                  }
                >
                  {status === 'confirmed'
                    ? 'Роль подтверждена человеком'
                    : status === 'rejected'
                      ? 'Кандидат отклонён человеком'
                      : 'Кандидат по тексту · не подтверждён'}
                </Status>
                <Quote>{candidate.quote}</Quote>
                {token && (
                  <Actions>
                    {(['confirmed', 'rejected'] as const).map((choice) => (
                      <Button
                        key={choice}
                        variant="secondary"
                        disabled={stale || loading || sending || !!pending || status === choice}
                        onClick={() =>
                          void submit({
                            requestId: crypto.randomUUID(),
                            draftId: source.draftId,
                            expectedRevisionId: source.revisionId,
                            assessmentId: source.assessmentId,
                            candidateId: candidate.id,
                            expectedDecisionId: source.decisions[0]?.id ?? null,
                            decision: choice,
                          })
                        }
                      >
                        {choice === 'confirmed' ? 'Подтвердить роль актора' : 'Отклонить кандидата'}
                      </Button>
                    ))}
                  </Actions>
                )}
              </div>
            );
          })}
          <p className="parking-help">
            Подтверждение означает принятую человеком интерпретацию сообщения. Юридическая
            ответственность и причинность этим не устанавливаются; Lean эту роль не проверяет.
          </p>
        </>
      )}
      {notice && (
        <Notice tone="success" role="status">
          {notice}
        </Notice>
      )}
      {error && (
        <Notice tone="danger" role="alert">
          {error}
        </Notice>
      )}
      {pending && !sending && (
        <>
          <Notice>
            Сохранение не подтверждено. Обновите список или повторите то же решение с прежним ID.
          </Notice>
          <Button
            variant="secondary"
            disabled={stale || loading}
            onClick={() => void submit(pending)}
          >
            Повторить сохранение с тем же ID
          </Button>
        </>
      )}
      {(error || pending) && (
        <Button
          variant="quiet"
          disabled={loading || sending}
          onClick={() => setRefresh((value) => value + 1)}
        >
          Обновить решения об акторе
        </Button>
      )}
    </section>
  );
}
