from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import PowerEvent, Role, User
from ..security import audit, get_current_user, require_roles

router = APIRouter(prefix="/api/power", tags=["power"])

ALLOWED = (Role.OPERATOR, Role.SHIFT_LEAD, Role.DIRECTOR, Role.MECHANIC)


class PowerEventIn(BaseModel):
    action: str  # "start" | "end"
    source: str = "ups"  # grid/ups/generator/none
    is_planned: bool = False
    affected_zones: str = ""
    notes: str = ""


@router.get("/status")
def power_status(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Текущий статус: открытое событие (end_time IS NULL) или сеть."""
    ev = db.execute(
        select(PowerEvent).where(PowerEvent.end_time.is_(None)).order_by(PowerEvent.start_time.desc())
    ).scalars().first()
    if ev:
        return {
            "status": ev.source,
            "since": ev.start_time.isoformat(),
            "event_id": ev.id,
            "is_planned": ev.is_planned,
            "affected_zones": ev.affected_zones,
        }
    return {"status": "grid", "since": None, "event_id": None}


@router.post("/event")
def power_event(
    payload: PowerEventIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ALLOWED)),
):
    ip = request.client.host if request.client else ""
    if payload.action == "start":
        # закрыть незакрытые
        open_ev = db.execute(
            select(PowerEvent).where(PowerEvent.end_time.is_(None))
        ).scalars().all()
        for e in open_ev:
            e.end_time = datetime.utcnow()
        ev = PowerEvent(
            start_time=datetime.utcnow(),
            event_type="outage" if payload.source in ("none", "ups", "generator") else "restore",
            source=payload.source,
            is_planned=payload.is_planned,
            affected_zones=payload.affected_zones,
            notes=payload.notes,
            created_by=user.username,
        )
        db.add(ev)
        db.commit()
        db.refresh(ev)
        audit(db, user, "power_start", "power_event", ev.id, ip, f"source={payload.source}", module="power")
        return {"event_id": ev.id, "status": payload.source}
    else:  # end — восстановление сети
        open_ev = db.execute(
            select(PowerEvent).where(PowerEvent.end_time.is_(None)).order_by(PowerEvent.start_time.desc())
        ).scalars().all()
        for e in open_ev:
            e.end_time = datetime.utcnow()
        db.commit()
        if open_ev:
            audit(db, user, "power_end", "power_event", open_ev[0].id, ip, "restore", module="power")
        return {"status": "grid"}


@router.get("/events")
def power_events(
    days: int = 7,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    since = datetime.utcnow() - timedelta(days=days)
    rows = db.execute(
        select(PowerEvent).where(PowerEvent.start_time >= since).order_by(PowerEvent.start_time.desc())
    ).scalars().all()
    out = []
    daily = {}
    for e in rows:
        end = e.end_time or datetime.utcnow()
        dur = int((end - e.start_time).total_seconds() // 60)
        day = e.start_time.strftime("%Y-%m-%d")
        d = daily.setdefault(day, {"count": 0, "minutes": 0})
        if e.source in ("none", "ups", "generator"):
            d["count"] += 1
            d["minutes"] += dur
        out.append({
            "id": e.id,
            "start": e.start_time.isoformat(),
            "end": e.end_time.isoformat() if e.end_time else None,
            "duration_min": dur,
            "source": e.source,
            "is_planned": e.is_planned,
            "affected_zones": e.affected_zones,
            "notes": e.notes,
        })
    return {"events": out, "daily": daily}
