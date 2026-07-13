# LOCUS — Runbook

Ёмкая шпаргалка по эксплуатации. Специфика конкретного инстанса (хост, пути, доступ) — в `DEPLOYMENT.md` (не в git).

## Что это

Telegram-бот → Claude Agent SDK (подписка, `claude-sonnet-5`) → конспект в `vault/raw/` + обновление LLM-вики (`vault/wiki/`) → ответ файлом в чат. Один контейнер, long polling, портов и ingress нет.

## Деплой / обновление

```bash
git clone https://github.com/tcher-coder/LOCUS.git && cd LOCUS
cp bridge/.env.example .env && $EDITOR .env && chmod 600 .env
docker compose -f docker-compose.server.yml up -d --build
```

Обновление: `git pull && docker compose -f docker-compose.server.yml up -d --build`
(vault/ и data/ — bind-mount'ы, пересборка их не трогает).

## Диагностика

```bash
docker ps | grep locus                     # Up?
docker logs -f locus-bridge                # живой лог (JSON-строки процесса)
docker logs locus-bridge 2>&1 | grep -i error
docker restart locus-bridge                # перезапуск (offset очереди TG не теряется)
```

Бот молчит → проверить по порядку:
1. `docker logs` — есть ли `Starting Telegram long polling loop`;
2. `curl https://api.telegram.org/bot<BOT_TOKEN>/getWebhookInfo` — поле `url` должно быть ПУСТЫМ (webhook несовместим с polling; удалить: `.../deleteWebhook`);
3. второй запущенный инстанс (локальный?) перехватывает getUpdates — должен работать ровно один;
4. пишете ли вы боту с аккаунта `OWNER_CHAT_ID` — остальных он игнорирует.

Агент падает на старте задачи → проверить `CLAUDE_CODE_OAUTH_TOKEN` (истекает через 1 год после `claude setup-token`; `/stats` в боте показывает срок) и что `ANTHROPIC_API_KEY` НЕ задан в окружении.

## Архивный канал

Канал подключён (`ARCHIVE_CHANNEL_ID` в `.env`). Каждый успешный ingest автоматически постится в канал (файл + TL;DR + теги).

Первичная настройка (если канал ещё не создан):
1. Создать приватный канал, добавить бота админом с правами «Публикация сообщений» + «Изменение профиля канала».
2. Узнать ID канала (`-100…`): переслать пост канала боту @userinfobot.
3. В `.env`: `ARCHIVE_CHANNEL_ID=-100…` → `docker restart locus-bridge`.
4. Аватар канала: `python bridge/set_channel_avatar.py` (использует `avatars/archive_avatar.png`).
5. `/backfill` в боте — догрузит существующие конспекты в канал.

## Данные

| Что | Где | Бэкап |
|---|---|---|
| База знаний | `./vault` (git-репозиторий, коммит после каждого ingest и `/lint`) | `git -C vault log`; при желании добавить remote |
| Реестр архива | `./data/archive_index.json` | пересоздаваем (`/backfill` сверится) |
| Сессии диалога | `./data/session_map.json` (reply_to → session_id; переживает рестарт) | не критично, пересоздаётся |
| Секреты | `./.env` (chmod 600) | вручную |

## Годовые/периодические операции

- **CLAUDE_CODE_OAUTH_TOKEN** живёт 1 год: `claude setup-token` на любой машине с подпиской → обновить `.env` → restart. `/stats` предупредит за 30 дней.
- Обновление образа (новые версии claude CLI/SDK): `docker compose -f docker-compose.server.yml build --no-cache && docker compose -f docker-compose.server.yml up -d`.

## Локальная разработка (Windows/Linux)

```bash
pip install -r bridge/requirements.txt
python bridge/smoke.py        # проверка окружения (env, ffmpeg, yt-dlp, SDK)
python bridge/main.py         # секреты берёт из bridge/.env
```
⚠️ Не запускать локально одновременно с сервером — два потребителя getUpdates конфликтуют.

## Аватары

`avatars/bot_avatar.png` — аватар бота (ставится через API: `setMyProfilePhoto`, уже установлен). `avatars/archive_avatar.png` — для канала (ставится скриптом `python bridge/set_channel_avatar.py` или вручную в настройках канала).

## Особенности команд

- `/lint` — запускает агента для гигиены вики (дубли, битые ссылки, устаревшее). **Коммитит изменения в vault** после завершения.
- `/ask` — только чтение, vault не изменяется, но тратит лимиты подписки (агентная сессия).
- `/digest`, `/archive`, `/find`, `/get` — выполняются локально без агента, лимиты не тратятся.
- `/backfill` — догрузка в архивный канал, троттлинг ~1 сообщение/3 сек.
- Диалоговый режим: ответ реплаем на сообщение бота продолжает ту же сессию (resume). Карта сессий хранится в `session_map.json` и переживает рестарт контейнера.
