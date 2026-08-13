# Disk Analyzer

Инструмент для анализа содержимого дисков. Сканирует файловую систему, сохраняет каталог в SQLite-базу и позволяет исследовать его через CLI или диалог с AI-ассистентом.

Работает на **Windows**, **Linux** и **macOS**. Данные хранятся локально — никуда не отправляются.

---

## Возможности

- Быстрое сканирование дисков с сохранением в SQLite
- Топ крупнейших файлов, папок и расширений
- Поиск дубликатов по содержимому (трёхэтапное хэширование, не по имени)
- Поиск файлов по имени, расширению, размеру, дате изменения
- Интерактивный проводник — ходить по папкам прямо в терминале
- AI-чат поверх каталога: задавать вопросы на естественном языке
- Поддержка нескольких LLM-провайдеров: Anthropic (Claude), OpenAI, Ollama

---

## Установка

**Требования:** Python 3.10+

```bash
git clone <repo>
cd DiskAnalyzer
pip install -r requirements.txt
```

Для AI-чата нужен как минимум один провайдер:

```bash
pip install anthropic   # для Claude
pip install openai      # для OpenAI или Ollama
```

---

## Быстрый старт

```bash
# Просканировать диск
python3 main.py scan /home

# Показать что занимает больше всего места
python3 main.py top

# Поговорить с AI про содержимое диска
python3 main.py chat
```

---

## Команды

### `scan` — сканирование

```
python3 main.py scan <путь> [опции]
```

| Опция | Описание |
|---|---|
| `--one-filesystem` | Не выходить за пределы одной ФС (аналог `find -xdev`). **Обязательно при сканировании `/`**, иначе snap/bind-маунты раздуют счётчик |
| `--follow-reparse` | Заходить в symlink и junction-точки (по умолчанию пропускаются) |
| `--db <путь>` | Путь к SQLite-базе (по умолчанию `disk_catalog.db` рядом со скриптом) |

Примеры:

```bash
python3 main.py scan C:\                        # Windows, весь диск C
python3 main.py scan / --one-filesystem         # Linux, корневая ФС без mount-ов
python3 main.py scan /home/dan --db ~/my.db     # с нестандартной базой
```

---

### `stats` — история сканирований

```
python3 main.py stats [--limit 10]
```

Показывает последние N сканов: путь, дата, количество файлов и папок, суммарный размер, число ошибок доступа.

---

### `top` — крупнейшие файлы и папки

```
python3 main.py top [files|dirs|both|ext] [опции]
```

| Аргумент | Описание |
|---|---|
| `files` | Топ крупнейших файлов |
| `dirs` | Топ крупнейших папок (размер считается рекурсивно) |
| `both` | Файлы и папки вместе (по умолчанию) |
| `ext` | Топ расширений по суммарному объёму |

```bash
python3 main.py top both --limit 30
python3 main.py top ext --scan-id 5
```

---

### `duplicates` — поиск дубликатов

```
python3 main.py duplicates [опции]
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
python3 main.py duplicates --min-size 1048576   # только файлы от 1 МБ
```

---

### `search` — поиск файлов

```
python3 main.py search [опции]
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
python3 main.py search --ext .mp4 --min-size 104857600   # видео от 100 МБ
python3 main.py search --name backup --after 2024-01-01  # бэкапы за 2024+
```

---

### `explore` — интерактивный проводник

```
python3 main.py explore [путь]
```

Текстовый проводник: показывает содержимое папки постранично (25 элементов), отсортированное по размеру.

| Команда | Действие |
|---|---|
| `<номер>` | Зайти в папку / показать инфо о файле |
| `u` | На уровень вверх |
| `n` / `p` | Следующая / предыдущая страница |
| `q` | Выход |

```bash
python3 main.py explore                  # с корня последнего скана
python3 main.py explore /home/dan        # с конкретной папки
```

---

### `chat` — диалог с AI

```
python3 main.py chat [--provider anthropic|openai|ollama]
```

AI-ассистент умеет читать каталог через встроенные инструменты: смотреть топы, искать дубликаты, листать папки, запускать новые сканы. Удалять или изменять файлы не может — только анализировать.

**Настройка провайдера:**

| Провайдер | Переменная окружения | Ключ |
|---|---|---|
| Anthropic (по умолчанию) | `DISK_ANALYZER_ANTHROPIC_MODEL` (модель) | `ANTHROPIC_API_KEY` |
| OpenAI | `DISK_ANALYZER_OPENAI_MODEL` | `OPENAI_API_KEY` |
| Ollama (локально) | `DISK_ANALYZER_OLLAMA_MODEL`, `DISK_ANALYZER_OLLAMA_URL` | не нужен |

```bash
# Claude (по умолчанию)
export ANTHROPIC_API_KEY=sk-ant-...
python3 main.py chat

# GPT-4o
export OPENAI_API_KEY=sk-...
python3 main.py chat --provider openai

# Локальная модель через Ollama
python3 main.py chat --provider ollama
```

Примеры запросов к AI:
```
> Что занимает больше всего места?
> Найди дубликаты на диске, сколько можно освободить?
> Покажи все .iso файлы крупнее 1 ГБ
> Есть ли старые логи в /var/log?
```

---

## База данных

По умолчанию каталог хранится в `disk_catalog.db` рядом со скриптом. Это обычный SQLite-файл — можно открыть любым инструментом (DB Browser for SQLite, DBeaver и т.п.).

**Схема:**

```sql
scans(id, root, started_at, finished_at, file_count, dir_count, total_size, errors)
entries(scan_id, path, parent, name, ext, size, is_dir, mtime, depth)
```

Можно хранить сканы нескольких дисков в одной базе. Флаг `--db` позволяет использовать несколько разных баз.

---

## Сборка в исполняемый файл

```bash
pip install -r requirements-dev.txt
python3 build.py
```

Результат: `dist/disk-analyzer` (Linux/macOS) или `dist/disk-analyzer.exe` (Windows). Сборка кроссплатформенная — для каждой ОС нужно запускать на ней же.

---

## Структура проекта

```
DiskAnalyzer/
├── main.py                  # точка входа
├── build.py                 # сборка через PyInstaller
├── requirements.txt         # зависимости (anthropic, openai)
├── requirements-dev.txt     # + pyinstaller
└── disk_analyzer/
    ├── cli.py               # CLI, парсинг аргументов, команды
    ├── db.py                # SQLite: схема, подключение
    ├── scanner.py           # обход ФС, запись в БД
    ├── sizes.py             # топ файлов/папок/расширений
    ├── duplicates.py        # поиск дубликатов (BLAKE2b)
    ├── search.py            # фильтрованный поиск по каталогу
    ├── explore.py           # интерактивный проводник
    └── ai/
        ├── agent.py         # цикл tool-use, хранение истории
        ├── providers.py     # Anthropic / OpenAI / Ollama
        └── tools.py         # инструменты агента (8 функций)
```
