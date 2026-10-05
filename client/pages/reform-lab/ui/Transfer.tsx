import { useEffect, useState } from 'react';
import type { LabBootstrap } from '@/entities/norm';
import {
  MAX_EXPERIMENT_BYTES,
  MAX_EXPERIMENT_ITEMS,
  type ImportedExperimentSummary,
  type ImportedExperimentView,
} from '@/entities/norm';
import {
  ConsequenceMetrics,
  Evidence,
  ExplanationPanel,
  downloadData,
  findingNames,
} from './Views.js';

async function call<T>(path: string, token?: string, body?: unknown): Promise<T> {
  const response = await fetch(
    path,
    body === undefined
      ? {}
      : {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-NormLab-Token': token ?? '' },
          body: JSON.stringify(body),
        },
  );
  const value = await response.json();
  if (!response.ok) throw new Error(value.error ?? 'Операция не выполнена.');
  return value as T;
}
async function readFile(file: File, limit: number) {
  if (file.size > limit) throw new Error(`Размер файла превышает ${limit} bytes.`);
  return new TextDecoder('utf-8', { fatal: true }).decode(await file.arrayBuffer());
}

export function Transfer({
  data,
  busy,
  setBusy,
}: {
  data: LabBootstrap;
  busy: boolean;
  setBusy: (busy: boolean) => void;
}) {
  const [selected, setSelected] = useState<string[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [keyFile, setKeyFile] = useState<File | null>(null);
  const [imports, setImports] = useState<ImportedExperimentSummary[]>([]);
  const [opened, setOpened] = useState<ImportedExperimentView | null>(null);
  const [itemIndex, setItemIndex] = useState(0);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const downloadHref = `/api/reform/experiments/download?${selected
    .map((id) => `analysisId=${encodeURIComponent(id)}`)
    .join('&')}`;
  useEffect(() => {
    let active = true;
    call<ImportedExperimentSummary[]>('/api/reform/imports')
      .then((items) => {
        if (active) setImports(items);
      })
      .catch((e) => {
        if (active) setError(e instanceof Error ? e.message : 'История импорта недоступна.');
      });
    return () => {
      active = false;
    };
  }, []);
  async function perform(action: () => Promise<void>) {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await action();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Операция не выполнена.');
    } finally {
      setBusy(false);
    }
  }
  function open(view: ImportedExperimentView) {
    setOpened(view);
    setItemIndex(0);
    setNotice(
      view.views.every((v) => v.metricsReport?.evidence.current)
        ? 'Все результаты подтверждены fresh replay. Набор открыт только для чтения.'
        : 'Исторический набор открыт. Текущая проверка подтверждена не для всех результатов.',
    );
  }
  const view = opened?.views[itemIndex];
  return (
    <>
      {error && (
        <p className="message error" role="alert">
          {error}
        </p>
      )}
      {notice && (
        <p className="message" role="status">
          {notice}
        </p>
      )}
      <section className="lab-panel">
        <h2>Перенести эксперимент</h2>
        <p className="lab-note">
          Выберите до {MAX_EXPERIMENT_ITEMS} сохранённых результатов. Набор содержит входы, sources,
          annotations, manifest и locks. Подтверждённые findings остаются частью исходного snapshot.
        </p>
        <fieldset className="lab-transfer-selection" disabled={busy}>
          <legend>Результаты для экспорта</legend>
          {data.workspace.analyses
            .filter((a) => a.proofStatus === 'verified')
            .map((a) => (
              <label key={a.id}>
                <input
                  type="checkbox"
                  checked={selected.includes(a.id)}
                  disabled={!selected.includes(a.id) && selected.length >= MAX_EXPERIMENT_ITEMS}
                  onChange={(e) =>
                    setSelected(
                      e.target.checked ? [...selected, a.id] : selected.filter((id) => id !== a.id),
                    )
                  }
                />
                <span>
                  {a.title} ·{' '}
                  {a.snapshotId
                    ? `snapshot #${data.workspace.snapshots.find((s) => s.id === a.snapshotId)?.revision ?? '?'}`
                    : a.queryId}
                  <small>
                    {new Date(a.createdAt).toLocaleString('ru-RU')} · {a.resultStatus}
                  </small>
                </span>
              </label>
            ))}
          {!data.workspace.analyses.some((a) => a.proofStatus === 'verified') && (
            <p className="lab-note">Сначала сравните A/B/C или проверьте общее свойство.</p>
          )}
        </fieldset>
        <div className="lab-form-actions">
          <button
            className="primary"
            disabled={busy || !selected.length}
            onClick={() => {
              setError('');
              setNotice(
                `Запрошено скачивание результатов: ${selected.length}. Передайте public key по доверенному каналу.`,
              );
              window.location.assign(downloadHref);
            }}
          >
            Скачать набор ({selected.length})
          </button>
          <button
            className="secondary"
            disabled={busy}
            onClick={() => downloadData('issuer-public.pem', data.issuerPublicKey, true)}
          >
            Public key ↓
          </button>
        </div>
      </section>
      <section className="lab-panel">
        <h2>Импорт и независимая проверка</h2>
        <p className="lab-note">
          Выберите JSON-набор (до 2 MiB) и public key, которому доверяете. Ключ из самого набора не
          устанавливает доверие. Импорт сохраняется после проверки подписи, exact bindings и fresh
          Lean replay всех результатов.
        </p>
        <div className="lab-case-input">
          <label>
            Набор эксперимента
            <input
              type="file"
              accept=".json,application/json"
              disabled={busy}
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </label>
          <label>
            Доверенный public key
            <input
              type="file"
              accept=".pem,text/plain"
              disabled={busy}
              onChange={(e) => setKeyFile(e.target.files?.[0] ?? null)}
            />
          </label>
        </div>
        <button
          className="primary"
          disabled={busy || !file || !keyFile}
          onClick={() =>
            perform(async () => {
              const experiment = JSON.parse(await readFile(file!, MAX_EXPERIMENT_BYTES));
              const trustedPublicKey = await readFile(keyFile!, 16384);
              const result = await call<ImportedExperimentView>(
                '/api/reform/imports',
                data.csrfToken,
                { experiment, trustedPublicKey },
              );
              open(result);
              setImports(await call<ImportedExperimentSummary[]>('/api/reform/imports'));
            })
          }
        >
          Проверить и сохранить импорт
        </button>
      </section>
      <section className="lab-panel">
        <h2>История импортов</h2>
        <p className="lab-note">
          Импортированные snapshots не становятся рабочими ревизиями. Открытие повторяет проверку;
          сохранённый набор не изменяется.
        </p>
        {imports.map((item) => (
          <button
            key={item.id}
            className="lab-history-row"
            disabled={busy}
            onClick={() =>
              perform(async () =>
                open(
                  await call<ImportedExperimentView>(
                    `/api/reform/imports/${item.id}/replay`,
                    data.csrfToken,
                    {},
                  ),
                ),
              )
            }
          >
            <span>
              <strong>Набор · {item.itemCount} результатов</strong>
              <small>
                Issuer: {item.issuer.slice(0, 16)}… · {item.id.slice(0, 12)}…
              </small>
            </span>
            <time>{new Date(item.importedAt).toLocaleString('ru-RU')}</time>
            <span aria-hidden="true">→</span>
          </button>
        ))}
        {!imports.length && <p className="lab-note">Импортированных наборов пока нет.</p>}
      </section>
      {opened && view && (
        <>
          <section className="lab-panel">
            <span className="eyebrow">ИМПОРТ · ТОЛЬКО ДЛЯ ЧТЕНИЯ</span>
            <h2>Результаты исходного эксперимента</h2>
            <label>
              Сохранённый результат
              <select
                value={itemIndex}
                disabled={busy}
                onChange={(e) => setItemIndex(Number(e.target.value))}
              >
                {opened.views.map((v, i) => (
                  <option key={i} value={i}>
                    {i + 1}. {v.analysis.title}
                  </option>
                ))}
              </select>
            </label>
            {view.analysis.snapshot && (
              <div className="lab-import-findings">
                <p>{view.analysis.snapshot.narrative}</p>
                <p>
                  Snapshot #{view.analysis.snapshot.revision} · {view.analysis.snapshot.group} ·
                  supersedes: {view.analysis.snapshot.supersedes ?? 'нет'}
                </p>
                {(['M', 'N', 'E'] as const).map((p) => (
                  <p key={p}>
                    <strong>
                      {p}: {findingNames[view.analysis.snapshot!.findings[p].state]}
                    </strong>{' '}
                    · {view.analysis.snapshot!.findings[p].rationale}
                  </p>
                ))}
              </div>
            )}
            <Evidence view={view} />
            <div className="lab-form-actions">
              <a
                className="secondary"
                href={`/api/reform/imports/${opened.experiment.id}/export`}
                download
              >
                Исходный набор ↓
              </a>
              <button
                className="secondary"
                onClick={() =>
                  downloadData('trusted-issuer-public.pem', opened.trustedPublicKey, true)
                }
              >
                Public key ↓
              </button>
              <button
                className="secondary"
                onClick={() =>
                  perform(async () =>
                    open(
                      await call<ImportedExperimentView>(
                        `/api/reform/imports/${opened.experiment.id}/replay`,
                        data.csrfToken,
                        {},
                      ),
                    ),
                  )
                }
                disabled={busy}
              >
                Повторить проверку
              </button>
            </div>
          </section>
          <ExplanationPanel key={`${opened.experiment.id}:${itemIndex}`} view={view} />
          <ConsequenceMetrics view={view} />
        </>
      )}
    </>
  );
}
