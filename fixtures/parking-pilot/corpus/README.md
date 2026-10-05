# Source discovery corpus — 2026-10-05

**Статус: discovery / development, unlabelled. Не gold, не holdout.**

Собраны 15 source leads и 10 коротких editorial paraphrases из пяти source pages. Это не десять проверенных независимых происшествий. Публикации просмотрены человеком-агентом через web retrieval; источники с failed open отмечены отдельно и не использованы для создания фабул. Search snippet не заменяет полный судебный акт.

- [sources.json](sources.json): URL, дата публикации (null, если не установлена), дата просмотра, тип, доступность и ограничения.
- [manifest.json](manifest.json): происхождение фабулы, locator, source/incident groups, hash файла, jurisdiction evidence, статус labels.
- `Cxx.source.txt`: обезличенный краткий пересказ фактов/утверждений. Это **написанный нами input**, не дословная публикация и не оригинальный рассказ пользователя. Hash подтверждает именно этот файл, не remote page.

СМИ и читательские рассказы фиксируют заявленные обстоятельства, не устанавливают их истинность. Отдельная редакционная рекомендация не включена в input как факт эпизода. Legal outcome не размечен. Официальные FAQ/news используются как context или aggregate, не как отдельные происшествия и не как normative lock.

## Источники

| ID | Материал | Использование |
|---|---|---|
| S01 | [РАПСИ, сообщение о другом автомобиле](https://rapsinews.ru/judicial_news/20260526/311876981.html) | C01; первичный акт ещё не найден |
| S02 | [Autonews, опечатка в СМС](https://www.autonews.ru/amp/news/64faea299a7947215ab536fb) | C02; сообщение адвоката |
| S03 | [Т—Ж, вопрос и комментарии](https://t-j.ru/ask/shtraf-za-parkovku/) | C03–C07; неподтверждённые рассказы |
| S04 | [Т—Ж, задержка пополнения](https://t-j.ru/delayed-payment/) | C08; город не указан |
| S05 | [Т—Ж, сбой оплаты](https://t-j.ru/parking-payment-failed/) | C09–C10; разные части страницы, не один эпизод |
| S06 | [АМПП, сводка СМС-сбоев](https://parking.mos.ru/news/2123/) | Aggregate; не размножать в 24 кейса |
| S07 | [РБК, сбой 22 июля 2026](https://www.rbc.ru/technology_and_media/22/07/2026/6a60d0589a7947529b7eb68b) | Open failed; lead, не готовая фабула |
| S08 | [РАПСИ, обзор десяти дел](https://rapsinews.ru/judicial_analyst/20200521/305826398.html) | Aggregate; нужны отдельные акты, часть scope процедурная |
| S09 | [Дело 7-3319/2024](https://base.garant.ru/339197988/) | Full open 403; требуется официальный акт |
| S10 | [Дело 7-2271/2026](https://base.garant.ru/470539167/) | Full open 403; требуется dedup с другими сообщениями |
| S11 | [Дело 5-АД18-55](https://base.garant.ru/72069970/) | Full open failed; исторический lead |
| S12 | [Дептранс, разрешения](https://transport.mos.ru/parking/parking_permit) | Context |
| S13 | [Дептранс, оплата](https://transport.mos.ru/parking/aboutparking/pay_parking) | Context, просмотрен search result |
| S14 | [Дептранс, задолженности](https://transport.mos.ru/mostrans/all_news/130287) | Aggregate, open failed |
| S15 | [ГАРАНТ, условия знаков](https://www.garant.ru/news/1186980/) | Другой состав; discovery context |

## Перед разметкой

1. Сверить каждый пересказ с source locator: не добавлены ли город, личное использование, вина, отсутствие льгот или точное время.
2. Пометить scope: Москва явно; Москва только косвенно; место неизвестно; другой город. Не подставлять Москву по сумме штрафа или по теме страницы.
3. Разметить **содержание утверждений** с цитатами к нашему input, отдельно от фактической истинности события и правового результата.
4. Второй reviewer независимо отмечает coverage, predicate, polarity, attribution, unknowns и contradictions. Разногласия сохраняются до adjudication.
5. Назначить incident groups после dedup. Один эпизод, его судебные стадии, перепечатки и synthetic варианты не являются независимыми наблюдениями.

## Дальнейший набор

Методика и квоты: [CORPUS_COLLECTION_PLAN.md](../../../docs/CORPUS_COLLECTION_PLAN.md). Эти материалы уже просмотрены при проектировании и не могут стать чистым holdout. Не запускать на них текущий четырёхкейсный evaluator без отдельного dataset/labels contract: его expectations относятся только к P01/P02/P04/P09.

Полные copyrighted статьи и комментарии не скопированы; сохранены ссылки и краткие пересказы, без имён и регистрационных знаков. Перед распространением raw originals нужно отдельно проверить права использования. Editorial paraphrases проверяют также наш стиль пересказа; качество на оригинальных пользовательских текстах измеряется отдельным набором.
