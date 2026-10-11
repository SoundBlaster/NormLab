# План повышения качества pipeline

Согласовано 2026-10-11. Цель — найти работающую стратегию разбора на доступных
моделях, а не составить рейтинг Jev/Luna. Модель, её роль и настройки являются
частью конфигурации pipeline. Более сложный вариант не считается полезным заранее.

## Этапы и результаты

| Этап | Объём | Работа | Критерий завершения |
| --- | --- | --- | --- |
| Development | 30–50 разнообразных исходных фабул | Разметка, каталог ошибок, проверка одной гипотезы за эксперимент | Для каждого включённого кейса проверены весь текст и rubric; сохранены ошибки, исправления и регрессии |
| Freeze | Одна выбранная конфигурация | Зафиксировать inputs contract, этапы, модели/роли, prompts, schema, scorer, routing, budget и selection record | Конфигурацию можно воспроизвести; quality labels не входят в model input |
| Holdout | 100 новых фабул | Однократная проверка выбранного pipeline без настройки по результатам | Независимая разметка и adjudication; полный denominator, ошибки и uncertainty опубликованы |
| Уточнение | По необходимости, ориентир 400 | Повысить точность оценки или исследовать оставшиеся типы ошибок | Отдельный заранее заданный протокол; не дописывать кейсы до желаемого результата |

