# NormLab — roadmap

Обновлено: 2026-10-04. Основания — переписка «Проектирование правового движка» и локальные свидетельства реализации. Исходная точка реализации: commit `fe7f01c`.

Цель — наглядная исследовательская лаборатория для обсуждения реформы УК: структурного упрощения, сокращения числа норм и гуманизации наказаний через явные обязательные правила. Завершённые входы экспериментального reform profile должны определять единственный составной результат в объявленном scope.

Завершены **M0 и локальный демонстратор M1 A/B/C**: contracts/producer v2, independent decision/comparison/property verification, signed receipts, explanations, separate metrics, SQLite/HTTP/Laboratory UI и CLI export/replay. [Свидетельства NL-502](docs/LABORATORY_UI.md) фиксируют проверенный пользовательский flow и ограничения. Перенос и replay artifacts (NL-503) завершены; текущий срез — delivery (NL-504), часть его gates ещё открыта. Этот файл описывает текущий план; будущие пункты не считаются реализованными или доказанными.

## Основания и правила ведения

- [Замысел проекта](docs/VISION.md) — цель, однозначность, обязательность смягчения и границы гарантий.
- [Первый демонстратор A/B/C](docs/DEMONSTRATOR.md) — сценарий и критерии следующего среза.
- [Происхождение решений](docs/DESIGN_NOTES.md) — прямые авторские цели, инженерные предложения и открытые вопросы.
- [Contracts v2](docs/CONTRACTS.md), [семантика](docs/REFORM_SEMANTICS.md) и [проверки](docs/CONTRACT_VERIFICATION.md) — реализованное отдельное ядро нового профиля.
- [Lean decision verification v2](docs/REFORM_VERIFICATION.md) — независимое отношение, общие теоремы, kernel checks и границы гарантий.
- [Исходная архитектура](prototype/normlab-architecture/README.ru.md) — целевое описание компонентов и ограничений.
- [Решения и границы текущего MVP](docs/MVP.md) — фактически реализованный подход и trusted computing base.
- [Отчёт локальной проверки](docs/VERIFICATION.md) — свидетельства для исходного среза.
- [Инструкция запуска](README.md) — команды работы с приложением.

Статусы: `[x]` — выполнен описанный объём с указанными свидетельствами и границами; `[ ]` — запланировано либо частично реализовано. Спецификация, producer tests и formal proof имеют разные статусы. Решения со статусом **Open** требуют отдельного обоснования перед соответствующей реализацией. Наличие пункта в roadmap не является разрешением на публикацию данных или подключение внешнего AI-провайдера.

Каждый завершённый пункт должен ссылаться на реализацию и подходящую проверку. Для формальных гарантий дополнительно фиксируются утверждение, domain, assumptions и toolchain. Даты следующих этапов определяются после оценки конкретного среза.

Task IDs сохранены при изменении приоритетов: номер `NL-xxx` не определяет этап или порядок выполнения. Добавлены NL-107 и NL-108. Локальная демонстрация reviewed fixtures не зависит от AI, PostgreSQL, multi-tenancy или второго предметного домена.

## M0. Локальный сквозной срез — завершён

- [x] React UI: рабочая область, пакеты норм, сравнение редакций, история снимков.
- [x] TypeScript strict и ограниченные типизированные контракты Legal IR и certificate.
- [x] Один synthetic profile и две фиксированные редакции: множители срока 2/3 и 1/2.
- [x] Четыре состояния A: `unreviewed`, `established`, `refuted`, `not-established`.
- [x] Immutable snapshots, supersession, сохранение в SQLite и защита от lost updates.
- [x] Чистый интерпретатор, обязательный rule ledger, сохранение штрафа и условных ветвей.
- [x] Независимый checker и Lean kernel verification конкретных результатов; audit аксиом с явным allowlist.
- [x] Ed25519 receipts, экспорт входов и результатов, проверка подписи.
- [x] Привязка результата к snapshot, bundle и verifier identity; устаревшая проверка сохраняется как историческая.
- [x] Локальная production-сборка, 11 domain/API tests и 2 Lean integration tests; проверка UI на 1440 и 390 px.

**Граница:** две редакции одного правила подтверждают работу примера. Они ещё не подтверждают универсальность ядра. Сравнение редакций вычисляется на двух завершённых состояниях, отдельной formal comparison receipt нет. Полный Hypercode adapter, AI extraction, multi-tenant authorization, PostgreSQL/outbox и OS sandbox остаются впереди.

