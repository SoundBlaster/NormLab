# Development casebook — candidate review v1

45 existing inputs; whole-text candidate readings, not independent human gold.
All examples are development-only; no pipeline outputs scored.
The headings and notes are reviewer-only, not model input.

## DEV001 — synthetic-v1/SYN001

> В Москве я оставил автомобиль на городской парковке. Парковку оплатил через приложение.

### Candidate readings

- Место парковочного эпизода явно связано с Москвой.
- Городской тип парковки прямо указан; платность из этого не следует.
- Рассказчик сообщает об успешной оплате через приложение.

### Candidate followups (apply requiredWhen from JSON)

- eventDate [exact-day-not-stated]: Какова полная дата выбранной стоянки?
- placementInterval [full-standing-interval-not-stated]: Когда началась и закончилась выбранная стоянка? Не заменять временем платежа или уведомления.
- paidRegime [not-established-for-event-interval]: Какой режим действовал в этот период? Отсутствие разрешения или факт оплаты не отвечают на этот вопрос.

Independent review: pending. Automatic output review: not started.

## DEV002 — synthetic-v1/SYN002

> В Москве я оставил автомобиль на городской парковке. Парковку не оплачивал.

### Candidate readings

- Место парковочного эпизода явно связано с Москвой.
- Городской тип парковки прямо указан; платность из этого не следует.
- Рассказчик отрицает собственную оплату этой парковки; это не утверждение, что никто другой не платил.

### Candidate followups (apply requiredWhen from JSON)

- eventDate [exact-day-not-stated]: Какова полная дата выбранной стоянки?
- placementInterval [full-standing-interval-not-stated]: Когда началась и закончилась выбранная стоянка? Не заменять временем платежа или уведомления.
- paidRegime [not-established-for-event-interval]: Какой режим действовал в этот период? Отсутствие разрешения или факт оплаты не отвечают на этот вопрос.

Independent review: pending. Automatic output review: not started.

## DEV003 — synthetic-v1/SYN003

> В Москве я оставил автомобиль на городской парковке. Не знаю, прошла ли оплата.

### Candidate readings

- Место парковочного эпизода явно связано с Москвой.
- Городской тип парковки прямо указан; платность из этого не следует.
- Рассказчик явно не знает, прошла ли оплата; ни успех, ни неуспех не установлен.

### Candidate followups (apply requiredWhen from JSON)

- eventDate [exact-day-not-stated]: Какова полная дата выбранной стоянки?
- placementInterval [full-standing-interval-not-stated]: Когда началась и закончилась выбранная стоянка? Не заменять временем платежа или уведомления.
- paidRegime [not-established-for-event-interval]: Какой режим действовал в этот период? Отсутствие разрешения или факт оплаты не отвечают на этот вопрос.
- paymentOutcome [explicit-unknown]: Что известно о результате оплаты именно выбранной стоянки?

Independent review: pending. Automatic output review: not started.

## DEV004 — synthetic-v1/SYN004

> В Москве я оставил автомобиль на городской парковке. Я оплатил первый час, второй час не оплачивал.

### Candidate readings

- Место парковочного эпизода явно связано с Москвой.
- Городской тип парковки прямо указан; платность из этого не следует.
- Рассказчик оплатил первый час.
- Рассказчик не оплатил второй час; интервалы нельзя слить в полностью оплаченную либо полностью неоплаченную стоянку.

### Candidate followups (apply requiredWhen from JSON)

- eventDate [exact-day-not-stated]: Какова полная дата выбранной стоянки?
- placementInterval [full-standing-interval-not-stated]: Когда началась и закончилась выбранная стоянка? Не заменять временем платежа или уведомления.
- paidRegime [not-established-for-event-interval]: Какой режим действовал в этот период? Отсутствие разрешения или факт оплаты не отвечают на этот вопрос.

Independent review: pending. Automatic output review: not started.

## DEV005 — synthetic-v1/SYN005

> В Москве я оставил автомобиль на городской парковке. Оплату не отменял; парковку оплатил.

### Candidate readings

- Место парковочного эпизода явно связано с Москвой.
- Городской тип парковки прямо указан; платность из этого не следует.
- Рассказчик отрицает отмену оплаты.
- Отдельно положительно утверждает оплату парковки; отрицание относится к отмене.

### Candidate followups (apply requiredWhen from JSON)

- eventDate [exact-day-not-stated]: Какова полная дата выбранной стоянки?
- placementInterval [full-standing-interval-not-stated]: Когда началась и закончилась выбранная стоянка? Не заменять временем платежа или уведомления.
- paidRegime [not-established-for-event-interval]: Какой режим действовал в этот период? Отсутствие разрешения или факт оплаты не отвечают на этот вопрос.

Independent review: pending. Automatic output review: not started.

## DEV006 — synthetic-v1/SYN006

> В Москве я припарковал автомобиль А на городской парковке. Платёж прошёл за автомобиль Б, который тоже принадлежит мне.

### Candidate readings

- Место парковочного эпизода явно связано с Москвой.
- Городской тип парковки прямо указан; платность из этого не следует.
- На городской парковке размещён автомобиль А.
- Платёж прошёл за автомобиль Б; оба автомобиля принадлежат рассказчику.
- Платёж за Б не подтверждает оплату А; самостоятельная оплата А не сообщена.

### Candidate followups (apply requiredWhen from JSON)

- eventDate [exact-day-not-stated]: Какова полная дата выбранной стоянки?
- placementInterval [full-standing-interval-not-stated]: Когда началась и закончилась выбранная стоянка? Не заменять временем платежа или уведомления.
- paidRegime [not-established-for-event-interval]: Какой режим действовал в этот период? Отсутствие разрешения или факт оплаты не отвечают на этот вопрос.
- paymentForParkedVehicle [not-mentioned]: Есть ли сведения об оплате именно размещённого автомобиля?

Independent review: pending. Automatic output review: not started.

## DEV007 — synthetic-v1/SYN007

