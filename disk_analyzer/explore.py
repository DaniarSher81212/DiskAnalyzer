"""Интерактивный просмотр каталога: заходим в папки, поднимаемся наверх."""
from __future__ import annotations

import sqlite3

from . import sizes

PAGE_SIZE = 25


def _human(n: float) -> str:
    for unit in ("Б", "КБ", "МБ", "ГБ", "ТБ", "ПБ"):
        if abs(n) < 1024:
            return f"{n:,.1f} {unit}".replace(",", " ")
        n /= 1024
    return f"{n:,.1f} ЭБ".replace(",", " ")


def _entry_info(conn: sqlite3.Connection, scan_id: int, path: str) -> tuple[int, str] | None:
    row = conn.execute(
        "SELECT size, parent FROM entries WHERE scan_id = ? AND path = ? AND is_dir = 1",
        (scan_id, path),
    ).fetchone()
    return tuple(row) if row else None


def run(
    conn: sqlite3.Connection,
    scan_id: int,
    start_path: str,
    input_fn=input,
    print_fn=print,
) -> None:
    root_row = conn.execute("SELECT root FROM scans WHERE id = ?", (scan_id,)).fetchone()
    if root_row is None:
        print_fn(f"Скан {scan_id} не найден.")
        return
    scan_root = root_row[0]

    info = _entry_info(conn, scan_id, start_path)
    if info is None:
        print_fn(f"Папка не найдена в каталоге: {start_path}")
        return

    current = start_path
    offset = 0

    while True:
        size, parent = _entry_info(conn, scan_id, current)
        all_children = sizes.children(conn, scan_id, current)
        total = len(all_children)
        page = all_children[offset: offset + PAGE_SIZE]

        print_fn(f"\n{current}  ({_human(size)}, {total} элементов)")
        print_fn("-" * 60)
        for i, (path, item_size, is_dir) in enumerate(page, start=offset + 1):
            name = path[len(current):].lstrip("\\/") or path
            kind = "DIR " if is_dir else "FILE"
            print_fn(f"{i:>4}. {kind} {_human(item_size):>10}  {name}")

        if offset + PAGE_SIZE < total:
            print_fn(f"   ... ещё {total - offset - PAGE_SIZE} (n — следующая страница)")

        can_go_up = current != scan_root
        prompt_bits = ["номер — зайти в папку"]
        if can_go_up:
            prompt_bits.append("u — вверх")
        if offset > 0:
            prompt_bits.append("p — назад")
        if offset + PAGE_SIZE < total:
            prompt_bits.append("n — далее")
        prompt_bits.append("q — выход")
        print_fn("(" + ", ".join(prompt_bits) + ")")

        try:
            choice = input_fn("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print_fn("")
            return

        if choice == "" or choice.lower() == "q":
            return
        if choice.lower() == "u":
            if can_go_up:
                current = parent
                offset = 0
            else:
                print_fn("Уже в корне скана.")
            continue
        if choice.lower() == "n":
            if offset + PAGE_SIZE < total:
                offset += PAGE_SIZE
            continue
        if choice.lower() == "p":
            offset = max(0, offset - PAGE_SIZE)
            continue

        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < total:
                path, item_size, is_dir = all_children[idx]
                if is_dir:
                    current = path
                    offset = 0
                else:
                    mtime_row = conn.execute(
                        "SELECT mtime FROM entries WHERE scan_id = ? AND path = ?",
                        (scan_id, path),
                    ).fetchone()
                    mtime = mtime_row[0] if mtime_row else "?"
                    print_fn(f"Файл: {path}\nРазмер: {_human(item_size)}\nИзменён: {mtime}")
            else:
                print_fn("Нет такого номера на этой странице.")
            continue

        print_fn("Не понял команду.")
