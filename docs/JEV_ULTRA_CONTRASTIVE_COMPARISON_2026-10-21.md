# Jev и D1 Ultra: те же шесть контрастов

Дата: 2026-10-21. Ledger: [#70](https://github.com/SoundBlaster/NormLab/issues/70).
Пользователь прямо запросил Jev для более полного сравнения. Новый bounded arm
зафиксирован до inference в `c60b27c`. Серия остановлена после первой попытки:
unknown network outcome, 0 ответов модели, 11 not-executed. Полное сравнение
семантического качества пока невозможно.

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

## Наблюдённый результат

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
без текста, потенциально содержащего credentials. Результаты пока pending.