## M1. Содержательный демонстратор реформы A/B/C — локальный срез завершён

**Результат:** пользователь исследует один синтетический уголовно-правовой фрагмент, сравнивает последствия и проверяет смысл упрощения или реформы.

**Зависимость:** M0. До готовности соответствующих механизмов M3 используются локальные reviewed fixtures. Это этап расширения поддержанной семантики под конкретный исследовательский сценарий.

- [x] **NL-107 — Исследовательский fixture.** Зафиксированы [синтетический текст A/B/C, source mappings и D16](fixtures/reform-v1/README.md): две группы, три обстоятельства, два обязательных уменьшения и исключение. [Арифметический аудит](fixtures/reform-v1/VALIDATION.md) проверяет 48 вычислений, пять relations и учебный counterexample. Producer, decision/comparison verifier и поддержанный counterexample реализованы; HTTP/UI подключены в [NL-502](docs/LABORATORY_UI.md).
- [x] **NL-101 — Контракты.** Реализованы десять строгих [Zod/JSON schemas](docs/CONTRACTS.md) для Legal IR, NormPackage, SemanticProfile, NormBundle, snapshots, query, result, certificate и receipt. Зафиксированы совместимость v1/v2, encoding, units, bounds, unsupported cases и contextual bindings. [Проверка](docs/CONTRACT_VERIFICATION.md) включает Ajv Draft 2020-12, Unicode limits и schema freshness. Signed receipts/comparison verifier реализованы отдельно в NL-405; HTTP integration выполнена в [NL-502](docs/LABORATORY_UI.md).
- [x] **NL-102 — Семантика.** Реализован [profile demo.reform-mitigation/v1](docs/REFORM_SEMANTICS.md): typed scopes, completion, exact arithmetic, order M/N и exclusion E. Producer не выбирает behavior по fixture/rule ID. Проверены 384 snapshot/model combinations и 1296 branches. Существование/единственность подтверждены в NL-106; unsupported baseline profiles с диапазонами не сводятся к выбранной точке.
- [x] **NL-104 — Взаимодействие правил.** Реализованы producer/ledger и независимый [Lean decision verifier](docs/REFORM_VERIFICATION.md): обязательные M/N, exclusion E, порядок и один applyCount. Kernel отклоняет missing M/N, неверное exclusion, двойной учёт и повреждения ledger/steps с обходом TypeScript result guards. Pipeline подключён к локальному HTTP/UI в [NL-502](docs/LABORATORY_UI.md).
- [x] **NL-106 — Formal properties.** Реализовано независимое [Lean relation](lean/Reform.lean): soundness, outcome/mandatory-rule completeness принятого result и existence/uniqueness любого WellFormed model на D16. [Проверены](docs/REFORM_VERIFICATION.md) все 384 A/B/C results и 1296 branches, девять общих теорем, binding attacks и unsupported/inconclusive statuses. Универсальная верификация TypeScript code не заявляется; comparison/property queries реализованы в NL-405.
- [x] **NL-404 — Comparison contract.** Реализован [query/certificate/receipt contract](docs/CONTRACTS.md) с отдельными baseline/candidate, D16, identity mapping и точными scopes properties. Перестановка roles, скрытое сужение domain и ложный coverage отклоняются. Для иных mappings и диапазонов требуется отдельная поддержка; comparison proofs/receipts реализованы в NL-405.
- [x] **NL-405 — Comparison proofs.** [Lean проверяет](docs/COMPARISON_VERIFICATION.md) equivalence A/B, три свойства A/C, unary M mitigation A/B/C и bound counterexample поддержанной ошибочной поправки. Четыре общие scope/witness theorem проходят axiom audit; corpus не получает universal coverage. Signer сам проверяет certificate; receipts связывают statement/query/models/assumptions/toolchain. Восемь demo exports проходят fresh replay с explicit trusted key; 13 новых ложных statements отклонены kernel. HTTP/UI v2 реализованы в [NL-502](docs/LABORATORY_UI.md).
- [x] **NL-406 — Объяснения.** [Core/CLI projector и renderer](docs/EXPLANATIONS.md) показывают полный ledger, numeric steps, findings/completion assumptions, source sections, scope и отдельные signature/proof/coverage/current statuses. Decision читает certificate derivation; general queries восстанавливают trace из locked model и связывают его с certified outcome. Sidecar проверяется через fresh replay и deterministic reconstruction; он не подписан receipt и не является отдельным Lean proof. Проверены все 384 explanations / 1296 branches; demo сохраняет 12 exports с JSON/Markdown explanations. UI реализован в [NL-502](docs/LABORATORY_UI.md).
- [x] **NL-108 — Метрики упрощения и изменений.** Реализованы [методика, projector и CLI](docs/METRICS.md): source provisions, IR templates/repeats и expansion, reviewed definitions/text references, conditions/exceptions/human judgment, категории (group, baseline M) и отдельные consequence components. Exact scope/coverage, annotations и generator связаны digest; JSON sidecar проверяется через fresh replay и recount. Demo сохраняет 12 metrics reports; все 12 sidecars прошли отдельный CLI replay: A/B 0/16 изменений, A/C 8/16 только срока; conditional exclusion сохраняет 2 completions при 1 outcome. Typecheck/build/schema freshness проходят; test suites этого этапа не запускались. Метрики не имеют отдельного Lean proof и не образуют «индекс гуманности». HTTP/UI реализованы в [NL-502](docs/LABORATORY_UI.md).
- [x] **NL-502 — Laboratory UI.** [Реализованы и проверены](docs/LABORATORY_UI.md) v2 snapshots/analysis/export в SQLite и HTTP, A/B/C для одного snapshot, составные последствия, полный ledger, источники, отдельные metrics и proof/coverage statuses. Есть counterexample explorer, findings revisions и история с fresh replay. Browser walkthrough подтвердил A/B/C, conditional exclusion, старую ревизию, download/replay, layout 1440/390 px и базовый keyboard focus. Добавлены пять storage/API regression tests. Полный accessibility audit, внешний import и публичное размещение остаются отдельными задачами.