> В Москве я припарковал автомобиль А на городской парковке. Оплатил именно автомобиль А, а не автомобиль Б.

### Candidate readings

- Место парковочного эпизода явно связано с Москвой.
- Городской тип парковки прямо указан; платность из этого не следует.
- Размещён автомобиль А.
- Рассказчик оплатил именно А, а не Б; отрицание относится к объекту платежа Б.

### Candidate followups (apply requiredWhen from JSON)

- eventDate [exact-day-not-stated]: Какова полная дата выбранной стоянки?
- placementInterval [full-standing-interval-not-stated]: Когда началась и закончилась выбранная стоянка? Не заменять временем платежа или уведомления.
- paidRegime [not-established-for-event-interval]: Какой режим действовал в этот период? Отсутствие разрешения или факт оплаты не отвечают на этот вопрос.

Independent review: pending. Automatic output review: not started.

## DEV008 — synthetic-v1/SYN008

> В Москве я оплатил стоянку автомобиля на городской парковке, но ошибся одной цифрой в номере.

### Candidate readings

- Место парковочного эпизода явно связано с Москвой.
- Городской тип парковки прямо указан; платность из этого не следует.
- Рассказчик утверждает оплату стоянки автомобиля.
- Введённый номер содержит ошибку в одной цифре; успешная привязка платежа к размещённому автомобилю не установлена.

### Candidate followups (apply requiredWhen from JSON)

- eventDate [exact-day-not-stated]: Какова полная дата выбранной стоянки?
- placementInterval [full-standing-interval-not-stated]: Когда началась и закончилась выбранная стоянка? Не заменять временем платежа или уведомления.
- paidRegime [not-established-for-event-interval]: Какой режим действовал в этот период? Отсутствие разрешения или факт оплаты не отвечают на этот вопрос.
- paymentVehicleLink [ambiguous]: К какому автомобилю относится платёж?

### Unresolved / scope notes

- Связь платежа с нужным автомобилем/зоной/эпизодом требует отдельного подтверждения; юридическое действие ошибки не оценено.

Independent review: pending. Automatic output review: not started.

## DEV009 — synthetic-v1/SYN009

> В Москве я оплатил стоянку на городской парковке. Зону указал неверно, затем отправил исправление. Не знаю, сохранилось ли оно.

### Candidate readings

- Место парковочного эпизода явно связано с Москвой.
- Городской тип парковки прямо указан; платность из этого не следует.
- Рассказчик утверждает оплату и неверно выбранную зону.
- После этого отправил исправление; сохранение исправления явно неизвестно.

### Candidate followups (apply requiredWhen from JSON)

- eventDate [exact-day-not-stated]: Какова полная дата выбранной стоянки?
- placementInterval [full-standing-interval-not-stated]: Когда началась и закончилась выбранная стоянка? Не заменять временем платежа или уведомления.
- paidRegime [not-established-for-event-interval]: Какой режим действовал в этот период? Отсутствие разрешения или факт оплаты не отвечают на этот вопрос.
- correctionSaved [explicit-unknown]: Известно ли, что исправление сохранилось?
- targetZone [not-mentioned]: Какую зону следовало указать для этой стоянки?

### Unresolved / scope notes

- Связь платежа с нужным автомобилем/зоной/эпизодом требует отдельного подтверждения; юридическое действие ошибки не оценено.

Independent review: pending. Automatic output review: not started.

## DEV010 — synthetic-v1/SYN010

> В Москве я стоял на городской парковке. В истории есть платёж, но не помню, какой автомобиль и какую зону выбрал.

### Candidate readings

- Место парковочного эпизода явно связано с Москвой.
- Городской тип парковки прямо указан; платность из этого не следует.
- В истории есть платёж.
- Рассказчик не помнит выбранные автомобиль и зону; платёж нельзя уверенно привязать к этому эпизоду.

### Candidate followups (apply requiredWhen from JSON)

- eventDate [exact-day-not-stated]: Какова полная дата выбранной стоянки?
- placementInterval [full-standing-interval-not-stated]: Когда началась и закончилась выбранная стоянка? Не заменять временем платежа или уведомления.
- paidRegime [not-established-for-event-interval]: Какой режим действовал в этот период? Отсутствие разрешения или факт оплаты не отвечают на этот вопрос.
- paymentVehicleLink [explicit-unknown]: К какому автомобилю относится платёж?
- paymentZoneLink [explicit-unknown]: К какой зоне относится платёж?

### Unresolved / scope notes

- Связь платежа с нужным автомобилем/зоной/эпизодом требует отдельного подтверждения; юридическое действие ошибки не оценено.

Independent review: pending. Automatic output review: not started.

## DEV011 — synthetic-v1/SYN011

> В Москве автомобиль стоял на городской парковке с 12:00 до 12:30. Оплату провёл в 12:04:59.

### Candidate readings

- Место парковочного эпизода явно связано с Москвой.
- Городской тип парковки прямо указан; платность из этого не следует.
- Автомобиль стоял с 12:00 до 12:30.
- Оплата проведена в 12:04:59; время сохраняется с секундами.

### Candidate followups (apply requiredWhen from JSON)

- eventDate [exact-day-not-stated]: Какова полная дата выбранной стоянки?
- paidRegime [not-established-for-event-interval]: Какой режим действовал в этот период? Отсутствие разрешения или факт оплаты не отвечают на этот вопрос.

Independent review: pending. Automatic output review: not started.

## DEV012 — synthetic-v1/SYN012

> В Москве автомобиль стоял на городской парковке с 12:00 до 12:30. Оплату провёл в 12:05:00.

### Candidate readings

- Место парковочного эпизода явно связано с Москвой.
- Городской тип парковки прямо указан; платность из этого не следует.
- Автомобиль стоял с 12:00 до 12:30.
- Оплата проведена ровно в 12:05:00; правовой эффект границы не размечен.

### Candidate followups (apply requiredWhen from JSON)

