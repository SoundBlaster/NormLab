# Clairic RU / negation / repeated spans / Unicode smoke

Дата: 2026-10-20. Ledger: [#70](https://github.com/SoundBlaster/NormLab/issues/70).
Разрешение пользователя: «Ок. Готовь и проверяй» после предложения русского smoke.
Это один authored development probe, не holdout, human gold или общий benchmark.

## До inference: frozen input и expectations

Fixture: [clairic-ru-unicode-v1.json](../fixtures/providers/clairic-ru-unicode-v1.json).
В provider request отправляются только `model`, `state`, `fields`; ожидания,
source annotations и SHA256 не передаются модели.

> 🙂 Заметка «кафе́». В 09:00 Анна сказала: «Я не оплачивала парковку». В 10:00 Борис сказал: «Я оплатил парковку». В 11:00 Виктор сказал: «Я оплатил парковку». Номер квитанции не указан.

В fixture после «кафе» находится U+0301; текст не нормализуется. Начальный emoji
отличает code points от UTF-16, кириллица — от UTF-8 bytes.

| Поле               | Ожидается                               | Code-point span, end-exclusive                   |
| ------------------ | --------------------------------------- | ------------------------------------------------ |
| `anna_statement`   | `Я не оплачивала парковку`              | `[42, 66]`                                       |
| `boris_statement`  | `Я оплатил парковку`, вхождение Бориса  | `[92, 110]`                                      |
| `viktor_statement` | `Я оплатил парковку`, вхождение Виктора | `[137, 155]`                                     |
| `unicode_marker`   | `кафе` + U+0301                         | `[11, 16]`                                       |
| `viktor_time`      | `11:00`                                 | `[115, 120]`                                     |
| `receipt_number`   | `null`                                  | Не требуется, diagnostic guess/span игнорируются |

## Protocol и caps

- Один HTTP attempt, шесть text fields в одном запросе, без retries, fallback
  или дополнительного binding call.30s socket timeout,1MiB response bound.
- Официальный Cloudflare Workers AI endpoint, requested model `clairic`;
  credentials в памяти процесса, без файлов и публикации.
- До запуска закрепить fixture и script commit. Отчёт сохраняет fixture SHA256.
- Проверить шесть типов/значений, `truncated=false`, каждый exact occurrence span.
- Сравнить spans с тремя заранее выбранными end-exclusive conventions:
  Unicode code points, UTF-16 code units, UTF-8 bytes. Один кандидат должен
  совпасть на всех пяти non-null полях. Разные conventions по полям, неверное
  повторное вхождение и другой `state_text` дают fail.
- Кандидат — диагностическое наблюдение на этой строке, не доказанный контракт
  координат provider. Не устанавливать production policy по этому smoke.
- Не исправлять ответы или offsets перед scoring. Отдельно показать совпадение
  значений и координат; не считать semantic binding успешным только по словам.
- При HTTP/network/protocol failure либо mismatch остановиться; новых calls
  автоматически не делать. Usage/latency и неизвестность списания сохраняются.

## Воспроизведение

```bash
python3 scripts/clairic_smoke.py --case ru-unicode
python3 -m unittest discover -s scripts -p 'test_clairic_smoke.py'
# После подготовки CF_ACCOUNT_ID / CF_API_TOKEN и согласования запуска:
python3 scripts/clairic_smoke.py --case ru-unicode --live
```

Первые две команды offline. Последняя может расходовать средства аккаунта;
число HTTP attempts не равно числу provider passes. Это отдельный вызов от
предыдущего [английского smoke](CLAIRIC_SMOKE.md).

## Результат

Fixture, scorer и protocol закреплены в `cf00f38` до inference.
Fixture SHA256: `9bf7081c17c7f9c07d9c4bef6a5db3e8926b28d171054d7d50c92937d743302f`.
До запуска прошли12 offline unit tests, CLI dry-run, Ruff и targeted Prettier.
Unit tests подключены к существующему CI job, без новых provider calls.

Один live HTTP attempt: **200**, модель `clairic`, `truncated=false`, **1,213 s**.
Usage: **1381 input /0 output tokens,6 passes**; breakdown71 state/955 schema/0 image.
CF-Ray: `a4d920e05994ba49-DEN`. Повторов и дополнительных model calls не было.

### Frozen scoring: fail

| Поле           | Фактически                  | Значение         | Точный ожидаемый span                |
| -------------- | --------------------------- | ---------------- | ------------------------------------ |
| Anna           | `Я не оплачивала парковку»` | fail: лишняя `»` | fail: `[42,67]` вместо `[42,66]`     |
| Boris          | `Я оплатил парковку»`       | fail: лишняя `»` | fail: `[92,111]` вместо `[92,110]`   |
| Viktor         | `Я оплатил парковку»`       | fail: лишняя `»` | fail: `[137,156]` вместо `[137,155]` |
| Marker         | `кафе́»`                     | fail: лишняя `»` | fail: `[11,17]` вместо `[11,16]`     |
| Viktor time    | `11:00`                     | pass             | pass: `[115,120]`                    |
| Receipt number | `null`                      | pass             | Не требуется                         |

Итог: **2/6 значений**, **1/5 frozen anchors**, общий `pass=false`, script exit1.
Это поля одного кейса, не шесть независимых кейсов. Условия и ожидания не менялись
после ответа; кавычки не удалялись ради улучшения score.

[Санитизированный live-отчёт](evidence/clairic-ru-unicode-smoke-2026-10-20.json)
содержит answers, frozen checks и usage. Это вывод скрипта, не raw HTTP archive.
Credentials и account ID не опубликованы; фактическое списание не проверено.

### Post-hoc diagnostic: source consistency

Отдельная offline-проверка сравнила каждый **фактически возвращённый value** с
исходным slice по provider span для тех же трёх candidate conventions.
[Результат](evidence/clairic-ru-unicode-source-diagnostic-2026-10-20.json):
**5/5 non-null spans совпадают с actual value при code points / end-exclusive**;
ни UTF-16, ни UTF-8 не совпали на всех полях. Исходный score остаётся fail.

Следовательно, наблюдаемая проблема здесь — захват соседней закрывающей кавычки,
а не обнаруженное рассогласование actual text с offsets. Отрицание и combining
mark сохранены в actual text. Борис и Виктор получили разные нужные starts92/137,
а время Виктора выделено верно. Это локальные наблюдения на одной синтетической
строке, не общая оценка actor/episode binding и не доказательство универсального
контракта координат Clairic.

Следующий предлагаемый шаг — отдельная проверка границ цитат на новых коротких
строках; не вводить автоматическое trimming или production offset policy на
основании этого результата. Повторный inference этим отчётом не запущен.

После capture добавлен offline replay-test: пересчёт checks и anchor diagnostics
из сохранённого ответа воспроизводит исходный fail и fixture digest. Все13 unit
tests прошли на Python3.14.8; Ruff lint/format, targeted Prettier, локальные ссылки,
JSON и исключение account/token из evidence проверены. Repository CI — отдельная
проверка после push; локальные результаты не объявляют его зелёным заранее.
