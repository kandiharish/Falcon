"""The background worker: takes queued processing jobs and runs the pipeline.

    uv run python -m app.worker

How a job is claimed safely (several workers can run at once):

    SELECT … FROM processing_jobs WHERE status = 'queued'
    ORDER BY created_at LIMIT 1
    FOR UPDATE SKIP LOCKED          ← lock the row; other workers skip it instead of waiting

Progress is committed after every step, so the browser can show "72% · Metadata extraction".
A worker that crashes leaves its job "running"; jobs without a heartbeat for STALE_AFTER
are put back in the queue (up to MAX_ATTEMPTS).
"""

import logging
import os
import socket
import time
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import Evidence, ProcessingJob
from app.processing.pipeline import StepContext, StepFailed, steps_for
from app.services import audit_service, correlation_service, notification_service
from app.services.evidence_service import audit_object_id

log = logging.getLogger("falcon.worker")

POLL_SECONDS = 1.0
ERROR_BACKOFF_SECONDS = 5
STALE_AFTER = timedelta(minutes=2)
MAX_ATTEMPTS = 3
WORKER_ID = f"{socket.gethostname()}:{os.getpid()}"


def _now() -> datetime:
    return datetime.now(UTC)


def claim_next_job(db: Session) -> ProcessingJob | None:
    job = db.scalar(
        select(ProcessingJob)
        .where(ProcessingJob.status == "queued")
        .order_by(ProcessingJob.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if job is None:
        db.rollback()
        return None
    now = _now()
    job.status = "running"
    job.attempts += 1
    job.worker_id = WORKER_ID
    job.started_at = job.heartbeat_at = now
    job.progress = 0
    job.steps = []
    job.error_message = None
    job.evidence.status = "processing"
    db.commit()
    return job


def run_job(db: Session, job: ProcessingJob) -> None:
    evidence: Evidence = job.evidence
    steps = steps_for(evidence)
    ctx = StepContext(db=db, evidence=evidence)
    results: list[dict] = []

    for index, step in enumerate(steps):
        job.current_step = step.label
        job.progress = round(100 * index / len(steps))
        job.heartbeat_at = _now()
        db.commit()  # make progress visible before the (possibly slow) step runs
        started = time.perf_counter()
        try:
            summary = step.run(ctx)
        except StepFailed as failure:
            results.append(_step_result(step.name, step.label, "failed", str(failure), started))
            _finish(db, job, results, ok=False, message=str(failure))
            return
        except Exception:
            log.exception("Step %s crashed for evidence %s", step.name, evidence.id)
            db.rollback()  # discard the half-done step; then record the failure cleanly
            message = f"{step.label} could not be completed because of an unexpected error."
            results.append(_step_result(step.name, step.label, "failed", message, started))
            _finish(db, job, results, ok=False, message=message)
            return
        results.append(_step_result(step.name, step.label, "done", summary, started))
        job.steps = list(results)

    _finish(db, job, results, ok=True, warnings=ctx.warnings)


def _step_result(name: str, label: str, status: str, summary: str, started: float) -> dict:
    return {
        "name": name,
        "label": label,
        "status": status,
        "summary": summary,
        "duration_ms": round((time.perf_counter() - started) * 1000),
    }


def _finish(
    db: Session,
    job: ProcessingJob,
    results: list[dict],
    *,
    ok: bool,
    message: str | None = None,
    warnings: list[str] | None = None,
) -> None:
    evidence = job.evidence
    job.steps = results
    job.finished_at = _now()
    job.heartbeat_at = job.finished_at
    if ok:
        job.status = "succeeded"
        job.progress = 100
        job.current_step = "Completed"
        evidence.status = "requires_review" if warnings else "processed"
        if warnings:
            job.error_message = " ".join(warnings)
    else:
        job.status = "failed"
        job.current_step = "Failed"
        job.error_message = message
        evidence.status = "requires_review"
    audit_service.record(
        db,
        "evidence.processed" if ok else "evidence.processing_failed",
        actor_email="processing-worker",
        object_type="evidence",
        object_id=audit_object_id(evidence),
        new_state={"status": evidence.status, "steps": [r["name"] for r in results]},
        note=job.error_message,
    )
    notification_service.processing_finished(
        db, evidence, evidence.investigation, ok, job.error_message
    )
    db.commit()
    if ok:  # new facts may connect this evidence to others
        correlation_service.refresh_quietly(db, evidence.investigation_id)


def requeue_stale_jobs(db: Session) -> int:
    """Jobs left 'running' by a crashed worker go back to the queue (or fail after 3 tries)."""
    cutoff = _now() - STALE_AFTER
    requeued = db.execute(
        update(ProcessingJob)
        .where(
            ProcessingJob.status == "running",
            ProcessingJob.heartbeat_at < cutoff,
            ProcessingJob.attempts < MAX_ATTEMPTS,
        )
        .values(status="queued", current_step="Waiting in queue (retry)")
    ).rowcount
    db.execute(
        update(ProcessingJob)
        .where(
            ProcessingJob.status == "running",
            ProcessingJob.heartbeat_at < cutoff,
            ProcessingJob.attempts >= MAX_ATTEMPTS,
        )
        .values(
            status="failed",
            current_step="Failed",
            error_message="Processing stopped repeatedly. Try reprocessing, or check the file.",
            finished_at=_now(),
        )
    )
    db.commit()
    return requeued


def process_one() -> bool:
    """Claim and run one job. Returns False when the queue is empty."""
    with SessionLocal() as db:
        job = claim_next_job(db)
        if job is None:
            return False
        log.info("Processing %s (%s)", job.evidence.reference, job.id)
        run_job(db, job)
        log.info("Finished %s: %s", job.evidence.reference, job.status)
        return True


def process_job_by_id(job_id: uuid.UUID) -> None:
    """Used by tests: run one specific queued job synchronously."""
    with SessionLocal() as db:
        job = db.get(ProcessingJob, job_id)
        if job is None or job.status != "queued":
            return
        job.status = "running"
        job.attempts += 1
        job.started_at = job.heartbeat_at = _now()
        job.evidence.status = "processing"
        db.commit()
        run_job(db, job)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    log.info("FALCON worker %s started. Waiting for evidence to process…", WORKER_ID)
    last_stale_check = 0.0
    try:
        while True:
            try:
                if time.monotonic() - last_stale_check > 30:
                    with SessionLocal() as db:
                        if count := requeue_stale_jobs(db):
                            log.warning("Re-queued %s stale job(s)", count)
                    last_stale_check = time.monotonic()
                if not process_one():
                    time.sleep(POLL_SECONDS)
            except Exception:
                # e.g. the database restarted. Keep the worker alive and try again shortly.
                log.exception("Worker loop error; retrying in %s seconds", ERROR_BACKOFF_SECONDS)
                time.sleep(ERROR_BACKOFF_SECONDS)
    except KeyboardInterrupt:
        log.info("Worker stopped.")


if __name__ == "__main__":
    main()
