# Инструкция по загрузке бота в Git репозиторий

## Пошаговая инструкция

### Шаг 1: Инициализация Git репозитория

Откройте терминал в папке проекта и выполните:

```bash
git init
```

### Шаг 2: Добавление всех файлов

```bash
git add .
```

Эта команда добавит все файлы, кроме тех, что указаны в `.gitignore` (`.env`, `bot_database.db` и т.д.)

### Шаг 3: Создание первого коммита

```bash
git commit -m "Initial commit: Telegram bot for room management"
```

### Шаг 4: Добавление удаленного репозитория

Замените `<your-repository-url>` на URL вашего репозитория:

**Для GitHub:**
```bash
git remote add origin https://github.com/ваш-username/название-репозитория.git
```

**Для GitLab:**
```bash
git remote add origin https://gitlab.com/ваш-username/название-репозитория.git
```

**Для других сервисов:**
```bash
git remote add origin <URL-вашего-репозитория>
```

### Шаг 5: Отправка кода в репозиторий

```bash
git branch -M main
git push -u origin main
```

Если ваша ветка называется `master` вместо `main`:
```bash
git push -u origin master
```

## Проверка

После выполнения команд проверьте:

1. Откройте ваш репозиторий в браузере
2. Убедитесь, что все файлы загружены
3. Проверьте, что `.env` и `bot_database.db` НЕ загружены (они должны быть в `.gitignore`)

## Если возникли проблемы

### Ошибка аутентификации

Если Git просит логин/пароль:
- Для GitHub: используйте Personal Access Token вместо пароля
- Или настройте SSH ключи

### Изменение URL репозитория

Если нужно изменить URL:
```bash
git remote set-url origin <новый-URL>
```

### Просмотр текущего remote

```bash
git remote -v
```

## Дальнейшая работа

После первой загрузки, для обновления кода:

```bash
git add .
git commit -m "Описание изменений"
git push
```

