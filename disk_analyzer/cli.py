"""Командная строка disk-analyzer."""
from __future__ import annotations

import argparse
import os
import sys
import threading
import time
from pathlib import Path

from . import config as cfg_module
from . import db, duplicates, explore, scanner, search, sizes


def _c(code: str, text: str) -> str:
    """Обернуть текст в ANSI-код, если терминал поддерживает цвета."""
    if not sys.stdout.isatty():
        return text
    return f"\033[{code}m{text}\033[0m"


def _bold(t: str) -> str: return _c("1", t)
def _cyan(t: str) -> str: return _c("36", t)
def _yellow(t: str) -> str: return _c("33", t)
def _dim(t: str) -> str: return _c("2", t)


def cmd_help(args):
    W = 64
    line = "─" * W

    def section(title: str) -> None:
        print(f"\n{_bold(_cyan(title))}")
        print(_dim(line))

    def cmd(name: str, desc: str) -> None:
        print(f"  {_bold(_yellow(f'disk-analyzer {name}'))}")
        print(f"    {desc}")

    def opt(flag: str, desc: str) -> None:
        print(f"    {_cyan(flag):<30} {desc}")

    def example(line_: str) -> None:
        print(f"    {_dim('$')} {line_}")

    print(_bold(f"\ndisk-analyzer — анализатор содержимого дисков"))
    print(_dim(f"Сохраняет каталог файловой системы в SQLite и позволяет исследовать его"))
    print(_dim(f"через команды CLI или диалог с AI-ассистентом.\n"))

    # ── Первый запуск ──────────────────────────────────────
    section("ПЕРВЫЙ ЗАПУСК")
    cmd("setup", "Мастер настройки: провайдер, API-ключ, URL Ollama")
    print()
    example("disk-analyzer setup")
    example("disk-analyzer config show        # показать текущие настройки")

    # ── Сканирование ───────────────────────────────────────
    section("СКАНИРОВАНИЕ")
    cmd("scan <путь>", "Просканировать путь и сохранить каталог в базу данных")
    print()
    opt("--one-filesystem",    "Не выходить за пределы одной ФС (нужно при сканировании /)")
    opt("--follow-reparse",    "Заходить в symlink и junction-точки")
    opt("--db <файл>",         "Путь к базе данных (по умолчанию disk_catalog.db)")
    print()
    example("disk-analyzer scan /home")
    example("disk-analyzer scan / --one-filesystem")
    example(r"disk-analyzer scan C:\\")

    # ── Анализ ─────────────────────────────────────────────
    section("АНАЛИЗ")
    cmd("stats",               "История сканирований: пути, даты, размеры")
    cmd("top [files|dirs|both|ext]", "Крупнейшие файлы / папки / расширения")
    cmd("duplicates",          "Группы файлов-дубликатов по содержимому (BLAKE2b)")
    cmd("search",              "Поиск по имени, расширению, размеру, дате")
    cmd("diff [scan_a] [scan_b]", "Сравнить два скана: что появилось, исчезло, изменилось")
    cmd("purge",               "Удалить старые сканы из БД, оставив N последних на каждый путь")
    cmd("export",              "Выгрузить каталог в CSV или JSON")
    cmd("explore [путь]",      "Интерактивный проводник: ходить по папкам в терминале")
    print()
    opt("--limit N",           "Количество результатов")
    opt("--scan-id N",         "Использовать конкретный скан")
    opt("--root <путь>",       "Взять последний скан для указанного корня")
    opt("--under <путь>",      "Показывать только файлы/папки внутри указанного пути (для top и search)")
    print()
    example("disk-analyzer top both --limit 30")
    example("disk-analyzer top ext --under /home/dan")
    example("disk-analyzer search --ext .mp4 --under /home/dan/work")
    example("disk-analyzer duplicates --min-size 1048576")
    example("disk-analyzer diff              # два последних скана")
    example("disk-analyzer diff 12 14        # конкретные сканы")
    example("disk-analyzer purge             # удалить старые, оставить 3 последних")
    example("disk-analyzer export -o catalog.csv")
    example("disk-analyzer export --format json -o catalog.json")
    example("disk-analyzer explore /home/dan")

    # ── Параметры search ───────────────────────────────────
    section("ПАРАМЕТРЫ ПОИСКА (search)")
    opt("--name <подстрока>",  "Часть имени файла или папки")
    opt("--ext <.расш>",       "Расширение, например .pdf или .mp4")
    opt("--min-size N",        "Минимальный размер в байтах")
    opt("--max-size N",        "Максимальный размер в байтах")
    opt("--after YYYY-MM-DD",  "Дата изменения — от")
    opt("--before YYYY-MM-DD", "Дата изменения — до")
    opt("--files-only",        "Только файлы")
    opt("--dirs-only",         "Только папки")

    # ── Проводник ──────────────────────────────────────────
    section("УПРАВЛЕНИЕ В ПРОВОДНИКЕ (explore)")
    opt("<номер>",             "Зайти в папку / показать информацию о файле")
    opt("u",                   "Подняться на уровень вверх")
    opt("n / p",               "Следующая / предыдущая страница (по 25 элементов)")
    opt("q",                   "Выйти из проводника")

    # ── AI-чат ─────────────────────────────────────────────
    section("AI-ЧАТ")
    cmd("chat [--provider anthropic|openai|ollama]",
        "Диалог с AI-ассистентом поверх каталога дисков")
    print()
    print("    AI умеет:")
    for item in [
        "находить что занимает больше всего места",
        "искать дубликаты и предлагать их удалить (с подтверждением)",
        "искать файлы по типу, размеру, дате",
        "запускать сканирование если каталога нет",
        "отвечать на вопросы про структуру диска",
    ]:
        print(f"    {_dim('·')} {item}")
    print()
    example("disk-analyzer chat")
    example("disk-analyzer chat --provider openai")
    print()
    print(f"    {_dim('Примеры запросов к AI:')}")
    for q in [
        "Что занимает больше всего места?",
        "Найди дубликаты и удали их",
        "Покажи все .iso файлы крупнее 1 ГБ",
        "Есть ли старые логи в /var/log?",
    ]:
        print(f"    {_dim('>')} {q}")

    # ── Провайдеры ─────────────────────────────────────────
    section("НАСТРОЙКА ПРОВАЙДЕРОВ")
    print(f"  Приоритет: {_bold('CLI-флаг')} → {_bold('ENV')} → {_bold('конфиг-файл')}\n")
    print(f"  {'Провайдер':<12} {'ENV-ключ':<30} {'Конфиг-файл'}")
    print(f"  {_dim('─'*12)} {_dim('─'*30)} {_dim('─'*20)}")
    rows = [
        ("anthropic", "ANTHROPIC_API_KEY", "~/.config/disk-analyzer/config.toml"),
        ("openai",    "OPENAI_API_KEY",    "(тот же файл)"),
        ("ollama",    "DISK_ANALYZER_OLLAMA_URL", "(тот же файл)"),
    ]
    for name, env, conf in rows:
        print(f"  {_yellow(name):<12} {env:<30} {_dim(conf)}")

    # ── Конфиг ─────────────────────────────────────────────
    section("УПРАВЛЕНИЕ КОНФИГОМ")
    cmd("setup",               "Интерактивный мастер первого запуска")
    cmd("config show",         "Показать текущие настройки (ключи замаскированы)")
    print()
    print(f"  Конфиг хранится в: {_cyan(str(cfg_module.CONFIG_PATH))}")

    print()


