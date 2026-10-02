# Метрики структуры, решения и изменений v1

Дата: 2026-10-02. **NL-108 реализован для core/CLI** профиля `demo.reform-mitigation/v1`. Методика: `reform-structure-decision-changes/v1`. Последующий [NL-502](LABORATORY_UI.md) подключает metrics к локальным HTTP/SQLite/React UI; свидетельства NL-108 ниже сохраняют исходную область.

## Назначение и единицы

Измерения разделяют структуру представления, условия получения решения и изменения типизированных последствий. Пороги успешности исследования и понятность интерфейса этим срезом не устанавливаются. Срок, штраф, квалификация и валюта сохраняют отдельные единицы; общего индекса гуманности нет.

| Счётчик                            | Единица / представление                             | Правило подсчёта                                                                                                                                  |
| ---------------------------------- | --------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| `provisionCount`                   | Именованный section точного source                  | Один section `### rule-ID` на mapped rule; заголовки моделей, общий контекст и определения не входят                                              |
| `irRuleCount`                      | Authored Legal IR rule                              | Число rules в locked IR; в текущем fixture совпадает с source provisions, это разные представления                                                |
| `groupExpandedRuleCount`           | Пара (rule, group)                                  | Сумма размеров `rule.groups`; вынесение общего правила не удаляет его действие в каждой группе                                                    |
| `operationTemplateCount`           | Typed operation template                            | Число разных canonical операций с учётом mandatory/applyCount, без ID и group scope                                                               |
| `repeatedOperationCount`           | Дополнительный экземпляр operation template         | `irRuleCount − operationTemplateCount`; источник каждого повтора — список rule IDs в template                                                     |
| `definitionCount`                  | Reviewed predicate definition в source              | Число размеченных определений M/N/E; общие определения учитываются для каждой модели, их нельзя суммировать между моделями как разные определения |
| `normativeTextReferenceCount`      | Размеченное ребро (from rule, to rule, source line) | Нормативная отсылка внутри mapped provision; упоминания происхождения и редакционной истории исключены human review                               |
| `exclusionReferenceCount`          | Typed IR edge                                       | От exclusion rule к N scale rule при пересечении groups; это отдельный graph count, не текстовая отсылка                                          |
| `independentConditionCount`        | Predicate identity                                  | Число разных explicit operation triggers в supported IR; в этом profile M/N/E                                                                     |
| `explicitConditionOccurrenceCount` | Пара (rule, trigger)                                | Один явно записанный trigger для каждого scale/exclude rule; implied N guard исключения не является дополнительным explicit trigger               |
| `exceptionCount`                   | Exclude rule                                        | Число authored операций `exclude`                                                                                                                 |
| `humanJudgmentCount`               | Finding identity в profile                          | Три independently reviewed findings M/N/E; group supplied извне и находится вне scope установлений                                                |
| `orderedScalePairCount`            | Typed IR edge M → N                                 | Число пар пересекающихся по groups M/N rules, связанных порядком profile; это structural count, не runtime apply count                            |

Повтор operation не означает одинаковые строки текста или доказанную юридическую избыточность. Сравнение выполняется по точному typed encoding; эквивалентные, но иначе записанные дроби не нормализуются для этого счётчика. Наличие общего template не доказывает, что такое вынесение сохраняет последствия. Для A/B это отдельное [Lean equivalence obligation](COMPARISON_VERIFICATION.md).

Счётчики по authored IR и group-expanded representation явно разделены. Human judgment count не измеряет время работы reviewer, качество evidence или когнитивную сложность.

## Reviewed source annotations

[metric-annotations.json](../fixtures/reform-v1/metric-annotations.json) содержит `normlab.metrics-source-annotations/v1` для A/B/C. Каждая запись связывает точный bundle reference, semantic/provenance/profile digests и source digest с reviewer и утверждением полноты разметки mapped provisions/shared definitions.

