from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import RouteSegment, Role, Shipment, TransportUnit, User
from ..security import audit, get_current_user, require_roles

router = APIRouter(prefix="/api/logistics", tags=["logistics"])

ALLOWED = (Role.LOGISTICIAN, Role.SHIFT_LEAD, Role.DIRECTOR)

PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


class ShipmentIn(BaseModel):
    ship_type: str = "in"
    priority: str = "medium"
    contents: str = ""
    origin: str = ""
    destination: str = ""
    transport_type: str = "truck"
    status: str = "planned"
    planned_eta: datetime | None = None
    notes: str = ""


class DelayIn(BaseModel):
    delay_reason: str
    delay_minutes: int = 0
    notes: str = ""


class SegmentIn(BaseModel):
    status: str
    blocked_reason: str = ""


class TransportIn(BaseModel):
    unit_type: str = "truck"
    capacity_kg: int = 0
    status: str = "available"
    current_location: str = ""
    notes: str = ""


def _ship_dict(s: Shipment):
    return {
        "id": s.id, "ship_type": s.ship_type, "priority": s.priority, "contents": s.contents,
        "origin": s.origin, "destination": s.destination, "transport_type": s.transport_type,
        "status": s.status, "planned_eta": s.planned_eta.isoformat() if s.planned_eta else None,
        "actual_arrival": s.actual_arrival.isoformat() if s.actual_arrival else None,
        "delay_reason": s.delay_reason, "delay_minutes": s.delay_minutes,
        "notes": s.notes, "created_by": s.created_by,
    }


# ---- Shipments ----

@router.get("/shipments")
def list_shipments(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.execute(select(Shipment)).scalars().all()
    rows.sort(key=lambda s: (PRIORITY_ORDER.get(s.priority, 9), s.id))
    return [_ship_dict(s) for s in rows]


@router.post("/shipments")
def create_shipment(payload: ShipmentIn, request: Request, db: Session = Depends(get_db), user: User = Depends(require_roles(*ALLOWED))):
    s = Shipment(**payload.model_dump(), created_by=user.username)
    db.add(s)
    db.commit()
    db.refresh(s)
    audit(db, user, "create", "shipment", s.id, request.client.host if request.client else "", f"{s.contents}", module="logistics")
    return {"id": s.id}


@router.put("/shipments/{sid}")
def update_shipment(sid: int, payload: ShipmentIn, request: Request, db: Session = Depends(get_db), user: User = Depends(require_roles(*ALLOWED))):
    s = db.get(Shipment, sid)
    if not s:
        raise HTTPException(404, "Поставка не найдена")
    for k, v in payload.model_dump().items():
        setattr(s, k, v)
    if payload.status == "delivered" and not s.actual_arrival:
        s.actual_arrival = datetime.utcnow()
    db.commit()
    audit(db, user, "update", "shipment", s.id, request.client.host if request.client else "", module="logistics")
    return {"ok": True}


@router.post("/shipments/{sid}/delay")
def mark_delay(sid: int, payload: DelayIn, request: Request, db: Session = Depends(get_db), user: User = Depends(require_roles(*ALLOWED))):
    s = db.get(Shipment, sid)
    if not s:
        raise HTTPException(404, "Поставка не найдена")
    s.status = "delayed"
    s.delay_reason = payload.delay_reason
    s.delay_minutes = payload.delay_minutes
    if payload.notes:
        s.notes = (s.notes + " | " if s.notes else "") + payload.notes
    db.commit()
    audit(db, user, "delay", "shipment", s.id, request.client.host if request.client else "",
          f"{payload.delay_reason} +{payload.delay_minutes}мин", module="logistics")
    return {"ok": True}


@router.delete("/shipments/{sid}")
def delete_shipment(sid: int, request: Request, db: Session = Depends(get_db), user: User = Depends(require_roles(*ALLOWED))):
    s = db.get(Shipment, sid)
    if not s:
        raise HTTPException(404, "Поставка не найдена")
    db.delete(s)
    db.commit()
    audit(db, user, "delete", "shipment", sid, request.client.host if request.client else "", module="logistics")
    return {"ok": True}


# ---- Route segments ----

@router.get("/segments")
def list_segments(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.execute(select(RouteSegment).order_by(RouteSegment.id)).scalars().all()
    return [{"id": r.id, "name": r.name, "from_point": r.from_point, "to_point": r.to_point,
             "status": r.status, "blocked_reason": r.blocked_reason} for r in rows]


@router.put("/segments/{seg_id}")
def update_segment(seg_id: int, payload: SegmentIn, request: Request, db: Session = Depends(get_db), user: User = Depends(require_roles(*ALLOWED))):
    seg = db.get(RouteSegment, seg_id)
    if not seg:
        raise HTTPException(404, "Сегмент не найден")
    seg.status = payload.status
    seg.blocked_reason = payload.blocked_reason
    db.commit()
    audit(db, user, "segment_status", "route_segment", seg_id, request.client.host if request.client else "",
          f"{seg.name}->{payload.status}", module="logistics")
    return {"ok": True}


# ---- Transport ----

@router.get("/transport")
def list_transport(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.execute(select(TransportUnit).order_by(TransportUnit.id)).scalars().all()
    return [{"id": t.id, "unit_type": t.unit_type, "capacity_kg": t.capacity_kg,
             "status": t.status, "current_location": t.current_location, "notes": t.notes} for t in rows]


@router.post("/transport")
def create_transport(payload: TransportIn, request: Request, db: Session = Depends(get_db), user: User = Depends(require_roles(*ALLOWED))):
    t = TransportUnit(**payload.model_dump())
    db.add(t)
    db.commit()
    db.refresh(t)
    audit(db, user, "create", "transport", t.id, request.client.host if request.client else "", module="logistics")
    return {"id": t.id}


@router.put("/transport/{tid}")
def update_transport(tid: int, payload: TransportIn, request: Request, db: Session = Depends(get_db), user: User = Depends(require_roles(*ALLOWED))):
    t = db.get(TransportUnit, tid)
    if not t:
        raise HTTPException(404, "Транспорт не найден")
    for k, v in payload.model_dump().items():
        setattr(t, k, v)
    db.commit()
    audit(db, user, "update", "transport", tid, request.client.host if request.client else "", module="logistics")
    return {"ok": True}


# ---- KPI ----

@router.get("/kpi")
def kpi(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ships = db.execute(select(Shipment)).scalars().all()
    active = [s for s in ships if s.status not in ("delivered", "problem")]
    by_priority = {}
    for s in active:
        by_priority[s.priority] = by_priority.get(s.priority, 0) + 1
    delayed = [s for s in ships if s.status == "delayed"]
    avg_delay = round(sum(s.delay_minutes for s in delayed) / len(delayed)) if delayed else 0
    blocked = db.execute(select(func.count(RouteSegment.id)).where(RouteSegment.status == "blocked")).scalar_one()
    avail_transport = db.execute(select(func.count(TransportUnit.id)).where(TransportUnit.status == "available")).scalar_one()
    total_transport = db.execute(select(func.count(TransportUnit.id))).scalar_one()
    return {
        "active": len(active),
        "by_priority": by_priority,
        "delayed": len(delayed),
        "avg_delay_min": avg_delay,
        "delay_pct": round(len(delayed) / len(ships) * 100) if ships else 0,
        "blocked_routes": blocked,
        "transport_available": avail_transport,
        "transport_total": total_transport,
    }
