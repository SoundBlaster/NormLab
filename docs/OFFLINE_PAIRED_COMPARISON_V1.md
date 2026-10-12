# Offline paired comparison v1

Slice 2 [#77](https://github.com/SoundBlaster/NormLab/issues/77).
[Implementation](../evaluation/offline_compare.py) принимает два проверенных
[offline bundles](OFFLINE_ENVELOPE_V1.md) без SDK, scorer replay или inference.

## CLI

```bash
python3 -B -S evaluation/offline_compare.py baseline-bundle candidate-bundle \
  --output .artifacts/comparison-001

# Legacy classification: явно ограниченный diagnostic comparison.
python3 -B -S evaluation/offline_compare.py baseline-bundle candidate-bundle \
  --context legacy-logical-diagnostic --vary provider \
  --output .artifacts/comparison-diagnostic-001
```

Без `--output` печатается summary. С ним создаётся новый каталог с
`report.json` и `report.md`; существующий каталог не перезаписывается.
JSON ограничен 2 MiB. Invalid input/export даёт exit 1 и fixed diagnostic.
Валидный comparison с несовместимыми или неоценёнными строками даёт exit 0:
исключения представлены данными, а не скрытым quality pass.

Это portable report, не новый execution checkpoint или registry. Он содержит
source bindings и результаты, но не копирует оба raw input bundles. Для повторного
вычисления нужны исходные bundles и шесть stdlib-only modules: comparator и пять
reader modules. Source text/raw answers в comparison rows не копируются;
experiment metadata сохраняется из входов. Автоматической публикации нет.

## Pair identity

Общий ключ: `(caseId, candidateId, armId, repeat, slot)`.

- S1.3 A/B/C: candidate ID и repetition берутся из validated task.
- S1.3 D: slot — digest полного source target из logical payload. Несколько
  targets одного case не сливаются; scheduled job number не заменяет target identity.
- Classification: slot — original record ID. Legacy repeat number неизвестен;
  matching разных record IDs по порядку или только по case не выполняется.
- Дубли одного ключа внутри view отклоняются как ambiguous pairing.

Task IDs разных runs могут различаться. Оба сохраняются в строке comparison.
Односторонние keys становятся `baseline-only`/`candidate-only`; не заполняются
нулевой оценкой и не исчезают из union denominator.

## Compatibility

Сначала каждый bundle проходит reader validation и artifact hash checks.
Comparator повторно проверяет hash/size потребляемых artifacts и привязывает
результат к byte digest index. Это consistency unsigned evidence, не authenticity.

Для оценки пары требуется:

- Один source family: classification v1/v2 либо S1.3.
- Одинаковый dataset ID/revision/digest, experiment policy, scorer artifacts и
  dependencies, score scope и evidence kind.
- Одинаковые strategy/tactic/provider metadata, кроме переменных, явно объявленных
  через повторяемый `--vary provider|strategy|tactic`. Это разрешение на variable,
  не доказательство её изоляции или причинности.
- Одинаковые family/language/source/task digests для paired tasks.
- Одинаковые reference schema/status/revision и expected answers выбранной пары.
  Reference IDs могут различаться: classification labels включают experiment byte
  digest, который меняется при другом capture/manifest. Оба original reference IDs
  остаются в source bindings; schema-specific reference validation не обходится.
- Для logical context — одинаковые context policy и payload digest. У S1.3 это
  provider-neutral logical context, не подтверждение точного wire request.

`strict` по умолчанию исключает из quality comparison context `unavailable`.
`legacy-logical-diagnostic` разрешает лишь этот недостаток legacy classification;
сохраняет все остальные compatibility checks и не снимает запрет на разные
сохранённые logical payloads. Это не strict matched-context experiment.

Отсутствие reference или незавершённый outcome даёт `not-evaluated`.
Несовпадение reference expectations/provenance и других обязательных bindings
даёт `incompatible`. Несовместимость может быть глобальной или только per-row.
Одинаковые projections reference не доказывают independent human review.

## Metrics и denominators

Comparison schema: `normlab.offline-comparison/v1`. Policy ID/digest, comparator
и reader code digests входят в deterministic comparison identity. Привязаны оба
bundle digests, run/score/reference IDs, dataset и experiment metadata.

В `summary` и arm/family slices сохраняются:

- Число planned tasks каждой стороны, union/matched tasks, односторонние keys,
  incompatible и not-evaluated rows.
- Status counts по всем planned rows каждой стороны и отдельно по matched rows.
  Failures/invalid/missing не становятся успешными abstentions.
- `selectedReferenceAgreement`: numerator каждой стороны и **один общий paired
  denominator** только для совместимых задач с двумя completed/scored outcomes.
  Нулевой denominator даёт null delta; неоценённые строки не превращаются в zero quality.
- Classification pass — native selected payment `probePass`; S1.3 pass — agreement
  всех selected questions данной task. Это разные scopes, не общий model rating.
- `regression`: true → false; `rescue`: false → true; `unchanged`: остальные
  оцениваемые пары. Failure → completed не получает semantic rescue автоматически.

Raw side outcomes сохраняются даже у excluded pairs. `sameRun`, `sameCaptureSet`
и `sameScoreView` явно показывают повторное использование evidence;
`executionIndependence: not-established` не выводится из различия hashes.
Это особенно важно для двух rescored views одного legacy run.

Repeated tasks/переводы/семейства не считаются независимыми кейсами. Указаны unique
cases/families; confidence intervals и case-level critical-error-free quality
остаются null. Для comparison разных стратегий, меняющих inputs/context, потребуется
отдельный frozen protocol; ослабление этих checks автоматически не выполняется.

Markdown содержит counts, причины исключения и до 50 changed/unpaired events.
Глобальные несовместимости показываются отдельным разделом даже без matched tasks;
`incompatible` в таблице counts относится только к matched rows.
JSON сохраняет полные keys, reasons, исходные statuses и все arm/family slices.

## Выполненные сравнения

[Runtime report](OFFLINE_PAIRED_COMPARISON_2026-10-13.md): девять fixture/diagnostic
сценариев и побайтово одинаковый portable результат, с запрещённой сетью.
Новые unit tests в этом slice не добавлялись; предыдущий suite #85 проверяет
export/reader, но не объявляется regression coverage нового comparator.

Следующий шаг после review — regression coverage comparison policies, затем
adapter Stage 1 attempts/retries; MLflow projection остаётся отдельным slice #77.
