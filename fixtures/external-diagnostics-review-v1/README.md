# Candidate semantic review v1 — reviewer only

Разметка, подготовленная AI assistant, 2026-10-12 (Europe/Moscow): все **24 RCB
пары** и **50 целевых attribution probes в 12 судебных текстах**. Исходные
snapshots в [external-diagnostics-v1](../external-diagnostics-v1/README.md)
сохранены неизменными. Это development evidence, не human gold и не holdout.

## Файлы и границы

- `candidate-reviews.jsonl` — proposed readings, запрещённые выводы и exact
  source anchors. **Не передавать этот файл исследуемой модели.**
- `manifest.json` — hashes, scope, reviewer status и provenance исходного
  manifest. Upstream labels были видимы; этот проход не blind и не independent.
- [Отчёт](../../docs/EXTERNAL_DIAGNOSTIC_REVIEW_2026-10-12.md) — спорные случаи
  и требования к следующим questions. Ответы исследуемых моделей для этого
  прохода не читались; новые provider calls не выполнялись.

В RCB прочитаны полные короткие пары; это targeted semantic review, а не
проверка всех возможных извлечений. В судебных текстах просмотрены начала,
целевые фрагменты и окончания; **полная extraction completeness, все факты,
gaps, независимость дел и юридическая правильность не оценены**. Все записи
сохраняют `humanReviewed: false`, `adjudicated: false`, `criticalErrorFree: null`
и `expectedGaps: null`. Ни один статус priority не означает, что метка утверждена.

## Rubric для RCB

`proposedRelation` относится к содержанию candidate **с сохранением указанного
`requiredFrame`**, а не к истинности события в реальном мире:

| Значение | Смысл |
| --- | --- |
| `supported-in-frame` | Содержание поддержано только в названной рамке: мнение, сообщение, предсказание или прямое утверждение рассказчика. |
| `not-established` | Из source такое содержание/время/модальность не установлены; это не автоматическое опровержение. |
| `ambiguous` | Несколько говорящих, эллипсис, scope или прагматика требуют adjudication. |
| `incompatible-in-same-episode` | Несовместимость предлагается только при совпадении эпизода и времени. |

**Это не переименование трёх NLI labels.** Upstream label хранится рядом для
review и не изменяется. Например, `supported-in-frame` для «он предполагает P»
не разрешает публиковать P как установленный факт. Метрику agreement с этими
полями нельзя сравнивать с upstream NLI accuracy без нового task contract.

`unqualifiedProjection: do-not-project` запрещает автоматическое снятие рамки.
`candidate-only-with-original-text-frame` у RCB-007/020 допускает предложенное
чтение как прямого утверждения рассказчика, с сохранением происхождения и
времени. **Ни одно значение не устанавливает фактическую достоверность.**

`adjudicationPriority: high` у 13 пар означает повышенный приоритет проверки
из-за ambiguity или заметного расхождения с upstream; это не число ошибок.
Все 24 пары ещё требуют human review перед утверждением reference labels.

## Attribution в судебных текстах

Каждый probe содержит `voice`, `safeReading`, `mustNotInfer` и exact anchor.
Роль — локальная для дела и стадии; **`ФИО` не является stable person ID**.
Просьба стороны, мнение прокурора, редакционная заметка, решение нижестоящего
суда и вывод текущего суда различаются. Отмена процессуального определения не
равна отмене штрафа. Отказ по давности не опровергает все утверждения по существу.

RCB anchors покрывают полные короткие premises; court anchors — только
выбранные фрагменты, которые нужно читать в контексте полного source.
Offsets: zero-based half-open `[start, end)`, `char` — Unicode code points,
`byte` — UTF-8. Это не JavaScript UTF-16 offsets; для UI требуется преобразование.

SUD-007/008 прямо обозначены upstream как «По материалам решения»: это дайджест,
а не сверенная официальная публикация. В SUD-002/003/004/009/010 замечены остаточные
идентификаторы, включая фамилии. Остальные источники имеют `privacyReview:
not-assessed`, а не «обезличено». Полная privacy/redaction проверка ещё нужна
перед использованием в открытом демо. Исходные артефакты не исправлялись.

## Лицензии и attribution

Цитаты происходят из закреплённых RCB (MIT) и sud-resh (upstream GPL-3.0)
snapshots. Сохраняются [notices, attribution и тексты лицензий](../external-diagnostics-v1/LICENSES.md).
Этот review не меняет лицензию исходных материалов и не добавляет их в runtime
приложения. Upstream provenance не равен сверке с первичной официальной публикацией.

## Проверка целостности

```sh
python3 -B -S evaluation/collect_external_diagnostics.py --check
python3 -B -S evaluation/check_external_diagnostic_review.py
```

Вторая команда проверяет hashes, 36 IDs, 50 probes, все 74 char/byte anchors,
сохранность upstream labels и candidate-only flags. **Она не проверяет смысл
разметки.** Новый semantic review/adjudication получает отдельную версию и lineage;
этот candidate snapshot не перезаписывается как якобы human gold.
