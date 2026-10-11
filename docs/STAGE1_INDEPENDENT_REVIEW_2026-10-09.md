# Независимый LLM review Stage 1 — 2026-10-09

## Результат

После записи [идеи narrative augmentation](NARRATIVE_AUGMENTATION_EXPERIMENTS.md)
выполнен review отдельным LLM-агентом без истории переписки. Проверены все 16
источников и 32 candidate expectations. **30 expectations согласованы reviewer,
1 требует пересмотра, 1 оставлено спорным. Это не accuracy score.**

Статусы кейсов: 12 agree / 1 revise / 3 ambiguous. Это независимое модельное
прочтение, не human/expert ground truth. Labels остаются candidate; полный
critical-error-free rate не вычисляется. Corpus generation и provider inference
API в этом проходе не запускались.

## Протокол и evidence

1. Reviewer получил только ID и исходные тексты. До чтения авторских labels,
   definitions и audit он сохранил разбор всех 16 источников в `blind.json`.
2. Затем прочитал корпус, кандидатов, labels и текущий audit; сравнил каждый record.
3. Интеграционный владелец проверил сохранённый hash, source matches, цитаты,
   coverage и согласованность итоговых counts. Blind-разбор после freeze не менялся.

[Portable evidence bundle](../fixtures/parking-pilot/stage1-independent-review/README.md):
[blind analysis](../fixtures/parking-pilot/stage1-independent-review/blind.json),
[полные verdicts](../fixtures/parking-pilot/stage1-independent-review/review.json),
[исходный отчёт reviewer](../fixtures/parking-pilot/stage1-independent-review/report.md),
[manifest и gate decision](../fixtures/parking-pilot/stage1-independent-review/manifest.json).

Blind SHA-256: `480bddd3eefe05cdce18665bf006cc352472a01f7c696c98108a26ffd65d720e`.
Input hashes привязывают review к историческому v1 corpus и audit. Hashes не
доказывают отсутствие bias или identity reviewer. Точная model version не
зафиксирована интерфейсом делегирования; результат не является benchmark модели.

## Findings и интеграционное решение

| ID | Что обнаружено | Решение |
| --- | --- | --- |
| IR-001 | C014 / baseline R028: одна и та же парковка не устанавливает один и тот же автомобиль; обе claims используют vehicle_1 | Принять замечание о недоопределённой identity convention. До явной семантики placeholders или исправленной entity binding не считать ожидание compatible окончательным |
| IR-002 | C008 / mutation R015: payment сохраняет mode=speech-act и scope=assertion-of-payment; incompatibility зависит от композиции полей | Принять. Зафиксировать operator/field semantics либо заменить mutation на denied → asserted для самого speech act |
| IR-003 | «Я не оплатил» не означает «никто не оплатил»; actor может потеряться при проекции | Принять как policy issue. Разделить отрицание действия лица и отрицание оплаты эпизода перед mapping/scoring |
| IR-004 | C016: неизвестное ПП влияет также на выбранный placement, поскольку definition требует парковку | Принять уточнение. Ambiguity не ограничивается невыбранными paidRegime/cityParking |
| IR-005 | Неоднозначность всего источника и поддержка выбранного modal claim — разные критерии | Принять как policy issue. Назвать record-level policy; не требовать единственного полного прочтения по умолчанию |

Reviewer не обнаружил арифметической ошибки в [исходном audit](STAGE1_REPRESENTABILITY_AUDIT_2026-10-09.md).
Counts sentence 7/7/2 и claim 9/5/2 воспроизводят выбранные requiredTypedFields и
alternativeReadings. Это условные structural bookkeeping counts, которые review
не повышает до доказательства полного сохранения semantics.

16 mutations действительно меняют по одному объявленному полю. Из этого не
следует ровно одна суммарная semantic defect: R027 наследует спорную identity
baseline C014, R031 — uncertainty C016. Для R015 сам дефект зависит от convention.
Оригинальные v1 sources/labels/candidates/audit сохранены без переписывания истории.

## Проверки

- 69/69 локальных pytest checks: review integrity, Stage 1 audit и прежние
  provider/capture/Mellea fixtures.
- Stage 1 stdlib suite: 11/11 unittest checks без внешних dependencies.
- Проверены hashes сохранённых artifacts и inputs, 16/32 coverage и итоговые counts.
- 25 blind evidence spans и 46 candidate claim spans точно совпали с источниками;
  evidence spans замечаний reviewer также проверены.
- CI Stage 1 job расширен проверками review bundle; сетевой inference не нужен.
- Проверки integrity не являются самостоятельным semantic review и не доказывают
  истинность рассказов или юридическую правильность.

## Gate и следующий шаг

**Решение: hold для fair model comparison.** Это исследовательское решение,
зафиксированное в manifest, а не программная блокировка API runner.

Следующий ход — новая revision разметки и conventions:

1. Определить entity identity/unresolved references для C014, не добавляя сведения
   об автомобиле в неизменный исходник.
2. Уточнить composition predicate/mode/scope; заменить недоказанную mutation R015
   на однозначный контраст, сохранив старый вариант как исторический спорный пример.
3. Определить actor-scoped payment denial и поддержку selected claim относительно
   общей неоднозначности. Затем пересчитать затронутые projections/labels.
4. Выполнить targeted offline review новой revision. После этого фиксировать
   matrix, инструкции, policy и billable budget для Jev/Luna comparisons.

[Предложенные контрпримеры владельца интеграции](../fixtures/parking-pilot/stage1-independent-review/adjudication-counterexamples.json)
помогают сформулировать эти conventions; это не новые независимые reviewed labels.
Платных сравнений и augmentation generation этот review не разрешает.
