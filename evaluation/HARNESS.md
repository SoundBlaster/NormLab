# Offline evaluation harness v1

Первый реализованный срез [плана](../docs/EVALUATION_HARNESS_PLAN.md). Общая live matrix, multi-turn execution, MLflow import нового формата и независимый case-level quality review пока не реализованы.

## Запуск из корня репозитория

Python 3.10+; внешние Python зависимости и ключи не нужны. Используются текущие deterministic contracts из `mellea_candidate.py`, `classification_v3.py`, `anchor.py`.

```bash
python3 evaluation/harness.py fixtures/parking-pilot/evaluation-harness/experiment.json \
  --labels fixtures/parking-pilot/evaluation-harness/reviewer-labels.json --dry-run

python3 evaluation/harness.py fixtures/parking-pilot/evaluation-harness/experiment.json \
  --labels fixtures/parking-pilot/evaluation-harness/reviewer-labels.json \
  --output .artifacts/harness-run-001

python3 evaluation/harness.py .artifacts/harness-run-001/dataset/experiment.json \
  --labels .artifacts/harness-run-001/reviewer-labels.json \
  --output .artifacts/harness-rescore-001
```

Каждый output — новый каталог. Без `--labels` semantic probes остаются not_evaluated/null; структура проверяется. Dry-run проверяет manifest, digests, source binding и labels, не создаёт output. CLI не имеет live mode и не конструирует provider.

## Контракт первого среза

- `normlab.evaluation-experiment/v1`: experiment/dataset identity, strategy/tactic, provider metadata, offline budget, hashed definitions, cases и records.
- `normlab.evaluation-capture/v1`: record/source/parent identity, returned model и один classification turn. Status completed/failed/partial; raw output только completed; ошибки безопасными enum, без HTTP body. Usage/latency/cost в fixture v1 всегда null.
- `normlab.evaluation-labels/v1`: отдельный reviewer-only файл, bound к полным bytes manifest через experimentDigest, candidate review status, payment probes по record IDs. Labels не часть model input; в этом срезе model input вообще не отправляется.
- `normlab.evaluation-replay/v1`: per-record structure/probe results и counts, manifest/labels/scorer/dependency/definitions hashes. `criticalErrorFreeRate` всегда null, verifier quality not_evaluated.

Manifest/artifacts/labels полностью валидируются до записи output. Файлы ограничены 2 MiB; пути relative, без выхода за каталог; source digests и exact fragment binding проверяются существующим контрактом. Другой definition contract требует явно новой совместимой конфигурации, не молчаливого пересчёта.

`classification-selected-probes/v1` проверяет выбранные expected fragment/predicate/stance: среди результатов того predicate/fragment должна присутствовать ровно expected stance. Не измеряет свободную семантику valueText, unsupported extra predicates, полноту всего источника или истинность speakers. Проблемы frozen discovery в этом срезе не оцениваются. `probePass` нельзя переименовать в critical-error-free score.

Failure/partial/invalid output дают probePass=false при наличии labels и остаются в total records. Counts относятся к records, не независимым source cases. Fixture содержит один source family и три candidate records; это control-flow diagnostic, не качество модели и не статистическая выборка.

Capture snapshots включают dataset, labels при наличии, code/definitions copies и unsigned artifact manifest. Для replay используется текущий repo CLI; snapshot не заявлен standalone executable. Изменение scorer/dependencies видно по hashes; побайтная идентичность ожидается только при одинаковых версиях.

## Свидетельство 2026-10-09

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
