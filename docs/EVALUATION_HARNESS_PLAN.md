# Повторяемый evaluation harness: стратегии, тактики и новые модели

Дата: 2026-10-09. Статус: первый offline replay срез реализован; live/provider matrix и registry extension остаются планом. Связь: [roadmap экспериментов](EXTRACTION_EXPERIMENT_ROADMAP.md), [rubric](EVALUATION_PLAN.md).

Актуальный срез на 2026-10-12: [inventory существующих contracts и пробелов](HARNESS_GAP_INVENTORY_2026-10-12.md) для [#77](https://github.com/SoundBlaster/NormLab/issues/77). Он учитывает Stage 1 provider/retry и S1.3; historical пункты ниже сохраняют исходную дату. Следующий ограниченный результат — общий offline envelope и adapters harness v2 / S1.3.

[Offline envelope v1](OFFLINE_ENVELOPE_V1.md) реализует additive export/reader для этих двух путей. [Runtime verification](OFFLINE_EXPORT_VERIFICATION_2026-10-13.md) пройдена; [paired comparison v1](OFFLINE_PAIRED_COMPARISON_V1.md) добавляет saved-view compare/export с compatibility checks и явными denominators. Его [fixture comparisons](OFFLINE_PAIRED_COMPARISON_2026-10-13.md) не являются model quality evaluation. [Regression coverage и Stage 1 transport adapter](OFFLINE_STAGE1_ADAPTER_2026-10-13.md) добавляют offline first/final/attempt evidence. [Stage 1 seal/reference/score import](OFFLINE_STAGE1_REFERENCE_V1.md) сохраняет candidate provenance и проверяет native score views. Следующие slices — идемпотентный MLflow import и execution/resume contract.

## Задача

При появлении Jev 2, новой Luna или нового способа разбора быстро выполнить один и тот же protocol, сохранить evidence и сравнить результаты с baseline. Проверять отдельно качество стратегии, отдельных тактик, verifier и всей цепочки. Замена модели не должна незаметно менять dataset, prompts, labels, thresholds или условия взаимодействия.

Успех инфраструктуры: новый совместимый provider/model задаётся конфигурацией и проходит contract smoke; существующая матрица запускается без новых ad-hoc скриптов. Изменения wire contract, prompts или schema требуют новой версии адаптера/стратегии и явно помеченного comparison. Это не обещание автоматической совместимости с будущими API.

## Роли инструментов и текущий статус

| Компонент                   | Роль                                                                                  | Что есть / что требуется                                                                                                                             |
| --------------------------- | ------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| Mellea                      | Generation/sampling, requirements, bounded repair выбранного candidate                | Есть classification runner; не заменяет независимые labels и scorer                                                                                  |
| NormLab evaluation runner   | Dataset × strategy × tactic × provider; budgets, captures, replay и paired comparison | Есть отдельные runners/scorers; общий manifest/control plane ещё нужно собрать                                                                       |
| MLflow                      | Registry runs, configuration, metrics/artifacts, этапные traces и human feedback      | `mlflow==3.16.1`, `evaluation/import_mlflow.py`: локальный SQLite registry и offline import уже в коде; новые форматы и tracing ещё не интегрированы |
| Evidently                   | Опциональные visual reports, сравнение распределений/срезов, позже monitoring         | Не подключён; добавить только при конкретной пользе сверх текущих отчётов и MLflow                                                                   |
| Независимый reviewer/scorer | Ground truth и оценка критических ошибок                                              | Candidate expectations и partial probes уже есть; independent review/holdout остаются открытыми                                                      |

MLflow и Evidently поддерживают evaluation/monitoring, но не определяют, какой разбор текста правильный. Их LLM judges не заменяют независимую разметку. Модель, которую исследуем как verifier, не должна единолично выставлять себе итоговый quality score.

## Контракты harness

### 1. Dataset manifest

- Version/hash, immutable sources, family IDs, split, language и paired translation IDs.
- Отдельные inputs, reviewer-only expectations и provenance; labels/scorer versions и review status.
- Представимые/непредставимые/неоднозначные случаи, selected probes и полный review различаются.

### 2. Experiment manifest

- Strategy: discovery/classification, statement-first, source-only reconstruction, validation/repair; любая другая стратегия через тот же контракт результата.
- Tactic: общий/локальный requirement, independent/batch/sequential questions, context policy, question order, examples, IR и segmentation.
- Provider и API route, adapter/dependency versions, requested/returned model, reasoning/sampling settings, prompts/schema hashes.
- Baseline run IDs, arms, seed/schedule, заранее заданные повторы, per-run/case/turn calls/questions/tokens/deadline и repair budget.
- Acceptance policy отдельно от raw predictions; replay не меняет historical predictions, новая policy получает новую version.
- Ключи/Authorization/secret references не сохраняются в captures. Публичный endpoint metadata отделён от secrets; generic exception bodies не печатать.

### 3. Stage/turn captures

- Run/case/arm/attempt/turn IDs, parent IDs, input/source/context hashes и полный synthetic контекст, фактически переданный модели.
- Raw output, parsed annotation, deterministic checks, semantic verdict, abstention/refusal/error, localized repair feedback.
- Request ID, returned model, measured durations/usage/cost; недоступные значения null. Aggregate usage не считать дважды при batched questions.
- Candidate failures и exhausted/cancelled executions сохраняются, нет accepted fallback. Незавершённый capture явно partial, а не успешный run.

### 4. Scoring и comparison

- Deterministic replay scorer без сети: schema, spans, candidate probes и versioned expectations. Независимые human labels прикладываются отдельной revision.
- Frozen predictions можно оценить заново без inference; новые semantic judge calls — отдельный opt-in run с отдельным бюджетом и provenance.
- Case-level critical-error-free score; verifier false acceptance/rejection/abstention и accepted coverage отдельно; omissions, attribution, scope и contradictions по типам.
- Paired per-case regressions/rescues, family slices, uncertainty intervals с подходящей единицей независимости; повтор/перевод не новый независимый case.
- Отдельно report operational completion, correctness, user corrections, latency/cost. При partial review quality остаётся partial/not_evaluated.

## Режимы запуска

Ниже целевые режимы будущего общего CLI; готовые команды этим документом не объявляются.

1. **Plan/dry-run:** проверить manifests, зависимости, dataset и совместимость, показать matrix и верхние лимиты без API.
2. **Offline replay:** rescoring сохранённых artifacts и paired comparison без создания live provider.
3. **Contract smoke:** fixtures/mock transport через настоящий adapter/control flow. Не является live compatibility proof.
4. **Live smoke:** минимальные синтетические requests после явного opt-in, прекращение при provider failure; никакого скрытого fallback.
5. **Bounded evaluation:** фиксированная matrix, checkpoint/case completion и resume только незавершённых tasks. Неизвестный исход отправленного запроса не повторять автоматически: отметить ambiguous и учитывать возможный расход.
6. **Compare/export:** portable JSON/Markdown report, затем идемпотентный MLflow import по run ID/digest; MLflow UI не единственная копия evidence.

## Этапы реализации

### Harness 1 — общий manifest и offline replay

- [ ] Инвентаризировать текущие report schemas и сохранить legacy import без переписывания старых evidence.
- [x] Определить первые offline experiment/capture/labels/report v1 contracts и neutral fixture manifest. Общий multi-turn и полный Stage 1 dataset ещё впереди.
- [x] Добавить dry-run и replay фиксированных capture artifacts без платных запросов: [harness_v2.py](../evaluation/harness_v2.py), [контракт и команды](../evaluation/HARNESS.md). Отдельный one-batch ProxyAPI verifier capture и SDK-free replay реализованы: [live smoke](PROXYAPI_LIVE_CHECK_2026-10-09.md). Общая provider matrix остаётся планом.
- [x] Зафиксировать failure/partial/invalid output в denominators; без labels probes null/not_evaluated. Полный critical-error-free score отсутствует до independent review.

**Gate:** сохранённый запуск воспроизводимо пересчитывается офлайн; capture не содержит secrets/labels в model context. На fixture из 3 records повторный пересчёт snapshot дал побайтно одинаковый report; model/semantic quality этим не оценивалась.

### Harness 2 — provider и interaction matrix

- [x] Подготовить [frozen matched comparison protocol/plan](STAGE1_COMPARISON_PROTOCOL.md) на annotation v2: одинаковый task, public planned request bodies, изоляция contexts, counterbalanced schedule, caps 24/192/12 без inference. `evaluation/plan_stage1_comparison.py` работает без SDK/ключей/сети; исполнение/captures/scoring пока впереди.

- [ ] Подготовить Jev4Mellea 0.3.0 локально с exact pin, отдельным окружением и проверкой compatibility; сохранить исторический 0.2.1 baseline.
- [ ] Подключить Jev Noul/Choice, Luna Responses Low и opt-in Luna Decisions через общие stage/turn records.
- [ ] Реализовать independent/batch/sequential context policy, bounded execution и explicit resume semantics.
- [ ] Первым прогоном подтвердить actual route/model/settings; затем выполнять Stage 1 comparisons.

**Gate:** модель меняется конфигурацией, protocol changes явно versioned; live availability доказана отдельно для выбранного endpoint/account.

### Harness 3 — MLflow registry и regression report

- [ ] Расширить имеющийся offline importer на новый run contract; params/tags содержат strategy/tactic/provider/model/data/scorer versions.
- [ ] Сделать идемпотентный import и ссылки от metrics к raw captures; фиксировать parent/turn tracing при живых прогонах отдельно.
- [ ] Сформировать paired baseline comparison с перечислением regressions и not_evaluated cases; пороги promotion фиксируются заранее после Stage 1.
- [ ] В CI выполнять offline contracts/scoring; live evaluation только вручную по opt-in. Зеленый CI не означает модельный quality pass.

**Gate:** сохранённый новый provider run сравнивается с baseline без повторного платного inference; иной protocol виден в UI/report.

### Harness 4 — решение по Evidently

- [ ] Выбрать конкретный недостающий отчёт: family slices, review burden, input/claim distribution или временной drift.
- [ ] Сравнить полезность одной локальной Evidently report integration с существующим portable report/MLflow. Совпадающие метрики не вычислять с разными denominators.
- [ ] Подключать periodic drift monitoring после появления повторяемых сопоставимых потоков/окон. Drift — сигнал изменения данных, не доказательство ошибки или правильности.

**Gate:** есть проверенная польза и сопровождаемый отчёт. Допустимое решение — Evidently пока не добавлять. Локальные dataset comparison/report возможности допустимы и до production traffic.

## Как проверять Jev 2 или новый релиз

1. Заморозить baseline и inputs/labels/scorer. Отдельно различать новый provider adapter и новую model version.
2. Dry-run/contract smoke; затем один live compatibility probe с конкретным account/route.
3. Выполнить ту же matrix на фиксированных candidates; далее выбранные полные pipelines, если это входит в эксперимент.
4. Replay scoring и paired report, MLflow import; записать improvements, regressions, uncertainty и расходы.
5. Принять решение continue / investigate / reject / promote. Новый номер версии не является основанием promotion; independent review остаётся обязательным.

## Источники

- [MLflow evaluation and monitoring](https://mlflow.org/docs/latest/genai/eval-monitor/) — datasets, custom scorers, feedback и tracing; совместимость с закреплённой версией проверить при реализации.
- [Evidently library](https://docs.evidentlyai.com/docs/library/overview) — evaluation metrics, exportable reports и monitoring; это опциональная интеграция.
- [Jev4Mellea 0.3.0](https://github.com/SoundBlaster/Jev4Mellea/releases/tag/v0.3.0) — OpenAI primitives и provider evaluation; live native availability отдельное свидетельство.

## ProxyAPI bridge — подготовка 2026-10-09

Экспериментальный bridge скопирован из immutable commit ветки
`proxyapi-adapter` в [evaluation/providers](../evaluation/providers/README.md).
Он переиспользует выпущенный adapter 0.3.0; опубликованный native OpenAIProvider
не заменяет proxy state/questions wire contract. Factory читает PROXYAPI_API_KEY
только при явном construction. Верхнеуровневые зависимости закреплены отдельно
в requirements-providers.txt; старое окружение 0.2.1 сохранено. Offline CLI
не переключён на live calls; provider/multi-turn интеграция остаётся следующим
срезом. Upstream license metadata discrepancy зафиксирована в provenance.

[Offline bridge verification](PROXYAPI_OFFLINE_CHECK_2026-10-09.md): 41 tests
passed against installed 0.3.0, with fake transport and real Requirement hooks.
Provider contracts are now included in CI. One bounded live batch and SDK-free turn replay passed: [live report](PROXYAPI_LIVE_CHECK_2026-10-09.md). No corpus quality inference follows from this smoke.

[Stage 1 annotation v2](STAGE1_ANNOTATION_V2_2026-10-09.md) preserves 16 sources, 13 families and 32 records with explicit semantics and repeated LLM review. Labels remain candidates, not expert ground truth. [Fair comparison protocol](STAGE1_COMPARISON_PROTOCOL.md) and offline plan are frozen; live execution and quality evidence remain pending.
