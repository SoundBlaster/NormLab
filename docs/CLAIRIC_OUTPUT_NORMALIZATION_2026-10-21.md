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

Текущий набор правил `quote-boundaries/v4`: numeric-unit suffix guard и
отмена общего запрета вложенности в source по уточнению пользователя.
ASCII остаётся explicit opt-in. Исторические v1/v2/v3 и evidence сохранены ниже:

| Rule ID                          | Delimiters | Действие                                                                                                               |
| -------------------------------- | ---------- | ---------------------------------------------------------------------------------------------------------------------- |
| `single-trailing-guillemet/v1`   | `«…»`      | Удалить ровно одну подтверждённую trailing `»` из derived span                                                         |
| `single-trailing-ascii-quote/v1` | `"…"`      | Только explicit opt-in после независимого подтверждения quotation context; numeric-unit guard недостаточен сам по себе |

Правила — альтернативы для одного преобразования, не бесконтрольный цикл
trimming. Enabled rule IDs передаются явно или используются versioned defaults;
неизвестный ID/target — configuration error. В default enabled только guillemet
rule. ASCII ending без explicit opt-in даёт `review` и не имеет derived value.
Включать его автоматически по наличию двух `"` нельзя: это снова активирует
обнаруженную неоднозначность unit/quote. `ALL_RULE_IDS` — явный opt-in, а не
автоматическое доказательство контекста. Enabled IDs записываются в result.
Новый тип коррекции требует
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
4. Выбранный тип delimiters образует balanced, unescaped пары; нужная пара
   совпадает с `start-1` и `end-1`. Вложенность в source разрешена: `«outer «x»»`
   и `«outer "x"»` не блокируют извлечение `x`. Пары другого типа не проверяются.
   При неоднозначном pairing одинаковых ASCII marks остаётся review, например
   `"outer «middle "x"»"`. Это ограничение parser, не общий запрет вложенности.
5. Content не пуст/whitespace-only и не содержит других поддержанных quote marks.
   Существующая проверка numeric prefix перед предполагаемой opening ASCII quote
   сохранена, чтобы не принять `12" and 24"` за цитату.
6. Если raw оканчивается decimal digit + `"`, `'`, `′` или `″` (между ними
   разрешён whitespace), символ сохраняется и возвращается
   `review: possible_numeric_unit_suffix`. Например: `12"`, `5'`, `55°45'30"`,
   `12″`, `5′`, `12.5"`, `−12,5"`. Проверка действует до opt-in/correction и
   не решает, дюймы это, футы, угловые минуты или секунды. `"12"` с raw `12"`
   тоже требует review; смысл не угадывается. Отдельного trimming rule для
   apostrophe/primes нет. Числа словами этот guard не распознаёт, поэтому
   ASCII default restriction остаётся.

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

При первом v1-прогоне **43 tests прошли на Python3.14.8:**21 существующий smoke test плюс22 для
normalization, guards и capture replay. Новый файл
[test_clairic_normalization.py](../scripts/test_clairic_normalization.py) покрывает
одиночный closer, one-character content, full quote, whole target, inches,
nested/mixed/unbalanced/escaped quotes, whitespace, отключение rules, invalid
coordinates/source mismatch, повторные вхождения, Unicode/negation и idempotence.
Existing CI job расширяет pattern до `test_clairic*.py`; сеть тестам не нужна.

### Исторический v1: post-hoc replay известных captures

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

## Новые safety probes: обнаруженный дефект и v2 default

По поручению «Проверяй» до запуска frozen36 новых synthetic examples:
[fixture](../fixtures/providers/quote-rules-new-cases-v1.json), commit `ded34d5`.
12 positive cases требуют точного применения правила;24 must-not-apply cases
проверяют названия/литералы, digit/word inches, nested/mixed/escaped/unbalanced
quotes, пустые строки, координаты и другие quotation styles. Сценарии написаны
с пониманием v1; это не blind gold, не независимые события и не production rate.
Ожидания после прогона не менялись.

Первый запуск **v1 дал3 false corrections** — N06/N07/N08: два значения дюймов,
записанные словами, превращались в мнимую ASCII quotation. Например:
`двенадцать" и двадцать четыре"`. Удалять финальную `"` здесь нельзя.
Numeric-prefix guard не распознаёт записанное словами измерение. Распознавание
произвольных слов/контекста не добавлено в generic normalizer.

Вместо языкового эвристического парсера v2 отключает ASCII correction в default;
он требует независимого решения caller о quotation context и explicit rule opt-in.
Это **ограничение области автоматизации**, а не устранение semantic ambiguity
при принудительном включении ASCII rule. Сама ASCII transformation остаётся v1.