def human_size(n: float) -> str:
    for unit in ("Б", "КБ", "МБ", "ГБ", "ТБ", "ПБ"):
        if abs(n) < 1024:
            return f"{n:,.1f} {unit}".replace(",", " ")
        n /= 1024
    return f"{n:,.1f} ЭБ".replace(",", " ")


def _resolve_scan_id(conn, args) -> int:
    scan_id = getattr(args, "scan_id", None)
    if scan_id:
        return scan_id
    root = getattr(args, "root", None)
    found = db.latest_scan_id(conn, root)
    if found is None:
        print("Нет завершённых сканирований. Сначала выполните: scan <путь>", file=sys.stderr)
        sys.exit(1)
    return found


def cmd_scan(args):
    conn = db.connect(args.db)
    print(f"Сканирование {args.path} ...")
    t0 = time.time()

    def on_progress(fc: int, dc: int, ts: int) -> None:
        if sys.stdout.isatty():
            print(f"\r  Файлов: {fc:,}  Папок: {dc:,}  Объём: {human_size(ts)}   ", end="", flush=True)

    scan_id = scanner.scan(
        args.path, conn,
        follow_reparse=args.follow_reparse,
        one_filesystem=args.one_filesystem,
        on_progress=on_progress,
    )
    if sys.stdout.isatty():
        print()  # сброс строки прогресса
    elapsed = time.time() - t0
    row = conn.execute(
        "SELECT file_count, dir_count, total_size, errors FROM scans WHERE id = ?",
        (scan_id,),
    ).fetchone()
    file_count, dir_count, total_size, errors = row
    print(
        f"Готово за {elapsed:.1f}с: scan_id={scan_id}, файлов={file_count}, "
        f"папок={dir_count}, объём={human_size(total_size)}, ошибок={errors}"
    )


