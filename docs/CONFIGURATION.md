# Конфигурация

Все параметры передаются монитору через переменные окружения, которые systemd загружает из `EnvironmentFile`.

## Переменные окружения

| Переменная | Описание | Значение по умолчанию |
|---|---|---|
| `SOCKET` | Путь к HAProxy UNIX-socket | `/run/haproxy/haproxy.sock` |
| `INTERVAL` | Период опроса HAProxy, секунды | `5` |
| `WINDOW` | Длительность окна агрегации, секунды | `600` |
| `FLAP_THRESHOLD` | Warning: количество флапов статуса | `3` |
| `CHKFAIL_THRESHOLD` | Warning: дельта `chkfail` | `2` |
| `CHKDOWN_THRESHOLD` | Warning: дельта `chkdown` | `1` |
| `RESP5XX_THRESHOLD` | Warning: дельта `hrsp_5xx` | `5` |
| `CRITICAL_FLAP_THRESHOLD` | Critical: количество флапов | `6` |
| `CRITICAL_CHKFAIL_THRESHOLD` | Critical: дельта `chkfail` | `4` |
| `CRITICAL_CHKDOWN_THRESHOLD` | Critical: дельта `chkdown` | `2` |
| `CRITICAL_5XX_THRESHOLD` | Critical: дельта `hrsp_5xx` | `20` |
| `DURATION` | Остановиться через N секунд, `0` = работать бесконечно | `0` |
| `ALERT_COOLDOWN` | Cooldown warning алертов, сек | `300` |
| `CRITICAL_ALERT_COOLDOWN` | Cooldown critical алертов, сек | `120` |
| `ONLY_BAD` | `1` — показывать только проблемные бэкенды в консоли | `1` |
| `TELEGRAM_BOT_TOKEN` | Токен Telegram-бота | — |
| `TELEGRAM_CHAT_ID` | ID чата/канала | — |

## Рекомендации по порогам

- `WINDOW` должен быть заметно больше `INTERVAL`, чтобы накапливалась значимая статистика.
- Critical-пороги обычно устанавливают в 2-3 раза выше warning-порогов.
- Если бэкенд часто `UP/DOWN`, снижайте `FLAP_THRESHOLD`.

## Пример для высоконагруженного сервиса

```text
INTERVAL=5
WINDOW=300
FLAP_THRESHOLD=2
CRITICAL_FLAP_THRESHOLD=5
RESP5XX_THRESHOLD=10
CRITICAL_5XX_THRESHOLD=50
ALERT_COOLDOWN=600
CRITICAL_ALERT_COOLDOWN=300
```
