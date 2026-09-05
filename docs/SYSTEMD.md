# Запуск через systemd

Проект содержит два unit-файла.

## haproxy-backend-monitor.service

Логи отправляются в journald.

```ini
[Unit]
Description=HAProxy Backend Stability Monitor
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=/opt/haproxy-watchdog
EnvironmentFile=/opt/haproxy-watchdog/etc/haproxy-backend-monitor.env
ExecStart=/usr/bin/env python3 /opt/haproxy-watchdog/bin/haproxy_backend_monitor.py ...
Restart=always
RestartSec=5
NoNewPrivileges=true
StandardOutput=journal
StandardError=journal
SyslogIdentifier=haproxy-backend-monitor

[Install]
WantedBy=multi-user.target
```

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
