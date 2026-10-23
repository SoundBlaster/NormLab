import { useEffect, useState } from 'react';
import { apiUrl } from '@/shared/api';
import { Button, Notice, Status } from '@/shared/ui';
import {
  contextProposalSchema,
  type ContextProposal as Proposal,
  type ReviewDraft,
} from '../model/contracts.js';

const topicLabels = {
  parking: 'Парковка',
  other: 'Другая тема',
  unclear: 'Требуется уточнение',
  mixed: 'Несколько разных эпизодов',
};
const parkingLabels = {
  'paid-parking-topic': 'Тема платной парковки',
  'parking-payment-topic': 'Вопрос об оплате парковки',
  'parking-unspecified': 'Парковка без сведений об оплате',
  'not-established': 'Не установлен',
};
const intentLabels = {
  incident: 'Конкретный эпизод',
  information: 'Информация или новость',
  unclear: 'Требуется уточнение',
};

export function ContextProposal({
  draft,
  token,
  blocked,
  onWorking,
  onUse,
}: {
  draft: ReviewDraft;
  token: string;
  blocked: boolean;
  onWorking: (working: boolean) => void;
  onUse: (suggestion: Proposal['suggestion']) => void;
}) {
  const [saved, setSaved] = useState<{ revisionId: string; proposal: Proposal }>();
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');
  const proposal = saved?.revisionId === draft.revisionId ? saved.proposal : undefined;
  useEffect(() => {
    const controller = new AbortController();
    setError('');
    fetch(apiUrl(`/api/parking/context/${draft.draftId}`), {
      signal: AbortSignal.any([controller.signal, AbortSignal.timeout(10000)]),
    })
      .then(async (response) => {
        if (!response.ok) throw new Error('Context unavailable');
        const raw: unknown = await response.json();
        if (!raw) return;
        const value = contextProposalSchema.parse(raw);
        if (value.sourceDigest !== draft.sourceDigest) throw new Error('Source mismatch');
        if (!controller.signal.aborted) setSaved({ revisionId: draft.revisionId, proposal: value });
      })
      .catch(() => {
        if (!controller.signal.aborted)
          setError(
            'Не удалось загрузить сохранённое предложение контекста. Ручной выбор доступен.',
          );
      });
    return () => controller.abort();
  }, [draft.draftId, draft.revisionId, draft.sourceDigest]);
  async function propose() {
    if (blocked || sending) return;
    setSending(true);
    onWorking(true);
    setError('');
    try {
      const response = await fetch(apiUrl('/api/parking/context'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-NormLab-Token': token },
        body: JSON.stringify({ draftId: draft.draftId, expectedRevisionId: draft.revisionId }),
        signal: AbortSignal.timeout(150000),
      });
      const raw = await response.json();
      if (!response.ok) throw new Error(raw.error ?? 'Не удалось получить предложение контекста.');
      const value = contextProposalSchema.parse(raw);
      if (value.sourceDigest !== draft.sourceDigest)
        throw new Error('Предложение относится к другому тексту.');
      setSaved({ revisionId: draft.revisionId, proposal: value });
    } catch (failure) {
      setError(
        failure instanceof Error && failure.name === 'TimeoutError'
          ? 'Ответ не получен вовремя. Запрос мог быть оплачен; автоматического повтора нет. Проверьте журнал или выберите контекст вручную.'
          : failure instanceof Error
            ? failure.message
            : 'Не удалось получить предложение контекста.',
      );
    } finally {
      setSending(false);
      onWorking(false);
    }
  }
  return (
    <section className="parking-auto-analysis" aria-label="Предложение контекста моделью">
      <h3>Определить контекст по тексту</h3>
      <p className="parking-help">
        Модель предложит тему и характер обращения. Затем вы проверите и подтвердите контекст. Этот
        запрос может потребовать оплаты.
      </p>
      <Button disabled={blocked || sending} onClick={() => void propose()}>
        {sending ? 'Модель определяет контекст…' : 'Предложить контекст по тексту'}
      </Button>
      {error && (
        <Notice tone="danger" role="alert">
          {error}
        </Notice>
      )}
      {proposal && (
        <>
          <Status>Предложение модели · требует подтверждения</Status>
          <dl className="parking-journal-details">
            <dt>Тема</dt>
            <dd>{topicLabels[proposal.suggestion.topic]}</dd>
            <dt>Контекст</dt>
            <dd>{parkingLabels[proposal.suggestion.parkingContext]}</dd>
            <dt>Обращение</dt>
            <dd>{intentLabels[proposal.suggestion.intent]}</dd>
          </dl>
          <p>{proposal.suggestion.rationale}</p>
          <p className="parking-help">
            Модель: {proposal.model}. Это предложение о теме текста; обстоятельства события ещё не
            установлены.
          </p>
          <Button
            variant="secondary"
            disabled={blocked || sending}
            onClick={() => onUse(proposal.suggestion)}
          >
            Использовать предложение в форме ниже
          </Button>
        </>
      )}
    </section>
  );
}
