# NormLab ontology candidate 0.1.0

Подготовлено: 2026-10-04. Статус обоих пакетов: `candidate`. Это authoring artifacts, не подключённая runtime-интеграция и не утверждённая юридическая модель.

| Пакет                            | Namespace | Содержимое                                                               |
| -------------------------------- | --------- | ------------------------------------------------------------------------ |
| [case-core.yaml](case-core.yaml) | `nlcase`  | 14 классов, 12 отношений, 5 design policies, lifecycle review assertions |
| [parking.yaml](parking.yaml)     | `nlpark`  | 11 классов, 17 отношений, 4 design policies, lifecycle scope assessment  |

Базовое ядро содержит ревизию, участников, автомобиль, эпизод, место, время, источник/цитату, assertion, роль, review decision, деньги и unmapped mention. Parking extension добавляет размещение, место/зону, сессию, попытку/платёж, claims о разрешении, исправлении и санкции, scope assessment.

## Представление отношений

Отношения `placedAt`, `paymentTargetsVehicle`, `coversInterval` и подобные — определения predicates. Неподтверждённый instance link записывается через `nlcase:Assertion`, с subject/object, predicateRef, stance и source anchors; он не становится доверенным ребром из-за наличия в графе.

Core и parking subject/object relations являются альтернативами. Consumer должен обеспечить ровно один subject суммарно и допустимую комбинацию object/valueText. Нулевые минимумы в отдельных семействах позволяют parking assertion не иметь одновременно фиктивный core subject. Совместное ограничение не проверяется компилятором.

Фактические значения платного режима, времени и отрицаний — proposals; условия обязанности, штрафы и виновность не входят в vocabulary. Их определяет отдельный NormPackage и engine на reviewed inputs.

## Проверка и генерация

На локальном checkout Ontology `3d0c977c61fb4f725cbc4261fa8c6efad412f12b` без source изменений выполнены `ontologyc check` и `ontologyc compile --target typescript` для обоих пакетов: **PASS**. Компилятор собран отдельно в `/tmp/normlab-ontology-build`. Test suites не запускались.

Сгенерированы [core artifacts](generated/case-core/) и [parking artifacts](generated/parking/): normalized IR, refs/registry, types, Zod schemas, validators, relations, policies и state machines. Они сохранены без ручных правок и не импортируются в приложение. В текущий TypeScript build приложения каталог `ontology/` не включён.

Пример повторения из корня NormLab после сборки компилятора:

```bash
rtk proxy /tmp/normlab-ontology-build/debug/ontologyc check ontology/parking-pilot/case-core.yaml
rtk proxy /tmp/normlab-ontology-build/debug/ontologyc check ontology/parking-pilot/parking.yaml
rtk proxy /tmp/normlab-ontology-build/debug/ontologyc compile ontology/parking-pilot/case-core.yaml --target typescript --out ontology/parking-pilot/generated/case-core
rtk proxy /tmp/normlab-ontology-build/debug/ontologyc compile ontology/parking-pilot/parking.yaml --target typescript --out ontology/parking-pilot/generated/parking
```

Сборка при отсутствии бинарника:

```bash
rtk proxy swift build --package-path /Users/egor/Development/GitHub/0AL/Ontology --scratch-path /tmp/normlab-ontology-build --product ontologyc
```

[artifact-manifest.json](artifact-manifest.json) фиксирует compiler commit и SHA-256 входов/outputs. Manifest не является подписью, approval или доверенным registry lock.

## Что compiler PASS не доказывает

- Imports `specgraph.foundation@0.1.0` и `normlab.case-core@0.1.0` объявлены явно. Текущий resolver принимает imported concept по namespace, не читая содержимое импортированного пакета: `check` не подтверждает existence/identity каждого внешнего concept. Требуются consumer resolution и content locks. Core/parking outputs пока два отдельных registries.
- Fields `stance`, `role`, `precision`, `participantKind`, `decision`, `status` имеют тип `string`; допустимые значения описаны, но enum enforcement не сгенерирован. Это ограничение текущего compiler input format.
- Generated entity IDs optional, Zod objects не strict. Consumer должен потребовать IDs, запретить дубликаты и неизвестные поля, ограничить размеры и разрешённые model-output classes.
- Generated validators проверяют форму отдельной entity/локальный ref, а не полный instance graph. Cardinality, cross-package refs, domain/range, источник цитаты и правила revision binding требуют отдельного adapter.
- Lifecycle definitions не дают модели права выпустить ReviewDecision, CaseRevision или ScopeAssessment. Приложение владеет этими artifacts и переходами.
- Числа `MoneyAmount` не задают currency enum, единицы для вычисления и допустимые границы. Они представляют исходное утверждение; строгий денежный контракт будущего engine не подменяется ими.
- Все policies имеют `enforceability: design`. Source extraction, review, immutable storage и scope guards этим пакетом не реализованы.

## Competency questions

| Вопрос                                | Представление / corpus                                     | Что отдельно должен проверить consumer                      |
| ------------------------------------- | ---------------------------------------------------------- | ----------------------------------------------------------- |
| Кто участвовал и в какой роли?        | Participant + RoleAssignment; P01/P10/P12                  | Разделение owner/driver/user; aliases и attribution         |
| Какой эпизод выбран?                  | Episode + Assertion context; P06                           | Один выбранный эпизод, другие не теряются                   |
| Где и когда был автомобиль?           | ParkingPlacement, ParkingPlace/Zone, TimeInterval; P01/P05 | Unknown boundaries, точность, timezone, источники           |
| Была попытка или успешный платёж?     | PaymentAttempt/Payment; P12                                | Попытка не означает успешность                              |
| Какой автомобиль/зона оплачены?       | Assertion с paymentTargetsVehicle/Zone; P02/P04            | Реквизиты не объединяются автоматически                     |
| Чем различаются стоянка и сессия?     | ParkingPlacement/Session, интервалы; P14                   | Покрытие не выводится из одного списания                    |
| Почему две версии оплаты конфликтуют? | Два Assertion с evidence; P09                              | Совпадение контекста; review каждой версии                  |
| Откуда взялась названная сумма?       | SanctionClaim + MoneyAmount + Assertion; P11               | Source claim отдельно от engine output                      |
| Почему кейс неподдержан?              | Correction/Permit claims, ScopeAssessment; P04/P07/P08     | Application scope gate; model не присваивает trusted status |
| Как сохранить неизвестный нюанс?      | UnmappedMention + SourceSpan                               | Gap candidate не мутирует общую ontology                    |

## Ограничения consumer integration

1. Consumer whitelist подготовлен отдельно для C01–C17; scalar predicates остаются consumer vocabulary, не generated ontology concepts. Перевод reviewed assertions в engine findings ещё не реализован.
2. Bounded model-output envelope и graph validator подготовлены; семантическая корректность и полнота требуют review и corpus evaluation.
3. Проверка cross-package refs и domain/range; нельзя выдавать namespace-only resolution за полный import lock.
4. Raw source spans могут содержать имена: aliases не обеспечивают полного обезличивания источника.
5. Ontology approval после review candidate; compiler evidence не заменяет одобрение семантики.

Следующий шаг — структурированные reference graphs и baseline extraction по consumer contract.

Consumer contract v1 подготовлен в [документации](../../docs/PARKING_EXTRACTION_CONTRACT.md): strict model envelope, ограниченный scalar vocabulary и graph validation. Runtime/model integration пока отсутствует.