**Критерии готовности:** выполнен [сценарий демонстратора](docs/DEMONSTRATOR.md). A/B/C проходят общий pipeline; A/B сохраняют последствия во всём объявленном D; C имеет единственный результат на завершённых входах и проверенное заявленное свойство. Пропуск обязательного смягчения обнаруживается. Counterexample воспроизводится, метрики не смешиваются с semantic proof, неподдержанные запросы получают `unsupported` или `inconclusive`.

**Принято для этого среза:** TypeScript producer и отдельный Lean checker. [Обоснование и ограничения](docs/CONTRACTS.md) сохранены в документации. Перенос в compiled Lean возможен как отдельное техническое решение с сохранением контрактов и независимого отношения. Hypercode сохраняет ответственность за композицию и resolved IR; юридическая семантика принадлежит NormLab.

## M2. Authoring, модель дела и human review

**Результат:** нормативные пакеты имеют воспроизводимый authoring pipeline; пользователь разбирает несколько дел с несколькими участниками, эпизодами и мотивированными установлениями.

**Зависимость:** контракты M1. До внедрения авторизации M3 режим остаётся локальным и simulated.

- [ ] **NL-103 — Сборка пакетов.** Реализовать путь authoring → reference Hypercode resolved IR → доменный adapter → Legal IR → locked NormBundle. Проверять ссылки, dependency locks, совместимость профиля и source mappings. Semantic и provenance digests учитывать отдельно. M1 может использовать вручную подготовленные reviewed bundles.
- [ ] **NL-201 — Case workspace.** Создание и выбор нескольких дел, ревизии narrative, типизированные участники, эпизоды, propositions и applicability context.
- [ ] **NL-202 — Claims и evidence.** Отдельные attributed claims со ссылками на speaker, revision и source span; evidence references и сохранение противоречий.
- [ ] **NL-203 — FindingEvent.** Append-only события с rationale, signer/actor identity, scope полномочий, временем и `supersedes`. Конфликтующие установления хранятся явно; процедурный эффект задаётся профилем.
- [ ] **NL-204 — Snapshot и applicability.** Детерминированно строить снимок из истории; фиксировать точные bundle, interpretations и временной контекст применения. Изменение значимого входа создаёт новое вычисление.
- [ ] **NL-205 — Review flow.** Разделить исходный текст, claims, findings и открытые вопросы; поддержать исправление, просмотр истории и переход от условного вывода к завершённому. Вопросы выводятся из незакрытых формальных условий.

