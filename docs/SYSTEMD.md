# Запуск через systemd

Проект содержит два unit-файла.

## haproxy-backend-monitor.service

Логи отправляются в journald.

Unit-файл передаёт скрипту все параметры из `etc/haproxy-backend-monitor.env`, включая необязательный `DURATION` (если задан — монитор остановится через N секунд).

Актуальное содержимое unit-файлов смотрите в репозитории:

- `etc/haproxy-backend-monitor.service`
- `etc/haproxy-backend-monitor-filelog.service`

## haproxy-backend-monitor-filelog.service

Логи дополнительно дублируются в `/var/log/haproxy-backend-monitor.log` через `tee`.

## Команды управления

```bash
sudo systemctl start haproxy-backend-monitor
sudo systemctl stop haproxy-backend-monitor
sudo systemctl restart haproxy-backend-monitor
sudo systemctl status haproxy-backend-monitor
sudo journalctl -u haproxy-backend-monitor -f
```

## Диагностика

Если сервис не запускается:

```bash
sudo journalctl -u haproxy-backend-monitor --no-pager -n 50
```

Типичные причины:

- HAProxy-socket недоступен по указанному пути.
- Неверный `TELEGRAM_BOT_TOKEN` или `TELEGRAM_CHAT_ID`.
- Некорректные значения в `.env` (например, пустые строки для cooldown).
