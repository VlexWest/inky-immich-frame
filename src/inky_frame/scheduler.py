from typing import Callable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger


def build_scheduler(
    refresh_times: list[str], job: Callable[[], None]
) -> BackgroundScheduler:
    sched = BackgroundScheduler()
    for t in refresh_times:
        hour, minute = t.split(":")
        sched.add_job(job, CronTrigger(hour=int(hour), minute=int(minute)))
    return sched
