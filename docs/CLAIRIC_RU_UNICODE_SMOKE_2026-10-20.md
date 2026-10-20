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

Pending: frozen protocol и offline checks должны предшествовать единственному
live-вызову. Качество RU/negation/binding или единицы offsets пока не заявляются.
