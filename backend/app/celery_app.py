"""Kinesis Celery app — Redis broker/backend + beat schedule for the ledger.

Ports StockAnalyzer's proven wiring (the hard-won lessons: queue routing so a .delay()
doesn't silently die on the unconsumed default 'celery' queue; acks_late + an idempotent
cycle so redelivery is safe; `kwargs` as a TOP-LEVEL beat key, NOT nested in `options`),
trimmed to Kinesis: one queue (maintenance), one combined worker+beat container.

The cycle core is a plain function (services/ledger/cycle.py); Celery tasks are thin
triggers that own the DB session + transaction. Beat runs in America/New_York: the
paper-trading cycle daily at 19:00 ET (after the close) for every live account, plus a
twice-daily digest (AM pre-market / PM post-cycle). The digest arriving daily IS the
worker+beat heartbeat — an in-stack task can't detect its own scheduler dying.
"""
import os

from celery import Celery
from celery.schedules import crontab

celery_app = Celery(
    'kinesis',
    broker=os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/1'),
    include=['app.tasks.ledger_tasks'],
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='America/New_York',
    enable_utc=True,

    # ledger -> maintenance. WITHOUT this a manual .delay() lands in the unconsumed
    # default 'celery' queue and silently never runs (the StockAnalyzer trap).
    task_routes={'app.tasks.ledger_tasks.*': {'queue': 'maintenance'}},

    worker_prefetch_multiplier=1,        # one task at a time (the cycle is sequential)
    worker_max_tasks_per_child=100,      # recycle to bound memory

    task_acks_late=True,                 # redelivery is safe — the cycle is idempotent
    task_reject_on_worker_lost=True,     # re-queue if the worker dies mid-task

    # Ledger cycles are ~1-2s/engine; 10-min cap catches a truly stuck task.
    task_soft_time_limit=600,
    task_time_limit=660,

    task_default_retry_delay=60,
    task_max_retries=3,

    result_expires=3600,
)

celery_app.conf.beat_schedule = {
    # Daily cycle for every live account, 19:00 ET (after the day's settled daily bar).
    # engine_id omitted => all live accounts (multi-engine live A/B in one beat entry).
    'paper-trading-cycle-daily': {
        'task': 'app.tasks.ledger_tasks.run_paper_trading_cycle',
        'schedule': crontab(minute=0, hour=19),
        'options': {'queue': 'maintenance'},
    },
    # Twice-daily digest. crontab hour is in the beat TZ (America/New_York); defaults
    # 2 & 14 ET => 08:30 & 20:30 in Prague (CEST, a constant 6h ahead of ET). Override
    # DIGEST_AM_HOUR / DIGEST_PM_HOUR (ET-clock hours) if your local TZ differs.
    'paper-trading-digest-am': {
        'task': 'app.tasks.ledger_tasks.send_daily_digest',
        'schedule': crontab(minute=30, hour=int(os.getenv('DIGEST_AM_HOUR', '2'))),
        'kwargs': {'window': 'AM'},     # top-level beat key, NOT inside options
        'options': {'queue': 'maintenance'},
    },
    'paper-trading-digest-pm': {
        'task': 'app.tasks.ledger_tasks.send_daily_digest',
        'schedule': crontab(minute=30, hour=int(os.getenv('DIGEST_PM_HOUR', '14'))),
        'kwargs': {'window': 'PM'},
        'options': {'queue': 'maintenance'},
    },
}


# ── logging signals ──────────────────────────────────────────────────────────
from celery.signals import task_failure, task_postrun, task_prerun, task_retry


@task_prerun.connect
def _prerun(sender=None, task_id=None, task=None, **_):
    print(f"[TASK START] {task.name} [{task_id}]")


@task_postrun.connect
def _postrun(sender=None, task_id=None, task=None, retval=None, **_):
    print(f"[TASK DONE] {task.name} [{task_id}]")


@task_failure.connect
def _failure(sender=None, task_id=None, exception=None, **_):
    print(f"[TASK FAIL] {sender.name} [{task_id}] - {exception}")


@task_retry.connect
def _retry(sender=None, task_id=None, reason=None, **_):
    print(f"[TASK RETRY] {sender.name} [{task_id}] - {reason}")