- eventDate [exact-day-not-stated]: Какова полная дата выбранной стоянки?
- paidRegime [not-established-for-event-interval]: Какой режим действовал в этот период? Отсутствие разрешения или факт оплаты не отвечают на этот вопрос.

Independent review: pending. Automatic output review: not started.

## DEV013 — synthetic-v1/SYN013

> В Москве автомобиль стоял на городской парковке с 12:00 до 12:30. Оплату провёл в 12:05:01.

### Candidate readings

- Место парковочного эпизода явно связано с Москвой.
- Городской тип парковки прямо указан; платность из этого не следует.
- Автомобиль стоял с 12:00 до 12:30.
- Оплата проведена в 12:05:01; отличие в одну секунду не округлять.

### Candidate followups (apply requiredWhen from JSON)

- eventDate [exact-day-not-stated]: Какова полная дата выбранной стоянки?
- paidRegime [not-established-for-event-interval]: Какой режим действовал в этот период? Отсутствие разрешения или факт оплаты не отвечают на этот вопрос.

Independent review: pending. Automatic output review: not started.

## DEV014 — synthetic-v1/SYN014

> В Москве я оплатил городскую парковку с 12:00 до 13:00. Платёж отправил в 12:02, уехал в 12:40.

### Candidate readings

- Место парковочного эпизода явно связано с Москвой.
- Городской тип парковки прямо указан; платность из этого не следует.
- Заявленный оплаченный интервал — с 12:00 до 13:00.
- Платёж отправлен в 12:02; отправка и покрываемый интервал различаются.
- Рассказчик уехал в 12:40; фактическое начало стоянки явно не названо.

### Candidate followups (apply requiredWhen from JSON)

- eventDate [exact-day-not-stated]: Какова полная дата выбранной стоянки?
- placementInterval [full-standing-interval-not-stated]: Когда началась и закончилась выбранная стоянка? Не заменять временем платежа или уведомления.
- paidRegime [not-established-for-event-interval]: Какой режим действовал в этот период? Отсутствие разрешения или факт оплаты не отвечают на этот вопрос.

Independent review: pending. Automatic output review: not started.

## DEV015 — synthetic-v1/SYN015

> В Москве я стоял на городской парковке. Баланс пополнил в 12:02, но парковочную сессию не оплатил.

### Candidate readings

- Место парковочного эпизода явно связано с Москвой.
- Городской тип парковки прямо указан; платность из этого не следует.
- Баланс пополнен в 12:02.
- Парковочная сессия не оплачена; пополнение баланса не является оплатой сессии.

### Candidate followups (apply requiredWhen from JSON)

- eventDate [exact-day-not-stated]: Какова полная дата выбранной стоянки?
- placementInterval [full-standing-interval-not-stated]: Когда началась и закончилась выбранная стоянка? Не заменять временем платежа или уведомления.
- paidRegime [not-established-for-event-interval]: Какой режим действовал в этот период? Отсутствие разрешения или факт оплаты не отвечают на этот вопрос.

Independent review: pending. Automatic output review: not started.

## DEV016 — synthetic-v1/SYN016

> В Москве я стоял на городской парковке. Приложение выдало ошибку, но через СМС я успешно оплатил эту стоянку.

### Candidate readings

- Место парковочного эпизода явно связано с Москвой.
- Городской тип парковки прямо указан; платность из этого не следует.
- Приложение выдало ошибку.
- Рассказчик успешно оплатил именно эту стоянку через СМС; ошибка одного канала не означает неоплату.

### Candidate followups (apply requiredWhen from JSON)

- eventDate [exact-day-not-stated]: Какова полная дата выбранной стоянки?
- placementInterval [full-standing-interval-not-stated]: Когда началась и закончилась выбранная стоянка? Не заменять временем платежа или уведомления.
- paidRegime [not-established-for-event-interval]: Какой режим действовал в этот период? Отсутствие разрешения или факт оплаты не отвечают на этот вопрос.

Independent review: pending. Automatic output review: not started.

## DEV017 — synthetic-v1/SYN017

> В Москве я стоял на городской парковке. Приложение и СМС не работали, оплатить парковку не удалось.

### Candidate readings

- Место парковочного эпизода явно связано с Москвой.
- Городской тип парковки прямо указан; платность из этого не следует.
- Приложение и СМС не работали.
- Рассказчику не удалось оплатить парковку; вина и исключения ответственности из этого не выводятся.

### Candidate followups (apply requiredWhen from JSON)

- eventDate [exact-day-not-stated]: Какова полная дата выбранной стоянки?
- placementInterval [full-standing-interval-not-stated]: Когда началась и закончилась выбранная стоянка? Не заменять временем платежа или уведомления.
- paidRegime [not-established-for-event-interval]: Какой режим действовал в этот период? Отсутствие разрешения или факт оплаты не отвечают на этот вопрос.

Independent review: pending. Automatic output review: not started.

## DEV018 — synthetic-v1/SYN018

> В Москве я стоял на городской парковке. Банк показывает списание, но в парковочном приложении оплата не отображается.

### Candidate readings

- Место парковочного эпизода явно связано с Москвой.
- Городской тип парковки прямо указан; платность из этого не следует.
- Банк показывает списание.
- В парковочном приложении оплата не отображается; эти наблюдения относятся к разным системам, итог сессии не установлен.

### Candidate followups (apply requiredWhen from JSON)

- eventDate [exact-day-not-stated]: Какова полная дата выбранной стоянки?
- placementInterval [full-standing-interval-not-stated]: Когда началась и закончилась выбранная стоянка? Не заменять временем платежа или уведомления.
- paidRegime [not-established-for-event-interval]: Какой режим действовал в этот период? Отсутствие разрешения или факт оплаты не отвечают на этот вопрос.
- parkingSessionPaymentOutcome [conflicting-system-evidence]: Подтверждено ли зачисление в нужную парковочную сессию, а не только банковское списание?

Independent review: pending. Automatic output review: not started.

## DEV019 — synthetic-v1/SYN019

> В Москве я стоял на городской парковке. Приложение снова заработало в 13:00. Сведений о моей оплате у меня нет.

