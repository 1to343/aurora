from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from datetime import timedelta

from pydantic import BaseModel
from sqlalchemy import func

from ..models import (
    Cell,
    Lot,
    LotStatus,
    Material,
    Movement,
    MovementType,
    QuarantineItem,
    Role,
    Stock,
    User,
    Warehouse,
    Zone,
)
from ..schemas import IssueIn, MaterialIn, ReceiptIn, TransferIn
from ..security import audit, get_current_user, require_roles
from .chat import post_system_message

router = APIRouter(prefix="/api/wms", tags=["wms"])


def _upsert_stock(db: Session, material_id: int, lot_id: int, cell_id: int, delta: float):
    stock = db.execute(
        select(Stock).where(
            Stock.material_id == material_id, Stock.lot_id == lot_id, Stock.cell_id == cell_id
        )
    ).scalar_one_or_none()
    if stock is None:
        if delta < 0:
            raise HTTPException(400, "Нет остатка для списания")
        stock = Stock(material_id=material_id, lot_id=lot_id, cell_id=cell_id, qty=0)
        db.add(stock)
        db.flush()
    new_qty = stock.qty + delta
    if new_qty < -1e-9:
        raise HTTPException(400, f"Недостаточно остатка в ячейке (доступно {stock.qty})")
    stock.qty = max(0.0, new_qty)


# ---- Справочники ----

@router.get("/materials")
def list_materials(db: Session = Depends(get_db), user=Depends(get_current_user)):
    rows = db.execute(select(Material).order_by(Material.sku)).scalars().all()
    return [
        {
            "id": m.id,
            "sku": m.sku,
            "name": m.name,
            "unit": m.unit,
            "is_hazmat": m.is_hazmat,
            "reorder_point": m.reorder_point,
        }
        for m in rows
    ]


@router.post("/materials")
def create_material(
    payload: MaterialIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.LOGISTICIAN, Role.TECHNOLOGIST)),
):
    if db.execute(select(Material).where(Material.sku == payload.sku)).scalar_one_or_none():
        raise HTTPException(400, "SKU уже существует")
    m = Material(**payload.model_dump())
    db.add(m)
    db.commit()
    db.refresh(m)
    audit(db, user, "create", "material", m.id, request.client.host if request.client else "")
    return {"id": m.id}


@router.get("/cells")
def list_cells(db: Session = Depends(get_db), user=Depends(get_current_user)):
    rows = (
        db.execute(
            select(Cell, Zone, Warehouse)
            .join(Zone, Cell.zone_id == Zone.id)
            .join(Warehouse, Zone.warehouse_id == Warehouse.id)
            .order_by(Warehouse.code, Zone.code, Cell.code)
        )
    ).all()
    return [
        {
            "id": c.id,
            "label": f"{w.code}/{z.code}/{c.code}",
            "zone_type": z.zone_type,
        }
        for c, z, w in rows
    ]


@router.get("/stock")
def stock_report(db: Session = Depends(get_db), user=Depends(get_current_user)):
    rows = (
        db.execute(
            select(Stock, Material, Lot, Cell, Zone, Warehouse)
            .join(Material, Stock.material_id == Material.id)
            .join(Lot, Stock.lot_id == Lot.id)
            .join(Cell, Stock.cell_id == Cell.id)
            .join(Zone, Cell.zone_id == Zone.id)
            .join(Warehouse, Zone.warehouse_id == Warehouse.id)
            .where(Stock.qty > 0)
            .order_by(Material.sku, Lot.received_at)
        )
    ).all()
    result = []
    for s, m, l, c, z, w in rows:
        result.append(
            {
                "material_sku": m.sku,
                "material_name": m.name,
                "lot_no": l.lot_no,
                "qty": s.qty,
                "unit": m.unit,
                "cell": f"{w.code}/{z.code}/{c.code}",
                "received_at": l.received_at.isoformat(),
                "expires_at": l.expires_at.isoformat() if l.expires_at else None,
                "below_reorder": _aggregate_below(db, m),
            }
        )
    return result