30–50 — рабочий объём development, не доказательство статистической значимости.
100 — начальная цель untouched holdout, не гарантия достаточности для любого
вывода. При независимой репрезентативной binomial выборке и доле около 50%
планировочная погрешность двустороннего 95% interval составляет примерно ±10
процентных пунктов для 100 и ±5 для 400. [NIST: планирование размера выборки](https://www.itl.nist.gov/div898/handbook/ppc/section3/ppc333.htm).
Новостной или synthetic challenge set не становится representative от увеличения
размера. Фактический интервал рассчитывается по наблюдениям и sampling design.
Нет обязательной цели различить модели на несколько процентных пунктов.

## Что уже есть

[Проверяемый inventory](../fixtures/parking-pilot/pipeline-quality-v1/corpus-inventory.json):

| Набор | Текстов | Группировка | Граница доказательств |
| --- | ---: | --- | --- |
| Synthetic v1 | 40 | 8 authored contrast families, общие source inspirations | Частичные candidate probes; не полный gold case review |
| Stage 1 audit v2 | 16 | 13 declared families; 32 candidate records — производные, не новые фабулы | Представимость/верификация кандидатов и LLM review, не оценка всей extraction-цепочки |
| Editorial corpus | 15 | 10 source groups; incident dedup требует проверки | Пересказы, unlabelled; не оригинальные обращения |

Всего **71 текст с различными SHA256**, но число независимых кейсов **не
установлено**. Различные hashes не доказывают независимость. Общие происшествия,
страницы, шаблоны, переводы и парафразы объединяются до split; перекрёстная
семантическая дедупликация ещё нужна. Все три набора уже просмотрены при
разработке: eligible holdout сейчас **0**.

Входной pool позволяет начать диагностику сейчас. Он не закрывает автоматически
задачу 30–50 разнообразных, полностью размеченных development-фабул. Нужны отбор,
проверка coverage и добор новых сюжетов, а не размножение одного шаблона.

```sh
python3 -B -S evaluation/audit_pipeline_corpus.py --check
```

Команда проверяет исходные hashes и committed inventory без SDK, ключей и сети.
Она не проверяет семантическую независимость, корректность labels или полноту
разметки. При изменении входов inventory должен быть явно пересмотрен.

Отдельно собран [external diagnostic set v1](../fixtures/external-diagnostics-v1/README.md):
24 RCB NLI-пары и 12 полных судебных текстов. Сохранены dataset revisions,
upstream IDs, исходные hashes, licensing notices и deterministic selection recipe.
Labels RCB вынесены в reviewer-only файл и требуют проверки; судебные LLM-ответы
не используются как gold. Это development material для языковых diagnostics,
не 36 новых подтверждённо независимых parking-фабул. Его результаты не объединять
с доменным case-pass score без отдельного protocol. Holdout eligibility — 0.

## Единица оценки и rubric

Единица — вся исходная фабула с выбранным эпизодом и объявленным extraction scope.
Clauses, candidate mutations и повторные вызовы не добавляют независимые кейсы.
Полнота оценивается по всему исходному тексту, а не только по найденным моделью
утверждениям. Фактическую истинность рассказа и правильность юридического решения
этот этап не устанавливает.

Кейс не проходит automatic quality gate при любой критической ошибке:

1. Потеря/инверсия отрицания, modality или scope: «не утверждал, что оплатил» не
   превращается в «не оплатил» или «оплатил».
2. Выдуманное утверждение либо неподдержанная привязка к цитате.
3. Неверный speaker, участник, автомобиль, событие или эпизод.
4. Утрата противоречия либо слияние разных источников в установленный факт.
5. Превращение explicit unknown / not mentioned / ambiguous в false или true.
6. Пропуск значимого явно сообщённого обстоятельства либо необходимого для
   объявленного задания gap. Relevance gap задаётся rubric до inference;
   не требуется извлекать всю возможную юридическую онтологию.

Корректно сохранённая неопределённость и конкретный запрос уточнения могут быть
успехом для неполной фабулы. Универсальное «недостаточно данных», пустой ответ или
unsupported без оснований не получают автоматический pass. Structure/schema и
anchor validity проверяются отдельно; валидный JSON сам по себе не semantic pass.

Labels готовятся по source до просмотра ответов исследуемой конфигурации.
Для holdout два reviewer размечают независимо, разногласия сохраняются и проходят
adjudication. LLM может помогать reviewer, но её согласие с собственным ответом не
является независимой оценкой. Пока human review отсутствует, labels остаются
candidate и показатель полного quality gate не объявляется установленным.

## Метрики

**Основная:** usable automatic outputs без критических ошибок / все назначенные
кейсы. No output, provider failure и invalid schema не удаляются из denominator;
их технические причины показываются отдельно от ошибок понимания текста.
Неразмеченные outputs остаются `not-evaluated`, не получают pass; итоговый quality
score до полного review остаётся pending.

Дополнительно сохраняются:

- Критические ошибки по классам; исправленные кейсы и новые регрессии относительно
  baseline на тех же development-фабулах.
- Semantic result среди пригодных ответов и operational completion отдельно.
- First-attempt completion, retry recovery, все attempts, unknown outcomes/usage.
- Calls, semantic questions, known tokens, фактически доступная стоимость,
  latency и время ручного review. Отсутствующие данные — null.
- Число ручных правок, уточнений и итог после human review — отдельно от качества
  автоматического результата. Подтверждение пользователем не переписывает baseline.

50% кейсов без критических ошибок до ручной правки остаётся целью демо; 80% —
дальнейший ориентир. Наблюдаемые 50/100 не доказывают population quality ≥50%.
До любых population claims отдельно фиксируются sampling frame и confidence rule.

## Первый development-эксперимент

[Стартовый каталог ошибок](PIPELINE_ERROR_CATALOGUE.md) связывает наблюдения
с конкретными входами и этапами; он ещё не заменяет полного review корпуса.

Начать с **S1.3 task decomposition** из [roadmap экспериментов](EXTRACTION_EXPERIMENT_ROADMAP.md):
сравнить общий candidate judgment с локальными проверками polarity/scope,
attribution и source support; source-only reconstruction — отдельный arm.
Это диагностика verifier, не автоматический end-to-end extraction benchmark.

- Сохранить текущий whole-task baseline, source/candidates и definitions.
- На одном доступном provider/model зафиксировать semantic task, контекст и
  budgets; менять постановку проверки, а не одновременно модель и pipeline.
  Применимость к другим компонентам проверяется позднее, если есть польза.
- Подготовить labels и error locations; отдельно учитывать представимость
  отрицания speech act, ambiguity и explicit unknown. Невыразимый случай не
  принуждать к текущей schema.
- До inference заморозить versioned manifest и call/question/token caps. Сначала
  offline contract/replay, затем отдельное live-разрешение; этот план новых
  платных вызовов не авторизует.
- По итогам сохранить supported / contradicted / inconclusive с исправлениями,
  false acceptance/rejection, coverage, regressions и затратами. Без улучшения
  не добавлять этап в основной pipeline.

Если diagnostics оправдают изменение extraction, следующий отдельный эксперимент
— существующий 2×2 ablation indexed spans × minimal claim IR. Отдельное выделение
утверждений и scope — гипотеза; классический parser, LangExtract, augmentation и
Mellea repair не добавляются одновременно. Full pipeline проверяется снова,
поскольку улучшение verifier не доказывает улучшения extraction.

## Holdout и freeze

После development выбрать минимальный достаточный вариант и сохранить selection
record. Final holdout не используется для выбора из трёх моделей или тактик:
проверяется выбранная полная конфигурация. При смене доступной модели/provider
конфигурация получает новую версию, совместимость проверяется отдельно.

100 новых исходных фабул собираются после freeze, отдельно от development
families/source pages/templates. Синтетические варианты и реальные обращения
маркируются отдельно; отсутствие популяционной выборки явно ограничивает вывод.
Inputs, reviewer-only labels и predictions хранятся раздельно. Разработчик
pipeline не использует holdout inputs/labels для examples, отладки и repair prompt.

Количество API-запросов определяется выбранной цепочкой: 100 кейсов × её этапы
и вопросы плюс реально разрешённые retries. **300 запросов не обязательны**:
одновременный прогон всех трёх моделей не является целью final evaluation.

Если после просмотра final test меняются prompts, stages или policy, этот test
становится development evidence. Для новой итоговой оценки нужен новый untouched
набор. Расширение до 400 и правила остановки задаются до следующего сбора/запуска,
а не по желанию получить нужный score. MLflow регистрирует версии и результаты;
Evidently добавляется только при конкретной пользе, не как источник ground truth.

## Следующие deliverables

- [x] Зафиксировать согласованный порядок и inventory исходного pool.
- [x] Подготовить [candidate review внешних diagnostics](EXTERNAL_DIAGNOSTIC_REVIEW_2026-10-12.md): 24 RCB пары и 50 targeted attribution probes; content, attribution, scope и projection разделены. Это не полная разметка доменных фабул и не human gold.
- [ ] Adjudicate спорные external readings; сохранить upstream labels и independent reviewer decisions отдельно, не объединять NLI и parking quality denominators.
- [ ] Каталог ошибок и полнота reviewer rubric для 30–50 выбранных development-фабул.
- [ ] Versioned S1.3 manifest, локальные questions, source-only arm и offline contract.
- [ ] Разрешённый development experiment и полный отчёт, затем решение об extraction ablation.
- [ ] Freeze выбранного pipeline; собрать и независимо разметить 100 новых holdout-фабул.
