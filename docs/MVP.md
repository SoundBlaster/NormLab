# MVP 0.1.0: решения и область проверки

## Реализованный срез

`prototype/normlab-architecture/` сохраняет исходный проект архитектуры. Реализация ограничена synthetic reduction fixture. Редакция 0.1.0 вручную перенесена в ограниченный типизированный Legal IR; редакция 0.2.0 добавлена как экспериментальный вариант с множителем 1/2. Автоматическая совместимость с reference Hypercode CLI не заявляется.

| Архитектурный элемент         | MVP                                                                                           |
| ----------------------------- | --------------------------------------------------------------------------------------------- |
| CaseService                   | Одно синтетическое дело, immutable snapshots и supersession в SQLite                          |
| FindingEvent                  | Одно установление A включено в подписываемый снимок; полная модель событий ещё не реализована |
| NormRegistry                  | Две фиксированные версии одного профиля; сторонние пакеты не загружаются                      |
| AnalysisCoordinator           | Snapshot/bundle binding, два активных задания, повторное использование verified result        |
| AnalysisWorker                | Чистый TypeScript producer; отдельно запускаемый Lean kernel проверяет результат              |
| LeanVerifier                  | Ограниченный JSON certificate, собственный statement constructor, фиксированный шаблон Lean   |
| ReceiptService                | Ed25519, hashes, assumptions и export                                                         |
| ComparisonService             | Полный обход established/refuted; без отдельного proof receipt                                |
| PostgreSQL / durable queue    | SQLite WAL и ограниченный локальный исполнитель; crash recovery задания — повторный запуск    |
| AIWorker / PublicationService | Отложены                                                                                      |

## Проверяемое утверждение

`Permissible n d outcome` задаёт независимое отношение:

- штраф точно равен 200 000;
- установленное A требует `prisonMonths * d = 120 * n` и ledger `applied`;
- опровергнутое A требует 120 месяцев и ledger `inapplicable`.

`ValidResult` дополнительно требует положительных n/d, n ≤ d, правильного статуса завершённости, точного набора ветвей и сводного ledger. Для `unreviewed` и `not-established` обязательны ровно две ветви в каноническом порядке. Для завершённых состояний обязательна ровно одна соответствующая ветвь.

Нормативные правила представлены данными и определениями. Текст сценария не становится аксиомой. Наличие runtime-функции не используется как доказательство единственности: в Lean есть отдельные теоремы о допустимых последствиях.

Перед Lean TypeScript checker заново проверяет immutable snapshot digest, весь bundle против реестра, semantic/provenance bindings и строгую форму сертификата. Он не импортирует producing interpreter. Доверенный конструктор берёт состояние A из снимка, множитель из реестра и формирует `ValidResult` для предложенного результата.

В Lean source интерполируются только проверенные ограниченные числа, boolean и фиксированные enum tokens. Текст описания, rationale, произвольные импорты и предоставленный пользователем Lean source не попадают в процесс verifier.

## Trusted computing base

- Локальный host, Node.js, backend и его registry / digest / statement-construction code.
- Доверенный `lean/NormLab.lean` и дистрибутив Lean 4.30.0 с bundled libraries.
- Lean kernel и его вычисление через `by decide`; результат native evaluation не принимается вместо proof term.
- Стандартная `propext` включена в явный allowlist. Фактические транзитивные зависимости `checked` записываются в receipt.
- Ключ issuer и доступ к локальному хранилищу.

`toolchainDigest` в этом MVP включает версию Lean, SHA-256 локального бинарника, формальную модель, код verifier/registry/contracts/hashing, Node.js version и dependency lock. Это не digest всего дерева bundled libraries. Полная проверка целостности дистрибутива, отдельный повторный checker и hardened OS sandbox — следующие этапы.

Процесс ограничен 512 MiB Lean memory budget, heartbeat budget и 20-секундным timeout; одновременно допускаются две проверки. Он получает минимальное окружение, однако изоляция файловой системы и сети на уровне OS пока не реализована. Поэтому здесь нет входа для произвольного кода или импортируемых пакетов.

Описание подходов к проверке Lean: [Validating a Lean Proof](https://lean-lang.org/doc/reference/latest/ValidatingProofs/). Гарантии этого MVP относятся только к описанному фиксированному процессу и доверенной локальной среде.

## Хранение и stale results

Snapshot содержит описание, мотивированное состояние A, simulated authority, время и ссылку `supersedes`. Изменение любого поля создаёт новый snapshot digest. SQLite transaction обеспечивает проверку ожидаемого предыдущего снимка и вставку новой ревизии; повторная запись устаревшего клиента получает 409.

Анализ всегда хранится со своим snapshot и bundle. Результат асинхронной проверки старого снимка остаётся историческим. UI выбирает результат по паре snapshot/bundle и помечает изменённый черновик как ещё не проверенный.

Реестр и Lean toolchain фиксированы на время процесса. При изменении модели/верификатора и перезапуске старые квитанции показываются как исторические; они не переиспользуются как текущая проверка. Пользователь может повторить проверку, сохранив прежнюю квитанцию в истории. Каждый новый analysis хранит точную копию своего bundle для экспорта. Новый каталог `NORMLAB_DATA_DIR` даёт чистый эксперимент.

## Local API

| Метод | Путь                          | Назначение                                                                     |
| ----- | ----------------------------- | ------------------------------------------------------------------------------ |
| GET   | `/api/bootstrap`              | Workspace, bundles, сравнение, доступность Lean и token локальной сессии       |
| POST  | `/api/snapshots`              | `{ input: { narrative, finding, rationale }, expectedSnapshotId }`             |
| POST  | `/api/analyze`                | `{ snapshotId, bundleId }`                                                     |
| GET   | `/api/analyses/:id/export`    | JSON с snapshot, bundle, certificate и signed receipt                          |
| POST  | `/api/analyses/:id/signature` | Проверка подписи сохранённой квитанции против публичного ключа текущего issuer |

POST требует `Content-Type: application/json` и `X-NormLab-Token` из bootstrap. Проверяются Host и Origin. Это защита локального демо от запросов чужих сайтов, а не многопользовательская authentication/authorization. Максимальный JSON body — 32 KiB.

Экспорт содержит публичный ключ для проверки математической целостности подписи. Доверие к issuer требует независимо зафиксированного ключа; ключ внутри самой квитанции не создаёт доверие автоматически.

## Следующий этап и критерии успеха

1. **Стабилизировать нормативный adapter:** версионированные schemas и второй пакет с другой семантикой. Критерий — новый пакет работает без специальных ветвей в backend.
2. **Выделить worker:** OS sandbox, полная toolchain identity, durable jobs и recovery. Критерий — сбой/timeout/повтор доставки не создают ложный verified или текущий stale result.
3. **Расширить события дела:** несколько субъектов и эпизодов, evidence provenance и capabilities. Критерий — каждое установление имеет проверяемое происхождение и область полномочий.
4. **Добавить extraction и review:** AI только предлагает данные; публикация требует отдельного действия. Критерий — извлечённое утверждение не может самостоятельно изменить accepted finding.