| Метрика на frozen36                          | v1 defaults | v2 defaults                 |
| -------------------------------------------- | ----------- | --------------------------- |
| Правильные transformations среди12 positives | 12          | 8                           |
| False corrections среди24 must-not-apply     | **3**       | **0**                       |
| Positive abstentions                         | 0           | **4 ASCII quotes → review** |
| Exact action/value expectations              | 33/36       | **32/36**                   |

Четыре несовпавших positive expectations не переименованы в успех: результат
v2 менее полный, зато в этом наборе не портит literal/unit examples. Отсутствие
новых false corrections в36 авторских probes не гарантирует безопасность на
произвольном тексте; default guillemet rule тоже ограничен своей грамматикой.

Evidence:
[baseline v1](evidence/quote-rules-new-cases-baseline-v1-2026-10-21.json),
[default v2](evidence/quote-rules-new-cases-default-v2-2026-10-21.json),
[v2 replay: defaults и explicit known-quotation mode](evidence/clairic-quote-normalization-default-v2-2026-10-21.json).
Historical v1 module digest проверен против commit `06e663f`; frozen fixture
digest и три исходных failures проверяются regression test.

В v2 на известных captures default исправляет шесть guillemet variants до6/6,
а два ASCII variants оставляет с raw2/6 и четырьмя reviews. Explicit ASCII mode
на этих заведомо quotation fixtures воспроизводит6/6, но не подтверждает безопасное
включение на иных inputs. Historical raw/model scores и captures не изменены.

**47 offline tests прошли** на Python3.14.8, включая новые safety probes и
preserved-failure checks; Ruff/Prettier,JSON,links/digests проверены отдельно от
CI. Новых model calls, runtime integration или deployment не было.

## Review fix: cross-delimiter enclosure, v3

P2 [discussion4330399700](https://github.com/SoundBlaster/NormLab/pull/171#discussion_r4330399700)
подтвердился на head `3566d66`: при explicit ASCII mode внутри `«outer "x"»`
внутренняя ASCII quote ошибочно нормализовалась; inverse `"outer «x»"` также
обходил запрет mixed/nested конструкции, в том числе в default guillemet mode.

v3 после проверки собственной пары проверяет пары **обоих поддержанных типов**.
Любое пересечение/enclosure с другой парой или неразрешимая структура другого
типа даёт review без derived span. Disjoint flat pairs остаются допустимыми.
ASCII default policy не расширена; её semantic ambiguity не считается решённой.

[Review evidence](evidence/quote-normalization-cross-delimiter-review-2026-10-21.json)
содержит source digest и targeted examples. **51 offline test прошёл**, включая
оба направления nesting в default/explicit modes, deeper nesting, disjoint
positive controls и неоднозначную внешнюю структуру. На frozen36 старые метрики
остались32/36,0 false corrections и4 positive abstentions. v1/v2 evidence и
provider captures не переписаны. Новых API calls и hosted integration нет.
Новый CI после push считается отдельно; прежний head был6/6 SUCCESS.

## Уточнение пользовательского контракта: v4

После v3 пользователь уточнил: правило относится к одной непарной кавычке
**в извлечённой строке**, а не к отсутствию вложенности во всём source.
Cross-delimiter ban был дополнительным ограничением реализации, а не исходным
требованием. v4 снимает этот ban, разрешает balanced guillemet nesting и добавляет
отдельное исключение для numeric unit suffix. Raw/span/source guards сохранены.

[Новый offline report](evidence/quote-normalization-v4-2026-10-21.json)
разделяет targeted checks нового контракта и replay старого fixture.
На неизменённом frozen36 scorer выдаёт **31/36**, один `false_correction` N09
и четыре ASCII abstentions: N09 требовал запретить `«outer «x»»`, теперь этот
конкретный запрет снят по решению пользователя. Это несовпадение со старым
контрактом явно сохранено, не исправлено переписыванием labels. Оно не является
измеренной частотой ошибок нового контракта. Предыдущие 32/36 относятся к v2/v3.

**52 offline tests прошли** на Python3.14.8, включая numeric suffix/default/explicit
modes, Unicode digits, source nesting, ambiguous pairing и старые capture replay.
Новых API calls, runtime integration, model quality claims или deployment нет.

## Дальнейший gate

Перед интеграцией проверить rules на новых строках с literal/unit/escaped/nested
quotes и отдельно оценить false corrections/abstentions. Принимать решение о
включении policy в application adapter отдельно; reusable extractor client
продолжает возвращать исходное evidence. Hosted application не изменено.
