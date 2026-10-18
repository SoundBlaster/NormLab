# Development error catalogue — v1

Начальный evidence register, 2026-10-11. Не полный review 30–50 фабул и не новый
gold dataset. Ошибка относится к конкретному этапу и входу; её нельзя переносить
на качество всей модели или extraction pipeline.

| ID   | Наблюдение                                                                                  | Этап                                                                       | Свидетельство                                                                                                                      | Что проверять далее                                                                                 |
| ---- | ------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| E001 | Источник отрицает оплату; candidate меняет stance на asserted; verifier принимает candidate | Candidate verification, false acceptance относительно candidate convention | C002/R003, Jev в [retry v2 live](STAGE1_RETRY_LIVE_2026-10-11.md); исходная фабула и candidate заморожены                          | Локальный вопрос о polarity/scope против общего judgment; source-only reconstruction отдельно       |
| E002 | Candidate сохраняет исходное отрицание оплаты; verifier отвергает candidate                 | Candidate verification, false rejection относительно candidate convention  | C002/R004, Luna Decisions в том же sealed capture                                                                                  | Сохраняется ли ошибка при локальном question; не уменьшать false acceptance ценой blanket rejection |
| E003 | Typed projection не сохраняет обязательные identity/scope/operator distinctions             | Representability / contract, не model inference                            | [Annotation v2 audit](STAGE1_ANNOTATION_V2_2026-10-09.md): 1 representable / 15 lossy sources для обоих layouts при строгой policy | Разделять schema loss и неверный ответ; не ждать от модели невыразимого контракта                   |

Текущие E001/E002 измеряют проверку уже заданной разметки. Они не доказывают,
что extractor потерял отрицание, и не оценивают omissions или gap detection.
Labels остаются candidate; уже просмотренные случаи не могут стать holdout.

Update 2026-10-18: E001 повторился на `C002/R003` в завершающем framework pilot
(Jev 1.13.0, request `req_01a14e4575b87a109e5db33ef764b188`): `compatible` против
candidate `incompatible`. Полный request/capture сохранён в
[finish evidence](https://github.com/SoundBlaster/NormLab/blob/17446d665efb7ee595932fc60559f267cebff490/docs/EVALUATION_FRAMEWORK_V1_FINISH_2026-10-18.md).
Отдельное исследование — [#145](https://github.com/SoundBlaster/NormLab/issues/145),
backlog. Это повтор того же diagnostic case, не новая независимая ошибка для
оценки частоты. Подготовка [45 development-карточек](../fixtures/parking-pilot/development-review-v1/README.md)
не запускала новую модельную серию и не добавляет наблюдаемые errors в каталог.

## Отдельный operational register

В retry v2 live capture: 12 dispatches, 6 accepted outputs, 6 TLS failures;
4 задания восстановлены. Это transport failures, не semantic polarity errors.
First/final denominators и unknown usage сохраняются в scorer. Исправление
сети не засчитывается как улучшение понимания текста.

## Карточка для полного development review

Для каждого нового наблюдения сохранить:

- Case/source hash, family/incident group, выбранный episode и объявленное задание.
- Run/arm/stage/attempt IDs и точную версию output; исходный quote/span.
- Expected representation и допустимые alternatives до просмотра outputs.
- Critical-error class, missing/incorrect claim или gap, scope и rationale.
- Статус candidate / independently reviewed / adjudicated; reviewer disagreement.
- Результат whole-case review, а не только найденного fragment; неисследованные
  omissions остаются pending.
- Изменение pipeline, rescue и все новые regressions на тех же входах;
  human correction хранится отдельно от automatic output.

Полный каталог собирается по [rubric качества](PIPELINE_QUALITY_PLAN.md).
Следующая карточка/гипотеза выбирается по повторяющемуся failure mode и
доступности корректного представления; не по желанию объявить конкретную модель
победителем. Частота ошибок считается только после review всех назначенных кейсов.
