# Offline export/verify: runtime verification

Дата: 2026-10-13 (Europe/Moscow). Задача: [#77](https://github.com/SoundBlaster/NormLab/issues/77).
Проверяемая реализация: merge [#84](https://github.com/SoundBlaster/NormLab/pull/84),
commit `7a3acba9180b25d200fe3e31d0f07f3bad183640`.

## Результат

**16 tests прошли**, включая **49 отрицательных mutation-сценариев**.
Невалидные bundles отклонены; корректные exports, portable verify и positive controls приняты.
Изменений production reader/scorer для прохождения проверок не потребовалось.

Это runtime-проверка [offline contract](OFFLINE_ENVELOPE_V1.md), не измерение
semantic quality модели, независимости reference или юридической корректности.

## Воспроизведение и изоляция

Из корня репозитория, без установки dependencies:

```bash
python3 -B -S -m unittest discover -s evaluation -p 'test_offline_bundle.py' -v
```

[Suite](../evaluation/test_offline_bundle.py) использует только stdlib и временные каталоги.
Каждый CLI subprocess запускается с `-B -S`, минимальным environment без credentials
и audit hook, запрещающим `socket.*`, вложенный `subprocess.Popen` и импорты
перечисленных provider/HTTP SDK. Два control probes отдельно подтверждают отказ
при создании socket и импорте `openai`.

Portable verify запускается вне repository из копии только пяти reader modules,
без legacy scorers, repository fixtures и site-packages. Каждый из трёх bundles
проверяется этим reader. Export использует repository и исходные frozen scorers;
reader не выполняет сохранённый Python из bundle.

В CI добавлен тот же stdlib-only suite в job `Stage 1 dataset audit`.
Локальный результат и будущий CI outcome — отдельные evidence.

## Исходные bundles

| Проверка                                     | Classification с labels | Classification без labels | S1.3 fixture |
| -------------------------------------------- | ----------------------- | ------------------------- | ------------ |
| Export + verify                              | Pass                    | Pass                      | Pass         |
| Повторный export, побайтово одинаковый index | Pass                    | Pass                      | Pass         |
| Portable reader                              | Pass                    | Pass                      | Pass         |
| Planned tasks                                | 3                       | 3                         | 453          |
| Planned questions                            | null                    | null                      | 909          |
| Recorded outcomes                            | 3                       | 3                         | 19           |
| Known input/output tokens                    | 0 / 0                   | 0 / 0                     | 1600 / 160   |
| Unknown-usage outcomes                       | 3                       | 3                         | 3            |
| Inference calls этой offline операции        | 0                       | 0                         | 0            |

Classification сохраняет 2 `completed` и 1 `failed`. Без labels reference остаётся
null, `probePass` — null, `expectationsStatus` — `not_evaluated`. Run identity
совпадает с labeled view, score identity отличается. Отдельный export/verify
подтвердил manifest v2 и сохранение requested/returned model names с `/` и `:`.

S1.3 сохраняет 13 `completed`, 1 `deadline`, 3 `invalid-schema`,
434 `not-dispatched` и 2 `transport-failed`. Все 453 задачи остаются в denominator;
attempts/latency/cost остаются null. Fixture tokens не означают оплаченный inference.

Исходные classification manifest/captures сохранены побайтово. Повторная запись в
существующий output отклонена, существующий index не изменился и продолжил проходить verify.

## Coordinated mutations

Suite не ограничивается повреждением checksum. Для reference/report mutations
создаются новые content-addressed artifacts, обновляются bytes/hash refs,
reference identity, report binding и score identity. Старые artifacts могут
оставаться в inventory, но изменённый score view ссылается на новые bytes.

| Группа                                                                                                    | Сценариев | Результат        |
| --------------------------------------------------------------------------------------------------------- | --------: | ---------------- |
| Classification reference: два недопустимых статуса, schema, experiment digest, coverage                   |         5 | Все rejected     |
| S1.3 reference: status/schema/plan/coverage; human status без подходящих revision/evidence                |         9 | Все rejected     |
| S1.3 reference questions: missing, extra, invalid label                                                   |         3 | Все rejected     |
| Native report: counts, provenance/quality metadata, tokens, status/question counts, bool вместо integer   |        19 | Все rejected     |
| S1.3 arms: question counts/agreement, verdict/status summaries, false acceptance/rejection, D null policy |        10 | Все rejected     |
| Scored status: одновременно изменены native row, task status/score artifact и envelope counts             |         2 | Оба rejected     |
| Capture bytes без обновления hash                                                                         |         1 | Rejected         |
| **Итого отрицательных mutation-сценариев**                                                                |    **49** | **Все rejected** |

Native summaries проверяются отдельно от envelope counts: изменение report вместе
с его ref/score ID не позволяет заявить другие token totals, agreement или denominator.
Scored-status mutations сохраняют согласованность task/report/envelope status counts,
но отвергаются из-за противоречия original prediction.

Positive control: S1.3 test reference со статусом `human-adjudicated`, отдельной
revision и непустым textual evidence принят. Evidence явно помечен synthetic test
declaration; это не реальный human review и не human gold. Контроль подтверждает
schema-specific проверку, а не безусловный запрет этого статуса.

## Границы результата

- 16 tests и 49 mutations — coverage implementation contract, не 49 независимых
  реальных дел и не статистическая оценка качества pipeline.
- Guard запрещает сетевые операции проверяемых CLI subprocesses. Live providers,
  ключи, тарифы, deployment и фактическая transport history здесь не проверялись.
- Unsigned bundle не устанавливает автора или истинность evidence. Coordinated
  замена самих source artifacts с согласованными bindings остаётся вне authenticity guarantee.
- Reader не повторяет full classification parsing, S1.3 plan compilation,
  defect-location или candidate-stance derivation; ограничения #84 сохраняются.
- Cross-run paired comparison, Stage 1 retry adapter, execution/resume и MLflow
  import остаются незавершёнными частями #77.

Следующий implementation slice: portable paired comparison с compatibility checks,
явными unmatched/not-evaluated rows и denominator scopes.
