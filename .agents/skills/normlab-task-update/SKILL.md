---
name: normlab-task-update
description: Update a NormLab issue status, evidence, blocker, or handoff and assess completion against acceptance criteria; does not authorize merge, deployment, or paid inference.
---

# NormLab task update

Прочитай [правила ledger](../../../AGENTS.md). Используй их status/field contract,
не копируй его в отдельный checklist со своими определениями.

1. Перечитай Issue и связанные dependencies/PR. Установи фактическое текущее
   состояние; локальная память и старая CI-сводка не подтверждают завершение.
2. Сопоставь выполненное с acceptance. Для каждого существенного результата
   укажи evidence: commit/PR/закреплённый отчёт, точную выполненную проверку и
   её исход. Различай implementation, provider compatibility, semantic quality
   и deployment. Отсутствующая проверка остаётся pending, не получает pass.
3. Обнови единственное authoritative status field: Project Status, если оно
   настроено, иначе Status в body. При `blocked` укажи внешний blocker и условие
   снятия; при `deferred` — причину и условие возвращения. Не превращай прежнее
   defer в `ready` только из-за зелёного CI или свободного исполнителя.
4. При handoff сохрани частичный результат, outstanding acceptance, owner и
   next action. При существенном изменении scope оставь датированную запись
   с причиной; не стирай исходные ограничения и отрицательные результаты.
5. Закрывай как выполненную только после выполнения всех acceptance criteria.
   Если PR лишь реализовал будущий эксперимент/деплой, задача этого эксперимента/
   деплоя остаётся открытой. Отмена — `dropped` с причиной; completed negative
   experiment может быть `done` без положительного результата гипотезы.
6. Выполни только необходимые ledger mutations в пределах поручения. Для body
   используй structured arguments/`--body-file`, сохрани чужие concurrent edits
   свежим чтением перед записью. При неизвестном исходе перечитай state до retry;
   не дублируй comments и не публикуй неизменные heartbeat updates.
7. Перечитай сохранённую запись, проверь согласованность open/closed и status.
   Сообщи Issue URL, новый статус, evidence, pending work и один следующий ход.
   При недоступном GitHub явно сообщи, что обновление не подтверждено.

Skill обновляет ledger; он не исполняет связанный merge/deploy/live experiment
и не создаёт автоматические follow-ups без отдельного поручения пользователя.
