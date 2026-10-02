# Перенос эксперимента — NL-503

Локальная реализация: 2026-10-03. Формат `normlab.experiment/v1` объединяет 1–12 подписанных exports текущего synthetic reform profile. JSON Schema: [experiment.schema.json](../schemas/transfer/experiment.schema.json). Реализация: [transfer](../server/reform-transfer.ts), [HTTP](../server/reform-lab.ts), [SQLite](../server/reform-store.ts), [UI](../client/lab/Transfer.tsx).

## Состав и границы доверия

Каждый item содержит существующий `normlab.reform-export/v1`: exact query, locked bundles с исходными текстами и mappings, snapshot либо `null`, certificate и receipt. Source annotations передаются отдельным полем. Manifest фиксирует artifact/annotation/bundle/query/certificate/statement digests, receipt verification metadata, Lean toolchain, Node engine requirement и digest `package-lock.json`.

Manifest проверяет согласованность набора, но не является отдельной подписанной publication receipt. Доверие задаёт явно выбранный public key из независимого доверенного канала. Ключ внутри receipt не становится trusted автоматически. Fingerprint issuer — существующий `digest(publicKey)`: SHA-256 canonical JSON строки PEM, а не SHA-256 raw PEM bytes.

Подпись receipt связывает формальное утверждение и входы. Source annotations не входят в подпись receipt: этот release принимает только exact reviewed sidecar из `fixtures/reform-v1/metric-annotations.json` либо `null`. При отсутствии annotations соответствующие метрики недоступны, а не равны нулю. Manifest не доказывает истинность findings, fidelity перевода источника или human review.

Импорт ограничен exact registry A/B/C и поддержанной synthetic поправкой D; неизвестная модель, версия, altered bundle и иной scope/roles общих queries отклоняются. Нужны текущие dependency locks и свежая проверка exact receipt claim/toolchain. Отсутствие Lean или historical/mismatched proof не допускают сохранения нового импорта.

## Через Laboratory UI

1. В «Перенос эксперимента» выбрать сохранённые результаты и скачать набор. Выбор нескольких ревизий сохраняет их исходные snapshot IDs, revision, findings и supersedes внутри exports.
2. Передать `Public key` отдельно по доверенному каналу и проверить issuer identity.
3. В принимающей локальной установке выбрать JSON и доверенный PEM. «Проверить и сохранить импорт» проверяет все items перед записью.
4. Открыть запись в «История импортов». Открытие выполняет fresh replay. Findings, explanations и metrics доступны только для чтения; исходный набор можно скачать повторно.

Набор переносит выбранные результаты, а не полную SQLite database. Predecessor snapshot, на который ссылается `supersedes`, включается только при выборе результата этой ревизии. Импортированные snapshots не входят в рабочую последовательность ревизий, не меняют текущую форму и не становятся accepted findings нового рабочего snapshot.

## CLI

Упаковка существующих exports с reviewed annotations:

```sh
npm run reform:pack -- A.json B.json C.json AB.json \
  --issuer-key trusted-issuer-public.pem \
  --annotations source-annotations.json \
  --output experiment.json
```

`--annotations` необязателен. Output создаётся с `0600` и `wx`: существующий файл не перезаписывается. Упаковка проверяет signature, bindings, registry и sidecar, но сама не запускает Lean и не выдаёт новый receipt.

Fresh replay без записи:

```sh
npm run reform:import -- experiment.json --issuer-key trusted-issuer-public.pem
```

Импорт в отдельное хранилище после успешного replay всех items:

```sh
npm run reform:import -- experiment.json \
  --issuer-key trusted-issuer-public.pem \
  --data-dir .artifacts/imported-experiment
```

CLI выводит отдельные signature/bindings/current/proof statuses. При неподтверждённом replay exit code — 1, запись не производится. В указанном data directory будет стандартный начальный рабочий snapshot принимающей лаборатории; imported findings хранятся отдельно. Чистая установка toolchain остаётся частью NL-504.

## HTTP и storage

| Method / path | Назначение |
| --- | --- |
| `POST /api/reform/experiments/export` | `{analysisIds}` → переносимый набор из 1–12 локальных signed analyses |
| `GET /api/reform/imports` | Краткая история импортов, без утверждения о текущем proof status |
| `POST /api/reform/imports` | `{experiment, trustedPublicKey}` → fresh replay, затем immutable запись |
| `POST /api/reform/imports/:digest/replay` | `{}` → read-only view с fresh evidence |
| `GET /api/reform/imports/:digest/export` | Исходный переносимый набор |

Все POST используют существующие session token/Origin/Host checks. Import request ограничен 2 MiB + 32 KiB для wrapper/key; сам набор — 2 MiB, public key — 16 KiB. File reads используют strict UTF-8. Нет архивов, filesystem paths из набора или распаковки.

`reform_imports` — отдельная append-only таблица с запретом UPDATE/DELETE. ID — digest всего experiment; повторный импорт идентичного набора сохраняет исходное время записи. Проверка всех items предшествует единственной записи: частично прошедший набор не сохраняется. Смена текущего состояния evidence при replay не переписывает исторический record. Общий лимит jobs остаётся два; items проверяются последовательно.

## Полученные свидетельства и оставшиеся проверки

Production build и TypeScript strict прошли. CLI упаковал ранее сохранённый browser export и выполнил successful fresh Lean replay в отдельном data directory. Также выполнен перенос набора из пяти существующих exports: conditional decision A/B/C, A→B equivalence и A→D counterexample. Для каждого результата подтверждены signature, exact bindings и `current: true`; используются case theorem и finite-domain theorem соответственно.

Финальный набор с runtime locks находится в ignored `.artifacts/nl503-final-experiment.json`, принимающее хранилище — `.artifacts/reform-nl503-final`. Эти локальные данные не входят в Git. Это перенос между data directories на одной машине, а не доказательство установки на чистой машине.

Негативные HTTP/tampering regression tests и browser walkthrough новой вкладки в этом срезе не выполнялись. Пока эти gates открыты, NL-503 остаётся незавершённым в roadmap. Полный domain/Lean integration suite не запускался; имеющиеся результаты предыдущих этапов не считаются новым regression evidence.
