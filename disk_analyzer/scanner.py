"""Обход файловой системы и запись каталога в БД."""
from __future__ import annotations

import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

BATCH_SIZE = 2000


def _ext(name: str) -> str:
    dot = name.rfind(".")
    return name[dot:].lower() if dot > 0 else ""


class _Frame:
    """Один уровень обхода: директория + её ещё не обработанные дочерние элементы."""

    __slots__ = ("path", "depth", "children", "size")

    def __init__(self, path: str, depth: int):
        self.path = path
        self.depth = depth
        self.children: list[os.DirEntry] = []
        self.size = 0


def scan(root: str, conn: sqlite3.Connection, follow_reparse: bool = False, one_filesystem: bool = False, on_progress=None) -> int:
    """Сканирует `root` и сохраняет каталог в БД. Возвращает scan_id."""
    root = str(Path(root).resolve())
    started_at = datetime.now(timezone.utc).isoformat()
    cur = conn.execute(
        "INSERT INTO scans (root, started_at) VALUES (?, ?)", (root, started_at)
    )
    scan_id = cur.lastrowid

    file_count = 0
    dir_count = 0
    total_size = 0
    error_count = 0
    batch: list[tuple] = []

    def flush():
        nonlocal batch
        if batch:
            conn.executemany(
                "INSERT INTO entries (scan_id, path, parent, name, ext, size, "
                "is_dir, mtime, depth) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                batch,
            )
            batch = []

    try:
        root_entry_stat = os.stat(root)
        root_dev = root_entry_stat.st_dev
    except OSError as exc:
        print(f"Не удалось открыть корень сканирования: {exc}", file=sys.stderr)
        conn.execute("UPDATE scans SET finished_at = ?, errors = 1 WHERE id = ?",
                     (datetime.now(timezone.utc).isoformat(), scan_id))
        conn.commit()
        return scan_id

    root_frame = _Frame(root, 0)
    stack = [root_frame]
    dir_count += 1
    seen_dirs: set[str] = set()

    while stack:
        frame = stack[-1]
        if frame.path not in seen_dirs:
            seen_dirs.add(frame.path)
            try:
                with os.scandir(frame.path) as it:
                    frame.children = list(it)
            except OSError as exc:
                error_count += 1
                print(f"Пропуск (нет доступа): {frame.path} ({exc})", file=sys.stderr)
                frame.children = []

        if frame.children:
            entry = frame.children.pop()
            try:
                is_symlink_or_junction = entry.is_symlink() or (
                    os.name == "nt" and bool(entry.stat(follow_symlinks=False).st_file_attributes
                                               & 0x400)  # FILE_ATTRIBUTE_REPARSE_POINT
                )
            except OSError:
                is_symlink_or_junction = False

            try:
                if entry.is_dir(follow_symlinks=False):
                    if is_symlink_or_junction and not follow_reparse:
                        continue
                    if one_filesystem and entry.stat(follow_symlinks=False).st_dev != root_dev:
                        continue
                    dir_count += 1
                    stack.append(_Frame(entry.path, frame.depth + 1))
                else:
                    st = entry.stat(follow_symlinks=False)
                    size = st.st_size
                    mtime = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat()
                    batch.append((
                        scan_id, entry.path, frame.path, entry.name,
                        _ext(entry.name), size, 0, mtime, frame.depth + 1,
                    ))
                    frame.size += size
                    file_count += 1
                    total_size += size
                    if on_progress and file_count % 1000 == 0:
                        on_progress(file_count, dir_count, total_size)
                    if len(batch) >= BATCH_SIZE:
                        flush()
            except OSError as exc:
                error_count += 1
                print(f"Пропуск (ошибка чтения): {entry.path} ({exc})", file=sys.stderr)
            continue

        # Директория полностью обработана: записываем её и складываем размер родителю
        mtime = None
        try:
            mtime = datetime.fromtimestamp(
                os.stat(frame.path).st_mtime, tz=timezone.utc
            ).isoformat()
        except OSError:
            pass
        name = os.path.basename(frame.path) or frame.path
        # Для корня скана dirname() на Windows возвращает саму букву диска
        # (dirname('C:\\') == 'C:\\'), что дало бы записи саму себя в родители.
        parent = "" if frame.path == root else os.path.dirname(frame.path)
        batch.append((
            scan_id, frame.path, parent, name, "", frame.size, 1, mtime, frame.depth,
        ))
        if len(batch) >= BATCH_SIZE:
            flush()
        stack.pop()
        if stack:
            stack[-1].size += frame.size

    flush()
    conn.execute(
        "UPDATE scans SET finished_at = ?, file_count = ?, dir_count = ?, "
        "total_size = ?, errors = ? WHERE id = ?",
        (datetime.now(timezone.utc).isoformat(), file_count, dir_count,
         total_size, error_count, scan_id),
    )
    conn.commit()
    return scan_id
