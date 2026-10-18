# Offline evaluation harness v2

Первый реализованный срез [плана](../docs/EVALUATION_HARNESS_PLAN.md). Общая live matrix, multi-turn execution и независимый case-level quality review пока не реализованы. [Local MLflow import](../docs/OFFLINE_MLFLOW_IMPORT_V1.md) принимает verified bundles и отдельные score views.

[Inventory на 2026-10-12](../docs/HARNESS_GAP_INVENTORY_2026-10-12.md) связывает существующие classification, Stage 1/retry и S1.3 contracts и фиксирует состояние до первого envelope slice [#77](https://github.com/SoundBlaster/NormLab/issues/77). Команды ниже сохраняют свои contracts.

[Offline envelope v1](../docs/OFFLINE_ENVELOPE_V1.md) добавляет отдельный SDK-free export/reader для classification v2 и frozen S1.3 fixture. Он сохраняет legacy evidence, derived run/score identities, planned denominators и unavailable attempt/context metadata. [Runtime validation](../docs/OFFLINE_EXPORT_VERIFICATION_2026-10-13.md), [paired comparison](../docs/OFFLINE_PAIRED_COMPARISON_V1.md) и [идемпотентный local MLflow import](../docs/OFFLINE_MLFLOW_IMPORT_V1.md) реализованы отдельными slices #77.

## Запуск из корня репозитория

Python 3.10+; внешние Python зависимости и ключи не нужны. Новые replay используют `harness_v2.py` и deterministic contracts из `mellea_candidate_v2.py`, `classification_v3.py`, `anchor.py`.

```bash
python3 evaluation/harness_v2.py fixtures/parking-pilot/evaluation-harness/experiment.json \
  --labels fixtures/parking-pilot/evaluation-harness/reviewer-labels.json --dry-run

python3 evaluation/harness_v2.py fixtures/parking-pilot/evaluation-harness/experiment.json \
  --labels fixtures/parking-pilot/evaluation-harness/reviewer-labels.json \
  --output .artifacts/harness-v2-run-001

python3 evaluation/harness_v2.py .artifacts/harness-v2-run-001/dataset/experiment.json \
  --labels .artifacts/harness-v2-run-001/reviewer-labels.json \
  --output .artifacts/harness-v2-rescore-001
```

Каждый output — новый каталог. Без `--labels` semantic probes остаются not_evaluated/null; структура проверяется. Dry-run проверяет manifest, digests, source binding и labels, не создаёт output. CLI не имеет live mode и не конструирует provider.

## Совместимость и lineage

`harness_v2.py` принимает manifests `normlab.evaluation-experiment/v2` и прежние v1 без изменения исходных bytes, captures или labels. Requested/returned model — bounded opaque metadata: 1–256 ASCII symbols, leading alphanumeric, затем letters/digits/`_./:-`. Эти значения не используются как пути. Experiment/dataset/provider/route/case/record identifiers сохраняют прежний узкий contract.

Новый classification report всегда `normlab.evaluation-replay/v2`, содержит `replayContract: model-metadata/v2`, исходный `inputSchema` и hashes v2 исходников. Payment probe scorer остаётся `classification-selected-probes/v1`: scoring semantics не изменены. Повторный scoring v1 capture означает новый v2 replay, а не замену исторического отчёта. `harness.py` и `mellea_candidate.py` заморожены для исторических pins; команды с ними предназначены для воспроизведения v1 evidence. Frozen Stage1 planner/manifest остаются на v1 и не используют новые model metadata. [Подробности lineage](../docs/CONTRACT_REPAIRS_2026-10-10.md).

## Контракт первого среза

- `normlab.evaluation-experiment/v2` (или historical v1 input): experiment/dataset identity, strategy/tactic, provider metadata, offline budget, hashed definitions, cases и records.
- `normlab.evaluation-capture/v1`: record/source/parent identity, returned model и один classification turn. Status completed/failed/partial; raw output только completed; ошибки безопасными enum, без HTTP body. Usage/latency/cost в fixture v1 всегда null.
- `normlab.evaluation-labels/v1`: отдельный reviewer-only файл, bound к полным bytes manifest через experimentDigest, candidate review status, payment probes по record IDs. Labels не часть model input; в этом срезе model input вообще не отправляется.
- `normlab.evaluation-replay/v2`: per-record structure/probe results и counts, manifest/labels/scorer/dependency/definitions hashes. `criticalErrorFreeRate` всегда null, verifier quality not_evaluated.

Manifest/artifacts/labels полностью валидируются до записи output. Файлы ограничены 2 MiB; пути relative, без выхода за каталог; source digests и exact fragment binding проверяются существующим контрактом. Другой definition contract требует явно новой совместимой конфигурации, не молчаливого пересчёта.

`classification-selected-probes/v1` проверяет выбранные expected fragment/predicate/stance: среди результатов того predicate/fragment должна присутствовать ровно expected stance. Не измеряет свободную семантику valueText, unsupported extra predicates, полноту всего источника или истинность speakers. Проблемы frozen discovery в этом срезе не оцениваются. `probePass` нельзя переименовать в critical-error-free score.

Failure/partial/invalid output дают probePass=false при наличии labels и остаются в total records. Counts относятся к records, не независимым source cases. Fixture содержит один source family и три candidate records; это control-flow diagnostic, не качество модели и не статистическая выборка.

Capture snapshots включают dataset, labels при наличии, code/definitions copies и unsigned artifact manifest. Для replay используется текущий repo CLI; snapshot не заявлен standalone executable. Изменение scorer/dependencies видно по hashes; побайтная идентичность ожидается только при одинаковых версиях.

## Историческое v1 свидетельство 2026-10-09

Dry-run: 3 records, 0 live calls. Replay: 2 completed, 2 structuralPass, 1 probePass, 1 fixture transport failure в denominator. Повторный replay сохранённого dataset дал побайтно одинаковый report. Ключи и API не использовались. Это два CLI-прогона, не подтверждение test-suite или live interoperability.

Следующее: оформить representability audit cases, независимые labels и общий turn/context contract для Stage 1. Затем provider adapter matrix, bounded live execution и расширение существующего MLflow importer, который пока принимает только legacy parking reports.

## Verifier turn capture (experimental ProxyAPI)

A separate `normlab.verifier-experiment/v1` manifest binds synthetic source text,
neutral question IDs, provider, batch tactic, one-call budget and Noul routing
thresholds. This is a contract smoke, not a corpus quality score. Choice and Score
are recorded without imposing an acceptance decision.

```bash
# No SDK credentials or calls required for manifest preflight.
python evaluation/run_verifier.py fixtures/parking-pilot/evaluation-harness/verifier-smoke.json

# Explicit opt-in: one potentially billable request, no retry, no fallback.
# PROXYAPI_API_KEY must be set in the process environment.
.tools/provider-evaluation/bin/python evaluation/run_verifier.py \
  fixtures/parking-pilot/evaluation-harness/verifier-smoke.json \
  --live --output .artifacts/verifier-new-run

# SDK-free replay of the archived live capture; performs zero API calls.
python evaluation/harness.py \
  fixtures/parking-pilot/evaluation-harness/verifier-smoke.json \
  --verifier-capture fixtures/parking-pilot/evaluation-harness/verifier-live-capture.json \
  --output .artifacts/verifier-new-replay
```

The transport records the exact outgoing body and URL but no headers or key.
Capture is written before transport invocation and after completion/failure;
interrupted runs retain `sent` status and must not be retried automatically.
Errors use fixed categories without provider bodies or exception messages.
One call contains at most three questions, with a ten-second transport timeout.
This timeout is not a guaranteed wall-clock deadline. No monetary estimate is
invented: `cost` remains null, while returned token usage is recorded.

Run artifacts preserve the exact manifest bytes, normalized typed response,
request ID, returned model, dependency versions, latency, source/manifest hashes,
and source snapshots with an unsigned file hash inventory. Hashes detect changes
relative to the inventory; they do not authenticate its author. The offline CLI
validates binding and response contracts, then applies the pinned Noul policy.
It does not re-run inference or estimate `criticalErrorFreeRate`.

The committed capture is synthetic and contains no authentication material.
Real narratives may contain personal data: run artifacts stay local by default.
This runner currently supports only the pinned ProxyAPI batch bridge. It does not
connect the production UI, sequential tactics, an MLflow importer, or a Mellea
sampling loop. Those require subsequent experiments.

## Configurable providers — current adapter 0.8.0; historical Stage 1 0.4.0

[Provider configuration](../docs/PROVIDER_CONFIGURATION.md) describes native
TypeSafe/OpenAI and custom full endpoints. `provider_smoke.py` is dry-run by
default; its separate smoke report is not a Stage 1 quality evaluation or replay
capture. Historical v1 evidence and pinned source digests remain unchanged.
Use `requirements-providers-current.txt` for current smoke/SDK contracts and
`requirements-providers.txt` only for exact archived Stage 1 execution. The
copied ProxyAPI bridge also supports current 0.8.0. CI uses one current SDK
environment and a mock-only Stage 1 compatibility probe; it does not disable
production version checks. The native execution runner is SDK-free.

The separate [categorical Responses entry point](../docs/CATEGORICAL_RESPONSES_INTEGRATION.md)
connects ordinary Luna to the released SDK with the same Choice task input,
explicit independent/batch dispatch and label-only metadata. Its smoke report
is a new versioned contract; it is not silently imported into frozen native
archives/scorers or used as a quality score.

## Stage 1 provider execution

[Three-arm Stage 1 transport](../docs/STAGE1_PROVIDER_TRANSPORT.md) connects Jev, native Luna Decisions and Responses Low through CoreInfra application endpoints. Dry-run/replay require no SDK; mock HTTP uses real SDK request construction. Paid execution requires a separate plan-bound permit and operator-confirmed external spending limit.

# Sealed Stage 1 provider scoring

See [candidate-label scorer](../docs/STAGE1_PROVIDER_SCORING.md) and the
[first partial live context](../docs/STAGE1_LIVE_PILOT_2026-10-11.md).

The separate [network retry runner](../docs/STAGE1_NETWORK_RETRIES.md) preserves
each attempt and enforces a shared dispatch cap. Historical no-retry runs remain
unchanged. Use the [retry-aware scorer](../docs/STAGE1_RETRY_SCORING.md) for retry
captures; it keeps first/final outcomes and per-attempt costs separate.

### Retry v2 entrypoints

New retry experiments use `stage1_retry_executor_v2.py` and
`score_stage1_retries_v2.py`. Corpus jobs are exported separately under the 2 MiB
artifact bound, and pending completed children preserve known usage without
exposing a verdict. V1 captures remain replayable by their frozen v1 tools.
See [commands and contracts](../docs/STAGE1_RETRY_SCORING.md#current-entrypoints-v2).