- Definition annotation указывает predicate и точную строку source с её текстом.
- Reference annotation указывает from/to rule IDs и точную строку нормативной отсылки.
- Проверяются source digest, exact line text, принадлежность from/to rules модели, положение строки внутри from section, присутствие target ID и отсутствие повторных записей.
- Подсчёт не использует AI или автоматическое распознавание юридического смысла текста.
- Полнота и классификация annotations остаются результатом human review. Проверка адресов и digests не доказывает правильность этой классификации.

Если для модели нет annotation, `definitionCount` и `normativeTextReferenceCount` имеют **null / unavailable**, а не ноль. Остальные IR/source-section counts доступны. Полный набор annotations включён в `annotationsDigest`; использованная запись присутствует в model metrics. CLI replay требует тот же набор. Набор может содержать annotations других моделей; отсутствие записи для текущей модели явно сохраняется.

Учебный erroneous model D имеет собственный source и не покрыт A/B/C annotation. Его source definitions/references обозначаются unavailable. Структура IR и изменения последствий остаются измеримыми.

## Изменения последствий и категории

| Query kind   | Единица наблюдения  | Что сравнивается                                                 |
| ------------ | ------------------- | ---------------------------------------------------------------- |
| `comparison` | Completed input     | Baseline и candidate model на одном identity-mapped входе        |
| `property`   | Mitigation pair     | Одна модель, M=false → true при неизменных group/N/E             |
| `decision`   | Snapshot completion | Все совместимые завершения findings; межмодельного сравнения нет |

Для comparison/property report содержит все наблюдения с input/outcome обеих сторон и списком изменённых components. `changedCount` считает наблюдения, где изменён хотя бы один полный компонент; `unchangedCount` — остальные. Component counters независимо показывают changed/unchanged. Для срока и штрафа дополнительно показаны decreased/increased и min/max delta. **Delta = candidate − baseline**, диапазон включает сохранённые наблюдения. Для qualification/currency порядок величин не вводится.

Категории определены как непересекающиеся пары **(group, baseline M)**. Каждая категория содержит observed/changed counts и изменённые components; N/E остаются явными в полных rows. Это описательное разбиение покрытой области, без утверждения причинности, распределения реальных дел или поиска минимальной формулы категории. Property query считает пары, а не два независимых дела.

Coverage и scope копируются из exact query/certificate projection. При `corpus` статус остаётся `partial`, включая corpus из всех 16 входов. Changed fraction относится только к наблюдениям; она не экстраполируется на непроверенную область. Scope M=true/M=false не превращается во весь D16.

Decision report отдельно показывает число completions, число разных **полных** outcomes и число открытых human judgment points. Две ветви с равными численными последствиями сохраняются: они могут иметь разные findings и ledger. Условный snapshot не получает произвольный выбранный outcome.

## Результат A/B/C

Единицы соответствуют таблице методики; определения — общие source definitions, normative text references — только принятие исключения X в правилах N.

| Метрика                               |   A |   B |   C |
| ------------------------------------- | --: | --: | --: |
| Source provisions / authored IR rules |   7 |   5 |   5 |
| Group-expanded rules                  |   8 |   8 |   8 |
| Operation templates                   |   5 |   5 |   5 |
| Repeated operations                   |   2 |   0 |   0 |
| Shared predicate definitions          |   3 |   3 |   3 |
| Normative text references             |   2 |   1 |   1 |
| Exclusion IR edges                    |   2 |   1 |   1 |
| Independent conditions                |   3 |   3 |   3 |
| Explicit trigger occurrences          |   5 |   3 |   3 |
| Exception rules                       |   1 |   1 |   1 |
| Human judgment points                 |   3 |   3 |   3 |
| Ordered M/N IR pairs                  |   2 |   1 |   1 |

A → B сокращает число именованных положений на 2 и убирает 2 дополнительных экземпляра operations. Число independent findings и group-expanded rules сохраняется. Снижение числа положений само по себе не устанавливает сокращение труда reviewer.

- **A/B, весь D16:** изменено 0/16 full outcomes; все четыре components сохранены.
- **A/C, весь D16:** изменено 8/16, только `prisonMonths`. В двух категориях с M=true изменены все четыре N/E комбинации каждой группы. M=false даёт 0/8 изменений.
- **A/C, M=true scope:** 8/8 strict reductions. Prison delta лежит от −40 до −15 месяцев; на полном D16 диапазон от −40 до 0. Fine delta равен 0 DEMO, qualification/currency сохранены.
- **Unary M:** восемь mitigation pairs каждой модели; их нельзя складывать с completed-input counts.
- **Conditional C, E=true и N открыт:** 2 completions, 1 distinct full outcome, 1 open human judgment point.

