# Parking extraction contract v1

Статус: candidate consumer contract, 2026-10-04. Основание — [ontology package](../ontology/parking-pilot/README.md) и [условия C01–C17](PARKING_CONDITIONS.md). Это исполняемая проверка proposals; HTTP/UI и локальная модель ещё не подключены.

## Артефакты

- [Zod schema, types и graph validator](../shared/parking-contracts.ts).
- [JSON Schema draft 2020-12](../schemas/parking/extraction.schema.json).
- [Application request и prompt](../server/parking-extraction.ts).
- `npm run schemas:write` обновляет schema; `npm run schemas:check` обнаруживает расхождение.

Schema генерируется из consumer Zod contract, который сужает candidate vocabulary. Compiler SDK не заменяет его. Domain/range разрешённых link predicates берутся из normalized IR обоих пакетов, а не дублируются вручную. В core разрешён Episode как assertion object: это нужно связям контекста эпизода.

## Envelope модели

Единственный JSON object содержит `schema`, `entities`, `spans`, `assertions`, `unmappedMentions`. Все поля и вложенные объекты strict. Дополнительные поля, review decisions, ScopeAssessment, команды, SourceDocument, locks и результаты запрещены.

| Collection       | Назначение                                                                                   | Limit |
| ---------------- | -------------------------------------------------------------------------------------------- | ----- |
| entities         | Только 16 разрешённых concept variants; поля и enum ограничены                               | 128   |
| spans            | Exact quote, обязательные offsets внутри одного source                                       | 512   |
| assertions       | Subject, predicate, episode context, stance, evidence, attribution; object **или** valueText | 256   |
| unmappedMentions | Нюанс, невыразимый текущим словарём; evidence, optional episode                              | 64    |

Все IDs обязательны и уникальны **между всеми collections**, regex `[A-Za-z][A-Za-z0-9_-]{0,63}`. Evidence: 1–8 уникальных span IDs. attributedTo: 0–8 уникальных Participant IDs. Эпизоды — entities `nlcase:Episode`; модель не выбирает один для расчёта. Every assertion has exactly one episode context; links targeting an Episode must match it. Нет поля raw edges: каждый domain link — самостоятельный assertion.

Модель может предложить неполный граф, включая пустые collections. При отсутствии распознаваемого события source-backed nuance сохраняется в unmappedMentions. Успешная validation не означает полноту данных; downstream review должен предложить отсутствующие обязательные обстоятельства.

## Predicates

16 link predicates перечислены в `parkingLinkPredicates`; их domain/range следуют пакетам. Например `nlpark:paymentTargetsVehicle`: Payment → Vehicle; `nlcase:roleParticipant`: RoleAssignment → Participant. Служебные relations review/source/revision нельзя выдавать как model links.

15 scalar predicates имеют отдельный prefix `nlinput:` и version binding consumer contract. Они **не объявляются импортированными ontology concepts**. Текущий compiler не описывает scalar predicate constraints, поэтому это явный consumer vocabulary поверх ontology classes.

| Condition | Predicate            | Subject          |
| --------- | -------------------- | ---------------- |
| C02       | eventTime            | Episode          |
| C03       | inMoscow             | Location         |
| C04       | cityParking          | ParkingPlace     |
| C05       | placement            | Episode          |
| C06       | paidRegime           | Episode          |
| C07       | subjectScope         | Episode          |
| C08       | attribution          | Episode          |
| C09       | payment              | Episode          |
| C10       | paymentStart         | Payment          |
| C11       | departure            | ParkingPlacement |
| C12       | paymentComplexity    | Episode          |
| C13       | permit               | Episode          |
| C14       | disabilityConditions | Episode          |
| C15       | specialTariff        | Episode          |
| C16       | faultAndExclusions   | Episode          |

