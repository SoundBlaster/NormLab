# Jev и D1 Ultra: те же шесть контрастов

Дата: 2026-10-21. Ledger: [#70](https://github.com/SoundBlaster/NormLab/issues/70).
Пользователь прямо запросил Jev для более полного сравнения. Новый bounded arm
фиксируется до inference; результаты пока pending.

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
