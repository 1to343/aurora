from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import AuditLog, Role
from ..security import require_roles

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("/")
def get_audit(
    limit: int = 300,
    module: str = Query(""),
    db: Session = Depends(get_db),
    user=Depends(require_roles(Role.ADMIN, Role.DIRECTOR)),
):
    q = select(AuditLog).order_by(AuditLog.ts.desc()).limit(limit)
    if module:
        q = select(AuditLog).where(AuditLog.module == module).order_by(AuditLog.ts.desc()).limit(limit)
    rows = db.execute(q).scalars().all()
    return [
        {
            "ts": r.ts.isoformat(),
            "user": r.username,
            "action": r.action,
            "entity": r.entity,
            "entity_id": r.entity_id,
            "ip": r.ip,
            "details": r.details,
            "module": r.module,
            "context": r.context,
        }
        for r in rows
    ]
