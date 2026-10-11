# ProxyAPI verifier turn — 2026-10-09

## Что подключено

Experimental provider из PR #36 подключён к отдельному one-batch runner
`evaluation/run_verifier.py`. Manifest фиксирует source, named questions, provider,
model, budget и Noul policy. `evaluation/harness.py` поддерживает SDK-free replay
нового verifier capture; прежний classification replay сохранён.

## Live evidence

Один авторизованный POST к `https://api.proxyapi.ru/v1/decisions`, без retries.
Ключ взят только из `PROXYAPI_API_KEY` и не сохранялся в артефакты.

Source: «Я оплатил парковку. В письме: парковка не оплачена.» Все три вопроса
относятся к содержанию письма; labels для оценки качества в запрос не включались.

| Primitive | Ответ |
|---|---|
| Noul: письмо утверждает отсутствие оплаты? | `p_yes=1.0`, policy outcome `pass` |
| Choice: позиция письма об оплате | `denied`, confidence `0.99` |
| Score: явность сообщения об отсутствии оплаты | `1.96` по шкале 0–2, confidence `0.94` |

- HTTP 200; один вызов, три вопроса.
- Requested model: `openai/gpt-6-luna-decisions`.
- Returned model: `openai/gpt-6-luna-decisions-20261006`.
- Request ID: `gen-dec-1791528021-wx2U1MQFut3X3WAiE330`.
- Returned usage: 521 input / 0 output tokens. Нулевой output записан как вернул
  поставщик; самостоятельного измерения тарификации нет.
- Измеренное время provider invocation: 380.113 ms; цена неизвестна (`null`).
- Dependencies: adapter 0.3.0, typesafe-sdk 0.7.2, httpx2 2.13.1.
- Manifest SHA-256: `c0c310f9ca3824a10a868fda37076adc1a1ffd8b9b4a78552662ef5475e3dfaa`.
- Source SHA-256: `e2c7ce0cf61e3d4f696037e352824c1bc8d2fe0bf65693ce88355f361a38ce96`.

[Manifest](../fixtures/parking-pilot/evaluation-harness/verifier-smoke.json) и
[capture](../fixtures/parking-pilot/evaluation-harness/verifier-live-capture.json)
сохранены для независимого offline replay. Полный локальный run с исходными
snapshots и unsigned artifact hashes находится в ignored
`.artifacts/proxyapi-turn-live-20261009/`.

## Verification

- 58/58 локальных pytest checks: provider contracts, capture/replay и прежние
  Mellea control-flow fixtures.
- Mock HTTP через реальный adapter: success, HTTP/protocol/transport failures,
  один вызов без retries, `uncertain` не превращается в `pass`, отсутствие ключа
  в snapshots/capture, отклонение изменённого source binding и boolean probability.
- Командный offline replay с `python -S`, без site packages и API key, прошёл.
- SDK-free replay настоящего capture воспроизводит report; live inference при
  replay не выполняется. `calls=1` описывает исходный capture.

Команды приведены в [HARNESS.md](../evaluation/HARNESS.md).

## Что это доказывает

Проверенный provider совместим с тремя primitives на одном запросе; сохраняются
model/request ID/usage, distributions и policy outcome. Для этого текста модель
различила позицию автора и утверждение письма.

Это не оценка общей semantic accuracy или цели 50%/80%, не benchmark latency,
не production/UI integration и не доказательство Mellea repair loop. Поэтому
`criticalErrorFreeRate=null`, `quality=not_evaluated`. Других live calls и corpus
run в этой проверке не было.

## Следующий эксперимент

Сначала Stage 1 representability audit на 12–16 diagnostic случаях с независимой
разметкой отрицаний, attribution и противоречий. Затем одинаковые manifests и
policy для paired Jev / Luna Responses Low / Luna Decisions сравнения. Расширение
runner на другие providers и MLflow import остаётся отдельной задачей.
