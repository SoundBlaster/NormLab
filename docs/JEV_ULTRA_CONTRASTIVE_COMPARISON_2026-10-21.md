# Jev и D1 Ultra: те же шесть контрастов

Дата: 2026-10-21. Ledger: [#70](https://github.com/SoundBlaster/NormLab/issues/70).
Пользователь прямо запросил Jev для более полного сравнения. Первый arm
`c60b27c` остановился без ответа. Затем retry-сегмент `1c5bef2` и отдельно
разрешённый suffix `2c62302` обработали все 12 jobs: **16 attempts, 4 retries,
10 labels и 2 unknown jobs**. На одинаковых десяти inputs Jev — **8/10**,
Ultra — **9/10** candidate agreement. На четырёх полностью полученных парах —
2/4 и 3/4 соответственно. Это частичная semantic coverage, не общая accuracy.
Ниже сохранены протокол, промежуточные результаты и amendments.

## Что сравниваем

Используется тот же [набор из 12 tasks](LIQUID_D1_CONTRASTIVE_PLAN_2026-10-21.md),
шесть source texts, исходная overall instruction, conventions, definitions,
candidate references и порядок a/b, b/a. До запуска сверены все `state/questions`
с реально отправленными Ultra objects; в новых body меняется только `model`.

| Arm                  | Requested model | Endpoint                                             | Статус перед запуском                                          |
| -------------------- | --------------- | ---------------------------------------------------- | -------------------------------------------------------------- |
| Liquid               | d1-ultra        | `https://api.liquid.ai/decisions/v1/systemone`       | [12/12 выполнены](LIQUID_D1_CONTRASTIVE_RESULTS_2026-10-21.md) |
| CoreInfra / TypeSafe | jev-1.13.0      | `https://hub.coreinfra.ai/typesafe/api/v1/systemone` | 12 planned, отдельный новый arm                                |

Оба arm идут direct HTTP через одинаковый standard-library transport, по одному
Choice `overall` на независимый запрос. Это не проверка SDK/bridge integration.
Меняются backend/model/endpoint и время запуска: последовательные runs не
изолируют causal model effect, не равны по compute и не дают общего рейтинга.
Новых Ultra/Luna запросов не требуется.

## Freeze, авторизация и stopping rule

[Plan](../fixtures/providers/jev-contrastive-controls-v1/plan.json) связывает
task/reference/config/driver/helper hashes и неизменный Ultra capture/analysis.
Ожидания остаются вне model input; новые claims/labels не сочиняются.

- Прямой запрос пользователя разрешает этот Jev arm на прежних 12 заданиях.
- Максимум 12 attempts, 0 retries/repair/fallback; 30 s/request, 360 s/series,
  1 MiB/response. Первый transport/HTTP/protocol/unknown outcome, model/task
  drift или cap останавливает серию. Semantic mismatch не останавливает её.
- `COREINFRA_API_KEY` берётся только из окружения, не печатается и не попадает
  в files/argv/capture/ledger. Redirects запрещены. Driver отказывается запускаться
  с optimized Python, грязным checkout или существующим capture.
- Ранее указанный пользователем внешний CoreInfra ceiling $4 остаётся
  непроверенным. API usage/cost учитываются как provider evidence; отсутствующая
  цена не заменяется нулём. Liquid estimate к Jev не применяется.
- Freeze actual driver и inputs сохраняется в Git до первой отправки.
  Новый arm не возобновляет отдельно отложенное исследование причин Jev #145.

## Критерии и отчёт

Для обоих arm показать все 12 expected/actual labels и все шесть пар с counts,
false acceptance из пяти incompatible, false rejection из шести compatible,
unnecessary review из 11 определённых и overdetermination из одного indeterminate.
При stop сохранить attempted и not-executed jobs; пропущенное не считать ни
верным, ни ошибочным semantic ответом. Captures сохраняют полный JSON response,
confidence отдельно от P(selected), returned model, request ID, usage и latency.

Главный результат — какие конкретные контрасты различают arm и где совпадают
ошибки; hypothesis о качестве на всех выбранных контрастах отклоняется при
хотя бы одной неправильной label. Operational incomplete не заменяет semantic
отрицательный вывод. После dispatch метрики пересчитываются offline из captures.

Это прежние authored development sources, candidate references без нового
independent human gold, не holdout или доля безошибочных разборов дела. Старые
Jev/Ultra серии не добавляются к denominator. Порог confidence, production route,
UI и автоматическая маршрутизация по этому сравнению не меняются.

## Наблюдённый результат первой серии без retries

| Показатель            | Jev / CoreInfra | Ultra / Liquid, ранее |
| --------------------- | --------------- | --------------------- |
| Planned               | 12              | 12                    |
| Attempted             | 1               | 12                    |
| Completed             | 0               | 12                    |
| Unknown outcome       | 1               | 0                     |
| Not-executed          | 11              | 0                     |
| Retries               | 0               | 0                     |
| Candidate agreement   | Не измерено     | 10/12                 |
| Полностью верные пары | Не измерено     | 4/6                   |

Первый P01a («Я должен был оплатить парковку», correct obligation candidate)
завершился за 6.554 s со статусом `unknown`; HTTP status, response и usage
не получены. Серия целиком — 6.555 s. В driver эта категория объединяет
network/TLS/timeout errors без сохранения конкретного exception type/message,
поэтому точная причина этой попытки неизвестна. Остальные 11 не отправлены.
Unknown не означает неверную label, review, отказ Jev или нулевую accuracy.
Стоимость и usage неизвестны, возможность обработки запроса на стороне сервиса
не исключена. Исходный capture не перезапускался и не перезаписывался.

После остановки выполнен **один credential-free TLS handshake**, без ключа,
HTTP и inference: `hub.coreinfra.ai` доступен по TLS 1.3, handshake 1.406 s.
Это проверка текущей transport reachability, не доказательство причины прошлого
сбоя, доступности authenticated API или качества модели.

- [Capture](evidence/jev-contrastive-run-2026-10-21/report.json).
- [Analysis](evidence/jev-contrastive-run-2026-10-21/analysis.json).
- [Offline verification](evidence/jev-contrastive-run-2026-10-21/verification.json).
- [TLS probe](evidence/jev-contrastive-run-2026-10-21/transport-probe.json).

Проверены frozen Git plan/driver/helper/tasks/references/baseline hashes,
точное равенство отправленного state/questions с Ultra, request digest,
один unknown и неизменный not-executed suffix, null usage/grades и отсутствие
credentials. Все offline checks прошли, без HTTP. Новых Ultra/Luna запросов,
app tests, installs, builds, deploy или merge не было.

## Следующий запуск — предложение, не исполнение

Поскольку frozen rule запрещает продолжение после первого unknown, оставшиеся
11 attempts не используются как неявное разрешение на restart. Предложение:
те же 12 tasks, максимум **16 новых попыток**, из них до четырёх transport retries,
не больше одного повтора на job; 30 s/attempt и 360 s/series. Повтор только после
network/TLS/timeout unknown, никогда после полученной label; HTTP/protocol/model
ошибки останавливают серию. Сохранить все attempts и ограниченный backoff.
Повтор unknown может повторно тарифицироваться. Нужны отдельное разрешение и
новый pre-inference freeze; driver должен сохранить безопасный exception type
без credentials. Эта серия и её unknown останутся отдельным evidence.

## Повторная серия разрешена

После описанного предложения и отдельной проверки хаба пользователь ответил:
«Повтори». Новая серия ограничена теми же 12 jobs, максимум 16 **новых** attempts,
до четырёх network-unknown retries суммарно и не больше одного на job. Backoff
1 s, 30 s/attempt, 360 s/series. После валидной label повтор не делается, даже
если она не совпадает с reference. HTTP/protocol/model errors или unrecovered
unknown останавливают серию. Возможность повторного billing unknown была
раскрыта при предложении. Первая остановленная попытка не стирается и не
вычитается из фактического расхода; она вне нового лимита и semantic score.

[Новый plan](../fixtures/providers/jev-contrastive-retry-v1/plan.json) фиксирует
тот же task/reference/order, Ultra baseline, прежний stopped capture и actual
[driver](evidence/jev-contrastive-retry-2026-10-21/driver.py). До inference всё
сохраняется в Git. Capture пишет отдельный attempt log и итог каждого job;
учитываются все usage/unknown outcomes, отдельно ответы с первой попытки
и после retry. Для ошибки сохраняется безопасный exception type и reason type,
без текста, потенциально содержащего credentials.

### Первый retry-сегмент

Frozen commit `1c5bef2`: 8 attempts, 2 retries, 29.345 s. Получены 5 labels,
4/5 совпали с candidate references; Ultra на тех же пяти tasks — 5/5. Четыре
ответа с первой попытки верны, один восстановленный ответ ошибочен: P02a
«Допустим, парковка была оплачена», faithful hypothetical candidate отвергнут
как incompatible. Это не показывает, что retry вызвал semantic ошибку:
ответа первой попытки нет. Полностью получены две пары: obligation верна,
hypothetical неверна из-за ложного отклонения supported candidate.

P02a первый раз получил URLError с reason SSLEOFError, затем ответ. P03b
получил тот же TLS EOF дважды; сработало правило остановки этого сегмента.
Итого 3 unknown attempt outcomes, один финальный unknown job и 6 not-executed.
Known usage пяти ответов — 9 580 input/224 output; usage трёх unknown неизвестен,
стоимость null. Ключ и body в диагностические exception fields не попали.

Сохранены [capture](evidence/jev-contrastive-retry-2026-10-21/report.json),
[analysis](evidence/jev-contrastive-retry-2026-10-21/analysis.json) и
[offline verification](evidence/jev-contrastive-retry-2026-10-21/verification.json).
Frozen inputs/driver/baselines, все attempt requests, retry caps, schema и
grades проверены offline без HTTP. Результат остаётся частичным.

### Продолжение в оставшемся лимите

Человеческое разрешение охватывает 12 jobs/16 новых attempts и 4 network retries,
максимум один на job; лимит не исчерпан. После сохранения первого сегмента
готовится **отдельный continuation protocol до новых отправок**, без изменения
его capture: только ещё не отправленные P04b/a, P05a/b, P06b/a, максимум
8 attempts и 2 retries. Сумма двух сегментов не превысит исходные 16/4.
Никаких новых попыток уже завершённых jobs или исчерпавшего retry P03b.

В этой версии после unrecovered network unknown job сохраняется unknown и
выполняются остальные jobs; HTTP/protocol/model failures всё ещё останавливают
сегмент. Это **post-observation design amendment**, а не выполнение прежнего
stop-on-unrecovered протокола без отклонений. Его влияние на coverage раскрывается
в итоговом сравнении. Время двух сегментов, backoff и все попытки вместе
ограничены исходными 360 s; новые sources/prompts/reference labels не вводятся.

**Статус continuation: не исполнено.** Пока сохранялся retry-сегмент и
готовился amendment, первоначальное 360-секундное execution window истекло.
Никаких дополнительных запросов после восьмой попытки не отправлено.
Оставшиеся восемь attempts не используются для неявного сброса deadline.
Для шести неотправленных jobs нужен новый явно разрешённый execution window;
16 aggregate attempts и четыре retries не должны увеличиваться. Draft amendment
выше — предложение, не утверждение об исполнении или новом разрешении.

### Текущий сопоставимый semantic результат

| Job                   | Expected     | Jev          | Ultra        |
| --------------------- | ------------ | ------------ | ------------ |
| P01a, obligation      | compatible   | compatible   | compatible   |
| P01b, ошибочно actual | incompatible | incompatible | incompatible |
| P02a, hypothetical    | compatible   | incompatible | compatible   |
| P02b, ошибочно actual | incompatible | incompatible | incompatible |
| P03a, платил друг     | compatible   | compatible   | compatible   |

Только на этих пяти полученных inputs Jev — **4/5**, Ultra — **5/5**. Это
условный ранний prefix при нестабильном транспорте, а не полное или независимое
сравнение точности моделей. P03b не имеет label; P04/P05/P06 не оценены Jev.
Из полностью полученных пар Jev прошёл 1/2, Ultra 2/2. Ранее Ultra на всех
шести парах дал 4/6, на 12 candidates — 10/12; эти denominators не смешиваются.

Подтверждённая новая semantic проблема Jev — ложное отклонение корректной
hypothetical-разметки. Отдельная operational проблема — три SSLEOFError attempt
outcomes в новой серии. Все они остаются неизвестными по usage/billing; вместе
с первой stopped-серией сохранены четыре unknown attempts, ни один не принят
за semantic ошибку. Смена provider/default или confidence routing не выполнялась.

## Итог после отдельно разрешённого suffix

Пользователь явно разрешил новое окно 360 s только для шести неотправленных
jobs, максимум 8 attempts/2 retries, aggregate 16/4 без увеличения, без повторов
завершённых jobs и P03b. До отправки сохранены [plan](../fixtures/providers/jev-contrastive-suffix-v1/plan.json)
и [driver](evidence/jev-contrastive-suffix-2026-10-21/driver.py) в `2c62302`.
В suffix после unrecovered network unknown разрешено выполнять следующий job;
это согласованный post-observation amendment, не исходный stopping rule.

Suffix: 8 attempts, 2 retries, 30.526 s, 5 completed/1 unknown. После retry
восстановились P04a и P05b; P06b получил SSLEOFError при уже исчерпанном retry
cap и сохранился unknown, после него P06a был выполнен. Последующие semantic
ответы не отбирались по правильности: валидная label никогда не повторялась.

| Контраст                                | Expected a / b             | Jev a / b                      | Ultra a / b               | Сравнение пары                       |
| --------------------------------------- | -------------------------- | ------------------------------ | ------------------------- | ------------------------------------ |
| Обязанность / actual                    | compatible / incompatible  | compatible / incompatible      | compatible / incompatible | Оба верны                            |
| Гипотеза / actual                       | compatible / incompatible  | incompatible / incompatible    | compatible / incompatible | Jev ложное отклонение                |
| Друг-плательщик / рассказчик            | compatible / incompatible  | compatible / unknown transport | compatible / incompatible | Jev неполно                          |
| Автор письма / рассказчик               | compatible / incompatible  | compatible / compatible        | compatible / compatible   | Оба приняли подмену                  |
| Explicit unknown / asserted             | compatible / incompatible  | compatible / incompatible      | compatible / incompatible | Оба верны                            |
| Raw standing / parking placement при ПП | compatible / indeterminate | compatible / unknown transport | compatible / compatible   | Jev неполно; Ultra overdetermination |

`unknown transport` означает отсутствие ответа, а не модельную label
`indeterminate`. Jev не дал ответа на P03b и P06b. Для одинакового denominator
исключаются **обеими** сторонами только эти два inputs: Jev 8/10, Ultra 9/10.
Полные Ultra counts 10/12 и 4/6 сохранены отдельно. Сравнимы четыре полные пары:
Jev 2/4, Ultra 3/4; две неполные пары Jev не получают ошибочный semantic score.

### Все полученные Jev labels и evidence fields

| Job  | Expected      | Jev          | Native confidence | P(selected) | Job attempts |
| ---- | ------------- | ------------ | ----------------- | ----------- | ------------ |
| P01a | compatible    | compatible   | 0.49              | 0.66        | 1            |
| P01b | incompatible  | incompatible | 0.97              | 0.98        | 1            |
| P02a | compatible    | incompatible | 0.28              | 0.52        | 2            |
| P02b | incompatible  | incompatible | 0.95              | 0.97        | 1            |
| P03a | compatible    | compatible   | 0.86              | 0.91        | 1            |
| P03b | incompatible  | Нет ответа   | null              | null        | 2            |
| P04a | compatible    | compatible   | 0.64              | 0.76        | 2            |
| P04b | incompatible  | compatible   | 0.46              | 0.64        | 1            |
| P05a | compatible    | compatible   | 0.69              | 0.79        | 1            |
| P05b | incompatible  | incompatible | 0.66              | 0.77        | 2            |
| P06a | compatible    | compatible   | 0.69              | 0.79        | 1            |
| P06b | indeterminate | Нет ответа   | null              | null        | 1            |

Среди completed references: false acceptance 1/4 incompatible (P04b),
false rejection 1/6 compatible (P02a). На indeterminate reference ответа нет:
overdetermination Jev здесь не измерена. Семь ответов с первой попытки — 6/7
совпадений; три recovered — 2/3. Recovery не означает semantic correctness.

### Transport, ресурсы и границы

- В рамках retry + suffix: **16/16 attempts, 4/4 retries**, все 12 jobs attempted;
  10 completed, 2 final unknown, 0 not-executed.
- 6 unknown attempt outcomes с SSLEOFError, usage неизвестен. Из четырёх retries
  три восстановили ответ; повтор P03b тоже завершился unknown.
- Known usage 10 ответов: **19 164 input / 442 output tokens**. Это нижняя
  граница полного usage с учётом шести unknown attempts. Cost/billing null,
  к Jev не применяется Liquid price estimate.
- Первая отдельная no-retry серия — ещё один unknown attempt вне нового cap.
  Он сохраняется отдельно: всего в истории этих Jev arms 17 attempts и 7
  unknown attempt usages. Semantic score из него не пополняется.
- Execution durations двух retry windows: 29.345 s и 30.526 s. Это не общий
  wall-clock всех подготовки/review/разрешений и не чистая latency модели.
- Старые captures/references не менялись. Новых Ultra/Luna calls, confidence
  thresholds, provider/default/UI changes, deployments или merge не было.

Последовательные provider runs, retries, отсутствие двух ответов и amendment
мешают трактовать разницу как model ranking или оценку общей точности.
Практическая находка — общая ошибка attribution плюс отдельная ошибка Jev на
поддержанной гипотезе; TLS-отказы учитываются в availability, не в semantics.
Следующий research-кандидат остаётся узкой проверкой автора утверждения перед
overall evaluation. Для дальнейшего inference текущий cap полностью исчерпан.

### Итоговое evidence

- [Suffix capture](evidence/jev-contrastive-suffix-2026-10-21/report.json).
- [Combined analysis](evidence/jev-contrastive-suffix-2026-10-21/analysis.json):
  12 rows, все шесть пар, matched denominators, attempt/retry/resource counts.
- [Suffix/combined offline verification](evidence/jev-contrastive-suffix-2026-10-21/verification.json).

Проверены pre-inference commit/plan/driver/helper/task/reference/baseline и prior
capture hashes, exact requests versus Ultra кроме model, JSON schemas,
distributions/grades, attempt order, per-job/global caps, отсутствие повторов
после label, first/recovered counts и unknown usage. Все checks offline,
0 HTTP. Это не independent human gold, billing или SDK integration check.
