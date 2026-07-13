# EPIC: LOCUS — Telegram-агент «ссылка → знание»

**Версия:** 2.0 (самодостаточная) · **Дата:** 2026-07-13 · **Статус:** утверждён к реализации

> **Этот документ — единственный источник контекста.** Он написан так, чтобы новая сессия Claude Code могла выполнить любую стори без доступа к переписке, в которой проект проектировался. Прочитай разделы 0–6 перед началом любой работы.

---

## 0. Как продолжить работу (для новой сессии)

**Текущее состояние репозитория (обновлено 2026-07-13, вечер):** реализация начата. Что существует:

```
V:\ANTIGRAVITY_PROJECTS\LOCUS\
├── EPIC.md              ← этот документ (основной эпик)
├── EPIC-2-ARCHIVE.md    ← отдельный эпик: архив документов в Telegram (канал + /archive,/find,/get)
├── README.md            ← создан
├── .gitignore           ← git инициализирован в корне И отдельно в vault/
├── vault/AGENTS.md      ← схема вики написана (Story 2)
├── vault/wiki/index.md, log.md  ← созданы
├── bridge/.env          ← GROQ_API_KEY заполнен; статус остальных ключей — см. сам файл
├── bridge/smoke.py, requirements.txt  ← Story 1 в работе
└── prompts/ingest_article.md, ingest_text.md, ingest_video.md, ask_wiki.md  ← Stories 3–4 в работе
```

⚠️ Чекбоксы в сторях ниже могли отстать от фактического прогресса — при возобновлении работы сверяйся с содержимым репозитория, а выполненное отмечай здесь.

**Статус (2026-07-13): ПОЛНОСТЬЮ РЕАЛИЗОВАН.** Stories 1–9 выполнены. Бридж, доставка, лимиты, архивный канал, persistence session-map — всё работает. Код в публичном репо https://github.com/tcher-coder/LOCUS, контейнер `locus-bridge` на сервере (Docker, long polling). Rich Messages верифицированы по API 10.1 (cells/is_header для таблиц, blocks для list items); `/lint` коммитит изменения; `reply_session_map` персистится в `session_map.json`. EPIC-2 (архив): код готов, `ARCHIVE_CHANNEL_ID` подключён.

**Владелец:** один пользователь (личный бот). План подписки: **Claude Pro, $20/мес** — лимиты скромные, экономия токенов является требованием, а не пожеланием. ОС: Windows 11 Pro. Общение с ботом — на русском языке.

---

## 1. Цель продукта

Личный агент, которому владелец шлёт в Telegram ссылку (YouTube/видео, статья, любой сайт) или сырой текст — и получает обратно **структурированный Markdown-конспект**, при этом каждый конспект вливается (ingest) в **самоподдерживающуюся базу знаний** — «память Карпатого» (LLM Wiki, см. раздел 3). Бот также умеет отвечать на вопросы по накопленной базе и исполнять свободные инструкции («обойди карту сайта и возьми все страницы по теме»).

---

## 2. Результаты исследования — ФАКТЫ, на которых построен дизайн

Все факты проверены по первоисточникам 2026-07-13. Не пере-исследовать без причины; если что-то не сходится при реализации — сначала перепроверить именно этот пункт по указанному источнику.

### 2.1 Подписка вместо API — легально

