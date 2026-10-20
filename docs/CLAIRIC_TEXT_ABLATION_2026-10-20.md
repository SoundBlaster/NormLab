# Clairic: Unicode и кавычки, мини-абляция 2×2

Дата: 2026-10-20. Ledger: [#70](https://github.com/SoundBlaster/NormLab/issues/70).
Поручение: проверить гипотезу пользователя, что модель требует очистки текста
от непонятных символов после [RU smoke](CLAIRIC_RU_UNICODE_SMOKE_2026-10-20.md).

## Frozen protocol до inference

[Plan/fixtures](../fixtures/providers/clairic-text-ablation-v1.json): четыре
условия, те же шесть полей и **байт-в-байт одинаковые инструкции**.

| Порядок | Case                     | Emoji / combining mark | Кавычки |
| ------- | ------------------------ | ---------------------- | ------- |
| 1       | `ablation-original`      | Сохранены              | `«…»`   |
| 2       | `ablation-unicode-clean` | Удалены                | `«…»`   |
| 3       | `ablation-ascii-quotes`  | Сохранены              | `"…"`   |
| 4       | `ablation-both`          | Удалены                | `"…"`   |

Точные преобразования: удалить только начальный U+1F642 с последующим пробелом
и U+0301 из marker; отдельно заменить U+00AB/U+00BB на U+0022. Удаление ударения
**не является NFC normalization**. Оно меняет marker, поэтому expectation этого
поля меняется вместе с input. Остальные ожидаемые слова, отрицание, имена и время
не меняются. Оригинальная fixture/исторический capture остаются неизменными.

Свежий original — текущий контроль, предыдущий live capture не подставляется
вместо него. Unicode factor объединяет две замены и не отделяет вклад emoji
от combining mark. У каждого условия только одно наблюдение, fixed order;
случайность/порядок/доступность provider не контролируются полностью.

### Caps и stopping rule

Максимум **4 HTTP attempts**, по одному на условие;0 retries/fallback calls.
Официальный Workers AI endpoint/model clairic,30s socket timeout и1MiB response
bound на call. При HTTP/network/protocol failure оставшиеся calls остановить.
Semantic mismatch не останавливает остальные условия. Credential в памяти;
не публиковать account/token. Provider usage/passes считать как возвращены;
фактический денежный лимит аккаунта этим скриптом не устанавливается.

### Scoring до inference

- Exact typed values: шесть checks, `null` отдельно от отсутствующего поля/guess.
- Exact expected occurrences: пять non-null spans по frozen annotations каждого
  transformed input. Нельзя сравнивать их с offsets оригинального текста.
- Для этой абляции достаточно одного или нескольких общих candidate conventions
  на всех полях: code points / UTF16 / UTF8, end-exclusive. После удаления emoji
  code points и UTF16 могут не различаться; это не ошибка модели. Не объявлять
  неоднозначные единицы установленными. Старый RU scorer сохраняет свою policy.
- Overall pass требует exact values, совместимых exact expected spans и
  `truncated=false`. Фактические outputs/quotes не trim-ить перед scoring.
- Отдельный описательный diagnostic: соответствует ли каждый actual returned
  value source slice по его provider span. Он не исправляет frozen score.
- Go/no-go: сравнить, исчезает ли лишняя closing quote в зависимости от факторов.
  Один sample/cell может дать лишь рабочую гипотезу; production preprocessing
  и причинность/статзначимость не объявляются доказанными.

## Запуск

```bash
python3 scripts/clairic_smoke.py --case ablation-original
# Тот же CLI --live для каждого из четырёх case по frozen order/caps.
```

До вызовов закрепить script, fixtures, expectations и этот protocol в Git;
проверить offline controls, anchors, старый replay и форматирование.

## Результат

Protocol, fixtures и scorer закреплены в `d523d89` до inference; fixture SHA256:
`c63a40d47b054975cd775e24e0eaf47a619bb3ec8e9f983a81af620fc33c5447`.
До вызовов прошли15 offline tests и четыре CLI dry-runs; ожидания не отправлялись
provider и не менялись после ответов.

| Case          | Exact values | Exact expected spans | Лишний символ | Time / input tokens |
| ------------- | ------------ | -------------------- | ------------- | ------------------- |
| Original      | 2/6          | 1/5                  | `»` в4 полях  | 1,114s /1381        |
| Unicode clean | 2/6          | 1/5                  | `»` в4 полях  | 1,092s /1369        |
| ASCII quotes  | 2/6          | 1/5                  | `"` в4 полях  | 0,941s /1381        |
| Both          | 2/6          | 1/5                  | `"` в4 полях  | 1,055s /1369        |

Все4 HTTP200, model clairic, truncated=false; общий pass=false во всех условиях.
Всего5500 input tokens,0 output,24 provider passes;4 HTTP attempts,0 retries.
Фактическое списание аккаунта не проверено. Во всех условиях совпали время Виктора
и null для отсутствующей квитанции; остальные4 поля захватили closing quote.

Отдельный source diagnostic: actual returned values соответствуют их slices
при code-point/end-exclusive offsets на5/5 non-null полях каждого input.
Это не отменяет frozen failures и не устанавливает общий provider contract.

Sanitized script captures:
[original](evidence/clairic-ablation-original-2026-10-20.json),
[Unicode clean](evidence/clairic-ablation-unicode-clean-2026-10-20.json),
[ASCII quotes](evidence/clairic-ablation-ascii-quotes-2026-10-20.json),
[both](evidence/clairic-ablation-both-2026-10-20.json),
[summary/derived diagnostics](evidence/clairic-text-ablation-summary-2026-10-20.json).
Это не raw HTTP archives; credentials/account из evidence исключены.

### Интерпретация

На этом фиксированном примере удаление emoji/combining mark и замена вида
кавычек **не улучшили** exact extraction. Ошибка перенеслась с `»` на `"`.
Гипотеза, что здесь достаточно очистить «непонятные модели символы», поддержки
не получила. Это не доказывает отсутствие пользы любого preprocessing на других
текстах и не оценивает поведение без кавычек вообще.

Рабочая следующая гипотеза — выбор правой границы текстового span и выполнение
инструкции «без кавычек». Механизм ошибки (включая возможную tokenizer/decoder
granularity) не установлен: output сам по себе его не доказывает. Не включать
автоматическое удаление символов или trimming ответа на основании этой серии.
Следующий отдельный probe может сравнить точное определение запрашиваемого span
(цитата целиком / содержимое кавычек), с новыми fixed expectations и caps.

Дополнительные inference calls не выполнялись и автоматически не планируются.
После capture все16 offline tests прошли, включая replay четырёх зафиксированных
failures; Ruff lint/format, targeted Prettier, JSON/links и credential exclusion
проверены локально. Repository CI после push считается отдельно.

## Граница возможного внедрения

Даже при улучшении нельзя просто удалить символы из пользовательской фабулы и
считать offsets привязанными к оригиналу. Для будущего preprocessing нужен
отдельный derived text с provenance, точное отображение диапазонов обратно
на original и явное сохранение непредставимых/неоднозначных привязок. Удаление
символов может менять смысл; разбор исходного текста остаётся доступным.
Здесь такой mapper и production cleaning не реализуются.

## Дополнение: sentence line breaks — frozen protocol

Поручение пользователя: «Можно ещё разбить текст на строки по предложениям.
Переносами». Это отдельная пара условий, не замена результатов 2×2 выше.
Fixture: [clairic-linebreak-ablation-v1.json](../fixtures/providers/clairic-linebreak-ablation-v1.json).

Варианты: `linebreak-original` и `linebreak-sentences`. Во втором только четыре
пробела после sentence-ending `.` заменяются на LF. Для этой короткой fixture
границы заданы вручную; это не универсальный sentence splitter. Кавычки,
отрицание, emoji и U+0301 остаются. Field instructions, expectations и все span
indices побайтно одинаковы: SPACE и LF занимают по одной единице в рассматриваемых
coordinate systems. Только исходные source strings и их hashes различаются.

```text
🙂 Заметка «кафе́».
В 09:00 Анна сказала: «Я не оплачивала парковку».
В 10:00 Борис сказал: «Я оплатил парковку».
В 11:00 Виктор сказал: «Я оплатил парковку».
Номер квитанции не указан.
```

До inference закрепить fixture/protocol/scorer commit и SHA256. Новый original
запускается первым, затем sentences: max2 HTTP attempts, один на условие,
0 retries,30s socket timeout,1MiB response bound. Operational/protocol failure
останавливает пару; semantic mismatch не останавливает второе условие.
Те же six-value/five-span критерии, truncated=false, без trimming и передачи
expectations provider. Для этой пары сохраняется unique-coordinate criterion,
так как emoji остаётся и различимость code points/UTF16 не исчезает.

После ответов сравнить exact values/anchors, отдельно source consistency,
latency/usage и лишние delimiters. Один sample/condition, fixed order: результат
не доказывает причинность, general RU accuracy или пользу segmentation вообще.
Контроль из предыдущей серии не подставляется вместо нового original.

### Результат переноса строк

Pending. Дополнительные calls за пределами этой пары не выполняются автоматически.