def _aggregate_below(db: Session, m: Material) -> bool:
    total = (
        db.execute(select(Stock.qty).where(Stock.material_id == m.id)).scalars().all()
    )
    return sum(total) < m.reorder_point if m.reorder_point > 0 else False


# ---- Операции ----

@router.post("/receipt")
def receipt(
    payload: ReceiptIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.LOGISTICIAN, Role.OPERATOR)),
):
    material = db.get(Material, payload.material_id)
    if not material:
        raise HTTPException(404, "Материал не найден")
    cell = db.get(Cell, payload.cell_id)
    if not cell:
        raise HTTPException(404, "Ячейка не найдена")
    # лот по номеру + материалу
    lot = db.execute(
        select(Lot).where(Lot.lot_no == payload.lot_no, Lot.material_id == material.id)
    ).scalar_one_or_none()
    if not lot:
        lot = Lot(
            lot_no=payload.lot_no,
            material_id=material.id,
            status=LotStatus.NEW,
            received_at=datetime.utcnow(),
            expires_at=payload.expires_at,
        )
        db.add(lot)
        db.flush()
    _upsert_stock(db, material.id, lot.id, cell.id, payload.qty)
    db.add(
        Movement(
            move_type=MovementType.RECEIPT,
            material_id=material.id,
            lot_id=lot.id,
            qty=payload.qty,
            to_cell_id=cell.id,
            user_id=user.id,
        )
    )
    db.commit()
    audit(
        db,
        user,
        "receipt",
        "material",
        material.id,
        request.client.host if request.client else "",
        f"lot={payload.lot_no} qty={payload.qty}",
    )
    return {"lot_id": lot.id}


@router.post("/transfer")
def transfer(
    payload: TransferIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.LOGISTICIAN, Role.OPERATOR)),
):
    _upsert_stock(db, payload.material_id, payload.lot_id, payload.from_cell_id, -payload.qty)
    _upsert_stock(db, payload.material_id, payload.lot_id, payload.to_cell_id, payload.qty)
    db.add(
        Movement(
            move_type=MovementType.TRANSFER,
            material_id=payload.material_id,
            lot_id=payload.lot_id,
            qty=payload.qty,
            from_cell_id=payload.from_cell_id,
            to_cell_id=payload.to_cell_id,
            user_id=user.id,
            note=payload.note,
        )
    )
    db.commit()
    audit(
        db, user, "transfer", "material", payload.material_id,
        request.client.host if request.client else "",
    )
    return {"ok": True}


@router.post("/issue")
def issue_to_production(
    payload: IssueIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.LOGISTICIAN, Role.OPERATOR, Role.SHIFT_LEAD)),
):
    """Выдача в производство с FIFO/FEFO."""
    q = (
        select(Stock, Lot)
        .join(Lot, Stock.lot_id == Lot.id)
        .where(Stock.material_id == payload.material_id, Stock.qty > 0)
    )
    if payload.from_cell_id:
        q = q.where(Stock.cell_id == payload.from_cell_id)
    if payload.strategy == "fefo":
        q = q.order_by(Lot.expires_at.is_(None), Lot.expires_at, Lot.received_at)
    else:
        q = q.order_by(Lot.received_at, Lot.id)
    rows = db.execute(q).all()
    remaining = payload.qty
    picked = []
    for s, l in rows:
        if remaining <= 0:
            break
        take = min(s.qty, remaining)
        s.qty -= take
        remaining -= take
        picked.append({"lot_id": l.id, "lot_no": l.lot_no, "qty": take, "cell_id": s.cell_id})
        db.add(
            Movement(
                move_type=MovementType.ISSUE,
                material_id=payload.material_id,
                lot_id=l.id,
                qty=take,
                from_cell_id=s.cell_id,
                user_id=user.id,
                work_order_id=payload.work_order_id,
                note=payload.note,
            )
        )
    if remaining > 1e-9:
        db.rollback()
        raise HTTPException(400, f"Недостаточно остатка: не хватает {remaining}")
    db.commit()
    audit(
        db, user, "issue", "material", payload.material_id,
        request.client.host if request.client else "",
        f"qty={payload.qty} strategy={payload.strategy}",
    )
    return {"picked": picked}