- `claude setup-token` генерирует OAuth-токен **сроком 1 год**, кладётся в env-переменную `CLAUDE_CODE_OAUTH_TOKEN`. Официальная документация (https://code.claude.com/docs/en/authentication) описывает его для «CI pipelines and scripts»; работает с планами Pro/Max/Team/Enterprise. Токен «scoped to inference only».
- Та же страница: `apiKeyHelper`, `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN` и, соответственно, вся цепочка кредов «apply to the CLI **and the surfaces that wrap it, including the Agent SDK**» — т.е. Agent SDK официально работает на подписочных кредах.
- Статья поддержки «Use the Claude Agent SDK with your Claude plan» (https://support.claude.com/en/articles/15036540): анонсированный на 2026-06-15 отдельный кредитный пул для Agent SDK **приостановлен** («For now, nothing has changed») — использование SDK сейчас расходует обычные лимиты подписки.
- Ограничение правил: подписочная аутентификация — для **личной автоматизации**; продукт для третьих лиц требует API-ключей. LOCUS — личный бот одного владельца, это разрешённый сценарий.
- ВАЖНО: приоритет кредов — если в окружении торчит `ANTHROPIC_API_KEY`, он перекроет подписку. В bridge не должно быть этой переменной.

### 2.2 Telegram Bot API 10.1 (выпущен 2026-06-11)

- Добавлены **Rich Messages**: метод `sendRichMessage` (структурированный контент), `sendRichMessageDraft` (стриминг частями). Changelog: https://core.telegram.org/bots/api-changelog
- Блоки: RichBlockParagraph, RichBlockSectionHeading, RichBlockPreformatted, RichBlockTable, RichBlockList, RichBlockDivider, RichBlockDetails, RichBlockAnchor, RichBlockThinking, RichBlockMathematicalExpression, медиа-блоки; inline: RichTextBold/Italic/Code/… (union RichText: строка / массив / 25 вариантов).
- Библиотека python-telegram-bot на момент исследования **ещё не имела полной поддержки 10.1** (issue: https://github.com/python-telegram-bot/python-telegram-bot/issues/5261). Дизайн-решение: Rich Messages слать **сырым HTTP** (`requests`/`httpx` на `https://api.telegram.org/bot<TOKEN>/sendRichMessage`), остальное — любой библиотекой или тоже сырым HTTP.
- Классический `sendDocument` (файл `.md`) работает всегда и используется как дублирующий канал.

### 2.3 «Память Карпатого» = LLM Wiki

- Первоисточник: гист Карпатого, апрель 2026 — https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f (5000+ звёзд). Идея: знание **компилируется** в поддерживаемую LLM-ом вики из markdown-файлов, а не достаётся по запросу (анти-RAG).
- Три слоя: **raw/** (неизменяемые исходники — агент читает, никогда не правит), **wiki/** (страницы-концепты с перекрёстными [[ссылками]], плюс `index.md` для навигации и `log.md` — хронология операций), **AGENTS.md** (схема: конвенции, правила сопровождения).
- Операция ingest: прочитать новый источник → положить конспект в `raw/` → обновить 5–15 существующих страниц вики → создать недостающие → починить [[ссылки]] → запись в `log.md` → обновить `index.md`.
- Правила гигиены (кодируются в AGENTS.md): не плодить дубли (сначала искать каноническую страницу и обновлять её), отделять разовые наблюдения от переиспользуемого знания, помечать устаревшее, противоречия фиксировать на странице явно (не перезаписывать молча).

### 2.4 Видео: скилл `bradautomates/claude-video`

- Репозиторий: https://github.com/bradautomates/claude-video — скилл `/watch` для Claude Code. Установка: `/plugin marketplace add bradautomates/claude-video` + `/plugin install watch@claude-video`, либо `npx skills add bradautomates/claude-video -g`.
- Пайплайн: сперва нативные субтитры через `yt-dlp` (бесплатно), при необходимости кадры через `ffmpeg`, фолбэк-транскрибация через Whisper (**Groq** предпочтителен, ключ уже лежит в `bridge/.env` как `GROQ_API_KEY`).
- Режимы: `transcript` (только субтитры — **наш дефолт**, кадры жгут vision-токены), `efficient` (~50 кадров), `balanced` (~100, дефолт скилла — нам НЕ подходит), `token-burner`.
- Источники: YouTube, TikTok, Vimeo, X и 300+ через yt-dlp; локальные `.mp4/.mov/.mkv/.webm`.
- Зависимости на хосте: `ffmpeg`, `yt-dlp`.

### 2.5 Claude Agent SDK (Python) — механика

- Пакет: `claude-agent-sdk` (`pip install claude-agent-sdk`); требует установленный `claude` CLI (Node.js). Базовое использование: `from claude_agent_sdk import query, ClaudeAgentOptions` — `query(prompt=..., options=...)` асинхронный генератор сообщений; опции включают `model`, `cwd`, `allowed_tools`, `permission_mode`, `system_prompt`, `setting_sources`, `max_turns`, возобновление сессии (resume по session id). Docs: https://code.claude.com/docs/en/agent-sdk
- SDK — это Claude Code как библиотека: встроенные Read/Write/Edit/Bash/Glob/Grep/WebFetch/WebSearch + скиллы/плагины окружения. Аутентификация — из окружения (`CLAUDE_CODE_OAUTH_TOKEN`).
- Модель: `claude-sonnet-5`. ⚠️ **Открытый вопрос** (проверить в Story 5): точный способ задать effort low/medium через SDK-опции (возможно через настройку модели/settings). Если параметра нет — компенсировать промптом («работай экономно, без глубокого размышления») и `max_turns`.

---

## 3. Архитектура

```
Telegram (владелец) ──ссылка/текст──▶ bridge/ (Python, long polling, очередь=1)
                                          │ query(prompt, options)
                                          ▼
                              Claude Agent SDK (claude-sonnet-5, effort low/mid,
                              cwd = vault/, auth = CLAUDE_CODE_OAUTH_TOKEN)
                                          │
                    статьи: WebFetch/WebSearch · видео: /watch (transcript)
                    текст: напрямую → пишет raw/<doc>.md → ingest в wiki/
                                          │ git commit (vault)
                                          ▼
Telegram ◀── Rich Message (10.1) + документ .md ── bridge читает результат
```

Принципы:
- **Одна свежая сессия на задачу** — память живёт в файлах vault, контекст сессии не нужен; очередь строго в один поток (параллельные сессии жгут Pro-лимиты).
- **Long polling** — не нужен домен/webhook/белый IP; работает с домашнего ПК и с VPS.
- **Vault под git** — каждый ingest = коммит (история, откат).
- Бридж — тонкий: классификация входа без LLM, весь интеллект — в сессии агента.

### 3.1 Контракты между компонентами (обязательны к соблюдению)

**Промпт → агент.** Бридж выбирает шаблон из `prompts/` по типу входа (video-URL / URL / текст), подставляет: полный текст сообщения владельца (не только URL!), флаги, кап страниц. Шаблон — каркас; свободные инструкции владельца исполняются.

**Агент → бридж (маркер результата).** Последнее сообщение агента обязано содержать строки:
```
RESULT: <относительный путь к документу в vault, например raw/2026-07-13-nazvanie.md>
SUMMARY: <1-3 предложения TL;DR для чата>
```
Если задача не выполнена: `RESULT: NONE` + `SUMMARY: <причина>`. Бридж парсит только эти строки.

**Формат документа в `raw/`** (детализируется в AGENTS.md, Story 2): имя файла `YYYY-MM-DD-slug.md`; YAML front-matter: `url`, `type` (video|article|text), `title`, `author`, `date_ingested`, `tags`; тело: TL;DR → ключевые тезисы → детали/структура источника (для видео — таймкоды) → цитаты → выводы/связи (ссылки [[на страницы вики]]).

**env-переменные (`bridge/.env`):**
| Ключ | Статус | Назначение |
|---|---|---|
| `GROQ_API_KEY` | ✅ уже заполнен | Whisper-фолбэк скилла /watch |
| `CLAUDE_CODE_OAUTH_TOKEN` | заполнить в S1 | подписочная аутентификация SDK (из `claude setup-token`) |
| `BOT_TOKEN` | заполнить в S1 | токен бота от @BotFather |
| `OWNER_CHAT_ID` | заполнить в S1 | единственный разрешённый chat_id |
| `ARCHIVE_CHANNEL_ID` | заполнить в EPIC-2 | приватный канал-архив (см. `EPIC-2-ARCHIVE.md`) |

---

## 4. Стори

### Story 1 — Окружение и аутентификация
**Как** владелец, **я хочу** подготовленное окружение, **чтобы** агент работал на подписке Pro без API-ключей.

- [x] Проверить/установить: Node.js + `claude` CLI, Python 3.11+, `ffmpeg` (`winget install Gyan.FFmpeg`), `yt-dlp` (`pip install yt-dlp` или winget).
- [x] `claude setup-token` → токен в `bridge/.env` (`CLAUDE_CODE_OAUTH_TOKEN`). Записать дату выпуска токена в README (живёт 1 год).
- [x] Установить скилл видео: `npx skills add bradautomates/claude-video -g` (альтернатива — plugin marketplace, см. 2.4).
- [x] Бот у @BotFather → `BOT_TOKEN`; узнать свой chat_id (например через @userinfobot) → `OWNER_CHAT_ID`.
- [x] `pip install claude-agent-sdk httpx python-dotenv` (+ выбранная TG-библиотека, если используется).
- [x] `bridge/smoke.py`: (а) вызов Agent SDK «ответь ok» проходит на подписке (проверить, что `ANTHROPIC_API_KEY` НЕ задан в окружении); (б) `ffmpeg -version` и `yt-dlp --version` доступны.
- [x] `git init` в корне LOCUS (или отдельно в vault — см. S2).

Приёмка: ✅ smoke зелёный; `.env` не попадает в git.

### Story 2 — Vault и схема памяти (`AGENTS.md`)
**Как** агент, **я хочу** явную схему вики, **чтобы** каждый ingest вёл базу одинаково и без дублей.

- [x] Дозаполнить структуру: `vault/wiki/index.md` (пустая навигация), `vault/wiki/log.md` (заголовок хронологии).
- [x] Написать `vault/AGENTS.md` со схемой из раздела 2.3 и контрактами из 3.1: формат raw-документа, алгоритм ingest (5–15 страниц, [[ссылки]], log, index), правила гигиены, неизменяемость raw/, правило «/watch в режиме transcript», кап краулинга (20 страниц по умолчанию), требование маркера RESULT/SUMMARY.
- [x] `git init` в `vault/` (если vault — отдельный репозиторий; решение: отдельный, чтобы база знаний жила независимо от кода).

Приёмка: ✅ ручной прогон в интерактивном Claude Code (cwd=vault) даёт корректный raw-документ.

### Story 3 — Ingest статей и сырого текста
- [x] `prompts/ingest_article.md`: WebFetch → конспект по формату 3.1 → ingest по AGENTS.md → маркер RESULT/SUMMARY.
- [x] `prompts/ingest_text.md`: то же без загрузки.
- [x] Пейволл/блокировка WebFetch → честный `RESULT: NONE` с причиной (не галлюцинировать).
- [x] Свободные инструкции: сообщение владельца целиком вставляется в промпт; сценарий «карта сайта» — найти sitemap.xml, отфильтровать по теме, кап 20 страниц, при превышении — прислать план и ждать подтверждения (см. S5 диалоговый режим).

Приёмка: ✅

### Story 4 — Ingest видео через `/watch`
- [x] `prompts/ingest_video.md`: `/watch <url>` в режиме `transcript` → конспект с таймкодами → ingest.
- [x] Флаг `+frames` в сообщении → режим `efficient`.
- [x] Прокинуть `GROQ_API_KEY` из `.env` в окружение сессии (Whisper-фолбэк). Без субтитров и без работающего фолбэка → честный отказ.

Приёмка: ✅

### Story 5 — Telegram-бридж (ядро)
- [x] `bridge/main.py`: long polling (`getUpdates`); сообщения **только** от `OWNER_CHAT_ID`.
- [x] Классификатор без LLM: video-URL (youtube.com/youtu.be/tiktok/vimeo/x.com…) / прочий URL / сырой текст → выбор шаблона; полный текст сообщения всегда идёт в промпт.
- [x] Очередь FIFO в один поток; на постановку — «⏳ принято, в очереди N».
- [x] `bridge/agent.py`: query() с `cwd=vault/`, `model="claude-sonnet-5"`, разрешённые инструменты, таймаут задачи ~30 мин; effort — родное поле `ClaudeAgentOptions(effort=...)` (SDK 0.2.116); парсинг RESULT/SUMMARY.
- [x] Статусы стадий в чат («читаю → конспектирую → обновляю вики → готово»).
- [x] Диалоговый режим: ответ реплаем на сообщение бота = resume той же сессии SDK. **Session map персистится в `session_map.json`** (переживает рестарт).
- [x] `git commit` в vault после успешного ingest (сообщение коммита = title документа).

Приёмка: ✅

### Story 6 — Доставка: Rich Messages + `.md`
- [x] `bridge/telegram_out.py`: конвертер Markdown → RichBlocks (заголовки→SectionHeading, списки→List, таблицы→Table, код→Preformatted, цитаты→BlockQuotation) + `sendRichMessage` сырым HTTP. **Формат верифицирован по API 10.1** (cells/is_header, list items с blocks).
- [x] Всегда дублировать `sendDocument` с `.md`-файлом из vault.
- [x] Фолбэк при ошибке Rich Message: обычное сообщение (HTML parse_mode, обрезка до 4096) + файл.
- [x] Длинные конспекты: в чат — TL;DR/тезисы, полное — файлом.

Приёмка: ✅

> Архив всех результатов (канал «LOCUS Archive» + команды /archive, /find, /get) — **отдельный эпик `EPIC-2-ARCHIVE.md`**, выполняется после S5–S6.

### Story 7 — Экономия лимитов и устойчивость
- [x] Effort low по умолчанию; `+deep` в сообщении → medium.
- [x] Порог длины входа: сверх него — конспект по частям или явное сокращение.
- [x] Rate-limit подписки: понятное сообщение + автоповтор после окна сброса; ошибка одной задачи не блокирует очередь; ретрай сетевых ошибок ×1; лог в файл.
- [x] `/stats`: задач сегодня, очередь, дата выпуска setup-token (предупреждение за 30 дней до годовщины).

### Story 8 — Команды памяти
- [x] `/ask <вопрос>` — сессия-запрос: поиск по wiki (Grep/Read), ответ со ссылками на страницы, БЕЗ ingest (тратит лимиты).
- [x] `/digest` — сводка последних записей log.md.
- [x] `/lint` — ручной сеанс гигиены вики по AGENTS.md (дубли, битые [[ссылки]], устаревшее). **Коммитит изменения в vault.**

> Команды доступа к архиву документов (`/archive`, `/find`, `/get`, `/backfill`) — см. `EPIC-2-ARCHIVE.md`.

### Story 9 — Развёртывание 24/7
- [x] Вариант A (старт): Windows-ПК владельца — автозапуск (Task Scheduler/NSSM), рестарт при падении.
- [x] Вариант B (цель): Linux-сервер — Docker-контейнер (`docker-compose.server.yml`), `restart: always`; на сервере Node.js+claude CLI, Python, ffmpeg, yt-dlp — всё внутри образа; `CLAUDE_CODE_OAUTH_TOKEN` в `.env` (браузер не нужен); vault — bind-mount.
- [x] `README.md`: запуск/обновление/перенос, продление setup-token. `RUNBOOK.md`: эксплуатация, диагностика. `DEPLOYMENT.md`: специфика инстанса (не в git).

### Story 10 — E2E-приёмка
- [ ] Статья → конспект + `.md` + вики + git-коммит. · [ ] YouTube с субтитрами → конспект с таймкодами. · [ ] Сырой текст → ingest. · [ ] Пейволл → честный отказ, очередь жива. · [ ] `/ask` отвечает по вики со страницами-источниками. · [ ] Две ссылки подряд → последовательно. · [ ] Чужой chat_id → отказ. · [ ] «Обойди sitemap по теме X» → план → подтверждение реплаем → пачка документов. · [ ] Расход лимитов за тестовый день записан в README.

---

## 5. Порядок и зависимости

```
S1 ─▶ S2 ─▶ S3 ─▶ S5 ─▶ S6 ─▶ S7 ─▶ S8 ─▶ S9 ─▶ S10
        └─▶ S4 ────┘
```
MVP = S1–S6 (ссылка → документ в чате). Каждую стори завершать git-коммитом и отметкой чекбоксов в этом файле.

## 6. Риски и открытые вопросы

| # | Риск / вопрос | Действие |
|---|---|---|
| 1 | ✅ ЗАКРЫТО: effort — родное поле `ClaudeAgentOptions(effort="low"\|"medium"\|...)` (SDK 0.2.116) | Используется в agent.py |
| 2 | Anthropic возобновит кредитный пул Agent SDK | Архитектура не меняется; следить за support-статьёй (2.1) |
| 3 | Pro-лимитов мало при активном использовании | effort low, очередь=1, /stats; при нужде — апгрейд плана |
| 4 | python-telegram-bot без 10.1 | Rich Messages сырым HTTP (S6); фолбэк HTML+файл |
| 5 | setup-token истекает через год | README + предупреждение в /stats |
| 6 | Groq-ключ засвечен в переписке при передаче | При желании перевыпустить в консоли Groq и заменить в .env |

## 7. Глоссарий

- **vault** — папка базы знаний (raw + wiki + AGENTS.md), отдельный git-репозиторий.
- **ingest** — операция «источник → raw-документ → обновление вики» по правилам AGENTS.md.
- **bridge** — Python-процесс: Telegram long polling + вызовы Agent SDK.
- **RESULT/SUMMARY** — обязательный маркер в финальном сообщении агента (контракт 3.1).
- **/watch** — скилл claude-video для видео (2.4).
