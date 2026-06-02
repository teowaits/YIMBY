"""In-memory job store for pipeline runs."""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

JobStatus = Literal["queued", "running", "done", "error"]


@dataclass
class Job:
    id: str
    status: JobStatus = "queued"
    logs: list[str] = field(default_factory=list)
    result: dict[str, Any] | None = None
    error: str | None = None


_lock = threading.Lock()
_jobs: dict[str, Job] = {}


def create_job() -> Job:
    job = Job(id=uuid.uuid4().hex[:12])
    with _lock:
        _jobs[job.id] = job
    return job


def get_job(job_id: str) -> Job | None:
    with _lock:
        return _jobs.get(job_id)


def append_log(job_id: str, message: str) -> None:
    with _lock:
        job = _jobs.get(job_id)
        if job:
            job.logs.append(message)
            if len(job.logs) > 200:
                job.logs = job.logs[-200:]


def set_status(
    job_id: str,
    status: JobStatus,
    *,
    result: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    with _lock:
        job = _jobs.get(job_id)
        if not job:
            return
        job.status = status
        if result is not None:
            job.result = result
        if error is not None:
            job.error = error
