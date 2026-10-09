# Stage 1: matched verifier protocol v1

Дата: 2026-10-09. Статус: **frozen offline plan**, inference не выполнялся.
[Manifest и сохранённые summaries](../fixtures/parking-pilot/stage1-comparison-v1/README.md)
связаны с [annotation v2](STAGE1_ANNOTATION_V2_2026-10-09.md) через SHA-256.

## Что сравниваем

Одинаково ли Jev и обычная Luna Low распознают поддержку готового candidate
исходным текстом? Это verifier experiment на ручном diagnostic IR. Он не измеряет
discovery/extraction, полноту фабулы, правовую квалификацию или целевые 50%/80%.
Текущий production contract сохраняет выбранный typed смысл только C004; richer
IR здесь является входом для verifier, а не результатом production extractor.

Первый matched arm использует **общий three-way Choice**. Это новая постановка,
отдельная от прежнего предложения Jev Noul vs обязательный boolean Luna: там
abstention contracts различаются. Noul/boolean, локальные вопросы, восстановление
stance без candidate, язык, independent/batch/sequential остаются отдельными
ablation experiments. Их эффект этим планом не исследуется.

## Вход и вопрос

Каждый запрос получает один неизменный original source и claims только одного
candidate. Общий task содержит `sourceText`, `candidateClaims`, predicate definitions,
identity/operator/scope conventions и один именованный вопрос `overall`.
Jev получает state/questions; Luna — тот же canonical JSON внутри Responses input
с JSON Schema ответа. Различия wire format сохраняются в planned requests.

| Ответ | Значение |
| --- | --- |
| `compatible` | Все выбранные claims поддержаны исходником при заданных conventions. |
| `incompatible` | Есть установленное несовпадение predicate, stance, modality, role, claimant, episode или scope. Установленная ошибка имеет приоритет над неопределённостью других claims. |
| `indeterminate` | Установленной ошибки нет, но поддержка выбранного claim не определяется без разрешения неоднозначности/недостатка свидетельств. |

Explicit-unknown claim может быть полностью поддержан текстом и получить
`compatible`. Necessity/obligation/conditional/hypothetical и отрицание speech act
не подтверждают actual payment. Null vehicle reference не задаёт identity.
Пропущенные факты вне selected claims не входят в этот quality contract.

Точные instructions/criteria зафиксированы в manifest. Нет few-shot примеров,
reference answers, expected labels, mutation descriptions, reviewer notes,
`requiredTypedFields` или исторических verdicts. Compiler не читает
`reviewer-only.json`/raw review. Reviewer-only expectations доступны будущему
offline scorer после фиксации predictions.

## Модели и маршруты

| Arm | Endpoint | Requested model/settings |
| --- | --- | --- |
| Jev через CoreInfra | `https://hub.coreinfra.ai/typesafe/api/v1/systemone` | `jev-1.13.0`, Choice, без дополнительных sampling settings |
| Обычная Luna через CoreInfra | `https://hub.coreinfra.ai/codex/api/v1/responses` | `gpt-6-luna`, `reasoning.effort=low`, `max_output_tokens=1024`, `store=false`, strict JSON Schema |
| Дополнительный Luna Decisions | `https://api.proxyapi.ru/v1/decisions` | `openai/gpt-6-luna-decisions`, Choice через существующий proxy wire contract |

Это requested configuration, не утверждение о доступности модели для конкретного
account. В live evidence нужны actual endpoint/body, returned model, request ID,
usage, duration, dependency versions и status. Первую returned model version
фиксировать для arm; смена внутри запуска останавливает серию. Requested Low не
выдавать за аттестацию фактического reasoning effort. При несовместимости нет
перехода на другой endpoint/model/Chat Completions.

Ключи будущий executor берёт из `COREINFRA_API_KEY` или `PROXYAPI_API_KEY`.
Planner не читает окружение и не создаёт provider. Auth не входит в model input,
manifest snapshots или planned request bodies. Текущий CLI не имеет live-режима.

## Контекст, порядок, повторы

1. Новый context для каждого source/candidate/arm/repeat. Нет previous response,
   conversation ID, tools, накопленной истории или ответа соседнего candidate.
2. Один request содержит один `overall` Choice. Это одноэлементный batch; по нему
   нельзя заключать о преимуществе batch над independent/sequential тактиками.
3. Три повтора заданы заранее; они измеряют variability, не добавляют новых cases.
4. Case order циклически сдвигается между rounds; порядок двух neutral record IDs
   и начальный arm чередуются детерминированно без чтения labels. В pilot 6 пар
   начинаются с Jev и 6 с Luna; в corpus — 48/48.
5. Concurrency 1, без adaptive stopping при хорошем/плохом semantic ответе,
   retries, repair, смены prompt, дополнительных уточняющих вопросов и тюнинга
   thresholds. Provider/format/budget failures останавливают серию с partial report.

Язык первого запуска — русский. Переводы ещё не прошли отдельный review; H1 о
языке остаётся открытой. Augmentation не входит в эти входы.

## Budget profiles

| Profile | Cases / families | Arms | Repeats | HTTP calls / questions | Wall deadline |
| --- | --- | ---: | ---: | ---: | ---: |
| `pilot` | C002, C008 / 2 | Jev + Luna Low | 3 | **24** = 2 × 2 candidates × 2 arms × 3 | 900 s |
| `corpus` | все 16 / 13 | Jev + Luna Low | 3 | **192** = 16 × 2 × 2 × 3 | 7200 s |
| `decisions-pilot` | C002, C008 / 2 | Luna Decisions | 3 | **12** = 2 × 2 × 1 × 3 | 450 s |

