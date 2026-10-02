# Comparison proofs и signed receipts v2

Дата: 2026-10-02. Статус: **NL-405 выполнен** для `demo.reform-mitigation/v1`. Реализован локальный core/CLI flow; HTTP, SQLite и React UI продолжают использовать M0/v1.

## Проверенные утверждения

| Query                                    | Область            | Результат                                                               |
| ---------------------------------------- | ------------------ | ----------------------------------------------------------------------- |
| A/B equivalence                          | D16, все 16 inputs | Полные типизированные последствия равны                                 |
| A/C component-no-increase                | D16, все 16 inputs | Срок не увеличен; qualification, fine и currency сохранены              |
| A/C strict-reduction                     | M=true, 8 inputs   | Срок строго уменьшен; остальные последствия сохранены                   |
| A/C preserved-outside                    | M=false, 8 inputs  | Полные последствия равны                                                |
| strict-M-mitigation отдельно для A, B, C | 8 пар на модель    | При одинаковых group/N/E переход M=false → M=true строго уменьшает срок |
| A/D preserved-outside                    | M=false, 8 inputs  | Проверен bound counterexample: K1, N=true, E=false, 90 → 80 месяцев     |

Это свойства относительно locked synthetic models и принятого formal relation. Истинность narrative/findings, выбор группы, fidelity перевода source и соответствие реальному праву находятся за пределами доказательства. Наличие `verified` у counterexample подтверждает свидетель нарушения; verdict остаётся `counterexample`.

## Producer и независимый checker

[server/reform-queries.ts](../server/reform-queries.ts) создаёт query и candidate certificate через TypeScript producer. [server/reform-verifier.ts](../server/reform-verifier.ts) строит Lean statement из authenticated query и locked bundles, не вычисляя ожидаемые последствия через producer.

[lean/Reform.lean](../lean/Reform.lean) проверяет `WellFormed` обеих моделей, каждое последствие через `ModelPermissible`, точный scope, уникальность inputs, coverage, property и фактическое присутствие witness в переданных rows/pairs. Unary pair меняет только M. Currency фиксирована wire schema как DEMO; qualification и fine входят в Lean relation.

- `comparison_scope_sound` и `property_scope_sound` связывают полное canonical coverage с утверждением для любого input заявленной области и любых допустимых последствий. Единственность этих последствий следует из ранее доказанной `model_exists_unique`.
- `comparison_counterexample` и `property_counterexample` подтверждают scope, допустимость обоих последствий и нарушение свойства конкретным witness.
- Generated `checked` всегда проходит kernel и axiom audit. Полный `holds` дополнительно предъявляет `scopeChecked`; counterexample — `scopeRefuted`.
- Для `corpus` проверяются только переданные строки/пары. Даже corpus из всех 16 inputs остаётся `coverage.status=partial`, `method=case-theorem`; универсальная theorem автоматически не добавляется.

