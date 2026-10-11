# Independent semantic review — Stage 1

**Рекомендация: сохранить Gate на fair model comparison закрытым до точечного уточнения annotation conventions.** Проверены все 16 источников и 32 records. Это fresh LLM reviewer, не human/expert ground truth и не оценка фактической или юридической истинности.

## Порядок и независимость

1. Сначала прочитан только `.artifacts/stage1-independent-review/source-only.json`. Независимый разбор всех 16 текстов сохранён в `blind.json` до чтения labels, candidates, definitions, audit code и документации.
2. Затем прочитаны шесть заданных JSON artifacts, `evaluation/audit_stage1.py` и `docs/STAGE1_REPRESENTABILITY_AUDIT_2026-10-09.md`. После сопоставления записан `review.json` с отдельным verdict для каждого case и record.

Frozen `blind.json` SHA-256:

```text
480bddd3eefe05cdce18665bf006cc352472a01f7c696c98108a26ffd65d720e
```

После начала comparison `blind.json` не изменялся. Network, inference APIs, credentials, production, augmentation plan, branches, commits и PRs не использовались. Изменены только три разрешённых review artifacts.

## Findings по severity

### Medium — IR-001: C014 добавляет тождество автомобиля

Источник: «Сегодня **на той же парковке** я не оплатил **новую стоянку**». Одинаковая парковка и разные вчерашний/сегодняшний эпизоды заданы явно. Автомобиль не назван; один и тот же автомобиль из текста не следует.

В `reviewer-only.json#/cases/13/claims` и baseline **R028** обеим claims назначены `subject=vehicle_1` и `aboutEntity=vehicle_1`. При обычной семантике entity IDs это лишняя связь. Рекомендую считать baseline `indeterminate` до устранения связи или явного определения, что этот ID — несемантический placeholder, чьё тождество не оценивается. Это проверка выбранного subject relation, а не требование извлечь все детали текста.

Mutation **R027** действительно добавляет ошибку: сегодня/new stay нельзя объединять со вчерашним эпизодом. Она наследует проблему baseline; поэтому «одно изменённое поле» здесь не доказывает «ровно одна суммарная semantic defect».

### Medium — IR-002: для R015 semantic defect зависит от композиции полей

C008: «Я не утверждал, что оплатил парковку». Baseline **R016** корректно отрицает speech act и не устанавливает факт оплаты.

Mutation **R015** меняет только `predicate: speechAct → payment`, сохраняя `stance=denied`, `mode=speech-act`, `scope=assertion-of-payment`. Если `mode/scope` задают внешний operator, такая запись всё ещё может означать отрицание assertion об оплате. Это согласуется с использованием `payment + obligation` для C009: оно обозначает обязанность, не завершённый платёж.

Ожидаемая `incompatible` оправдана, если `predicate` обязательно называет outermost claim kind. Эта convention в предоставленных artifacts не определена. Рекомендация: определить композицию/precedence полей либо заменить mutation на `speechAct stance: denied → asserted`, которая явно противоречит источнику. До этого incompatibility R015 не считаю доказанной.

### Medium, условно — IR-003: личная неоплата и отсутствие любой оплаты различаются

C002 «**Я** не оплатил», C013 «парковку машины друга не оплатил» и C014 «**я** не оплатил новую стоянку» отрицают действие рассказчика. Они допускают оплату другим лицом. C012 прямо показывает такой сценарий: друг оплатил, рассказчик — нет.

Диагностические claims C002/C013 сохраняют actor; fragment contract отдельного typed actor/scope не имеет. В C014 actor уже `null`. Это **не автоматическая ошибка selected-field audit**: actor может быть намеренно вне выбранного probe, а quote/valueText сохраняют его текстом. Числа становятся завышенным заявлением только при последующем прочтении `payment=denied` как полного vehicle-level факта «никто не оплатил».

Нужно определить, что именно отрицает payment stance: процитированное действие конкретного лица или существование оплаты парковочного эпизода. В первом варианте явно ограничить representability выбранными полями; во втором — учитывать actor/scope и пересчитать зависимые projections. Неполноту выбранных probes саму по себе дефектом не считаю.

### Low — IR-004: C016 неоднозначен также по выбранному placement

