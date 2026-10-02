# Deterministic explanations v1

Дата: 2026-10-02. **NL-406 выполнен для core/CLI** профиля `demo.reform-mitigation/v1`. HTTP, SQLite и React UI сохраняют M0/v1; их интеграция остаётся NL-502.

## Что получает пользователь

- Для decision: все совместимые ветви, исходные findings и rationale, числовая цепочка, полный rule ledger и summary со статусом `unresolved`.
- Для comparison/property: оба последствия, отдельные изменения qualification/prisonMonths/fineAmount/currency, правила с изменёнными operations/conditions/statuses/step values и bound counterexample.
- Для каждого правила: source ID/digest, anchor, точные строки section и origin rule IDs. Несовпадение группы, ложное условие и exclusion имеют отдельные reason codes.
- Отдельно: assumptions, scope, coverage, signature trust, fresh proof status/method и current status receipt.

Explanations строятся из typed artifacts, без AI. Narrative не превращается в finding и не дублируется в sidecar; rationale сохраняется. Выбор группы, истинность findings и fidelity перевода source находятся за пределами proof.

## Pipeline и границы свидетельств

[server/reform-explanations.ts](../server/reform-explanations.ts) реализует producer-consistent projector; [shared/reform-explanations.ts](../shared/reform-explanations.ts) — strict Zod schemas, общие types и Markdown renderer.

1. Проверить locked bundles, query/certificate/snapshot bindings и coverage.
2. Для decision сопоставить весь result с locked-model reconstruction, затем читать **steps и ledger из certificate**.
3. Для general query восстановить branch через существующий TypeScript producer и проверить точное совпадение с certified outcome. Comparison certificate содержит outcomes, а не ledger; origin такой trace — `reconstructed-from-locked-model`.
4. Проецировать events, source references, числовые различия и rule changes в deterministic data.
5. Для evidence report выполнить trusted signature/bindings check и **fresh Lean replay**. Explanation body доступен только при `current=true`.

`projectReformExplanation` всегда возвращает `proofStatus=unchecked`: producer consistency не является independent proof. `explainReformExport` формирует отдельный report с actual replay evidence. Lean подтверждает исходное утверждение certificate. Текст renderer и reconstructed ledger comparisons не имеют отдельного Lean proof.

Valid signature с историческим toolchain claim может сочетаться с fresh `proofStatus=verified` и `current=false`; explanation body тогда отсутствует. При чужом issuer proof не запускается, status остаётся `unchecked`. Corpus всегда сохраняет `partial` coverage, даже если переданы все строки.

## Объяснение причины изменения

Сопоставление выполняется по typed operation slots: baseline, M, N, exclusion. IDs и порядок IR array не выбирают behavior; timeline строится в порядке baseline → applied exclusion → M → N.

| Сценарий                        | Что показывает explanation                                                                                     |
| ------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| A/B                             | Последствия и параметры operations равны; source/IDs принадлежат своим моделям                                 |
| A/C при M=true, N=true, E=false | M меняется 2/3 → 1/2; значения следующего N step меняются при сохранённой операции 3/4                         |
| Unary M mitigation              | Меняется input M=false → true и applicability M; параметры модели сохранены                                    |
| A/D counterexample вне M        | N меняется 3/4 → 2/3; K1 получает 90 → 80, остальные компоненты сохранены                                      |
| N открыт, E=true                | Сохраняются две разные ветви с равным сроком; N имеет `inapplicable`/`excluded`, summary остаётся `unresolved` |

Condition origin отделяет terminal **finding**, предположение **completion** открытой ветви и **domain-input** general query. Открытое `not-established` не объясняется как `refuted`.

Source sections извлекаются из точного locked text, от `### rule-ID` до следующего heading уровня 1–3. Повторный heading с тем же ID отклоняется как ambiguous source section. Source mapping удостоверяет адрес и происхождение; interpretation fidelity по-прежнему требует human review.

## Sidecar и повторная проверка

- `normlab.explanation/v1` связывает query/certificate/assumptions/snapshot/model references и `generatorDigest`.
- `normlab.explanation-report/v1` связывает исходный export через `artifactDigest`, projection через `explanationDigest` и отдельные actual replay evidence.
- Generator fingerprint включает projector, schemas/renderer, producer semantics, query helpers, model validation и hashing source; фиксируется при загрузке модуля. Изменение кода требует нового процесса.
- `validateReformExplanation` заново строит projection и сравнивает полный canonical digest.
- `verifyReformExplanationReport` повторяет trusted replay и projection. Исправление hash после подмены текста, числа, coverage или source section не делает sidecar допустимым.

Sidecar **не подписан receipt** и не изменяет `normlab.reform-export/v1`. При импорте нельзя доверять его `current`/proof fields без повторной проверки. Точный исходный export и отдельно выбранный trusted public key остаются необходимыми входами. Markdown — представление данных; standalone Markdown не является переносимым proof artifact.

Новые Zod schemas живут в explanation module; существующие десять generated JSON schemas v2 сохраняются. Report parsing ограничен 512 KiB. Общий CLI reader использует file descriptor, bounded buffer и strict UTF-8 decode; key limit — 16 KiB. Source excerpts выводятся как indented code, rationale/assumptions — как escaped literal text. Реальная browser/DOM проверка будущего UI относится к NL-502.

## Команды

```sh
npm run reform:demo
```

Новый каталог `<run>` в `.artifacts/` содержит **12 exports**, manifest, public key и JSON/Markdown explanations: восемь general queries, общий conditional snapshot в A/B/C и C snapshot с установленным E. NL-108 дополнительно сохраняет [metrics reports и source annotations](METRICS.md). Private key demo существует только в памяти. Каталог и output files создаются без перезаписи.

```sh
npm run reform:explain -- <run>/C-conditional-decision.json --issuer-key <run>/issuer-public.pem
npm run reform:explain -- <run>/AD-preserved-outside-counterexample.json --issuer-key <run>/issuer-public.pem --format json --out <new-report.json>
npm run reform:explain -- <run>/C-conditional-exclusion.json --issuer-key <run>/issuer-public.pem --report <run>/C-conditional-exclusion.explanation.json
```

`--report` проверяет импортированный JSON sidecar; без него report строится заново. По умолчанию выводится Markdown; `--format json` сохраняет structured report. `--out` требует новый файл. Неподтверждённый current receipt, изменённый sidecar, oversized/invalid input или попытка перезаписи дают ненулевой exit code.

## Выполненные проверки

- **35 unit/API tests**: семь новых tests проверяют все **384 explanations / 1296 branches**, все finding states, E/N/M interaction, timeline при перестановке locked rules, exact source sections и changed-operation/propagated-value distinctions.
- Проверено отклонение неправильных steps/outcomes/ledger, ложного verdict, изменённого lock, ambiguous section, подменённых explanation fields и unsupported proof claim.
- **14 Lean integration tests**: две новые проверки охватывают decision/comparison/property, corpus, counterexample, deterministic report replay, rehashed sidecar tampering, wrong issuer и trusted historical receipt.
- Реальный CLI выпускает JSON/Markdown, проверяет sidecar, сохраняет output без перезаписи и отклоняет invalid trust/data. Все прежние M0/v2 Lean checks сохранены.
- TypeScript strict, production build, schema freshness и formatting проходят. Demo предъявляет 12 локальных exports с explanations; отдельный CLI replay проверяет сохранённые sidecars.

[NL-108](METRICS.md) реализует separate structure, decision и consequence-change metrics для core/CLI. Следующий этап — NL-502: v2 storage/HTTP/UI и полный пользовательский A/B/C flow.
