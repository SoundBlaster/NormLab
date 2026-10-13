---
name: normlab-task-intake
description: Find, deduplicate, scope, or split NormLab ledger tasks in GitHub Issues before authorized work; use for backlog intake, not for executing experiments or merging PRs.
---

# NormLab task intake

Прочитай [правила ledger](../../../AGENTS.md): это единственный источник полей,
статусов и критериев. Skill применим к NormLab и связанным задачам Platform/адаптеров.

1. Определи repo из remote; выясни существующий Project, если он настроен.
   Через доступный GitHub connector или `gh issue list --state all` найди
   связанные задачи по результату, а не только по словам в заголовке. Прочитай
   найденные Issues и ссылки; отсутствие совпадения в одной странице не доказывает,
   что задачи нет — используй search/pagination по необходимости.
2. Переиспользуй подходящую открытую Issue. Для closed/deferred сначала выясни
   причину и действующее поручение; не возобновляй работу автоматически. При дубле
   свяжи записи и сохрани историю; не удаляй результат прежней работы.
3. Для новой задачи задай минимальные поля из AGENTS.md. Acceptance описывает
   наблюдаемый результат, а next action — ближайшее действие. Не превращай
   исследовательскую гипотезу в обещание улучшения accuracy.
4. Делить задачу стоит, если результаты можно независимо проверить/завершить или
   у них разные blockers. Свяжи parent/sub-issues и dependency URLs; не делай PR
   автоматически отдельной задачей. Для cross-repo работы выбери основной repo
   и свяжи независимо проверяемые результаты других repos.
5. Создание/изменение Issues выполняй только в рамках порученного task-management
   scope; эта инструкция не авторизует массовую миграцию backlog или настройку
   Project. Для multiline body используй structured tool argument или временный
   файл с `gh ... --body-file`. Не интерполируй свободный текст в shell code.
6. Перед повтором неясно завершившегося create проверь, не появилась ли Issue.
   После успешной записи перечитай её и сообщи canonical URL, status, dependencies
   и next action. При ошибке доступа сохрани handoff и укажи несинхронизированный
   результат; не создавай второй canonical ledger.

Выход: одна конкретная запись или связанный набор без дублей, с проверяемыми
критериями. Этот skill не запускает inference и не меняет код приложения.
