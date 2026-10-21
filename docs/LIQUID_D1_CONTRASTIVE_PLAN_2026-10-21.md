# D1 Ultra: шесть контрастов разметки

Дата: 2026-10-21. Ledger: [#70](https://github.com/SoundBlaster/NormLab/issues/70).
Подготовка сохранена в commit `ee0cee9`. Пользователь отдельно разрешил
12 запросов с предложенными caps: «Делай, разрешаю». Authorization и actual
driver зафиксированы в `ab7be2d` до inference. Серия завершена: 12/12 HTTP 200;
10/12 candidate agreement и 4/6 полностью верных пар.
См. [результаты и evidence](LIQUID_D1_CONTRASTIVE_RESULTS_2026-10-21.md).

## Зачем следующая серия

В [предыдущей серии, PR #175](https://github.com/SoundBlaster/NormLab/pull/175)
Ultra отклонил ошибочное утверждение оплаты при отрицании в источнике, но принял
парковочную трактовку неоднозначного «ПП». Оригинальная и уточнённая инструкция
дали одинаковые labels: 3/4 совпадения в каждой постановке. Это мотивирует
проверить другие семантические контрасты, прежде чем менять provider или prompt.

Гипотеза: при неизменной исходной инструкции Ultra различает поддержанную
разметку и изменение одного typed field — модальности, участника, автора
сообщения, stance или предиката. Для неоднозначного предиката нужна review,
а для правильно размеченного unknown — accept.

Это проверка выбранных утверждений в тексте. Система не устанавливает истинность
оплаты, состав правонарушения, полноту извлечения или юридический результат.

## Тексты, кандидаты и ожидания

В [packet](../fixtures/providers/liquid-contrastive-controls-v1/README.md) —
12 tasks, шесть пар и шесть неизменных source texts из прежнего development-набора.
В каждой паре меняется ровно одно поле одного claim. Цитаты, offsets, остальные
claims и исходный текст остаются одинаковыми. `a`/`b` обозначают кандидатов,
**не варианты инструкции**; их IDs в модель не передаются.

| Пара | Исходный текст                                        | Кандидат a → ожидание            | Кандидат b → ожидание                        |
| ---- | ----------------------------------------------------- | -------------------------------- | -------------------------------------------- |
| P01  | «Я должен был оплатить парковку.»                     | `mode=obligation` → compatible   | `mode=actual` → incompatible                 |
| P02  | «Допустим, парковка была оплачена.»                   | `mode=hypothetical` → compatible | `mode=actual` → incompatible                 |
| P03  | «Парковку моего автомобиля оплатил друг, а не я.»     | `actor=person_2` → compatible    | `actor=person_1` → incompatible              |
| P04  | «В письме сообщили, что моя парковка не оплачена.»    | `claimant=letter_1` → compatible | `claimant=narrator` → incompatible           |
| P05  | «Не помню, оплатил ли парковку.»                      | `stance=unknown` → compatible    | `stance=asserted` → incompatible             |
| P06  | «В постановлении: “ТС стояло в зоне ПП; оплаты нет”.» | raw `standing` → compatible      | parking-specific `placement` → indeterminate |

В таблице P06 кавычки приведены для чтения; точный source с «ёлочками» сохранён
в JSON без изменений. Обе версии сохраняют `claimant=notice_1` и правильно
отрицательную оплату. `standing` не расшифровывает «ПП» и не утверждает парковку.
`placement` требует парковочной трактовки: без уточнения paid parking versus
pedestrian crossing остаётся indeterminate. Исходный R032 не переименован в
indeterminate: это отдельный кандидат T04 с другим предикатом.

В P01/P02 неверен перенос obligation/hypothetical в actual; это конфликт
разметки с явно указанной модальностью, а не доказательство фактической неоплаты.
В P04 письмо — автор сообщения, рассказчик сообщает о нём. В P05 принимается
корректное представление неопределённости, а не положительный факт оплаты.

Все expectations — **candidate references, не independent human gold**.
Переиспользуются существующие v2 labels и ранее согласованное с пользователем
толкование T04. Новый независимый semantic review этих 12 tasks не проведён.
P05a и P06b повторяют старые T03/T04: это regression sentinels, не новые примеры.
Остальные десять ещё не проверены на Ultra в предыдущей серии; весь материал
ранее открыт при разработке и не подходит для holdout. Шесть пар не являются
двенадцатью независимыми кейсами.

## Постановка и proposed caps

[Plan](../fixtures/providers/liquid-contrastive-controls-v1/plan.json) связывает
точные tasks, исходные файлы, question, policy и references через SHA-256.
В task только `state` и `questions`; references и metadata хранятся отдельно.

- `d1-ultra`, тот же официальный Liquid endpoint, direct HTTP.
- Одна исходная question из bridge T01, без добавления B-инструкции. Во всех
  tasks одинаковые conventions и predicate definitions. Никаких новых prompt
  tactics, переводов, нормализации, repairs или резюме.
- 12 последовательных независимых запросов, по одному Choice `overall` каждый.
  Нет общего диалога. Порядок внутри пар чередуется a/b и b/a и указан в plan.
- Максимум **12 HTTP attempts**, **0 retries**, 30 секунд на запрос,
  360 секунд на серию, 1 MiB на response. Без новых Jev/Luna вызовов и fallback.
- Первый transport/HTTP/protocol/unknown outcome, model/task drift или cap
  останавливает серию; неисполненный suffix остаётся not-executed.
  Несовпадение label не останавливает остальные запланированные задания.
- Ключ только в памяти процесса через скрытый stdin; в repository, argv,
  capture, plan и ledger он не попадает. Redirects запрещены.
- Внешний Liquid monetary cap не подтверждён. Прежний CoreInfra $4 ceiling
  не переносится. Usage, поле API cost и estimate отмечаются раздельно;
  фактическое списание без billing evidence остаётся неизвестным.

При подготовке `authorizedAttempts=0`; прошлое разрешение на восемь запросов
исчерпано. Новое разрешение относится только к этим 12 tasks и указанным caps.
Actual [driver](evidence/liquid-contrastive-run-2026-10-21/driver.py), его hash
и hash общей deadline/redirect utility связаны plan и сохраняются в Git
до первого вызова. Driver не перезаписывает capture и отказывается запускаться
из грязного checkout или с optimized Python. Ключ поступает через скрытый stdin.
Это одноразовый direct-HTTP diagnostic, без нового provider SDK или framework.

## Что измеряем и какое решение принимаем

1. Для каждого из 12 planned jobs: HTTP/status/error, requested/returned model,
   exact request и raw response, label, policy outcome, native confidence,
   P(selected), distribution, token usage, API cost и latency. Недоступные
   данные остаются null, failures/unknown/not-executed не скрываются.
2. Candidate agreement с denominator 12 и отдельными counts по завершённым.
   Полный правильный контраст — **обе** labels пары совпали; denominator 6.
3. False acceptance из пяти incompatible candidates; false rejection из шести
   compatible; unnecessary review для определённых references; overdetermination
   для единственного indeterminate P06b. Acceptance всех подряд не проходит пары.
4. Все raw outcomes учитываются; дубликаты старых controls показаны отдельно,
   старые и новые серии не объединяются в accuracy или большой denominator.
5. После серии — offline пересчёт из capture и review всех несовпадений. При
   спорном reference сохранить prediction и объявить его inconclusive до
   adjudication; новые толкования версионировать, старый score не переписывать.

Reject criterion гипотезы «на выбранных контрастах достаточно текущей постановки»:
хотя бы одна пара с неправильной label. Тогда показать конкретный неподдержанный
переход и выбрать **одну** следующую тактику для этой ошибки. Operational stop
делает серию неполной, а не отрицательным semantic результатом.

Если все шесть пар пройдут, вывод ограничен этими контролями в этом запуске.
Нет доказательства общей accuracy, superiority, calibration или достаточности
для production. Confidence threshold по этим 12 ответам не подбирается;
primary route и реальные пользовательские решения не меняются.

## Acceptance подготовки

- Exact source/claims/question/provenance и ожидания сохранены до inference.
- Для каждой пары подтверждён один изменённый claim field, все quotes/offsets
  сверены с оригиналом; reference labels отсутствуют в wire task.
- Исторические файлы не изменены, hashes и локальные links проверены.
- На этапе подготовки авторизация, runtime freeze и результаты явно pending;
  0 live requests. Эта историческая проверка сохранена в `preparation.json`.
- После отдельного разрешения — freeze actual driver с сохранением исходных
  tasks/references, затем максимум 12 attempts и offline сверка результатов.
