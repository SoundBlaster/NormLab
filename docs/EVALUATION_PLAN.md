# Evaluation и проверка извлечения

## Цель, согласованная 2026-10-05

Цель — не менее 80% кейсов без критических ошибок **до** вмешательства человека. После ручной проверки измеряется отдельный результат; исправления пользователя не повышают score исходной модели. Четыре synthetic candidate cases — diagnostic set, не достаточный release benchmark.

Критические ошибки: потеря отрицания/противоречия; неподдержанное источником утверждение; неверный участник, автомобиль или эпизод; превращение unknown в false; потеря обязательного факта. Синтаксис и graph validity — отдельные обязательные gates. Юридическая корректность требует отдельной экспертной проверки норм и результатов.

## Реализация

1. Evaluation contract и candidate expectations для существующих P01/P02/P04/P09. Автоматические проверки проверяют явно перечисленные ожидания; непроверенная семантика остаётся pending, а не pass.
2. Импорт неизменённых raw baseline artifacts, scoring без повторного inference, локальный MLflow как registry прогонов, metrics и reports. JSON artifacts/hashes остаются независимым источником evidence.
3. LangExtract как альтернативный statement-first extractor. После диагностического single-pass baseline реализован двухэтапный вариант: literal assertions без predicates, затем классификация фрагментов по определениям признаков и polarity. Второй этап ссылается на fragment IDs, исходные quotes не переписываются. Few-shot examples отделены от evaluation cases. Local provider, дополнительные definitions и structured output фиксируются как новая конфигурация, не изолированный эффект числа проходов.
4. Локальный экран проверки: источник, выделение текста, создание/редактирование/отклонение утверждений, обязательное подтверждение каждого. Сохраняются исходное предложение, новые review revisions и источник. Изменение фабулы требует явного создания нового draft; предыдущая цепочка сохраняется, подтверждения сбрасываются.
5. Отдельный holdout и экспертная разметка перед заявлением о достижении 80%. MLflow хранит и machine checks, и human review отдельно. Evidently отложен до появления пользовательского потока.

## Границы первой реализации

Экран statement review — экспериментальный этап извлечения; он не выносит решение по КоАП и не запускает Lean. Ручное подтверждение устанавливает review status, не доказывает юридическую истинность. Сохранение statements не означает, что весь ontology graph уже построен.

Labels имеют статус candidate. `candidate_case_pass_rate` показывает выполнение кодируемых expectations; `release_case_pass_rate` отсутствует до independent expert review. Не подсчитываем precision/recall по совпадению generated IDs. Пропущенный этап имеет not_evaluated, provider failure остаётся в denominator. Показатели latency разделяются по runtime configuration.

## Acceptance первой реализации

- Сохранённые серии импортируются без model calls; source/contract/raw identity доступны в отчёте.
- P09 с отрицанием только в unmappedMentions не проходит conflict-preservation check.
- Отрицание faultAndExclusions по отсутствию payment corrections не считается корректным выводом.
- LangExtract outputs проходят independent exact quote validation; fuzzy/unlocated extraction не принимается автоматически.
- UI сохраняет revisions и manual provenance; редактирование снимает подтверждение изменённого утверждения и общий reviewed status.
- В MLflow можно сравнить отчёты, сохраняя версии labels/scorer и полную конфигурацию.

## Источники решений

- [MLflow code-based scorers и replay traces](https://mlflow.org/docs/latest/genai/eval-monitor/scorers/custom/tutorial/)
- [MLflow datasets и SQL backend](https://mlflow.org/docs/latest/genai/datasets/)
- [Google LangExtract](https://github.com/google/langextract), Apache-2.0
- [Luna comparison](PARKING_LUNA_COMPARISON_2026-10-05.md)
