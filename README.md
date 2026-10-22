# NormLab

## Парковочный extraction pilot

Реализован локальный двухэтапный разбор текста: дословные assertions через LangExtract, затем классификация по predicates и polarity. Экран «Парковка · Разбор текста» поддерживает выделение цитат, ручные правки, подтверждение каждого утверждения и историю ревизий. Это этап извлечения, ещё без правового расчёта.

[Установка и пользовательский путь](docs/EVALUATION_SETUP.md) · [Методика и цель 80%](docs/EVALUATION_PLAN.md) · [Диагностические результаты](docs/PARKING_EVALUATION_2026-10-05.md). MLflow хранит candidate checks отдельно от экспертной оценки; достижение 80% пока не подтверждено.

[Подготовка hosted inference](docs/HOSTED_INFERENCE.md): серверные адаптеры OpenAI и TypeSafe, точные пути секретов и изолированный выход через allowlist proxy. Production inference включается отдельно; наличие кода не подтверждает доступность провайдера или качество извлечения.

Norms for People

Исследовательская лаборатория для проектирования и публичного обсуждения реформы уголовного закона: упрощения структуры норм, объяснимого определения последствий и обязательного смягчения при установленных обстоятельствах.

Реализован локальный демонстратор A/B/C на синтетических правилах: мотивированные findings, неизменяемые snapshots, сравнение последствий, Lean verification, подписанные receipts и экспорт для независимого replay. Laboratory UI показывает источники, rule ledger, метрики структуры и counterexamples.

## Лицензия

