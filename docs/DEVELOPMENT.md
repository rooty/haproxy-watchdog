# Разработка

## Структура кода

- `bin/haproxy_backend_monitor.py` — единственный модуль с логикой.
- `Monitor` — основной класс, управляющий циклом опроса и алертами.
- `parse_stat()` — парсинг CSV от HAProxy (возвращает `{pxname/svname: Snap}`).
- `classify()` — классификация состояния (`none`/`warning`/`critical`).
- `WinCounters` — накапливаемые дельты за окно (`flaps`, `chkfail`, `chkdown`, `resp5xx`).
- `build_telegram_message()` — сборка HTML-сообщения для Telegram.
- `send_telegram()` — отправка уведомлений с cooldown.
- `print_console_report()` — консольный отчёт по истечении окна.

## Правила внесения изменений

1. Не добавляйте внешние зависимости (только stdlib).
2. Покрывайте изменения тестами в `tests/`.
3. Запускайте `PYTHONPATH=bin python -m unittest discover -s tests -p "*.py"`.
4. Не коммитьте реальные токены Telegram.

## Архитектурные особенности

- Все пороги и токены передаются через `argparse.Namespace` (объект `cfg`).
- `Monitor` хранит историю в `prev_snaps`, `win_counters` и `backend_prev_level`.
- Cooldown реализован через `last_alert_time[level]`: метка ставится при отправке,
  первый алерт уровня всегда разрешён (пока метки нет).

## Отладка

Запуск в консоли:

```bash
python3 bin/haproxy_backend_monitor.py --socket /run/haproxy/haproxy.sock --window 60 --interval 5
```