# ============ A4. Аварийный склад ============

def _material_total(db: Session, material_id: int) -> float:
    return db.execute(
        select(func.coalesce(func.sum(Stock.qty), 0.0)).where(Stock.material_id == material_id)
    ).scalar_one()


def _avg_daily_consumption(db: Session, material_id: int, days: int = 7) -> float:
    since = datetime.utcnow() - timedelta(days=days)
    issued = db.execute(
        select(func.coalesce(func.sum(Movement.qty), 0.0)).where(
            Movement.material_id == material_id,
            Movement.move_type == MovementType.ISSUE,
            Movement.ts >= since,
        )
    ).scalar_one()
    return issued / days if days else 0


@router.get("/critical")
def critical_stock(db: Session = Depends(get_db), user=Depends(get_current_user)):
    mats = db.execute(select(Material).where(Material.reorder_point > 0)).scalars().all()
    out = []
    for m in mats:
        total = _material_total(db, m.id)
        if total < m.reorder_point:
            avg = _avg_daily_consumption(db, m.id)
            days_left = round(total / avg, 1) if avg > 0 else None
            ratio = total / m.reorder_point if m.reorder_point else 0
            level = "empty" if total <= 0 else ("red" if ratio < 0.25 else "yellow")
            out.append({
                "id": m.id, "sku": m.sku, "name": m.name, "unit": m.unit,
                "qty": total, "reorder_point": m.reorder_point,
                "level": level, "days_left": days_left,
            })
    return out


def _check_and_alert(db: Session, material: Material):
    """Если остаток упал ниже точки заказа — системное сообщение в чат."""
    if material.reorder_point <= 0:
        return
    total = _material_total(db, material.id)
    if total < material.reorder_point:
        post_system_message(
            db,
            f"⚠️ {material.name}: остаток {total:g} {material.unit} ниже минимума {material.reorder_point:g}",
            priority="important",
        )


class QuickReceiptIn(BaseModel):
    material_id: int
    qty: float
    zone_type: str = "general"  # general/quarantine
    lot_no: str = ""


@router.post("/quick-receipt")
def quick_receipt(payload: QuickReceiptIn, request: Request, db: Session = Depends(get_db),
                  user: User = Depends(require_roles(Role.OPERATOR, Role.LOGISTICIAN, Role.SHIFT_LEAD))):
    material = db.get(Material, payload.material_id)
    if not material:
        raise HTTPException(404, "Материал не найден")
    # первая свободная ячейка в нужной зоне
    cell = db.execute(
        select(Cell).join(Zone, Cell.zone_id == Zone.id).where(Zone.zone_type == payload.zone_type)
    ).scalars().first()
    if not cell:
        cell = db.execute(select(Cell)).scalars().first()
    if not cell:
        raise HTTPException(400, "Нет ячеек на складе")
    lot_no = payload.lot_no or f"AUTO-{int(datetime.utcnow().timestamp())}"
    lot = Lot(lot_no=lot_no, material_id=material.id, status=LotStatus.PASS, received_at=datetime.utcnow())
    db.add(lot)
    db.flush()
    _upsert_stock(db, material.id, lot.id, cell.id, payload.qty)
    db.add(Movement(move_type=MovementType.RECEIPT, material_id=material.id, lot_id=lot.id,
                    qty=payload.qty, to_cell_id=cell.id, user_id=user.id, note="quick"))
    db.commit()
    audit(db, user, "quick_receipt", "material", material.id,
          request.client.host if request.client else "", f"qty={payload.qty}", module="wms")
    return {"lot_id": lot.id, "cell_id": cell.id}


class QuickIssueIn(BaseModel):
    material_id: int
    qty: float


