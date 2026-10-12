# Evaluation harness: inventory и следующий offline-контракт

Дата: 2026-10-12. Задача: [#77](https://github.com/SoundBlaster/NormLab/issues/77), parent [#63](https://github.com/SoundBlaster/NormLab/issues/63).

## Границы результата

Это inventory исходников на commit `da486e3fcbd6dde7c687ea85d9f501005c589b20`, после merge #82. Ссылки на код ниже закреплены на этом commit. Новые contracts в разделах 4–6 — **предложение для реализации**, а не существующие schemas или CLI.

Уже есть несколько работающих путей plan → capture → replay/score. Главный пробел — общий слой identity, lineage и comparison между этими путями. Добавление MLflow само по себе этот пробел не закрывает: текущий importer принимает только старый parking report и каждый раз создаёт новые runs.

Проверка в этом срезе: чтение исходников, сверка schema literals, ссылок и diff. Inference, SDK construction, replay, tests и MLflow import здесь не запускались; runtime-совместимость и качество моделей этим inventory не подтверждаются.

## 1. Семейства данных и lineage

Префикс `normlab.` подразумевается у каждого schema name в таблице. Версии принадлежат конкретной schema; одинаковый `/v1` у двух семейств не означает совместимость.

| Семейство / источник                                                                         | Входы → выходы                                                                                                                   | Что уже связано                                                                                                               | Ограничение общего harness                                                                                                  |
| -------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| [Parking scorer][parking] и [MLflow importer][mlflow]                                        | `parking-evaluation-expectations/v1`, baseline artifacts → `parking-evaluation-report/v1`                                        | Source/raw/scorer/expectations digests; per-run artifact manifest digest, per-case gates и candidate checks                   | Run identity — имя каталога; нет общего attempt/turn contract. Только этот report принимает importer                        |
| [Synthetic parking scorer][synthetic]                                                        | Corpus/labels, `synthetic-extraction-run/v1`, typed или `langextract-statements/v1` outputs → `synthetic-parking-evaluation/v1`  | Dataset/expectations/run/artifact digests, family/case metrics и pipeline metadata                                            | Отдельный report; gaps не оцениваются, target quality остаётся null                                                         |
| [Classification harness v1][harness-v1] → [v2 reader][harness-v2]                            | `evaluation-experiment/v1` или `/v2`, `evaluation-capture/v1`, `evaluation-labels/v1` → `evaluation-replay/v1` или `/v2`         | Manifest/source/parent/definitions/labels/code hashes, record IDs, requested/returned model                                   | Один classification turn; v2 reader создаёт новый replay, не заменяет v1 evidence. Labels bound к bytes experiment manifest |
| [One-batch verifier][verifier] / [runner][verifier-runner]                                   | `verifier-experiment/v1` → `verifier-capture/v1` → `verifier-replay/v1`                                                          | Exact request body/URL, source/manifest digest, dependencies, normalized response и request ID; Noul policy отдельно          | Один `turn_1`, до трёх вопросов; Choice/Score capture не равен policy verdict. Нет общего dialogue contract                 |
| [Stage 1 dataset audit][audit]                                                               | `stage1-audit/v1`, `/v2`; sources, candidates, review, conventions → audit reports `/v1`, `/v2`, `/v3`                           | Dataset/source/annotation provenance, representability и conventions                                                          | Audit/reference evidence, не provider run. Review revisions нельзя выводить из версии capture                               |
| [Frozen Stage 1 planner][planner] / [offline executor v2][offline-stage1]                    | `stage1-comparison/v1` → `stage1-comparison-plan/v1`, export `/v1`; wire fixtures → offline capture/turn `/v1` или `/v2`         | Jobs, case/family/record/repeat, source/task digests, schedule и code pins                                                    | Оба executor поколения используют summary `stage1-offline-summary/v1`; lineage определяется также capture/code pins         |
| [Provider planner][provider-plan] / [executor][provider-executor] / [scorer][provider-score] | `stage1-provider-experiment/v1` → plan `/v1` → provider capture `/v1` → prediction seal `/v1` → provider score `/v1`             | Parent plan, exact planned/actual HTTP request, job IDs, dependencies, model/usage, capture seal и отдельные candidate labels | Три фиксированных arms/protocols; paired rows внутри одного plan. Не общий provider registry или cross-run compare          |
| [Retry runner v1][retry-v1] → [v2][retry-v2] / [v2 scorer][retry-score]                      | Retry plan/capture/summary `/v1` или `/v2`; child `stage1-provider-attempt-plan/v1`; retry prediction seal/score `/v1` или `/v2` | Job + ordinal + child artifact hashes, aggregate cap, first/final outcomes, все attempts и known/unknown usage                | V2 export разделяет plan на отдельные job JSON. Это не dialogue turns; неизвестный dispatch останавливает цепочку           |
| [S1.3 offline][s13]                                                                          | `s13-offline/v1` → plan summary `/v1`, `s13-offline-capture/v1`, отдельный `s13-reference/v1` → replay report `/v1`              | Manifest/code/plan/capture/reference digests, reference revision/status, jobs/questions, planned denominators                 | Только `offline-fixture`, provider binding unbound. A/B/C и D имеют разные outputs/metrics; общего live run нет             |

Auxiliary artifacts также требуют сохранения исходной schema и bytes: `baseline-artifacts/v1`, `evaluation-artifacts/v1`, provider config, execution permits, provider-smoke reports, discovery diagnostics, external corpus provenance/review. Они остаются связанными artifacts; smoke или audit не превращается в scored provider run. [Provider configuration][provider-config] задаёт маршруты, но не нормализует перечисленные report families.

Отдельная граница: [продуктовый `normlab.experiment/v1`][product-transfer] переносит reform artifacts, runtime locks и receipts. Его проверки доверия/Lean нельзя объединять с evaluation captures под общим названием «experiment». Unsigned hash inventory evaluation artifacts обнаруживает drift относительно inventory, но не удостоверяет автора и не доказывает legal correctness.

## 2. Capability inventory

«Есть» ниже означает реализацию в указанном коде; повторной runtime-проверки в этом срезе не было.

| Возможность                     | Что есть                                                                                         | Что отсутствует / следующий contract                                                                                   |
| ------------------------------- | ------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------- |
| Plan/dry-run                    | Classification, verifier preflight, Stage 1/provider/retry plans и S1.3 offline export           | Единый диспетчер по schema и общий machine-readable capability result                                                  |
| SDK-free replay                 | Отдельные classification/verifier/Stage 1/retry/S1.3 readers                                     | Единый offline envelope; portable bundle пока не гарантирует standalone executable replay                              |
| Prediction/reference separation | Stage 1 seal до чтения labels; S1.3 capture binding и отдельная reference revision               | Унифицированный prediction seal и immutable score view для всех семейств                                               |
| Failure accounting              | Локальные denominators сохраняют missing, failed, partial, unknown outcomes                      | Общая status taxonomy с обязательным сохранением original status и причины                                             |
| Paired comparison               | Stage 1 provider/retry scorers сопоставляют arms одного плана                                    | Сравнение двух saved runs с проверкой context/task/reference compatibility и списком непарных rows                     |
| Request/context evidence        | Verifier и provider transport записывают planned/actual body; retry сохраняет child attempts     | Общая context policy и sequential/repair history; для старых classification captures exact HTTP context не восстановим |
| Checkpoint/retry                | Provider checkpoint до dispatch; retry v2 ограничивает attempts/calls и сохраняет pending suffix | Общий resume contract: unknown sent outcome не может автоматически стать новой отправкой                               |
| Version identity                | Digests источников, manifests, code pins, отдельные adapter/dependency versions                  | Общие versioned strategy/tactic/context/acceptance-policy identities; config name недостаточен                         |
| MLflow                          | Локальный importer старого parking report                                                        | Новые schemas, idempotence, lineage к raw capture, сравнения и tracing                                                 |

### Конкретные ограничения, влияющие на миграцию

1. `harness_v2.py` проверяет definitions против текущего classification contract, требует пустые provider settings и `offline-replay`. Его output snapshot содержит code copies, но для запуска используется repo CLI. Нельзя обещать произвольный historical replay только по наличию hashes.
2. Stage 1 provider plan присваивает `contextId` каждому arm/job. Для matching нужен semantic key (`caseId`, `recordId`, `repeat`, source/task binding), а не равенство этих context IDs между arms.
3. Retry v2 считает неизвестную зарезервированную попытку потенциально оплаченной, даже если child capture отсутствует. При pending child известный usage сохраняется, но итоговый verdict не принимается. Нормализация не должна терять эту асимметрию.
4. S1.3 считает calls и questions отдельно; false acceptance/rejection для D остаются null. Повтор и несколько questions одного source не добавляют независимых cases.
5. В [requirements][provider-requirements] уже pin adapter `0.4.0` / Mellea `0.8.0`; [план от 2026-10-09](EVALUATION_HARNESS_PLAN.md) содержит исторические пункты про `0.3.0`. Новая summary должна брать фактическую dependency provenance из конкретного run, сохраняя старые записи.

## 3. MLflow: точный разрыв

[`import_mlflow.py`][mlflow] принимает только `normlab.parking-evaluation-report/v1`. Для каждого `report.runs` вызывается `mlflow.start_run`, без поиска ранее импортированного run ID/digest. Повторный запуск кода создаёт новые runs. Имя run не является idempotency key.

Сохраняются report/run JSON, metrics, expectations/scorer/artifact-manifest digests и четыре deterministic scorers через `mlflow.genai.evaluate`. Raw artifact manifest/capture tree по указанному digest importer не обходит и не загружает. Поэтому digest в params ещё не даёт пользователю путь к самим raw captures. Generic dataset/strategy/provider/attempt/turn/reference lineage отсутствует.

`mlflow==3.16.1` закреплён в [requirements][mlflow-requirements]; установленная версия и SDK API в этом срезе не проверялись. Следующий importer должен сначала получать валидированный offline bundle. MLflow остаётся проекцией переносимого evidence, а labels и scorers — источником определённых ими оценок.

## 4. Предлагаемый минимальный offline envelope

Ниже — требования к будущему versioned contract. Названия полей иллюстративные; schema name и CLI будут закреплены в implementation PR.

| Entity              | Identity / связи                                                    | Обязательное содержание                                                                                              |
| ------------------- | ------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| Dataset revision    | `datasetId`, revision, content digest                               | Source/case/family/split/language/translation provenance; inputs отдельно от reference                               |
| Experiment revision | ID/revision + manifest digest, dataset revision                     | Arms; strategy/tactic/context policy versions; prompts/settings/schema/code/dependency pins; schedule/repeats/caps   |
| Run                 | `runId`, experiment revision, `evidenceKind`, capture bundle digest | Одна execution identity; offline fixture / mock HTTP / live явно различаются; provenance и completeness              |
| Logical task        | Run + case/arm/repeat + semantic task digest                        | Source/candidate bindings, stage, question IDs; batching и calls/questions не смешиваются                            |
| Turn                | `turnId`, task ID, parent turn IDs                                  | Новый вопрос/шаг/repair; exact model-visible context или явное `unavailable`; context digest и policy                |
| Attempt             | `attemptId`, turn ID, ordinal                                       | Одна transport attempt; dispatch status, request/response refs, error/refusal, model/request ID, usage/duration/cost |
| Prediction seal     | Run + capture bundle digest                                         | Frozen artifacts и predictions; не включает reviewer-only answers в model inputs                                     |
| Reference revision  | ID/revision/digest, dataset/task scope, review status               | Candidate/human provenance, coverage, independent review evidence; неизвестное не заполняется догадкой               |
| Score view          | Seal + reference + scorer/policy revision/digests                   | Per-row results, planned/observed/scored denominators, null/not-evaluated, ограничения конкретной метрики            |
| Comparison view     | Два score views + comparison policy digest                          | Compatible paired rows, regressions/rescues, unmatched/excluded rows с причинами и family slices                     |

Связь execution: run → logical task → turn → attempt. Связь оценки: prediction seal + reference + scorer/policy → score view. Новый scorer/reference создаёт новый score view; повторное исполнение experiment создаёт новый run. Retry внутри исполнения сохраняет run ID. Runtime run ID выделяется до dispatch; для legacy bundle можно использовать явно помеченную deterministic import identity, не выдавая её за исторический execution ID.

Transport retry повторяет запрос того же turn и получает новый attempt. Sequential question создаёт новый turn с зафиксированным history. Repair создаёт новый turn с ссылкой на candidate/feedback и использованным контекстом. Совпадение нескольких этих сущностей в нынешнем one-turn runner не должно стать общим ограничением.

### Сохранение смысла и denominators

- Общий status отображается вместе с `originalSchema`, original status и evidence refs. Invalid output, refusal, model rejection, transport failure, interrupted/unknown dispatch и not-dispatched не объединяются в успешное abstention.
- Нужны отдельные planned tasks/questions/calls, observed dispatches, completed predictions, scored rows и independently reviewed cases. Любая rate содержит numerator/denominator и scope. Zero denominator даёт null.
- Token usage относится к HTTP attempt/batch один раз; per-question attribution возможна только при наличии такой provenance. Known usage и число unknown outcomes сохраняются отдельно; unknown cost не становится нулём.
- Candidate agreement, deterministic gate, selected-claim verification и case-level critical-error-free quality — отдельные metrics. Partial review не получает полный quality pass; качество всей extraction цепочки не выводится из S1.3 replay.
- Exact context нельзя восстановить из source text и model name. При отсутствии bytes/context policy сохраняется unavailable + причина; такая row не получает strict matched-context compatibility.
- Парность требует совпадения dataset/source/candidate/task/reference/scorer scope, repeat и объявленного context policy. Wire-format различия между Jev/Decisions/Responses допустимы только как явно заданная экспериментальная переменная. Несовпадение не исправляется молчаливым join по case ID.
- Local raw artifacts и публичная projection разделяются. Не копировать headers/keys или arbitrary error bodies. Provider plans сейчас содержат `keyEnvironment` как locator переменной, а не ключ; публичный export должен исключать такие locators по политике [плана](EVALUATION_HARNESS_PLAN.md). Exact context реальных текстов может содержать персональные данные и остаётся локальным по умолчанию.

### Idempotent registry projection

Предлагается отдельная import identity, связывающая target registry, run ID, score view ID и portable bundle digest. Повтор той же identity возвращает существующую projection; тот же run/view ID с другим digest — conflict. Повторный scoring сохраняет исходный execution и добавляет новую score view.

Import должен сохранять raw capture refs и проверять их доступность, а не только записывать digest. Нужны состояния pending/completed/failed и восстановление после частичной записи без дублирования metrics/artifacts. Гарантию от concurrent duplicate imports надо реализовать явно через ledger/locking и проверить на закреплённом MLflow SDK; tags сами по себе не объявляются atomic unique constraint. Эта часть ещё не реализована и не проверена.

## 5. Миграция без переписывания evidence

1. Оставить legacy bytes, schema names, original reports и code pins неизменными. Для новых readers добавлять versioned modules/adapters; изменение pinned старого replay может сломать историческую binding.
2. Adapter сначала проверяет исходный bundle его reader/contract, затем выпускает дополнительный normalized view с source artifact hashes и adapter revision. Не ослаблять source/fragment/definitions checks ради универсального импорта.
3. Новая artifact inventory включает исходный bundle и normalized view. Хранить byte digests отдельно от canonical semantic digests; указать алгоритм/serialization и dependency coverage. Hashes не заменяют подписи.
4. Reference выбирается явно; сохранять её status/coverage. Отсутствующие legacy attempts, wire contexts или usage остаются unknown. Unsupported schema даёт явный отказ/capability result, без heuristic fallback.
5. Replay не конструирует SDK и не читает credentials. Contract smoke/live execution остаются отдельными opt-in путями; offline CI не получает live разрешения из Issue status.

## 6. Приоритетные implementation slices внутри #77

Это порядок работы в существующей Issue, не новый параллельный ledger. Полный acceptance #77 остаётся незавершённым.

| Порядок                                | Ограниченный результат                                                                                        | Наблюдаемый acceptance / evidence                                                                                                                                                     |
| -------------------------------------- | ------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1. Offline identity + adapter contract | Закрепить envelope/schema и adapters для classification harness v2 и S1.3 fixture; общий SDK-free read/export | Оба saved bundles получают normalized views с lineage, reference status, planned denominators и unavailable metadata; original bytes не меняются. Unsupported inputs явно отклоняются |
| 2. Baseline compare                    | Два score views, compatibility checks и portable JSON/Markdown comparison                                     | Saved run сравнивается с baseline без сети; paired/unmatched/unevaluated rows и denominator scope видны. Разные reference/scorer versions не скрываются                               |
| 3. Stage 1 attempts/context            | Adapter для provider/retry v2 с first/final и полным attempt tree                                             | Pending/unknown suffix не возобновляется; known usage не теряется; batch usage не дублируется; raw request/task bindings сохранены                                                    |
| 4. MLflow import                       | Идемпотентная projection normalized evidence с raw artifacts                                                  | Повторный import не создаёт дубль; ID/digest conflict и partial import явно обработаны; новый score view не перезаписывает старый                                                     |
| 5. Общий execution contract            | Plan/dry-run dispatch и versioned context policies, затем bounded resume                                      | Новые turns/attempts пишут envelope до dispatch; unknown outcome требует явного решения. Live smoke отдельно разрешается и документируется                                            |

Для каждого implementation slice фиксируются validation scope и фактически выполненные проверки; этот документ не сообщает, что они уже прошли. [Evidently #78](https://github.com/SoundBlaster/NormLab/issues/78), независимая разметка [#64](https://github.com/SoundBlaster/NormLab/issues/64) и новые платные эксперименты не входят в этот inventory.

### Сопоставление с acceptance #77

- Inventory и lineage описаны; versioned relationships пока предложены, implementation criterion полностью не закрыт.
- Unified plan/replay/compare/export, context policies и resume — pending; отдельные реализации учтены выше.
- Metadata/version mapping — частично есть в legacy, единый contract pending.
- Idempotent MLflow import и raw-capture navigation — pending.
- Saved baseline comparison через общий путь — pending; новый replay или inference в этом срезе не запускался.

**Следующий ход:** implementation slice 1 — versioned offline envelope и два adapters (harness v2 / S1.3), сохраняя исходные contracts и evidence boundaries.

## Проверка документа

- Static validation: 21 commit-pinned source links существуют в указанном Git tree; 24 relative links трёх изменённых документов разрешаются в файлы; 25 явных записей schema names (с префиксом или без него) найдены в literals исходников/expectations. Сокращённые имена и семантические утверждения таблиц дополнительно сверены чтением кода, а не выполнением readers.
- Prettier check трёх Markdown files и `git diff --check` прошли.
- Tests/replay/import/live calls не запускались. CI нового PR — отдельное evidence после публикации; этот документ не объявляет его результат заранее.

[parking]: https://github.com/SoundBlaster/NormLab/blob/da486e3fcbd6dde7c687ea85d9f501005c589b20/scripts/parking-evaluate.ts
[synthetic]: https://github.com/SoundBlaster/NormLab/blob/da486e3fcbd6dde7c687ea85d9f501005c589b20/scripts/parking-synthetic-evaluate.ts
[mlflow]: https://github.com/SoundBlaster/NormLab/blob/da486e3fcbd6dde7c687ea85d9f501005c589b20/evaluation/import_mlflow.py
[harness-v1]: https://github.com/SoundBlaster/NormLab/blob/da486e3fcbd6dde7c687ea85d9f501005c589b20/evaluation/harness.py
[harness-v2]: https://github.com/SoundBlaster/NormLab/blob/da486e3fcbd6dde7c687ea85d9f501005c589b20/evaluation/harness_v2.py
[verifier]: https://github.com/SoundBlaster/NormLab/blob/da486e3fcbd6dde7c687ea85d9f501005c589b20/evaluation/verifier_capture.py
[verifier-runner]: https://github.com/SoundBlaster/NormLab/blob/da486e3fcbd6dde7c687ea85d9f501005c589b20/evaluation/run_verifier.py
[audit]: https://github.com/SoundBlaster/NormLab/blob/da486e3fcbd6dde7c687ea85d9f501005c589b20/evaluation/audit_stage1_v2.py
[planner]: https://github.com/SoundBlaster/NormLab/blob/da486e3fcbd6dde7c687ea85d9f501005c589b20/evaluation/plan_stage1_comparison.py
[offline-stage1]: https://github.com/SoundBlaster/NormLab/blob/da486e3fcbd6dde7c687ea85d9f501005c589b20/evaluation/stage1_executor_v2.py
[provider-plan]: https://github.com/SoundBlaster/NormLab/blob/da486e3fcbd6dde7c687ea85d9f501005c589b20/evaluation/stage1_provider_plan.py
[provider-executor]: https://github.com/SoundBlaster/NormLab/blob/da486e3fcbd6dde7c687ea85d9f501005c589b20/evaluation/stage1_provider_executor.py
[provider-score]: https://github.com/SoundBlaster/NormLab/blob/da486e3fcbd6dde7c687ea85d9f501005c589b20/evaluation/score_stage1_providers.py
[retry-v1]: https://github.com/SoundBlaster/NormLab/blob/da486e3fcbd6dde7c687ea85d9f501005c589b20/evaluation/stage1_retry_executor.py
[retry-v2]: https://github.com/SoundBlaster/NormLab/blob/da486e3fcbd6dde7c687ea85d9f501005c589b20/evaluation/stage1_retry_executor_v2.py
[retry-score]: https://github.com/SoundBlaster/NormLab/blob/da486e3fcbd6dde7c687ea85d9f501005c589b20/evaluation/score_stage1_retries_v2.py
[s13]: https://github.com/SoundBlaster/NormLab/blob/da486e3fcbd6dde7c687ea85d9f501005c589b20/evaluation/s13_offline.py
[product-transfer]: https://github.com/SoundBlaster/NormLab/blob/da486e3fcbd6dde7c687ea85d9f501005c589b20/server/reform-transfer.ts
[provider-config]: https://github.com/SoundBlaster/NormLab/blob/da486e3fcbd6dde7c687ea85d9f501005c589b20/evaluation/provider_config.py
[provider-requirements]: https://github.com/SoundBlaster/NormLab/blob/da486e3fcbd6dde7c687ea85d9f501005c589b20/evaluation/requirements-providers.txt
[mlflow-requirements]: https://github.com/SoundBlaster/NormLab/blob/da486e3fcbd6dde7c687ea85d9f501005c589b20/evaluation/requirements.txt
