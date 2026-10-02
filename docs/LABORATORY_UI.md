# Laboratory UI — NL-502

Дата: 2026-10-02. **Локальный срез M1 реализован** для reviewed synthetic fixture A/B/C и `demo.reform-mitigation/v1`. Исходный M0/v1 доступен в прежних разделах приложения. Запуск: [README](../README.md).

## Пользовательский flow

По умолчанию открывается «Реформа A/B/C». Рабочая область содержит narrative, выбранную извне группу K1/K2 и мотивированные findings M/N/E. Четыре состояния сохраняют семантику профиля: `unreviewed` и `not-established` оставляют обе completion-возможности.

«Сравнить A/B/C» проверяет один immutable snapshot во всех трёх моделях. Карточки показывают срок, штраф, число completions и proof/coverage status. Одинаковые outcomes могут отображаться одной суммой, но ветви сохраняются в explanation selector. Ledger показывает каждый rule в scope, основание применения или исключения, finding/completion origins, числовые шаги и exact source excerpts.

Изменённые findings сохраняются новой ревизией с `supersedes`. Сервер принимает запись только при совпадении `expectedSnapshotId` с последней ревизией; конфликт возвращает 409. Исторический snapshot доступен только для чтения. Открытие сохранённых результатов запускает fresh replay. Draft сохраняется при переключении разделов; переход к другой ревизии и перенос counterexample блокируются до сохранения либо явного сброса draft.

Вкладки Laboratory:

| Раздел | Содержание |
| --- | --- |
| Рабочая область | Один snapshot, три модели, findings, explanations и artifacts |
| Свойства и counterexamples | Восемь фиксированных queries: A/B equivalence, три свойства A/C, unary M mitigation A/B/C и ошибочная поправка D |
| Метрики | Структура A/B/C и последствия текущего analysis с названием query и точным scope |
| Источники | Synthetic source, typed rules, mappings и semantic/provenance digests |
| История | Ревизии findings и сохранённые общие queries с повторной проверкой при открытии |

Общие queries используют объявленный D16 либо его явно заданный scope. Findings рабочего snapshot не сужают их domain. Counterexample explorer показывает вход и обе модели. Перенос его условий создаёт draft для сравнения A/B/C; ошибочная модель D остаётся частью отдельного query.

## Evidence и artifacts

`Проверено в Lean` появляется только при `metricsReport.evidence.current`: trusted signature, exact bindings и fresh independent verification согласованы. Signer выдаёт receipt после успешной verification; отсутствие Lean или незавершённая проверка оставляют candidate без подписанного export. Исторический issued status в списке не становится текущим доказательством без replay.

Сохранённые анализы содержат точные query, bundles, snapshot при decision, certificate, receipt, verification metadata и source annotations. Версия модели дополнительно сравнивается с текущим registry. Explanation и metrics — deterministic projections с собственными digest; их подсчёт и rendering не имеют отдельного Lean proof. Для текущего evidence доступны JSON reports, annotations и публичный issuer key.

«Export и receipt» скачивает существующий `normlab.reform-export/v1`. Он совместим с `reform:verify`, `reform:explain` и `reform:metrics`. CLI требует явно выбранный trusted public key. При переносе в другую среду канал доверия ключу должен быть определён отдельно; ключ из самого недоверенного export не устанавливает trust.

Formal claims относятся к locked IR, findings, поддержанному профилю и объявленному scope. Истинность обстоятельств, выбор группы, fidelity перевода текста, соответствие реальному праву и социальный эффект не выводятся из Lean verification.

## Storage и HTTP API

Реализация: [ReformStore](../server/reform-store.ts), [ReformLab](../server/reform-lab.ts), [HTTP app](../server/app.ts), [wire types](../shared/reform-lab.ts), [React UI](../client/lab/Lab.tsx).

`reform_snapshots` и `reform_analyses` — отдельные таблицы в `normlab.sqlite`. SQL triggers запрещают UPDATE/DELETE; snapshot revisions создаются в transaction. M0 tables и v1 artifacts сохраняют прежние contracts. Миграция v1 snapshots в v2 не выполняется. По умолчанию данные и signing keys находятся в `.data/`; `NORMLAB_DATA_DIR` задаёт другой каталог. Private keys не входят в HTTP responses и downloads.

