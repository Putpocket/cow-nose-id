from __future__ import annotations

import logging
import os
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path

from app.config import Settings


def start_backup_scheduler(settings: Settings, logger: logging.Logger) -> None:
    if not settings.backup_enabled:
        return

    thread = threading.Thread(target=_backup_loop, args=(settings, logger), daemon=True)
    thread.start()


def _backup_loop(settings: Settings, logger: logging.Logger) -> None:
    while True:
        time.sleep(settings.backup_interval_seconds)
        try:
            run_backup(settings)
        except Exception:
            logger.exception("Scheduled database backup failed.")


def run_backup(settings: Settings) -> Path:
    backup_dir = Path(settings.backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(backup_dir, 0o750)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = backup_dir / f"cow_nose_id-{timestamp}.dump"
    subprocess.run(
        ["pg_dump", "--format=custom", "--file", str(target), settings.database_url],
        check=True,
        capture_output=True,
        text=True,
    )
    os.chmod(target, 0o640)
    return target
