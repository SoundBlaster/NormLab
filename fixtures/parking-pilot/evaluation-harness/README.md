# Neutral offline replay fixtures

Один synthetic source, одна contrast family, три записи: два completed classification candidates и один смоделированный transport failure. Нейтральные IDs не сообщают качество candidate. Source/parent взяты из существующих Mellea control-flow fixtures.

`experiment.json` содержит только captures и исходные данные. `reviewer-labels.json` содержит candidate payment expectations и отдельно передаётся scorer. Manifest/dataset binding — SHA-256 bytes, labels привязаны к hash manifest. Actual definitions сохранены для воспроизводимого replay, не для нормативной актуальности.

Ни один capture не получен от живой модели. Включение defective candidate и failure предназначено для диагностики scorer/denominators, а не для оценки model quality. Human labels не экспертные; complete case-level review не проведён.

Команды и контракт: [HARNESS.md](../../../evaluation/HARNESS.md).
