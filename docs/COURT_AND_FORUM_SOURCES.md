# Court и forum discovery — 2026-10-05

## Судебные материалы

Открылись два текста актов именно по делам об административных правонарушениях, содержащие парковочную статью 8.14 КоАП Москвы:

- [Мосгорсуд, 7-21539/2022, 09.12.2022](https://zakony.online/doc/7-215392022-%D1%80%D0%B5%D1%88%D0%B5%D0%BD%D0%B8%D0%B5/): физическое лицо; первоначальное вменение и процессуальная оценка фиксации различаются. C15 передаёт содержание первоначального постановления, не установленную неоплату.
- [Мосгорсуд, 7-4640/2022, 31.03.2022](https://zakony.online/doc/7-46402022-%D1%80%D0%B5%D1%88%D0%B5%D0%BD%D0%B8%D0%B5/): организация, вне personal-car scope пилота. Оставлен как lead.

Это зеркала. Их ссылка на официальный сайт как происхождение документа не означает, что мы сверили официальный экземпляр. Хранить case ID, дату, allegations, findings и reasoning отдельно. Disposition не является автоматическим extraction gold.

## Официальные маршруты

| Маршрут | Результат web retrieval |
|---|---|
| [Мосгорсуд, поиск](https://mos-gorsud.ru/search) | Timeout |
| [Симоновский суд, карточка 12-0692/2021](https://mos-gorsud.ru/rs/simonovskij/services/cases/appeal-admin/details/c77fea00-11d4-11eb-8bea-018a80b0988a) | Найдена через сторонний index; open failed |
| [ГАС «Правосудие», BSR](https://bsr.sudrf.ru/bigs/portal.html) | Open failed; поиск не выполнен |
| [ВС, электронная справочная](https://www.vsrf.ru/lk/practice) | Landing page открылась; конкретный акт не получен |

Ошибки не доказывают закрытие базы или отсутствие категории дел. Полнота индекса, bulk export/API и стабильность доступа не подтверждены. Следующий способ — interactive browser search по case ID/article и опубликованным PDF.

Искать «дела об административных правонарушениях», а не ограничиваться административными исками. Для нашего corpus ключи: 8.14, АМПП, неоплата/оплата парковки. Исторические нормы не заменять текущим FAQ.

## Форумы

- [Roads.ru: номер машины супруги](https://roads.ru/forum/topic/40126-shvatil-shtraf-za-parkovku-na-platnom-meste-oplatil-no-dopustil-oshibku-v-nomere/): C11, vehicle/driver/owner attribution.
- [Polo forum: отсутствие знаков](https://polosedan.ru/forum/viewtopic.php?f=24&t=13916): C12, заявленное наблюдение и несколько стоянок.
- [Правовед: формат номера](https://pravoved.ru/question/1780587/): C13, деньги из депозита и предполагаемое поведение приложения.
- [Mom.life: дистанционная оплата](https://mom.life/post/68af31038ebe295a171b7e95-devochki-kto-znaet-kak-otmenit): C14, разные payer/driver и сообщённое время отъезда.

Короткие обезличенные paraphrases и ссылки добавлены в [registry](../fixtures/parking-pilot/corpus/README.md). Это unverified reports, не установленные факты или принятые системой юридические советы. Replies, повторные цитаты и обновления одного эпизода не считать независимыми cases. Thread держать в одной split group; имена/номера не передавать extractor.

Forum complaints также имеют selection bias. [40 synthetic inputs](../fixtures/parking-pilot/synthetic-v1/README.md) хранятся отдельно от editorial real-source candidates; labels не передаются модели.
