"""
Scheduler service for background jobs.

This service manages scheduled background tasks using APScheduler.
Add your custom jobs in the _setup_jobs method.
"""
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from app.config import settings
from app.core.logging import get_logger


logger = get_logger(__name__)


class SchedulerService:
    """
    Service for managing scheduled background tasks.

    Usage:
        scheduler = get_scheduler_service()
        await scheduler.start()
        # ... app running ...
        await scheduler.shutdown()
    """

    _instance: Optional["SchedulerService"] = None

    def __init__(self):
        """Initialize the scheduler service."""
        self._scheduler: Optional[AsyncIOScheduler] = None
        self._timezone = pytz.timezone(settings.scheduler_timezone)

    @property
    def scheduler(self) -> Optional[AsyncIOScheduler]:
        """Get the APScheduler instance."""
        return self._scheduler

    async def start(self) -> None:
        """Start the scheduler and setup jobs."""
        if not settings.scheduler_enabled:
            logger.info("Scheduler is disabled")
            return

        if self._scheduler is not None:
            logger.warning("Scheduler already running")
            return

        logger.info("Starting scheduler service...")

        self._scheduler = AsyncIOScheduler(timezone=self._timezone)
        self._setup_jobs()
        self._scheduler.start()

        logger.info("Scheduler service started successfully")

    async def shutdown(self) -> None:
        """Shutdown the scheduler gracefully."""
        if self._scheduler is None:
            return

        logger.info("Shutting down scheduler service...")
        self._scheduler.shutdown(wait=True)
        self._scheduler = None
        logger.info("Scheduler service stopped")

    def _setup_jobs(self) -> None:
        """
        Setup scheduled jobs.

        Add your custom jobs here. Example:

            self._scheduler.add_job(
                self._my_job,
                CronTrigger(hour=0, minute=5, timezone=self._timezone),
                id="my_job",
                name="My Custom Job",
                replace_existing=True
            )
        """
        # Example placeholder job (disabled by default)
        # Uncomment and customize as needed:
        #
        # self._scheduler.add_job(
        #     self._example_job,
        #     CronTrigger(hour=0, minute=0, timezone=self._timezone),
        #     id="example_job",
        #     name="Example Daily Job",
        #     replace_existing=True
        # )

        logger.info("Scheduler jobs configured (no jobs defined yet)")

    async def _example_job(self) -> None:
        """Example scheduled job - customize or remove."""
        logger.info("Example job executed")

    def get_status(self) -> dict:
        """Get scheduler status and job information."""
        if self._scheduler is None:
            return {"status": "stopped", "jobs": []}

        jobs = []
        for job in self._scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger)
            })

        return {
            "status": "running",
            "timezone": str(self._timezone),
            "jobs": jobs
        }

    async def run_job_manually(self, job_id: str) -> bool:
        """
        Run a job manually by its ID.

        Args:
            job_id: The job identifier

        Returns:
            True if job was triggered, False if job not found
        """
        if self._scheduler is None:
            return False

        job = self._scheduler.get_job(job_id)
        if job is None:
            return False

        job.modify(next_run_time=None)
        self._scheduler.wakeup()
        return True


# Singleton instance
_scheduler_service: Optional[SchedulerService] = None


def get_scheduler_service() -> SchedulerService:
    """Get or create the scheduler service singleton."""
    global _scheduler_service
    if _scheduler_service is None:
        _scheduler_service = SchedulerService()
    return _scheduler_service
