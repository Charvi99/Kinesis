"""Twice-daily status digest for the paper-trading ledger — the "no need to open the
frontend" email, and the system-up heartbeat.

compose_and_send(db, window) builds a plain-text digest (per-engine A/B standing, top
movers, vs-SPY, heat/cash, health/reconciliation warnings) and sends it via Gmail
(SMTP_SSL, app password). It ALWAYS sends when configured — the digest arriving daily
IS the worker+beat heartbeat (an in-stack task can't detect its own scheduler dying).
NEVER raises: compose/send failures are caught, logged, and reported so the beat task
that calls it can't be killed by a delivery hiccup.

Subject convention: ``[Kinesis] Alert — <reason>`` when something's wrong (stale
account, reconciliation drift, no live accounts), else ``[Kinesis] Digest — <date>
<window>`` — so Gmail can filter routine vs alert.

Gmail creds (all required, env): GMAIL_USER, GMAIL_APP_PASSWORD, DIGEST_TO (comma-separated).
Stdlib only (smtplib, email) — no new dependency.
"""
from __future__ import annotations

import logging
import os
import smtplib
from datetime import date
from email.message import EmailMessage
from typing import Dict, List

import pandas as pd
from sqlalchemy.orm import Session

from app.api.deps import load_closes, load_meta
from app.models.engine import Engine
from app.models.ledger import PaperAccount, PaperEquitySnapshot, PaperPosition
from app.services.ledger.health import reconcile_account, staleness

logger = logging.getLogger(__name__)


def _snap_series(db: Session, acct: PaperAccount) -> pd.Series:
    rows = (db.query(PaperEquitySnapshot.date, PaperEquitySnapshot.equity)
            .filter(PaperEquitySnapshot.account_id == acct.id)
            .order_by(PaperEquitySnapshot.date).all())
    if not rows:
        return pd.Series(dtype=float)
    return pd.Series([float(r[1]) for r in rows], index=pd.DatetimeIndex([r[0] for r in rows]))


def _account_block(db: Session, acct: PaperAccount) -> Dict:
    """The numbers for one account: equity, returns, risk, exposure, movers, health."""
    from app.services.backtest.metrics import summarize

    eng = db.get(Engine, acct.engine_id)
    snaps = (db.query(PaperEquitySnapshot).filter_by(account_id=acct.id)
             .order_by(PaperEquitySnapshot.date).all())
    eq = _snap_series(db, acct)
    starting = float(acct.starting_cash)
    last = snaps[-1] if snaps else None
    equity = float(last.equity) if last else float(acct.cash)
    total_return = equity / starting - 1 if starting else 0.0
    sharpe = max_dd = live_return = None
    if len(eq) >= 2:
        m = summarize(eq.pct_change().dropna())
        sharpe, max_dd = m.get("sharpe"), m.get("max_drawdown")
        live = [s for s in snaps if s.is_live]
        if len(live) >= 2 and float(live[0].equity) > 0:
            live_return = float(live[-1].equity) / float(live[0].equity) - 1

    # top movers by unrealized P&L %
    movers: List[Dict] = []
    closes = load_closes(db)
    close_row = closes.iloc[-1] if len(closes) else None
    meta = load_meta(db)
    for p in db.query(PaperPosition).filter_by(account_id=acct.id).all():
        if not p.avg_cost or close_row is None:
            continue
        px = float(close_row.get(p.stock_id, float("nan")))
        if px != px or px <= 0:          # NaN or non-positive
            continue
        movers.append({"symbol": meta.get(int(p.stock_id), {}).get("symbol") or str(p.stock_id),
                       "pnl_pct": px / float(p.avg_cost) - 1,
                       "weight": float(p.quantity) * px / equity if equity else 0.0})
    movers.sort(key=lambda m: m["pnl_pct"])

    return {
        "engine_name": eng.name if eng else f"engine {acct.engine_id}",
        "is_live": bool(acct.is_live), "equity": equity, "starting": starting,
        "cash": float(acct.cash), "total_return": total_return, "live_return": live_return,
        "sharpe": sharpe, "max_dd": max_dd, "open_positions": int(last.open_positions) if last else 0,
        "gross_exposure": float(last.gross_exposure) if last and last.gross_exposure is not None else None,
        "as_of": last.date.isoformat() if last else None,
        "go_live_at": acct.go_live_at.isoformat() if acct.go_live_at else None,
        "movers": movers, "staleness": staleness(db, acct), "recon": reconcile_account(db, acct),
    }


