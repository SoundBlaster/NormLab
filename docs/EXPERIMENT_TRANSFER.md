# Перенос эксперимента — NL-503

Локальная реализация: 2026-10-03. Формат `normlab.experiment/v1` объединяет 1–12 подписанных exports текущего synthetic reform profile. JSON Schema: [experiment.schema.json](../schemas/transfer/experiment.schema.json). Реализация: [transfer](../server/reform-transfer.ts), [HTTP](../server/reform-lab.ts), [SQLite](../server/reform-store.ts), [UI](../client/pages/reform-lab/ui/Transfer.tsx).

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

| Method / path                             | Назначение                                                              |
| ----------------------------------------- | ----------------------------------------------------------------------- |
| `POST /api/reform/experiments/export`     | `{analysisIds}` → переносимый набор из 1–12 локальных signed analyses   |
| `GET /api/reform/imports`                 | Краткая история импортов, без утверждения о текущем proof status        |
| `POST /api/reform/imports`                | `{experiment, trustedPublicKey}` → fresh replay, затем immutable запись |
| `POST /api/reform/imports/:digest/replay` | `{}` → read-only view с fresh evidence                                  |
| `GET /api/reform/imports/:digest/export`  | Исходный переносимый набор                                              |

Все POST используют существующие session token/Origin/Host checks. Import request ограничен 2 MiB + 32 KiB для wrapper/key; сам набор — 2 MiB, public key — 16 KiB. File reads используют strict UTF-8. Нет архивов, filesystem paths из набора или распаковки.

`reform_imports` — отдельная append-only таблица с запретом UPDATE/DELETE. ID — digest всего experiment; повторный импорт идентичного набора сохраняет исходное время записи. Проверка всех items предшествует единственной записи: частично прошедший набор не сохраняется. Смена текущего состояния evidence при replay не переписывает исторический record. Общий лимит jobs остаётся два; items проверяются последовательно.

## Полученные свидетельства и оставшиеся проверки

Production build и TypeScript strict прошли. CLI упаковал ранее сохранённый browser export и выполнил successful fresh Lean replay в отдельном data directory. Также выполнен перенос набора из пяти существующих exports: conditional decision A/B/C, A→B equivalence и A→D counterexample. Для каждого результата подтверждены signature, exact bindings и `current: true`; используются case theorem и finite-domain theorem соответственно.

Финальный набор с runtime locks находится в ignored `.artifacts/nl503-final-experiment.json`, принимающее хранилище — `.artifacts/reform-nl503-final`. Эти локальные данные не входят в Git. Это перенос между data directories на одной машине, а не доказательство установки на чистой машине.

Focused HTTP regression 2026-10-03: отклоняются wrong trusted key, dependency lock drift, query/certificate mismatch, tampered signature/manifest/annotations, unknown model identity/version, unknown receipt role и корректно подписанный `unsupported` proof claim. После каждого отказа история остаётся пустой. В отдельном двух-item наборе повреждение второго receipt не сохраняет первый item. Валидный набор проходит fresh replay; повторный импорт сохраняет исходный `importedAt` и не создаёт duplicate. Imported history и исходный workspace переживают закрытие и повторное открытие приложения; history можно заново открыть с fresh replay. Отдельный HTTP сценарий переносит результаты двух последовательных revisions: `supersedes` и revision сохраняются, а receiving workspace остаётся byte-for-byte эквивалентен состоянию до импорта. Результат focused tests: 2/2 passed.

Повторные проверки после изменений: обычный domain/API suite 42/42, Lean integration suite 14/14, TypeScript strict, production build и Prettier прошли. Непосредственное UI-скачивание подтверждено в Safari; автоматизированный download handler Playwright/Browser Preview отдельно остаётся непроверенным из-за сбоя connector. Persistence состояния клиентского незавершённого draft после перезапуска не проводилась.

Продолжение browser walkthrough: пользователь передал скачанный `normlab-experiment.json` (23,544 bytes, один item). CLI проверил его с public key, полученным из локального issuer key: signature и bindings valid, evidence current, fresh Lean proof verified (`case-theorem`). Затем UI импортировал файл с явно выбранным trusted public key; страница показала, что все результаты подтверждены fresh replay и набор открыт только для чтения. Запись появилась в истории импортов; её повторное открытие снова выполнило replay и показало verified result (1/1 completions). Рабочий snapshot/findings не изменялись. Для загрузки файл был временно помещён в разрешённую browser automation директорию, затем временные копии и public key удалены. Тестовые проверки дополнительно подтвердили сохранение истории импорта после перезапуска сервера и точное сохранение цепочки двух revisions в portable наборе.

Bounded Playwright Chromium walkthrough 2026-10-03 (10 calls): приложение открылось, Transfer tab и доступный export result обнаружены. После выбора одного результата клик «Скачать набор (1)» снова вызвал `TypeError: Cannot read properties of undefined (reading 'url')`; наблюдение показало переход страницы на `about:blank`, а network request list не содержал download request. Одна восстановительная навигация вернула приложение; после неё браузерная консоль не содержала errors. Persistent application state не менялся; checkbox selection была временным UI state.

Клик «Скачать набор (3)» в Browser Preview ранее вызвал ту же automation ошибку, после чего пользователь приложил crash report Chrome с `EXC_BAD_ACCESS (SIGSEGV)` в `CrBrowserMain` в соответствующий момент. Стек не символизирован; совпадение по времени не доказывает первопричину и не позволяет приписать сбой приложению. Playwright повторяет automation сбой на download gesture, но не зафиксировал HTTP request, поэтому endpoint через этот UI walkthrough не проверен. Переданный пользователем файл доказывает успешное скачивание в его браузере, но браузер/канал получения отдельно не установлен; отдельно API regression проверяет export endpoint, а tests проверяют import/replay. Перенос полной SQLite history и чистая установка не проводились.

Safari Computer Use walkthrough 2026-10-03: в отдельной вкладке Safari загружен текущий локальный UI, дождались fresh Lean результата, выбрали сохранённый результат C и нажали «Скачать набор (1)». Safari оставил страницу приложения открытой и показал в Downloads файл `normlab-experiment-2.json` размером 24 KB без сообщения о прогрессе или ошибке. Automation error не возник. Скачанный файл не импортировался повторно, чтобы не создавать лишнюю запись истории. Workspace, snapshots и findings не менялись; изменилось только временное выделение export checkbox. Это подтверждает browser download gesture в Safari. Причина ошибки Playwright/Browser Preview остаётся неустановленной, а не блокирует transfer flow.
