# Neutral offline replay fixtures

Один synthetic source, одна contrast family, три записи: два completed classification candidates и один смоделированный transport failure. Нейтральные IDs не сообщают качество candidate. Source/parent взяты из существующих Mellea control-flow fixtures.

`experiment.json` содержит только captures и исходные данные. `reviewer-labels.json` содержит candidate payment expectations и отдельно передаётся scorer. Manifest/dataset binding — SHA-256 bytes, labels привязаны к hash manifest. Actual definitions сохранены для воспроизводимого replay, не для нормативной актуальности.

Captures R001–R003 не получены от живой модели. Включение defective candidate и failure предназначено для диагностики scorer/denominators, а не для оценки model quality. Human labels не экспертные; complete case-level review не проведён.

Команды и контракт: [HARNESS.md](../../../evaluation/HARNESS.md).

`verifier-smoke.json` и `verifier-live-capture.json` — отдельный ProxyAPI smoke от 2026-10-09: один реальный батч Noul/Choice/Score на synthetic тексте. Это проверка API contract и replay, без case-level quality labels. См. [отчёт](../../../docs/PROXYAPI_LIVE_CHECK_2026-10-09.md).
