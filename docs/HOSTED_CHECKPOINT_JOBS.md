# Hosted recovery: задания, checkpoints и «Продолжить»

Дата: 2026-10-21. Ledger: [#179](https://github.com/SoundBlaster/NormLab/issues/179).
Зависимость: [single-stage gateway RPC](HOSTED_STAGE_PROTOCOL.md), PR #181.
Это реализация в исходниках; deployment и реальные provider calls здесь не заявлены.

## Путь пользователя

1. Сохранить фабулу и подтвердить парковочный контекст. «Запустить авторазбор с
   начала» создаёт задание и быстро возвращает управление; вкладку можно закрыть.
2. После discovery доступны точные цитаты. После каждого batch появляются
   предложения `model/pending`, отдельно от проверки человеком. Пока не завершены
   все batch, UI явно пишет «Частичный разбор»; отсутствие предложения не является
   отрицанием обстоятельства. Завершение этапов также не является решением по КоАП.
3. При отказе сохраняются этап, безопасная причина и история. Исправить доступ или
   баланс и нажать «Продолжить с сохранённых этапов»: inference повторяется только
   для недостающего этапа. Нет автоматического retry или смены провайдера.
4. Если исход попытки неизвестен, отдельно подтвердить возможную повторную оплату.
   Старая попытка остаётся `unknown`, даже после успешного продолжения; журнал
   сохраняет предупреждение. Подтверждение не устанавливает, были ли списаны деньги.
5. Если появились ручные правки, задание сохраняет полученный checkpoint и
   останавливается с конфликтом. Открыть актуальную ревизию и явно разрешить её
   замену предложениями задания. Прежняя ручная ревизия остаётся в истории.
   Автоматического объединения правок нет. Локальные несохранённые правки в форме
   не заменяются polling-ответом; для их отбрасывания требуется отдельная галка.

Новые задания не возобновляют старые автоматически. Изменение фабулы создаёт
отдельный черновик по прежнему UX. Локальный Python/legacy extractor сохраняет
прежний полный запуск: staged UI включается только при наличии gateway transport.

## API и владение

| Route                               | Назначение                                                                                                                                                           |
| ----------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `POST /api/parking/jobs`            | `draftId`, `expectedRevisionId`; необязательные `jobId` для Continue, `replaceStatements` и `acknowledgeUnknown`. Возвращает состояние задания, не ожидая inference. |
| `GET /api/parking/job/:draftId`     | Выбранное последнее задание или `null`, плюс актуальная сохранённая ревизия. Не запускает inference.                                                                 |
| `GET /api/parking/journal/:draftId` | Общий журнал ревизий, прежних запусков и новых заданий; последние 100 событий с полным количеством.                                                                  |

Все маршруты используют существующую authentication/CSRF boundary приложения.
Публичный статус содержит прогресс, цитаты, настроенные модели и safe failure;
raw provider evidence и attempt log остаются в приватном storage. Журнал сохранённых заданий читается и после отключения
inference transport в конфигурации; новые запросы в этом режиме запрещены.

Один процесс приложения владеет одним активным авторазбором; legacy extraction
разделяет этот guard. Это ограничение не distributed lock: несколько replicas
или независимых процессов с одним dataDir не поддерживаются. Сначала нужен один
app owner. Нет отдельного сервиса, очереди, библиотеки или изменений evaluation.

## Сохранение и crash policy

В существующем dataDir:

```text
parking-review/<draftId>/jobs/
  current.json                 # atomically replaced pointer to selected job
  <jobId>/job.json              # profile, revision, attempts, refs, journal events
  <jobId>/<checkpointId>.json   # immutable private stage response/evidence
```

Каталоги создаются 0700, файлы 0600. Attempt reservation сохраняется **до**
запроса. Ответ проверяется, записывается отдельным файлом, затем его SHA-256 и
reference атомарной заменой включаются в job.json. Только после этого публикуется
ревизия и отправляется следующий batch. Hash покрывает JSON bytes, включая
floating-point evidence. При чтении проверяются hash, схема, source/config/input
binding, порядок этапов, цитаты, pending/model и суммарный предел 256 утверждений.

Это atomic rename отдельных файлов, **не** транзакция между checkpoint, job и
ревизией и **не** fsync-гарантия при отключении питания:

- Незаконченный `running` после перезапуска становится paused; reservations без
  подтверждённого outcome становятся unknown. GET не возобновляет их.
- Orphan checkpoint без committed reference не принимается автоматически.
  Перед повтором reserved/unknown пользователь подтверждает возможную оплату.
- Commit checkpoint до публикации позволяет продолжить без повторного inference.
  Crash после сохранения ревизии до обновления job pointer может дать консервативный
  revision conflict; явное разрешение замены использует те же checkpoints.
- Повреждённый/пропавший checkpoint блокирует reuse с причиной storage. Нет
  молчаливого пересчёта. Исправление данных — operator action вне этой UI.
- Изменение модели/endpoint/prompt/schema/settings даёт configuration mismatch:
  требуется явный новый запуск. Ротация ключа не меняет binding. Смена модели за
  неизменным provider alias не обнаруживается; returned model сохранена в evidence.
- Revision может измениться при ручной работе; reuse допускается для **того же
  source digest** только после явного разрешения замены. Это не reuse юридически
  подтверждённых фактов: все опубликованные предложения снова pending.

Background означает независимость от browser HTTP connection при живом процессе.
Перезапуск сервера сам по себе не возобновляет задание. Удаление dataDir, потеря
неперсистентного deployment volume или restore старого backup теряет соответствующую
историю; для сохранности нужен существующий persistent volume/backup.

## Ограничения

- Один явный Start/Continue: 300 секунд сетевого runtime budget, profile timeout
  10 секунд; внутренние provider/gateway deadlines сохраняются из stage protocol.
- Максимум 3 отправки одного этапа, 99 provider attempts одного задания; unknown
  и failed входят в счётчик. Продолжение не обнуляет их. Продолжение блокируется
  после 450 journal events, с запасом для завершения оставшихся этапов; бесконечного loop нет.
- Gateway считает каждый dispatched stage в общей hourly quota; профиль бесплатен.
  При default 6 больший разбор может потребовать ожидания следующего окна.
- Эти ограничения **не** денежный лимит и не авторитетная сверка биллинга. Денежные
  caps задаются у провайдера; unknown мог быть оплачен. Usage и raw response доступны
  в приватном evidence успешных этапов; usage ошибок/unknown не выдумывается.
- Нет автоматического fallback, model repair, orphan adoption, multi-owner locking,
  фонового автопродолжения после restart или сложного merge engine.

## Реализованная последовательность

```mermaid
sequenceDiagram
    autonumber
    actor U as Пользователь
    participant UI as Browser UI
    participant A as NormLab app / job owner
    participant S as Private dataDir
    participant G as Existing gateway
    participant P as Configured API
    U->>UI: Start / Continue (explicit permissions)
    UI->>A: POST jobs with expected revision
    A->>S: Save job and selected-job pointer
    A-->>UI: Running, without waiting for inference
    Note over UI,A: Browser can disconnect; app owns background promise
    A->>G: Profile, check configuration binding
    loop Discovery then sequential classification batches
        A->>S: Verify committed checkpoint
        alt Valid checkpoint exists
            S-->>A: Reuse, no provider request
        else Missing stage
            A->>S: Save attempt reservation
            A->>G: One bound stage RPC
            G->>P: One request, no retry
            alt Valid complete stage response
                P-->>G: Response
                G-->>A: Bound stage + private evidence
                A->>S: Checkpoint file then committed reference
            else Access / quota / timeout / invalid response
                G-->>A: Safe failure or unknown
                A->>S: Pause, preserve attempts and checkpoints
                Note over U,S: Continue by button; unknown needs payment acknowledgement
            end
        end
        break No committed result for the required stage
            A-->>UI: Paused, saved checkpoints and safe reason
        end
        alt Human revision still matches
            A->>S: Publish partial pending proposals, update job revision
            UI->>A: Poll saved state (when tab is open)
            A-->>UI: Progress and saved draft
        else Human edited the revision
            A->>S: Conflict; checkpoint retained, edits preserved
            Note over U,S: Explicit replacement required before Continue
        end
        break Human revision conflict
            A-->>UI: Explicit replacement required; dependent dispatch stops
        end
    end
    A->>S: Mark stages completed
    A-->>UI: Still requires human review, no legal verdict
```

## Verification evidence

Focused fake-provider tests: quota failure and reuse of only missing batch,
stable statement IDs across continuation, unknown acknowledgement/history,
checkpoint binding/tampering, manual-edit conflict with explicit replacement,
crashed reservation/restart without redispatch, attempt caps, invalid/confirmed
model statements, shared legacy lock and actual HTTP start/disconnect/background
completion. No real provider calls.

Bounded browser audit (15 calls, 2 inspected screenshots): synthetic 402 pause,
expanded literal fragments, Continue 1/2 → 2/2 batches and 8 → 10 statements.
Desktop viewport 1403/panel 1023 px, mobile 390/panel 320 px: 0 overflowing panel
descendants. Browser reload navigation succeeded, but opening parking after reload
hit a stale automation ref and reattachment was **not** verified in browser within
the call cap. Restart persistence/reuse is API-test evidence. First console excerpt
contained only React DevTools info; full console/AX audit not performed. Task-owned
synthetic preview stopped. No paid inference or deployment.

Local checks: полный `npm test` — 112 pass; typecheck, Oxlint/Steiger, format,
production build (output на TB5) и relative documentation links — pass. Dependency
install не выполнялся. Отдельные CI/review результаты фиксируются в ledger/PR.
