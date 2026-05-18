from __future__ import annotations

import argparse
from pathlib import Path
import sys

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import get_settings


def main() -> int:
    parser = argparse.ArgumentParser(description="Find or delete uploaded files not referenced by cow_images.")
    parser.add_argument("--delete", action="store_true", help="Delete orphaned files. Defaults to dry-run.")
    args = parser.parse_args()

    settings = get_settings()
    upload_dir = Path(settings.upload_dir).resolve()
    if not upload_dir.exists():
        print(f"Upload directory does not exist: {upload_dir}")
        return 0

    referenced_paths = fetch_referenced_upload_paths(settings.database_url)
    uploaded_files = {
        path.resolve()
        for path in upload_dir.iterdir()
        if path.is_file()
    }
    orphaned_files = sorted(uploaded_files - referenced_paths)

    if not orphaned_files:
        print("No orphaned uploaded files found.")
        return 0

    action = "Deleting" if args.delete else "Dry-run"
    print(f"{action}: {len(orphaned_files)} orphaned uploaded file(s)")
    for path in orphaned_files:
        if upload_dir not in path.parents:
            print(f"Skipped outside upload dir: {path}")
            continue
        print(path)
        if args.delete:
            path.unlink()
    return 0


def fetch_referenced_upload_paths(database_url: str) -> set[Path]:
    pool = ConnectionPool(database_url, kwargs={"row_factory": dict_row}, min_size=0, max_size=10)
    try:
        with pool.connection() as conn:
            rows = conn.execute("SELECT image_path FROM cow_images").fetchall()
    finally:
        pool.close()
    return {Path(row["image_path"]).resolve() for row in rows}


if __name__ == "__main__":
    raise SystemExit(main())
