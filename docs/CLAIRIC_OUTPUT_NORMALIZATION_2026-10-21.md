# Output normalization: явные правила для границ цитат

Дата: 2026-10-21 MSK. Ledger: [#70](https://github.com/SoundBlaster/NormLab/issues/70).
Поручение пользователя: проверить rule-based приведение строк к норме; пример —
одна closing quote при длине строки больше одного символа.

## Реализованный scope

[text_span_normalization.py](../scripts/text_span_normalization.py) — небольшой
pure-function prototype в standard library. Не импортирует NormLab ontology,
Clairic SDK, Mellea, HTTP или prompts. Это отдельная явно вызываемая policy
потребителя; она не встроена в generic client, smoke scorer или hosted pipeline.
Источник и provider captures не изменяются. Новых API calls нет.

Набор правил `quote-boundaries/v1`:

| Rule ID                          | Delimiters | Действие                                                                |
| -------------------------------- | ---------- | ----------------------------------------------------------------------- |
| `single-trailing-guillemet/v1`   | `«…»`      | Удалить ровно одну подтверждённую trailing `»` из derived span          |
| `single-trailing-ascii-quote/v1` | `"…"`      | Аналогично для одного trailing `"`, с дополнительным numeric-unit guard |

Правила — альтернативы для одного преобразования, не бесконтрольный цикл
trimming. Enabled rule IDs передаются явно или используются versioned defaults;
неизвестный ID/target — configuration error. Новый тип коррекции требует
отдельного versioned rule и тестов. Иные знаки пунктуации не удаляются.

## Условия применения

Caller явно выбирает `target="inner_content"` и заранее установленную
`coordinate_system="code_points"`. Неизвестные единицы/UTF16/bytes не угадываются:
возвращается `review`, derived span отсутствует. Подтверждение единиц конкретного
provider остаётся обязанностью caller, наблюдение из smoke не становится default.

Для candidate ending delimiter должны одновременно выполняться проверки:

1. Valid integer bounds и точное `source[start:end] == raw.value`.
2. Длина raw value больше1, ровно одна closing quote, без opening quote в value.
3. Непосредственно перед raw start находится matching opening quote.
4. В source выбранные delimiters образуют flat, balanced, unescaped пары;
   нужная пара точно совпадает с `start-1` и `end-1`. Вложенные/непарные конструкции
   вызывают abstention; prototype намеренно не пытается их «восстановить».
5. Content не пуст/whitespace-only, не содержит других поддержанных quote marks.
   Для ASCII numeric prefix перед предполагаемой opening quote вызывает review:
   два измерения `12" and 24"` нельзя автоматически объявлять цитатой.

Тогда `derived.value = raw.value[:-1]`, `derived.start = raw.start`,
`derived.end = raw.end - 1`. Это source-preserving изменение диапазона: отрицания,
диакритика, пробелы внутри content и остальные знаки не переписываются.
Prototype не доказывает семантическую природу кавычек во всех возможных текстах;
его ограниченная грамматика сознательно отказывается от неоднозначных случаев.

Статусы:

- `applied` — одно правило применено, raw и derived доступны отдельно.
- `unchanged` — правило не подходит/выключено/target whole quote; derived равен raw.
- `review` — контекст или source/span не позволяют безопасно применить правило;
  derived отсутствует. Это технический finding, не human-review verdict.

Result содержит immutable raw/derived DTOs, source SHA256, coordinate system,
target, ruleset version, applied rule IDs, findings и supporting source quote span.
Confidence модели не переносится на derived value. Ни один статус не означает
подтверждение юридического факта, actor/episode binding или acceptance человеком.

## Проверка без inference

```bash
python3 -m unittest discover -s scripts -p 'test_clairic*.py'
```

**43 tests прошли на Python3.14.8:**21 существующий smoke test плюс22 для
normalization, guards и capture replay. Новый файл
[test_clairic_normalization.py](../scripts/test_clairic_normalization.py) покрывает
одиночный closer, one-character content, full quote, whole target, inches,
nested/mixed/unbalanced/escaped quotes, whitespace, отключение rules, invalid
coordinates/source mismatch, повторные вхождения, Unicode/negation и idempotence.
Existing CI job расширяет pattern до `test_clairic*.py`; сеть тестам не нужна.

### Post-hoc replay известных captures

[Сохранённый derived report](evidence/clairic-quote-normalization-replay-2026-10-21.json)
содержит rule source digest, hashes неизменённых captures и per-field raw/derived.

| Свойство                                        | Raw provider output | Derived по явным правилам |
| ----------------------------------------------- | ------------------- | ------------------------- |
| Exact values на каждом из8 variants             | 2/6                 | 6/6                       |
| Exact non-null expected spans на каждом variant | 1/5                 | 5/5                       |
| Правила на variant                              | Нет                 | 4 quoted fields           |
| Source text / capture files                     | Сохранены           | Не изменяются             |

Остальные поля: время проходит unchanged, `null` receipt остаётся null, guess
не используется. Target whole quote намеренно не включён в inner-content replay;
его raw fail не переписывается. Нормализация не выбирает другое повторное
вхождение: start сохраняется, поэтому ошибочный actor binding она не исправит.

Это **8 вариантов одного известного authored сюжета**, включая повторные captures
и input/prompt ablations; правило подобрано после наблюдения ошибки. Это не8
независимых дел, не blind evaluation, не general accuracy6/6 и не новый результат
модели. Raw scores2/6 остаются в исходных отчётах. Новый inference не проводился.

## Дальнейший gate

Перед интеграцией проверить rules на новых строках с literal/unit/escaped/nested
quotes и отдельно оценить false corrections/abstentions. Принимать решение о
включении policy в application adapter отдельно; reusable extractor client
продолжает возвращать исходное evidence. Hosted application не изменено.
