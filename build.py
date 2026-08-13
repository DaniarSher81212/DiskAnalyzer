"""Сборка disk-analyzer в один исполняемый файл под текущую ОС.

Кроссплатформенности в смысле одного универсального бинарника не бывает —
PyInstaller собирает только под ту ОС, на которой запущен. Чтобы получить
все три платформы, запустите этот скрипт на Windows, на macOS и на Linux
(руками, в CI или через WSL/VM) — на выходе получится dist/disk-analyzer(.exe)
для каждой из них.
"""
import subprocess
import sys

NAME = "disk-analyzer"


def main() -> int:
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--name", NAME,
        "--console",
        "main.py",
    ]
    print("Запуск:", " ".join(cmd))
    result = subprocess.run(cmd)
    if result.returncode == 0:
        print(f"\nГотово: dist/{NAME}" + (".exe" if sys.platform == "win32" else ""))
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
