# Candidate reference graphs

Подготовлено Codex: 2026-10-04. Статус: **candidate-reference-draft**, не одобренные человеком юридические эталоны. Словарь — [parking contract v1](../../../docs/PARKING_EXTRACTION_CONTRACT.md). Эти графы подготовлены по текстам corpus, а не получены запуском локальной extraction модели.

## Файлы и проверка

Для каждого case сохранены `Pxx.source.txt` и `Pxx.graph.json`. Source — точная однострочная фабула из [CASES.md](../CASES.md), с завершающим LF. В source нет reviewer notes. [manifest.json](manifest.json) содержит SHA-256 файлов и **reviewer-only** expectations; manifest не является подписью или approval.

```bash
rtk proxy npm run parking:references:check
```

Команда проверяет digest, совпадение source с corpus, strict extraction contract, IDs/refs/domain/range, offsets/quotes и сохранение аннотированной пары P09. Она включена в CI. Успех не подтверждает, что цитата семантически поддерживает каждый proposal, что все нюансы извлечены или что case соответствует праву.

| Case | Entities | Assertions | Unmapped | Основная проверяемая семантика                                                                       |
| ---- | -------- | ---------- | -------- | ---------------------------------------------------------------------------------------------------- |
| P01  | 10       | 19         | 3        | Явные отрицания оплаты, сложности и льгот; без выдуманных Payment/Session                            |
| P02  | 13       | 26         | 2        | Payment/Session отдельно от размещения; правильные vehicle/zone; интервалы 11:00–11:30 и 11:00–12:00 |
| P04  | 14       | 23         | 3        | Два Vehicle IDs; исходный платёж → vehicle2; SessionCorrectionClaim без переопределения платежа      |
| P09  | 12       | 23         | 1        | Два opposing payment assertions одного episode; attribution к рассказчику и его заметке              |

IDs, labels и количество spans — выбранное представление, не единственный допустимый ответ. При baseline нельзя сравнивать JSON byte-for-byte: модель может использовать другие IDs и более короткие/длинные подходящие quotes. Нужны semantic matching и review.

## Контрольные точки evaluator

- **P01:** `noPayment` denied; `noComplexity` и `noPermit` тоже denied. `paidPeriod` — утверждение автора, не normative verification. Нет sanctions или полного вывода о виновности.
- **P02:** `paymentVehicle` → vehicle1, `paymentZone` → zone1, `paymentCoverage` → paidTime. `paymentTime` 11:02 не перепутан с началом оплаченного интервала 11:00. `departure` 11:30 не является завершением app session. Amount/currency отсутствуют.
- **P04:** `paymentVehicle` → vehicle2, размещение → vehicle1. `correctionSession` не создаёт новый Payment и не меняет target vehicle. Время correction 18:00 и сообщение app сохранены в gaps. Оплаченный интервал и paid regime не придуманы.
- **P09:** `paymentPresent` asserted и `paymentDenied` denied остаются двумя assertions. Их IDs записаны в reviewer manifest. `attributionText` сохраняет различие текущего рассказа и заметки; attributedTo у обоих — один рассказчик. Payment 16:02, известный конец покрытия 17:00, неизвестное начало покрытия. Нет выдуманной Session.

`valueText` содержит proposition, а `stance` — её утверждение/отрицание. Exact source quote хранит исходное отрицание. Подтверждение/отвержение пользователя в графах отсутствует: все statements считаются unreviewed. `participantKind: unknown` не делает вывод о формальном статусе физического лица из первого лица/имени; personal car extraction ещё не закрывает C07.

## Явные пробелы vocabulary

- RoleAssignment имеет participant и episode, но нет target Vehicle. Слова о принадлежности автомобиля сохранены в `ownerVehicleTarget`/`ownershipTarget`. Особенно в P04 нельзя использовать роль owner для назначения собственности vehicle1: исходная фраза относится к vehicle2.
- Нет scalar predicate «сессия не запущена»: P01 содержит `noSession` gap, существующая Session не создаётся из отрицания.
- Нет отдельного predicate о споре знаков: P01/P02 сохраняют явное отрицание в `noSignDispute`.
- Нет predicate времени correction и app-сохранения: P04 сохраняет `correctionTime`/`applicationReport`. Сообщение app не удостоверяет правовой эффект.
- ParkingZone не имеет label/code field; текст зоны сохраняется в evidence entity и placeInZone. Location с Moscow assertion не получает выдуманный relation к place: такого predicate пока нет. Для typed findings adapter связь места и юрисдикции требует явного проектирования/review.

Gap — сохранённая source-backed информация, а не автоматически утверждённое расширение онтологии. Достаточность графов и необходимость каждой ontology delta нужно обсудить на baseline.

## Reviewer expectations

Expected flows в manifest — ориентиры **после соответствующего review**, не computed ScopeAssessment:

- P01/P02: базовые неоплаченный/оплаченный кандидаты при закрытии остальных условий и normative lock.
- P04: unsupported после подтверждения сложности оплаты.
- P09: конфликт после установления несовместимости statements. Validator лишь проверяет, что аннотированная пара не потерялась; generic semantic conflict detection не реализована.

Перечни unknown/incomplete conditions — reviewer заметки, не полная модель обязательных уточнений. Во всех случаях C08/C16 и normative lock открыты; отсутствие подробностей об исключениях не означает их отрицание. Temporal precision `exact` означает точность **как в источнике** (минуты), без придумывания секунд/UTC offset.

## Следующий шаг

Baseline GPT OSS 20B: в модель отправить только `source.txt` плюс общий prompt/schema из application request. Не передавать graph, manifest, expected flows или эти заметки. Записать raw responses, bindings, runtime/model/sampling, latency, validator errors; затем вручную сравнить смысл statements, роли, эпизоды, отрицания и gaps. Численные acceptance thresholds ещё не утверждены.
