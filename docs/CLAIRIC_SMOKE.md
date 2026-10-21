# Clairic: один нейтральный smoke-запрос

Подготовительный скрипт: [scripts/clairic_smoke.py](../scripts/clairic_smoke.py).
Ledger: [#70](https://github.com/SoundBlaster/NormLab/issues/70).
Python 3.10+, только standard library, установка зависимостей не нужна.
Это exploratory smoke, а не реализация reusable package из
[proposal PR #167](https://github.com/SoundBlaster/NormLab/pull/167).

## Что отправляем и ожидаем

Одна короткая английская строка о нейтральном отчёте. Шесть полей в одном запросе:

| Поле             | Тип          | Ожидаемое значение                          |
| ---------------- | ------------ | ------------------------------------------- |
| `report_id`      | text         | `R-104`                                     |
| `report_date`    | date         | `2026-10-19`                                |
| `monthly_income` | number       | `5000`                                      |
| `monthly_rent`   | number       | `1500`                                      |
| `contacts`       | list of text | `Dana Ruiz`, `Priya Shah`, порядок не важен |
| `purchase_order` | text         | `null`: номер заказа не указан              |

`guess` не подменяет `value: null`. Отсутствие ответа не считается корректным null.
Числа сравниваются по значению, тип поля проверяется отдельно. Общий pass также
требует `truncated: false`. Confidence и spans выводятся как metadata; их
калибровка, coordinate system и общее качество extraction не проверяются.

## Запуск

Из корня NormLab посмотреть payload и expectations **без сети и credentials**:

```bash
python3 scripts/clairic_smoke.py
```

Для реального запроса нужны `CF_ACCOUNT_ID` и `CF_API_TOKEN` в окружении.
Account ID — 32 hex characters. Токен не передаётся аргументом CLI, не читается
из tracked config и не сохраняется скриптом. Можно ввести значения в текущем
zsh без записи их значений в shell history:

```zsh
read -r 'CF_ACCOUNT_ID?Cloudflare Account ID: '
read -rs 'CF_API_TOKEN?Cloudflare API Token: '; printf '\n'
export CF_ACCOUNT_ID CF_API_TOKEN
python3 scripts/clairic_smoke.py --live
unset CF_API_TOKEN CF_ACCOUNT_ID
```

Скрипт делает один HTTP attempt, без retries и redirects, с socket timeout 30 s и общим deadline 30 s
и ограничением ответа 1 MiB. `--live` может расходовать средства Cloudflare;
этот инструмент не устанавливает денежный лимит аккаунта. Использовать только
после согласования запуска и account budget. Provider может считать несколько
внутренних passes: usage выводится как получен, цена не вычисляется по догадке.

Результат — JSON в stdout: фактические/ожидаемые значения, pass каждого поля,
model, usage, HTTP status, CF-Ray и elapsed time. Никакие файлы скрипт не создаёт;
необработанный HTTP body не архивируется. Доступны Workers AI `result` envelope
и direct model response, показанный в model reference. Неподдержанный/ошибочный
ответ даёт protocol error, а не «поле не найдено».

Ошибки 401/403 отдельно указывают на auth/access, 429 — на quota/rate limit.
При network/TLS/timeout исход и usage могут остаться неизвестными; автоматического
повтора нет. Provider error body не печатается, чтобы не отражать секреты.

Exit codes: `0` — все шесть expectations совпали; `1` — mismatch/truncation;
`2` — config; `3` — HTTP/network; `4` — invalid/unsuccessful model response.

Успешный smoke подтвердит только доступ и эти конкретные значения. Проверка
русского языка, Unicode offsets, attribution и эпизодов — отдельный эксперимент.

## Live-результат — 2026-10-20

Один авторизованный запрос выполнен скриптом из commit `795cfbc` через официальный
Workers AI endpoint. Credential передан процессу в памяти; account/token в
публикуемый отчёт не включены. Повторов и дополнительных model calls не было.

| Показатель                            | Наблюдение                                             |
| ------------------------------------- | ------------------------------------------------------ |
| HTTP / script exit                    | `200` / `0`                                            |
| Фактическая model                     | `clairic`                                              |
| Совпадение фиксированных expectations | **6/6**, включая отсутствующий purchase order → `null` |
| Truncated                             | `false`                                                |
| Измеренное время запроса и разбора    | **1,082 s**, без времени ввода credential              |
| Usage                                 | **557 input**, **0 output**, **3 passes**              |
| Usage breakdown                       | 45 state tokens, 422 schema tokens, 0 image tokens     |
| CF-Ray                                | `a4d913e42d72e65d-DEN`                                 |

Сохранён [санитизированный JSON-отчёт](evidence/clairic-neutral-smoke-2026-10-20.json)
с фактическими ответами, metadata и checks. Это вывод smoke-скрипта, а не архив
исходного HTTP body/headers; полное независимое wire replay им не заявляется.
Числа usage приведены как вернул provider, breakdown не пересчитывается в total.
Фактическая сумма списания аккаунта не проверена.

Показательный ответ: `purchase_order.value = null`, но `guess = R-104`,
`confidence ≈ 0,9929`, `p_null ≈ 0,999998`. Высокая confidence в metadata не
отменяет null; diagnostic guess и его span не приняты как найденный номер заказа.

Вывод ограничен доступностью официального API и этими шестью английскими
полями одного нейтрального примера. Это не оценка общей accuracy, русского
языка, калибровки confidence или пригодности для NormLab. Следующий предлагаемый
шаг — зафиксировать короткий RU/Unicode/negation smoke с expectations и отдельным
лимитом запросов до его запуска.

Источники, проверены 2026-10-20:
[Clairic model/API reference](https://developers.cloudflare.com/workers-ai/models/clairic/),
[Workers AI REST API](https://developers.cloudflare.com/workers-ai/get-started/rest-api/).

## Review: total deadline

Socket timeout ограничивает отдельные операции, но не trickling response.
Теперь live CLI дополнительно использует POSIX ITIMER_REAL/SIGALRM вокруг
open/read/parse; timer и прежний handler восстанавливаются в finally.
Live mode вне main thread, без POSIX timer или при уже активном timer отклоняется
до запроса. Dry-run остаётся portable. Deadline interruption оставляет outcome/usage
unknown, не делает retry и не доказывает отмену серверного inference.
Offline test имитирует регулярные короткие чтения без HTTP и проверяет общий cap.
