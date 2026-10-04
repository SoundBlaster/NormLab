# Parking extraction baseline — 2026-10-04

Статус: выполненный ограниченный эксперимент, **acceptance gate не пройден**. Это оценка одной комбинации prompt/schema/model/runtime, не юридической корректности и не возможностей GPT OSS 20B вообще. Сохранены [исходные artifacts](../experiments/parking-baseline/2026-10-04-gpt-oss-20b/); [reference graphs](../fixtures/parking-pilot/reference/README.md) — candidate drafts, не human-approved semantic truth.

## Конфигурация

- LM Studio 0.4.23+1; CLI commit `07b7252`.
- Model API identifier `openai/gpt-oss-20b`, GGUF MXFP4. Веса не хешированы; ID/quantization не удостоверяют идентичность конкретного файла.
- Через `lms load` установлен context 16384, TTL 1800 секунд. `lms ps --json` во время первого запроса подтвердил contextLength 16384 и parallel 1. Load занял 18.46 s, сообщил 11.28 GiB.
- Requested sampling: temperature 0, seed 42, max_tokens 8192, stream false. Это параметры запроса, не доказательство deterministic decoding или соблюдения каждого параметра backend.
- Один запрос на P01/P02/P04/P09, последовательно, timeout 240000 ms; никаких retries/JSON repairs/provider grammar. Модель получила source + common prompt/schema/scalar catalogue, без эталонов и reviewer notes.
- Application request содержит source/schema/ontology bindings. Raw HTTP responses, content и validation results сохранены как были получены; timeout не имеет завершённого response/content.

## Результаты

| Case | Outcome                       | Latency   | Tokens prompt/completion | Первичный отказ                                                                |
| ---- | ----------------------------- | --------- | ------------------------ | ------------------------------------------------------------------------------ |
| P01  | JSON получен, schema rejected | 21.147 s  | 3382 / 799               | ParkingZone содержит запрещённый `label`                                       |
| P02  | JSON получен, schema rejected | 23.176 s  | 3385 / 966               | coversInterval использует valueText вместо entity object                       |
| P04  | HTTP provider error           | 17.800 s  | Не получены              | `The model produced output that does not match the expected peg-native format` |
| P09  | Timeout                       | 240.122 s | Не получены              | `The operation was aborted due to timeout`                                     |

Итого: 2/4 завершённых model JSON responses, 0/4 принятых proposals. Это наблюдаемые counts данной серии. Precision/recall, устойчивость и semantic quality score не вычислены; одна попытка на case не определяет их. Finish reason P01/P02 — stop, не length. Latency включает HTTP/inference, без отдельной оценки prefill/decoding; model load выполнен до серии.

## Дополнительный review raw JSON

Runtime validator возвращает shape errors до graph validation. Следующие ошибки найдены **статическим review raw answers**; это не результаты повторного запуска исправленного JSON.

### P01

- Source quote точно воспроизводит всю фабулу без завершающего LF (540 UTF-16 units), но endOffset задан 400. Такой anchor не совпадает с quote.
- Участник получил alias `Алексей`, то есть имя не обезличено.
- roleParticipant имеет Participant subject и строку `driver` вместо ссылки на Participant object от RoleAssignment; роль водитель дополнительно не установлена текстом.
- involvesVehicle связывает Vehicle с Participant, а placementInEpisode — Vehicle с ParkingZone. Это неверные domain/range.
- inMoscow/cityParking применены к Episode вместо Location/ParkingPlace.
- Потеряны ключевые явные отрицания: оплаты, payment complexity и permit. Нет нужных ParkingPlacement/ParkingPlace/TimeInterval/RoleAssignment instances; gaps пусты.

### P02

- Source quote содержит 494 UTF-16 units, endOffset 374. Alias `Мария` сохраняет исходное имя.
- Object `owner` не является entity ID, а роль owner не моделируется через RoleAssignment.
- `ti1`, `sess1`, `pay1`, `zone_M102` используются в links, но instances не созданы. Есть неверные domain/range и направления связей.
- coversInterval должно ссылаться на TimeInterval, не valueText.
- Нет отдельных корректных paymentStart/departure proposals; не сохранены явные отрицания complexity/permit.
- Gap `No mention of permit, subscription or special tariff` ошибочен для permit/subscription: фабула прямо отрицает разрешения, абонементы и льготы. Отсутствие специальных тарифов отдельно из текста не следует.

### P04/P09

Завершённых model proposals нет, поэтому сохранение двух автомобилей/исправления и противоречия P09 этим прогоном не оценено. Строка ошибки P04 указывает на сбой формата/протокола engine; конкретная первопричина backend не установлена. Timeout P09 сам по себе не доказывает semantic/model error. Во время последующего `lms ps --json` загруженных моделей не было; причина выгрузки не исследована.

## Проблемы нашего input contract

Schema сообщает link predicate names и обязательность object, но request modelInput не передаёт domain/range и объяснения link semantics. Scalar catalogue передаёт domain, но не полные descriptions. Это неполное описание vocabulary для модели; нельзя приписывать все ошибочные links только её возможностям.

Ручной счёт UTF-16 offsets оказался ненадёжным в обеих полученных responses. Exact quotes воспроизведены, но привязка чисел неверна. Следующий дизайн может предложить quotes/occurrence, а application разрешать offsets по неизменному source: неоднозначную цитату нужно отклонять/уточнять, не выбирать скрытно.

Здесь prompt и validator не ослаблены после наблюдения результатов. Исправленные/восстановленные outputs не выдаются за baseline model responses.

## Следующий ограниченный эксперимент

1. Дополнить modelInput явным typed predicate catalogue с domain/range и короткими neutral examples, не используя ответы evaluation cases.
2. Отдельно проверить provider structured output/grammar на supported schema; сохранить ошибки совместимости вместо silent fallback.
3. Спроектировать application quote anchoring с проверкой уникальности и явным handling повторов; сохранить provenance и отсутствие silent repair фактов.
4. Повторить те же четыре cases в новом run directory, сохранив старую серию; менять факторы явно и сравнивать format/ref/source errors отдельно от semantics/latency.

До этого не подключать текущую конфигурацию как надёжный auto-extraction путь UI. Manual review остаётся обязательным даже после устранения structural errors. Norm source provenance и legal lock gate развиваются независимо от model evaluation.
