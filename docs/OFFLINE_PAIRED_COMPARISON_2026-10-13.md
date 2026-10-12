# Offline paired comparison: выполненные сравнения

Дата: 2026-10-13 (Europe/Moscow). Задача: [#77](https://github.com/SoundBlaster/NormLab/issues/77).
Исходная база: `cbcf07f639de8cd63d701196aff5308a66fe7eaf` (#85).
[CLI/contract](OFFLINE_PAIRED_COMPARISON_V1.md).

## Результат

Выполнены **9 offline comparisons**. Portable запуск вне repository дал
**побайтово одинаковый JSON** для S1.3 synthetic variant comparison.
Production scorers, fixtures и source pins не изменялись.

Это демонстрация comparison infrastructure на сохранённых fixture evidence,
а не сравнение качества Jev и Luna или evidence улучшения модели.

| Сценарий                                          | Matched | Evaluated | Not evaluated | Incompatible | Baseline only | Candidate only | Regressions / rescues                   |
| ------------------------------------------------- | ------: | --------: | ------------: | -----------: | ------------: | -------------: | --------------------------------------- |
| S1.3 self                                         |     453 |        13 |           440 |            0 |             0 |              0 | 0 / 0                                   |
| S1.3 synthetic variant                            |     453 |        13 |           440 |            0 |             0 |              0 | 1 / 1                                   |
| Classification self, strict                       |       3 |         0 |             3 |            0 |             0 |              0 | Not evaluated                           |
| Classification self, diagnostic                   |       3 |         2 |             1 |            0 |             0 |              0 | 0 / 0                                   |
| Labeled → unlabeled, diagnostic                   |       3 |         0 |             3 |            0 |             0 |              0 | Not evaluated                           |
| Classification subset/provider change, undeclared |       2 |         0 |             0 |            2 |             1 |              0 | Not evaluated                           |
| Тот же subset, `--vary provider`                  |       2 |         2 |             0 |            0 |             1 |              0 | 0 / 0                                   |
| Предыдущая пара в обратном порядке                |       2 |         2 |             0 |            0 |             0 |              1 | 0 / 0                                   |
| Classification → S1.3                             |       0 |         0 |             0 |            0 |             3 |            453 | Not evaluated; global incompatibilities |

У S1.3 все 453 planned rows остаются в отчёте: 13 `completed`, 1 `deadline`,
3 `invalid-schema`, 434 `not-dispatched`, 2 `transport-failed` с каждой стороны.
Comparison не скрывает 440 неоценённых пар за denominator 13.

У classification strict mode отказался считать quality delta без exact context.
Diagnostic mode явно включён только по logical inputs. Одна failed task остаётся
not-evaluated; paired completed selected-probe pass равен 1/2 с каждой стороны.
Это не 50% case-level accuracy: fixture содержит один case и три legacy records.

## Почему aggregate delta недостаточно

Для synthetic variant вручную изменены **две разные** completed fixture predictions,
без изменения plan, reference, source/task contexts или statuses:

| Job       | Question | Expected | Baseline p_yes | Variant p_yes | Transition |
| --------- | -------- | -------- | -------------: | ------------: | ---------- |
| S13-1-046 | overall  | yes      |           0.95 |           0.0 | regression |
| S13-1-091 | overall  | no       |           0.95 |           0.0 | rescue     |

Selected-reference task agreement остался **9 → 9 / 13**, delta 0.
Per-row comparison показал 1 regression, 1 rescue и 11 unchanged pairs.
Это иллюстрирует пользу paired report: сводное среднее скрывает взаимно
компенсирующие изменения. Изменения synthetic, вывод о моделях отсутствует.

Variant получен копированием `mock-capture.json`, заменой указанных двух
`answers.overall.p_yes` и новым export через frozen S1.3 adapter.
Исходные files в repository не менялись.

Subset получен копированием classification fixture в scratch directory: оставлены
R001/R002, `provider.requestedModel` установлен в `synthetic-offline-variant`;
обновлены manifest byte digest и label expectations coverage. Cases, inputs,
parent, definitions, budget и native scorer сохранены. Без `--vary provider`
две совпавшие task исключены с `undeclared-provider-change`; R003 виден как
baseline-only. В обратном направлении он candidate-only.

## Изоляция и artifacts

Сравнения запускались с `-B -S`, минимальным environment без credentials и audit
guard из [offline verification suite](../evaluation/test_offline_bundle.py).
Guard запрещает `socket.*`, вложенный subprocess dispatch и перечисленные
provider/HTTP SDK imports. Scorers/model calls comparison не выполняет.

Для portable запуска скопированы только comparator и пять reader modules в
отдельный каталог без repository fixtures, SDK и legacy scorers. Входами служили
absolute bundle paths; JSON совпал побайтово с repository comparison.

Локальные raw reports: `.artifacts/paired-comparison-20261013/`.
Каждый output содержит полный JSON и Markdown. Это scratch evidence, не public
dataset или автоматически публикуемые raw bundles. Report содержит source
bundle digests и IDs, policy/code digests, per-row reasons и arm/family slices.

## Ограничения и следующий шаг

- Новые unit tests не добавлялись; evidence здесь — выполненные CLI comparisons,
  portable byte comparison и static checks. Existing export/verify tests #85
  не заменяют regression suite нового comparator.
- CLI умеет compare/export; отдельный reader/verification schema для imported
  comparison report ещё не реализован. Для проверки результата нужно повторить
  comparison из двух original bundles.
- Dataset/context/scorer/reference mismatches исключаются; автоматического
  semantic alignment разных protocols нет.
- Model quality, actual live requests, execution independence и confidence
  intervals здесь не оценивались. Исходные candidate labels не human gold.

Следующий ход — review comparison contract и отдельная regression coverage для
его policies; далее Stage 1 attempts/retries adapter и MLflow projection в #77.