| Method / path | Вход / результат |
| --- | --- |
| `GET /api/reform/bootstrap` | Workspace, A/B/C, structure metrics, verifier availability, public key, session token |
| `POST /api/reform/snapshots` | `{input, expectedSnapshotId}` → 201, новый snapshot и workspace |
| `POST /api/reform/analyze` | `{snapshotId}` → A/B/C views и workspace |
| `POST /api/reform/queries` | `{queryId}` → view фиксированного general query и workspace |
| `POST /api/reform/analyses/:id/replay` | `{}` → fresh evidence и projections сохранённого analysis |
| `GET /api/reform/analyses/:id/export` | Bound v2 export с receipt; 409 при отсутствии receipt |

Все POST требуют текущий `x-normlab-token` из bootstrap и `application/json`. Host ограничен loopback адресом с текущим портом; переданный Origin должен совпадать с ним. V2 request body ограничен 64 KiB, M0 — 32 KiB; JSON декодируется как strict UTF-8. Wire objects строгие: неизвестные поля и query IDs отклоняются. Одновременно допускаются два jobs суммарно для M0/v2; одинаковые активные v2 jobs объединяются. Последовательные явные запуски могут создавать новые immutable analyses.

V2 анализ сохраняется по мере завершения каждой модели. Если batch A/B/C прерван после A, уже записанный результат остаётся в истории; незавершённые модели можно вычислить новым запуском. Это локальный in-process pipeline; durable queue, crash recovery и OS sandbox относятся к M3.

## Проверка этого среза

Проверки выполнены локально 2026-10-02:

| Проверка | Свидетельство |
| --- | --- |
| TypeScript strict и production build | `npm run build` прошёл; 21 client modules |
| JSON schema freshness | `npm run schemas:check`: 10 schemas актуальны |
| Domain/API regression suite | `npm test`: 40/40 passed, включая 5 новых [NL-502 tests](../tests/reform-lab.test.ts) |
| Исходный snapshot через UI | K1, M established, N/E refuted → A/B/C = 80/80/60 месяцев, штраф 200 000 DEMO; три verified receipts |
| Новая ревизия через UI | N not-established, E established → snapshot #2; 2/2 completions для каждой модели, один outcome; при N=true ledger исключает N и применяет M |
| История через UI | Snapshot #1 открыт после #2; три результата повторно проверены, historical form disabled |
| General query через UI | A→D preserved-outside: verified bound witness K1/M=false/N=true/E=false, 90→80; declared-complete, 8/8 scope вне M |
| Download и независимый replay | Browser download сохранён, `reform:verify` подтвердил signature/bindings/current и fresh Lean 4.30.0 finite-domain-theorem |
| Desktop/mobile | Просмотрены screenshots 1440 и 390 px; на mobile document/body width = 390, таблицы имеют собственную horizontal scroll region |
| Базовая accessibility | Формы имеют labels/legends; keyboard Tab переводит focus на «Источники», outline solid; historical controls disabled |
| Browser console | 0 warnings, 0 errors в проверенном контексте |

Новые tests проверяют нормализацию и сохранение findings, reopening SQLite, Unicode rationale limits, stale revision, SQL immutability, CSRF/Origin/Host, совместимость bootstrap с M0, unknown query/extra fields и malformed UTF-8. Полный Lean integration suite в этом срезе повторно не запускался: actual Lean выполнялся в browser flow, history replay, CLI replay и существующем HTTP regression test. Исторические exhaustive proof checks описаны отдельно в [decision](REFORM_VERIFICATION.md) и [comparison evidence](COMPARISON_VERIFICATION.md).

Bounded browser audit: 17:19:33–17:25:43 UTC, 15/15 browser calls, 2/6 screenshots, один автоматически сохранённый initial snapshot, два focused source reads. Два locator timeout исправлены по наблюдённому DOM; они не сопровождались ошибками приложения. Использовался настроенный Playwright Chrome 154, отдельный data directory `.artifacts/reform-nl502-runtime`; создано два snapshots и семь analyses. Screenshots и download лежат в ignored `.artifacts/nl502-*` и не входят в Git.

По результатам walkthrough добавлено название текущего analysis в metrics panel и уточнён заголовок неподтверждённого candidate witness. Финальный build включает эти текстовые изменения; дополнительный визуальный проход после них не выполнялся. Полный screen-reader/keyboard audit, полный browser обход восьми queries, перенос witness в draft и recovery после аварийного завершения не заявляются проверенными.

## Следующий срез

NL-503: переносимый набор artifacts и явный import/read-only replay с проверкой trusted issuer, exact bindings, locks и tampering. Чистая установка, CI и recovery — NL-504; исследование понятности A/B/C с участниками — NL-505. Произвольный upload нормативных пакетов, multi-user authorization и публичное размещение в NL-502 не входят.