### Candidate readings

- Место парковочного эпизода явно связано с Москвой.
- Городской тип парковки прямо указан; платность из этого не следует.
- Приложение снова заработало в 13:00.
- Сведений об оплате рассказчика нет; восстановление приложения не означает успешный платёж.

### Candidate followups (apply requiredWhen from JSON)

- eventDate [exact-day-not-stated]: Какова полная дата выбранной стоянки?
- placementInterval [full-standing-interval-not-stated]: Когда началась и закончилась выбранная стоянка? Не заменять временем платежа или уведомления.
- paidRegime [not-established-for-event-interval]: Какой режим действовал в этот период? Отсутствие разрешения или факт оплаты не отвечают на этот вопрос.
- paymentOutcome [explicit-no-information]: Что известно о результате оплаты именно выбранной стоянки?

Independent review: pending. Automatic output review: not started.

## DEV020 — synthetic-v1/SYN020

> В Москве я стоял на городской парковке. Ошибок реквизитов и последующих исправлений не было.

### Candidate readings

- Место парковочного эпизода явно связано с Москвой.
- Городской тип парковки прямо указан; платность из этого не следует.
- Рассказчик отрицает ошибки реквизитов и последующие исправления.
- Об оплате, вине и разрешениях ничего не сообщает; отрицания этих фактов недопустимы.

### Candidate followups (apply requiredWhen from JSON)

- eventDate [exact-day-not-stated]: Какова полная дата выбранной стоянки?
- placementInterval [full-standing-interval-not-stated]: Когда началась и закончилась выбранная стоянка? Не заменять временем платежа или уведомления.
- paidRegime [not-established-for-event-interval]: Какой режим действовал в этот период? Отсутствие разрешения или факт оплаты не отвечают на этот вопрос.
- paymentOutcome [not-mentioned]: Что известно о результате оплаты именно выбранной стоянки?

Independent review: pending. Automatic output review: not started.

## DEV021 — synthetic-v1/SYN021

> В Москве я стоял на городской парковке. У меня есть действующее резидентное разрешение.

### Candidate readings

- Место парковочного эпизода явно связано с Москвой.
- Городской тип парковки прямо указан; платность из этого не следует.
- У рассказчика есть действующее резидентное разрешение.
- Применимость разрешения к месту, времени и автомобилю не указана.

### Candidate followups (apply requiredWhen from JSON)

- eventDate [exact-day-not-stated]: Какова полная дата выбранной стоянки?
- placementInterval [full-standing-interval-not-stated]: Когда началась и закончилась выбранная стоянка? Не заменять временем платежа или уведомления.
- paidRegime [not-established-for-event-interval]: Какой режим действовал в этот период? Отсутствие разрешения или факт оплаты не отвечают на этот вопрос.
- permitApplicability [not-mentioned]: На какие автомобиль, место и время распространяется разрешение?
- paymentOutcome [not-mentioned]: Что известно о результате оплаты именно выбранной стоянки?

Independent review: pending. Automatic output review: not started.

## DEV022 — synthetic-v1/SYN022

> В Москве я стоял на городской парковке. Действующего разрешения или абонемента у меня нет.

### Candidate readings

- Место парковочного эпизода явно связано с Москвой.
- Городской тип парковки прямо указан; платность из этого не следует.
- У рассказчика нет действующего разрешения или абонемента.
- Это не отрицание инвалидности, специального тарифа или иной льготы.

### Candidate followups (apply requiredWhen from JSON)

- eventDate [exact-day-not-stated]: Какова полная дата выбранной стоянки?
- placementInterval [full-standing-interval-not-stated]: Когда началась и закончилась выбранная стоянка? Не заменять временем платежа или уведомления.
- paidRegime [not-established-for-event-interval]: Какой режим действовал в этот период? Отсутствие разрешения или факт оплаты не отвечают на этот вопрос.
- paymentOutcome [not-mentioned]: Что известно о результате оплаты именно выбранной стоянки?

Independent review: pending. Automatic output review: not started.

## DEV023 — synthetic-v1/SYN023

> В Москве я стоял на городской парковке. Не помню, действует ли ещё моё разрешение.

### Candidate readings

- Место парковочного эпизода явно связано с Москвой.
- Городской тип парковки прямо указан; платность из этого не следует.
- Рассказчик не помнит, действует ли ещё его разрешение; статус явно неизвестен.

### Candidate followups (apply requiredWhen from JSON)

- eventDate [exact-day-not-stated]: Какова полная дата выбранной стоянки?
- placementInterval [full-standing-interval-not-stated]: Когда началась и закончилась выбранная стоянка? Не заменять временем платежа или уведомления.
- paidRegime [not-established-for-event-interval]: Какой режим действовал в этот период? Отсутствие разрешения или факт оплаты не отвечают на этот вопрос.
- permitValidity [explicit-unknown]: Известен ли срок действия разрешения на момент стоянки?
- paymentOutcome [not-mentioned]: Что известно о результате оплаты именно выбранной стоянки?

Independent review: pending. Automatic output review: not started.

## DEV024 — synthetic-v1/SYN024

> В Москве я стоял на городской парковке. Заявление на разрешение подал, но само разрешение ещё не получил.

### Candidate readings

- Место парковочного эпизода явно связано с Москвой.
- Городской тип парковки прямо указан; платность из этого не следует.
- Рассказчик подал заявление на разрешение.
- Само разрешение ещё не получил; подача заявления не означает наличие действующего разрешения.

### Candidate followups (apply requiredWhen from JSON)

- eventDate [exact-day-not-stated]: Какова полная дата выбранной стоянки?
- placementInterval [full-standing-interval-not-stated]: Когда началась и закончилась выбранная стоянка? Не заменять временем платежа или уведомления.
- paidRegime [not-established-for-event-interval]: Какой режим действовал в этот период? Отсутствие разрешения или факт оплаты не отвечают на этот вопрос.
- paymentOutcome [not-mentioned]: Что известно о результате оплаты именно выбранной стоянки?

