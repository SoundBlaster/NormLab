# Semantic profile: demo.reform-mitigation/v1

Статус: TypeScript producer и независимый Lean decision/comparison/property verifier реализованы. Все 384 snapshot/model combinations проверены kernel; общие relation theorems описаны в [REFORM_VERIFICATION.md](REFORM_VERIFICATION.md). [NL-405](COMPARISON_VERIFICATION.md) подтверждает equivalence A/B, свойства A/C, bound counterexample и signed receipt replay.

Источники: [синтетический текст](../fixtures/reform-v1/source.md), [контракты](CONTRACTS.md), [shared/reform-semantics.ts](../shared/reform-semantics.ts).

## Inputs и completion

Один snapshot содержит одну группу K1/K2, narrative и findings M/N/E. Основания ответственности и выбор группы находятся вне scope; narrative не преобразуется в findings автоматически.

`established` задаёт true, `refuted` — false. `unreviewed` и `not-established` сохраняют обе возможности. `not-established` не становится `refuted`.

Completion — совместимый завершённый вход `(group, M, N, E)` из D16. Порядок ветвей фиксирован: M, затем N, затем E; false перед true. `complete` требует terminal states всех трёх findings. Иначе результат `conditional`, даже если численные последствия всех completions совпадают.

Для полностью открытого snapshot доступны восемь branches одной группы. Ветви с одинаковыми последствиями сохраняются отдельно с их условиями. Findings, отличные от `unreviewed`, требуют мотивировки; это simulated review без предоставления судебных полномочий.

## Valid package

Для каждой группы пакет обязан содержать ровно одно подходящее baseline rule, одно scale-M, одно scale-N и одно exclusion-E. Rule IDs уникальны; group scopes не повторяются. Все правила обязательны и применяются не более одного раза.

Отсутствующее правило, два подходящих baseline или два масштабирующих правила одного trigger — ошибка пакета. Producer не выбирает первое правило среди конфликтующих. До применения проверяется поддержка пакета для всех 16 завершённых входов; нецелочисленный случай не удаляется из domain.

Правила могут быть отдельными для групп, как в A, или общими, как в B/C. Поведение выбирается operation и scope, не bundle/rule ID. Порядок arrays является частью artifact identity, но не приоритетом норм.

## Отношение последствий

Пусть `b(g)` — базовый срок группы, `f(g)` — базовый штраф, `m(g)` — multiplier M, `n(g)` — multiplier N. Тогда описание независимого отношения для завершённого x:

```text
eligible_N(x) = x.N and not x.E
factor_M(x)   = m(x.group), если x.M; иначе 1
factor_N(x)   = n(x.group), если eligible_N(x); иначе 1

Permissible_IR(x, y) требует:
    y.qualification = x.group
    y.prisonMonths  = b(x.group) * factor_M(x) * factor_N(x)
    y.fineAmount    = f(x.group)
    y.currency      = DEMO
```

Дополнительно ledger и steps должны удовлетворять обязательствам ниже. Независимое [Lean определение](../lean/Reform.lean) проверяет exact equations и подтверждает soundness/completeness принятого certificate. Свидетельства запуска kernel сохранены отдельно от этого описания.

В A/B multiplier M равен 2/3, в C — 1/2. Multiplier N равен 3/4 во всех моделях. Базы K1: 120 месяцев/200 000 DEMO; K2: 240 месяцев/400 000 DEMO. Изменение C ограничено M.

## Порядок и арифметика

1. Выбрать базу группы.
2. Определить exclusion для N.
3. Применить M, если оно установлено.
4. Применить N, если оно установлено и не исключено.

Scale использует BigInt multiplication и exact division. Каждая применённая стадия обязана дать целое число месяцев; дробные промежуточные значения отклоняются как `unsupported`. Rounding отсутствует. При действии M и N множители применяются последовательно, их уменьшения не складываются относительно базы.

Producer сохраняет step `{ruleId, beforeMonths, afterMonths}` каждого применённого scale. Штраф никогда не участвует в scale. Исключение E не отменяет M и не создаёт отдельного увеличения базы. Lean verifier независимо проверяет арифметику последствия и точный required list steps.

## Полный ledger

Для каждого rule модели имеется запись в каждой branch:

| Условие                                     | Статус                                          |
| ------------------------------------------- | ----------------------------------------------- |
| Группа вне scope rule                       | `inapplicable`                                  |
| Подходящий baseline                         | `applied`                                       |
| Scale trigger опровергнут                   | `inapplicable`                                  |
| Scale-M trigger установлен                  | `applied`                                       |
| Scale-N trigger установлен и E опровергнуто | `applied`                                       |
| Scale-N trigger установлен и E установлено  | `excluded`, ссылка на подходящее exclusion rule |
| Exclusion при N=true и E=true               | `applied`                                       |
| Exclusion в остальных завершённых случаях   | `inapplicable`                                  |

Сводный ledger совпадает с branch entry, если статус и `excludedBy` одинаковы во всех completions. В остальных случаях используется `unresolved` без `excludedBy`. Например, N открыто при установленном E даёт `inapplicable`/`excluded` в ветвях и `unresolved` в summary, сохраняя равные численные последствия.

`validateReformResultContext` проверяет completeness/order branches, полный набор rule IDs, exclusion references, отсутствие repeated transforms и согласованность summary. Это contextual checker формы и ссылок; допустимость чисел и смысл применения rules требуют независимого verifier.

## Доказательные обязательства

- Soundness: каждая producer branch удовлетворяет независимому `Permissible_IR`.
- Outcome completeness: представлены все допустимые outcomes каждого compatible completion.
- Mandatory-rule completeness: каждый обязательный rule в scope учтён с корректным статусом и основанием.
- Existence/uniqueness: у завершённого входа существует ровно одно полное допустимое последствие.
- Comparison: equivalence A/B и конкретные ограничения A/C относятся к указанному D16 и mapping.
- Binding: statement конструируется из доверенного query/snapshot/bundles; доказательство другого утверждения не принимается.

TypeScript tests проверяют конкретный fixture и повреждения структуры. Lean integration checks подтверждают decision obligations профиля на A/B/C и общие теоремы relation; M0 проверяется отдельно. Источники свидетельств — [contract report](CONTRACT_VERIFICATION.md), [Lean decision report](REFORM_VERIFICATION.md) и [comparison/receipt report](COMPARISON_VERIFICATION.md). HTTP/UI integration v2 остаётся NL-502.
