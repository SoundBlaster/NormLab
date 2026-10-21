# Liquid AI D1 Ultra: bounded Choice smoke

Дата: 2026-10-21. Ledger: [#70](https://github.com/SoundBlaster/NormLab/issues/70).
Результат: один live request завершён; три ответа совпали с authored expectations.
Protocol/fixture закреплены до inference в commit `ab3c216`.

## Разрешение и protocol

Пользователь предоставил Liquid key и попросил быстрый тест. Один потенциально
платный HTTP attempt, три Choice questions в одном batch, без retries/repair/
fallback или других моделей. Endpoint и requested model закреплены в
[fixture](../fixtures/providers/liquid-d1-ultra-choice-v1.json).
Total deadline30s, response cap1MiB, redirects disabled. При первом failure
остановиться; usage/cost при неизвестном исходе не считать нулевыми. Денежный cap
CoreInfra не переносится на Liquid; внешний лимит Liquid не проверен.

Hypothesis: API доступен и возвращает валидные Choice distributions, различая
явное отрицание, явно выраженную неизвестность и отсутствие сведений об оплате.

| Вопрос         | Source                             | Ожидание до inference |
| -------------- | ---------------------------------- | --------------------- |
| Anna payment   | «Я не оплачивала парковку»         | denied                |
| Boris payment  | «Я не знаю, оплатил ли я парковку» | unknown               |
| Viktor payment | «Я приехал в09:00»                 | unsupported           |

Полный source/criteria в fixture. Проверить HTTP/model, exact question membership,
Choice labels, finite/range/sum of distributions, выбранную top label,
confidence, usage и latency. Отдельно посчитать agreement с тремя ожиданиями.
Confidence хранится как metadata модели и не доказывает её точность.
Один authored сюжет не устанавливает general accuracy или преимущество над Jev/Luna.

Прямой HTTP smoke не проверяет совместимость Jev4Mellea, полный extraction pipeline
или deployment. Ключ передаётся скрытым stdin в память процесса; в Git, argv,
public config или capture он не сохраняется.

Источники: [Liquid API](https://docs.liquid.ai/lfm/models/d1),
[анонс D1 Ultra](https://www.liquid.ai/blog/d1-ultra).

## Результат одного запроса

[Capture](evidence/liquid-d1-ultra-choice-smoke-2026-10-21.json): HTTP 200,
requested/returned model `d1-ultra`, 1 attempt, 0 retries, latency 1.124 s.

| Вопрос         | Ожидалось   | Получено    | Confidence модели | P выбранной label |
| -------------- | ----------- | ----------- | ----------------- | ----------------- |
| Anna payment   | denied      | denied      | 0.991656          | 0.993742          |
| Boris payment  | unknown     | unknown     | 0.995754          | 0.996816          |
| Viktor payment | unsupported | unsupported | 0.987461          | 0.990596          |

Question membership, Choice type/labels, finite/range/sum of distributions,
top-label consistency и confidence checks прошли для всех 3 ответов.
Usage: 608 input / 0 output tokens. API вернул `usage.cost=0.000025536`; оценка по
анонсированному input rate $0.042/M тоже даёт $0.000025536. Денежная единица поля
API отдельно по schema не проверена; списание со счёта/billing не проверялось,
поэтому capture сохраняет `costUSD:null` и отдельную estimate.

Вывод: endpoint доступен с этим ключом из текущего окружения, Choice wire shape
подходит для этих 3 вопросов; явное отрицание, unknown и silence не смешаны
на данном authored примере. Это 3 связанных вопроса к одному короткому тексту,
не 3 независимых дела и не general accuracy 100%. Никакого live сравнения с
Jev/Luna, Noul/Score, SDK/Jev4Mellea integration или deployed verification нет.

Fixture bytes/digest сверены с pre-inference commit; raw JSON response сохранён
в sanitized capture, без ключа/Authorization. Это не подписанная квитанция provider
и не полный HTTP wire archive. После этого запроса новых calls не было.

Следующий отдельный шаг — проверить Liquid через существующий TypeSafe adapter:
сначала offline contract, затем при новом bounded разрешении на спорных
source-grounding/polarity controls из нашего корпуса. Этот smoke не меняет
основной route приложения и не запускает расширенную оценку.
