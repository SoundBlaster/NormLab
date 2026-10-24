import { useState } from 'react';
import { Button, Disclosure, Notice, Quote, Status } from '@/shared/ui';
import {
  legalStateLabels,
  type LegalFinding,
  type LegalWorkspace,
  type ReviewStatement,
} from '../model/contracts.js';
import type { LegalValidationIssue } from '../model/legal-validation.js';
import { LegalFindingEditor } from './LegalFindingEditor.js';

export function LegalCandidate({
  condition,
  candidate,
  finding,
  proposalId,
  statements,
  disabled,
  acceptDisabled = false,
  issues = [],
  onAccept,
  onChange,
}: {
  condition: LegalWorkspace['package']['conditions'][number];
  candidate: LegalFinding;
  finding: LegalFinding;
  proposalId: string;
  statements: ReviewStatement[];
  disabled: boolean;
  acceptDisabled?: boolean;
  issues?: LegalValidationIssue[];
  onAccept: () => void;
  onChange: (patch: Partial<LegalFinding>) => void;
}) {
  const [manualOpen, setManualOpen] = useState(false);
  const accepted = finding.proposalId === proposalId;
  const hasIssues = issues.some((issue) => issue.key.startsWith(`${condition.id}.`));
  const proposedSources = statements.filter((statement) =>
    candidate.statementIds.includes(statement.id),
  );
  const currentSources = statements.filter((statement) =>
    finding.statementIds.includes(statement.id),
  );
  return (
    <fieldset className="parking-legal-fields" disabled={disabled}>
      <legend>{condition.label}</legend>
      <Status tone={accepted ? 'success' : 'neutral'}>
        {accepted ? 'Решение на основе предложения' : 'Предложение требует вашего решения'}
      </Status>
      <p>
        <strong>Предложение модели: {legalStateLabels[candidate.state]}</strong>
      </p>
      <p>
        {candidate.rationale || 'Модель не предложила основание. Уточните обстоятельство вручную.'}
      </p>
      {proposedSources.length > 0 && (
        <Disclosure summary={`Источники предложения · ${proposedSources.length}`}>
          {proposedSources.map((statement) => (
            <Quote key={statement.id}>
              «{statement.quote}» — {statement.valueText}
            </Quote>
          ))}
        </Disclosure>
      )}
      {!accepted && (
        <Button variant="secondary" disabled={disabled || acceptDisabled} onClick={onAccept}>
          Принять это предложение
        </Button>
      )}
      <div>
        <p>
          <strong>В расчёт сейчас: {legalStateLabels[finding.state]}</strong>
        </p>
        <p>{finding.rationale || 'Основание пока не указано.'}</p>
        {currentSources.length > 0 && (
          <Disclosure summary={`Ссылки текущего решения · ${currentSources.length}`}>
            {currentSources.map((statement) => (
              <Quote key={statement.id}>
                «{statement.quote}» — {statement.valueText}
              </Quote>
            ))}
          </Disclosure>
        )}
      </div>
      {hasIssues && <Notice tone="danger">Исправьте отмеченные поля текущего решения.</Notice>}
      <Disclosure
        summary={accepted ? 'Исправить принятое решение вручную' : 'Указать своё решение вручную'}
        open={manualOpen || hasIssues}
        onToggle={(event) => {
          if (hasIssues && !event.currentTarget.open) {
            event.currentTarget.open = true;
            return;
          }
          setManualOpen(event.currentTarget.open);
        }}
      >
        <LegalFindingEditor
          condition={condition}
          finding={finding}
          statements={statements}
          disabled={disabled}
          issues={issues}
          onChange={onChange}
        />
      </Disclosure>
    </fieldset>
  );
}
