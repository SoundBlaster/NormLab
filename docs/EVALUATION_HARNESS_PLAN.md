# Повторяемый evaluation harness: стратегии, тактики и новые модели

Дата: 2026-10-09. Статус: план реализации, не готовый runner. Связь: [roadmap экспериментов](EXTRACTION_EXPERIMENT_ROADMAP.md), [rubric](EVALUATION_PLAN.md).

## Задача

При появлении Jev 2, новой Luna или нового способа разбора быстро выполнить один и тот же protocol, сохранить evidence и сравнить результаты с baseline. Проверять отдельно качество стратегии, отдельных тактик, verifier и всей цепочки. Замена модели не должна незаметно менять dataset, prompts, labels, thresholds или условия взаимодействия.

Успех инфраструктуры: новый совместимый provider/model задаётся конфигурацией и проходит contract smoke; существующая матрица запускается без новых ad-hoc скриптов. Изменения wire contract, prompts или schema требуют новой версии адаптера/стратегии и явно помеченного comparison. Это не обещание автоматической совместимости с будущими API.

## Роли инструментов и текущий статус

| Компонент | Роль | Что есть / что требуется |
| --- | --- | --- |
| Mellea | Generation/sampling, requirements, bounded repair выбранного candidate | Есть classification runner; не заменяет независимые labels и scorer |
| NormLab evaluation runner | Dataset × strategy × tactic × provider; budgets, captures, replay и paired comparison | Есть отдельные runners/scorers; общий manifest/control plane ещё нужно собрать |
| MLflow | Registry runs, configuration, metrics/artifacts, этапные traces и human feedback | `mlflow==3.16.1`, `evaluation/import_mlflow.py`: локальный SQLite registry и offline import уже в коде; новые форматы и tracing ещё не интегрированы |
| Evidently | Опциональные visual reports, сравнение распределений/срезов, позже monitoring | Не подключён; добавить только при конкретной пользе сверх текущих отчётов и MLflow |
| Независимый reviewer/scorer | Ground truth и оценка критических ошибок | Candidate expectations и partial probes уже есть; independent review/holdout остаются открытыми |

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
- [ ] Определить versioned run/case/turn contracts и neutral Stage 1 dataset manifest.
- [ ] Объединить dry-run, capture и replay для fixed candidates без платных запросов.
- [ ] Зафиксировать правила отсутствующих outputs, partial runs и denominators.

**Gate:** сохранённый запуск воспроизводимо пересчитывается офлайн; capture не содержит secrets/labels в model context.

### Harness 2 — provider и interaction matrix

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
