from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import (
    Lot,
    LotStatus,
    OperationLog,
    Role,
    RoutingStep,
    User,
    WorkOrder,
    WorkOrderStatus,
)
from ..schemas import OperationIn, WorkOrderIn
from ..security import audit, get_current_user, require_roles

router = APIRouter(prefix="/api/prod", tags=["production"])


@router.get("/work-orders")
def list_work_orders(db: Session = Depends(get_db), user=Depends(get_current_user)):
    rows = db.execute(select(WorkOrder).order_by(WorkOrder.created_at.desc())).scalars().all()
    out = []
    for wo in rows:
        lot_count = db.execute(
            select(func.count(Lot.id)).where(Lot.work_order_id == wo.id)
        ).scalar_one()
        out.append(
            {
                "id": wo.id,
                "wo_no": wo.wo_no,
                "product": wo.product_name,
                "qty_planned": wo.qty_planned,
                "status": wo.status.value,
                "created_at": wo.created_at.isoformat(),
                "lots": lot_count,
                "steps": [
                    {"i": s.order_index, "name": s.name, "recipe": s.recipe} for s in wo.steps
                ],
            }
        )
    return out


@router.post("/work-orders")
def create_work_order(
    payload: WorkOrderIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.TECHNOLOGIST, Role.SHIFT_LEAD)),
):
    if db.execute(select(WorkOrder).where(WorkOrder.wo_no == payload.wo_no)).scalar_one_or_none():
        raise HTTPException(400, "Номер WO уже существует")
    wo = WorkOrder(
        wo_no=payload.wo_no,
        product_name=payload.product_name,
        qty_planned=payload.qty_planned,
        due_date=payload.due_date,
        notes=payload.notes,
        status=WorkOrderStatus.RELEASED,
    )
    db.add(wo)
    db.flush()
    for s in payload.steps:
        db.add(
            RoutingStep(
                work_order_id=wo.id,
                order_index=s.order_index,
                name=s.name,
                recipe=s.recipe,
                target_param=s.target_param,
                tolerance=s.tolerance,
            )
        )
    db.commit()
    audit(db, user, "create", "work_order", wo.id, request.client.host if request.client else "")
    return {"id": wo.id}


@router.post("/work-orders/{wo_id}/release-lot")
def release_lot(
    wo_id: int,
    lot_no: str,
    wafer_qty: int = 25,
    request: Request = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.SHIFT_LEAD, Role.TECHNOLOGIST, Role.OPERATOR)),
):
    wo = db.get(WorkOrder, wo_id)
    if not wo:
        raise HTTPException(404, "WO не найден")
    if not wo.steps:
        raise HTTPException(400, "У WO нет маршрута")
    if db.execute(select(Lot).where(Lot.lot_no == lot_no)).scalar_one_or_none():
        raise HTTPException(400, "Лот с таким номером уже существует")
    lot = Lot(
        lot_no=lot_no,
        wafer_qty=wafer_qty,
        status=LotStatus.IN_PROGRESS,
        work_order_id=wo_id,
        current_step_index=0,
    )
    db.add(lot)
    if wo.status == WorkOrderStatus.RELEASED:
        wo.status = WorkOrderStatus.IN_PROGRESS
    db.commit()
    db.refresh(lot)
    audit(db, user, "release_lot", "lot", lot.id, request.client.host if request and request.client else "")
    return {"lot_id": lot.id}


@router.get("/lots")
def list_lots(db: Session = Depends(get_db), user=Depends(get_current_user)):
    rows = db.execute(select(Lot).order_by(Lot.id.desc())).scalars().all()
    out = []
    for l in rows:
        wo = db.get(WorkOrder, l.work_order_id) if l.work_order_id else None
        current_step = None
        if wo and l.current_step_index < len(wo.steps):
            current_step = wo.steps[l.current_step_index].name
        out.append(
            {
                "id": l.id,
                "lot_no": l.lot_no,
                "status": l.status.value,
                "wafer_qty": l.wafer_qty,
                "wo_no": wo.wo_no if wo else None,
                "current_step": current_step,
                "step_index": l.current_step_index,
                "received_at": l.received_at.isoformat(),
            }
        )
    return out