Числа относятся только к synthetic profile и D16. Source annotations, математические доказательства и социальная оценка реформы имеют разные основания.

## Pipeline и sidecar

[shared/reform-metrics.ts](../shared/reform-metrics.ts) содержит strict Zod contracts/renderer; [server/reform-metrics.ts](../server/reform-metrics.ts) — projector/recount/replay; [scripts/reform-metrics.ts](../scripts/reform-metrics.ts) — CLI.

1. Проверить exact query, bundles, certificate, snapshot и reconstruction через существующий [explanation projector](EXPLANATIONS.md).
2. Посчитать source/IR/decision counters и проверить переданные source annotations.
3. Сгруппировать certified outcomes по components и фиксированным категориям.
4. Для evidence report выполнить explicit trusted-key check и fresh Lean replay исходного export.
5. При импорте metrics sidecar повторить replay и полный deterministic recount; сравнить весь canonical digest.

`projectReformMetrics` всегда выдаёт `proofStatus=unchecked`. `measureReformExport` выдаёт body только при current receipt. Evidence относится к исходному certificate; Lean не доказывает projector или completeness human annotations. Историческая signature с current=false даёт null body, даже если fresh proof отдельно verified.

`normlab.metrics/v1` связывает query/certificate/models/snapshot/assumptions, methodology, annotations и generator digest. `normlab.metrics-report/v1` дополнительно связывает exact export через artifact digest и actual replay evidence. Generator fingerprint включает metrics schemas/renderer/projector, contracts/bindings и explanation generator fingerprint.

Sidecar **не подписан исходным receipt**. Изменение метрик и пересчёт их hash не заменяют deterministic recount. Markdown — отображение report; сам по себе не служит переносимым proof artifact. Существующие десять generated JSON schemas, receipt format и Lean TCB не меняются.

## Команды

```sh
npm run reform:demo
npm run reform:metrics -- <run>/AB-equivalence.json --issuer-key <run>/issuer-public.pem --annotations <run>/source-annotations.json
npm run reform:metrics -- <run>/AC-component-no-increase.json --issuer-key <run>/issuer-public.pem --annotations <run>/source-annotations.json --format json --out <new-report.json>
npm run reform:metrics -- <run>/C-conditional-exclusion.json --issuer-key <run>/issuer-public.pem --annotations <run>/source-annotations.json --report <run>/C-conditional-exclusion.metrics.json
```

Demo создаёт новый каталог с 12 exports, 12 metrics reports в JSON/Markdown, explanation reports, public key, exact source annotation set и manifest. Private key существует только в памяти. CLI использует bounded file reader со strict UTF-8; JSON input/output ограничен 512 KiB, trusted public key — 16 KiB. `--out` создаёт новый файл без перезаписи. Без `--annotations` source definition/reference counts остаются unavailable.

## Свидетельства этого среза

TypeScript strict, production build и freshness прежних десяти schemas проходят. Локальный run `.artifacts/reform-nl108-final/` сохранил все **12 metrics reports** с current receipts. Все 12 sidecars повторно импортированы через отдельные CLI processes с exact source annotations, trusted public key, fresh Lean replay и deterministic recount; получено `current=true`. Reports предъявляют exact counts, outcomes и evidence, включая bound counterexample и две равные conditional branches. Подсчёт не имеет нового formal theorem. Test suites этого этапа не добавлялись и не запускались; исторические проверки предыдущих этапов перечислены в их отчётах.

**[NL-502](LABORATORY_UI.md)** подключает v2 storage/HTTP и Laboratory UI: A/B/C, explanations, metrics, findings revisions и counterexample explorer. Structural counts показаны с отдельными единицами; current evidence для consequence reports требует fresh replay. Проверка понятности этих метрик участниками остаётся задачей пилота.
