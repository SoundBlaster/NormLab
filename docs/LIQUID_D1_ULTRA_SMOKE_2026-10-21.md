# Liquid AI D1 Ultra: bounded Choice smoke

Дата: 2026-10-21. Ledger: [#70](https://github.com/SoundBlaster/NormLab/issues/70).
Статус до inference: protocol frozen, results pending.

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
