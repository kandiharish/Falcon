"""Rebuild the DEVELOPMENT database and evidence storage from scratch with demo data.

    uv run python -m app.scripts.reset_demo_data --yes

Deletes everything in the development database and storage/ (originals included), then runs
all migrations and the demo seeds. Refuses to run outside development or without --yes.
Use it after changing demo data, or to return to a clean, known state.
"""

import os
import shutil
import stat
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config

from app.core.config import REPO_ROOT, get_settings
from app.scripts import (
    seed_demo_evidence,
    seed_demo_investigations,
    seed_demo_users,
    seed_demo_work,
)


def _make_writable(func, path, _exc) -> None:
    os.chmod(path, stat.S_IWRITE | stat.S_IREAD)  # originals are read-only on purpose
    func(path)


def main() -> int:
    settings = get_settings()
    if settings.environment != "development" or "--yes" not in sys.argv:
        print("This deletes ALL development data. Run with --yes (development only).")
        return 1

    alembic = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    print("Dropping all tables…")
    command.downgrade(alembic, "base")
    print("Recreating tables…")
    command.upgrade(alembic, "head")

    storage = Path(settings.storage_dir).resolve()
    if storage.is_relative_to(REPO_ROOT) and storage.exists():
        print(f"Clearing {storage}…")
        shutil.rmtree(storage, onexc=_make_writable)

    for seed in (seed_demo_users, seed_demo_investigations, seed_demo_evidence, seed_demo_work):
        if seed.main() != 0:
            return 1
    print("Done. The worker will process the demo evidence within a few seconds.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
