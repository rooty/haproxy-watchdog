# Установка haproxy-watchdog

## 1. Требования

- Python 3.8+
- HAProxy с настроенным UNIX-сокетом статистики, например:

```haproxy
global
    stats socket /run/haproxy/haproxy.sock mode 660 level admin
```

- Пользователь, под которым будет запущен сервис, должен иметь доступ к сокету.

## 2. Размещение файлов

Рекомендуемый путь:

```bash
sudo git clone <repo> /opt/haproxy-watchdog
sudo chown -R root:root /opt/haproxy-watchdog
```

## 3. Переменные окружения

Скопируйте шаблон:

```bash
sudo cp /opt/haproxy-watchdog/etc/haproxy-backend-monitor.env /etc/default/haproxy-backend-monitor
sudo chmod 600 /etc/default/haproxy-backend-monitor
```

Отредактируйте `/etc/default/haproxy-backend-monitor`:

```bash
sudo nano /etc/default/haproxy-backend-monitor
```

Минимально обязательно при использовании Telegram:

```text
TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234...
TELEGRAM_CHAT_ID=-1001234567890
```

## 4. systemd unit

```bash
sudo cp /opt/haproxy-watchdog/etc/haproxy-backend-monitor.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable haproxy-backend-monitor.service
sudo systemctl start haproxy-backend-monitor.service
```

Проверка:

```bash
sudo systemctl status haproxy-backend-monitor
sudo journalctl -u haproxy-backend-monitor -f
```

## 5. logrotate (опционально)

```bash
sudo cp /opt/haproxy-watchdog/etc/haproxy-backend-monitor.logrotate /etc/logrotate.d/haproxy-backend-monitor
sudo chmod 644 /etc/logrotate.d/haproxy-backend-monitor
```

## 6. Обновление

```bash
cd /opt/haproxy-watchdog
sudo git pull
sudo systemctl restart haproxy-backend-monitor
```
