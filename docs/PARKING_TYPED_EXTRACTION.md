# Typed parking extraction and application anchoring

Дата: 2026-10-05. Candidate model wire contract `normlab.parking-extraction-proposal/v2`; внутренний reviewed-proposal vocabulary и normalized graph остаются [v1](PARKING_EXTRACTION_CONTRACT.md). [Implementation](../server/parking-typed-extraction.ts), [model schema](../schemas/parking/model-proposal-v2.schema.json).

## Изменения относительно первого baseline

1. В modelInput включены определения разрешённых entity concepts и typed link catalogue из compiler IR: predicate, domain, range, description. Разрешённый набор определяется contract v1 whitelist, не всеми imported concepts.
2. Модель предлагает exact quote и optional zero-based `occurrence`, не числовые offsets. Source разрешает приложение из сохранённой request revision.
3. Prompt явно напоминает направления roleParticipant/roleAboutEpisode, разделение Payment/Session/Placement, запрет label на ParkingZone, aliases без имён и необходимость сохранять explicit denials.

Это новый contract/prompt digest. Artifacts первой серии не изменены; первый runner сохраняет прежнюю extraction конфигурацию. После серии оба runner дополнены автоматическим manifest, исторические runner hashes относятся к commits, указанным в baseline README. Вывод новой серии сравнивается с первой как результат совместного изменения input catalogue/prompt/anchor representation, не как изолированное доказательство эффекта одного фактора.

## Quote resolution

- Quote отсутствует в source → `quote_not_found`.
- Единственное точное совпадение, occurrence не задан → разрешить его.
- Несколько совпадений без occurrence → `ambiguous_quote`, не выбирать первое скрытно.
- Заданный occurrence вне диапазона → `invalid_occurrence`.
- Для явно выбранного совпадения определить UTF-16 start/exclusive end и проверить полный normalized graph validator v1.

Поиск учитывает и overlapping occurrences; нумерация с нуля в порядке позиции source. Никаких fuzzy matches, normalization, trim, изменения facts/stances/IDs или repair malformed JSON. Final validator проверяет boundaries/surrogate pairs, IDs, evidence, domain/range и episode context. Отсутствие/неоднозначность quote блокирует proposal, не подтверждает факт.

Успешное consume возвращает normalized proposal, application bindings, `reviewState: unreviewed` и `anchoringMethod: exact-source-substring`. Raw output сохраняется отдельно. Приложение не подменяет model wire response вычисленными offsets; normalized graph — derived artifact. Application request должен быть сохранён и сопоставлен с соответствующим ответом; HTTP orchestration/persistence пока отсутствует.

## Baseline reproduction

```bash
rtk proxy npm exec tsx -- scripts/parking-typed-baseline.ts experiments/parking-baseline/new-typed-run
```

По умолчанию model ID `openai/gpt-oss-20b`; если эта модель уже загружена под другим alias, задайте `NORMLAB_PARKING_MODEL` явно. Runner записывает requested alias и returned model; совпадение алиасов само по себе не удостоверяет идентичность weights.

Один запрос на каждую из P01/P02/P04/P09, только source + common catalogue/prompt/schema, без reference/reviewer answers. Temperature 0, seed 42, max_tokens 8192, timeout 240 s, без retries/repair. Старый directory не перезаписывается. Decode mode — prompt-only JSON; совместимость provider grammar проверяется отдельным экспериментом, не считается доказанной.

## Открытые ограничения

Schema и exact anchoring не гарантируют полноту/семантику, корректные aliases или отсутствие придуманных statements. Role-to-vehicle и другие gaps vocabulary из reference corpus остаются открытыми. Не реализованы generic conflict detection, engine mapping, normative lock и UI ingestion. Quality acceptance thresholds ещё не установлены.

## Выполненная серия 2026-10-05

[Отчёт и comparison](PARKING_TYPED_BASELINE_2026-10-05.md): 4/4 завершённых JSON responses, 0/4 accepted proposals. Отдельный replay четырёх candidate reference graphs через v2 quote mode сохранил исходные offsets и прошёл final graph validator; это проверка adapter на известных artifacts, не доказательство качества extraction модели.