Independent review: pending. Automatic output review: not started.

## DEV025 — synthetic-v1/SYN025

> В Москве я стоял на городской парковке. Я перевожу человека с инвалидностью, но сведений о реестре и знаке в этом рассказе нет.

### Candidate readings

- Место парковочного эпизода явно связано с Москвой.
- Городской тип парковки прямо указан; платность из этого не следует.
- Рассказчик перевозит человека с инвалидностью; инвалидность относится к пассажиру, не автоматически к водителю.
- Сведений о реестре и знаке в рассказе нет; отсутствие сведений не означает отсутствие регистрации или знака.

### Candidate followups (apply requiredWhen from JSON)

- eventDate [exact-day-not-stated]: Какова полная дата выбранной стоянки?
- placementInterval [full-standing-interval-not-stated]: Когда началась и закончилась выбранная стоянка? Не заменять временем платежа или уведомления.
- paidRegime [not-established-for-event-interval]: Какой режим действовал в этот период? Отсутствие разрешения или факт оплаты не отвечают на этот вопрос.
- disabilityRegistry [explicit-not-mentioned]: Что известно о записи в реестре для выбранного автомобиля?
- disabilitySign [explicit-not-mentioned]: Что известно о наличии и применении знака?
- paymentOutcome [not-mentioned]: Что известно о результате оплаты именно выбранной стоянки?

### Unresolved / scope notes

- Юридические условия льготы и доказанность инвалидности не проверяются данным linguistic review.

Independent review: pending. Automatic output review: not started.

## DEV026 — synthetic-v1/SYN026

> В Москве я стоял на городской парковке. О той же стоянке я говорю: «Я оплатил парковку». В моей заметке написано: «Я не оплатил парковку».

### Candidate readings

- Место парковочного эпизода явно связано с Москвой.
- Городской тип парковки прямо указан; платность из этого не следует.
- О той же стоянке рассказчик сейчас утверждает: оплатил.
- В его заметке содержится противоположное утверждение: не оплатил.
- Нужно сохранить обе версии и их источники; противоречие не разрешено.

### Candidate followups (apply requiredWhen from JSON)

- eventDate [exact-day-not-stated]: Какова полная дата выбранной стоянки?
- placementInterval [full-standing-interval-not-stated]: Когда началась и закончилась выбранная стоянка? Не заменять временем платежа или уведомления.
- paidRegime [not-established-for-event-interval]: Какой режим действовал в этот период? Отсутствие разрешения или факт оплаты не отвечают на этот вопрос.
- reconcilePaymentClaims [unresolved-conflict]: Как соотносятся нынешнее утверждение и противоположная запись в заметке?

### Unresolved / scope notes

- Не решать за рассказчика, какая версия об оплате окончательная; уточнение/источники сохраняются отдельно.

Independent review: pending. Automatic output review: not started.

## DEV027 — synthetic-v1/SYN027

> В Москве я сделал две стоянки на городских парковках. Утреннюю парковку оплатил. Вечернюю парковку не оплатил.

### Candidate readings

- Место парковочного эпизода явно связано с Москвой.
- Городской тип парковки прямо указан; платность из этого не следует.
- Описаны две стоянки на городских парковках Москвы.
- Утренняя оплачена; вечерняя не оплачена.
- Выбор одного эпизода ещё не сделан; разные статусы разных эпизодов не противоречие.

### Candidate followups (apply requiredWhen from JSON)

- eventDate [exact-day-not-stated]: Какова полная дата выбранной стоянки?
- placementInterval [full-standing-interval-not-stated]: Когда началась и закончилась выбранная стоянка? Не заменять временем платежа или уведомления.
- paidRegime [not-established-for-event-interval]: Какой режим действовал в этот период? Отсутствие разрешения или факт оплаты не отвечают на этот вопрос.
- selectedEpisode [requires-user-selection]: Какую стоянку разбирать: утреннюю или вечернюю?

Independent review: pending. Automatic output review: not started.

## DEV028 — synthetic-v1/SYN028

> В Москве я стоял на городской парковке. Я утверждаю, что оплатил эту стоянку. В уведомлении указано, что она не оплачена.

### Candidate readings

- Место парковочного эпизода явно связано с Москвой.
- Городской тип парковки прямо указан; платность из этого не следует.
- Рассказчик утверждает оплату этой стоянки.
- В уведомлении указана неоплата; сообщение уведомления не становится установленным фактом.
- Между источниками есть нерешённое расхождение об одном эпизоде.

### Candidate followups (apply requiredWhen from JSON)

- eventDate [exact-day-not-stated]: Какова полная дата выбранной стоянки?
- placementInterval [full-standing-interval-not-stated]: Когда началась и закончилась выбранная стоянка? Не заменять временем платежа или уведомления.
- paidRegime [not-established-for-event-interval]: Какой режим действовал в этот период? Отсутствие разрешения или факт оплаты не отвечают на этот вопрос.
- reconcileNarratorAndNotice [unresolved-conflict]: Чем объясняется расхождение рассказчика и уведомления об оплате?

### Unresolved / scope notes

- Не решать за рассказчика, какая версия об оплате окончательная; уточнение/источники сохраняются отдельно.

Independent review: pending. Automatic output review: not started.

## DEV029 — synthetic-v1/SYN029

> В Москве я стоял на городской парковке. Я не утверждаю, что парковка оплачена: мне неизвестен результат платежа.

### Candidate readings

- Место парковочного эпизода явно связано с Москвой.
- Городской тип парковки прямо указан; платность из этого не следует.
- Рассказчик не утверждает оплату; отрицание относится к speech act.
- Он явно не знает результат платежа; не утверждает ни оплату, ни неоплату.

### Candidate followups (apply requiredWhen from JSON)

