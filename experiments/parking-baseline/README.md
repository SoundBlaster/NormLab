# Parking baseline runs

[Серия 2026-10-04 GPT OSS 20B](2026-10-04-gpt-oss-20b/) содержит raw requests/responses, content, validation results, runtime observations и unsigned SHA-256 manifest. [Отчёт](../../docs/PARKING_BASELINE_2026-10-04.md) разделяет structural/semantic/provider ошибки. Все исходные тексты synthetic; artifacts могут содержать исходные synthetic имена.

## Повторение

```bash
rtk proxy lms load openai/gpt-oss-20b --context-length 16384 --ttl 1800 --yes
rtk proxy npm run parking:baseline -- experiments/parking-baseline/new-run
```

Нужен работающий LM Studio API на `127.0.0.1:1234` и скачанная модель. Runner использует только source.txt из reference corpus и common application prompt/schema; не читает graph/manifest/reviewer notes для запросов. Timeout 240 s на case, 4 последовательных запроса, без повторов. Existing output directory отклоняется; старые результаты не перезаписываются.

Результат каждого case записывается сразу. `summary.json` обновляется после каждого завершённого case; при interruption он может описывать неполную серию. Exit 0 означает завершение capture loop, **не** прохождение model acceptance. Runtime model loading/config/version собираются отдельно; model list snapshot не удостоверяет веса/их hashes. В первой серии runtime-observation.json содержит явно обозначенные наблюдения оператора после прогона.

HTTP response files и model content сохраняются без formatting/repair. Validation results — derived artifacts, не исправленные ответы модели. Для проверки digest используйте artifact-manifest.json; manifest не подписан и сам по себе не подтверждает подлинность эксперимента.

Runner автоматически создаёт manifest после завершения всех четырёх cases; при interruption завершённого manifest может не быть. Если позже добавлены runtime observations, manifest нужно сформировать заново после последней записи. Historical artifacts и их digests сохранены: runnerSha256 первой серии относится к runner в commit `1a97369`, до добавления автоматического manifest.

## Typed/quote серия

[2026-10-05](2026-10-05-typed-quotes-gpt-oss-20b/): новая wire schema v2, typed catalogue, application-resolved offsets. [Отчёт](../../docs/PARKING_TYPED_BASELINE_2026-10-05.md). Для повторения используйте `scripts/parking-typed-baseline.ts` с новым output directory; `NORMLAB_PARKING_MODEL` выбирает явно загруженный alias. Оба runner автоматически создают manifest. Исторический runnerSha256 второй серии относится к commit `a8d6cb7`, до добавления автоматического manifest; первая конфигурация extraction сохраняется в отдельном runner.

## Codex Luna low comparison

[Серия](2026-10-05-codex-gpt-6-luna-low/), [отчёт и ограничения сравнения](../../docs/PARKING_LUNA_COMPARISON_2026-10-05.md). Вход v2 совпадает с typed GPT OSS серией; Codex CLI добавляет собственный context и отличается decoding/transport. 4/4 shape/quote pass, 1/4 structural pass; семантическая готовность не подтверждена. Runner `scripts/parking-codex-baseline.ts` сохраняет requests, events, raw final messages, stderr, validation и manifest.
