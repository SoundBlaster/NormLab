# Luna Low → Medium: парный development experiment

Дата: 2026-10-19 MSK. Задачи: [#79](https://github.com/SoundBlaster/NormLab/issues/79),
[#70](https://github.com/SoundBlaster/NormLab/issues/70). Статус: **protocol proposal;
новых provider calls нет, execution authority ещё не выдана**.

## Вопрос и гипотеза

Уменьшит ли `reasoning.effort=medium` ошибки полного extraction pipeline при
неизменных prompts, schema и token/time limits по сравнению с сохранённым `low`?
Улучшение — гипотеза, а не ожидаемый заранее результат. Отдельно проверить новые
ошибки и расход ресурсов. Не исправлять actor/episode/subject defects до сравнения.

Официальная [карточка GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna)
перечисляет `low` и следующий уровень `medium`. Это подтверждает официальный
параметр модели, но не реализацию/цену через CoreInfra. Доступность и echo параметра
проверяются в первых запланированных extraction requests, без отдельного smoke.
Принятый request или echo не является аттестацией внутренних вычислений провайдера.

## Зафиксированный baseline

- Low execution: commit `5d35e47`; опубликованное evidence: commit
  `d157ef929c4d8eedca5fd0177981695291295fef`, [PR #159](https://github.com/SoundBlaster/NormLab/pull/159).
- [Полный отчёт](LUNA_DEVELOPMENT_PILOT_2026-10-19.md),
  [authority](evidence/luna-development-2026-10-19/authority.json),
  [исходный архив](evidence/luna-development-2026-10-19/evidence.zip).
- Archive SHA256: `da81366eb21084af19183410210ae9f3e3d51e1b3a12163cd2502f6e915d295a`.
- 10/10 completed, 20 attempts, 70,035 ms, 16,382 input / 4,876 output tokens.
- Same-agent candidate review: 4 provisional passes, 3 candidate critical concerns,
  3 unresolved. Это не human gold и не baseline accuracy 40%.

## Arms и controls

| Условие                                 | Archived baseline                                 | Новый arm                         |
| --------------------------------------- | ------------------------------------------------- | --------------------------------- |
| Effort discovery **и** classification   | `low`                                             | **`medium`**                      |
| Модель / provider / endpoint            | `gpt-6-luna`, CoreInfra Responses                 | То же                             |
| Фабулы и порядок                        | DEV001/002/003/006/013/017/027/028/032/044        | Те же исходные bytes и DTO hashes |
| Pipeline                                | `literal-discovery-then-classification/hosted-v1` | Тот же                            |
| Prompts, definitions, JSON schemas      | Заморожены в low authority                        | Те же                             |
| Output cap discovery / classification   | 16,384 / 8,192                                    | Те же                             |
| Batch size / concurrency                | 8 / 3                                             | Те же                             |
| Timeout operation / extraction / series | 120 / 300 / 900 s                                 | Те же                             |
| Retry / repair / judge / tools          | 0 / 0 / 0 / none                                  | То же                             |
| Candidate reference / rubric            | Исходный preparation packet                       | Без правок и без передачи модели  |

Единственный заданный экспериментатором factor — effort на **обоих** этапах.
Discovery при medium может выделить другие fragments, поэтому classification
inputs и число batches естественно могут отличаться. Это сравнение общего эффекта
стратегии; оно не изолирует вклад classifier при одинаковых готовых fragments.
Classifier-only ablation и свежий low rerun — отдельные возможные опыты, не часть
данного предложения.

Не добавлять `temperature`, seed, новые output fields, дополнительные tokens,
переводы, улучшенный prompt или новые онтологические проверки. При недостаточном
token cap сохранить incomplete/protocol failure, не увеличивать cap в ходе серии.

## Execution gate и ограничения

После согласования нового bounded запуска подготовить и закрепить отдельный
execution commit/runtime authority до dispatch. Проверить старые source hashes
и разрешённый effective diff: только значение effort, без исправления production
default или исторических low artifacts. Замороженные build/driver из low не
перезаписывать. Medium prompt/config digest должен отражать фактический effort;
нельзя отправить medium, сохранив low provenance как будто конфигурация одинакова.

Проверить emitted request bodies: medium в обоих этапах, остальные настройки
совпадают; model inputs не содержат reviewer cards, baseline outputs и findings.
Повторно проверить runtime/dependencies и TB5 перед artifact-producing commands.
Текущая preparation — документация, без сборки/установки/нового test suite.

Предлагаемый бюджет: **10 новых case runs, ожидаемо 20 requests, максимум 30
aggregate provider attempts**, ноль retries/repair/judge. $4 — ранее сообщённый
пользователем внешний потолок аккаунта, не новая выдача $4 и не проверенный баланс.
Цена CoreInfra неизвестна; runner ограничивает attempts/time, а не достоверно
известную денежную стоимость. Перед live нужна явная bounded авторизация новой
серии: предыдущая относилась к завершённому low run.

Стоп при первом operational/protocol/unknown outcome, достижении cap/deadline или
дрейфе controls. Не менять provider/модель/effort и не запускать fallback. Записать
все отправленные attempts, оставшиеся cases как not-executed и дождаться исходов
уже начатых запросов. Semantic disagreement не вызывает retries и не останавливает
серию. Unsupported/rejected medium не выдавать за negative semantic result.

## Полный review и таблица сравнения

1. Сохранить raw requests/responses и immutable normalized output. Проверить
   schema, UTF-16 evidence anchors, source/config binding и все operational исходы.
2. Для **всех десяти** фабул прочитать source → output и output → source, включая
   unclassified fragments. Candidate cards и rubric остаются прежними; review
   тем же агентом не независимый и не blind, даже при скрытых arm names.
3. Для каждого кейса записать: expected meaning, low actual, medium actual,
   candidate errors, unresolved nuances, новые regressions и слой проблемы.
   Общие категории: `improved`, `regressed`, `unchanged`, `unresolved`,
   `operational/not-comparable`; не сводить всё к одному pass score.
4. Отдельно сравнить три известных concerns: DEV002 payer scope, DEV027 common
   episode scope, DEV032 placement subject type. Для DEV006/017/044 проверить,
   стали ли relations/cause/modality явнее, не назначая quote-only retention
   автоматически ни успехом, ни полной потерей факта.
5. На DEV001/003/013/028 проверить отсутствие регрессий: никаких новых paidRegime,
   потери unknown, округления секунды или разрешения конфликта вместо пользователя.
   Все другие новые ошибки также перечислить; не ограничивать review этими probes.
6. Сопоставить actual input/output/reasoning/cache tokens, attempts, per-case и
   series latency. Отсутствующие usage/details/cost — null; не подставлять тариф
   официального API вместо CoreInfra и не считать cache/сеть эффектом effort.
7. Offline replay сохранённых medium bytes, archive/hash/credential verification.
   Human correction sessions и burden остаются неизмеренными, если их реально нет.

У extractor по-прежнему нет dedicated followup list/multi-episode scope/out-of-demo
routing fields. Medium не добавляет эти поля в schema. Разделять semantic gains,
structured representability и полноту assisted task; не выдавать лучшее извлечение
за завершение всего пользовательского пути.

## Интерпретация и решение

- Если стало меньше подтверждённых critical concerns без новых critical regressions,
  medium — кандидат для следующего development шага с явной ценой tokens/latency;
  это не автоматическая смена production default.
- Если прежние ошибки остаются, улучшение этой десятки не поддержано; работать
  над найденными actor/scope/type/contract причинами, не повышать effort до high
  автоматически. Смешанный результат отразить по кейсам, без победителя заранее.
- Unresolved adjudication не превращать в confirmed improvement. No overall
  accuracy, статистической значимости или гарантии для других текстов.
- Один medium ответ на текст и исторический low baseline не измеряют variance.
  Нельзя отделить стохастику, скрытый drift модельного alias/proxy, cache и время
  запуска от effort уверенным causal выводом. Returned model/echo/config/usage
  записать; практический вывод ограничить наблюдёнными парными примерами.

Следующий ход: согласовать proposed caps → закрепить отдельную medium runtime
authority с offline checks → выполнить bounded arm → сохранить парный отчёт.
Не расширять framework и не возобновлять deferred Jev investigation.
