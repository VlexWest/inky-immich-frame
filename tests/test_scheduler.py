from inky_frame.scheduler import build_scheduler


def test_build_scheduler_one_job_per_time():
    sched = build_scheduler(["07:30", "12:30", "18:00"], lambda: None)
    sched.start()
    try:
        assert len(sched.get_jobs()) == 3
    finally:
        sched.shutdown(wait=False)
