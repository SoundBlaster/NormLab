# Evaluation framework v1: завершающий pilot

Дата: 2026-10-18. Ledger: [#77](https://github.com/SoundBlaster/NormLab/issues/77).
Исполняемый код: `fc1f91cb64d84f9b8ea105c9d443428a6761b73c`, после
[PR #143](https://github.com/SoundBlaster/NormLab/pull/143).

**Инфраструктурный этап v1 завершён.** Реальный ответ прошёл путь inference →
archive → selected-reference score → local MLflow → повторная offline-проверка.
Новых функций для завершения этого этапа не требуется. Следующий результат —
исследование ошибок разбора текста, а не расширение harness.

## Условия и фактическое выполнение

- Frozen Stage1 pilot: 36 задач, общий исходный план сохранён полностью.
  Plan digest: `e113c12ecd7bc8cdcf5d1d608e811158e62a14699e7057a81c51a7a44d55846a`.
- Выбрана первая задача `J0001`, `C002/R003`, Jev через
  `https://hub.coreinfra.ai/typesafe/api/v1/systemone`, модель `jev-1.13.0`.
- Пользователь подтвердил внешний лимит **$4**. Permit каждого запуска ограничен
  одним attempt, одним вопросом, input reservation 4096 / output reservation 256.
  Dollar limit — заявление оператора о настройке поставщика; локальный runner его
  не устанавливает. Output reservation для Jev не является wire token limit.
- Оба запуска использовали native `run-once`, без внутренних retries. Исходные
  intent, claims и outcomes не переписывались.
- Producer: существующий Docker image `python:3.12-slim-bookworm`, Python 3.12.13,
  настоящий Linux `CLOCK_BOOTTIME` и VM boot ID, persistent container machine ID.
  Этот ID создан при подготовке контейнера и сохранён отдельно; clock и transport
  не подменялись. Image digest есть в evidence packet.
- Reader/registry: Python 3.13.15, MLflow 3.16.1. Отличие reader runtime сохраняется
  как `readerRuntimePinsMatched=false`, а не скрывается.

### Отклонение от плана: ошибка настройки Docker

Первоначальный контейнер был создан с сетью `none`. Попытка добавить `bridge`
была отвергнута Docker; оператор ошибочно продолжил вызов runner. Результат —
`ConnectError`, без ответа провайдера. Это ошибка подготовки данного pilot,
не установленный дефект CoreInfra или framework.

Этот запуск сохранён целиком. Перед дополнительной попыткой записано изменение
протокола: отключить `none`, подключить `bridge`, проверить DNS без inference,
затем создать отдельный intent с новым UUID и fresh output. Таким образом,
**всего были два native dispatch attempts, один ответ провайдера**.
Первый outcome не превращён в нулевой расход: его usage остаётся неизвестным.

| Показатель                  | Setup failure                          | Реальный запрос                        |
| --------------------------- | -------------------------------------- | -------------------------------------- |
| Run ID                      | `50c77285-0dab-4d13-9672-e301e39a05aa` | `e9931db2-2c05-4605-8d2f-3c5cf1b23f1e` |
| Attempt outcome             | `transport-failed`                     | `completed`                            |
| Observed dispatches         | 0                                      | 1                                      |
| Unknown dispatch attempts   | 1                                      | 0                                      |
| Known input / output tokens | 0 / 0                                  | 1872 / 43                              |
| Unknown usage attempts      | 1                                      | 0                                      |
| Остальные задачи            | 35 `not-dispatched`                    | 35 `not-dispatched`                    |
| Selected questions scored   | 0 / 1                                  | 1 / 1                                  |
| Candidate agreement         | null                                   | 0 / 1                                  |
| Actual dollar cost          | null                                   | null                                   |

Request ID успешного ответа: `req_01a14e4575b87a109e5db33ef764b188`.
Оба запуска остановлены с `operator-stop`; это partial captures, а не выполненная
матрица 36 задач. Prediction seal остаётся `unsealed`. После ответа контейнер
снова изолирован от сети. Никаких последующих provider requests не выполнялось.

## Проверка archive, score и MLflow

Оба исхода экспортированы в самостоятельные archives v2. В активном offline guard
до imports удалены переменные API keys; запрещены socket resolution/connect/bind.
Контрольный `getaddrinfo(example.invalid)` подтвердил, что guard действует.
Дополнительно библиотека попыталась сделать `bind(::1, 0)`; эта операция тоже
отклонена. Успешных network operations — **0**.

Проверены:

1. Archive inventory, producer pins, исходные request/context bytes и native replay.
2. Повторный selected-reference score с точным совпадением сохранённого JSON.
3. Self-comparison и её повторная проверка: сохранены partial denominators.
   Это контроль воспроизводимости одного запуска, не независимый baseline и
   не сравнение качества моделей.
4. Повторные actual local MLflow imports обоих captures и scores: те же run IDs,
   `alreadyImported=true`, по четыре registry records на capture, всего восемь.
5. **130 metric histories** (64 для failure, 66 для completed capture): в каждой
   ровно одна запись; повторный import не дублировал metrics.
6. Raw archive и score, скопированные в MLflow artifacts, повторно прочитаны и
   проверены. Для этого не использовался оригинальный live output.
7. Проверка отсутствия действующего ключа CoreInfra в raw captures и archives.

Финальный pass использовал production readers/scorer/importer без изменения их
исходников. Исправлялась только локальная orchestration проверки: порядок
аргументов `verify_comparison` и слишком строгое ожидание полного отсутствия
попыток socket operations. Запрет успешных network operations оставался активен.
Это не новые regression tests и не повтор полного CI suite.

## Содержательный результат

Source: «Я не оплатил парковку». Candidate утверждает actual payment от narrator.
Зафиксированный до inference reference — `incompatible`, статус
`candidate-not-independent`. Jev вернул **`compatible`**.

Это конкретный пример false acceptance отрицания под данным prompt/context.
Он показывает, что infrastructure сохраняет и воспроизводит ошибочный ответ,
а не заменяет его успешным fallback. Это один selected-claim probe; independent
human gold, case-level accuracy, confidence interval и полнота extraction этим
запуском не установлены. `criticalErrorFreeRate` остаётся null.

## Audit acceptance #77

| Критерий                                                                  | Реализованное evidence                                                                                                                                                                                                                                                |
| ------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Inventory и versioned lineage                                             | [Legacy inventory](HARNESS_GAP_INVENTORY_2026-10-12.md), [offline envelope](OFFLINE_ENVELOPE_V1.md), [execution records](EXECUTION_RECORDS_V1.md), [references](RUNTIME_REFERENCE_V1.md).                                                                             |
| Plan/replay/compare/export, partial/failures, contexts и unknown handling | [Native schedule](STAGE1_NATIVE_SCHEDULE_V1.md), [paired comparison verification](RUNTIME_PAIRED_COMPARISON_VERIFICATION_2026-10-14.md), [safe resume](NATIVE_SAFE_RESUME_V1.md), [stop consumers](STOP_CONTROL_CONSUMERS_V4.md), оба сохранённых исхода этого pilot. |
| Versions/config/context и live opt-in отдельно от offline CI              | Plan pins и manifests в packet; explicit permit с пользовательским лимитом; independent public request policy; [CI](https://github.com/SoundBlaster/NormLab/actions/runs/39112165006) PR #143 — 6/6 success, review без findings.                                     |
| Idempotent MLflow и raw navigation                                        | [Registry verification](RUNTIME_MLFLOW_VERIFICATION_2026-10-14.md), [score import verification](RUNTIME_SCORE_MLFLOW_VERIFICATION_2026-10-14.md) и actual MLflow pass выше.                                                                                           |
| Saved baseline comparison без нового inference                            | [Существующие сравнения](OFFLINE_PAIRED_COMPARISON_2026-10-13.md), [runtime verification](RUNTIME_PAIRED_COMPARISON_VERIFICATION_2026-10-14.md); final pilot дополнительно проверяет self-comparison.                                                                 |

Последний полный CI относится к исполняемому `fc1f91c` / reviewed head `f1913d6`.
Локальные предыдущие результаты: SDK-free 368/368, Python 3.10 focused 10/10,
actual local MLflow 45/45. Этот отчёт не выдаёт их за повторный запуск сегодня.

## Portable evidence и повторение без inference

[Evidence packet](evidence/framework-v1-final-2026-10-18.zip) содержит оба archives,
references, scores, comparison JSON, protocol/amendment, source/image pins и
сводку actual local MLflow проверки. В нём 170 файлов, 250090 bytes compressed.
SHA-256 ZIP:
`fd8fb0f22cff0d8beb616e32a7962adb9e183a9d0e0c2721979f0bbae61b5584`.

Packet unsigned: hashes проверяют согласованность, не подтверждают подпись
провайдера, независимость reference или достоверность всех runtime declarations.
Проверять его надо доверенными readers из указанного source revision; code из
archive не исполняется. SQLite registry и API keys в packet не входят.

Опубликованный ZIP дополнительно распакован в fresh directory и проверен на
Python 3.14.8 с удалённым CoreInfra key и network-denying audit hook: все 169 payload
hashes/lengths, оба archives, scores и self-comparisons прошли проверку. Это
отдельный replay из packet, без обращения к оригинальным output directories.

После распаковки в `$PILOT` из checkout с этим reader revision:

```bash
python3 -B -S evaluation/runtime_archive_cli.py verify "$PILOT/archive-real"
python3 -B -S evaluation/runtime_score_cli.py verify \
  "$PILOT/archive-real" "$PILOT/score-real.json"
python3 -B -S evaluation/runtime_archive_cli.py verify "$PILOT/archive-setup-failure"
python3 -B -S evaluation/runtime_score_cli.py verify \
  "$PILOT/archive-setup-failure" "$PILOT/score-setup-failure.json"
# В окружении с закреплённым MLflow; storage вне archive:
python3 -B evaluation/import_runtime_mlflow.py "$PILOT/archive-real" \
  --score "$PILOT/score-real.json" --storage "$PILOT/registry"
# Повторить ту же import-команду: IDs должны сохраниться.
```

Эти команды не вызывают inference и не требуют provider keys. Для проверки
enforced network denial нужен отдельный OS/audit guard, как в выполненном pass.

## Жёсткая граница v1 и следующий ход

V1 завершает имеющийся independent-request execution и portable evidence path.
Attempt-correlated adoption, новые dialogue/repair стратегии, Evidently и
выделение общего пакета **отложены**; они не являются оставшимися acceptance #77.
Исторические записи «следующий slice» в ранних документах описывают прежний план.

Следующий ход: подготовить маленький development-набор ошибок polarity, scope и
attribution с зафиксированными candidate expectations, затем проверить одну
изменённую стратегию на тех же inputs. Independent review остаётся отдельной
задачей [#64](https://github.com/SoundBlaster/NormLab/issues/64). Цель — улучшить
качество доступной конфигурации, без нового рейтинга моделей и без расширения
инфраструктуры ради самого расширения.
