# haproxy-watchdog

[![CI](https://github.com/rooty/haproxy-watchdog/actions/workflows/ci.yml/badge.svg)](https://github.com/rooty/haproxy-watchdog/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Монитор стабильности бэкендов HAProxy с алертами в Telegram.

Скрипт на чистом Python 3 (только стандартная библиотека) подключается к UNIX-сокету HAProxy, собирает статистику по серверам бэкендов, вычисляет дельты внутри скользящего окна и отправляет уведомления при переходе состояния в `warning` или `critical`, а также при восстановлении.

---

## Содержание

- [Возможности](#возможности)
- [Архитектура](#архитектура)
- [Требования](#требования)
- [Установка](#установка)
- [Настройка](#настройка)
- [Запуск и systemd](#запуск-и-systemd)
- [Telegram](#telegram)
- [Принцип работы алертов](#принцип-работы-алертов)
- [Пороги и классификация](#пороги-и-классификация)
- [Тестирование](#тестирование)
- [Разработка](#разработка)
- [Лицензия](#лицензия)

---

## Возможности

- Подключение к HAProxy через UNIX-сокет (`show stat`).
- Поддержка только Python 3 стандартной библиотеки.
- Сбор статистики по статусам, `chkfail`, `chkdown`, `hrsp_5xx`.
- Скользящее окно агрегации с настраиваемым интервалом и размером.
- Классификация состояний: `none`, `warning`, `critical`.
- Отправка алертов в Telegram с HTML-форматированием.
- Cooldown между алертами (отдельно для warning и critical).
- Консольный отчёт по истечении окна.
- Готовые unit-файлы systemd.
- Поддержка logrotate.
- Unit-тесты на `unittest`.

---

## Архитектура

```text
haproxy-watchdog/
├── bin/haproxy_backend_monitor.py      # Основной монитор
├── etc/
│   ├── haproxy-backend-monitor.env     # Переменные окружения
│   ├── haproxy-backend-monitor.service # systemd unit (journald)
│   ├── haproxy-backend-monitor-filelog.service # systemd unit (файл)
│   └── haproxy-backend-monitor.logrotate
├── tests/
│   ├── test_parser.py                  # Тесты парсера CLI
│   └── test_monitor.py                 # Тесты cooldown-логики
└── docs/                               # Подробная документация
```

---

## Требования

- Python 3.8+
- HAProxy с настроенным UNIX-сокетом (`stats socket`)
- Доступ к сокету для пользователя, под которым запускается сервис
- Для Telegram: бот-токен и `chat_id`

---

## Установка

1. Клонировать репозиторий:

```bash
sudo git clone <repo> /opt/haproxy-watchdog
```

2. Скопировать переменные окружения:

```bash
sudo cp /opt/haproxy-watchdog/etc/haproxy-backend-monitor.env /etc/default/haproxy-backend-monitor
sudo chmod 600 /etc/default/haproxy-backend-monitor
```

3. Отредактировать `/etc/default/haproxy-backend-monitor` (сокет, пороги, токен Telegram).

4. Скопировать unit-файл:

```bash
sudo cp /opt/haproxy-watchdog/etc/haproxy-backend-monitor.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now haproxy-backend-monitor
```

Подробнее в [docs/INSTALL.md](docs/INSTALL.md).

---

## Настройка

Основные параметры задаются в `etc/haproxy-backend-monitor.env`:

| Переменная | Описание | По умолчанию |
|---|---|---|
| `SOCKET` | Путь к HAProxy UNIX-socket | `/run/haproxy/haproxy.sock` |
| `INTERVAL` | Период опроса, сек | `5` |
| `WINDOW` | Размер окна агрегации, сек | `600` |
| `FLAP_THRESHOLD` | Порог флапов для warning | `3` |
| `CHKFAIL_THRESHOLD` | Порог `chkfail` для warning | `2` |
| `CHKDOWN_THRESHOLD` | Порог `chkdown` для warning | `1` |
| `RESP5XX_THRESHOLD` | Порог `hrsp_5xx` для warning | `5` |
| `CRITICAL_FLAP_THRESHOLD` | Порог флапов для critical | `6` |
| `CRITICAL_CHKFAIL_THRESHOLD` | Порог `chkfail` для critical | `4` |
| `CRITICAL_CHKDOWN_THRESHOLD` | Порог `chkdown` для critical | `2` |
| `CRITICAL_5XX_THRESHOLD` | Порог `hrsp_5xx` для critical | `20` |
| `ALERT_COOLDOWN` | Cooldown warning, сек | `300` |
| `CRITICAL_ALERT_COOLDOWN` | Cooldown critical, сек | `120` |
| `ONLY_BAD` | Печатать только проблемные строки | `1` |
| `TELEGRAM_BOT_TOKEN` | Токен бота Telegram | `-` |
| `TELEGRAM_CHAT_ID` | ID чата/канала | `-` |

Подробнее в [docs/CONFIGURATION.md](docs/CONFIGURATION.md).

---

## Запуск и systemd

Ручной запуск:

```bash
python3 bin/haproxy_backend_monitor.py \
  --socket /run/haproxy/haproxy.sock \
  --window 600 --interval 5
```

Управление сервисом:

```bash
sudo systemctl start haproxy-backend-monitor
sudo systemctl status haproxy-backend-monitor
sudo journalctl -u haproxy-backend-monitor -f
```

Для логирования в файл используйте `haproxy-backend-monitor-filelog.service`.

Подробнее в [docs/SYSTEMD.md](docs/SYSTEMD.md).

---

## Telegram

Для настройки уведомлений:

1. Создайте бота через [@BotFather](https://t.me/BotFather) и получите токен.
2. Определите `chat_id` (личный или групповой чат/канал).
3. Запишите значения в `/etc/default/haproxy-backend-monitor`.
4. Перезапустите сервис.

Подробнее в [docs/TELEGRAM.md](docs/TELEGRAM.md).

---

## Принцип работы алертов

- На каждом интервале монитор читает `show stat`.
- На основе дельт между текущим и предыдущим замером заполняются счётчики окна (`WinCounters`).
- По истечении окна каждый бэкенд классифицируется:
  - `critical` — если статус `DOWN`/`NOLB`/`MAINT` либо превышены критические пороги.
  - `warning` — превышены обычные пороги.
  - `none` — состояние нормальное.
- Если состояние изменилось по сравнению с предыдущим окном, отправляется Telegram-уведомление.
- Cooldown предотвращает спам: повторный alert того же уровня не отправится раньше `ALERT_COOLDOWN`/`CRITICAL_ALERT_COOLDOWN` секунд.
- Если бэкенд исчез из статистики, он считается восстановленным (`recovered`).

---

## Пороги и классификация

| Метрика | Warning | Critical |
|---|---|---|
| Флапы статуса | `>= FLAP_THRESHOLD` | `>= CRITICAL_FLAP_THRESHOLD` |
| `chkfail` | `>= CHKFAIL_THRESHOLD` | `>= CRITICAL_CHKFAIL_THRESHOLD` |
| `chkdown` | `>= CHKDOWN_THRESHOLD` | `>= CRITICAL_CHKDOWN_THRESHOLD` |
| `hrsp_5xx` | `>= RESP5XX_THRESHOLD` | `>= CRITICAL_5XX_THRESHOLD` |
| Статус сервера | — | `DOWN`, `NOLB`, `MAINT` |

Если одновременно выполняются условия warning и critical, выбирается `critical`.

---

## Тестирование

```bash
PYTHONPATH=bin python -m unittest discover -s tests -p "*.py"
```

Подробнее в [docs/TESTING.md](docs/TESTING.md).

---

## Разработка

- Все изменения конфигурации и логики должны покрываться unit-тестами.
- Перед коммитом убедитесь, что тесты проходят.
- Не храните настоящие токены Telegram в репозитории.

Подробнее в [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

---

## Лицензия

Проект распространяется под лицензией [MIT](LICENSE).