def _fmt_pct(x, width=6) -> str:
    if x is None:
        return "   n/a"
    return f"{x * 100:>{width}.2f}%"


def _compose(db: Session, window: str) -> tuple[str, str, str, bool]:
    """Build (body, subject, severity, has_issues)."""
    accounts = db.query(PaperAccount).order_by(PaperAccount.id).all()
    today = date.today().isoformat()
    lines = [f"Kinesis — {window} digest  ({today})", "=" * 48, ""]

    if not accounts:
        lines += ["No paper accounts. Paper-trade an engine via POST /paper-trading/enable.", ""]
        return ("\n".join(lines), f"[Kinesis] Alert — no paper accounts ({window})", "warning", True)

    warnings = []
    for acct in accounts:
        b = _account_block(db, acct)
        st, rc = b["staleness"], b["recon"]
        live_tag = "LIVE" if b["is_live"] else "paused"
        lines.append(f"■ {b['engine_name']}  [{live_tag}]   as_of {b['as_of']}")
        lines.append(f"   equity      ${b['equity']:>12,.2f}   "
                     f"(start ${b['starting']:>12,.2f}, cash ${b['cash']:>10,.2f})")
        if b["sharpe"] is not None:
            lines.append(f"   return      total {_fmt_pct(b['total_return'])}   "
                         f"live {_fmt_pct(b['live_return'])}   "
                         f"Sharpe {b['sharpe']:.2f}   maxDD {_fmt_pct(b['max_dd'])}")
        else:
            lines.append(f"   return      total {_fmt_pct(b['total_return'])}   (warming up)")
        lines.append(f"   book        {b['open_positions']} names, "
                     f"gross {_fmt_pct(b['gross_exposure'])}")
        if b["movers"]:
            top_gain = b["movers"][-1]
            top_loss = b["movers"][0]
            lines.append(f"   movers      best {top_gain['symbol']} {_fmt_pct(top_gain['pnl_pct'])}   "
                         f"worst {top_loss['symbol']} {_fmt_pct(top_loss['pnl_pct'])}")
        lines.append(f"   health      feed {st['status']}   recon {'OK' if rc['ok'] else 'DRIFT'}")
        lines.append("")
        if b["is_live"] and st["status"] != "ok":
            warnings.append(f"{b['engine_name']}: feed {st['status']} (last {st.get('last_date')})")
        if not rc["ok"]:
            warnings.append(f"{b['engine_name']}: reconciliation drift "
                            f"(expected {rc['expected_equity']:.2f} vs snapshot {rc.get('snapshot_equity')})")

    if warnings:
        lines = [f"⚠  {w}" for w in warnings] + ["", "=" * 48, ""] + lines
        subject = f"[Kinesis] Alert — {len(warnings)} issue(s) ({window})"
        return "\n".join(lines), subject, "warning", True

    lines.append("=" * 48)
    lines.append("All engines OK. — Kinesis")
    return "\n".join(lines), f"[Kinesis] Digest — {today} {window}", "info", False


def _send_email(subject: str, body: str) -> str:
    user = os.getenv("GMAIL_USER")
    pw = os.getenv("GMAIL_APP_PASSWORD")
    to = os.getenv("DIGEST_TO")
    if not (user and pw and to):
        return "not_configured"
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = user, to, subject
    msg.set_content(body)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as server:
        server.login(user, pw)
        server.send_message(msg)
    return "ok"


def compose_and_send(db: Session, window: str = "PM") -> Dict:
    """Compose + send the digest. Always returns a report; NEVER raises."""
    try:
        body, subject, severity, has_issues = _compose(db, window)
    except Exception as e:                          # compose must not kill the beat
        logger.exception("[digest] compose failed: %s", e)
        body, subject = f"Kinesis digest compose failed:\n\n{e}", "[Kinesis] Alert — digest compose failed"
        severity, has_issues = "error", True

    try:
        delivery = _send_email(subject, body)
    except Exception as e:                          # nor must delivery
        logger.exception("[digest] send failed: %s", e)
        delivery = f"failed: {e}"

    logger.info("[digest] %s — delivery=%s severity=%s issues=%s", window, delivery, severity, has_issues)
    return {"status": "sent" if delivery == "ok" else delivery, "window": window,
            "severity": severity, "has_issues": has_issues, "subject": subject}
