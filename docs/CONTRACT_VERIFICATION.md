# Проверка контрактов и producer нового профиля

Дата: 2026-10-02. Область: NL-101/NL-102/NL-404, profile `demo.reform-mitigation/v1`. Решения и границы описаны в [CONTRACTS.md](CONTRACTS.md) и [REFORM_SEMANTICS.md](REFORM_SEMANTICS.md).

## Выполненные проверки

| Команда                 | Результат                                                                                                              |
| ----------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| `npm run check`         | TypeScript strict проходит для app, нового ядра, tests и schema exporter                                               |
| `npm test`              | 22 tests проходят: 11 прежних M0 и 11 новых v2                                                                         |
| `npm run test:lean`     | Семь integration tests проходят: две M0 и пять v2; подробности нового verifier в [Lean report](REFORM_VERIFICATION.md) |
| `npm run schemas:check` | Все десять generated JSON schemas совпадают с текущим Zod source                                                       |
| `npm run build`         | Typecheck и production bundle M0 проходят                                                                              |
| `npm audit --json`      | Ноль известных vulnerabilities в проверенном dependency graph                                                          |

`tests/reform.test.ts` использует Ajv 8.20.0 и ajv-formats 3.0.1 как dev dependencies. Все десять schemas компилируются по Draft 2020-12 в strict mode; проверенные artifacts принимаются как Zod, так и Ajv. Неизвестные поля отклоняются обоими validators. Проверена согласованность Unicode code-point limits, включая astral characters и границу длины с завершающим newline.

## Охват producer

- Все 128 комбинаций snapshot одной из двух групп с четырьмя состояниями M/N/E проверены во всех трёх моделях: **384 analyses**.
- Сохранены и проверены **1296 compatible completion branches**. Последствия каждой branch сопоставлены с зафиксированной таблицей NL-107.
- Открытые findings не превращаются в refuted, равные последствия не удаляют разные ветви.
- Exclusion E блокирует N, сохраняя M; summary ledger отражает unresolved status при различии branches.
- Rule IDs и порядок arrays не выбирают behavior и порядок M/N transforms.

## Отрицательные проверки

Проверено отклонение:

- duplicate rules, отсутствующего exclusion, нецелочисленной стадии и произвольного executable field;
- неподдержанной версии Legal IR и findings без rationale;
- изменённых source digests, package/profile locks и утраченных source mappings;
- потери или дублирования branch, ошибочного completion status, пропуска ledger и повторного transform;
- изменённого snapshot/query digest, переставленных baseline/candidate и скрытого сужения comparison scope;
- неполного finite-domain certificate, подменённых receipt roles, ложного coverage и `verified` metadata без требуемой toolchain/method.

## Что подтверждают эти свидетельства

Новый TypeScript producer согласован с finite fixture. Структурные и contextual contracts выполняют перечисленные checks. Отдельное изменение provenance при сохранении IR меняет provenance digest, сохраняя semantic digest.

Этот contract/producer audit сам по себе не является proof soundness/completeness независимого нормативного отношения. Contextual helpers не подтверждают candidate arithmetic или signature/issuer trust. Отдельный [Lean decision verifier](REFORM_VERIFICATION.md) проверяет arithmetic, ledger и completion coverage v2. Structural test receipt содержит synthetic unsigned bytes и статус inconclusive. Последующий [NL-405](COMPARISON_VERIFICATION.md) добавляет реальный signer/replay v2 для локального core/CLI flow; HTTP/UI остаются M0.

Исходные две Lean integration checks подтверждают M0. Новые пять проверяют A/B/C в отдельном Lean relation; их scope, axiom audit и границы описаны в [REFORM_VERIFICATION.md](REFORM_VERIFICATION.md).

## Оставшиеся этапы

- NL-104/NL-106 завершены для decision certificates текущего профиля; интеграция нового ядра в пользовательский flow остаётся отдельной задачей.
- NL-405 завершён в [отдельном отчёте](COMPARISON_VERIFICATION.md): property/comparison proofs, проверенный counterexample, signed receipts и CLI replay. Текущие totals: 28 unit/API tests и 12 Lean integration tests; таблица выше сохраняет свидетельства исходного contract/producer среза.
- NL-406 завершён в [отдельном отчёте](EXPLANATIONS.md): deterministic explanations и sidecar checks. Актуальный набор содержит 35 unit/API tests и 14 Lean integration tests. NL-502 сохраняет v2 HTTP/storage integration и пользовательский A/B/C flow.
- M3: hardened sandbox и полная identity проверяющего toolchain.

Исторический [M0 verification report](VERIFICATION.md) сохраняется отдельно.