Используется точный Lean 4.30.0, `decide +kernel` и allowlist только `propext` либо отсутствие аксиом. Warning, неполный audit, другая dependency, недоступный toolchain или resource failure не дают `verified`. Лимиты процесса: 30 seconds, 512 MiB, `-T200000`, 128 KiB output. Основания механизма проверки: [Lean proof validation](https://lean-lang.org/doc/reference/latest/ValidatingProofs/) и [axioms](https://lean-lang.org/doc/reference/latest/Axioms/).

## Ошибочный вариант поправки

[Отдельный источник D](../fixtures/reform-counterexample/source.md) сохраняет усиленное смягчение M из C, но ошибочно меняет N с 3/4 на 2/3. Это поддержанный профиль с integral arithmetic; никаких специальных branches по package ID в interpreter/checker нет.

Вне M изменяются два случая: K1 даёт 90 → 80, K2 — 180 → 160 месяцев при N=true, E=false. Certificate связывает первый witness с фактической строкой полного scope.

Исходный design fixture `C-missing-exclusion` сохранён. В текущем profile отсутствие exclusion нарушает требование ровно одного base/M/N/exclusion на группу и отклоняется при admission validation. Такой пакет не представляется как допустимая модель с verified comparison. Его учебный арифметический аудит и новый допустимый counterexample имеют разные области свидетельств.

## Подпись, trust и replay

[server/reform-receipts.ts](../server/reform-receipts.ts) реализует Ed25519 signer, strict export envelope и replay. Signer самостоятельно запускает independent verification и подписывает только `verified`; вызывающий код не может передать готовые verification metadata.

Receipt связывает query, assumptions, ordered model roles/references, certificate, result, statement и toolchain digests. Coverage и verdict хранятся отдельно от proof status. Подпись проверяется через [Node.js crypto sign/verify](https://nodejs.org/download/release/v26.5.0/docs/api/crypto.html#cryptosignalgorithm-data-key-callback) над canonical payload; принимается Ed25519 key и canonical Base64 signature длиной 64 bytes.

Replay выполняет последовательно:

1. Проверяет подпись и exact public-key pin, явно предоставленный пользователем. Вложенный public key сам по себе не устанавливает trust.
2. Проверяет integrity/locks и все contextual bindings query/certificate/receipt.
3. Повторно строит statement и запускает текущий Lean checker.
4. Сравнивает statement digest и claimed verification metadata с новым результатом. Только совпадение даёт `current=true`.

Историческая квитанция с valid signature и bindings может получить `current=false`, даже если fresh proof успешен: её toolchain claim отличается. Подписанная ложная арифметика также не проходит fresh proof. `exportReformArtifacts` проверяет структуру и bindings; signature trust устанавливается отдельно при replay.

`statementDigest` включает точный core, generated statement, query, snapshot/null, ordered bound bundles и certificate. `toolchainDigest` включает exact Lean identity, core и source fingerprint verifier/bindings/contracts/model validation, снятый при загрузке модуля. Producer и receipt signer не заменяют proof checker. Полная supply-chain identity и OS sandbox остаются M3; изменение кода требует нового процесса.

## Воспроизведение

Из корня проекта с установленным exact Lean:

```sh
npm run reform:demo
```

Команда создаёт новый каталог `.artifacts/reform-demo-…`, JSON exports, `manifest.json` и `issuer-public.pem`. Срез NL-405 предъявил восемь general exports с issuance и отдельным fresh replay. [NL-406](EXPLANATIONS.md) расширяет текущий demo до 12 exports, добавляя conditional decisions и JSON/Markdown explanations. Private key существует только в памяти demo. Артефакты не входят в Git. Для выбранного нового каталога можно передать `--out .artifacts/my-reform-run`; существующий каталог не перезаписывается.

Используйте выведенный каталог как `<run>`:

```sh
npm run reform:verify -- <run>/AB-equivalence.json --issuer-key <run>/issuer-public.pem
npm run reform:verify -- <run>/AD-preserved-outside-counterexample.json --issuer-key <run>/issuer-public.pem
```

CLI требует отдельно выбранный trusted key, ограничивает export 512 KiB и key file 16 KiB, печатает signature/bindings/current/fresh verification и завершает процесс с ненулевым кодом при `current=false`. Публичный ключ demo пригоден для проверки этого локально созданного run; доставка доверенного ключа внешнего issuer — отдельная задача управления trust.

Envelope `normlab.reform-export/v1` содержит strict query, один/два bound bundles, snapshot/null, certificate и receipt. Его Zod schema находится в receipt module; существующие десять generated JSON schemas v2 не изменены. Публичный release/import workflow и установка replay в чистой среде остаются NL-503/NL-504.

## Свидетельства проверки

- `npm test`: **28 tests**, включая шесть новых comparison/coverage/binding/export tests.
- `npm run test:lean`: **12 integration tests**, включая пять новых comparison/property/signature/replay tests; все четыре общие scope/witness theorem проходят allowlist audit.
- **13 новых ложных statements** отклонены kernel в обход contextual result guards: потеря/дублирование/порядок coverage, неверные срок/штраф/qualification, ложный `holds`, ложный или несвязанный witness, input вне scope, потеря unary pair и изменение E внутри pair.
- Проверены wrong issuer, payload/assumptions tampering, trusted signed historical toolchain claim, signed false arithmetic и отказ signer выпускать receipt для rejected result. Persistent issuer сохраняет identity при перезапуске и создаёт private key с `0600`.
- Сохранены прежние M0 checks и v2 decision checks: **384 results / 1296 branches**, девять общих relation theorems и 12 прямых негативных decision statements.
- TypeScript strict и schema freshness проходят. Обычный `npm run build` сначала столкнулся с `ENOSPC` при записи временного Vite config; `npm run build -- --configLoader runner` выполнил typecheck и production build без этого временного файла. Финальный повтор обычного `npm run build` также прошёл. Восемь demo exports проходят replay в отдельных процессах verifier.

Последующие [NL-406](EXPLANATIONS.md) и [NL-108](METRICS.md) реализуют deterministic explanations, separate metrics и sidecar replay. Следующий срез — NL-502: интеграция v2 pipeline в storage/HTTP/UI. M1 остаётся открытым до пользовательского A/B/C flow; totals выше сохраняют свидетельства NL-405.
