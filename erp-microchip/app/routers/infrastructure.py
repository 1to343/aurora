from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Equipment, Facility, Incident, Role, User
from ..security import audit, get_current_user, require_roles

router = APIRouter(prefix="/api/infra", tags=["infrastructure"])

ALLOWED = (Role.DIRECTOR, Role.SHIFT_LEAD, Role.MECHANIC)


class EquipmentIn(BaseModel):
    name: str
    eq_type: str = ""
    location: str = ""
    status: str = "working"
    condition_notes: str = ""


class StatusIn(BaseModel):
    status: str
    note: str = ""


class FacilityIn(BaseModel):
    name: str
    fac_type: str = ""
    status: str = "working"
    has_power: str = "yes"
    has_network: str = "yes"
    has_climate_control: bool = True
    capacity_percent: int = 100
    damage_description: str = ""


class IncidentIn(BaseModel):
    inc_type: str = "other"
    description: str = ""
    affected_equipment_ids: str = ""
    affected_facility_ids: str = ""
    severity: str = "medium"
    assigned_to: str = ""


# ---- Equipment ----

@router.get("/equipment")
def list_equipment(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.execute(select(Equipment).order_by(Equipment.id)).scalars().all()
    return [{
        "id": e.id, "name": e.name, "eq_type": e.eq_type, "location": e.location,
        "status": e.status, "condition_notes": e.condition_notes,
        "last_maintenance": e.last_maintenance.isoformat() if e.last_maintenance else None,
        "next_maintenance": e.next_maintenance.isoformat() if e.next_maintenance else None,
    } for e in rows]


@router.post("/equipment")
def create_equipment(payload: EquipmentIn, request: Request, db: Session = Depends(get_db), user: User = Depends(require_roles(*ALLOWED))):
    e = Equipment(**payload.model_dump(), updated_by=user.username)
    db.add(e)
    db.commit()
    db.refresh(e)
    audit(db, user, "create", "equipment", e.id, request.client.host if request.client else "", module="infrastructure")
    return {"id": e.id}


@router.put("/equipment/{eid}/status")
def set_equipment_status(eid: int, payload: StatusIn, request: Request, db: Session = Depends(get_db), user: User = Depends(require_roles(*ALLOWED))):
    e = db.get(Equipment, eid)
    if not e:
        raise HTTPException(404, "Оборудование не найдено")
    if not payload.note.strip():
        raise HTTPException(400, "Укажите причину изменения статуса")
    old = e.status
    e.status = payload.status
    e.condition_notes = payload.note
    e.updated_by = user.username
    db.commit()
    audit(db, user, "status_change", "equipment", eid, request.client.host if request.client else "",
          f"{e.name}: {old}->{payload.status} ({payload.note})", module="infrastructure")
    return {"ok": True}


# ---- Facilities ----

@router.get("/facilities")
def list_facilities(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.execute(select(Facility).order_by(Facility.id)).scalars().all()
    return [{
        "id": f.id, "name": f.name, "fac_type": f.fac_type, "status": f.status,
        "has_power": f.has_power, "has_network": f.has_network,
        "has_climate_control": f.has_climate_control, "capacity_percent": f.capacity_percent,
        "damage_description": f.damage_description,
    } for f in rows]


@router.post("/facilities")
def create_facility(payload: FacilityIn, request: Request, db: Session = Depends(get_db), user: User = Depends(require_roles(*ALLOWED))):
    f = Facility(**payload.model_dump(), updated_by=user.username)
    db.add(f)
    db.commit()
    db.refresh(f)
    audit(db, user, "create", "facility", f.id, request.client.host if request.client else "", module="infrastructure")
    return {"id": f.id}


@router.put("/facilities/{fid}")
def update_facility(fid: int, payload: FacilityIn, request: Request, db: Session = Depends(get_db), user: User = Depends(require_roles(*ALLOWED))):
    f = db.get(Facility, fid)
    if not f:
        raise HTTPException(404, "Помещение не найдено")
    for k, v in payload.model_dump().items():
        setattr(f, k, v)
    f.updated_by = user.username
    db.commit()
    audit(db, user, "update", "facility", fid, request.client.host if request.client else "", module="infrastructure")
    return {"ok": True}


# ---- Incidents ----

@router.get("/incidents")
def list_incidents(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.execute(select(Incident).order_by(Incident.timestamp.desc())).scalars().all()
    return [{
        "id": i.id, "timestamp": i.timestamp.isoformat(), "inc_type": i.inc_type,
        "description": i.description, "affected_equipment_ids": i.affected_equipment_ids,
        "affected_facility_ids": i.affected_facility_ids, "severity": i.severity,
        "status": i.status, "assigned_to": i.assigned_to, "resolution_notes": i.resolution_notes,
    } for i in rows]


@router.post("/incidents")
def create_incident(payload: IncidentIn, request: Request, db: Session = Depends(get_db), user: User = Depends(require_roles(*ALLOWED))):
    i = Incident(**payload.model_dump(), created_by=user.username)
    db.add(i)
    db.flush()
    # авто-обновление статусов затронутых объектов
    sev_to_status = {"critical": "destroyed", "high": "damaged", "medium": "limited", "low": "limited"}
    new_status = sev_to_status.get(payload.severity, "limited")
    for eid in [x for x in payload.affected_equipment_ids.split(",") if x.strip().isdigit()]:
        e = db.get(Equipment, int(eid))
        if e:
            e.status = new_status
            e.condition_notes = f"Инцидент: {payload.inc_type}"
    for fid in [x for x in payload.affected_facility_ids.split(",") if x.strip().isdigit()]:
        f = db.get(Facility, int(fid))
        if f:
            f.status = "destroyed" if payload.severity == "critical" else "limited"
            f.damage_description = payload.description
    db.commit()
    db.refresh(i)
    audit(db, user, "incident", "incident", i.id, request.client.host if request.client else "",
          f"{payload.inc_type} severity={payload.severity}", module="infrastructure")
    return {"id": i.id}


@router.put("/incidents/{iid}/status")
def set_incident_status(iid: int, payload: StatusIn, request: Request, db: Session = Depends(get_db), user: User = Depends(require_roles(*ALLOWED))):
    i = db.get(Incident, iid)
    if not i:
        raise HTTPException(404, "Инцидент не найден")
    i.status = payload.status
    i.resolution_notes = payload.note
    if payload.status in ("resolved", "unrecoverable"):
        i.resolved_at = datetime.utcnow()
    db.commit()
    audit(db, user, "incident_status", "incident", iid, request.client.host if request.client else "",
          f"->{payload.status}", module="infrastructure")
    return {"ok": True}


# ---- Summary KPI ----

@router.get("/summary")
def summary(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    eq = db.execute(select(Equipment)).scalars().all()
    fac = db.execute(select(Facility)).scalars().all()
    eq_working = sum(1 for e in eq if e.status == "working")
    fac_working = sum(1 for f in fac if f.status == "working")
    return {
        "equipment_working": eq_working,
        "equipment_total": len(eq),
        "facilities_working": fac_working,
        "facilities_total": len(fac),
        "zones_no_power": [f.name for f in fac if f.has_power == "no"],
        "zones_no_network": [f.name for f in fac if f.has_network == "no"],
        "damaged_equipment": [{"name": e.name, "status": e.status} for e in eq if e.status in ("damaged", "destroyed", "stopped")],
    }