Исходный код доступен для изучения и разрешённых лицензией некоммерческих целей по **PolyForm Noncommercial License 1.0.0**. Использование в коммерческих целях требует отдельного письменного разрешения. Лицензия содержит оговорённые категории разрешённых организаций и целей — см. [полный текст лицензии](https://polyformproject.org/licenses/noncommercial/1.0.0). Это source-available лицензия, не OSI-approved open source.

## Документация

- [План парковочного пилота](docs/PARKING_PILOT_PLAN.md): согласованный локальный сценарий для Москвы, review AI-утверждений, ревизии, этапы и критерии готовности; реализация ещё не начата.
- [Release notes v0.1.0 (draft)](docs/RELEASE_NOTES.md): возможности локального demonstrator, запуск и подтверждённые ограничения; GitHub Release ещё не опубликован.
- [Замысел и требования](docs/VISION.md): однозначность, обязательность смягчения, модели A/B/C и границы гарантий.
- [Laboratory UI](docs/LABORATORY_UI.md): пользовательский flow, v2 HTTP API, хранение, проверенные сценарии и ограничения.
- [Перенос эксперимента](docs/EXPERIMENT_TRANSFER.md): manifest/locks, explicit issuer trust, read-only import и CLI replay.
- [Первый демонстратор](docs/DEMONSTRATOR.md): сценарий, свойства и критерии готовности M1.
- [Reform fixture v0.1.0](fixtures/reform-v1/README.md): конкретный синтетический текст A/B/C, все 16 завершённых случаев и арифметический аудит.
- [Контракты v2](docs/CONTRACTS.md), [семантика нового профиля](docs/REFORM_SEMANTICS.md) и [отчёт проверки](docs/CONTRACT_VERIFICATION.md): ядро A/B/C, JSON schemas и bindings; v2 flow работает рядом с исходным M0/v1.
- [Независимая Lean verification v2](docs/REFORM_VERIFICATION.md): decision certificates A/B/C, общие теоремы и проверка всех 384 snapshots.
- [Comparison proofs и signed receipts v2](docs/COMPARISON_VERIFICATION.md): equivalence A/B, свойства A/C, bound counterexample и CLI export/replay.
- [Deterministic explanations](docs/EXPLANATIONS.md): полный ledger, finding/completion origins, source sections, числовые различия и проверка JSON sidecar.
- [Метрики структуры и изменений](docs/METRICS.md): единицы подсчёта source/IR, условия/human judgment и отдельные изменения components в exact scope.
- [Основания проектирования](docs/DESIGN_NOTES.md): авторские цели из переписки, происхождение решений, роль Hypercode и предложение интеграции со SpecGraph.
- [Roadmap](roadmap.md): этапы, зависимости и актуальные приоритеты.
- [Текущий MVP](docs/MVP.md) и [отчёт его проверки](docs/VERIFICATION.md): реализованные возможности, API и конкретные свидетельства.
- [Проверки качества кода](docs/QUALITY.md): линтер, форматтер, CI и документированные исключения.
- [Frontend architecture](client/ARCHITECTURE.md): FSD layers, public APIs, ownership и Steiger gate.
- [Исходная архитектура v0.1.0](prototype/normlab-architecture/README.ru.md): сохранённый проект из архива.

## Запуск

Нужен Node.js 22.18+ и npm. Для формальной проверки нужен **Lean 4.30.0**, зафиксированный в `lean-toolchain`.

### Запуск в Docker Compose

С Docker Desktop или Docker Engine с Compose plugin чистый запуск не требует Node.js/Lean на хосте:

```sh
docker compose up --build -d
docker compose ps
```

Открыть **http://127.0.0.1:4317**. Первый build скачает Lean 4.30.0. Данные SQLite и signing key сохраняются в именованном volume `normlab_normlab-data`; обычный `docker compose down` его сохраняет. Инструкции остановки, сброса и границы безопасного локального использования — в [руководстве развёртывания](docs/DEPLOYMENT.md).

```sh
npm ci
npm run dev
```

Открыть **http://127.0.0.1:4317**. Сервер слушает только loopback. Порт можно изменить через `PORT`.

Для запуска собранного интерфейса:

```sh
npm run build
npm start
```

В меню на desktop и под навигацией на mobile показаны время сборки UI (UTC)
и короткий commit SHA; полный SHA доступен в подсказке. В dev-режиме подпись
«Разработка» показывает время запуска dev-сервера. Без переданного commit
интерфейс честно сообщает «commit неизвестен».

GitHub передаёт SHA автоматически при публикации образа. Для собственной сборки
можно явно задать `NORMLAB_BUILD_REVISION` (полный SHA):

```sh
NORMLAB_BUILD_REVISION="$(git rev-parse HEAD)" npm run build
NORMLAB_BUILD_REVISION="$(git rev-parse HEAD)" docker compose build
```

Используйте SHA для чистого checkout: он обозначает исходники сборки. Метаданные
встраиваются во frontend при сборке; перезапуск контейнера их не меняет.

Lean устанавливается через [официальный elan](https://lean-lang.org/install/manual/). Если elan уже установлен:

```sh
elan toolchain install leanprover/lean4:v4.30.0
```

Приложение ищет `lean` в `~/.elan/bin`, затем в `PATH`. Можно явно задать `LEAN_BIN`. Если нужного Lean нет, сервис продолжает работать, а проверка получает **inconclusive**. Статус **verified** без успешной проверки Lean не выдаётся.

## Первый эксперимент

1. В открытой по умолчанию вкладке «Реформа A/B/C» нажать «Сравнить A/B/C». Исходный K1 snapshot с установленным M даёт 80/80/60 месяцев; штраф — 200 000 DEMO во всех моделях.
2. Установить E, оставить N в состоянии «Не установлено» и записать соответствующие основания. Нажать «Сохранить и сравнить A/B/C»: новая ревизия сохранит две completion-ветви, даже если их числовые последствия совпадают.
3. В «Разобрать вывод» выбрать ветвь `N=true, E=true`: ledger показывает исключение N и обязательное применение M. Раскрыть правило, чтобы увидеть источник и числовой шаг.
4. В «Свойства и counterexamples» проверить A→B или свойства A→C на объявленном domain. Запросы свойств не сужаются findings выбранного snapshot.
5. Выбрать «A → D: исследовать ошибочную поправку»: появится counterexample вне M, 90→80 месяцев. В «Метрики» сравнить структуру A/B/C и компоненты последствий текущего query.
6. Скачать «Export и receipt» и «Public key», затем выполнить `npm run reform:verify -- <export.json> --issuer-key <issuer-public.pem>`. Доверие ключу задаётся пользователем; подпись сама по себе не заменяет fresh Lean replay. В «История» доступны прежние snapshots и проверки свойств.

Текст сценария вводится вручную и не преобразуется в факты автоматически. Используйте только вымышленные данные: это однопользовательское локальное демо с simulated reviewer. Исходный M0 доступен в меню «Пример M0». В «Перенос эксперимента» можно объединить выбранные signed results в набор и импортировать его с отдельно выбранным trusted public key.

## Что реализовано

- Laboratory UI: A/B/C, findings M/N/E, immutable history, sources, полный rule ledger, отдельные metrics, свойства, counterexamples и exports; desktop/mobile layout. Исходный M0 UI сохранён.
- V2 storage/HTTP: отдельные append-only таблицы, защита от lost updates, сохранение exact query/bundles/certificate/receipt/annotations и fresh replay перед текущим proof status.
- TypeScript strict и Zod: ограниченный Legal IR, четыре состояния установления, сертификат и контракт API.
- SQLite: транзакционное создание снимков, supersession, optimistic concurrency; триггеры запрещают UPDATE/DELETE снимков.
- Чистый TypeScript interpreter: точная целочисленная арифметика в ограниченном профиле, обязательная поправка и сохранение штрафа.
- Независимый checker: проверяет bindings, полноту ветвей и ограничения без вызова интерпретатора.
- Lean: `Permissible` и `ValidResult`, доказательства единственности отдельных последствий, kernel-проверка конкретного результата через `by decide`.
- Audit транзитивных аксиом для теоремы `NormLab.checked`: разрешена только стандартная `propext`; `sorryAx`, native-evaluation и custom axioms не допускаются.
- Ed25519 receipt: snapshot, semantic/provenance, query, result, certificate, statement, toolchain и assumptions digests. Экспорт содержит входы для воспроизведения.
- Ограничение одновременно выполняемых проверок, дедупликация успешных заданий, timeout и Lean memory/heartbeat budgets.

Сравнение редакций M0 — исчерпывающий перебор двух завершённых состояний исходного профиля. Laboratory UI использует ядро v2 и formal comparison receipts A/B/C. Гарантии относятся к locked models, findings и заявленному scope; fidelity перевода нормативного текста и истинность обстоятельств требуют human review.

## A/B/C: локальный proof/export flow

```sh
npm run reform:demo
npm run reform:verify -- <run>/AB-equivalence.json --issuer-key <run>/issuer-public.pem
npm run reform:explain -- <run>/C-conditional-decision.json --issuer-key <run>/issuer-public.pem
npm run reform:metrics -- <run>/AB-equivalence.json --issuer-key <run>/issuer-public.pem --annotations <run>/source-annotations.json
```

Demo выводит путь `<run>` и сохраняет 12 exports, JSON/Markdown explanations и metrics reports, exact source annotations, manifest и публичный ключ в `.artifacts/`. Подтверждены equivalence A/B, три свойства A/C, mandatory M mitigation каждой модели, counterexample и conditional decisions. Replay требует явно выбранный trusted key и свежую Lean verification. [Scope и proof evidence](docs/COMPARISON_VERIFICATION.md), [explanation/sidecar commands](docs/EXPLANATIONS.md), [методика и metrics replay](docs/METRICS.md). Метрики являются deterministic projection; отдельного Lean proof подсчёта нет.

## Проверки

```sh
npm run lint
npm run format:check
npm run check        # TypeScript strict
npm test            # domain, tampering, persistence, signatures and HTTP workflow
npm run test:lean    # 14 integration tests; requires exact Lean 4.30.0
npm run schemas:check # generated v2 schema freshness
npm run build       # typecheck + production bundle
docker compose config --quiet
```

Отрицательные проверки включают пропуск обязательной нормы, изменение штрафа, потерю/дублирование ветви, замену снимка/модели, подмену issuer, конфликт одновременных записей и запросы с чужим Origin/Host. Lean отдельно получает заведомо неверный результат в обход TypeScript guard и обязан отклонить доказательство.

## Структура

```text
client/       React UI
shared/       Typed contracts, schemas and reform producer semantics
server/       Registry, interpreter, checker, receipts, SQLite and local HTTP API
lean/         Independent formal relation and trusted proof template
tests/        Domain, API and actual Lean integration checks
fixtures/     Source scenarios, expected outcomes and bounded design audits
schemas/      Generated JSON Schema artifacts
scripts/      Schema exporter, A/B/C demo, receipt replay, explanation and metrics CLI
docs/         Vision, design provenance, demonstrator, MVP and verification evidence
prototype/    Original architecture archive, preserved as supplied
```

Данные и локальный signing key хранятся в `.data/`, исключённой из Git. `NORMLAB_DATA_DIR` задаёт другой каталог. Ключ создаётся с правами `0600`; потеря ключа лишает новые запуски прежней issuer identity. Доступ к локальному аккаунту и файлам входит в trusted base.

## Границы MVP

Это реализация одного synthetic profile с двумя зафиксированными редакциями. Исходная архитектура описывает более широкий продукт. В текущем срезе SQLite заменяет PostgreSQL, задания выполняются локально, producer написан на TypeScript, Lean проверяет независимо построенное утверждение. Внешнего AI, загрузки произвольных нормативных пакетов, Hypercode → Legal IR compiler, многопользовательской авторизации, production sandbox и публичной публикации пока нет.

Внутри immutable snapshot сохраняется одно установление A. Полный event model по субъектам, эпизодам и evidence refs запланирован в M2.

Подпись подтверждает неизменность и происхождение квитанции. Lean подтверждает формальную допустимость результата относительно заданных входов и модели. Соответствие реальному праву и истинность описанных обстоятельств не проверяются. Подробнее: [границы проверки](docs/MVP.md).

Для A/B/C реализованы отдельное ядро producer, locked bundles, contracts v2, independent decision/comparison/property verification, signed receipts, deterministic explanations, separate structure/decision/change metrics, HTTP/UI и перенос выбранных экспериментов с read-only replay. NL-503 и NL-504 закрыты в объявленных границах локального demonstrator: hosted CI проходит на `main`, release notes подготовлены как draft, а migration engine покрыт synthetic upgrade/rollback regression. Branch protection недоступна текущему плану приватного GitHub-репозитория, поэтому CI не блокирует merge автоматически. Следующий исследовательский этап — NL-505; второй предметный домен, AI и production-инфраструктура имеют отдельные этапы в [roadmap](roadmap.md).
