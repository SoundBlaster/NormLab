# External diagnostic corpus v1

Собран 2026-10-11 для development стратегии extraction/verification.
**36 входов: 24 RCB и 12 исходных судебных текстов.** Это отдельный набор;
существующий inventory из 71 текста не переписан. Ни один вход не является
untouched holdout. Число независимых происшествий/дел не установлено.

## Файлы

- [inputs.jsonl](inputs.jsonl) — все входы в одном файле: `id`, `sourceText`,
  для RCB также `candidateText`. Здесь нет labels, жанров, категорий и ответов.
- [texts/](texts/) — те же исходные тексты как читаемые `.source.txt`, без
  добавления перевода строки или иной нормализации.
- [manifest.json](manifest.json) — provenance каждого входа: dataset, upstream
  ID, split, хеш исходного текста/кандидата/канонического upstream record,
  exact-text group, лицензия и путь к тексту.
- [upstream-sources.json](upstream-sources.json) — URL загрузки, repository
  revisions, SHA256 исходных файлов, attribution и evidence лицензий.
- [reviewer-annotations.jsonl](reviewer-annotations.jsonl) — **reviewer only**:
  исходные метки RCB и поля будущего review. `expectedClaims`, `expectedGaps`
  и `criticalErrorFree` пока `null`. Не передавать этот файл модели.
- [upstream/](upstream/) — неизменённые dataset cards на закреплённых revisions.
- [LICENSES.md](LICENSES.md) и [licenses/](licenses/) — notices и тексты лицензий.

## Откуда взяли и как выбрали

### RCB — 24 пары

[Russian SuperGLUE / Russian Commitment Bank](https://russiansuperglue.com/tasks/task_info/RCB),
[авторский HF repository](https://huggingface.co/datasets/RussianNLP/russian_super_glue).
Revision `53cb9d7f38b34c308a2eea3f4797f9edc7947d8b`, архив `data/RCB.zip`,
**только `RCB/train.jsonl`**. Validation/test не включены.

По восемь upstream labels `entailment`, `contradiction`, `neutral`; внутри
каждого класса четыре `negation` и четыре `no_negation` по upstream metadata.
Это целевые diagnostic quotas, не частоты естественных обращений. Поле
`negation` — разметка авторов, не результат нашего поиска слова «не».
Внутри каждой страты порядок задаёт SHA256 фиксированного seed и канонического
upstream JSON. Повторные exact premise hashes исключены.

`premise` скопирован в `sourceText`, `hypothesis` — в `candidateText`, дословно.
Остальная upstream metadata находится отдельно. Исходные labels сохранены без
исправлений; некоторые пары при первичном чтении выглядят спорно. Их семантика
и корректность требуют ручного review. Upstream NLI label не является полным
NormLab case-pass label и не устанавливает истинность рассказа.

### Судебные тексты — 12 источников

[lawful-good-project/sud-resh-benchmark](https://huggingface.co/datasets/lawful-good-project/sud-resh-benchmark),
revision `b51684df64fbc13094fa0448c3ad27c3dcef950a`, файл
`sud_resh_benchmark.json`. Взято **поле `source`**, а не LLM-пересказ `text`.
`correct_answer` не используется и не импортируется как gold.

Квоты по upstream category: шесть `sud_resh_admin_pravo`, три
`sud_resh_grazhd_pravo`, три `sud_resh_fin_pravo`. Ограничение длины до отбора:
1500–20000 Unicode characters. Тексты не обрезаются. Группируем все 7000 строк
по SHA256 поля `source`; связанные задания одного exact source перечислены в
`relatedUpstreamRows` с ID и JSON pointers. Внутри каждой категории выбираем
первые группы по hash-order с тем же seed. Representative upstream record —
наименьший ID в группе; его canonical JSON hash сохранён для восстановления.

Авторы называют источники анонимизированными. В них заметны артефакты замены
имён, включая «ФИО Федерации»; мы их не исправляли. Privacy и linguistic review
ещё нужны. Категория «административное право» не означает автоматически КоАП,
Москву или платную парковку. Это материал для attribution, аргументов сторон и
длинного контекста; не готовый benchmark нашего юридического пилота.

Судебный исход присутствует в полном документе как часть source. Поэтому набор
не пригоден для blind prediction исхода дела без отдельного input contract.
Историческое решение не доказывает актуальное состояние права.

## Границы provenance и оценки

Для каждого входа можно восстановить dataset artifact и строку/поле. Upstream
данные не дают URL первичной новости или официальной публикации каждого акта:
`originDocumentUrl: null` означает **не установлено**, а не «официально сверено».
Даты/номера дел остаются внутри оригинального source; URL по ним не выдумываем.

Exact dedup выполнен. Семантические повторы, разные стадии одного дела и связи
с прежними 71 текстом требуют manual cross-corpus dedup. Разные hashes не
доказывают независимость. Публичные тексты могли входить в обучение моделей;
training exposure неизвестна. Не использовать этот набор для population claims
или итоговой holdout-оценки 50%/80%.

Отбор exploratory: quotas отрицаний уточнены после первичного просмотра RCB,
до любого inference. Ни одного model output для выбора не использовали.
Следующий этап — source-first reviewer rubric и adjudication, затем versioned
S1.3 questions на утверждённых примерах. Общие NLI diagnostics и доменные
parking cases должны иметь отдельные denominators.

## Воспроизведение без inference

Offline integrity check (stdlib; без SDK, ключей и сети):

```sh
python3 -B -S evaluation/collect_external_diagnostics.py --check
```

Повторный сбор с загрузкой закреплённых публичных файлов (~215 MB):

```sh
python3 -B -S evaluation/collect_external_diagnostics.py \
  --fetch --cache .artifacts/external-corpus-upstream-v1 \
  --output .artifacts/external-diagnostics-v1-rebuilt
```

Без `--fetch` используются только уже скачанные файлы cache. Builder проверяет
все upstream SHA256, не перезаписывает существующий набор и не запускает LLM.
Canonical record hash: UTF-8 JSON, `ensure_ascii=False`, `sort_keys=True`,
`separators=(',', ':')`. Source/candidate hash: UTF-8 самого поля без нормализации.
Snapshot checks проверяют целостность и квоты, а не correctness labels или
семантическую независимость. Исходные архив/JSON хранятся только в ignored cache.
Локальный `.gitattributes` сохраняет bytes snapshots при checkout; исходные
пробелы dataset cards не исправляются форматтером ради совпадения SHA256.
