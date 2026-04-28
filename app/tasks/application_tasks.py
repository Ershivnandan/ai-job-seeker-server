import asyncio

from app.tasks.celery_app import celery_app
from app.agents.orchestrator import apply_to_single_job
from app.utils.logger import get_logger

logger = get_logger(__name__)


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(
    name="app.tasks.application_tasks.apply_to_job",
    bind=True,
    max_retries=3,
    default_retry_delay=300,
)
def apply_to_job(self, application_id: str):
    """Apply to a single job. Retries with exponential backoff on failure."""
    logger.info(f"Task: applying to job for application {application_id}")
    try:
        result = _run_async(apply_to_single_job(application_id))

        if not result["success"] and result.get("retryable"):
            countdown = 300 * (2 ** self.request.retries)
            logger.info(
                f"Retrying application {application_id} in {countdown}s "
                f"(attempt {self.request.retries + 1}/{self.max_retries})"
            )
            self.retry(countdown=countdown)

        return result

    except apply_to_job.MaxRetriesExceededError:
        logger.error(f"Max retries exceeded for application {application_id}")
        return {"success": False, "message": "Max retries exceeded"}
    except Exception as exc:
        logger.error(f"Apply task failed for {application_id}: {exc}")
        countdown = 300 * (2 ** self.request.retries)
        self.retry(exc=exc, countdown=countdown)


@celery_app.task(name="app.tasks.application_tasks.batch_apply", bind=True)
def batch_apply(self, application_ids: list[str]):
    """Queue apply tasks for multiple applications with staggered delays."""
    logger.info(f"Task: batch applying {len(application_ids)} applications")
    for i, app_id in enumerate(application_ids):
        delay_seconds = i * 120
        apply_to_job.apply_async(args=[app_id], countdown=delay_seconds)
        logger.info(f"Queued application {app_id} with {delay_seconds}s delay")
