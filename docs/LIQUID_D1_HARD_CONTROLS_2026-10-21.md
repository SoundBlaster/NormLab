# D1 Ultra на исторических проблемных контролях

Дата: 2026-10-21. Ledger: [#70](https://github.com/SoundBlaster/NormLab/issues/70).
Protocol фиксируется до inference. Результаты пока pending.

## Задача и неизменные inputs

Проверить, различает ли D1 Ultra ошибочную typed proposition и дословную цитату,
сохраняя правильные отрицания/unknown и необходимость уточнения неоднозначности.
Это verifier task, не извлечение полного дела и не юридический вывод.

Используются существующие [A/B tasks](../fixtures/providers/jev-quote-authority-v1/README.md).
A точно совпадает с [bridge controls](../fixtures/providers/bridge-semantic-probe-v1/README.md).
B меняет только инструкцию: цитата — evidence anchor, а typed fields определяют
проверяемое утверждение. Никаких переводов, нормализации, исправлений кандидата,
новых questions или подсказок с правильной label.

| Контроль | Что проверяем                                                                 | Ожидаемая label / policy | Jev baseline, исторически | Luna Decisions baseline, исторически |
| -------- | ----------------------------------------------------------------------------- | ------------------------ | ------------------------- | ------------------------------------ |
| T01      | «Я не оплатил парковку», но candidate утверждает оплату                       | incompatible / reject    | compatible — ошибка       | incompatible                         |
| T02      | Та же цитата, candidate правильно отрицает оплату                             | compatible / accept      | compatible                | compatible                           |
| T03      | «Не помню, оплатил ли парковку», candidate сохраняет unknown                  | compatible / accept      | compatible                | compatible                           |
| T04      | «ТС стояло в зоне ПП; оплаты нет», парковочная placement требует уточнения ПП | indeterminate / review   | compatible — ошибка       | incompatible — ошибка                |

Таблица использует [исторический bridge run](BRIDGE_SEMANTIC_PROBE_2026-10-18.md).
В отдельном [Jev A/B rerun](JEV_QUOTE_AUTHORITY_RETRY_2026-10-18.md) обе постановки
дали compatible на всех четырёх контролях: уточнение не исправило T01/T04.
Эти серии не объединяются в новую выборку. Jev/Luna повторно не вызываются.

## Разрешение и caps

Пользователь подтвердил: «Да, 8 запросов: исходная + уточнённая постановка».
[План](../fixtures/providers/liquid-d1-hard-controls-v1/plan.json) фиксирует hashes,
references и порядок AB / BA / AB / BA: 8 последовательных fresh requests,
по одному overall Choice на запрос, без общего диалога.

- Только `d1-ultra`, официальный Liquid endpoint; 8 attempts максимум.
- Без retries, repair, fallback, дополнительных вызовов Jev/Luna или повторов
  семантически неудачных ответов. 30s на operation, 300s на серию, 1MiB на response.
- Первый transport/HTTP/protocol/unknown outcome, drift model/task или deadline
  останавливает серию; остальные jobs остаются not-executed.
- Семантическое несовпадение не останавливает запланированную серию.
- Внешний денежный ceiling Liquid не проверен; CoreInfra ceiling не переносится.
  Usage, API cost и estimate учитываются отдельно, без фиктивного нулевого billing.
- Ключ передаётся через скрытый stdin, только в память процесса. Его нет в plan,
  Git, argv или capture. Credentials и Authorization не публикуются.

## Сравнение и границы вывода

Primary: исправление T01 false acceptance; T04 — сохранение review при ambiguity.
T02/T03 — обязательные positive/unknown controls для обнаружения регрессии.
Показать все 8 labels, policy outcomes, confidence отдельно от P(selected),
полные distributions, actual model, HTTP outcome, usage, cost и latency.
Внутри Ultra сравнить A/B: какие ошибки исчезли, сохранились или появились.

Новый arm идёт прямым HTTP, исторические — через bridge/SDK. Проверка prepared
inputs подтвердила равенство A state/questions с фактически отправленными
историческими native requests. Меняются provider/model/transport/time; это
исторический diagnostic comparison, не свежий matched cross-provider benchmark
и не проверка совместимости Jev4Mellea. Latency/confidence разных providers
не используются как сопоставимая шкала качества или эффективности.

Четыре контроли содержат три authored source texts; восемь A/B variants не равны
восьми независимым делам. References candidate, не independent human gold;
ожидания T03/T04 ранее согласованы с пользователем в guided nonblind discussion.
Нет population accuracy, статистической значимости, calibration или ranking.
Предыдущий [простой smoke PR174](https://github.com/SoundBlaster/NormLab/pull/174)
не добавляется к denominator этой серии. Основной route приложения не меняется.
