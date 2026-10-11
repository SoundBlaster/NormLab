# Stage 1: offline audit представимости — 2026-10-09

## Набор и границы

Подготовлены 16 synthetic источников на русском, 13 contrast families и 32
кандидата с нейтральными IDs. У каждой фабулы есть ручной diagnostic oracle и
одна single-field mutation: polarity, speaker, episode, predicate, modality или
actor. Источники не заимствованы из новостей/судов; юридических conclusions нет.

**Все labels — candidate, независимого review ещё нет.** Это не новый extractor
и не измерение точности моделей. Все случаи относятся к diagnostic development;
holdout отсутствует. 32 кандидата и варианты одного family не являются 32
независимыми наблюдениями. Полный case-level critical-error-free score не задан.

[Dataset и команды](../fixtures/parking-pilot/stage1-audit/README.md),
[reviewer-only разметка](../fixtures/parking-pilot/stage1-audit/reviewer-only.json),
[machine report](../fixtures/parking-pilot/stage1-audit/audit-report.json).

## Результат для выбранных typed признаков

| Представление | Representable | Lossy | Ambiguous |
| --- | ---: | ---: | ---: |
| Целое предложение + один набор attribution fields | 7 | 7 | 2 |
| Минимальные claims, заданные вручную | 9 | 5 | 2 |

`representable` относится к выбранным полям diagnostic задания, а не ко всему
смыслу текста. `lossy` означает отсутствие структурного адреса для нужной связи;
quote/valueText могут сохранять её свободным текстом. `ambiguous` имеет приоритет
над ограничениями schema: известную неоднозначность не подменяем ground truth.

## Таблица кейсов

| ID / family | Source | Sentence | Claims | Причина / оговорка |
| --- | --- | --- | --- | --- |
| C001 / F001 | Я оплатил парковку. | representable | representable | Выбранные поля выражаются. |
| C002 / F001 | Я не оплатил парковку. | representable | representable | Выбранные поля выражаются. |
| C003 / F002 | Не помню, оплатил ли парковку. | representable | representable | Выбранные поля выражаются. |
| C004 / F002 | Автомобиль стоял на городской парковке. | representable | representable | Выбранные поля выражаются. |
| C005 / F003 | Я оплатил парковку. В письме: парковка не оплачена. | representable | representable | Выбранные поля выражаются. |
| C006 / F003 | Я оплатил парковку, а письмо утверждает, что парковка не оплачена. | lossy | representable | multiple-attributions-in-one-sentence |
| C007 / F004 | Я не мог не оплатить парковку. | ambiguous | ambiguous | no-typed-field:mode Спорное чтение; candidate oracle не единственный ответ. |
| C008 / F005 | Я не утверждал, что оплатил парковку. | lossy | lossy | no-typed-field:mode; no-typed-field:scope; predicate-outside-catalog:speechAct |
| C009 / F006 | Я должен был оплатить парковку. | lossy | lossy | no-typed-field:mode |
| C010 / F007 | Если бы я оплатил парковку, то сохранил бы чек. | lossy | lossy | no-typed-field:mode; no-typed-field:scope |
| C011 / F008 | Допустим, парковка была оплачена. | lossy | lossy | no-typed-field:mode |
| C012 / F009 | Парковку моего автомобиля оплатил друг, а не я. | lossy | lossy | multiple-attributions-in-one-sentence; no-typed-field:aboutEntity; no-typed-field:actor; no-typed-field:scope |
| C013 / F010 | Парковку моей машины я оплатил, а парковку машины друга не оплатил. | lossy | representable | multiple-attributions-in-one-sentence |
| C014 / F011 | Вчера я оплатил стоянку. Сегодня на той же парковке я не оплатил новую стоянку. | representable | representable | Выбранные поля выражаются. |
| C015 / F012 | В письме сообщили, что моя парковка не оплачена. | representable | representable | Выбранные поля выражаются. |
| C016 / F013 | В постановлении: «ТС стояло в зоне ПП; оплаты нет». | ambiguous | ambiguous | Выбранные поля выражаются. Спорное чтение; candidate oracle не единственный ответ. |

## Что обнаружено

1. C006 и C013: у одного предложения несколько наборов speaker/subject/episode.
   Разбиение на claims даёт отдельные атрибуты; текущий whole-sentence prompt не
   даёт per-classification scope. Дублирование полного предложения с разными
   атрибутами само по себе не связывает каждую classification с нужной частью.
2. C008–C012: текущий evaluation slice не имеет typed modality/scope, а actor и
   aboutEntity не выражены отдельными полями. Speech-act predicate отсутствует
   в catalog. Простое уменьшение фрагментов эти ограничения не устраняет.
3. C003 и C004: явное «не помню» и отсутствие упоминания оплаты различаются.
   Во втором случае payment не добавляется даже со stance=unknown.
4. C007: «не мог не оплатить» допускает фактическое и модальное чтения. C016:
   значение сокращения ПП без словаря не фиксируется как платный режим. Оба
   случая требуют review; это не ошибки, определённые по majority vote моделей.

Аудит ограничен `evaluation/discovery_v2.py` → `classification_v3.py` и frozen
fragment contract. Более богатая production ontology целиком не исследована.
Ручной claim oracle служит диагностическим верхним ориентиром для выбранных
полей, но не показывает достижимое качество автоматического segmentation.

## Verification

- 64/64 локальных tests: новый audit + прежние provider/capture/Mellea checks.
- Новый suite: 6 unittest checks без внешних dependencies; CLI также проверен
  с `python -S`, без site packages и обращения к API.
- Проверены source/artifact hashes, Unicode spans, sentence containment, IDs,
  ровно одна объявленная field mutation и отделение reviewer labels.
- Ручные representable projections прошли реальные frozen-fragment и v3
  classification validators. Это structural validation, не semantic judgment.
- Offline report воспроизводим; `liveCalls=0`, `criticalErrorFreeRate=null`.
- Отдельный CI job выполняет audit без network inference.

## Gate и следующий ход

S1.1 частично выполнен: candidate corpus, offsets, frozen definitions, neutral
candidates и audit готовы. **Gate на fair model comparison ещё не пройден:**
нужен independent review oracle/alternative readings и выбранных expectations.
Аудит не разрешает новые платные запросы.

Следующий ход: независимо проверить разметку, начиная с C006–C013 и C016;
зафиксировать policy для unsupported/ambiguous cases и budget. Затем S1.2 smoke
с независимой подачей одного кандидата и одинаковыми definitions. Групповой
source-only Choice остаётся отдельным экспериментом, а не прямой заменой этого
verifier comparison.