@router.post("/quick-issue")
def quick_issue(payload: QuickIssueIn, request: Request, db: Session = Depends(get_db),
                user: User = Depends(require_roles(Role.OPERATOR, Role.LOGISTICIAN, Role.SHIFT_LEAD))):
    material = db.get(Material, payload.material_id)
    if not material:
        raise HTTPException(404, "Материал не найден")
    rows = db.execute(
        select(Stock, Lot).join(Lot, Stock.lot_id == Lot.id)
        .where(Stock.material_id == payload.material_id, Stock.qty > 0)
        .order_by(Lot.received_at, Lot.id)
    ).all()
    remaining = payload.qty
    for s, l in rows:
        if remaining <= 0:
            break
        take = min(s.qty, remaining)
        s.qty -= take
        remaining -= take
        db.add(Movement(move_type=MovementType.ISSUE, material_id=material.id, lot_id=l.id,
                        qty=take, from_cell_id=s.cell_id, user_id=user.id, note="quick"))
    if remaining > 1e-9:
        db.rollback()
        raise HTTPException(400, f"Недостаточно остатка: не хватает {remaining:g}")
    db.commit()
    audit(db, user, "quick_issue", "material", material.id,
          request.client.host if request.client else "", f"qty={payload.qty}", module="wms")
    _check_and_alert(db, material)
    return {"ok": True}


@router.get("/inventory")
def inventory(db: Session = Depends(get_db), user=Depends(get_current_user)):
    mats = db.execute(select(Material).order_by(Material.sku)).scalars().all()
    return [{"id": m.id, "sku": m.sku, "name": m.name, "unit": m.unit,
             "qty": _material_total(db, m.id)} for m in mats]


# ---- Карантин ----

class QuarantineIn(BaseModel):
    material_id: int
    qty: float
    reason: str
    lot_id: int | None = None


@router.post("/quarantine")
def to_quarantine(payload: QuarantineIn, request: Request, db: Session = Depends(get_db),
                  user: User = Depends(require_roles(Role.OPERATOR, Role.QC, Role.LOGISTICIAN, Role.SHIFT_LEAD))):
    material = db.get(Material, payload.material_id)
    if not material:
        raise HTTPException(404, "Материал не найден")
    q = QuarantineItem(material_id=payload.material_id, lot_id=payload.lot_id,
                       qty=payload.qty, reason=payload.reason)
    db.add(q)
    db.commit()
    db.refresh(q)
    audit(db, user, "quarantine", "material", payload.material_id,
          request.client.host if request.client else "", payload.reason, module="wms")
    return {"id": q.id}


@router.get("/quarantine")
def list_quarantine(db: Session = Depends(get_db), user=Depends(get_current_user)):
    rows = db.execute(
        select(QuarantineItem, Material).join(Material, QuarantineItem.material_id == Material.id)
        .order_by(QuarantineItem.created_at.desc())
    ).all()
    return [{
        "id": q.id, "material": m.name, "sku": m.sku, "qty": q.qty, "reason": q.reason,
        "status": q.status, "created_at": q.created_at.isoformat(),
        "resolved_by": q.resolved_by,
    } for q, m in rows]


class QResolveIn(BaseModel):
    action: str  # release/scrap
    qc_signoff: str = ""


@router.post("/quarantine/{qid}/resolve")
def resolve_quarantine(qid: int, payload: QResolveIn, request: Request, db: Session = Depends(get_db),
                       user: User = Depends(require_roles(Role.QC, Role.SHIFT_LEAD))):
    q = db.get(QuarantineItem, qid)
    if not q:
        raise HTTPException(404, "Запись не найдена")
    if payload.action == "release":
        if not payload.qc_signoff.strip():
            raise HTTPException(400, "Требуется подпись ОТК")
        q.status = "released"
    else:
        q.status = "scrapped"
    q.resolved_at = datetime.utcnow()
    q.resolved_by = user.username
    db.commit()
    audit(db, user, f"quarantine_{payload.action}", "quarantine", qid,
          request.client.host if request.client else "", payload.qc_signoff, module="wms")
    return {"ok": True}
