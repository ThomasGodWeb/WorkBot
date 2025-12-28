# Инструкция по развертыванию

## Быстрый старт

1. **Клонируйте репозиторий:**
```bash
git clone <repository-url>
cd "BOT WORKS"
```

2. **Установите зависимости:**
```bash
pip install -r requirements.txt
```

3. **Настройте переменные окружения:**
```bash
cp .env.example .env
```

Затем отредактируйте `.env` файл и укажите:
- `BOT_TOKEN` - токен от @BotFather
- `ADMIN_IDS` - ваш Telegram ID (узнайте у @userinfobot)

4. **Запустите бота:**
```bash
python main.py
```

## Развертывание на сервере

### Использование systemd (Linux)

Создайте файл `/etc/systemd/system/telegram-bot.service`:

```ini
[Unit]
Description=Telegram Bot Service
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/BOT WORKS
Environment="PATH=/usr/bin:/usr/local/bin"
ExecStart=/usr/bin/python3 /path/to/BOT\ WORKS/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Затем:
```bash
sudo systemctl daemon-reload
sudo systemctl enable telegram-bot
sudo systemctl start telegram-bot
```

### Использование screen/tmux

```bash
screen -S telegram-bot
cd /path/to/BOT\ WORKS
python main.py
# Нажмите Ctrl+A, затем D для отсоединения
```

### Использование Docker (опционально)

Создайте `Dockerfile`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
```

Создайте `docker-compose.yml`:
```yaml
version: '3.8'

services:
  bot:
    build: .
    restart: always
    env_file:
      - .env
    volumes:
      - ./bot_database.db:/app/bot_database.db
```

Запуск:
```bash
docker-compose up -d
```

## Обновление бота

1. Остановите бота
2. Сделайте резервную копию базы данных:
```bash
cp bot_database.db bot_database.db.backup
```
3. Обновите код:
```bash
git pull
```
4. Установите новые зависимости (если есть):
```bash
pip install -r requirements.txt
```
5. Запустите бота снова

## Резервное копирование

Регулярно делайте резервные копии:
- База данных: `bot_database.db`
- Файл конфигурации: `.env`

```bash
# Пример скрипта резервного копирования
tar -czf backup_$(date +%Y%m%d_%H%M%S).tar.gz bot_database.db .env
```

## Мониторинг

Проверка статуса (systemd):
```bash
sudo systemctl status telegram-bot
```

Просмотр логов:
```bash
sudo journalctl -u telegram-bot -f
```

## Безопасность

- Никогда не коммитьте `.env` файл в Git
- Регулярно обновляйте зависимости
- Используйте сильные пароли для сервера
- Ограничьте доступ к файлам бота:
```bash
chmod 600 .env
chmod 644 bot_database.db
```