- eventDate [exact-day-not-stated]: Какова полная дата выбранной стоянки?
- placementInterval [full-standing-interval-not-stated]: Когда началась и закончилась выбранная стоянка? Не заменять временем платежа или уведомления.
- paidRegime [not-established-for-event-interval]: Какой режим действовал в этот период? Отсутствие разрешения или факт оплаты не отвечают на этот вопрос.
- paymentOutcome [explicit-unknown]: Что известно о результате оплаты именно выбранной стоянки?

Independent review: pending. Automatic output review: not started.

## DEV030 — synthetic-v1/SYN030

> В Москве я стоял на городской парковке. Сначала написал, что не оплатил её. Позже уточнил: платёж был, но за другой автомобиль.

### Candidate readings

- Место парковочного эпизода явно связано с Москвой.
- Городской тип парковки прямо указан; платность из этого не следует.
- Ранее рассказчик написал, что не оплатил эту стоянку.
- Позднее уточнил, что платёж был за другой автомобиль.
- Поздний платёж за другой автомобиль не подтверждает оплату исходной стоянки; история уточнения сохраняется.

### Candidate followups (apply requiredWhen from JSON)

- eventDate [exact-day-not-stated]: Какова полная дата выбранной стоянки?
- placementInterval [full-standing-interval-not-stated]: Когда началась и закончилась выбранная стоянка? Не заменять временем платежа или уведомления.
- paidRegime [not-established-for-event-interval]: Какой режим действовал в этот период? Отсутствие разрешения или факт оплаты не отвечают на этот вопрос.
- paymentForOriginalVehicle [not-established]: Какой платёж относится к исходному автомобилю?

### Unresolved / scope notes

- Платёж за другую машину совместим с неоплатой исходной стоянки: логическое противоречие не установлено. Сохранить последовательность уточнения, не объявлять исходную стоянку оплаченной.

Independent review: pending. Automatic output review: not started.

## DEV031 — synthetic-v1/SYN031

> Я стоял на городской парковке в Москве и не оплатил её.

### Candidate readings

- Место парковочного эпизода явно связано с Москвой.
- Городской тип парковки прямо указан; платность из этого не следует.
- Рассказчик отрицает оплату стоянки на городской парковке Москвы.

### Candidate followups (apply requiredWhen from JSON)

- eventDate [exact-day-not-stated]: Какова полная дата выбранной стоянки?
- placementInterval [full-standing-interval-not-stated]: Когда началась и закончилась выбранная стоянка? Не заменять временем платежа или уведомления.
- paidRegime [not-established-for-event-interval]: Какой режим действовал в этот период? Отсутствие разрешения или факт оплаты не отвечают на этот вопрос.

Independent review: pending. Automatic output review: not started.

## DEV032 — synthetic-v1/SYN032

> Я стоял на городской парковке в Казани и не оплатил её.

### Candidate readings

- Городской тип парковки прямо указан; платность из этого не следует.
- Город — Казань; рассказчик не оплатил городскую парковку.
- Этот город вне московского demo scope; исходные факты всё равно извлекаются.

### Candidate followups (apply requiredWhen from JSON)

- eventDate [exact-day-not-stated]: Какова полная дата выбранной стоянки?
- placementInterval [full-standing-interval-not-stated]: Когда началась и закончилась выбранная стоянка? Не заменять временем платежа или уведомления.
- paidRegime [not-established-for-event-interval]: Какой режим действовал в этот период? Отсутствие разрешения или факт оплаты не отвечают на этот вопрос.

Independent review: pending. Automatic output review: not started.

## DEV033 — synthetic-v1/SYN033

> Я стоял на городской парковке и не оплатил её. Город не указан.

### Candidate readings

- Городской тип парковки прямо указан; платность из этого не следует.
- Рассказчик не оплатил городскую парковку.
- Город явно не указан; подстановка Москвы недопустима.

### Candidate followups (apply requiredWhen from JSON)

- eventDate [exact-day-not-stated]: Какова полная дата выбранной стоянки?
- placementInterval [full-standing-interval-not-stated]: Когда началась и закончилась выбранная стоянка? Не заменять временем платежа или уведомления.
- paidRegime [not-established-for-event-interval]: Какой режим действовал в этот период? Отсутствие разрешения или факт оплаты не отвечают на этот вопрос.
- city [explicit-not-mentioned]: В каком городе произошла стоянка?

Independent review: pending. Automatic output review: not started.

## DEV034 — synthetic-v1/SYN034

> Я стоял на парковке у торгового центра в Москве. Не знаю, городская это парковка или частная.

### Candidate readings

- Место парковочного эпизода явно связано с Москвой.
- Парковка находится у торгового центра в Москве.
- Неизвестно, городская она или частная; расположение у ТЦ не определяет тип парковки.

### Candidate followups (apply requiredWhen from JSON)

- eventDate [exact-day-not-stated]: Какова полная дата выбранной стоянки?
- placementInterval [full-standing-interval-not-stated]: Когда началась и закончилась выбранная стоянка? Не заменять временем платежа или уведомления.
- paidRegime [not-established-for-event-interval]: Какой режим действовал в этот период? Отсутствие разрешения или факт оплаты не отвечают на этот вопрос.
- parkingType [explicit-unknown]: Это городская парковка или частная территория?
- paymentOutcome [not-mentioned]: Что известно о результате оплаты именно выбранной стоянки?

Independent review: pending. Automatic output review: not started.

## DEV035 — synthetic-v1/SYN035

> Я стоял на городской парковке, но не в Москве. Город пока не назову.

### Candidate readings

- Городской тип парковки прямо указан; платность из этого не следует.
- Парковка городская и прямо указано, что она не в Москве.
- Точный город рассказчик пока отказывается назвать; это отличается от полного отсутствия сведений о географии.

### Candidate followups (apply requiredWhen from JSON)

- eventDate [exact-day-not-stated]: Какова полная дата выбранной стоянки?
- placementInterval [full-standing-interval-not-stated]: Когда началась и закончилась выбранная стоянка? Не заменять временем платежа или уведомления.
- paidRegime [not-established-for-event-interval]: Какой режим действовал в этот период? Отсутствие разрешения или факт оплаты не отвечают на этот вопрос.
- exactCity [withheld]: Нужно ли уточнять город, если московское demo уже неприменимо?
- paymentOutcome [not-mentioned]: Что известно о результате оплаты именно выбранной стоянки?

