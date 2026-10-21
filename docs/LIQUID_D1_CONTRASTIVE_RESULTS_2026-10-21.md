# D1 Ultra: результаты шести контрастов

Дата: 2026-10-21. Ledger: [#70](https://github.com/SoundBlaster/NormLab/issues/70).
[Protocol](LIQUID_D1_CONTRASTIVE_PLAN_2026-10-21.md) и 12 tasks подготовлены
в `ee0cee9`; разрешение и actual driver зафиксированы **до inference** в
`ab7be2d`. Execution plan, исходные tasks, references и driver после запуска
не менялись; к Markdown-протоколу добавлена ссылка на результат.

## Итог

**12/12 HTTP 200, 10/12 совпадений с candidate references, 4/6 полностью
пройденных контрастных пар.** Ни одного retry, technical failure или unknown
outcome. Серия заняла **10.496 s**.

| Пара | Проверяемый контраст                               | Ожидалось a / b            | Получено a / b            | Обе labels верны |
| ---- | -------------------------------------------------- | -------------------------- | ------------------------- | ---------------- |
| P01  | Обязанность → ошибочно фактическая оплата          | compatible / incompatible  | compatible / incompatible | Да               |
| P02  | Гипотеза → ошибочно фактическая оплата             | compatible / incompatible  | compatible / incompatible | Да               |
| P03  | Плательщик — друг → ошибочно рассказчик            | compatible / incompatible  | compatible / incompatible | Да               |
| P04  | Автор утверждения — письмо → ошибочно рассказчик   | compatible / incompatible  | compatible / compatible   | Нет              |
| P05  | Явный unknown → ошибочно положительный факт оплаты | compatible / incompatible  | compatible / incompatible | Да               |
| P06  | Raw standing → parking-specific placement при «ПП» | compatible / indeterminate | compatible / compatible   | Нет              |

Во всех парах источник и цитаты одинаковы; меняется одно typed field одного
claim. Сохранение supported candidate недостаточно для прохождения пары:
модель должна также отличить ошибочный или неразрешимый вариант.

### Что именно не сработало

**P04b — источник утверждения.** Текст: «В письме сообщили, что моя парковка
не оплачена». Correct candidate сохраняет `claimant=letter_1`; mutant меняет
только claimant на `narrator`. Ultra принял оба. Таким образом, проверка не
обнаружила переноса утверждения из письма на рассказчика. Это касается авторства
selected claim; никакой факт оплаты или неоплаты здесь не устанавливается.

**P06b — неоднозначный предикат.** «ТС стояло в зоне ПП; оплаты нет» корректно
поддерживает raw `standing` от имени постановления. Parking-specific `placement`
требует расшифровки «ПП», ранее согласованной как вопрос для пользователя.
Ultra снова принял эту версию без review. References не исправлялись под ответ;
raw R032 остаётся compatible, derived T04 остаётся indeterminate.

Гипотеза «на выбранных контрастах достаточно текущей постановки» отклонена
по заранее записанному criterion: две пары не прошли. При этом в данном запуске
модель различила obligation, hypothetical, payer и explicit unknown. Это
локализация ошибок стратегии, не основание для общего рейтинга моделей.

## Все 12 ответов

| Job  | Expected      | Actual       | Native confidence | P(selected) | Latency, s |
| ---- | ------------- | ------------ | ----------------- | ----------- | ---------- |
| P01a | compatible    | compatible   | 0.7927            | 0.8618      | 0.974      |
| P01b | incompatible  | incompatible | 0.8284            | 0.8856      | 0.793      |
| P02a | compatible    | compatible   | 0.7896            | 0.8597      | 0.837      |
| P02b | incompatible  | incompatible | 0.7430            | 0.8287      | 0.903      |
| P03a | compatible    | compatible   | 0.5092            | 0.6728      | 0.939      |
| P03b | incompatible  | incompatible | 0.2365            | 0.4910      | 0.905      |
| P04a | compatible    | compatible   | 0.6271            | 0.7514      | 0.854      |
| P04b | incompatible  | compatible   | 0.2235            | 0.4823      | 0.859      |
| P05a | compatible    | compatible   | 0.7536            | 0.8358      | 0.855      |
| P05b | incompatible  | incompatible | 0.4390            | 0.6260      | 0.820      |
| P06a | compatible    | compatible   | 0.6835            | 0.7890      | 0.897      |
| P06b | indeterminate | compatible   | 0.5248            | 0.6832      | 0.842      |

Выполненный порядок: P01a/b, P02b/a, P03a/b, P04b/a, P05a/b, P06b/a.
Confidence и P(selected) — разные provider fields, не проверенная вероятность
правильности. В Choice из трёх labels максимум может быть меньше 0.5: P03b
правильно отклонён при P(selected)=0.4910. P04b ошибочно принят при 0.4823.
P06b ошибочен при confidence=0.5248, выше правильного P03a=0.5092: один порог
не отделяет ошибки от всех правильных ответов даже в этих наблюдениях.
Порог и calibration не подбирались.

## Counts и ресурсы

- Planned 12, attempted 12, completed 12; 0 retries, failures, unknown и not-executed.
- Совпадения: 10/12; полностью верные пары: 4/6.
- False acceptance: **1/5** incompatible candidates — P04b.
- False rejection: **0/6** compatible candidates; все шесть приняты.
- Unnecessary review: **0/11** определённых references.
- Overdetermination: **1/1** indeterminate candidate — P06b, accept вместо review.
- Returned labels: 8 compatible, 4 incompatible, 0 indeterminate.
- Requested и returned model: `d1-ultra`. Direct HTTP, Python 3.14.8.
- Usage: **15 014 input / 0 output tokens**, missing usage 0.
- Сумма API `usage.cost`: **0.000630588**, валюта поля независимо не проверена.
- Estimate при assumed rate $0.042/M input: **$0.000630588**. Это расчёт по
  тарифному предположению из предыдущего smoke, не проверка актуального тарифа
  или фактического списания. `costUSD=null`, `billingVerified=false`.
- Разрешение исчерпано: **12/12**; дополнительных provider calls не было.

## Ограничения и следующий ход

Шесть прежних authored development texts, 12 связанных кандидатов, candidate
references без нового independent human review. Это не holdout, не оценка доли
полностью правильных разборов дела и не достижение целевых 80% case quality.
P05a/P06b повторяют старые T03/T04; их labels согласуются с предыдущим запуском,
но старые и новые ответы не объединяются в увеличенную выборку. Jev/Luna в этой
серии не вызывались. Production/default route и UI не менялись.

Следующая выбранная тактика для исследования — **узкая проверка происхождения
спорного утверждения до общей оценки**: отдельно спросить, кому текст приписывает
«парковка не оплачена», и сравнить это с candidate claimant. Это гипотеза
decomposition, не уже доказанный repair. Для неоднозначного «ПП» сохраняется
ранее согласованное ручное уточнение значения, без автоматического дописывания
фактов. Новый prompt, threshold, runtime gate или платный прогон пока не добавлены.

## Evidence и offline verification

- [Frozen plan](../fixtures/providers/liquid-contrastive-controls-v1/plan.json),
  [references](../fixtures/providers/liquid-contrastive-controls-v1/reviewer-only.json),
  [historical preparation](../fixtures/providers/liquid-contrastive-controls-v1/preparation.json).
- [Driver](evidence/liquid-contrastive-run-2026-10-21/driver.py) и
  [capture](evidence/liquid-contrastive-run-2026-10-21/report.json): все exact
  request objects, full response distributions, labels, outcomes, timing и usage.
- [Analysis](evidence/liquid-contrastive-run-2026-10-21/analysis.json): все rows,
  pair contrasts, denominators, ошибки и resource counts.
- [Verification](evidence/liquid-contrastive-run-2026-10-21/verification.json):
  frozen commit/plan/driver/helper/task/reference hashes; exact request equality
  и request digests; schema, finite normalized distributions, top labels,
  confidence/usage, deadlines, пересчёт grades и отсутствие credentials.
  Все проверки прошли без HTTP-запросов.

Offline checks подтверждают согласованность сохранённого evidence, не provider
authenticity, semantic gold, billing или SDK/bridge compatibility. Новых app
tests, installs, builds, deployments или merge не выполнялось. CI/review —
отдельные проверки текущего PR head.

Отдельно пользователь запросил [тот же набор для Jev через CoreInfra](JEV_ULTRA_CONTRASTIVE_COMPARISON_2026-10-21.md).
Этот arm остановился на первой сетевой попытке: 0 labels, 11 not-executed.
Результаты Ultra и его capture остались неизменными; сравнение качества с Jev
пока не измерено.
