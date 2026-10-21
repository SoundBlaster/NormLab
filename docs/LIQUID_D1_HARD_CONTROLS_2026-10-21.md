# D1 Ultra на исторических проблемных контролях

Дата: 2026-10-21. Ledger: [#70](https://github.com/SoundBlaster/NormLab/issues/70).
Protocol зафиксирован до inference в commit `c691951`.
Серия завершена: 8/8 HTTP 200, без retries и технических сбоев.

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

## Результат

| Контроль | Ожидание               | Ultra A               | Ultra B               | Совпадение с candidate reference |
| -------- | ---------------------- | --------------------- | --------------------- | -------------------------------- |
| T01      | incompatible / reject  | incompatible / reject | incompatible / reject | Да / да                          |
| T02      | compatible / accept    | compatible / accept   | compatible / accept   | Да / да                          |
| T03      | compatible / accept    | compatible / accept   | compatible / accept   | Да / да                          |
| T04      | indeterminate / review | compatible / accept   | compatible / accept   | Нет / нет                        |

В каждой постановке — **3/4 совпадения**; между A и B **0/4 изменений label**.
Ultra отклонил ошибочно утверждённую оплату T01, которую исторический Jev
принимал, и сохранил правильные отрицание T02 и unknown T03. Однако T04
принят без уточнения «ПП». Историческая Luna Decisions также совпала в 3/4,
но для T04 ошибочно выбрала reject; обычная Luna Low в историческом bridge
run совпала в 4/4. Это разные, несинхронные серии, а не рейтинг моделей.

Уточнение инструкции не исправило оставшуюся ошибку Ultra на этих контролях.
Оно меняло probabilities, но ни разу не поменяло итоговую label.

### Все ответы

| Job  | Label        | Native confidence | P(selected) | Latency, s |
| ---- | ------------ | ----------------- | ----------- | ---------- |
| T01A | incompatible | 0.5710            | 0.7140      | 1.005      |
| T01B | incompatible | 0.5685            | 0.7123      | 0.851      |
| T02A | compatible   | 0.9075            | 0.9384      | 0.908      |
| T02B | compatible   | 0.8902            | 0.9268      | 0.907      |
| T03A | compatible   | 0.7031            | 0.8021      | 0.938      |
| T03B | compatible   | 0.7779            | 0.8520      | 0.892      |
| T04A | compatible   | 0.3950            | 0.5967      | 0.915      |
| T04B | compatible   | 0.4385            | 0.6256      | 0.869      |

Порядок фактического выполнения: T01A, T01B, T02B, T02A, T03A, T03B,
T04B, T04A. Confidence — отдельное поле provider, не P(selected) и не
проверенная вероятность правильности. В T04 confidence ниже остальных
контролей, но порог для маршрутизации по этим ответам не подбирался и не
проверялся на независимых данных.

### Operations и стоимость

- 8 planned, 8 attempts, 8 completed; 0 retries, failures и unknown outcomes.
- Модель во всех ответах: `d1-ultra`. Время серии: **7.298 s**.
- Usage: **10 304 input / 0 output tokens**.
- Сумма API `usage.cost`: **0.000432768**, валюта поля отдельно не подтверждена.
- Estimate по опубликованной цене $0.042/M input: **$0.000432768**.
  Источник тарифа: [Liquid D1 documentation](https://docs.liquid.ai/lfm/models/d1).
  Estimate и API field не заменяют проверку фактического списания; billing
  не проверялся.
- Лимит разрешения исчерпан: **8/8**. Offline verification не вызывает API.

## Evidence и следующий шаг

- [Frozen plan](../fixtures/providers/liquid-d1-hard-controls-v1/plan.json),
  [одноразовый driver](evidence/liquid-d1-hard-controls-2026-10-21/driver.py).
- [Capture](evidence/liquid-d1-hard-controls-2026-10-21/report.json): точные request
  objects, полные response distributions, outcomes, timing и usage.
- [Comparison](evidence/liquid-d1-hard-controls-2026-10-21/comparison.json):
  сравнение с candidate references и историческими observations.
- [Offline verification](evidence/liquid-d1-hard-controls-2026-10-21/verification.json):
  hashes, соответствие tasks отправленным objects, schema/distributions,
  agreement, caps и отсутствие credentials. Это проверка согласованности
  сохранённых данных, не доказательство semantic gold, billing или SDK integration.

Следующий шаг — review этой серии. Для дальнейшего выбора стратегии нужен
отдельный замороженный набор с modality/attribution/ambiguity controls; текущие
четыре контроля не обосновывают замену provider или настройку confidence threshold.