«ТС стояло **в зоне ПП**» прямо говорит о стоянии в зоне. Frozen definition `placement` означает «Автомобиль находился **на парковке**». Без значения ПП parking-specific placement тоже требует интерпретации сокращения. Поэтому ambiguous касается выбранной claim, а не только невыбранных paidRegime/cityParking.

**R032 indeterminate** обоснован. «Оплаты нет» отдельно поддерживает отрицательную payment claim от имени постановления; **R031** добавляет явную ошибку polarity. Не следует расширять это до отсутствия записи об оплате: такого уточнения источник не даёт.

### Low — IR-005: неоднозначность источника и probe не всегда совпадает

В C007 обычное «не мог не оплатить» сильно подразумевает состоявшуюся оплату, но явно выражает modal necessity. **R013** сохраняет `mode=necessity`, поэтому selected modal claim может быть совместима с обоими чтениями. `indeterminate` допустим как консервативная policy, но необходимо назвать её: проверяется поддержка выбранной claim или единственность полного прочтения источника. **R014** с выдуманным letter claimant ошибочен при обоих чтениях.

## Coverage

| Case | Status | Baseline | Mutation | Verdict |
| --- | --- | --- | --- | --- |
| C001 | agree | R001 | R002 | Affirmative payment; polarity flip wrong. |
| C002 | agree | R004 | R003 | Personal nonpayment; polarity flip wrong. |
| C003 | agree | R005 | R006 | Explicit nonrecall; assertion unsupported. |
| C004 | agree | R008 | R007 | Vehicle placement/city parking; payment unsupported. |
| C005 | agree | R009 | R010 | Narrator vs letter; shared episode is natural discourse resolution. |
| C006 | agree | R012 | R011 | Same contrast inside one sentence; claimant flip wrong. |
| C007 | ambiguous | R013 | R014 | Conservative indeterminate accepted; invented letter wrong. |
| C008 | ambiguous | R016 | R015 | Baseline correct; predicate mutation needs composition policy. |
| C009 | agree | R017 | R018 | Obligation is not actual payment. |
| C010 | agree | R020 | R019 | Conditional antecedent is not an actual payment fact. |
| C011 | agree | R021 | R022 | Hypothetical assumption is not actual payment. |
| C012 | agree | R024 | R023 | Friend payer; narrator excluded; actor substitution wrong. |
| C013 | agree | R025 | R026 | Two vehicle targets; wrong subject is one incorrect relation. |
| C014 | revise | R028 | R027 | Shared vehicle unsupported; merged episodes definitely wrong. |
| C015 | agree | R029 | R030 | Letter’s claim is not narrator’s independent endorsement. |
| C016 | ambiguous | R032 | R031 | Parking-specific placement unresolved; payment polarity clear. |

Per-record expectations: **30 agree, 1 revise (R028), 1 unresolved (R015)**. Это не accuracy score. Per-case statuses: 12 agree, 1 revise, 3 ambiguous. Все вердикты, exact paths, quotes и Unicode spans находятся в `review.json`; независимые исходные прочтения — в `blind.json`.

## Representability и integrity

Заявленные counts воспроизводятся по выбранным `requiredTypedFields` и case-level `alternativeReadings`: sentence **7 representable / 7 lossy / 2 ambiguous**, claim **9 / 5 / 2**. Арифметической ошибки не найдено. Это условные bookkeeping counts для заданной selection, не подтверждение полного сохранения claim semantics или качества automatic segmentation.

Все **46 candidate claim spans** совпадают с literal substrings. Все **16 mutations** меняют ровно объявленное поле; все 16 baselines совпадают со своим diagnostic oracle. Семантически 15 mutations добавляют понятную ошибку при принятых role conventions; R015 требует уточнения. R027/R031 наследуют baseline uncertainty. Structural consistency не разрешает semantic Gate.

Интенционально невыбранные детали — например receipt consequent в C010 и отдельные eventTime predicates в C014 — не объявляются ошибками extraction. Не делается выводов об истине документов, legal compliance, holdout performance или model accuracy.

## Gate и следующий шаг

Сохранить набор как **synthetic diagnostic development / candidate labels**. Перед fair model comparison интеграционному владельцу следует разрешить C014 entity identity и R015 field composition, зафиксировать scope payment denial и record-level ambiguity policy, затем версионировать затронутые annotations и выполнить targeted offline review. Новые платные запросы этот review не разрешает.
