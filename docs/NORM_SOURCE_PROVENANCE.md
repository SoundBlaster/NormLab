# Norm source provenance — candidate design

Дата: 2026-10-04. Основание — решение автора о ссылках на официальные первоисточники. Применяется к будущим NormPackage и UI; runtime/storage пока не реализованы. [Исследовательский реестр парковочного пилота](PARKING_SOURCES.md) остаётся отдельным списком найденных документов и открытых проверок.

## Две цепочки оснований

```text
Вывод
├── Reviewed inputs → assertions → цитаты исходной фабулы
└── Engine rule → formalized norm fragment → зафиксированная официальная публикация
```

Извлечение source quote не удостоверяет факт. Наличие официального URL не удостоверяет актуальность редакции или правильность формализации. Human fact review, source/edition review и semantic rule review должны сохраняться раздельно.

## Source snapshot и fragment

Для каждого источника будущий package должен фиксировать:

- stable source ID, орган/издатель, название акта, дату и номер;
- официальный publication URL и происхождение копии;
- вид evidence: первичная публикация, изменяющий акт, консолидированная копия, официальное разъяснение или secondary host;
- edition identity и подтверждённую цепочку изменений для используемых положений;
- даты опубликования, начала/окончания действия, когда они установлены; неизвестное не заменять предположением;
- retrieval time, media type, неизменяемый local/archive artifact и SHA-256 исходных bytes;
- extracted text с отдельным digest и сведениями об OCR/преобразованиях;
- fragment locator: статья/часть/пункт, страница, exact quote и anchor в зафиксированной копии;
- reviewer decision, область проверки и открытые зависимости.

Hash фиксирует bytes, а не юридическую подлинность. OCR text не заменяет официальный скан; для спорного фрагмента нужна связь с оригинальной страницей. Недоступный URL не разрешает автоматически повысить статус secondary copy.

Для ссылки engine rule → norm fragment сохранять stable rule ID, source snapshot/fragment refs, formalization rationale, assumptions и semantic review. Один rule может иметь несколько оснований; amendment history и guidance refs не смешиваются с непосредственным нормативным основанием.

## Binding и воспроизводимость

Calculation revision связывается с digest NormPackage, ontology/contract и source snapshots. Старый результат продолжает ссылаться на использованную редакцию после обновления источников. Новый текст создаёт новый snapshot; нельзя незаметно переписать существующий artifact.

В пилоте используется один фиксированный reviewed нормативный пакет. История редакций не требует отдельного UI прямо сейчас, но identity и content binding обязательны. Fact-source binding из extraction contract не заменяет norm-source binding.

## UI требований

У результата два раскрываемых раздела: «Основания по фактам» и «Основания по нормам». Для нормы показывать понятное название, статью/пункт, использованную редакцию, цитату и ссылку на официальный ресурс. Если используется historical snapshot, consolidated copy или secondary host, показывать именно этот статус.

Если актуальность, применимость или semantic review не закрыты, результат не получает статус окончательно проверенного правового вывода. Общее объяснение/FAQ не показывается как текст нормативного акта. Оригинальные URLs сохраняются рядом с snapshot даже при недоступности сайта.

## Implementation roadmap

- [x] Зафиксировать design и связать с источниками/планом/roadmap.
- [ ] Создать bounded source-snapshot/fragment schema и storage policy, включая хранение originals/OCR.
- [ ] Зафиксировать официальные публикации и релевантные изменения выбранного parking fragment; закрыть нормативный lock gate.
- [ ] Связать rule IR и NormPackage с reviewed fragment refs и digests.
- [ ] Добавить в результат/UI обе цепочки оснований и проверку stale bindings.

Success criteria: каждый вычисляемый rule прослеживается до reviewed fragment в immutable snapshot; исходные bytes и quote можно проверить; новая редакция не меняет исторический расчёт; source evidence и юридические assumptions видимы пользователю. Это planned acceptance criteria, не выполненные проверки.
