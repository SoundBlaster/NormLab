import type { Ref } from 'react';
import { Button, Notice } from '@/shared/ui';
import type { LegalAssessment, LegalInput } from '../model/contracts.js';
import type { LegalValidationIssue } from '../model/legal-validation.js';

function focusField(targetId?: string) {
  if (!targetId) return;
  const field = document.getElementById(targetId);
  if (!field) return;
  field.focus({ preventScroll: true });
  field.scrollIntoView({ block: 'center', inline: 'nearest' });
}

function SavedLegalFeedback({ record }: { record: LegalAssessment }) {
  if (!record.result)
    return <Notice tone="success">Обстоятельства сохранены без расчёта и проверки Lean.</Notice>;
  if (record.verifiedByPreviousProfile)
    return (
      <Notice tone="warning">
        Расчёт сохранён. Проверка относится к прежней модели PoC. Выполните новый расчёт для
        проверки текущей моделью.
      </Notice>
    );
  switch (record.verification?.status) {
    case 'verified':
      return (
        <Notice tone="success">
          Расчёт сохранён. Lean проверил правила модели PoC для этого результата.
        </Notice>
      );
    case 'rejected':
      return (
        <Notice tone="danger">
          Расчёт сохранён. Lean отклонил результат: он не соответствует правилам модели PoC.
        </Notice>
      );
    case 'inconclusive':
      return (
        <Notice tone="warning">
          Расчёт сохранён. Результат не получил подтверждения Lean. {record.verification.reason}
        </Notice>
      );
    default:
      return (
        <Notice tone="warning">
          Расчёт сохранён без проверки Lean. Выполните новый расчёт для проверки.
        </Notice>
      );
  }
}

export function LegalActionFeedback({
  error,
  issues,
  validationAttempted,
  busy,
  action,
  record,
  feedbackRef,
}: {
  error: string;
  issues: LegalValidationIssue[];
  validationAttempted: boolean;
  busy: boolean;
  action?: LegalInput['action'];
  record?: LegalAssessment;
  feedbackRef: Ref<HTMLDivElement>;
}) {
  return (
    <div ref={feedbackRef} tabIndex={-1} aria-live="polite">
      {busy && (
        <Notice role="status">
          {action === 'calculate'
            ? 'Рассчитываем и проверяем в Lean…'
            : 'Сохраняем обстоятельства…'}
        </Notice>
      )}
      {error && (
        <Notice tone="danger" role="alert">
          {error}
        </Notice>
      )}
      {!busy && issues.length > 0 && (
        <>
          <Notice tone="danger">
            {action === 'save'
              ? 'Обстоятельства не отправлены. Исправьте поля:'
              : 'Расчёт не запущен. Исправьте поля:'}
          </Notice>
          <ul aria-label="Поля, требующие исправления">
            {issues.map((issue) => (
              <li key={`${issue.key}:${issue.message}`}>
                {issue.targetId ? (
                  <Button variant="quiet" onClick={() => focusField(issue.targetId)}>
                    {issue.message}
                  </Button>
                ) : (
                  issue.message
                )}
              </li>
            ))}
          </ul>
        </>
      )}
      {validationAttempted && issues.length === 0 && !error && !busy && !record && (
        <Notice>
          Исправления внесены. Нажмите «
          {action === 'save' ? 'Сохранить обстоятельства' : 'Рассчитать и проверить в Lean'}» ещё
          раз.
        </Notice>
      )}
      {record && !error && !busy && !validationAttempted && <SavedLegalFeedback record={record} />}
    </div>
  );
}
