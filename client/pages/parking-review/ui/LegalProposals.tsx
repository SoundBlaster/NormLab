import { Fragment, useEffect, useRef, useState } from 'react';
import { apiUrl } from '@/shared/api';
import { Actions, Button, Disclosure, Notice, Quote, Status } from '@/shared/ui';
import {
  legalCoordinateKeys,
  savedLegalProposalSchema,
  type ReviewDraft,
  type ReviewStatement,
  type SavedLegalProposal,
} from '../model/contracts.js';

const coordinateLabels = {
  participant: 'Участник',
  vehicle: 'Транспортное средство',
  location: 'Место события',
  eventDate: 'Дата события',
  timeInterval: 'Интервал размещения ТС',
};

export function LegalProposals({
  draft,
  token,
  episode,
  expectedAssessmentId,
  packageDigest,
  disabled,
  statements,
  coordinateProposalId,
  onAcceptCoordinates,
  onProposal,
  onWorking,
  onRecorded,
}: {
  draft: ReviewDraft;
  token: string;
  episode: string;
  expectedAssessmentId: string | null;
  packageDigest: string;
  disabled: boolean;
  statements: ReviewStatement[];
  coordinateProposalId: string | undefined;
  onAcceptCoordinates: (proposal: SavedLegalProposal) => void;
  onProposal: (proposal: SavedLegalProposal | undefined) => void;
  onWorking: (working: boolean) => void;
  onRecorded: () => void;
}) {
  const scope = JSON.stringify([
    draft.draftId,
    draft.revisionId,
    draft.sourceDigest,
    packageDigest,
    episode,
  ]);
  const currentScope = useRef(scope);
  currentScope.current = scope;
  const callbacks = useRef({ onProposal, onWorking, onRecorded });
  callbacks.current = { onProposal, onWorking, onRecorded };
  const post = useRef<{ scope: string; controller: AbortController } | undefined>(undefined);
  const [saved, setSaved] = useState<{ scope: string; proposal: SavedLegalProposal }>();
  const [available, setAvailable] = useState<boolean>();
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');
  const [unknownOutcome, setUnknownOutcome] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const proposal = saved?.scope === scope ? saved.proposal : undefined;
  const accepted = !!proposal && coordinateProposalId === proposal.proposalId;
  const statementIds = new Set(statements.map((statement) => statement.id));
  const matches = (value: SavedLegalProposal) =>
    value.draftId === draft.draftId &&
    value.revisionId === draft.revisionId &&
    value.sourceDigest === draft.sourceDigest &&
    value.packageDigest === packageDigest &&
    value.episode === episode &&
    [...Object.values(value.suggestion.coordinates), ...value.suggestion.findings].every((item) =>
      item.statementIds.every((id) => statementIds.has(id)),
    );

  useEffect(() => {
    setSaved(undefined);
    setAvailable(undefined);
    setSending(false);
    setError('');
    setUnknownOutcome(false);
    callbacks.current.onProposal(undefined);
    return () => {
      if (post.current?.scope === scope) {
        post.current.controller.abort();
        post.current = undefined;
        callbacks.current.onWorking(false);
      }
    };
  }, [scope]);

  useEffect(() => {
    if (!episode) {
      setLoading(false);
      return;
    }
    const controller = new AbortController();
    setLoading(true);
    setError('');
    fetch(apiUrl(`/api/parking/legal-proposals/${draft.draftId}`), {
      signal: AbortSignal.any([controller.signal, AbortSignal.timeout(10000)]),
    })
      .then(async (response) => {
        if (!response.ok) throw new Error('Не удалось загрузить сохранённые предложения.');
        const raw: unknown = await response.json();
        if (
          typeof raw !== 'object' ||
          raw === null ||
          !('available' in raw) ||
          typeof raw.available !== 'boolean' ||
          !('proposals' in raw)
        )
          throw new Error('Сервер вернул неподдерживаемый список предложений.');
        const values = savedLegalProposalSchema.array().parse(raw.proposals);
        if (controller.signal.aborted || currentScope.current !== scope) return;
        // The endpoint returns completed proposals newest first.
        const newest = values.find(matches);
        setAvailable(raw.available);
        setSaved(newest ? { scope, proposal: newest } : undefined);
        callbacks.current.onProposal(newest);
      })
      .catch(() => {
        if (!controller.signal.aborted && currentScope.current === scope)
          setError(
            'Не удалось загрузить сохранённые предложения. Обстоятельства можно заполнить вручную.',
          );
      })
      .finally(() => {
        if (!controller.signal.aborted && currentScope.current === scope) setLoading(false);
      });
    return () => controller.abort();
  }, [scope, refresh]);

  async function propose() {
    if (disabled || loading || post.current || !episode || available !== true) return;
    const controller = new AbortController();
    post.current = { scope, controller };
    setSending(true);
    setError('');
    callbacks.current.onWorking(true);
    let knownRejection = false;
    let serverError: string | undefined;
    try {
      const response = await fetch(apiUrl('/api/parking/legal-proposals'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-NormLab-Token': token },
        body: JSON.stringify({
          draftId: draft.draftId,
          expectedRevisionId: draft.revisionId,
          expectedAssessmentId,
          episode,
        }),
        signal: AbortSignal.any([controller.signal, AbortSignal.timeout(150000)]),
      });
      const raw: unknown = await response.json().catch(() => null);
      if (!response.ok) {
        knownRejection = response.status >= 400 && response.status < 500;
        serverError =
          typeof raw === 'object' && raw !== null && 'error' in raw && typeof raw.error === 'string'
            ? raw.error
            : `Не удалось получить предложение (HTTP ${response.status}).`;
        throw new Error(serverError);
      }
      const value = savedLegalProposalSchema.parse(raw);
      if (!matches(value))
        throw new Error('Предложение не соответствует текущему эпизоду и источникам.');
      if (controller.signal.aborted || currentScope.current !== scope) return;
      setSaved({ scope, proposal: value });
      setUnknownOutcome(false);
      callbacks.current.onProposal(value);
    } catch {
      if (!controller.signal.aborted && currentScope.current === scope) {
        if (!knownRejection) setUnknownOutcome(true);
        setError(
          serverError
            ? `${serverError} Обстоятельства можно заполнить вручную.`
            : 'Получение предложения не подтверждено. Запрос мог быть оплачен и сохранён. Обновите список сохранённых предложений или заполните обстоятельства вручную.',
        );
      }
    } finally {
      if (post.current?.controller === controller) {
        post.current = undefined;
        if (!controller.signal.aborted && currentScope.current === scope) {
          setSending(false);
          callbacks.current.onWorking(false);
          callbacks.current.onRecorded();
        }
      }
    }
  }

  return (
    <section className="parking-auto-analysis" aria-label="Предложения юридических обстоятельств">
      <h3>Предложить обстоятельства по проверенному тексту</h3>
      <p className="parking-help">
        Модель предложит координаты и решения по выбранному эпизоду. Вы проверяете источники и
        отдельно принимаете предложения. Каждый новый запрос модели может потребовать оплаты.
      </p>
      {!episode && <Notice>Сначала выберите эпизод. Ручной ввод доступен после выбора.</Notice>}
      <Actions>
        <Button
          disabled={disabled || loading || sending || !episode || available !== true}
          aria-busy={sending}
          onClick={() => void propose()}
        >
          {sending
            ? 'Модель предлагает обстоятельства…'
            : 'Запросить предложения модели · платный запрос'}
        </Button>
        <Button
          variant="secondary"
          disabled={disabled || loading || sending || !episode}
          onClick={() => setRefresh((value) => value + 1)}
        >
          {loading
            ? 'Загрузка сохранённых предложений…'
            : 'Показать последние сохранённые предложения'}
        </Button>
      </Actions>
      {error && (
        <Notice tone="danger" role="alert">
          {error}
        </Notice>
      )}
      {unknownOutcome && (
        <Notice tone="warning">
          Исход запроса модели ещё не подтверждён: он мог быть оплачен и сохранён. Список показывает
          последние сохранённые предложения, которые могут относиться к более ранним запросам.
          Обновление списка не вызывает модель; новый платный запрос запускается только отдельным
          нажатием.
        </Notice>
      )}
      {available === false && (
        <Notice>Предложения модели сейчас недоступны. Заполните обстоятельства вручную.</Notice>
      )}
      {episode && available !== false && !loading && !sending && !proposal && !error && (
        <Notice>
          Для этого эпизода ещё нет сохранённого предложения. Можно запросить его или указать
          решения вручную.
        </Notice>
      )}
      {proposal && (
        <>
          <Status tone={accepted ? 'success' : 'neutral'}>
            {accepted
              ? 'Координаты подготовлены по этому предложению; текущие значения выше'
              : 'Координаты требуют вашего подтверждения'}
          </Status>
          <dl className="parking-journal-details">
            {legalCoordinateKeys.map((key) => (
              <Fragment key={key}>
                <dt>{coordinateLabels[key]}</dt>
                <dd>
                  {proposal.suggestion.coordinates[key].value ||
                    `Не предложено. ${proposal.suggestion.coordinates[key].rationale}`}
                </dd>
              </Fragment>
            ))}
          </dl>
          <Disclosure summary="Основания и источники предложенных координат">
            {legalCoordinateKeys.map((key) => {
              const coordinate = proposal.suggestion.coordinates[key];
              return (
                <div key={key}>
                  <p>
                    <strong>{coordinateLabels[key]}</strong>: {coordinate.rationale}
                  </p>
                  {statements
                    .filter((statement) => coordinate.statementIds.includes(statement.id))
                    .map((statement) => (
                      <Quote key={statement.id}>
                        «{statement.quote}» — {statement.valueText}
                      </Quote>
                    ))}
                </div>
              );
            })}
          </Disclosure>
          <Button
            variant="secondary"
            disabled={disabled || sending || loading || accepted}
            onClick={() => onAcceptCoordinates(proposal)}
          >
            {accepted
              ? 'Предложение использовано для координат'
              : 'Принять предложенные координаты'}
          </Button>
          <p className="parking-help">
            Модель: {proposal.model}. Решения об обстоятельствах подтвердите отдельно ниже.
          </p>
        </>
      )}
    </section>
  );
}