**Критерии готовности:** пакет воспроизводимо собирается с точными locks и source mappings; каждое установление прослеживается до автора, основания и события. Цитата или AI proposal не становятся finding автоматически. Изменение одного эпизода сохраняет старые квитанции и корректно определяет, какие результаты утратили актуальность. `Not-established` не превращается в `refuted` без явно принятого правила профиля.

## M3. Надёжное выполнение и границы доверия

**Результат:** задания воспроизводятся после сбоев, а обработка недоверенных данных выполняется с обеспеченными runtime-ограничениями.

**Зависимость:** стабильные контракты M1 и события M2. Этот этап обязателен перед загрузкой недоверенных пакетов и многопользовательским доступом.

- [ ] **NL-301 — Persistence.** Внедрить PostgreSQL, миграции, transactional state/event/outbox, read projections и object storage. Подготовить перенос существующих локальных сценариев.
- [ ] **NL-302 — Durable jobs.** Выделить builder, analyzer и verifier workers; обеспечить at-least-once delivery, idempotency, retries, cancellation, лимиты ресурсов и восстановление после завершения процесса. Поздний результат не перезаписывает текущую проекцию.
- [ ] **NL-303 — Sandbox.** Реализовать deny-network и ограничения filesystem/secrets на уровне выбранной среды. Закрыть absolute paths, traversal, symlink escape и выход imports за package root/allowlist; проверять архивы до распаковки.
- [ ] **NL-304 — Verifier release.** Зафиксировать полную toolchain identity, включая библиотеки и trusted adapters; выпускать reviewed profiles/checkers отдельно от нормативных данных. Проверять statement binding и транзитивный axiom allowlist. Оценить дополнительный независимый proof checker.
- [ ] **NL-305 — Authorization.** Ввести tenant/case capabilities и server-verified authority для findings, review и активации пакетов. Изоляцию tenants подтвердить негативными проверками.
- [ ] **NL-306 — Эксплуатация.** Добавить управление ключами issuer, ротацию, backups/recovery, retention/deletion с tombstones, безопасные логи и метрики. Измерять latency этапов, очередь, долю `inconclusive`/`unsupported`, CPU, память и диск.

**Критерии готовности:** crash/retry/duplicate/cancel не создают ложный `verified`; sandbox действительно блокирует запрещённые действия; повреждённые артефакты и несовпадающие bindings отклоняются. Recovery сохраняет историю и проверяемую issuer identity. Данные одного tenant недоступны другому.

**Open:** целевая deployment platform, механизм sandbox, queue/object storage и управление секретами. Сначала определить требования и threat model, затем выбрать реализации. Численные performance budgets фиксируются по воспроизводимому benchmark corpus.

## M4. Расширение: AI-assisted review и переносимость

**Результат:** AI помогает подготовить модель дела, а второй предметный домен проверяет переносимость ядра. Эти направления могут выполняться независимо.

**Зависимость:** AI использует human review из M2 и необходимые ограничения доступа/данных из M3; внешний provider подключается после настройки передачи данных и provider policy. Для локального второго домена достаточно контрактов и package pipeline M1–M2. Сам демонстратор A/B/C не зависит от M4.

- [ ] **NL-401 — AI adapter.** Ввести заменяемую границу провайдера, structured proposals, provenance, budgets и явную настройку внешней передачи данных. Согласовывать retention policy с фактическими возможностями провайдера.
- [ ] **NL-402 — Extraction/review.** Извлекать claims с attribution и source spans, предлагать трактовки и формулировки вопросов. Человек принимает изменения через M2; AI не получает write-доступ к accepted findings, опубликованным нормам или статусу verification.
- [ ] **NL-403 — Устойчивость к недоверенному вводу.** Проверять prompt injection в материалах, schema failures, противоречия, неподтверждённые ссылки и timeout. Полнота поиска норм определяется formal scope, а не ответом AI.
- [ ] **NL-105 — Второй домен.** Добавить семантически иной синтетический пакет, например право на выплату с пороговыми условиями и исключением. Конкретный пример — предложение; пакет должен проверять другие типы условий и последствий. Выявленные расширения semantic profile оформлять явно, без специальных ветвей по ID пакета.

**Критерии готовности AI:** пользователь проходит путь narrative → proposals → human findings → analysis → receipt без ручного редактирования IR; AI не может сам принять finding или выставить `verified`. Если добавлены AI explanations, они проверяются на соответствие структурированным данным NL-406.