Profiles независимы, не запускаются цепочкой автоматически. Выполнение всех трёх
означало бы 228 вызовов; corpus заново включает pilot cases, их нельзя считать
новыми независимыми наблюдениями или объединять в улучшенную метрику.

Для каждого profile: 30 s transport timeout, максимум 32768 UTF-8 bytes общего
semantic task на request, ноль retries/repair. HTTP framing не входит в этот input
byte limit. Luna output ceiling включает её API output budget; у Jev/Decisions
аналогичный ceiling здесь не заявлен. Это не равные token/cost budgets.

**Authorized calls сейчас: 0.** Request caps — предложенные условия будущего
исполнения. Стоимость неизвестна (`monetaryCap=null`, `pricingVerified=false`):
лимит запросов не гарантирует денежный предел. До live нужен отдельный execution
opt-in, связанный с plan digest, актуальным тарифом/доступным балансом и денежным
ограничением. Первый route/model compatibility request входит в выбранный cap,
а не добавляется скрытым smoke сверх него. Если требуется другая постановка probe,
она получает собственный manifest и budget.

Timeout/unknown outcome после отправки записывать как возможно оплаченный
request; автоматически не повторять и не resume. Future runner должен сохранять
prepared/sent/completed/failed/not-executed states и проверять caps до отправки.
Compiler пока только проверяет и показывает эти условия; runtime enforcement,
provider parsing/captures и scorer этим PR не реализованы.

## Scoring до просмотра результатов

Все planned jobs остаются в отчёте, включая failures и неотправленный остаток.
Отдельно показывать scheduled/sent/completed/valid-output/failed/not-executed.
Raw choices и provider probabilities сохранять отдельно от interpretation.
Для primary comparison используется только выбранный label: не сравнивать Jev
confidence и self-reported Luna confidence как одинаковые probabilities.

| Метрика | Denominator и статус |
| --- | --- |
| False acceptance | `compatible` на заранее размеченном incompatible candidate; показать count/все planned mutant jobs и count/valid mutant outputs, completion отдельно. |
| Baseline rejection | `incompatible` на compatible baseline; отдельно `indeterminate`, invalid output и failure. |
| Label agreement | Совпадение с candidate expectations; не expert accuracy и не critical-error-free rate. |
| Contrast discrimination | Baseline compatible и mutation incompatible в том же case/repeat/arm; incomplete pairs отдельно, весь planned pair denominator сохранён. |
| Variability | Распределение трёх labels по repeat для одного record/arm; повторы не независимая выборка. |
| Operational evidence | HTTP calls, questions, latency range/median, returned versions/request IDs, usage и измеренная стоимость; unavailable значения null. Usage batch считать один раз. |

Pilot включает только polarity и speech-act contrast, поэтому не оценивает все
категории. Полный diagnostic corpus содержит 13 families; это development set с
LLM-reviewed candidate labels, не holdout или статистическое доказательство
превосходства. Не подбирать thresholds по этим результатам. Protocol/gateway
различия остаются confounds: вывод относится к двум endpoint+model configurations.

## Воспроизведение offline plan

Из корня проекта:

```bash
python -S evaluation/plan_stage1_comparison.py fixtures/parking-pilot/stage1-comparison-v1/experiment.json
python -S evaluation/plan_stage1_comparison.py fixtures/parking-pilot/stage1-comparison-v1/experiment.json --profile corpus
python -S evaluation/plan_stage1_comparison.py fixtures/parking-pilot/stage1-comparison-v1/experiment.json --profile decisions-pilot
python -S evaluation/plan_stage1_comparison.py fixtures/parking-pilot/stage1-comparison-v1/experiment.json --output .artifacts/new-comparison-plan
python -m unittest discover -s evaluation -p 'test_stage1*.py'
```

Export создаёт новый каталог: `plan.json` — index с hashes, `jobs/Jxxxx.json` —
отдельные planned bodies/context hashes, `summary.json` — сводка. Corpus целиком
превышает 2 MiB, поэтому экспорт разбит на jobs для совместимости с bounded
artifact loader. Существующий каталог не перезаписывается. SDK/ключи/сеть не нужны.
Summaries всех трёх profiles сохранены в fixture и проверяются в CI.

Для Jev 2 или другой совместимой model version можно задать requestedModel в
новой revision конфигурации и получить новый manifest/plan digest без изменения
compiler. Изменения wire protocol, settings, questions, tactics или dataset
требуют отдельной версии и обозначения confounds. Старые evidence не переписывать.

## Проверки реализации

- 32 Stage 1 unittest checks: старые audit/review и новый protocol compiler.
- 90 общих offline tests: provider contracts, verifier capture, Mellea и Stage 1.
- Ruff 0.15.0 lint/format прошли для evaluation/.
- CLI работает с `python -S`; corpus export обратимо читается существующим
  bounded artifact loader. Проверены hashes, пары/порядок, общие task bytes,
  оригинальные claims/quotes, отсутствие labels/auth/history и overwrite guard.
- Provider не создавался, ключи не читались, live requests не выполнялись.

**Следующий шаг:** bounded executor с настоящими adapter/control-flow mocks,
capture/replay и enforcement этих budgets. Затем отдельно разрешённый compatibility
pilot; запуск модели и получение quality evidence ещё впереди.
