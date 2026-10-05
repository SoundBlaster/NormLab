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

Source IDs относятся к [registry](../corpus/sources.json). Из публикаций взяты идеи сложности; даты, интервалы, Москва и отрицания могут быть придуманы. Ссылки не удостоверяют synthetic обстоятельства. Legal outcomes не заданы, действие льгот и юридический эффект исправлений не утверждаются.

## Использование

После [setup](../../../docs/EVALUATION_SETUP.md), из корня проекта:

```sh
.tools/parking-evaluation/bin/python evaluation/two_stage.py fixtures/parking-pilot/synthetic-v1/inputs/SYN019.input.json /tmp/normlab-SYN019-output.json
```

Выбрать новый output path: прямой worker может перезаписать файл. Inference по этому набору при подготовке не выполнялось. Текущий `parking-evaluate.ts` оценивает только четыре P-cases; для synthetic-v1 нужен dataset-aware runner/scorer после согласования labels.

## Границы проверки

В каждом case задан один выбранный semantic probe, не полный gold graph. Quote — пример достаточной опоры, не обязательное byte-for-byte совпадение ответа модели. Неизвестная запись платежа, ожидание разрешения, неполная дата и оплата другой машины допускают разные representations; нужна review/adjudication до scoring.

Unknown не означает false. Partial disability conditions не закрывают все условия льготы. Временные границы — языковые/арифметические probes, не validated legal rule. Запрет необоснованного отрицания вины не устанавливает вину.

По уточнению пользователя, **доказанность событий не требуется**: тестируем понимание заданной фабулы. `expectedGaps` перечисляет выбранные candidate уточнения, не полный набор нормативных требований. Корректно названный пробел и запрос уточнения — ожидаемый успех; уверенный вывод по неподтверждённым данным — ошибка. Эти expectations ещё не подключены к автоматическому scorer. Sufficiency правового вывода остаётся not-evaluated до реализации соответствующего этапа.

40 inputs не равны 40 независимым случаям (`realIncidentCount=0`). Варианты family держать в одном split; общие source inspirations связывают также разные families. Поэтому весь набор development-only. Его score не доказывает population accuracy или достижение 80% на реальных обращениях.

Следующий этап: review candidate labels, dataset-aware scoring и отдельный natural-language holdout.
