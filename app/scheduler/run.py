"""Scheduler entry point — run with: python -m app.scheduler.run"""

import logging
import sys
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings
from app.database import init_db
from app.scheduler.jobs import run_collection

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("Initializing database…")
    init_db()

    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(
        run_collection,
        trigger=IntervalTrigger(hours=settings.COLLECTION_INTERVAL_HOURS),
        next_run_time=datetime.utcnow(),  # Run immediately on startup
        id="trend_collection",
        name="Trend Collection",
        misfire_grace_time=300,
        coalesce=True,
    )

    logger.info(
        "Scheduler started — collecting every %dh. Press Ctrl+C to stop.",
        settings.COLLECTION_INTERVAL_HOURS,
    )
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")
        scheduler.shutdown()


if __name__ == "__main__":
    main()
