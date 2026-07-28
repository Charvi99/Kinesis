"""Celery tasks for the paper-trading ledger — thin triggers around the plain cycle.

Each task owns its own SessionLocal + transaction (commit on success, rollback on
failure); all position/defense math lives in services/ledger/cycle.py. run_cycle only
mutates the session (it never commits), so the commit boundary is here.

run_paper_trading_cycle books the latest bar for one account (engine_id) or every live
account. It is idempotent per (account, close date), so an acks_late redelivery or a
retry is a safe no-op. Per-account try/except (H4 isolation): one account's failure
never blocks the others, and either can be re-run independently.
"""
import logging

from celery.signals import worker_ready

from app.celery_app import celery_app
from app.db.database import SessionLocal
from app.models.ledger import PaperAccount

logger = logging.getLogger(__name__)


def _live_accounts(db, engine_id=None):
    """Accounts to cycle: one by engine_id, else every is_live account."""
    q = db.query(PaperAccount)
    if engine_id is not None:
        q = q.filter(PaperAccount.engine_id == engine_id)
    else:
        q = q.filter(PaperAccount.is_live.is_(True))
    return q.all()


@celery_app.task(bind=True, max_retries=3)
def run_paper_trading_cycle(self, engine_id=None):
    """Book the latest trading bar for one account (engine_id) or every live account.

    Returns {status, engine_id, results:[per-engine summary]}. Per-account errors are
    contained (recorded, rolled back, batch continues); only a structural failure (DB
    down) bubbles up to a retry (countdown 300s) — idempotent, so a retry is safe."""
    from app.services.ledger.cycle import run_cycle

    db = SessionLocal()
    results = []
    try:
        accounts = _live_accounts(db, engine_id)
        if not accounts:
            return {"status": "no_live_accounts", "engine_id": engine_id, "results": []}
        for acct in accounts:
            try:
                r = run_cycle(db, acct)
                db.commit()
                results.append({"engine_id": acct.engine_id, **r})
                logger.info("[ledger] cycle engine=%s -> %s", acct.engine_id, r)
            except Exception as e:                       # one account must not abort the batch
                db.rollback()
                results.append({"engine_id": acct.engine_id, "status": "error",
                                "error": str(e)})
                logger.exception("[ledger] cycle failed engine=%s", acct.engine_id)
        return {"status": "ok", "engine_id": engine_id, "results": results}

    except Exception as e:                               # structural (DB) — retry the batch
        db.rollback()
        logger.exception("[ledger] cycle batch failed: %s", e)
        raise self.retry(exc=e, countdown=300)
    finally:
        db.close()


@celery_app.task
def send_daily_digest(window="PM"):
    """Twice-daily status digest (AM/PM). ALWAYS sends — arriving daily is the
    worker+beat heartbeat. Composed + sent by services/ledger/digest (step 6); until
    that lands, this logs + no-ops (kept on the beat so step 6 needs no scheduler edit).
    NEVER raises: a dead digest best-effort logs and swallows."""
    try:
        from app.services.ledger.digest import compose_and_send
    except ImportError:
        logger.info("[ledger-digest] digest not wired yet (step 6) — skip %s", window)
        return {"status": "not_wired", "window": window}

    db = SessionLocal()
    try:
        return compose_and_send(db, window)
    except Exception as e:
        logger.exception("[ledger-digest] %s digest failed: %s", window, e)
        return {"status": "error", "window": window, "error": str(e)}
    finally:
        db.close()


# ── reboot-safe catch-up ─────────────────────────────────────────────────────
# On worker start, book the latest bar for every live account in case the 19:00 beat
# was missed while the worker was down. Idempotent, so a normal-day double-run (boot +
# beat) is a harmless no-op. The guard ensures a multi-process pool enqueues only once.
_caught_up = {"done": False}


@worker_ready.connect
def _catchup_on_boot(sender=None, **_):
    if _caught_up["done"]:
        return
    _caught_up["done"] = True
    try:
        run_paper_trading_cycle.delay()
        logger.info("[ledger] enqueued boot-time catch-up cycle (all live accounts)")
    except Exception as e:
        logger.warning("[ledger] boot catch-up enqueue failed: %s", e)