Independent review: pending. Automatic output review: not started.

## DEV036 — synthetic-v1/SYN036

> В Москве я стоял на городской парковке. Весь период моей стоянки был платным. Разрешений и абонементов у меня нет.

### Candidate readings

- Место парковочного эпизода явно связано с Москвой.
- Городской тип парковки прямо указан; платность из этого не следует.
- Весь период стоянки заявлен платным.
- Разрешений и абонементов у рассказчика нет; факт оплаты при этом не сообщён.

### Candidate followups (apply requiredWhen from JSON)

- eventDate [exact-day-not-stated]: Какова полная дата выбранной стоянки?
- placementInterval [full-standing-interval-not-stated]: Когда началась и закончилась выбранная стоянка? Не заменять временем платежа или уведомления.
- paymentOutcome [not-mentioned]: Что известно о результате оплаты именно выбранной стоянки?

Independent review: pending. Automatic output review: not started.

## DEV037 — synthetic-v1/SYN037

> В Москве я стоял на городской парковке. По условиям этого учебного случая весь период моей стоянки был бесплатным.

### Candidate readings

- Место парковочного эпизода явно связано с Москвой.
- Городской тип парковки прямо указан; платность из этого не следует.
- По условиям учебного случая весь период стоянки бесплатный.
- Это synthetic условие, не проверенная информация о реальном тарифе или правовом результате.

### Candidate followups (apply requiredWhen from JSON)

- eventDate [exact-day-not-stated]: Какова полная дата выбранной стоянки?
- placementInterval [full-standing-interval-not-stated]: Когда началась и закончилась выбранная стоянка? Не заменять временем платежа или уведомления.
- paymentOutcome [not-mentioned]: Что известно о результате оплаты именно выбранной стоянки?

Independent review: pending. Automatic output review: not started.

## DEV038 — synthetic-v1/SYN038

> В Москве я стоял на городской парковке. Я оплатил её, но о действовавшем тарифе сведений нет.

### Candidate readings

- Место парковочного эпизода явно связано с Москвой.
- Городской тип парковки прямо указан; платность из этого не следует.
- Рассказчик утверждает оплату парковки.
- Сведений о действовавшем тарифе нет; оплата не доказывает применимость платного режима.

### Candidate followups (apply requiredWhen from JSON)

- eventDate [exact-day-not-stated]: Какова полная дата выбранной стоянки?
- placementInterval [full-standing-interval-not-stated]: Когда началась и закончилась выбранная стоянка? Не заменять временем платежа или уведомления.
- paidRegime [not-established-for-event-interval]: Какой режим действовал в этот период? Отсутствие разрешения или факт оплаты не отвечают на этот вопрос.

Independent review: pending. Automatic output review: not started.

## DEV039 — synthetic-v1/SYN039

> В Москве я стоял на городской парковке. Штраф за эту стоянку оплатил, а саму парковку не оплачивал.

### Candidate readings

- Место парковочного эпизода явно связано с Москвой.
- Городской тип парковки прямо указан; платность из этого не следует.
- Рассказчик оплатил штраф за эту стоянку.
- Саму парковку не оплачивал; штраф и парковочный платёж — разные объекты.

### Candidate followups (apply requiredWhen from JSON)

- eventDate [exact-day-not-stated]: Какова полная дата выбранной стоянки?
- placementInterval [full-standing-interval-not-stated]: Когда началась и закончилась выбранная стоянка? Не заменять временем платежа или уведомления.
- paidRegime [not-established-for-event-interval]: Какой режим действовал в этот период? Отсутствие разрешения или факт оплаты не отвечают на этот вопрос.

Independent review: pending. Automatic output review: not started.

## DEV040 — synthetic-v1/SYN040

> В Москве я стоял на городской парковке. В июле получил уведомление о штрафе за майскую стоянку. Точная дата стоянки неизвестна; о платеже ничего не сообщаю.

### Candidate readings

- Место парковочного эпизода явно связано с Москвой.
- Городской тип парковки прямо указан; платность из этого не следует.
- В июле получено уведомление о штрафе за майскую стоянку.
- Точная дата стоянки явно неизвестна; год не назван.
- Об оплате ничего не сообщено; июль получения уведомления нельзя назначить временем стоянки.

### Candidate followups (apply requiredWhen from JSON)

- eventDate [exact-day-not-stated]: Какова полная дата выбранной стоянки?
- placementInterval [full-standing-interval-not-stated]: Когда началась и закончилась выбранная стоянка? Не заменять временем платежа или уведомления.
- paidRegime [not-established-for-event-interval]: Какой режим действовал в этот период? Отсутствие разрешения или факт оплаты не отвечают на этот вопрос.
- eventYearAndDay [explicit-partial-date]: Каковы год и день майской стоянки?
- paymentOutcome [not-mentioned]: Что известно о результате оплаты именно выбранной стоянки?

Independent review: pending. Automatic output review: not started.

## DEV041 — corpus/C01

> Автомобиль находился на платной городской парковке Москвы. По сообщению защитника, деньги за парковку списали, но водитель указал номер другого принадлежащего ему автомобиля.

### Candidate readings

- Автомобиль находился на платной городской парковке Москвы.
- Именно по сообщению защитника деньги списали, но водитель указал номер другого своего автомобиля.
- Размещённый автомобиль и автомобиль платежа различаются; его оплата этим списанием не подтверждена.

### Candidate followups (apply requiredWhen from JSON)

- eventDate [exact-day-not-stated]: Какова полная дата выбранной стоянки?
- placementInterval [full-standing-interval-not-stated]: Когда началась и закончилась выбранная стоянка? Не заменять временем платежа или уведомления.
- paymentForParkedVehicle [not-established]: Есть ли сведения об оплате именно размещённого автомобиля?

