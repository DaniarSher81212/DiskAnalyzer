"""Хранилище каталога файлов в SQLite."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS scans (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    root        TEXT NOT NULL,
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    file_count  INTEGER DEFAULT 0,
    dir_count   INTEGER DEFAULT 0,
    total_size  INTEGER DEFAULT 0,
    errors      INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS entries (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id   INTEGER NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    path      TEXT NOT NULL,
    parent    TEXT NOT NULL,
    name      TEXT NOT NULL,
    ext       TEXT NOT NULL DEFAULT '',
    size      INTEGER NOT NULL DEFAULT 0,
    is_dir    INTEGER NOT NULL DEFAULT 0,
    mtime     TEXT,
    depth     INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_entries_scan ON entries(scan_id);
CREATE INDEX IF NOT EXISTS idx_entries_parent ON entries(scan_id, parent);
CREATE INDEX IF NOT EXISTS idx_entries_size ON entries(scan_id, size);
CREATE INDEX IF NOT EXISTS idx_entries_ext ON entries(scan_id, ext);
CREATE INDEX IF NOT EXISTS idx_entries_name ON entries(scan_id, name);
"""

if getattr(sys, "frozen", False):
    # Собранный PyInstaller exe распаковывается во временную папку (_MEIxxxxx),
    # которая удаляется после выхода — БД нужно класть рядом с самим exe.
    _APP_DIR = Path(sys.executable).resolve().parent
else:
    _APP_DIR = Path(__file__).resolve().parent.parent

DEFAULT_DB_PATH = _APP_DIR / "disk_catalog.db"


def connect(db_path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def latest_scan_id(conn: sqlite3.Connection, root: str | None = None) -> int | None:
    if root:
        row = conn.execute(
            "SELECT id FROM scans WHERE root = ? AND finished_at IS NOT NULL "
            "ORDER BY id DESC LIMIT 1",
            (root,),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT id FROM scans WHERE finished_at IS NOT NULL ORDER BY id DESC LIMIT 1"
        ).fetchone()
    return row[0] if row else None
