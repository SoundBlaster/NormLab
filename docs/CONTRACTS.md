# Контракты нового профиля A/B/C

Версия среза: 2026-10-02. Реализовано для NL-101/NL-404. Семантика — [REFORM_SEMANTICS.md](REFORM_SEMANTICS.md), свидетельства — [CONTRACT_VERIFICATION.md](CONTRACT_VERIFICATION.md).

## Статус и совместимость

V2 реализован как отдельное типизированное ядро и набор artifact contracts. HTTP API, SQLite и UI продолжают использовать M0/v1. Существующие данные не мигрируются автоматически. Сборка locked bundles A/B/C выполняется из [зафиксированного fixture](../fixtures/reform-v1/README.md).

Литерал `schema` выбирает точный поддержанный контракт. Старый certificate v1 не становится certificate v2 после изменения имени поля. Для нового профиля реализован отдельный [decision verifier/statement constructor](REFORM_VERIFICATION.md); HTTP verifier продолжает проверять M0. Неизвестная версия или профиль не дают статус `verified`.

Для producer сохраняется TypeScript. Независимое отношение допустимости и Lean decision verification нового профиля реализованы в NL-106. Основание выбора: сохраняется существующее разделение producer/checker, а ограниченный D16 позволяет проверять все комбинации без добавления нового compiled runtime. Возможный перенос producer в Lean должен сохранять эти контракты и независимость проверки.

## Источник schemas

