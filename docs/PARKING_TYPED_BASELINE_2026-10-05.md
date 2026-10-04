# Typed/quote baseline — 2026-10-05

Вторая ограниченная серия. [Implementation design](PARKING_TYPED_EXTRACTION.md), [raw evidence](../experiments/parking-baseline/2026-10-05-typed-quotes-gpt-oss-20b/), [первая серия](PARKING_BASELINE_2026-10-04.md). Candidate references не считаются human-approved semantic truth.

## Конфигурация и изменения

GPT OSS 20B GGUF MXFP4 уже был загружен в LM Studio под identifier `hyperreview-gpt-oss-20b`; `lms ps --json` сообщил context 16384, parallel 1, idle перед серией. Instance использован без выгрузки/перезагрузки. Model weights не хешированы; alias не доказывает идентичность weights первой серии. Runtime edition предыдущего прогона была 0.4.23+1; повторное подтверждение версии в этой серии отдельно не записано.

Новый wire contract v2, typed entity/link catalogue и prompt reminders, quote-only spans вместо model offsets. Остались requested temperature 0, seed 42, max_tokens 8192, stream false, 240 s timeout, 4 последовательных запроса, без retries/repairs/provider grammar. Ground truth и reviewer notes не передавались. Source texts и reference set те же.

Меняются несколько факторов одновременно, включая использование уже загруженного instance с alias: нельзя приписывать разницу latency/transport одному catalogue или quote adapter.

## Outcomes

Все 4 responses — JSON, finish reason stop. Все 4 отклонены shape validation: graph/quote validation для них не выполнялась, поскольку schema является первым gate. Ни один output не нормализован и не принят.

| Case | Latency  | Первичные ошибки формы                            |
| ---- | -------- | ------------------------------------------------- |
| P01  | 39.640 s | label у ParkingPlace/Zone; пустой attributionText |
| P02  | 17.540 s | label у ParkingZone                               |
| P04  | 33.828 s | label у нескольких parking entity variants        |
| P09  | 35.192 s | label у ParkingZone; два пустых timezoneText      |

В первой серии было 2/4 JSON responses и 0/4 accepted; здесь 4/4 и 0/4. Acceptance gate не пройден. Это наблюдаемые counts двух небольших серий, не статистическая оценка качества или устойчивости.

## Static semantic review raw answers

- P01: источник имени остался в alias/ID; roleParticipant имеет Participant subject, RoleAssignment ref отсутствует. Ключевые отрицания оплаты/complexity/permit не сохранены. Unmapped evidence `source` не существует. Некоторые placement links получили правильные directions, но полный граф некорректен.
- P02: имя не обезличено; `driver` используется как entity object, involvesVehicle/placeInZone — self links неверных concepts. Payment/Session/coverage и основные отрицания пропущены.
- P04: не выделен второй автомобиль. Успешная оплата сведена к PaymentAttempt; paymentForSession от PaymentAttempt недопустим. ParkingPlacement не создан, но некоторые place links используются как placement links. Quotes `мой личный автомобиль` и `Москва` отсутствуют буквально в исходном тексте (там другие формулировки/падеж); exact anchoring также отклонил бы их после shape gate. Сообщение «исправление сохранено» необоснованно привязано к 18:00, хотя эта отметка относится к действию исправления, не времени сообщения app.
- P09: opposing asserted/denied представлены как coversInterval от Vehicle, не как payment assertions. Один quote о неоплате используется как evidence для положительных сведений/сущностей; refs evidence на Episode вместо span. Корректное сохранение semantic conflict не подтверждено.

Это чтение raw outputs, не auto-scoring по совпадению IDs и не повторный запуск repaired JSON. Precision/recall и общий semantic score не объявляются.

## Adapter validation

Четыре reference graphs преобразованы в quote-only wire representation без изменения statements. Для повторяющихся quotes occurrence выбран из исходного reference offset. Replay v2 consumer восстановил точные original offsets, прошёл graph validator и вернул unreviewed proposals. Это подтверждает compatibility adapter с этими artifacts; не доказывает, что модель выберет правильную quote/occurrence или что reference semantics одобрены.

Raw responses сохранены отдельно от derived validation. Старые artifacts первой серии не изменены. После серии оба runner дополнены автоматическим manifest; historical runner hashes относятся к commits, указанным в baseline README. Digest manifest второй серии фиксирует evidence bytes; он unsigned и не является attestation.

## Следующий ход

Проверить provider structured output compatibility и затем провести отдельную серию с constrained shape. Если форма стабилизируется, оценить semantic completeness/negation/roles отдельно. Рассмотреть более простой промежуточный extraction contract и application graph construction, если прямое построение графа продолжает терять факты. Не ослаблять доверенные graph/source проверки ради acceptance count.
