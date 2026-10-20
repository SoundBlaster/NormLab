# Clairic: Unicode и кавычки, мини-абляция 2×2

Дата: 2026-10-20. Ledger: [#70](https://github.com/SoundBlaster/NormLab/issues/70).
Поручение: проверить гипотезу пользователя, что модель требует очистки текста
от непонятных символов после [RU smoke](CLAIRIC_RU_UNICODE_SMOKE_2026-10-20.md).

## Frozen protocol до inference

[Plan/fixtures](../fixtures/providers/clairic-text-ablation-v1.json): четыре
условия, те же шесть полей и **байт-в-байт одинаковые инструкции**.

| Порядок | Case                     | Emoji / combining mark | Кавычки |
| ------- | ------------------------ | ---------------------- | ------- |
| 1       | `ablation-original`      | Сохранены              | `«…»`   |
| 2       | `ablation-unicode-clean` | Удалены                | `«…»`   |
| 3       | `ablation-ascii-quotes`  | Сохранены              | `"…"`   |
| 4       | `ablation-both`          | Удалены                | `"…"`   |

Точные преобразования: удалить только начальный U+1F642 с последующим пробелом
и U+0301 из marker; отдельно заменить U+00AB/U+00BB на U+0022. Удаление ударения
**не является NFC normalization**. Оно меняет marker, поэтому expectation этого
поля меняется вместе с input. Остальные ожидаемые слова, отрицание, имена и время
не меняются. Оригинальная fixture/исторический capture остаются неизменными.

Свежий original — текущий контроль, предыдущий live capture не подставляется
вместо него. Unicode factor объединяет две замены и не отделяет вклад emoji
от combining mark. У каждого условия только одно наблюдение, fixed order;
случайность/порядок/доступность provider не контролируются полностью.

### Caps и stopping rule

Максимум **4 HTTP attempts**, по одному на условие;0 retries/fallback calls.
Официальный Workers AI endpoint/model clairic,30s socket timeout и1MiB response
bound на call. При HTTP/network/protocol failure оставшиеся calls остановить.
Semantic mismatch не останавливает остальные условия. Credential в памяти;
не публиковать account/token. Provider usage/passes считать как возвращены;
фактический денежный лимит аккаунта этим скриптом не устанавливается.

### Scoring до inference

- Exact typed values: шесть checks, `null` отдельно от отсутствующего поля/guess.
- Exact expected occurrences: пять non-null spans по frozen annotations каждого
  transformed input. Нельзя сравнивать их с offsets оригинального текста.
- Для этой абляции достаточно одного или нескольких общих candidate conventions
  на всех полях: code points / UTF16 / UTF8, end-exclusive. После удаления emoji
  code points и UTF16 могут не различаться; это не ошибка модели. Не объявлять
  неоднозначные единицы установленными. Старый RU scorer сохраняет свою policy.
- Overall pass требует exact values, совместимых exact expected spans и
  `truncated=false`. Фактические outputs/quotes не trim-ить перед scoring.
- Отдельный описательный diagnostic: соответствует ли каждый actual returned
  value source slice по его provider span. Он не исправляет frozen score.
- Go/no-go: сравнить, исчезает ли лишняя closing quote в зависимости от факторов.
  Один sample/cell может дать лишь рабочую гипотезу; production preprocessing
  и причинность/статзначимость не объявляются доказанными.

## Запуск

```bash
python3 scripts/clairic_smoke.py --case ablation-original
# Тот же CLI --live для каждого из четырёх case по frozen order/caps.
```

До вызовов закрепить script, fixtures, expectations и этот protocol в Git;
проверить offline controls, anchors, старый replay и форматирование.

## Результат

Pending. Текущий документ не разрешает дополнительные автоматические прогоны.

## Граница возможного внедрения

Даже при улучшении нельзя просто удалить символы из пользовательской фабулы и
считать offsets привязанными к оригиналу. Для будущего preprocessing нужен
отдельный derived text с provenance, точное отображение диапазонов обратно
на original и явное сохранение непредставимых/неоднозначных привязок. Удаление
символов может менять смысл; разбор исходного текста остаётся доступным.
Здесь такой mapper и production cleaning не реализуются.
