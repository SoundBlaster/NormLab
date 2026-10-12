# Offline evidence envelope v1

Первый implementation slice [#77](https://github.com/SoundBlaster/NormLab/issues/77), после [inventory](HARNESS_GAP_INVENTORY_2026-10-12.md). Реализация: [IO](../evaluation/offline_bundle.py), [metadata contract](../evaluation/offline_contract.py), [task/turn contract](../evaluation/offline_task_contract.py), [reference/report contract](../evaluation/offline_score_contract.py), [adapters/CLI](../evaluation/offline_adapters.py).

## Scope

Общий формат связывает dataset, experiment, derived run, logical tasks, turns, reference revision и score view. История transport attempts в этих входных форматах неизвестна: `attempts: null`, а не пустой список или выдуманная попытка. Provider/retry adapters, cross-run comparison, live execution/resume и MLflow import остаются следующими slices #77.

Два поддержанных adapter paths:

| Adapter          | Вход                                                                                 | Validation/scoring                                                                                                   | Evidence kind                                                                           |
| ---------------- | ------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| `classification` | Manifest `normlab.evaluation-experiment/v1` или `/v2`, его captures; optional labels | `harness_v2.prepare/replay`: сохраняются source/parent/definitions/label bindings и selected payment probe semantics | `offline-fixed-captures`; происхождение исторических dispatches этим не устанавливается |
| `s13`            | Repo-pinned S1.3 v1 manifest; указанные capture/reference files                      | Frozen `s13_offline.compile_plan/replay`, включая code pins, prediction seal и reference revision                    | Только `offline-fixture`, не live evidence                                              |

Unsupported schema/mode не получает fallback. S1.3 adapter не принимает произвольный manifest и не добавляет live support. Classification exact HTTP context неизвестен; S1.3 сохраняет **logical payload**, а не SDK body или историю фактически отправленных запросов.

## Команды

Из корня repository, Python 3.10+, без установки SDK и без credentials:

```bash
# Без --output: сформировать и валидировать view в памяти, напечатать summary.
python3 -B -S evaluation/offline_adapters.py classification \
  fixtures/parking-pilot/evaluation-harness/experiment.json \
  --labels fixtures/parking-pilot/evaluation-harness/reviewer-labels.json

# Новый каталог: byte-preserved legacy artifacts + normalized evidence.
python3 -B -S evaluation/offline_adapters.py classification \
  fixtures/parking-pilot/evaluation-harness/experiment.json \
  --labels fixtures/parking-pilot/evaluation-harness/reviewer-labels.json \
  --output .artifacts/offline-classification-001

python3 -B -S evaluation/offline_adapters.py s13 \
  --output .artifacts/offline-s13-001

# Reader проверяет envelope/hash bindings, не запускает сохранённый Python.
python3 -B -S evaluation/offline_adapters.py verify \
  .artifacts/offline-s13-001
```

Это интерфейс реализации, а не отчёт о выполнении этих команд. Без labels classification scores остаются not-evaluated/null по исходному scorer. S1.3 требует полную reference coverage согласно frozen contract; optional reference там не заявлена. `verify` не импортирует legacy scorers или provider modules; для semantic rescoring используется соответствующий adapter в repository с его исходными dependency/definition restrictions.

## Layout и limits

```text
bundle.json                 normlab.offline-bundle/v1, final export marker
artifacts/<sha256>.blob      raw bytes или canonical JSON, content addressed
```

- Artifact reference: `{path, sha256, bytes}`; path строго `artifacts/<sha256>.blob`. Одинаковые bytes сохраняются один раз. Manifest/captures/inputs/references/code copies сохраняют исходные bytes; новые logical contexts, normalized task/score projections и regenerated replay report сериализуются canonical JSON.
- До 2 MiB на файл/index, 4096 artifacts, 1024 tasks и 64 MiB суммарных artifact bytes. Большая task matrix распределяется по отдельным task/context/score artifacts; весь план не складывается в один JSON report без лимита. Дедупликация contexts не меняет их bytes или число planned tasks.
- Output directory создаётся эксклюзивно; существующий или partial каталог не перезаписывается и не возобновляется. `bundle.json` записывается последним. При filesystem failure partial directory остаётся для диагностики; повреждённый/отсутствующий index не проходит reader. Это не durable execution checkpoint или автоматическое resume.
- Reader проверяет byte lengths/hashes, относительные content-addressed paths и containment после symlink resolution, index/reference membership, versioned fields и связи task/turn/run/score. Duplicate JSON keys и nonfinite numbers отклоняются.
- Это **unsigned** inventory. Редактирование одновременно данных и hashes не обнаруживается как подмена авторства. Reader не подтверждает независимость разметки, истинность фабулы, юридическую корректность или соответствие raw predictions смыслу текста.

## Identity и revisions

Canonical encoding: UTF-8 JSON, keys sorted, separators `,`/`:`, без whitespace, `ensure_ascii=False`, finite numbers only. Hash algorithm — SHA-256. `identity(kind, value)` даёт `kind-<sha256(canonical(value))>`.

| Entity          | Binding                                                                                                                                                                                           |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Dataset         | Original ID/revision, где доступны. Classification digest покрывает cases и input/parent artifacts; S1.3 digest — sources/candidates artifact digests. Неизвестная dataset revision остаётся null |
| Experiment      | Original experiment ID + manifest **byte** digest; strategy/tactic IDs и известные versions, provider metadata и исходные policies/caps                                                           |
| Run             | `run-<hash>` от `{schema, manifest: manifest byte digest, captures: ordered artifact refs}`; `identityKind: legacy-bundle-derived`                                                                |
| Prediction seal | Hash того же binding; capture set digest дополнительно сохраняется отдельно. Labels и adapter/scorer code не входят в run identity                                                                |
| Task            | `task-<hash>` от `[runId, originalId]`; сохраняет case/family/language/arm/repeat/source/task digest                                                                                              |
| Turn            | `turn-<hash>` от task ID; original status и normalized replay outcome раздельны                                                                                                                   |
| Reference       | `reference-<hash>` от reference artifact byte digest; revision/status отдельно, без повышения candidate до human gold                                                                             |
| Score view      | `score-<hash>` от `[runId, regenerated report digest, referenceId, adapter metadata/code refs]`; scorer/dependency artifacts отдельно                                                             |

Derived run ID — import identity исходного bundle, не восстановленный historical execution ID. Повторный экспорт тех же bytes даёт тот же run ID. Иные formatting/ordering manifest/capture bytes могут дать другую import identity. Reference/scorer/adapter changes создают новый score view того же run, если его source binding не менялся. Это deterministic identity, а не реализованный registry deduplication.

Legacy manifest classification содержит ссылки на captures: его revision не заявляется чистой независимой experiment configuration revision. Task digest classification — input/parent/definitions binding; он не является hash фактического HTTP payload. S1.3 task digest — canonical logical payload digest. Эти digest kinds не делают разные стратегии автоматически сопоставимыми.

## Envelope fields

`normlab.offline-bundle/v1` — strict top-level object:

| Field        | Содержание                                                                                           |
| ------------ | ---------------------------------------------------------------------------------------------------- |
| `adapter`    | ID/version и mapping module name to content-addressed copy пяти новых modules                        |
| `source`     | Original schema, manifest, ordered capture refs и role-labelled input artifact refs                  |
| `dataset`    | ID/revision/digest, без invented release version                                                     |
| `experiment` | ID/manifestDigest/strategy/tactic/provider/policy; неизвестные strategy/tactic versions null         |
| `run`        | Derived ID, identity/evidence kind, capture/seal digests, `inferenceCallsExecuted: 0` для normalizer |
| `reference`  | Reference identity/revision/status/artifact или null для classification без labels                   |
| `score`      | Score ID/report/referenceId/scorer/scope, `criticalErrorFreeRate: null`                              |
| `records`    | Refs на отдельные `normlab.offline-task/v1` objects                                                  |
| `counts`     | Planned/recorded/status/question denominators и known/unknown token accounting                       |
| `artifacts`  | Полный inventory content-addressed files                                                             |

`normlab.offline-task/v1` содержит IDs, originalId, case/candidate/family/language/arm/repeat, source/task digests, context, turn и scoreArtifact. У classification неизвестные repeat и candidate ID остаются null; original capture record ID сохраняется отдельно как originalId. Для S1.3 сохраняются planned repetition, candidate/target record ID и missing jobs; `not-recorded` original status означает отсутствие capture row, а normalized status остаётся `not-dispatched`.

Turn сохраняет stage, original/normalized statuses, prediction artifact, error, returned model, usage, latency/cost, attempts и question IDs. `predictionArtifact` classification ведёт к полному original capture; S1.3 — к canonical original prediction row или null при отсутствующем row. Per-task score ведёт к строке regenerated legacy report; reader связывает её с report и original ID.

### Context/reference separation

- Classification: `context.kind: unavailable`, artifact/policy null; original input/parent artifacts доступны через source inputs, но не выдаются за exact model-visible request.
- S1.3: `context.kind: logical-payload`, exact state/questions artifact и policy `provider-neutral-independent/v1`. Reference expected answers находятся только в отдельном reference/score evidence.
- Export локальный и может содержать персональные данные или текст, похожий на credentials, из входного narrative/raw output. Не публиковать bundle автоматически. CLI не собирает environment/Keychain/Authorization headers и не выводит arbitrary exception bodies; ошибки — fixed diagnostic. Public/redacted export ещё не реализован.

### Denominators и unavailable metadata

- `plannedTasks` — все records/jobs, включая отсутствующие/failed/partial/invalid/deadline. `statusCounts` вычисляется по всем tasks.
- `plannedQuestions` classification — null: labels/probes не превращаются в число реально заданных вопросов. У S1.3 это сумма logical question IDs, не число transport calls.
- `recordedOutcomes` — количество tasks с сохранённым capture/prediction artifact, включая failures; это не число completed predictions, dispatches или independently reviewed cases.
- `knownInputTokens`/`knownOutputTokens` суммируют доступные значения по prediction rows один раз на task. `unknownUsageOutcomes` считает recorded rows с отсутствующим usage хотя бы в одном поле. Отсутствующие rows не получают fabricated usage и видны в planned/status denominator. Fixture usage не является доказательством оплаченных live tokens.
- `attempts`, latency и cost остаются null в обоих adapters. Нулевой `inferenceCallsExecuted` относится к этой offline операции; он не доказывает, что исторический capture не требовал платного вызова.
- Original report сохраняет native metrics/scopes: selected probes и S1.3 A/B/C/D не объединяются в общий quality score. Для D false acceptance/rejection остаются null; completeness и case-level critical-error-free quality не оцениваются.

### Reference provenance и native summaries

Reader повторно проверяет reference по исходной schema: classification допускает только `candidate`, требует experiment digest и полное покрытие записей валидными payment probes. S1.3 требует plan digest, полное покрытие jobs/questions и допустимые labels. Для `human-adjudicated` обязательны revision, отличная от `s13-candidate-v1`, и непустые текстовые `adjudicationEvidence`, как в frozen scorer. Эти поля заявляют provenance и не удостоверяют личность reviewer.

Native report metadata и summaries пересчитываются из связанных строк: classification counts и candidate/not-evaluated status; S1.3 planned/status/question counts, agreement, verdicts, false acceptance/rejection по каждой arm и known/unknown usage из original predictions. S1.3 question predictions повторно нормализуются по frozen v1 response rules; expected answers связываются с reference. Изменение report вместе с его artifact ref и score ID не позволяет оставить противоречащие строкам сводные метрики. JSON booleans и integer counts различаются строго.

Это проверка внутренней согласованности unsigned bundle, а не подтверждение подлинности источника или независимого semantic review. Reader не выполняет сохранённый scorer code и не повторяет classification parsing, S1.3 plan compilation, defect-location или candidate-stance derivation. Полный replay выполняет исходный adapter при экспорте; последующая coordinated замена source evidence не предотвращается цифровой подписью в v1.

## Validation scope этого изменения

Локально: static Python syntax, Ruff lint/format, Markdown formatting, links и проверка неизменности legacy source pins. Новые tests не добавлялись; CLI export/verify и replay в этом implementation slice локально не запускались. Runtime-проверка двух exports и reader остаётся отдельным следующим validation шагом. Existing CI после публикации PR — отдельное evidence и не заменяет такую проверку новых CLI paths.

После runtime validation следующий implementation slice #77 — portable paired comparison с compatibility checks, unmatched/not-evaluated rows и заданными denominator scopes.
