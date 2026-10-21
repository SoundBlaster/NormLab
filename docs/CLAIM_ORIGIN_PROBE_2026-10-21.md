# Узкая проверка источника утверждения

Дата: 2026-10-21. Ledger: [#70](https://github.com/SoundBlaster/NormLab/issues/70).
Пользователь поручил выполнить узкую проверку и предложил прямой TypeSafe API.
Выбран bounded diagnostic: 6 main jobs, максимум 8 attempts. Protocol, inputs,
references и actual driver фиксируются до inference; результаты пока pending.

## Гипотеза и controls

В [предыдущем сравнении, PR #176](https://github.com/SoundBlaster/NormLab/pull/176)
обе модели приняли P04b с переносом утверждения из письма на рассказчика.
Проверяем, может ли source-only Choice сначала установить источник selected
proposition, после чего сравнение с candidate claimant выполняется отдельно.
Это не вопрос об авторе физического письма, плательщике или истинности неоплаты.

| Task | Исходный текст и выбранная цитата                                               | Candidate reference |
| ---- | ------------------------------------------------------------------------------- | ------------------- |
| S01  | «В письме сообщили, что моя парковка не оплачена.» → «моя парковка не оплачена» | letter_1            |
| S03  | «Я оплатил парковку. В письме: парковка не оплачена.» → «Я оплатил парковку»    | narrator            |

Оба source texts и spans точно взяты из v2 C015/R029/A01 и C005/R009/A01.
В S03 документ упомянут, но выбранное утверждение принадлежит рассказчику:
always-letter tactic не проходит оба controls. Неопределённое авторство,
вложенные источники и многозначные местоимения этой серией не проверяются.

В narrow input только full source, selected quote/offsets и определения origin
IDs; candidateClaims/claimant и expected answer исключены. Choices: narrator,
letter_1, other, indeterminate. Вопрос и entity definitions одинаковы для обоих
targets и providers. Это bundle из input projection и нового вопроса, а не
изолированная однофакторная instruction ablation.

## Отдельный контроль смены провайдера

Jev идёт напрямую в `https://api.typesafe.ai/v1/systemone` с `TYPESAFE_API_KEY`,
requested model `jev-1.13.0`. CoreInfra key и его денежный ceiling сюда не
переносятся. Ultra остаётся на Liquid `d1-ultra`, с ключом через hidden stdin.

Поскольку прежний Jev baseline был через CoreInfra, добавлены **два fresh native
overall controls** B01a/B01b: exact copies P04a/P04b из PR #176 commit `09fc8c0`.
Они сохраняют полную старую разметку и overall question; references compatible /
incompatible. Их задача — не приписать возможное изменение baseline одной
decomposition, когда одновременно изменился gateway. Временные/стохастические
различия всё равно не позволяют сделать causal conclusion по одному ответу.

Всего: 2 native baseline calls + 2 narrow targets × 2 providers = 6 main jobs.
Все calls независимы, без общего диалога. Точные order и bindings в
[plan](../fixtures/providers/claim-origin-probe-v1/plan.json), expectations отдельно
в [reviewer-only](../fixtures/providers/claim-origin-probe-v1/reviewer-only.json).

## Caps и stopping rule

- Максимум 8 attempts, включая до двух network/TLS/timeout retries, максимум
  один на job, backoff 1 s. После валидной label повторов нет.
- 30 s/attempt, 360 s/series, 1 MiB response. После unrecovered network unknown
  job остаётся unknown и серия идёт дальше в пределах cap. HTTP/protocol/model
  errors останавливают её. Никакого fallback между native и CoreInfra.
- Все attempts/outcomes, known и unknown usage сохраняются. Нет ответа — нет
  semantic score. Native confidence и P(selected) записываются отдельно.
- Native TypeSafe/Liquid monetary ceilings не подтверждены; request count
  ограничен. Keys только в памяти, не repository/argv/capture/ledger.
- Actual [driver](evidence/claim-origin-probe-2026-10-21/driver.py), hashes inputs,
  references и utility фиксируются в Git до первой отправки.

## Field-only guard, без интеграции в приложение

После получения narrow answer offline проверяется одно поле:

| Predicted origin                            | Candidate claimant | Field proposal   |
| ------------------------------------------- | ------------------ | ---------------- |
| narrator / letter_1                         | совпадает          | field_consistent |
| narrator / letter_1                         | отличается         | field_mismatch   |
| other / indeterminate / operational unknown | любое              | field_review     |

`field_consistent` не принимает всю разметку; `field_mismatch` — сигнал
относительно предсказанного origin, а не доказательство фактов дела. Для старых
R029/R030 на S01 ожидаются consistent/mismatch, на S03 narrator должен
сохраниться. Это offline proposal, без production gate или изменения overall
decisions. Остальные поля и полнота разбора не проверяются.

## Метрики и ограничения

Для каждого arm: narrow agreement out of 2, полный origin contrast только при
обоих правильных labels; original-letter recovery S01 отдельно. Для TypeSafe
показать оба fresh baseline ответа и отличия от исторического CoreInfra.
Field replay оценивается отдельно от origin agreement, не как pipeline accuracy.
Показать все responses, attempts, errors, model, confidence/probabilities, usage,
cost unknowns и latency; пересчитать offline из capture.

Два exposed authored development sources, candidate references без independent
human gold; это не holdout, statistical model ranking, calibration или оценка
доли кейсов без критических ошибок. Если baseline уже исправился на native
route, нельзя объявить narrow tactic причиной улучшения. Если narrow ошибается,
не заменять label постфактум и не повторять semantic answer.

Условие положительного диагностического результата: оба origin controls
проходят у arm, и field proposal для исходной пары не отвергает faithful claimant
и обнаруживает mutant. Даже такой результат не разрешает production adoption:
следующий шаг — review и более широкий набор sources/unknown origins.
