"""Wait until the processing worker has no queued or running jobs (used by CI before E2E tests).

    uv run python -m app.scripts.wait_for_processing [timeout_seconds]

Exits 0 when everything is processed, 1 on timeout or if any job failed.
"""

import sys
import time

from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models import ProcessingJob


def main() -> int:
    timeout = float(sys.argv[1]) if len(sys.argv) > 1 else 300
    deadline = time.monotonic() + timeout
    while True:
        with SessionLocal() as db:
            counts = dict(
                db.execute(
                    select(ProcessingJob.status, func.count()).group_by(ProcessingJob.status)
                ).all()
            )
        busy = counts.get("queued", 0) + counts.get("running", 0)
        if busy == 0:
            print(f"Processing finished: {counts}")
            return 1 if counts.get("failed") else 0
        if time.monotonic() > deadline:
            print(f"Timed out with jobs still busy: {counts}")
            return 1
        time.sleep(2)


if __name__ == "__main__":
    sys.exit(main())
