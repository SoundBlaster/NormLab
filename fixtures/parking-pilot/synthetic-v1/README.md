# Synthetic extraction corpus v1

**40 inputs в 8 families. Development material, candidate expectations, не gold и не holdout.** Подготовлено Codex 2026-10-05. Это придуманные агентом варианты, а не подтверждённые реальные происшествия или независимая разметка.

| Family | Cases | Probe |
|---|---|---|
| payment-polarity | SYN001–005 | Оплата, неоплата, unknown, интервалы и отрицание отмены |
| vehicle-and-zone | SYN006–010 | Объект платежа отдельно от размещения; попытка исправления |
| payment-time | SYN011–015 | Секундные границы, покрытие платежа, баланс |
| outage-and-corrections | SYN016–020 | Каналы оплаты, неизвестный результат, отсутствие ошибок |
| permits-and-gaps | SYN021–025 | Разрешения, заявки, неполные disability conditions |
| attribution-and-conflicts | SYN026–030 | Речь, заметка, уведомление; разные эпизоды |
| jurisdiction-and-scope | SYN031–035 | Москва, другой город, unknown, частный паркинг |
| regime-and-background | SYN036–040 | Режим отдельно от разрешений, платежа и штрафа |

## Файлы и происхождение

- `inputs/*.source.txt`: фабула с LF, без labels/reviewer notes.
- `inputs/*.input.json`: только narrative и SHA256, для передачи extractor.
- [manifest.json](manifest.json): версия, IDs, paths, hashes, family/split group, inspiration source IDs. Не передавать модели.
- [reviewer-expectations.json](reviewer-expectations.json): отдельные candidate probes, literal quotes с UTF16 offsets, forbidden inferences и manual review focus. Не передавать модели.

В `required.predicate` и `forbidden` predicate IDs указаны без namespace; dataset-aware scorer должен добавлять `nlinput:` при сравнении с полным ID извлечения.

Source IDs относятся к [registry](../corpus/sources.json). Из публикаций взяты идеи сложности; даты, интервалы, Москва и отрицания могут быть придуманы. Ссылки не удостоверяют synthetic обстоятельства. Legal outcomes не заданы, действие льгот и юридический эффект исправлений не утверждаются.

## Прогон и оценка

После [setup](../../../docs/EVALUATION_SETUP.md), из корня проекта. LM Studio должен обслуживать `openai/gpt-oss-20b` на `127.0.0.1:1234`:

```sh
.tools/parking-evaluation/bin/python evaluation/run_synthetic.py experiments/parking-baseline/2026-10-05-synthetic-v1-gpt-oss-20b
npm run parking:evaluate:synthetic -- experiments/parking-evaluation/2026-10-05-synthetic-v1-final experiments/parking-baseline/2026-10-05-synthetic-v1-gpt-oss-20b
```

Runner выполняет два model calls на case последовательно, не перезаписывает каталог и фиксирует source, pipeline, per-case status, stdout/stderr, outputs и SHA256 manifest. Можно ограничить ручной прогон списком IDs, например `.../run_synthetic.py /tmp/normlab-synthetic-smoke SYN001 SYN002`. Scorer использует только inputs/outputs из проверенного manifest, сверяет source digests и exact anchors, считает structural pass, required probes и forbidden inferences по всем 40 cases, включая пропуски и provider failures.

`expectedGaps` показываются отдельно как **not evaluated**: текущий output contract не содержит поля для извлечённых пробелов. Поэтому assertion-probe rate — только диагностическая оценка выбранных candidate probes, а целевой показатель «80% кейсов без критических ошибок» остаётся `null` до экспертной разметки и реализации gap scoring. Первый прогон опубликован в [отчёте](../../../docs/SYNTHETIC_EVALUATION_2026-10-05.md): 0/40 structural pass; discovery stage вернул пустые либо не привязанные к источнику утверждения.

## Границы проверки

В каждом case задан один выбранный semantic probe, не полный gold graph. Quote — пример достаточной опоры, не обязательное byte-for-byte совпадение ответа модели. Неизвестная запись платежа, ожидание разрешения, неполная дата и оплата другой машины допускают разные representations; нужна review/adjudication до scoring.

Unknown не означает false. Partial disability conditions не закрывают все условия льготы. Временные границы — языковые/арифметические probes, не validated legal rule. Запрет необоснованного отрицания вины не устанавливает вину.

По уточнению пользователя, **доказанность событий не требуется**: тестируем понимание заданной фабулы. `expectedGaps` перечисляет выбранные candidate уточнения, не полный набор нормативных требований. Корректно названный пробел и запрос уточнения — ожидаемый успех; уверенный вывод по неподтверждённым данным — ошибка. Эти expectations ещё не подключены к автоматическому scorer. Sufficiency правового вывода остаётся not-evaluated до реализации соответствующего этапа.

40 inputs не равны 40 независимым случаям (`realIncidentCount=0`). Варианты family держать в одном split; общие source inspirations связывают также разные families. Поэтому весь набор development-only. Его score не доказывает population accuracy или достижение 80% на реальных обращениях.

Следующий этап: review candidate labels, dataset-aware scoring и отдельный natural-language holdout.