### Unresolved / scope notes

- Связь платежа с нужным автомобилем/зоной/эпизодом требует отдельного подтверждения; юридическое действие ошибки не оценено.

Independent review: pending. Automatic output review: not started.

## DEV042 — corpus/C03

> Автор вопроса сообщает: оплата через приложение прошла, но в номере автомобиля была ошибочна одна цифра. После этого пришёл штраф.

### Candidate readings

- Автор вопроса сообщает, что оплата через приложение прошла.
- В номере автомобиля была ошибка в одной цифре; затем пришёл штраф.
- Город, тип парковки и связь штрафа с правовой оценкой не установлены этим input.

### Candidate followups (apply requiredWhen from JSON)

- eventDate [exact-day-not-stated]: Какова полная дата выбранной стоянки?
- placementInterval [full-standing-interval-not-stated]: Когда началась и закончилась выбранная стоянка? Не заменять временем платежа или уведомления.
- paidRegime [not-established-for-event-interval]: Какой режим действовал в этот период? Отсутствие разрешения или факт оплаты не отвечают на этот вопрос.
- city [not-mentioned]: В каком городе произошла стоянка?
- parkingType [not-mentioned]: Это городская парковка или частная территория?
- paymentVehicleLink [ambiguous]: К какому автомобилю относится платёж?

### Unresolved / scope notes

- Связь платежа с нужным автомобилем/зоной/эпизодом требует отдельного подтверждения; юридическое действие ошибки не оценено.

Independent review: pending. Automatic output review: not started.

## DEV043 — corpus/C08

> В декабре 2021 года автор приехал на платную парковку. На балансе не хватало денег; пополнение заняло несколько минут. Он утверждает, что платёж прошёл. Позже получил штраф, а в октябре 2022 года — постановление об исполнительном производстве.

### Candidate readings

- Автор приехал на платную парковку в декабре 2021 года.
- Денег на балансе не хватало; пополнение заняло несколько минут.
- Именно автор утверждает, что платёж прошёл; точное время и длительность задержки неизвестны.
- Позже он получил штраф; в октябре 2022 года — постановление об исполнительном производстве. Это процессуальные события после исходной стоянки.

### Candidate followups (apply requiredWhen from JSON)

- eventDate [exact-day-not-stated]: Какова полная дата выбранной стоянки?
- placementInterval [full-standing-interval-not-stated]: Когда началась и закончилась выбранная стоянка? Не заменять временем платежа или уведомления.
- city [not-mentioned]: В каком городе произошла стоянка?
- paymentAndPlacementTime [not-mentioned]: Когда началась стоянка и когда выполнен платёж?

### Unresolved / scope notes

- Начальный parking episode отделён от последующего штрафа и исполнительного производства; точные даты событий не восстанавливаются из дат публикации.

Independent review: pending. Automatic output review: not started.

## DEV044 — corpus/C11

> Автор сообщает: оплачивал стоянку машины супруги через приложение и ошибся первой буквой номера. Пришёл штраф. Он редко пользуется этой машиной и спрашивает, кому подавать жалобу — водителю или собственнику.

### Candidate readings

- Автор сообщает, что оплачивал через приложение стоянку машины супруги и ошибся первой буквой номера.
- Пришёл штраф; успешное зачисление оплаты нужной машине не сообщено.
- Автор редко пользуется этой машиной и задаёт вопрос, кому подавать жалобу: водителю или собственнику.
- Супруга, рассказчик, водитель и собственник — роли, которые нельзя автоматически отождествлять; procedural вопрос вне demo расчёта.

### Candidate followups (apply requiredWhen from JSON)

- eventDate [exact-day-not-stated]: Какова полная дата выбранной стоянки?
- placementInterval [full-standing-interval-not-stated]: Когда началась и закончилась выбранная стоянка? Не заменять временем платежа или уведомления.
- paidRegime [not-established-for-event-interval]: Какой режим действовал в этот период? Отсутствие разрешения или факт оплаты не отвечают на этот вопрос.
- city [not-mentioned]: В каком городе произошла стоянка?
- parkingType [not-mentioned]: Это городская парковка или частная территория?
- paymentOutcome [not-established]: Что известно о результате оплаты именно выбранной стоянки?
- driverOwnerIdentity [ambiguous]: Кто использовал автомобиль и к кому относятся сведения о владении?

### Unresolved / scope notes

- Связь платежа с нужным автомобилем/зоной/эпизодом требует отдельного подтверждения; юридическое действие ошибки не оценено.
- Принадлежность супруге не доказывает, кто водитель, адресат штрафа либо надлежащий заявитель; правовой ответ вне scope.

Independent review: pending. Automatic output review: not started.

## DEV045 — corpus/C13

> Автор сообщает, что в мае 2017 года оплатил парковку в Москве через приложение, но получил штраф. В истории номера не было региона. Позже формат изменился. Деньги списывались с ранее пополненного депозита.

### Candidate readings

- Автор сообщает об оплате парковки в Москве через приложение в мае 2017 года и полученном штрафе.
- В истории номера не было региона; позже формат изменился. Это сообщение автора, не установленный дефект приложения.
- Деньги списывались с ранее пополненного депозита; пополнение и списание различаются.

### Candidate followups (apply requiredWhen from JSON)

- eventDate [exact-day-not-stated]: Какова полная дата выбранной стоянки?
- placementInterval [full-standing-interval-not-stated]: Когда началась и закончилась выбранная стоянка? Не заменять временем платежа или уведомления.
- paidRegime [not-established-for-event-interval]: Какой режим действовал в этот период? Отсутствие разрешения или факт оплаты не отвечают на этот вопрос.
- parkingType [not-mentioned]: Это городская парковка или частная территория?
- paymentVehicleLink [ambiguous]: К какому автомобилю относится платёж?

### Unresolved / scope notes

- Связь платежа с нужным автомобилем/зоной/эпизодом требует отдельного подтверждения; юридическое действие ошибки не оценено.

Independent review: pending. Automatic output review: not started.
