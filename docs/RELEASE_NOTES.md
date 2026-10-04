# NormLab 0.1.0 — release notes (draft)

**Status:** подготовлен черновик для версии `0.1.0`; GitHub Release не опубликован.

NormLab 0.1.0 — локальная исследовательская лаборатория для сравнения трёх синтетических моделей реформы A/B/C. Срез предназначен для воспроизводимого обсуждения правил и последствий, а не для обработки реальных дел или автоматического толкования действующего права.

## Возможности

- Laboratory UI сравнивает модели A/B/C на одном snapshot, показывает мотивированные findings M/N/E, источник правила, полный rule ledger и составные последствия.
- История findings и analyses сохраняется в SQLite. Изменение snapshot создаёт новую ревизию; сохранённые результаты можно повторно открыть с fresh replay.
- Независимая Lean-проверка и подписанные Ed25519 receipts подтверждают ограниченные statements для зафиксированных моделей и объявленного конечного scope.
- Эксперименты можно экспортировать и передать как подписанный набор. Read-only import требует явно выбранного trusted public key и fresh replay до сохранения.
- Объяснения и метрики разделяют структуру, решения и изменения последствий; метрики показывают scope и coverage и не сводятся к общему «индексу гуманности».
- Docker Compose запускает локальный UI и API, сохраняет базу и ключи в named volume, а [runbook](DEPLOYMENT.md) описывает остановку, backup и восстановление.
- CI выполняет formatter, type-aware lint, TypeScript checks, unit/API и Lean integration tests, schema freshness и production build.

## Быстрый запуск

Требуется Docker Desktop или Docker Engine с Compose plugin:

```sh
docker compose up --build -d
```

Откройте <http://127.0.0.1:4317>. Первый запуск скачивает pinned Lean toolchain и может занять несколько минут. Команда `docker compose down` сохраняет named volume; `docker compose down -v` удаляет базу и локальные signing keys. Подробности — в [руководстве развёртывания](DEPLOYMENT.md).

Для запуска без контейнера требуются Node.js `22.18+` и Lean `4.30.0`; команды приведены в [README](../README.md).

## Границы этой версии

- Поддержан один reviewed synthetic legal profile и конечный demonstrator domain. Формальная проверка относится к locked inputs, проверяемому statement и объявленному scope; она не устанавливает истинность обстоятельств, полноту реального права или юридическую корректность перевода нормы.
- Не вводите реальные дела, персональные данные или конфиденциальные материалы. Compose-конфигурация рассчитана на одного локального исследователя и loopback-доступ; это не multi-user или internet-facing production service.
- В этой версии нет AI extraction, импорта произвольных нормативных пакетов, Hypercode-to-Legal-IR compiler, PostgreSQL, multi-tenant authorization, production sandbox или публичного publication flow.
- Подписанный receipt подтверждает целостность и происхождение artifact относительно доверенного ключа; сама подпись не доказывает правильность модели или входных данных.
- Тест migration engine использует synthetic v1/v2/v3 schemas, проверяет сохранение данных, atomic rollback, retry и повторный запуск. При добавлении реальной следующей версии SQLite-схемы нужен отдельный migration-specific regression и инструкция upgrade/rollback.
- Hosted CI проходит, но текущий план GitHub для этого private repository не позволяет включить branch protection или repository rulesets. Поэтому CI пока не является серверным merge gate.

Для будущего опубликованного release эти заметки следует сверить с точным git tag и набором проверок на этом tag.
