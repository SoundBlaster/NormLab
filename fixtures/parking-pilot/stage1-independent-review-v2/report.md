# Stage 1 v2 — targeted regression review

**Все 32 expectations согласуются с исходными текстами при явных v2 conventions: 32 agree, 0 revise, 0 unresolved.** Проверены 16 cases / 13 families. Это повторный targeted review тем же LLM reviewer после знакомства с v1; свежей blindness, human/expert ground truth или model-quality validation нет.

## Исправления v1

- **IR-001 / C014:** неназванные автомобили теперь `null`; null не задаёт identity, distinctness или explicit unknown. Вчерашний и сегодняшний/new stay остаются разными episodes. R028 совместим; R027 добавляет только ошибочное объединение эпизодов.
- **IR-002 / C008:** R015 теперь меняет `speechAct stance: denied → asserted`. Внешний speech act определён явно. Сохранённые wrappers больше не дают эквивалентное прочтение; R016 корректно оставляет оплату открытой.
- **IR-003:** `actor-payment` отделён от `episode-payment`, named actors сохранены. «Я не оплатил» не превращается в «никто не оплатил». Faithful projection учитывает actor/scope; намеренно невыбранные clauses не объявляются omissions.
- **IR-004 / C016:** `standing` означает стояние по raw location «в зоне ПП», без вывода о парковке. Документ отдельно сообщает «оплаты нет». Scoped diagnostic payment не отождествляется с parking-specific production predicate. R032 совместим независимо от расшифровки ПП; R031 ошибочно меняет payment polarity.
- **IR-005 / C007:** selected necessity поддерживается обоими отмеченными чтениями; `compatible` не утверждает actual completed payment. Source ambiguity сохранена отдельно.

## Заменённые mutations и wrappers

| Record | Изменение | Семантическая проверка |
| --- | --- | --- |
| R007 | placement asserted → denied | Противоречит «Автомобиль стоял на городской парковке». CityParking остаётся, но не исправляет denial placement. |
| R015 | speechAct denied → asserted | Противоречит «Я не утверждал». Отрицается/утверждается внешний speech act, не факт оплаты. |
| R019 | conditional stance asserted → denied | Источник содержит positive antecedent «Если бы я оплатил парковку». Conditional/antecedent wrappers сохраняют nonactuality, но не восстанавливают исходное positive содержание. |

Все остальные mutations также проверены по source: неверная polarity/epistemic stance, claimant, payer, vehicle target, episode либо modality. В R018 и R022 после смены mode не остаётся альтернативного obligation/hypothetical wrapper. В R026 сохранённый `aboutEntity=vehicle_2` показывает неверный subject, а не делает его эквивалентным baseline.

## Representability

В просмотренной версии `evaluation/audit_stage1_v2.py` не найдено omissions для текущих selected claims: учитываются actor/scope/mode/aboutEntity, nullable subject и diagnostic predicates вне production catalog. Ожидаемые counts для обоих layouts: **1 representable / 15 lossy / 0 ambiguous**; полностью representable остаётся C004. Source ambiguity C007/C016 при этом не удаляется.

Audit code находился в работе у интеграционного агента: reviewer его не hash/pin, не импортировал, не запускал и не тестировал. Structural integrity observations ограничены совпадением 46 literal candidate spans и одной объявленной field mutation на каждый contrast pair. Они не доказывают semantic correctness сами по себе.

## Gate и ограничения

Прежние targeted annotation objections разрешены; новых semantic blockers в этом bounded pass не найдено. Labels можно сохранить как **LLM-reviewed synthetic diagnostic-development annotations**, с candidate status. Expert/quality Gate, model accuracy, fair-comparison outcomes, live/paid calls этим review не одобрены.

Интеграционному владельцу следует зафиксировать финальные audit bytes и опубликовать regression evidence, сохранив эти ограничения. Полные per-case/per-record verdicts, quotes/Unicode offsets и SHA-256 четырёх входных JSON находятся в `review.json`.

## SHA-256 inputs

- `fixtures/parking-pilot/stage1-audit-v2/sources.json`: `030f957560600a9694ba47347f527423a095f036580b4d383ea7c56f0dec7b5c`
- `fixtures/parking-pilot/stage1-audit-v2/candidates.json`: `0c4201478b51a8f1b2cde7d1eabb699e4d8b4def482fc9f70a37746a53ce76dd`
- `fixtures/parking-pilot/stage1-audit-v2/reviewer-only.json`: `766c315a77e0cb24533609a9272b770cb8d0c516a33ad112839889998e370f91`
- `fixtures/parking-pilot/stage1-audit-v2/conventions.json`: `8673b5c4d2e1257b470e256f47a183963913975754755ba0a8e5ea284c08f9f8`
