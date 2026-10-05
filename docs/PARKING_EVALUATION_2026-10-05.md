# Parking extraction evaluation — 2026-10-05

## Evidence boundary

Цель пользователя: 80% кейсов без критических ошибок до human correction. P01/P02/P04/P09 — четыре synthetic diagnostic cases; labels candidate, independent expert approval отсутствует. Ни один вариант пока не прошёл все автоматические candidate checks. Это не оценка качества на пользовательской популяции.

Финальный replay: [report.json](../experiments/parking-evaluation/2026-10-05-two-stage-final/report.json). Входные SHA256 manifests проверены; snapshots scorer и expectations сохранены. Исторические outputs не изменены.

| Конфигурация | Gate scope | Gate pass | Все candidate checks |
|---|---|---:|---:|
| GPT OSS typed quotes | ontology graph | 0/4 | 0/4 |
| Codex Luna low | ontology graph | 1/4 | 0/4 |
| LangExtract, exact reanchoring | statement proposals | 1/4 | 0/4 |
| Двухэтапный GPT OSS | statement proposals | 2/4 | 0/4 |

Graph и statement gates проверяют разные контракты; сравнение их rates не доказывает превосходство модели. Новая конфигурация меняет schemas, prompts, definitions и количество calls одновременно. Release score остаётся null. UI/browser walkthrough и полноценный end-to-end legal calculation в этой серии не выполнялись.

## Двухэтапная серия

[Raw artifacts](../experiments/parking-baseline/2026-10-05-two-stage-gpt-oss-20b/artifact-manifest.json): локальный LM Studio, `openai/gpt-oss-20b`, temperature 0, seed 42; LangExtract 1.7.0. Первый этап выделяет literal statements без predicates. Второй ссылается на fragment IDs и классифицирует по определениям признаков. Quote, subject и episode берутся из первого этапа, не из классификатора. Оба ответа и промежуточные fragments сохранены.

| Case | Fragments | Statements | Quarantine | Время, s | Основная проблема |
|---|---:|---:|---:|---:|---|
| P01 | 5 | 10 | 8 | 35.877 | Нет отрицания permit; часть цитат не совпала с источником; paymentComplexity также ошибочно привязано к фразе о платном режиме |
| P02 | 8 | 14 | 0 | 30.248 | Неподдержанное отрицание faultAndExclusions; неверная дополнительная привязка paymentComplexity |
| P04 | 5 | 12 | 0 | 22.218 | Неподдержанный paidRegime из факта оплаты |
| P09 | 0 | 0 | 0 | 2.579 | Первый этап вернул `extractions: []`; второй этап не выполнялся |

P09 не проходит final gate: пустой ответ не считается успешной extraction. Предварительный [report](../experiments/parking-evaluation/2026-10-05-two-stage-comparison/report.json) ошибочно считал empty response структурным успехом (3/4); scorer исправлен, сохранён новый final replay (2/4). Raw inference evidence осталось прежним. Текущий worker также останавливается с error, если ни одного fragment нельзя привязать к источнику.

## Предыдущие LangExtract серии

- Первый local-provider запуск остановился на P01: LM Studio отклонил `json_object` response format. Остальные случаи не выполнялись. [Artifacts](../experiments/parking-baseline/2026-10-05-langextract-gpt-oss-20b/artifact-manifest.json).
- Explicit JSON Schema позволила получить ответы для всех четырёх случаев. [Artifacts](../experiments/parking-baseline/2026-10-05-langextract-schema-gpt-oss-20b/artifact-manifest.json).
- Offline exact reanchoring восстановил уникальные дословные цитаты, не меняя смысл/stance. Это replay без новых model calls; latency перенесена из исходного inference. [Derived artifacts](../experiments/parking-baseline/2026-10-05-langextract-exact-reanchored/artifact-manifest.json).

Точная привязка не исправила semantic ошибки. P09 в single-pass сохраняет два opposing payment assertions, но утверждает paymentComplexity по цитате «Ошибок реквизитов и последующих исправлений не было». P02 путает отсутствие разрешений с отрицанием платного режима.

## Что готово

- Локальный MLflow registry с native code-based scorers и sample-wise evidence, без LLM judge.
- Independent quote checks, source binding и artifact manifests.
- UI review: source selection, ручные assertions, edits, confirm/reject, checklist, immutable revisions и export.
- Новый source draft сохраняет прежнюю цепочку и сбрасывает подтверждения.

## Следующий ход

Разметить ошибки каждого этапа отдельно: missed assertion, wrong predicate, polarity, unsupported inference, attribution. Затем добавить независимые учебные примеры отрицаний и ограничить классификацию неподдержанных predicates, сохранив эту серию как baseline. Для проверки улучшения нужен новый holdout, не только переоптимизация этих четырёх кейсов. После human review подключать confirmed statements к ontology graph; legal result validation остаётся отдельным gate.