def cmd_stats(args):
    conn = db.connect(args.db)
    rows = conn.execute(
        "SELECT id, root, started_at, finished_at, file_count, dir_count, total_size, errors "
        "FROM scans ORDER BY id DESC LIMIT ?",
        (args.limit,),
    ).fetchall()
    if not rows:
        print("Сканирований пока нет.")
        return
    for scan_id, root, started, finished, fc, dc, size, errors in rows:
        status = "завершено" if finished else "прервано"
        print(
            f"[{scan_id}] {root} — {status}, файлов={fc}, папок={dc}, "
            f"объём={human_size(size)}, ошибок={errors}, начато={started}"
        )


def cmd_top(args):
    conn = db.connect(args.db)
    scan_id = _resolve_scan_id(conn, args)
    under = getattr(args, "under", None)
    suffix = f"  {_dim(f'(в {under})')}" if under else ""
    if args.what in ("files", "both"):
        print(f"== Топ {args.limit} файлов{suffix} ==")
        for path, size in sizes.top_files(conn, scan_id, args.limit, under=under):
            print(f"{human_size(size):>12}  {path}")
    if args.what in ("dirs", "both"):
        print(f"== Топ {args.limit} папок{suffix} ==")
        for path, size in sizes.top_dirs(conn, scan_id, args.limit, under=under):
            print(f"{human_size(size):>12}  {path}")
    if args.what == "ext":
        print(f"== Топ {args.limit} расширений по объёму{suffix} ==")
        for ext, total, cnt in sizes.top_extensions(conn, scan_id, args.limit, under=under):
            print(f"{human_size(total):>12}  {ext:<15} ({cnt} файлов)")


def cmd_duplicates(args):
    conn = db.connect(args.db)
    scan_id = _resolve_scan_id(conn, args)
    print("Поиск дубликатов (это может занять время на больших каталогах)...")
    groups = duplicates.find_duplicates(conn, scan_id, min_size=args.min_size)
    if not groups:
        print("Дубликаты не найдены.")
        return
    total_wasted = sum(g.wasted_bytes for g in groups)
    for g in groups[: args.limit]:
        print(f"\n-- {human_size(g.size)} x{len(g.paths)}, лишнее место: {human_size(g.wasted_bytes)}")
        for p in g.paths:
            print(f"   {p}")
    print(f"\nВсего групп: {len(groups)}. Потенциально можно освободить: {human_size(total_wasted)}")


