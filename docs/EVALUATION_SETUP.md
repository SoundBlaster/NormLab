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
4. Проверить предложения. Для пропуска выделить текст источника и добавить утверждение; выбрать predicate, polarity, subject и episode.
5. Сохранить изменения отдельной ревизией; затем подтвердить или отклонить каждое утверждение. Для отклонения нужна причина.
6. Выполнить checklist полноты и завершить review. Можно скачать сохранённую ревизию и открыть историю.

Изменение фабулы требует явного создания нового черновика. Предыдущая цепочка сохраняется, подтверждения не переносятся. Исходные ответы модели доступны в details и не заменяются ручной правкой. Статус «проверено человеком» не означает юридическую истинность. КоАП disposition, полный ontology graph и Lean calculation в этом экране ещё отсутствуют.

## Pipeline

`evaluation/two_stage.py`: LangExtract выделяет дословные assertions с участником, эпизодом и speaker; независимый exact search допускает только уникальные цитаты. Второй model call классифицирует эти fragments по определениям 15 predicates, возвращая fragment IDs, stance и valueText. Цитату, subject и episode второй этап не меняет. Неоднозначные или неверные привязки уходят в quarantine, не в доверенные proposals.

Разделение не гарантирует полноту или правильную polarity. Speaker сохраняется в raw evidence; UI пока не предоставляет отдельный редактор speaker. Сохраняются prompts, schemas, intermediate fragments, raw responses, versions и source digest. Фабула считается данными; инструкции внутри неё не являются разрешением на действия. У моделей нет tools.

## Воспроизводимый прогон

Использовать **новый** каталог для каждого запуска, старые artifacts не перезаписываются:

```sh
.tools/parking-evaluation/bin/python evaluation/run_langextract.py experiments/parking-baseline/my-two-stage --two-stage
npm exec tsx -- scripts/parking-evaluate.ts experiments/parking-evaluation/my-comparison experiments/parking-baseline/2026-10-05-langextract-exact-reanchored experiments/parking-baseline/my-two-stage
```

Первый runner делает реальные model calls; второй только replay/scoring. SHA256 manifests проверяют целостность, не являются подписью. Expectations — candidate, не expert-approved. Цель: 80% кейсов без критических ошибок **до** ручного исправления. Четыре учебных кейса не достаточны для release claim. Full graph gate и flat statement gate имеют разные scopes.

## MLflow

```sh
NORMLAB_MLFLOW_IMPORT=1 npm exec tsx -- scripts/parking-evaluate.ts experiments/parking-evaluation/my-mlflow experiments/parking-baseline/my-two-stage
.tools/parking-evaluation/bin/mlflow server --host 127.0.0.1 --port 5050 --backend-store-uri sqlite:///$PWD/.data/mlflow/tracking.sqlite --default-artifact-root "$PWD/.data/mlflow/artifacts"
```

Открыть `http://127.0.0.1:5050`, experiment «NormLab parking extraction». Импорт использует local SQLite и native code-based scorers, без LLM judge. MLflow может хранить полные фабулы: использовать synthetic/обезличенные данные. `.data` и `.tools` не коммитятся. Evidently отложен до появления пользовательского потока.

## Следующий этап

Независимая semantic review результатов, отдельный holdout, исправление основных классов ошибок; только затем подключение confirmed statements к ontology graph и правовому расчёту.
