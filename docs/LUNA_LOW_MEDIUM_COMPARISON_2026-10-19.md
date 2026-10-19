# Luna Low → Medium: результаты неполного парного прогона

2026-10-19 MSK. [Protocol](LUNA_EFFORT_COMPARISON_PLAN_2026-10-19.md),
[Low baseline](LUNA_DEVELOPMENT_PILOT_2026-10-19.md),
[PR #159](https://github.com/SoundBlaster/NormLab/pull/159),
[задача #70](https://github.com/SoundBlaster/NormLab/issues/70).

## Результат

**Medium arm остановлен после 11 provider attempts:** пять фабул завершены,
DEV017 отклонён локальной валидацией discovery, четыре следующих не запускались.
Все 11 ответов API — HTTP 200, `status=completed`, возвращённая модель
`gpt-6-luna`, effort echo `medium`. **Это не сетевой сбой.**

Повторов, repair, fallback и judge не было. First-error stopping rule соблюдено;
неиспользованный остаток cap30 не был превращён в разрешение повторить сбой.
Полное сравнение десяти фабул не получено; semantic verdict для suffix отсутствует.

Из пяти завершённых пар: три прежних candidate-pass сохранились, candidate
payer-scope concern остался, DEV006 получил полезное дополнительное описание
ошибки объекта платежа, но прежняя ownership неоднозначность не устранена.
**Оснований переключать default на Medium пока нет.** Это не доказательство,
что Medium хуже вообще; повышение effort не обеспечило успех текущего контракта.

## Что было зафиксировано до inference

User: «Ок, выполни» для десяти кейсов, максимум30 попыток, без retries/repair/judge,
120/300/900s operation/case/series, прежний сообщённый внешний потолок аккаунта$4.
Потолок не проверялся и не сбрасывался; денежная стоимость неизвестна.

Execution commit **`35fc3b8`**, [authority](evidence/luna-medium-2026-10-19/authority.json).
Production source/prompts/schema, старые low artifacts и набор не менялись.
Отдельный runtime использовал **единственную source substitution**:
`OPENAI_REQUEST_SETTINGS.reasoning.effort: low → medium` для discovery и classification.
Среда прежняя: Node v26.5.0, esbuild0.28.2, dependencies исходного Low runtime.
Все133 source/input/config/dependency/driver/plan bindings проверены. Build и
приватный capture на проверенном TB5; секрет только из окружения.

Проверки до отправки:

- Заново собранный Low bundle побайтно равен исходному Low bundle.
- Dry-run Medium прошёл, actual hosted prompt/config digest отличается от Low
  и соответствует фактическому effort.
- На всех20 archived Low responses проверено offline: emitted Medium request
  templates отличаются только effort; остальная обработка совпадает с ожидаемой.
- Bounded supervisor повторно использован через пять закреплённых transformations,
  включая self hash и actual prompt digest. Новый execution plan hash-bound.
- После live подтверждено: **все11 фактически отправленных request bodies**
  отличаются от соответствующих Low request bodies только `reasoning.effort`.
  Изменение effort в response echo не аттестует скрытые вычисления провайдера.

Baseline исторический, Low заново не вызывался. Сравнение не контролирует
стохастику и скрытый drift provider/model alias; это не causal significance test.

## Ожидаемый смысл и фактические различия

Проверены все10 fragments/10 decisions/**27 statements** завершённых Medium
результатов, source → output и output → source, плюс оба raw discovery extraction
в неуспешном DEV017. Отдельно сохранены immutable baseline, Medium output и review.
Тот же Codex готовил candidate cards и review; это не blind или независимый human gold.

| Кейс   | Ожидание                                                                                     | Low → Medium                                                                                                                  | Candidate вывод                                                                         |
| ------ | -------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| DEV001 | Москва, городская парковка, размещение и оплата через приложение без придуманного paidRegime | Четыре поддержанных statements в обоих arms; смысл сохранён                                                                   | Unchanged, без найденной critical ошибки                                                |
| DEV002 | **Сам рассказчик** не оплачивал; об оплате другими лицами не сказано                         | «Парковка не была оплачена» → **«Парковку не оплачивали»**. Новая attribution относится к оставлению машины, а не плательщику | Прежний candidate POL/ROLE concern остался                                              |
| DEV003 | Явное незнание результата оплаты                                                             | `payment=unknown` в обоих arms; не заменён на denied                                                                          | Unchanged, без найденной critical ошибки                                                |
| DEV006 | Стоял А, платёж за Б; оба принадлежат рассказчику, оплата А не установлена                   | А/Б разделены в обоих. Medium добавил **`paymentComplexity`: «Платёж прошёл за другой автомобиль — Б»**                       | Полезный частичный gain. Ownership А всё ещё только в контексте «тоже»; кейс unresolved |
| DEV013 | Стоянка12:00–12:30 и отдельный paymentStart12:05:01                                          | Точное время сохранено; Medium добавил поддержанную attribution оплаты                                                        | Unchanged, без найденной critical ошибки                                                |
| DEV017 | Оба канала не работали, оплатить не удалось; вина не установлена                             | Low completed; Medium discovery выбрал subject **«Приложение и СМС»**, запрещённый локальным контрактом                       | Новый pipeline contract failure; classification не было                                 |
| DEV027 | Две стоянки с разными оплатами и общими location/type facts                                  | Medium не запускался после DEV017                                                                                             | Общая episode-scope ошибка Low не проверена на Medium                                   |
| DEV028 | Сохранить конфликт narrator/notice без выбора победителя                                     | Medium не запускался                                                                                                          | Нет нового результата                                                                   |
| DEV032 | Казань/неоплата; не выдавать человека за автомобиль                                          | Medium не запускался                                                                                                          | Subject/type ошибка Low не проверена на Medium                                          |
| DEV044 | Процесс оплаты, ошибка номера, штраф и procedural вопрос без выдуманного payment success     | Medium не запускался                                                                                                          | Modality/contract вопрос не проверен на Medium                                          |

DEV006 не объявлен полным исправлением: новый `paymentComplexity` описывает другой
автомобиль благодаря контексту обоих fragments; его собственная quote — о платеже
за Б, subject — `vehicle_2`. Полная связь с parked А и владение обоими автомобилями
не стали отдельными отношениями. Эти решения по representability остаются на review.

Общая таблица состояний: **5 completed, 1 schema-invalid, 4 not-run** из10 назначенных.
Среди пяти завершённых:3 candidate-pass,1 candidate-critical-error,1 unresolved.
По transitions:4 unchanged,1 unresolved с частичным descriptive gain;
ещё5 operational/not-comparable. **Общий процент качества не вычисляется.**

## Почему упал DEV017

Источник:

> В Москве я стоял на городской парковке. Приложение и СМС не работали, оплатить парковку не удалось.

Raw discovery сохранил оба предложения дословно и вернул:

```json
{
  "statement": "Приложение и СМС не работали, оплатить парковку не удалось.",
  "statement_attributes": {
    "subject": "Приложение и СМС",
    "aboutEpisode": "episode_1",
    "speaker": "narrator"
  }
}
```

В provider JSON Schema `subject` описан как `{"type":"string"}`, без `pattern`.
Но локальная Zod discovery schema требует **`^(vehicle|person)_[1-9][0-9]*$`**.
Ошибка: `extractions[1].statement_attributes.subject`, `invalid_format`.
JSON соответствует строковому типу wire contract, но не локальному ID constraint.
Это известный механизм текущего source, обнаруженный данным ответом; нет оснований
говорить об API/network outage или недостатке output tokens.

Discovery instructions также требуют vehicle/person IDs; raw ответ их не соблюдает.
Нужно разделять ошибку следования prompt и недостаточную строгость отправляемой
schema. Дополнительно closed subject vocabulary не содержит приложений/каналов,
а буквальный grammatical subject здесь именно технический канал. Это вопрос
семантики ontology contract; механическая замена на vehicle_1 не доказана верной.

Повторная обработка **того же сохранённого ответа**, без API, воспроизвела точную
ошибку и показала, что classification не вызывается.
[Диагноз](evidence/luna-medium-2026-10-19/failure-diagnosis.json).
Raw first sentence получает `person_1`; это не квалифицированный placement claim,
поскольку весь discovery отвергнут. Нельзя приписывать неисполненной classification
дополнительные semantic ошибки или переносить результат на неисполненный DEV032.

## Расход ресурсов: сравниваем одинаковые пять завершённых кейсов

| Метрика                          |      Low |   Medium |    Разница |
| -------------------------------- | -------: | -------: | ---------: |
| Завершённые pairs / requests     |   5 / 10 |   5 / 10 |          — |
| Input tokens                     |    7 975 |    7 975 |          0 |
| Output tokens, включая reasoning |    1 973 |    2 354 | **+19,3%** |
| В том числе reasoning tokens     |      744 |    1 045 | **+40,5%** |
| Cached input tokens              |    4 320 |    4 320 |          0 |
| Cache-write tokens               |    1 640 |    1 640 |          0 |
| Сумма case latency               | 32,607 s | 37,586 s | **+15,3%** |

Observed cache counts совпали; это не превращает latency delta в чистую оценку
effort — сеть и другие скрытые условия не контролируются. Monetary cost не
рассчитана из официального тарифа вместо тарифа CoreInfra.

**Вся Medium-серия с неуспешным discovery:**11 HTTP200 attempts, **44,213 s**,
**8 379 input / 2 890 output tokens**, включая1 484 reasoning tokens; unknown
usage0. Неуспешный discovery отдельно потребил404 input/536 output, включая439
reasoning tokens; он включён в totals, не вычтен из оплачиваемых попыток.
`billing` сообщает только `payer=developer`, без денежной суммы.

Сравнивать44,213s этой незавершённой серии с70,035s полного Low run как «Medium
быстрее» неправильно. Деноминатор ресурсов для quality tradeoff — те же5 pairs.

## Верификация и границы результата

- Успешные Medium результаты: offline replay **5/5**,10 archived mocked responses,
  real fetch forbidden. Все поля сравниваются, кроме новых statement UUID/latency.
- Проверены27 statement anchors и10 fragment offsets; failed raw quotes также точны.
- Неуспешный discovery отдельно воспроизведён offline одним сохранённым response;
  дополнительных live requests не было.
- Raw requests/responses, неуспешный ответ, неизменённые results и suffix statuses
  включены в архив вместе с baseline evidence, effective provider source и driver.
- Проверки hashes/ZIP/credentials описаны в [verification](evidence/luna-medium-2026-10-19/verification.json).
- Human correction sessions0; время/edits/clarifications/post-correction review —
  null. UI, полная assisted task, deployment, MLflow import и production default
  не проверялись/не менялись. Нового framework/test suite нет.

## Решение и следующий ход

Сравнение **неполное и inconclusive для выбора effort**. Из наблюдаемого: Medium
не исправил payer-scope, дал одно полезное уточнение про другой автомобиль,
потребовал больше reasoning/output tokens и времени на matched cases, а на DEV017
ответ не прошёл локальный контракт. Ни «Medium победил», ни «Medium хуже вообще»
этот опыт не доказывает.

**Следующий ход — offline согласовать meaning `subject` и выровнять отправляемую
JSON Schema с локальной validation**, добавив точный saved-response regression.
После узкого исправления отдельно согласовать новый запуск; зафиксировать, что
сравнение уже относится к новой версии контракта, и не смешивать его с этим arm.
Не повышать effort до high и не добавлять retries для исправления semantic/schema
ошибки под видом сетевой устойчивости.

## Evidence

- [Observations и matched metrics](evidence/luna-medium-2026-10-19/observations.json).
- [Полный paired candidate review](evidence/luna-medium-2026-10-19/comparison.json).
- [Execution authority](evidence/luna-medium-2026-10-19/authority.json),
  [подготовка](evidence/luna-medium-2026-10-19/README.md),
  [offline control](evidence/luna-medium-2026-10-19/preparation.json).
- [Replay](evidence/luna-medium-2026-10-19/replay.json),
  [failure diagnosis](evidence/luna-medium-2026-10-19/failure-diagnosis.json),
  [verification](evidence/luna-medium-2026-10-19/verification.json),
  [архив](evidence/luna-medium-2026-10-19/evidence.zip).