def cmd_search(args):
    conn = db.connect(args.db)
    scan_id = _resolve_scan_id(conn, args)
    rows = search.search(
        conn,
        scan_id,
        name=args.name,
        ext=args.ext,
        min_size=args.min_size,
        max_size=args.max_size,
        after=args.after,
        before=args.before,
        dirs_only=args.dirs_only,
        files_only=args.files_only,
        limit=args.limit,
        under=getattr(args, "under", None),
    )
    if not rows:
        print("Ничего не найдено.")
        return
    for path, size, is_dir, mtime in rows:
        kind = "DIR " if is_dir else "FILE"
        print(f"{kind} {human_size(size):>12}  {mtime or '':<25} {path}")


def cmd_explore(args):
    conn = db.connect(args.db)
    scan_id = _resolve_scan_id(conn, args)
    start_path = args.path
    if start_path is None:
        start_path = conn.execute(
            "SELECT root FROM scans WHERE id = ?", (scan_id,)
        ).fetchone()[0]
    explore.run(conn, scan_id, start_path)


def cmd_export(args):
    import csv
    import json as _json

    conn = db.connect(args.db)
    scan_id = _resolve_scan_id(conn, args)
    cols = ("path", "name", "ext", "size", "is_dir", "mtime", "depth")
    cursor = conn.execute(
        f"SELECT {', '.join(cols)} FROM entries WHERE scan_id = ? ORDER BY path",
        (scan_id,),
    )

    out_path = args.output
    f = open(out_path, "w", encoding="utf-8", newline="") if out_path else sys.stdout
    count = 0
    try:
        if args.format == "csv":
            w = csv.writer(f)
            w.writerow(cols)
            for row in cursor:
                w.writerow(row)
                count += 1
        else:
            f.write("[\n")
            first = True
            for row in cursor:
                if not first:
                    f.write(",\n")
                f.write("  " + _json.dumps(dict(zip(cols, row)), ensure_ascii=False))
                first = False
                count += 1
            f.write("\n]\n")
    finally:
        if out_path:
            f.close()

    if out_path:
        print(f"Экспортировано {count:,} записей в {out_path}")
    else:
        print(f"# {count:,} записей", file=sys.stderr)