@router.get("/lots/{lot_id}/history")
def lot_history(lot_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    lot = db.get(Lot, lot_id)
    if not lot:
        raise HTTPException(404, "Лот не найден")
    ops = (
        db.execute(
            select(OperationLog, RoutingStep, User)
            .join(RoutingStep, OperationLog.step_id == RoutingStep.id)
            .outerjoin(User, OperationLog.operator_id == User.id)
            .where(OperationLog.lot_id == lot_id)
            .order_by(OperationLog.ts)
        )
    ).all()
    return {
        "lot": {
            "id": lot.id,
            "lot_no": lot.lot_no,
            "status": lot.status.value,
            "wafer_qty": lot.wafer_qty,
            "step_index": lot.current_step_index,
        },
        "operations": [
            {
                "ts": op.ts.isoformat(),
                "step": step.name,
                "operator": u.username if u else "—",
                "measured_value": op.measured_value,
                "result": op.result,
                "defect_qty": op.defect_qty,
                "note": op.note,
            }
            for op, step, u in ops
        ],
    }


@router.post("/operations")
def log_operation(
    payload: OperationIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.OPERATOR, Role.SHIFT_LEAD, Role.QC)),
):
    """Регистрация операции на текущем шаге маршрута для партии."""
    lot = db.get(Lot, payload.lot_id)
    if not lot:
        raise HTTPException(404, "Лот не найден")
    if lot.status in (LotStatus.DONE, LotStatus.REJECT):
        raise HTTPException(400, f"Лот в статусе {lot.status.value}, операции запрещены")
    wo = db.get(WorkOrder, lot.work_order_id) if lot.work_order_id else None
    if not wo or not wo.steps:
        raise HTTPException(400, "У лота нет привязанного маршрута")
    if lot.current_step_index >= len(wo.steps):
        raise HTTPException(400, "Все шаги маршрута уже выполнены")

    step = wo.steps[lot.current_step_index]
    db.add(
        OperationLog(
            lot_id=lot.id,
            step_id=step.id,
            operator_id=user.id,
            measured_value=payload.measured_value,
            result=payload.result,
            defect_qty=payload.defect_qty,
            note=payload.note,
        )
    )
    # дефекты вычитаем из wafer_qty
    if payload.defect_qty > 0:
        lot.wafer_qty = max(0, lot.wafer_qty - payload.defect_qty)

    if payload.result == "fail":
        lot.status = LotStatus.HOLD
        action = "operation_fail_hold"
    else:
        lot.current_step_index += 1
        if lot.current_step_index >= len(wo.steps):
            lot.status = LotStatus.DONE
            # проверяем, не все ли лоты WO готовы
            unfinished = db.execute(
                select(func.count(Lot.id)).where(
                    Lot.work_order_id == wo.id, Lot.status != LotStatus.DONE
                )
            ).scalar_one()
            if unfinished == 0:
                wo.status = WorkOrderStatus.DONE
        else:
            lot.status = LotStatus.IN_PROGRESS
        action = "operation_pass"
    db.commit()
    audit(db, user, action, "lot", lot.id, request.client.host if request.client else "",
          f"step={step.name} measured={payload.measured_value}")
    return {"lot_status": lot.status.value, "step_index": lot.current_step_index}


@router.post("/lots/{lot_id}/status")
def set_lot_status(
    lot_id: int,
    new_status: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.QC, Role.SHIFT_LEAD, Role.TECHNOLOGIST)),
):
    lot = db.get(Lot, lot_id)
    if not lot:
        raise HTTPException(404, "Лот не найден")
    try:
        lot.status = LotStatus(new_status)
    except ValueError:
        raise HTTPException(400, f"Недопустимый статус: {new_status}")
    db.commit()
    audit(db, user, "lot_status", "lot", lot.id, request.client.host if request.client else "",
          f"->{new_status}")
    return {"status": lot.status.value}


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), user=Depends(get_current_user)):
    by_status = {
        st.value: db.execute(
            select(func.count(Lot.id)).where(Lot.status == st)
        ).scalar_one()
        for st in LotStatus
    }
    wo_by_status = {
        st.value: db.execute(
            select(func.count(WorkOrder.id)).where(WorkOrder.status == st)
        ).scalar_one()
        for st in WorkOrderStatus
    }
    total_wafers_wip = db.execute(
        select(func.coalesce(func.sum(Lot.wafer_qty), 0)).where(
            Lot.status.in_([LotStatus.NEW, LotStatus.IN_PROGRESS, LotStatus.HOLD, LotStatus.REWORK])
        )
    ).scalar_one()
    total_ops = db.execute(select(func.count(OperationLog.id))).scalar_one()
    fail_ops = db.execute(
        select(func.count(OperationLog.id)).where(OperationLog.result == "fail")
    ).scalar_one()
    return {
        "lots_by_status": by_status,
        "wo_by_status": wo_by_status,
        "wip_wafers": int(total_wafers_wip),
        "operations_total": total_ops,
        "operations_fail": fail_ops,
        "defect_rate": round(fail_ops / total_ops, 4) if total_ops else 0,
    }
