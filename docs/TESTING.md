# Тестирование

## Запуск тестов

```bash
PYTHONPATH=bin python -m unittest discover -s tests -p "*.py"
```

Ожидаемый результат:

```text
Ran 6 tests in 0.006s
OK
```

## Структура тестов

- `tests/test_parser.py` — проверка аргументов CLI и значений cooldown по умолчанию.
- `tests/test_monitor.py` — проверка cooldown-логики Telegram-алертов.

## Добавление новых тестов

При добавлении функциональности создавайте или обновляйте файлы в `tests/`. Используйте `unittest` и `unittest.mock`.

## Ручная проверка классификации

```python
from haproxy_backend_monitor import classify, Snap, WinCounters
import argparse

cfg = argparse.Namespace(
    flap_threshold=3, chkfail_threshold=2, chkdown_threshold=1, resp5xx_threshold=5,
    critical_flap_threshold=6, critical_chkfail_threshold=4,
    critical_chkdown_threshold=2, critical_5xx_threshold=20,
)
print(classify(Snap(status='UP'), WinCounters(flaps=1), cfg))   # none
print(classify(Snap(status='UP'), WinCounters(flaps=5), cfg))   # warning
print(classify(Snap(status='DOWN'), WinCounters(), cfg))        # critical
```
