import argparse
import logging

from app.services.task_runner_service import run_fallback_sync_scheduler_task, run_watch_renewals_scheduler_task

logger = logging.getLogger(__name__)


def run_fallback_sync() -> int:
    event_ids = run_fallback_sync_scheduler_task()
    logger.info("Scheduled fallback sync queued", extra={"event_name": "scheduler.fallback_sync", "count": len(event_ids)})
    return len(event_ids)


def run_watch_renewals() -> int:
    connection_ids = run_watch_renewals_scheduler_task()
    logger.info(
        "Scheduled watch renewals queued",
        extra={"event_name": "scheduler.watch_renewal", "count": len(connection_ids)},
    )
    return len(connection_ids)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run scheduled support triage jobs")
    parser.add_argument("job", choices=["fallback-sync", "watch-renewals"])
    args = parser.parse_args()

    if args.job == "fallback-sync":
        run_fallback_sync()
    elif args.job == "watch-renewals":
        run_watch_renewals()


if __name__ == "__main__":
    main()