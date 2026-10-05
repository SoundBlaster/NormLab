# Локальное извлечение и evaluation

## Установка

Из корня NormLab, с установленными `uv`, Python 3.10+ и npm dependencies:

```sh
uv venv --python python3.10 .tools/parking-evaluation
uv pip install --python .tools/parking-evaluation/bin/python --require-hashes -r evaluation/requirements.lock
npm run dev
```

В LM Studio загрузить `openai/gpt-oss-20b` и запустить OpenAI-compatible server на `http://127.0.0.1:1234/v1`. Извлечение использует фиксированный loopback endpoint, dummy key, temperature 0, seed 42, без SDK retries. Оно работает на host; Python environment не включён в Compose image. Ручной review не требует модели.

## Пользовательский путь

1. Открыть NormLab, вкладку «Парковка · Разбор текста».
2. Выбрать учебную фабулу и создать черновик.
3. Нажать «Выделить и классифицировать утверждения».
4. Проверить предложения. Для пропуска выделить текст источника и добавить утверждение; выбрать predicate, polarity, subject, speaker и episode. Для нового утверждения vehicle_1 — редактируемый начальный идентификатор, а не установленный участник.
5. Сохранить изменения отдельной ревизией; затем подтвердить или отклонить каждое утверждение. Для отклонения нужна причина.
6. Выполнить checklist полноты и завершить review. Можно скачать сохранённую ревизию и открыть историю.

Изменение фабулы требует явного создания нового черновика. Предыдущая цепочка сохраняется, подтверждения не переносятся. Исходные ответы модели доступны в details и не заменяются ручной правкой. Статус «проверено человеком» не означает юридическую истинность. КоАП disposition, полный ontology graph и Lean calculation в этом экране ещё отсутствуют.

## Pipeline

HTTP/UI использует `evaluation/two_stage_v3.py`: direct discovery v2 выделяет дословные assertions с участником, эпизодом и speaker; независимый exact search допускает только уникальные цитаты. Classification v3 требует решения для каждого fragmentId: classifications либо explicit no-supported-predicate с причиной. Цитату, subject, speaker и episode второй этап не меняет. Неоднозначные или неверные привязки уходят в quarantine. Сервер принимает только v3 и неподтверждённые предложения модели. Отказ контракта сохраняет прежнюю ревизию; ручная разметка остаётся доступной.

Разделение не гарантирует полноту, правильную polarity или attribution. Speaker доступен для ручного редактирования. Сохраняются prompts, schemas, intermediate fragments, raw responses, versions и source digest. Фабула считается данными; инструкции внутри неё не являются разрешением на действия. У моделей нет tools.

## Воспроизводимый прогон

Использовать **новый** каталог для каждого запуска, старые artifacts не перезаписываются. Команды ниже воспроизводят исторический LangExtract v1 baseline, а не текущий UI v3; controlled comparison и fresh v3 запуск описаны в [отчёте v3](CLASSIFICATION_V3_2026-10-05.md):

```sh
.tools/parking-evaluation/bin/python evaluation/run_langextract.py experiments/parking-baseline/my-two-stage --two-stage
npm exec tsx -- scripts/parking-evaluate.ts experiments/parking-evaluation/my-comparison experiments/parking-baseline/2026-10-05-langextract-exact-reanchored experiments/parking-baseline/my-two-stage
```

Первый runner делает реальные model calls; второй только replay/scoring. SHA256 manifests проверяют целостность, не являются подписью. Expectations — candidate, не expert-approved. Цель демо: 50% кейсов без критических ошибок **до** ручного исправления; 80% — дальнейшая цель. Четыре учебных кейса и selected probes не достаточны для заявления о достижении этой метрики. Full graph gate и flat statement gate имеют разные scopes.

## MLflow

```sh
NORMLAB_MLFLOW_IMPORT=1 npm exec tsx -- scripts/parking-evaluate.ts experiments/parking-evaluation/my-mlflow experiments/parking-baseline/my-two-stage
.tools/parking-evaluation/bin/mlflow server --host 127.0.0.1 --port 5050 --backend-store-uri sqlite:///$PWD/.data/mlflow/tracking.sqlite --default-artifact-root "$PWD/.data/mlflow/artifacts"
```

Открыть `http://127.0.0.1:5050`, experiment «NormLab parking extraction». Импорт использует local SQLite и native code-based scorers, без LLM judge. MLflow может хранить полные фабулы: использовать synthetic/обезличенные данные. `.data` и `.tools` не коммитятся. Evidently отложен до появления пользовательского потока.

## Следующий этап

Независимая semantic review результатов, отдельный holdout, исправление основных классов ошибок; только затем подключение confirmed statements к ontology graph и правовому расчёту.
