# Поддержанный counterexample к границе реформы

`source.md` описывает synthetic model D: смягчение M равно 1/2, а N ошибочно изменено с 3/4 на 2/3. Exclusion E → N сохранён. Пакет поддерживает `demo.reform-mitigation/v1` без изменения profile и без специальных branches по ID.

При M=false, N=true, E=false:

| Group | A           | D           |
| ----- | ----------- | ----------- |
| K1    | 90 месяцев  | 80 месяцев  |
| K2    | 180 месяцев | 160 месяцев |

Query A/D `preserved-outside` получает verdict `counterexample`; Lean подтверждает допустимость последствий и нарушение equality связанным witness K1. Receipt имеет proof status `verified` и full scope coverage 8/8.

Исходный `C-missing-exclusion` в [design fixture](../reform-v1/fixture.json) остаётся учебным примером, отклоняемым admission validation текущего profile. Полный отчёт и команды replay — [COMPARISON_VERIFICATION.md](../../docs/COMPARISON_VERIFICATION.md).