def cmd_purge(args):
    conn = db.connect(args.db)
    keep = args.keep

    to_delete = conn.execute("""
        SELECT id, root, started_at, file_count, total_size FROM scans
        WHERE finished_at IS NULL
           OR id NOT IN (
               SELECT id FROM (
                   SELECT id, ROW_NUMBER() OVER (PARTITION BY root ORDER BY id DESC) as rn
                   FROM scans WHERE finished_at IS NOT NULL
               ) WHERE rn <= ?
           )
        ORDER BY root, id
    """, (keep,)).fetchall()

    if not to_delete:
        print(f"Нечего удалять — по {keep} последних завершённых сканов на каждый путь сохранено.")
        return

    total_entries = sum(row[3] or 0 for row in to_delete)
    print(f"Будет удалено {len(to_delete)} сканов ({total_entries:,} записей):")
    for scan_id, root, started_at, file_count, size in to_delete:
        status = f"файлов={file_count}" if file_count else "незавершён"
        print(f"  [{scan_id}] {root}  {(started_at or '')[:19]}  {status}  {human_size(size or 0)}")

    if args.dry_run:
        print("\n(--dry-run: ничего не удалено)")
        return

    try:
        answer = input("\nУдалить? [y/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("")
        return
    if answer != "y":
        print("Отменено.")
        return

    db_path = conn.execute("PRAGMA database_list").fetchone()[2]

    ids = [row[0] for row in to_delete]
    conn.execute(f"DELETE FROM scans WHERE id IN ({','.join('?' * len(ids))})", ids)
    conn.commit()

    print("Очистка базы данных (VACUUM)...")
    conn.execute("VACUUM")

    size_before, size_after = None, None
    if db_path:
        p = Path(db_path)
        if p.exists():
            size_after = p.stat().st_size

    freed_msg = f", освобождено {human_size(size_before - size_after)}" if size_before and size_after else ""
    print(f"Готово: удалено {len(ids)} сканов{freed_msg}.")


def cmd_diff(args):
    conn = db.connect(args.db)

    if args.scan_a is not None and args.scan_b is not None:
        id_a, id_b = args.scan_a, args.scan_b
    else:
        # По умолчанию: два последних скана одного корня, иначе — любые два последних
        latest = conn.execute(
            "SELECT root FROM scans WHERE finished_at IS NOT NULL ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if not latest:
            print("Нет завершённых сканирований.", file=sys.stderr)
            sys.exit(1)
        rows = conn.execute(
            "SELECT id FROM scans WHERE finished_at IS NOT NULL AND root = ? ORDER BY id DESC LIMIT 2",
            (latest[0],),
        ).fetchall()
        if len(rows) < 2:
            rows = conn.execute(
                "SELECT id FROM scans WHERE finished_at IS NOT NULL ORDER BY id DESC LIMIT 2"
            ).fetchall()
        if len(rows) < 2:
            print("Нужно минимум два завершённых скана.", file=sys.stderr)
            sys.exit(1)
        id_b, id_a = rows[0][0], rows[1][0]

    info_a = conn.execute("SELECT root, started_at FROM scans WHERE id = ?", (id_a,)).fetchone()
    info_b = conn.execute("SELECT root, started_at FROM scans WHERE id = ?", (id_b,)).fetchone()
    if not info_a or not info_b:
        print("Один из указанных scan_id не найден.", file=sys.stderr)
        sys.exit(1)

    print(f"\nСравнение сканов:")
    print(f"  A [{id_a}] {info_a[0]}  ({info_a[1][:19]})")
    print(f"  B [{id_b}] {info_b[0]}  ({info_b[1][:19]})")
    if info_a[0] != info_b[0]:
        print(_dim("  (разные корни — различий может быть много)"))
    print()

    fetch = args.limit + 1  # +1 чтобы понять есть ли ещё

    new_rows = conn.execute("""
        SELECT b.path, b.size FROM entries b
        WHERE b.scan_id = ? AND b.is_dir = 0
          AND NOT EXISTS (SELECT 1 FROM entries WHERE scan_id = ? AND path = b.path)
        ORDER BY b.size DESC LIMIT ?
    """, (id_b, id_a, fetch)).fetchall()

    del_rows = conn.execute("""
        SELECT a.path, a.size FROM entries a
        WHERE a.scan_id = ? AND a.is_dir = 0
          AND NOT EXISTS (SELECT 1 FROM entries WHERE scan_id = ? AND path = a.path)
        ORDER BY a.size DESC LIMIT ?
    """, (id_a, id_b, fetch)).fetchall()

    changed_rows = conn.execute("""
        SELECT a.path, a.size, b.size FROM entries a
        JOIN entries b ON a.path = b.path
        WHERE a.scan_id = ? AND b.scan_id = ?
          AND a.is_dir = 0 AND b.is_dir = 0 AND a.size != b.size
        ORDER BY ABS(CAST(b.size AS INTEGER) - CAST(a.size AS INTEGER)) DESC LIMIT ?
    """, (id_a, id_b, fetch)).fetchall()

    if not new_rows and not del_rows and not changed_rows:
        print("Различий не обнаружено.")
        return

    limit = args.limit

    if new_rows:
        has_more = len(new_rows) > limit
        shown = new_rows[:limit]
        total_size = sum(s for _, s in shown)
        print(_bold(_cyan(f"НОВЫЕ ({len(shown)}{'+'  if has_more else ''} файлов, +{human_size(total_size)}):")))
        for path, size in shown:
            print(f"  {_cyan('+'):>3} {human_size(size):>12}  {path}")
        if has_more:
            print(_dim(f"  ... показано {limit}, используйте --limit для большего"))
        print()

    if del_rows:
        has_more = len(del_rows) > limit
        shown = del_rows[:limit]
        total_size = sum(s for _, s in shown)
        print(_bold(_yellow(f"УДАЛЁННЫЕ ({len(shown)}{'+'  if has_more else ''} файлов, -{human_size(total_size)}):")))
        for path, size in shown:
            print(f"  {_yellow('-'):>3} {human_size(size):>12}  {path}")
        if has_more:
            print(_dim(f"  ... показано {limit}, используйте --limit для большего"))
        print()

    if changed_rows:
        has_more = len(changed_rows) > limit
        shown = changed_rows[:limit]
        print(_bold(f"ИЗМЕНЁННЫЕ ({len(shown)}{'+'  if has_more else ''} файлов):"))
        for path, size_a, size_b in shown:
            delta = size_b - size_a
            sign = "+" if delta >= 0 else ""
            print(f"  {'~':>3} {human_size(size_b):>12}  {path}  "
                  f"{_dim(f'({human_size(size_a)} → {human_size(size_b)}, {sign}{human_size(delta)})')}")
        if has_more:
            print(_dim(f"  ... показано {limit}, используйте --limit для большего"))
        print()


def cmd_setup(args):
    print("=== Настройка disk-analyzer ===")
    print(f"Конфиг будет сохранён в: {cfg_module.CONFIG_PATH}\n")

    providers = ["anthropic", "openai", "ollama"]
    current_default = cfg_module.get_default_provider()
    default_choice = input(f"Провайдер по умолчанию [{'/'.join(providers)}] (сейчас: {current_default}): ").strip().lower()
    if default_choice in providers:
        cfg_module.set_default_provider(default_choice)
        selected = default_choice
    else:
        selected = current_default

    if selected in ("anthropic", "openai"):
        env_var = "ANTHROPIC_API_KEY" if selected == "anthropic" else "OPENAI_API_KEY"
        current_key = cfg_module.get_api_key(selected)
        prompt = f"API-ключ для {selected}"
        if current_key:
            prompt += f" (сейчас: {cfg_module.masked(current_key)}, Enter — оставить)"
        prompt += ": "
        key = input(prompt).strip()
        if key:
            cfg_module.set_provider_setting(selected, "api_key", key)

    if selected == "ollama":
        current_url = cfg_module.get_ollama_url()
        url = input(f"URL Ollama (сейчас: {current_url}, Enter — оставить): ").strip()
        if url:
            cfg_module.set_provider_setting("ollama", "url", url)
        current_model = cfg_module.get_model("ollama") or "llama3.1"
        model = input(f"Модель Ollama (сейчас: {current_model}, Enter — оставить): ").strip()
        if model:
            cfg_module.set_provider_setting("ollama", "model", model)

    print(f"\nГотово. Настройки сохранены в {cfg_module.CONFIG_PATH}")


def cmd_config_show(args):
    print(f"Конфиг: {cfg_module.CONFIG_PATH}")
    if not cfg_module.CONFIG_PATH.exists():
        print("Файл не найден. Запустите: disk-analyzer setup")
        return
    config = cfg_module.load()
    providers = config.get("providers", {})
    print(f"Провайдер по умолчанию: {providers.get('default', 'anthropic')}")
    for name in ("anthropic", "openai", "ollama"):
        settings = providers.get(name, {})
        if not settings:
            continue
        print(f"\n[{name}]")
        for k, v in settings.items():
            display = cfg_module.masked(v) if k == "api_key" else v
            print(f"  {k} = {display}")


_TOOL_LABELS = {
    "list_scans":      "история сканов",
    "scan_disk":       "сканирование диска",
    "top_folders":     "крупнейшие папки",
    "top_files":       "крупнейшие файлы",
    "top_extensions":  "топ расширений",
    "list_folder":     "содержимое папки",
    "find_duplicates": "поиск дубликатов",
    "search_files":    "поиск файлов",
    "propose_deletion":"удаление файлов",
    "diff_scans":      "сравнение сканов",
}


class _Spinner:
    _FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

    def __init__(self) -> None:
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._active = False

    def start(self) -> None:
        if not sys.stdout.isatty() or self._active:
            return
        self._stop.clear()
        self._active = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if not self._active:
            return
        self._stop.set()
        if self._thread:
            self._thread.join()
        print("\r\033[K", end="", flush=True)
        self._active = False

    def _run(self) -> None:
        i = 0
        while not self._stop.is_set():
            print(f"\r\033[2m{self._FRAMES[i % 10]} Думаю...\033[0m", end="", flush=True)
            i += 1
            time.sleep(0.08)


def cmd_chat(args):
    from .ai.agent import Agent
    from .ai.providers import get_provider

    # readline: история команд между сообщениями
    try:
        import readline
        readline.set_history_length(500)
    except ImportError:
        pass

    provider_name = args.provider or os.environ.get("DISK_ANALYZER_PROVIDER") or cfg_module.get_default_provider()
    try:
        provider = get_provider(provider_name)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)
    except ImportError as exc:
        print(
            f"Не удалось загрузить провайдера '{provider_name}': {exc}\n"
            f"Установите зависимость: pip install anthropic  (или openai — для openai/ollama)",
            file=sys.stderr,
        )
        sys.exit(1)

    conn = db.connect(args.db)
    agent = Agent(provider, conn)
    spinner = _Spinner()

    def on_tool_call(name: str) -> None:
        spinner.stop()
        label = _TOOL_LABELS.get(name, name)
        print(f"\033[2m  → {label}...\033[0m", flush=True)

    def on_tool_end(name: str) -> None:
        if name != "propose_deletion":
            spinner.start()

    print(f"\nЧат с AI ({_bold(_cyan(provider_name))}). {_dim('Ctrl+C или пустая строка — выход.')}\n")

    while True:
        try:
            user_message = input(_bold("> ") if sys.stdout.isatty() else "> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("")
            return
        if not user_message:
            return

        spinner.start()
        try:
            answer = agent.ask(user_message, on_tool_call=on_tool_call, on_tool_end=on_tool_end)
        except Exception as exc:
            spinner.stop()
            print(f"Ошибка: {exc}", file=sys.stderr)
            continue
        spinner.stop()
        print(f"\n{answer}\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="disk-analyzer", description="Анализ содержимого дисков"
    )
    parser.add_argument(
        "--db", type=Path, default=db.DEFAULT_DB_PATH,
        help=f"Путь к файлу каталога SQLite (по умолчанию: {db.DEFAULT_DB_PATH})",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_scan = sub.add_parser("scan", help="Просканировать путь и сохранить каталог в БД")
    p_scan.add_argument("path", help="Путь для сканирования, например C:\\ или D:\\Data")
    p_scan.add_argument(
        "--follow-reparse", action="store_true",
        help="Заходить в symlink/junction точки (по умолчанию пропускаются во избежание циклов)",
    )
    p_scan.add_argument(
        "--one-filesystem", action="store_true",
        help="Не переходить на другие файловые системы (аналог find -xdev, полезно при сканировании /)",
    )
    p_scan.set_defaults(func=cmd_scan)

    p_stats = sub.add_parser("stats", help="Показать историю сканирований")
    p_stats.add_argument("--limit", type=int, default=10)
    p_stats.set_defaults(func=cmd_stats)

    p_top = sub.add_parser("top", help="Крупнейшие файлы/папки/расширения")
    p_top.add_argument("what", choices=["files", "dirs", "both", "ext"], nargs="?", default="both")
    p_top.add_argument("--scan-id", type=int, dest="scan_id")
    p_top.add_argument("--root", help="Использовать последний скан для этого корня")
    p_top.add_argument("--under", help="Показывать только файлы/папки внутри указанного пути")
    p_top.add_argument("--limit", type=int, default=20)
    p_top.set_defaults(func=cmd_top)

    p_dup = sub.add_parser("duplicates", help="Найти файлы-дубликаты по содержимому")
    p_dup.add_argument("--scan-id", type=int, dest="scan_id")
    p_dup.add_argument("--root", help="Использовать последний скан для этого корня")
    p_dup.add_argument("--min-size", type=int, default=1024, help="Игнорировать файлы меньше N байт")
    p_dup.add_argument("--limit", type=int, default=50, help="Сколько групп показать")
    p_dup.set_defaults(func=cmd_duplicates)

    p_search = sub.add_parser("search", help="Поиск файлов/папок в каталоге")
    p_search.add_argument("--scan-id", type=int, dest="scan_id")
    p_search.add_argument("--root", help="Использовать последний скан для этого корня")
    p_search.add_argument("--name", help="Подстрока в имени файла/папки")
    p_search.add_argument("--ext", help="Расширение, например .pdf")
    p_search.add_argument("--min-size", type=int, dest="min_size")
    p_search.add_argument("--max-size", type=int, dest="max_size")
    p_search.add_argument("--after", help="mtime >= ISO-дата")
    p_search.add_argument("--before", help="mtime <= ISO-дата")
    p_search.add_argument("--dirs-only", action="store_true")
    p_search.add_argument("--files-only", action="store_true")
    p_search.add_argument("--under", help="Ограничить поиск указанным поддеревом")
    p_search.add_argument("--limit", type=int, default=100)
    p_search.set_defaults(func=cmd_search)

    p_export = sub.add_parser("export", help="Выгрузить каталог в CSV или JSON")
    p_export.add_argument("--format", choices=["csv", "json"], default="csv", help="Формат вывода (по умолчанию csv)")
    p_export.add_argument("--output", "-o", help="Файл для записи (по умолчанию — stdout)")
    p_export.add_argument("--scan-id", type=int, dest="scan_id")
    p_export.add_argument("--root", help="Использовать последний скан для этого корня")
    p_export.set_defaults(func=cmd_export)

    p_purge = sub.add_parser("purge", help="Удалить старые сканы из БД, оставив N последних на каждый путь")
    p_purge.add_argument("--keep", type=int, default=3, help="Сколько последних сканов оставить на каждый путь (по умолчанию 3)")
    p_purge.add_argument("--dry-run", action="store_true", help="Показать что будет удалено, не удаляя")
    p_purge.set_defaults(func=cmd_purge)

    p_diff = sub.add_parser("diff", help="Сравнить два скана — что появилось, исчезло, изменилось")
    p_diff.add_argument("scan_a", type=int, nargs="?", help="ID старого скана (по умолчанию — предпоследний)")
    p_diff.add_argument("scan_b", type=int, nargs="?", help="ID нового скана (по умолчанию — последний)")
    p_diff.add_argument("--limit", type=int, default=20, help="Сколько файлов показать в каждой категории")
    p_diff.set_defaults(func=cmd_diff)

    p_explore = sub.add_parser("explore", help="Интерактивный просмотр каталога (зайти/выйти из папок)")
    p_explore.add_argument("path", nargs="?", default=None, help="С какой папки начать (по умолчанию — корень скана)")
    p_explore.add_argument("--scan-id", type=int, dest="scan_id")
    p_explore.add_argument("--root", help="Использовать последний скан для этого корня")
    p_explore.set_defaults(func=cmd_explore)

    p_chat = sub.add_parser("chat", help="Диалог с AI-ассистентом поверх каталога дисков")
    p_chat.add_argument(
        "--provider", choices=["anthropic", "openai", "ollama"],
        help="LLM-провайдер (по умолчанию — из конфига или anthropic)",
    )
    p_chat.set_defaults(func=cmd_chat)

    p_help = sub.add_parser("help", help="Полное руководство по всем командам")
    p_help.set_defaults(func=cmd_help)

    p_setup = sub.add_parser("setup", help="Интерактивная настройка: провайдер, API-ключи")
    p_setup.set_defaults(func=cmd_setup)

    p_config = sub.add_parser("config", help="Управление конфигурацией")
    config_sub = p_config.add_subparsers(dest="config_command", required=True)
    p_config_show = config_sub.add_parser("show", help="Показать текущие настройки")
    p_config_show.set_defaults(func=cmd_config_show)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
    return 0
