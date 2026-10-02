# Независимая проверка decision certificates v2

Дата: 2026-10-02. Область свидетельств ниже: NL-104/NL-106; `demo.reform-mitigation/v1`, D16 и locked models A/B/C. Последующий [NL-502](LABORATORY_UI.md) подключает этот pipeline к локальным HTTP/SQLite/UI рядом с M0/v1.

## Реализация

- [lean/Reform.lean](../lean/Reform.lean) определяет независимые `Permissible`, `BranchPermissible`, `WellFormed` и `ValidResult`.
- [server/reform-verifier.ts](../server/reform-verifier.ts) проверяет bindings и wire shape, конструирует конкретный statement и запускает точный Lean 4.30.0.
- [tests/reform-lean.integration.ts](../tests/reform-lean.integration.ts) проверяет producer, общие теоремы, повреждения certificates и статусы verifier.

Verifier не вызывает `interpretReform` для получения ожидаемого результата. Admission validation пакета пока использует существующий validator поддержанного IR; независимо от него Lean повторно проверяет модель, exact arithmetic всего D16 и candidate result. Негативные проверки строят statements напрямую, обходя TypeScript result guards.

## Отношение и теоремы

Для каждого completed input Lean выбирает ровно один baseline/M/N/exclusion по operation и group scope. `Permissible` требует сохранения qualification и fine, точного промежуточного M и уравнения для конечного N. Division задаёт промежуточный witness; уравнения исключают округление. E блокирует только N.

`BranchPermissible` дополнительно требует полный предписанный ledger и точный список M/N steps с before/after values. `ValidResult` проверяет модель, conditional status, все compatible completions в canonical order, каждую branch и summary ledger. Равные численные последствия не удаляют отдельные branches.

| Теорема                                                    | Утверждение                                                                             |
| ---------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| `domain_cardinality`, `domain_distinct`, `domain_complete` | D16 содержит 16 разных входов и весь тип `(K1/K2) × Bool³`                              |
| `permissible_unique`                                       | При valid parameters два допустимых полных последствия одного input совпадают           |
| `model_exists_unique`                                      | Для любого WellFormed model и input из D16 существует ровно одно допустимое последствие |
| `result_sound`                                             | Каждая branch принятого result удовлетворяет независимому отношению                     |
| `result_complete`                                          | Принятый result содержит все совместимые completions в заданном порядке                 |
| `outcome_complete`                                         | Каждое допустимое последствие каждого совместимого completion представлено в result     |
| `mandatory_complete`                                       | Каждая branch принятого result имеет предписанные ledger и ordered steps                |

Эти общие теоремы относятся к Lean relation и принятому result. Корректность TypeScript producer подтверждена исчерпывающей проверкой текущих A/B/C на 384 snapshots; универсальная верификация исходного TypeScript code для всех будущих пакетов не заявляется.

## Выполненные проверки

```sh
npm run check
npm test
npm run test:lean
npm run schemas:check
npm run build
```

- **22 unit/API/contract tests** проходят; прежний M0 сохраняется как regression scenario.
- **7 Lean integration tests** проходят: две прежние M0 и пять v2.
- **384 v2 decision results / 1296 branches** проверены kernel. Для A/B/C проверена `WellFormed` и применена общая theorem existence/uniqueness.
- Дополнительно проверены реальный `verifyReformDecision`, reordered locked rules, exact query/certificate/statement/toolchain digests и исключение source injection через narrative/rationale.
- **12 прямых негативных statements** отклонены kernel с обходом contextual result guards: missing M/N, wrong fine/qualification/intermediate value/order, double count, missing/false ledger, false summary, incorrect exclusion и lost completion. Отдельно runtime verifier отклоняет неверную арифметику.
- Изменённые snapshot/query/model bindings отклоняются до запуска Lean. Unary property query возвращает `unsupported`; недоступный exact Lean возвращает `inconclusive`.

Пакеты по восемь statements укладываются в установленный лимит **512 MiB**. Большой первоначальный пакет был отклонён по memory limit; проверка выполнена меньшими пакетами. Production decision ограничен 30 seconds, 512 MiB, `-T200000` и 128 KiB process output; batch tests используют собственные bounded limits. Повторный финальный прогон выполнен после устранения `ENOSPC`; отказ записи не считается kernel rejection.

## Audit и bindings

Используется `decide +kernel`, без native evaluation. После успешного процесса обязателен `#print axioms checked`; принимаются только `propext` либо отсутствие аксиом. Warning, неизвестная dependency, `sorryAx`, неполный audit или resource failure не дают `verified`. Общие теоремы и каждый batch certificate прошли тот же axiom allowlist. См. [Lean: validating proofs](https://lean-lang.org/doc/reference/latest/ValidatingProofs/) и [axioms](https://lean-lang.org/doc/reference/latest/Axioms/).

В generated source попадают только schema-bounded integers, booleans и фиксированные enum tokens. Rule IDs инъективно отображаются в индексы locked array; текст source/narrative/rationale и произвольный Lean code не интерполируются. `DEMO`, mandatory=true и applyCount=1 фиксированы wire schema; альтернативные значения не кодируются в этот Lean type и отвергаются на boundary.

`statementDigest` связывает точный core, generated statement, query, snapshot, bundle и certificate. `queryDigest`/`certificateDigest` возвращаются отдельно. `toolchainDigest` включает exact Lean identity из M0 discovery, core и source fingerprint нового checker/bindings/contracts/model validation, снятый при загрузке модуля. Изменение кода требует нового процесса; историческая проверка не становится текущей автоматически.

## Границы и следующий этап

Это проверка нормативного результата относительно locked synthetic IR и simulated findings. Она не проверяет истинность narrative, юридическую fidelity перевода source, выбор группы или реальный закон.

Проверки и количества выше фиксируют срез NL-104/NL-106. Последующий **[NL-405](COMPARISON_VERIFICATION.md)** реализует comparison/property proofs, bound counterexamples, signed receipts v2 и CLI export/replay; **[NL-406](EXPLANATIONS.md)** — explanations и sidecar checks. Срез NL-406 содержит 35 unit/API tests и 14 Lean integration tests; эти количества не означают повторного запуска всего набора при NL-502. Decision-only entry point по-прежнему отклоняет unary query; общий `verifyReformCertificate` поддерживает все три kinds. **[NL-502](LABORATORY_UI.md)** добавляет v2 storage/HTTP/UI для зарегистрированных synthetic fixtures. Hardened OS sandbox и полная supply-chain identity относятся к M3; bounded subprocess не объявляется OS sandbox.

Исторические [M0 report](VERIFICATION.md) и [contract/producer report](CONTRACT_VERIFICATION.md) сохраняют собственную область свидетельств.
