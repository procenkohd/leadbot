"""
Где лежит файл базы (leads.db).

По умолчанию — рядом с кодом: локальный запуск ничего не замечает. На
хостинге код при каждом деплое перезаписывается из репозитория, поэтому там
задаётся DATA_DIR, указывающий на постоянный том (на bothost.ru это
/app/data) — и база не обнуляется при каждом пуше.
"""

import os
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR") or Path(__file__).parent)


def data_path(filename: str) -> Path:
    """Путь к файлу состояния (каталог создаётся, если его ещё нет)."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR / filename
