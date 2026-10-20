# Development review v1

Ledger: [#65](https://github.com/SoundBlaster/NormLab/issues/65).
Дата: 2026-10-18. **45 development-текстов, candidate readings; human gold и
model quality score отсутствуют.** Нового inference в этом срезе нет.

## Что выбрано

- Все 40 существующих synthetic controls: по 5 текстов в 8 authored families.
- Пять существующих editorial paraphrases: `C01`, `C03`, `C08`, `C11`, `C13`.
  Они добавляют сообщение защитника, рассказ читателя, задержку пополнения,
  автомобиль супруги и сообщения о формате номера.
- Оставшиеся 26 текстов исходного pool не удалены: 16 Stage1 micro-probes и
  10 editorial inputs перечислены в exclusions с причинами. Полный исходный
  [inventory из 71 текста](../pipeline-quality-v1/corpus-inventory.json) неизменен.

Этот состав выбран по coverage, не случайно и не по удачным ответам моделей.
Полнота и разнообразие реальных пользовательских рассказов им не установлены.
Все тексты уже использовались при разработке; это не blind annotation.

## Файлы

| Файл                                                     | Назначение                                                                         | Передавать extractor?                                                                    |
| -------------------------------------------------------- | ---------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| [source-only.json](source-only.json)                     | Только ID, исходный текст с сохранённым LF и SHA256 его bytes                      | Да, только выбранный record; это data view, не новый runner contract                     |
| [selection.json](selection.json)                         | Отбор, оригинальные IDs/paths/hashes, source registry, происхождение и ограничения | Нет                                                                                      |
| [grouping-and-coverage.json](grouping-and-coverage.json) | Source/family связи, exclusions, coverage gaps и запрет holdout                    | Нет                                                                                      |
| [reviewer-only.json](reviewer-only.json)                 | 175 candidate readings, source spans и 173 условных уточнения                      | Нет                                                                                      |
| [rubric.json](rubric.json)                               | Whole-input review scope, critical errors, unknown/identity policies               | Только общую инструкцию будущего protocol после отдельного freeze; case labels — никогда |
| [casebook.md](casebook.md)                               | Читаемые тексты, readings, вопросы и нерешённые толкования                         | Нет                                                                                      |

`source-only.json` не содержит ожиданий, family tags, происхождения, gap hints или
ответов. Его SHA256 относится к `text.encode('utf-8')`, а не к сериализации JSON.
Readings опираются на source, но пока написаны одним агентом. Они не являются
подписью эксперта, independent review или автоматически исполняемым gold scorer.

## Полнота review и статус

Для каждого input выполнено candidate чтение всего текста: положительные и
отрицательные утверждения, unknowns, источники сообщений, время, автомобиль,
эпизоды, значимые контрасты и возможные unsupported scope. Некоторые readings
ссылаются на весь короткий input: spans показывают опору, не устанавливают её
семантическую достаточность механически. Offset unit — UTF-16 code units,
half-open `[start, end)`; это не bytes и не Python code-point indices.

Уточнения относятся к **явно заданному заданию этого review**, а не к полному
перечню юридических требований. У каждого есть `requiredWhen`: для известного
другого города не нужно спрашивать все поля московского расчёта. Эквивалентные
конкретные вопросы допустимы; отсутствие данных не превращается в отрицание.
Различаются missing, explicit unknown, ambiguous, withheld и unresolved conflict.

Автоматические outputs на этих 45 случаях не производились и не проверялись.
`outputReviewStatus=not-started`, `automaticCaseQuality=null`; нет результатов
case pass, полноты extraction или ошибки на каждое из 175 readings. Ошибка модели
вне этого среза сама по себе не подтверждает/опровергает все карточки.

Следующие обязательные действия перед заявлением полного качества:

1. Независимо проверить candidate readings/gaps и сохранить disagreements либо
   adjudication. Сначала прочитать `source-only.json` и общий rubric, записать
   собственные readings; только затем открывать candidate casebook для сравнения.
   Human review сейчас **0/45**; независимость не приписывается.
2. Заморозить один research protocol и выбранную конфигурацию.
3. Получить и проверить весь automatic output каждого назначенного input по
   rubric. Корректный JSON/anchors и частичные probes не заменяют whole-case review.
4. Если representation не выражает нужное различие или gaps, записать contract
   limitation; не считать такой показатель автоматически пройденным.

## Группировка до любых splits

45 разных text digests не означают 45 независимых событий. Общие source IDs и
synthetic family links образуют компоненты размеров **43, 1, 1**. Общая source
inspiration — ограничение для будущего split, а не доказательство, что истории
описывают один реальный эпизод.

Консервативно все 45 помещены в `DEV-ALL-SEEN`, `development-only`,
`holdoutEligible=false`. Existing Stage1 semantic relatives отмечены отдельно.
Validation/test splits не созданы, число независимых cases — null. Перекрёстная
проверка incident identity публикаций остаётся pending; сохранённые upstream
incident IDs не являются её результатом.

Coverage всё ещё слабое: 40 коротких synthetic inputs, только 5 редакционных
пересказов, мало длинных/шумных рассказов; conditional/hypothetical/obligation
operators не покрыты систематически. Нельзя подменить добор natural narratives
размножением этих шаблонов или перевести уже просмотренный текст в holdout.

## Происхождение, права и privacy

Исходные файлы и historical reviewer probes не изменены. Сохранены manifests и
registry hashes, URL/locator, известные даты и ограничения из существующего
registry. Сайты в этом offline-срезе повторно не открывались; соответствие
editorial пересказов публикациям не проверено заново.

Synthetic controls написаны в проекте; ссылки указывают источник идеи, а не
доказательство придуманного события. Editorial inputs — прежние обезличенные
пересказы, а не оригинальные статьи/комментарии. Сохранение ссылки не даёт права
перепубликовывать полный original. В пакет не добавлены full third-party texts,
имена, реальные номера автомобилей, ключи или outputs провайдеров.

## Следующий ход

Локальная проверка 2026-10-18: 45 source digests и исходные manifests/registry
совпали; 175 UTF-16 spans точно воспроизводят цитаты; 173 conditional followups
содержат условия применения; reader-only поля отсутствуют в source-only records.
Проверены 17 relative links, Prettier и исходный inventory 71/71 без изменений.
Это structural/provenance проверки, не доказательство semantic полноты карточек.
Новые tests, inference и output scoring в данном срезе не выполнялись.

Review карточек и rubric. После него — одна изменяемая стратегия на фиксированных
inputs, с отдельными capture/reference revisions и заранее заданным budget.
Кейс Jev `C002/R003` ведётся отдельно в
[#145](https://github.com/SoundBlaster/NormLab/issues/145), без новой серии запросов
в рамках подготовки этого набора.
