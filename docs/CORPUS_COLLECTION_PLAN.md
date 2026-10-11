# Parking corpus: сбор и статистические границы

## Цель

80% кейсов без критических ошибок extraction **до human correction**. Legal correctness, statement gate и graph gate — отдельные показатели. Текущие четыре P-cases и новый [source discovery pack](../fixtures/parking-pilot/corpus/README.md) являются development material.

## Этапы

1. **Discovery:** источники и происхождение, privacy, scope, dedup. Начальный результат: 15 source leads, 10 editorial candidate narratives из пяти страниц; labels отсутствуют.
2. **Development corpus, 30–50 cases:** semantic разметка, adjudication и отладка rubric. Подготовлены 40 synthetic inputs и 15 editorial source candidates. Проверка соответствия пересказа входному тексту и dedup нужны; доказанность реального происшествия для extraction-тестов не нужна. Synthetic controls маркируются отдельно.
3. **Validation и selection:** сравнить конфигурации на отдельном validation split; final test и его labels недоступны для выбора, настройки и ручной отладки.
4. **Frozen selection:** зафиксировать выбранный pipeline, definitions, prompts/schema, model/configuration, scorer, стоимость критических ошибок, acceptance rule и budget в selection record.
5. **Independent final test:** один раз оценить выбранный вариант на untouched наборе, собранном после freeze и не использованном в prompts, examples или ручной отладке. Отдельный adjudicated gold хранится вне model input. Изменения по результатам final test делают его development evidence и требуют нового untouched test для следующего final score.

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

[External diagnostic set v1](../fixtures/external-diagnostics-v1/README.md) добавляет
24 RCB пары (MIT) и 12 полных судебных source texts (upstream GPL-3.0). Provenance,
revisions, raw artifact hashes и per-record IDs закреплены; labels отделены от
model inputs. Набор предназначен для development диагностики, не holdout и не
замены 30–50 полностью размеченных доменных фабул. Primary publication URLs
не предоставлены upstream и помечены как неизвестные. Incident/semantic dedup
и human rubric review остаются обязательными следующими шагами.

- Новости: полезны для natural language и необычных ситуаций, но дают selection bias в сторону споров и ошибок. По ним нельзя оценить частоту успеха на всех обращениях.
- Судебные акты: case ID и официальный ресурс полезны для provenance и исследования права; официальная сверка не блокирует использование текста как extraction input. Отличать довод заявителя, установленное судом обстоятельство и правовую оценку. Решение суда не является gold label extraction автоматически.
- Официальные сводки: проверка тем и масштабов, не индивидуальные фабулы. Число упомянутых нарушений нельзя превращать в размер нашей выборки без текстов каждого эпизода.
- FAQ: context и идеи для separately labelled synthetic cases; не происшествие и не самостоятельная нормативная публикация.
- Рассказы читателей: unverified reports, useful linguistic material. Сохранять uncertainty и attribution, не распространять имена/номера; не назначать Москву при неизвестной географии.
- Historical events: дата события отдельно от публикации/обновления. В extraction наборе допустимы, legal outcomes требуют действовавшей тогда редакции норм. Не применять сегодняшние правила исправления платежа задним числом.

## Независимость и holdout

До split объединять по incident: все судебные стадии, перепечатки и варианты пересказа в одной группе. Дополнительно не разделять одну discussion page между development, validation и final test. Близость фактов и текстов проверять вручную; SHA256 ловит только точные повторы.

Несколько model runs на одном input оценивают stability, не добавляют независимые случаи. Несколько clauses одного case не добавляют наблюдения в case-level metric. Cluster dependence надо учитывать при интервалах и сравнении; 250 производных текстов от нескольких эпизодов не дают эффективную выборку 250.

## Разметка

Два reviewer сначала независимо отмечают explicit facts, polarity, subjects/vehicles/episodes, source support, unknowns и contradictions. Для extraction юридическая экспертиза не заменяет внимательную linguistic разметку; для состава/последствий нужен юрист. Labels готовить до просмотра model output. Разногласия обсуждать и adjudicate, сохраняя исходные версии.

Reviewer-only metadata: legal outcome, normative references и темы контроля не передаются extractor. В input только source narrative и общий contract. Редакционный пересказ и оригинальная фабула получают разные textOrigin; их scores не смешиваются без явно определённой population.

## Статистический план

Текущий согласованный порядок: [30–50 development-фабул → freeze → 100 новых
holdout-фабул](PIPELINE_QUALITY_PLAN.md), ориентир 400 только при необходимости
повысить точность. При доле около 50% планировочная погрешность 95% interval —
примерно ±10 pp для 100 и ±5 pp для 400 при независимой репрезентативной выборке.
100 не является универсальным числом для statistical significance. Пример с
0.8 ниже относится к дальнейшему ориентиру, а не к нынешней цели демо.

При независимой репрезентативной binomial выборке и ожидаемой доле 0.8 приближённое планирование двустороннего 95% interval даёт около 62 случаев для ±10 pp и 246 для ±5 pp (`n ≈ 1.96² × 0.8 × 0.2 / margin²`). Это ориентир **точности оценки**, не универсальное число для statistical significance и не доказательство достижения порога 80%. [NIST: confidence intervals](https://itl.nist.gov/div898/handbook/prc/section2/prc241.htm), [sample size planning](https://www.itl.nist.gov/div898/handbook/prc/section2/prc242.htm).

Для release threshold заранее определить one-sided lower confidence bound и допустимые отдельные critical-error classes. Для сравнения pipelines — одинаковые случаи, paired binary outcomes, минимальный полезный прирост и power calculation. Splits и критерии selection зафиксировать до comparison; выбор конфигурации выполнять на development/validation. Frozen selection проверяется один раз на untouched final test; его score не выбирает победителя. Одних 80% наблюдаемых successes недостаточно, чтобы уверенно утверждать population success ≥80%.

Новостной challenge corpus отчётно измеряет качество **на этом корпусе**. Для population claim нужен sampling frame обычных обезличенных обращений: consented volunteer narratives или последовательный сбор по заранее заданным условиям, включая простые и успешные эпизоды. Сейчас таких данных нет. Набор 250 новостей сам по себе selection bias не устраняет.

## Следующий ход

Review labels для 40 synthetic inputs и 15 editorial candidates, включая expected gaps и корректное abstention. Не ждать доказательства реальных событий. Подготовить validation split для выбора pipeline; после frozen selection собрать untouched final test. Текущие diagnostic sets остаются development.