[shared/reform-contracts.ts](../shared/reform-contracts.ts) содержит строгие Zod schemas и TypeScript types. Из них генерируются десять [JSON Schema](../schemas/v2/README.md) по [Draft 2020-12](https://json-schema.org/draft/2020-12) средствами [Zod](https://zod.dev/json-schema).

```sh
npm run schemas:write
npm run schemas:check
```

Генератор использует `unrepresentable: throw`. Файлы schemas являются generated artifacts; изменение выполняется в Zod source и затем регенерируется. Идентификаторы `urn:normlab:contract:v2:*` служат локальными идентификаторами schemas, без сетевого resolver.

| Artifact        | `schema`                              | Основная ответственность                                             |
| --------------- | ------------------------------------- | -------------------------------------------------------------------- |
| SemanticProfile | `normlab.semantic-profile/v1`         | Completion, порядок стадий, арифметика и поддержанная область        |
| Legal IR        | `normlab.legal-ir/v2`                 | Типизированные обязательные правила, их scope и operations           |
| NormPackage     | `normlab.norm-package/v1`             | IR, источник, mappings, версия и author/review provenance            |
| NormBundle      | `normlab.norm-bundle/v1`              | Точный пакет и профиль, locks, semantic/provenance digests           |
| SnapshotInput   | Artifact без собственного envelope    | Narrative, группа и три мотивированных findings                      |
| Snapshot        | `normlab.snapshot/v2`                 | Immutable content, simulated authority, supersession и digest        |
| DecisionResult  | `normlab.decision-result/v2`          | Все completions, последствия, branch ledgers, steps и summary ledger |
| Query           | `normlab.query/v2`                    | Decision, comparison или unary property; точные входы и роли         |
| Certificate     | `normlab.certificate/v2`              | Candidate result, связанный с полным query digest                    |
| SignedReceipt   | `payload.schema = normlab.receipt/v2` | Bindings, отдельный coverage и claimed verification metadata         |

## Structural и contextual validation

Все объекты strict: неизвестные поля, произвольный код и пользовательский Lean source отклоняются. Никакие imports, expressions или provider calls этот профиль не выполняет.

JSON Schema/Zod проверяют форму, enum, пределы чисел и размеров. Контекстные helpers дополнительно проверяют:

- уникальность rules и точное покрытие их source mappings;
- наличие ровно одного base/M/N/exclusion для каждой группы;
- уменьшение, целочисленность каждой стадии и поддержку пакета на всём D16;
- source digest, package/profile locks и оба bundle digests;
- snapshot integrity, rationale и completion coverage;
- наличие каждого rule в ledger, отсутствие повторного transform и ссылки exclusion;
- query roles, references, допустимый scope, certificate и receipt bindings;
- заявленный размер coverage и согласованность proof metadata.

Эти helpers не проверяют истинность findings или fidelity естественного исходного текста. Source mapping подтверждает адрес и наличие именованного положения; нормативный смысл перевода требует review.

`validateReformCertificateBindings` и `validateReformReceiptBindings` проверяют связи и структурную согласованность. Они не удостоверяют arithmetic candidate, signature, issuer trust, statement или факт запуска Lean. `verifyReformCertificate` независимо проверяет все три query kinds; `verifyReformDecision` сохраняет decision-only интерфейс. [Signer/replay v2](COMPARISON_VERIFICATION.md) проверяет signature trust и fresh proof отдельно. Полученный из внешнего artifact `verification.status` остаётся недоверенным до самостоятельной проверки.

## Query и comparison contract

Domain D16 зафиксирован: две группы × три boolean findings, все 16 комбинаций. Identity mapping сопоставляет `qualification`, `prisonMonths`, `fineAmount`, `currency`. Ledger/source IDs отличаются между A/B и не входят в equality последствий.

| Kind         | Bindings и область                                                                     |
| ------------ | -------------------------------------------------------------------------------------- |
| `decision`   | Exact snapshot digest и `model` bundle reference; все совместимые completions          |
| `comparison` | Отдельные `baseline` и `candidate`, identity mapping, property и разрешённое condition |
| `property`   | Один `model`; строгое смягчение M при прочих равных, восемь пар                        |

Reference включает bundle ID, semantic/provenance и profile digests. Query digest хеширует весь query, включая roles, domain, assumptions и conditions. Перестановка A/B создаёт другое утверждение, даже если набор bundle digests тот же.

Для `equivalence` и `component-no-increase` condition должно быть null: весь D16. Для `strict-reduction` condition равно M=true, для `preserved-outside` — M=false. Другие conditions и ontology mappings требуют новой поддержки; scope не сужается автоматически.

Comparison certificate содержит строки входов и обоих последствий. Property certificate содержит пары M=false/M=true при одинаковых группе/N/E. `exhaustive-finite-domain` требует всех строк объявленной области в canonical order; `corpus` допускает явно частичное покрытие. Повторы, чужие входы и witness вне представленных rows/pairs отклоняются.

Receipt coverage хранит domain digest, kind, declared/covered cardinality и отдельный status. Для decision область — completions snapshot, для comparison — D16 либо зафиксированные восемь случаев, для unary property — восемь пар. Coverage должен совпадать с query и certificate, а не только быть арифметически правдоподобным числом. `corpus` всегда получает `partial` и `case-theorem`, даже при совпадении cardinalities. `exhaustive-finite-domain` требует `declared-complete` и `finite-domain-theorem`; actual theorem проверяется независимо.

Strict envelope `normlab.reform-export/v1` содержит query, bound bundles, snapshot/null, certificate и receipt. Его Zod schema — [server/reform-receipts.ts](../server/reform-receipts.ts); он не добавляет одиннадцатую generated JSON schema. Import/replay ограничен 512 KiB и требует отдельно переданный trusted public key. Bindings helpers отклоняют duplicate bundle IDs; verifier нормализует bundle order по query roles.

## Encoding, digests и ограничения

Canonical encoding использует [server/hash.ts](../server/hash.ts): ключи объектов сортируются, порядок массивов сохраняется, строки кодируются через JSON, принимаются только safe integers. Unicode normalization не выполняется. Это ограниченный формат NormLab; совместимость с иным canonical JSON standard не заявляется.

- `packageDigest` — весь NormPackage; `profileDigest` — весь SemanticProfile.
- `semanticDigest` — `{ profile, ir }`; rule IDs и порядок arrays являются частью представления.
- `provenanceDigest` — ID/версия, author/review, source kind/content/digest и mappings.
- Source digest — digest canonical JSON string исходного текста, а не хеш сырых файловых байтов.
- Snapshot digest вычисляется по всему содержимому без поля `digest`.
- Certificate/result/query/assumptions digest вычисляются по соответствующим полным artifacts.

Эквивалентные последствия не требуют одинакового semantic digest: это свойство моделей, которое нужно проверить отдельно. Изменение source при неизменном IR меняет provenance и package lock, сохраняя semantic digest.

Предельные значения: 12 rules, 8 decision branches, 16 comparison rows, 8 unary pairs; срок 0–3600 месяцев, штраф 0–1 000 000 DEMO, множители 1–12 с numerator ≤ denominator. Narrative ограничен 6000 Unicode code points, rationale — 2000, source — 32768. Для чисел исключены NaN, Infinity и дробные wire values.

`parseReformJson` ограничивает serialized envelope 512 KiB в UTF-8 до `JSON.parse`. Этот helper относится к новому artifact boundary; действующий HTTP API M0 сохраняет собственный лимит 32 KiB. Новый endpoint ещё не добавлен.

Ошибочная известная структура или нарушенный invariant отклоняются; неизвестный profile/Legal IR version и нецелочисленная стадия получают `ReformContractError` с `code = unsupported`. Ошибки формы возвращаются как Zod validation errors. Преобразование этих ошибок в HTTP responses относится к интеграции API.

## Следующая интеграция

Decision relation, Lean statement constructor и kernel verification v2 реализованы; [свидетельства](REFORM_VERIFICATION.md) включают все 384 snapshots A/B/C. [NL-405](COMPARISON_VERIFICATION.md) добавляет comparison/property proofs, bound receipts и CLI export/replay; [NL-406](EXPLANATIONS.md) — отдельные explanation/report Zod contracts и проверяемые JSON sidecars. Эти schemas не изменяют прежние десять generated JSON schemas и receipt bindings. Следующий срез — метрики, v2 snapshots, анализ и A/B/C HTTP/UI. Исторические receipts M0 сохраняют свои версии и toolchain identity; изменение dependency lock меняет identity нового запуска verifier.