C01 выражается Episode, instances, role/context/vehicle links. C17 — SanctionClaim, sanctionAboutEpisode и sanctionAmount → MoneyAmount. paymentStart — исходное время, не вычисленная своевременность. `valueText` сохраняет исходную формулировку; это не boolean, normalized date или engine input. Следующий adapter должен отдельно переводить reviewed assertions в typed findings. Соответствие таблице не утверждает достаточность юридической модели.

`stance` относится к исходному высказыванию: asserted / denied / uncertain. Явно указанное неизвестное сохраняется как uncertain. Молчание — отсутствие assertion; оно не превращается в denied. Opposing assertions сохраняются, validator не выбирает победителя и не объявляет любые разные строки конфликтом. Выявление смысловых противоречий — отдельный downstream шаг. Cardinality каждого assertion обеспечивается envelope; min/max отношений между reviewed facts пока не проверяются. Несколько противоположных proposals о роли не отклоняются как нарушение cardinality.

## Source integrity и bindings

Application создаёт immutable request snapshot через `createParkingExtractionRequest(sourceRevisionId, sourceText)`. Request хранит ID, source revision и SHA-256 текста, contract/schema digest и SHA-256 ontology YAML из artifact manifest. Модель получает instructions, source text, каталог scalar predicates и JSON Schema. Bindings возвращаются приложением, а не извлекаются из ответа модели.

`consumeParkingExtraction(raw, issuedRequest)` проверяет bindings и graph, возвращает `unreviewed` proposal. Вызывать только с сохранённым приложением request соответствующего запуска; функция не удостоверяет произвольный JSON, выдаваемый за request. HTTP ingestion и persistence пока отсутствуют. Старый request сохраняет старую source revision; принятие результата в текущую рабочую ревизию должен блокировать будущий orchestration layer при изменении source.

Offsets — JavaScript UTF-16 code units, exclusive end, без normalization. `source.slice(startOffset,endOffset) === quote`; непустой диапазон в пределах source, без разделения surrogate pair. Runtime source limit — 32768 UTF-16 units; raw model-output limit — 262144 units до JSON.parse. String lengths в Schema считаются Unicode code points. JSON Schema не может проверить цитаты или resolution refs: для этого обязателен graph validator. Повторяющиеся JSON object keys JSON.parse разрешает по стандартному поведению последнего значения; duplicate artifact IDs всегда отклоняются.

Validation подтверждает происхождение цитаты, а не то, что цитата поддерживает семантику assertion. Ограничения не предотвращают hallucinations, косвенные prompt injections или ошибочную классификацию. Every accepted proposal requires human review. Алиасы не обезличивают raw source/quotes.

## Минимальный пример

Source: `Я не оплатил парковку.`

```json
{
  "schema": "normlab.parking-extraction/v1",
  "entities": [
    { "id": "episode1", "concept": "nlcase:Episode", "label": "Парковка", "evidence": ["span1"] }
  ],
  "spans": [
    { "id": "span1", "quote": "Я не оплатил парковку.", "startOffset": 0, "endOffset": 22 }
  ],
  "assertions": [
    {
      "id": "claim1",
      "subject": "episode1",
      "predicate": "nlinput:payment",
      "valueText": "оплатил парковку",
      "stance": "denied",
      "aboutEpisode": "episode1",
      "evidence": ["span1"],
      "attributedTo": []
    }
  ],
  "unmappedMentions": []
}
```

Это proposal о неуплате. Москва, платный период, C12, льготы и другие необходимые обстоятельства здесь неизвестны; вычислять нарушение нельзя.

## Границы и следующий шаг

Не реализованы provider adapter, HTTP/UI, persistent drafts/review, semantic conflict detection, полнота C01–C17, ontology approval, нормативный lock, перевод valueText в engine findings и вычисление scope/санкции. Generated SDK остаётся authoring artifact; приложение использует его normalized IR только для domain/range.

Следующий шаг: структурированные reference graphs P01/P02/P04/P09 и baseline GPT OSS 20B. Проверять отдельно schema/ref/source errors, пропуски/галлюцинации, episodes, отрицания, роли и latency; acceptance criteria согласовать до расширения scope.
