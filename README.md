# Disk Analyzer

Инструмент для анализа содержимого дисков. Сканирует файловую систему, сохраняет каталог в SQLite-базу и позволяет исследовать его через CLI или диалог с AI-ассистентом.

Работает на **Windows**, **Linux** и **macOS**. Python не нужен. Данные хранятся локально — никуда не отправляются.

---

## Возможности

- Быстрое сканирование дисков с сохранением в SQLite
- Топ крупнейших файлов, папок и расширений
- Поиск дубликатов по содержимому (трёхэтапное хэширование, не по имени)
- Поиск файлов по имени, расширению, размеру, дате изменения
- Интерактивный проводник — ходить по папкам прямо в терминале
- AI-чат поверх каталога: задавать вопросы на естественном языке, удалять файлы с подтверждением
- Спиннер и уведомления об инструментах прямо в чате, история команд через readline
- Поддержка нескольких LLM-провайдеров: Anthropic (Claude), OpenAI, Ollama
- Конфиг-файл для хранения API-ключей между сеансами

---

## Скачать

Готовые бинарники для всех платформ — на странице [Releases](https://github.com/DaniarSher81212/DiskAnalyzer/releases/latest):

| Платформа | Файл |
|---|---|
| Linux | `disk-analyzer` |
| macOS | `disk-analyzer-macos` |
| Windows | `disk-analyzer.exe` |

```bash
# Linux — сделать исполняемым после скачивания
wget https://github.com/DaniarSher81212/DiskAnalyzer/releases/download/v1.4.0/disk-analyzer
chmod +x disk-analyzer
./disk-analyzer help

# macOS
wget https://github.com/DaniarSher81212/DiskAnalyzer/releases/download/v1.4.0/disk-analyzer-macos
chmod +x disk-analyzer-macos
./disk-analyzer-macos help

# Windows (PowerShell)
Invoke-WebRequest -Uri "https://github.com/DaniarSher81212/DiskAnalyzer/releases/download/v1.4.0/disk-analyzer.exe" -OutFile disk-analyzer.exe
.\disk-analyzer.exe help
```

> **macOS:** при первом запуске Gatekeeper может заблокировать файл. Разрешите через:
> ```bash
> xattr -d com.apple.quarantine ./disk-analyzer-macos
> ```

---

## Первый запуск

```bash
# 1. Настроить провайдера и API-ключ
./disk-analyzer setup

# 2. Просканировать диск
./disk-analyzer scan /home

# 3. Посмотреть что занимает больше всего места
./disk-analyzer top

# 4. Поговорить с AI про содержимое диска
./disk-analyzer chat
```

Полная справка по всем командам:
```bash
./disk-analyzer help
```

---

## Установка из исходников

**Требования:** Python 3.10+

```bash
git clone https://github.com/DaniarSher81212/DiskAnalyzer
cd DiskAnalyzer
pip install -r requirements.txt
python3 main.py help
```

---

## Команды

### `setup` — первый запуск

```bash
disk-analyzer setup
```

Интерактивный мастер: выбор провайдера, ввод API-ключа, URL Ollama. Настройки сохраняются в `~/.config/disk-analyzer/config.toml`.

```bash
disk-analyzer config show   # посмотреть текущие настройки
```

---

### `scan` — сканирование

```
disk-analyzer scan <путь> [опции]
```

| Опция | Описание |
|---|---|
| `--one-filesystem` | Не выходить за пределы одной ФС (аналог `find -xdev`). **Обязательно при сканировании `/`**, иначе snap/bind-маунты раздуют счётчик |
| `--follow-reparse` | Заходить в symlink и junction-точки (по умолчанию пропускаются) |
| `--db <путь>` | Путь к SQLite-базе (по умолчанию `disk_catalog.db` рядом с бинарником) |

```bash
disk-analyzer scan C:\                        # Windows, весь диск C
disk-analyzer scan / --one-filesystem         # Linux, корневая ФС без маунтов
disk-analyzer scan /home/dan --db ~/my.db     # с нестандартной базой
```

---

### `stats` — история сканирований

```bash
disk-analyzer stats [--limit 10]
```

Показывает последние N сканов: путь, дата, количество файлов и папок, суммарный размер, число ошибок доступа.

---

### `top` — крупнейшие файлы и папки

```
disk-analyzer top [files|dirs|both|ext] [опции]
```

| Аргумент | Описание |
|---|---|
| `files` | Топ крупнейших файлов |
| `dirs` | Топ крупнейших папок (размер считается рекурсивно) |
| `both` | Файлы и папки вместе (по умолчанию) |
| `ext` | Топ расширений по суммарному объёму |

```bash
disk-analyzer top both --limit 30
disk-analyzer top ext --scan-id 5
```

---

### `duplicates` — поиск дубликатов

```
disk-analyzer duplicates [опции]
```

Находит группы файлов с одинаковым содержимым. Работает в три прохода:
1. Группировка по размеру — дёшево, без чтения файлов
2. Хэш первых 64 КБ — отсеивает большинство ложных совпадений
3. Полный хэш BLAKE2b — только для оставшихся кандидатов

| Опция | Описание |
|---|---|
| `--min-size N` | Игнорировать файлы меньше N байт (по умолчанию 1024) |
| `--limit N` | Показать первые N групп (по умолчанию 50) |
| `--scan-id N` | Использовать конкретный скан |

```bash
disk-analyzer duplicates --min-size 1048576   # только файлы от 1 МБ
```

---

### `search` — поиск файлов

```
disk-analyzer search [опции]
```

| Опция | Описание |
|---|---|
| `--name <подстрока>` | Поиск по части имени файла/папки |
| `--ext <.расш>` | Фильтр по расширению, например `.pdf` |
| `--min-size N` | Минимальный размер в байтах |
| `--max-size N` | Максимальный размер в байтах |
| `--after YYYY-MM-DD` | Изменён после даты |
| `--before YYYY-MM-DD` | Изменён до даты |
| `--files-only` | Только файлы |
| `--dirs-only` | Только папки |
| `--limit N` | Лимит результатов (по умолчанию 100) |

```bash
disk-analyzer search --ext .mp4 --min-size 104857600   # видео от 100 МБ
disk-analyzer search --name backup --after 2024-01-01  # бэкапы за 2024+
```

---

### `explore` — интерактивный проводник

```
disk-analyzer explore [путь]
```

Текстовый проводник: показывает содержимое папки постранично (25 элементов), отсортированное по размеру.

| Команда | Действие |
|---|---|
| `<номер>` | Зайти в папку / показать инфо о файле |
| `u` | На уровень вверх |
| `n` / `p` | Следующая / предыдущая страница |
| `q` | Выход |

```bash
disk-analyzer explore                  # с корня последнего скана
disk-analyzer explore /home/dan        # с конкретной папки
```

---

### `chat` — диалог с AI

```
disk-analyzer chat [--provider anthropic|openai|ollama]
```

AI-ассистент работает с каталогом через инструменты: смотрит топы, ищет дубликаты, листает папки, запускает сканы. Может предложить удалить файлы — файлы перемещаются в **корзину ОС** (не удаляются навсегда), каждое удаление требует подтверждения `y/N`.

Во время работы показывается анимированный спиннер, а каждый вызов инструмента сопровождается уведомлением:
```
> Найди дубликаты и удали лишнее
  → поиск дубликатов...
  → удаление файлов...

Перемещено в корзину: 6 объектов. Освобождено: 640 МБ.
```

История сообщений сохраняется в сеансе — стрелки ↑↓ для навигации.

**Настройка провайдера** (приоритет: CLI-флаг → ENV → конфиг-файл):

| Провайдер | ENV-переменная | Конфиг |
|---|---|---|
| Anthropic (по умолчанию) | `ANTHROPIC_API_KEY` | `~/.config/disk-analyzer/config.toml` |
| OpenAI | `OPENAI_API_KEY` | тот же файл |
| Ollama (локально) | `DISK_ANALYZER_OLLAMA_URL` | тот же файл |

```bash
disk-analyzer chat                       # Claude (из конфига или ENV)
disk-analyzer chat --provider openai     # GPT-4o
disk-analyzer chat --provider ollama     # локальная модель
```

Примеры запросов к AI:
```
> Что занимает больше всего места?
> Найди дубликаты и удали их
> Покажи все .iso файлы крупнее 1 ГБ
> Есть ли старые логи в /var/log?
```

---

## База данных

По умолчанию каталог хранится в `disk_catalog.db` рядом с бинарником. Это обычный SQLite-файл — можно открыть любым инструментом (DB Browser for SQLite, DBeaver и т.п.).

**Схема:**

```sql
scans(id, root, started_at, finished_at, file_count, dir_count, total_size, errors)
entries(scan_id, path, parent, name, ext, size, is_dir, mtime, depth)
```

Можно хранить сканы нескольких дисков в одной базе. Флаг `--db` позволяет использовать несколько разных баз.

---

## Сборка из исходников

```bash
pip install -r requirements-dev.txt
python3 build.py
```

Результат: `dist/disk-analyzer` (Linux/macOS) или `dist/disk-analyzer.exe` (Windows). Для каждой ОС нужно собирать отдельно — релизные бинарники собираются автоматически через GitHub Actions при пуше тега `v*.*.*`.

---

## Структура проекта

```
DiskAnalyzer/
├── main.py                  # точка входа
├── build.py                 # сборка через PyInstaller
├── requirements.txt         # зависимости
├── requirements-dev.txt     # + pyinstaller
└── disk_analyzer/
    ├── cli.py               # CLI, парсинг аргументов, все команды
    ├── config.py            # конфиг-файл (TOML, platformdirs)
    ├── db.py                # SQLite: схема, подключение
    ├── scanner.py           # обход ФС, запись в БД
    ├── sizes.py             # топ файлов/папок/расширений
    ├── duplicates.py        # поиск дубликатов (BLAKE2b)
    ├── search.py            # фильтрованный поиск по каталогу
    ├── explore.py           # интерактивный проводник
    └── ai/
        ├── agent.py         # цикл tool-use, хранение истории
        ├── providers.py     # Anthropic / OpenAI / Ollama
        └── tools.py         # инструменты агента (9 функций)
```
