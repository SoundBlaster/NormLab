# Parking corpus: сбор и статистические границы

## Цель

80% кейсов без критических ошибок extraction **до human correction**. Legal correctness, statement gate и graph gate — отдельные показатели. Текущие четыре P-cases и новый [source discovery pack](../fixtures/parking-pilot/corpus/README.md) являются development material.

## Этапы

1. **Discovery:** источники и происхождение, privacy, scope, dedup. Начальный результат: 15 source leads, 10 editorial candidate narratives из пяти страниц; labels отсутствуют.
2. **Development corpus, 30–50 cases:** semantic разметка, adjudication и отладка rubric. Подготовлены 40 synthetic inputs и 15 editorial source candidates. Проверка соответствия пересказа входному тексту и dedup нужны; доказанность реального происшествия для extraction-тестов не нужна. Synthetic controls маркируются отдельно.
3. **Freeze:** зафиксировать definitions, prompts, model/configuration, scorer, стоимость критических ошибок и acceptance rule.
4. **Independent evaluation:** новый набор, собранный после freeze и не использованный в prompts, examples или ручной отладке. Отдельный adjudicated gold хранится вне model input.

Синтетический development corpus уже собран; independent holdout ещё нет. Разметка оценивает faithful extraction и конкретные gaps, а не историческую истинность событий. Корректная нехватка данных для суждения может быть ожидаемым успехом.

## Development coverage (план на 40, не статистические веса)

| Тема | План |
|---|---:|
| Явная неоплата / полноценная заявленная оплата | 8 |
| Ошибочный автомобиль, номер, зона и исправления | 8 |
| Время платежа, интервал, продление и отъезд | 8 |
| Разрешения, льготы и условия их применения | 6 |
| Сбои и альтернативные каналы оплаты | 4 |
| Несколько эпизодов, противоречия и attribution | 4 |
| Явно неподдержанный город/тип парковки | 2 |

Темы пересекаются: назначается одна primary stratum и дополнительные tags. Не изобретать недостающие обстоятельства реального эпизода ради квоты. Если тема остаётся пустой, сообщать о пробеле coverage. Процессуальные стадии и исполнительное производство сохранять как noise/unsupported, не расширять текущую онтологию автоматически.

## Правила источников

- Новости: полезны для natural language и необычных ситуаций, но дают selection bias в сторону споров и ошибок. По ним нельзя оценить частоту успеха на всех обращениях.
- Судебные акты: case ID и официальный ресурс полезны для provenance и исследования права; официальная сверка не блокирует использование текста как extraction input. Отличать довод заявителя, установленное судом обстоятельство и правовую оценку. Решение суда не является gold label extraction автоматически.
- Официальные сводки: проверка тем и масштабов, не индивидуальные фабулы. Число упомянутых нарушений нельзя превращать в размер нашей выборки без текстов каждого эпизода.
- FAQ: context и идеи для separately labelled synthetic cases; не происшествие и не самостоятельная нормативная публикация.
- Рассказы читателей: unverified reports, useful linguistic material. Сохранять uncertainty и attribution, не распространять имена/номера; не назначать Москву при неизвестной географии.
- Historical events: дата события отдельно от публикации/обновления. В extraction наборе допустимы, legal outcomes требуют действовавшей тогда редакции норм. Не применять сегодняшние правила исправления платежа задним числом.

## Независимость и holdout

До split объединять по incident: все судебные стадии, перепечатки и варианты пересказа в одной группе. Дополнительно не разделять одну discussion page между development и evaluation. Близость фактов и текстов проверять вручную; SHA256 ловит только точные повторы.

Несколько model runs на одном input оценивают stability, не добавляют независимые случаи. Несколько clauses одного case не добавляют наблюдения в case-level metric. Cluster dependence надо учитывать при интервалах и сравнении; 250 производных текстов от нескольких эпизодов не дают эффективную выборку 250.

## Разметка

Два reviewer сначала независимо отмечают explicit facts, polarity, subjects/vehicles/episodes, source support, unknowns и contradictions. Для extraction юридическая экспертиза не заменяет внимательную linguistic разметку; для состава/последствий нужен юрист. Labels готовить до просмотра model output. Разногласия обсуждать и adjudicate, сохраняя исходные версии.

Reviewer-only metadata: legal outcome, normative references и темы контроля не передаются extractor. В input только source narrative и общий contract. Редакционный пересказ и оригинальная фабула получают разные textOrigin; их scores не смешиваются без явно определённой population.

## Статистический план

При независимой репрезентативной binomial выборке и ожидаемой доле 0.8 приближённое планирование двустороннего 95% interval даёт около 62 случаев для ±10 pp и 246 для ±5 pp (`n ≈ 1.96² × 0.8 × 0.2 / margin²`). Это ориентир **точности оценки**, не универсальное число для statistical significance и не доказательство достижения порога 80%. [NIST: confidence intervals](https://itl.nist.gov/div898/handbook/prc/section2/prc241.htm), [sample size planning](https://www.itl.nist.gov/div898/handbook/prc/section2/prc242.htm).

Для release threshold заранее определить one-sided lower confidence bound и допустимые отдельные critical-error classes. Для сравнения pipelines — одинаковые случаи, paired binary outcomes, минимальный полезный прирост и power calculation. Выбор final test и adjustment при множестве конфигураций зафиксировать до evaluation. Одних 80% наблюдаемых successes недостаточно, чтобы уверенно утверждать population success ≥80%.

Новостной challenge corpus отчётно измеряет качество **на этом корпусе**. Для population claim нужен sampling frame обычных обезличенных обращений: consented volunteer narratives или последовательный сбор по заранее заданным условиям, включая простые и успешные эпизоды. Сейчас таких данных нет. Набор 250 новостей сам по себе selection bias не устраняет.

## Следующий ход

Review labels для 40 synthetic inputs и 15 editorial candidates, включая expected gaps и корректное abstention. Не ждать доказательства реальных событий. После rubric freeze собрать независимый dataset; model improvements оценивать отдельно от текущих diagnostic sets.
