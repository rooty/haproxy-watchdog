# Настройка Telegram-уведомлений

## 1. Создание бота

1. Откройте [@BotFather](https://t.me/BotFather).
2. Отправьте `/newbot`.
3. Запишите полученный токен.

## 2. Определение chat_id

### Личные сообщения

Отправьте боту любое сообщение, затем откройте:

```bash
curl -s https://api.telegram.org/bot<TOKEN>/getUpdates | grep -o '"chat":{[^}]*}'
```

### Группа или канал

Добавьте бота в группу/канал и отправьте сообщение. `chat_id` будет отрицательным для групп и каналов.

## 3. Проверка отправки

```bash
curl -s -X POST https://api.telegram.org/bot<TOKEN>/sendMessage \
  -d chat_id=<CHAT_ID> \
  -d text="Test from haproxy-watchdog"
```

## 4. Интеграция с монитором

Отредактируйте `/etc/default/haproxy-backend-monitor`:

```text
TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234...
TELEGRAM_CHAT_ID=-1001234567890
```

Перезапустите сервис:

```bash
sudo systemctl restart haproxy-backend-monitor
```

## Безопасность

- Храните токен в `EnvironmentFile`, не в репозитории.
- Дайте файлу права `0600`.
- Не логируйте токен в открытом виде.