**Критерии переносимости:** семантически иной пакет подключается без условий по его ID в backend и проходит общий interpreter/checker pipeline. Зафиксированы поддержанные и неподдержанные свойства, domain и изменения профиля.

## M5. Публичная лаборатория и воспроизводимый release

**Результат:** исследовательские эксперименты можно безопасно демонстрировать и воспроизводить в объявленной конфигурации.

**Зависимость:** содержательный сценарий M1 и воспроизводимость выбранной конфигурации. Для размещённого интерактивного сервиса необходимы соответствующие M2/M3 gates: права, изоляция, сохранность данных и эксплуатация. AI и второй домен из M4 не обязательны. Публикация artifacts и размещение сервиса оформляются отдельными действиями.

- [ ] **NL-501 — Publication flow.** Synthetic-only gate, disclosure review и immutable publication. Анализ частного дела не вызывает публикацию как побочный эффект; публичный artifact содержит только разрешённые данные.
- [x] **NL-503 — Reproducibility.** [Реализованы](docs/EXPERIMENT_TRANSFER.md) набор 1–12 signed exports с manifest/runtime locks, explicit issuer trust, exact registry/bindings checks, CLI и HTTP/UI read-only import, отдельная immutable история и fresh replay перед сохранением. CLI перенос пяти результатов A/B/C/A→B/A→D в отдельный data directory подтвердил current evidence. HTTP regressions отклоняют wrong issuer, lock/binding/signature/manifest/annotation tampering, unknown model/version/role и подписанный `unsupported` proof claim; все отказы оставляют history пустой, включая повреждение второго item в multi-item import. Повторный импорт идемпотентен. Два snapshot revisions переносятся с точным `supersedes`, не изменяя receiving workspace. Проверены imported history и workspace persistence после перезапуска, fresh replay при повторном открытии, UI import переданного пользователем export и download gesture в Safari. Обычный domain/API suite 42/42 и Lean integration suite 14/14 прошли; остальные проверки перечислены отдельно в [отчёте NL-503](docs/EXPERIMENT_TRANSFER.md). Playwright/Browser Preview download automation остаётся проблемной (`reading 'url'`, `about:blank`), но Safari Computer Use подтвердил скачивание в обычном браузере; connector failure не приписывается backend без evidence. Перенос полной SQLite history и чистая установка не входят в этот transfer scope; хеширование публичных персональных полей не использовать вместо disclosure policy.
- [x] **NL-504 — Delivery (локальный single-user demonstrator).** CI с pinned GitHub Actions и quality gates проходит на `main`: [run 37182074599](https://github.com/SoundBlaster/NormLab/actions/runs/37182074599) для `d7dd98d` завершился success. Workflow проверяет форматирование, type-aware lint, TypeScript, unit/API и Lean integration tests, schema freshness и production build; Dependabot еженедельно проверяет npm и GitHub Actions. [Release notes v0.1.0](docs/RELEASE_NOTES.md) подготовлены как draft, не как опубликованный GitHub Release. [Runbook](docs/DEPLOYMENT.md) описывает Compose, loopback-доступ, ключи, backup и restore; clean-image build, replay и восстановление volume подтверждены ранее. Тест [migration engine](tests/database-migrations.test.ts) покрывает synthetic upgrade v1→v2 с сохранением данных, атомарный rollback неудачной v3, исправленный retry, idempotence и `integrity_check`. Это не migration-specific proof для будущего изменения таблиц приложения; при реальной следующей schema version нужен отдельный regression и upgrade/rollback guidance. Branch protection и repository rulesets недоступны текущему плану private repository (GitHub API отвечает 403), поэтому hosted CI не является обязательным серверным merge gate.
- [ ] **NL-505 — Research pilot.** Зафиксировать corpus и методику: воспроизводимость, охват scope, причины `inconclusive`/`unsupported`, понятность оснований и способность участников объяснить различие A/B/C. Измерять структуру, сложность решения и изменения последствий отдельно. Влияние прозрачности на разработку гуманных норм исследовать как гипотезу; социальный эффект не выводить из formal verification.

**Критерии готовности:** опубликованный эксперимент воспроизводится с тем же семантическим результатом и проверяемыми bindings; закрытые материалы не появляются в artifacts или telemetry; заявленные release gates подтверждены сохранёнными свидетельствами.

**Опционально после стабильного export contract:** интеграция со SpecGraph через IDs, provenance и receipts. Предложение `spec_ref` / `SpecBinding` сохранено в [заметках проектирования](docs/DESIGN_NOTES.md); готовый API не заявляется. Интеграция не является обязательной зависимостью чистого ядра или verifier.

## Ближайший рабочий срез

**M1 завершён для текущего synthetic fixture и локальной конфигурации; NL-503 закрыт в объявленных transfer границах. NL-504 завершён в границах локального delivery.** Подтверждены hosted CI на текущем `main`, Compose runbook/backup/restore, release-notes draft и synthetic versioned migration upgrade/rollback path. Ограничения: GitHub не даёт включить branch protection для текущего private repository plan; migration-specific тесты для будущей реальной schema version появятся вместе с этой миграцией. Незавершённый client-side draft остаётся отдельным UX-вопросом, не gate переносимости NL-503.

**Ближайший продуктовый срез — локальный парковочный пилот для Москвы.** [Согласованный план интервью](docs/PARKING_PILOT_PLAN.md) фиксирует один нормативный фрагмент, AI extraction с ручным review каждого утверждения, выбор эпизода, пробелы/противоречия, пересчёт, условные ветви и историю ревизий. Подготовлены source/conditions draft, synthetic corpus, candidate ontology packages и [extraction contract](docs/PARKING_EXTRACTION_CONTRACT.md) с JSON Schema, prompt и graph validator. HTTP/UI extraction ещё не подключены. Подготовлены [candidate reference graphs P01/P02/P04/P09](fixtures/parking-pilot/reference/README.md), с source/ref validation в CI. Первый [baseline GPT OSS 20B](docs/PARKING_BASELINE_2026-10-04.md) выполнен: 0/4 принятых proposals. Следующий шаг — typed predicate catalogue, quote anchoring и новая отдельная серия. Этот срез затрагивает будущие возможности event model и AI; завершённость synthetic M1 на него не переносится. NL-505 сохраняется как исследовательская задача: методику и метрики следует согласовать с новым corpus; сравнение A/B/C остаётся отдельным существующим экспериментом.

## Условия завершения этапов

- Реализация, спецификация и ограничения согласованы; runtime enforcement подтверждён отдельно от деклараций конфигурации.
- Положительные сценарии и относящиеся к изменению негативные проверки выполнены; исходные требования не заменены удобными для реализации свойствами.
- Proof status, coverage status, model provenance и фактическая проверка не смешиваются в одном признаке успеха.
- Документация и свидетельства обновлены; неготовые пункты остаются открытыми с конкретной причиной.
- Переход к следующему этапу определяется его зависимостями и критериями готовности, а не только наличием работающего UI или успешной сборки.

### Первичные источники норм и воспроизводимость

[Candidate design](docs/NORM_SOURCE_PROVENANCE.md) фиксирует прямые ссылки на официальные публикации, edition identity, immutable source snapshots и SHA-256, fragment locators, semantic review и связи rule → fragment. В UI планируются отдельные цепочки «основания по фактам» и «основания по нормам». Для пилота достаточно одного fixed reviewed NormPackage; старые результаты сохраняют использованную редакцию.

- [ ] Реализовать source snapshot/fragment schema и storage.
- [ ] Закрыть normative lock parking fragment по официальным публикациям и релевантным изменениям.
- [ ] Добавить rule provenance bindings и раскрытие первоисточников в результате/UI.

### Parking baseline evidence — 2026-10-04

[Первый ограниченный прогон](docs/PARKING_BASELINE_2026-10-04.md) выполнен: 0/4 принятых proposals. Обнаружены schema/ref/source проблемы, неполный link vocabulary в prompt, provider error и timeout. AI readiness gate остаётся открытым.

- [x] Передавать модели typed link predicate catalogue с domain/range.
- [ ] Проверить совместимость provider structured output без silent fallback.
- [x] Спроектировать application quote anchoring с handling неоднозначных цитат.
- [x] Провести следующую отдельную серию и semantic review, сравнив с сохранённым baseline.

### Typed extraction и quote anchoring — 2026-10-05

[Model contract v2](docs/PARKING_TYPED_EXTRACTION.md) передаёт typed link catalogue и разрешает exact quotes приложением с явным occurrence для повторов. Replay четырёх reference graphs восстановил исходные offsets. [Вторая серия](docs/PARKING_TYPED_BASELINE_2026-10-05.md): 4/4 JSON responses, 0/4 accepted proposals; shape и semantic проблемы сохраняются. AI readiness gate остаётся открытым. Следующий ход — отдельная проверка provider structured output и constrained-shape серия; при сохранении semantic потерь рассмотреть упрощённый промежуточный extraction contract.

### Luna low comparison — 2026-10-05

[Сравнение через Codex CLI](docs/PARKING_LUNA_COMPARISON_2026-10-05.md): 4/4 shape/quote pass и 1/4 structural pass при том же application input. P09 проходит validator, но теряет отрицание оплаты из assertions; semantic readiness gate остаётся открытым. Следующий ход — независимый checklist сохранения отрицаний/противоречий, evidence support и обязательных unknowns, затем statement-first extraction с построением графа приложением. Сравнение не изолирует эффект модели от Codex context/decoding/transport.

### Evaluation и statement review — 2026-10-05

[Методика](docs/EVALUATION_PLAN.md), [setup](docs/EVALUATION_SETUP.md), [результаты](docs/PARKING_EVALUATION_2026-10-05.md): MLflow registry, candidate expectations, single-pass LangExtract и двухэтапное literal discovery → classification. Реализован HTTP/UI этап выделения и ручного review утверждений с immutable revisions. Это не полный ontology graph и не КоАП calculation. Двухэтапная серия: 2/4 statement gate, 0/4 всех candidate checks; цель 80% не достигнута, release score pending.

- [x] Хранить raw outputs, intermediate fragments, prompts, source hashes и scorer snapshots.
- [x] Дать пользователю выделение текста, правку и подтверждение каждого утверждения.
- [ ] Провести browser walkthrough нового review flow.
- [ ] Независимо разметить semantic ошибки и расширить holdout.
- [x] Подготовить [source discovery pack](fixtures/parking-pilot/corpus/README.md): 15 leads и 10 unlabelled editorial candidates; [collection plan](docs/CORPUS_COLLECTION_PLAN.md) отделяет development, holdout и population sampling.
- [ ] Сверить и разметить source candidates, добрать development corpus до 30–50 distinct cases; текущие новости не являются representative benchmark.
- [ ] Улучшить discovery coverage и классификацию polarity без неподдержанных выводов.
- [ ] Построить ontology graph из reviewed assertions и подключить legal calculation.
- [ ] Включить Evidently при появлении пользовательского потока и согласованных drift metrics.

### Synthetic corpus и forum/court discovery — 2026-10-05

Подготовлены [40 synthetic inputs в восьми families](fixtures/parking-pilot/synthetic-v1/README.md) с отдельными candidate probes и model-only inputs. [Source registry](fixtures/parking-pilot/corpus/README.md) расширен до 24 leads и 15 editorial candidates, включая [форумы и судебные зеркала](docs/COURT_AND_FORUM_SOURCES.md). Это development material, не independent holdout.

[Первый scored-прогон](docs/SYNTHETIC_EVALUATION_2026-10-05.md): 40/40 model calls завершились без извлечённых утверждений, structural pass 0/40; 36 discovery responses пусты, 4 скопировали demo-example из prompt. Ни один кейс не достиг classification. Это diagnostic baseline для конкретного GPT OSS 20B + LangExtract pipeline, не оценка 80% quality и не population estimate.

- [x] Разделить synthetic inputs, provenance и reviewer-only labels.
- [ ] Сверить официальные акты, source facts и candidate semantic expectations.
- [x] Подключить dataset-aware runner/scorer; сохранить полный scored baseline по 40 synthetic cases и family-level breakdown.
- [x] Разобрать empty/unanchored discovery outputs и зафиксировать следующую версию extraction pipeline до нового прогона.
- [x] Уточнить [rubric](docs/EVALUATION_PLAN.md): faithful extraction вместо проверки исторической истинности; конкретные gaps и корректное недостаточно-данных считаются положительным результатом, blanket refusal — нет.
- [ ] Реализовать gap detection и sufficiency scoring отдельно от extraction; оценивать relevance уточнений и необоснованные definitive conclusions.

### Direct discovery v2 — 2026-10-05

[Отдельный candidate и сравнение](docs/DISCOVERY_V2_2026-10-05.md): русский direct prompt без demo, exact anchoring, сохранение `speaker` в review contract. Три development probes прошли quote/attribution checks. В 40-case прогоне все кейсы достигли classification; structural pass 39/40, selected assertion-probe pass 11/40. Discovery покрывает 44/46 контрольных spans, но 22 покрытых spans не получили classification. AI readiness gate открыт; HTTP worker пока использует v1.

- [x] Реализовать отдельно versioned discovery candidate, сохранить raw requests/responses и повторить 40-case evaluation.
- [x] Сохранить источник утверждения в v2 statements и дать ручную правку в review UI.
- [x] Сделать classification candidate с обязательным результатом для каждого fragmentId, explicit unknown и непустым valueText; отдельно считать omissions и polarity.
- [ ] Закрыть пропуски discovery в SYN019/SYN033 и привязку к другому автомобилю в SYN030.
- [ ] Провести независимый semantic review и browser walkthrough перед promotion v2 в HTTP/UI.

### Complete classification v3 — 2026-10-05

[Контракт и controlled comparison](docs/CLASSIFICATION_V3_2026-10-05.md): обязательное решение для каждого fragmentId, explicit unrelated reason, runtime validation и девять offline checks в CI. На неизменных 82 fragments v2 модель представила все 82 ID; 79 решений приняты, два case responses отклонены. Selected assertion-probe pass вырос с 11/40 до 28/40, structural pass снизился с 39/40 до 38/40. Это не оценка 80% critical-error-free; на момент controlled comparison HTTP/UI оставался на v1 (подключение v3 описано ниже).

- [x] Сохранить controlled replay, parent digests, полные ответы и отдельно сравнить submitted coverage / accepted decisions / semantic probes.
- [x] Проверить три свежих end-to-end cases без replay.
- [ ] Разобрать 12 semantic-probe failures: unknown, отрицания, интервалы, другой автомобиль, место и ошибки реквизитов.
- [ ] Проверять evidence support каждого predicate; не переносить место/режим из соседнего fragment без provenance binding.
- [ ] Устранить status/reason grammar inconsistency отдельной версией, сохраняя ошибки текущего прогона в denominator.

### Локальное демо с ручной правкой — 2026-10-05

[Результат подключения и browser walkthrough](docs/ASSISTED_DEMO_V3_2026-10-05.md). Цель демо снижена до **50% кейсов без критических ошибок до ручной правки**, 80% остаётся дальнейшей целью. Достижение 50% ещё не подтверждено: 28/40 selected semantic probes не покрывают всю метрику. V3 подключён как экспериментальные предложения для обязательного human review; AI readiness gate не закрыт.

- [x] Подключить свежий discovery v2 → classification v3 к HTTP/UI, принимать только model/pending statements с точной цитатой.
- [x] Проверить в Browser Preview ручную правку реальных предложений, подтверждение, checklist, сброс после следующей правки и read-only историю.
- [x] Зафиксировать regression test сохранения ревизий и сброса после изменения speaker.
- [ ] Добавить отдельные structured gap proposals и их ручную проверку: сейчас неизвестные обстоятельства записываются только в rationale.
- [ ] Проверить ручное добавление выделенного текста, отказ модели и экспорт отдельным browser проходом.
- [ ] Провести независимую разметку критических ошибок кейсов и оценить цель 50% до вмешательства пользователя.
- [ ] Подключить проверенные утверждения и gaps к ontology graph и правовому расчёту; review сам по себе расчётом не является.

### Общая дизайн-система — 2026-10-05

[UI foundation и правила развития](client/shared/ui/README.md): semantic tokens и небольшие reusable React primitives. Парковочный review и главная форма A/B/C используют общие поля, кнопки, панели и статусы; CSS парковки содержит layout и оформление domain editor. `StatementEditor` отделён от состояния экрана.

- [x] Вынести цвета, интервалы, размеры controls, radii и состояния в общую основу.
- [x] Перевести parking review и основную форму A/B/C на shared components; убрать повторяющиеся базовые стили.
- [x] Проверить refs/выделение цитаты, ручное добавление и редактирование pending statement без сохранения учебной правки.
- [ ] Новые gap proposals собирать из тех же primitives.
- [ ] Постепенно мигрировать legacy M0 и оставшиеся Views/Transfer с compatibility selectors.

### Frontend architecture: FSD

- [x] Separate app composition from page workflows, including legacy M0.
- [x] Public APIs, aliases and shared UI under `client/shared/ui`.
- [x] Steiger enforces layer boundaries, public APIs and import locality in local lint and CI.
- [ ] Build the parking gaps editor using the same shared primitives and page-local model.

See [frontend architecture](client/ARCHITECTURE.md).
