from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import ChatMessage, Role, User, ROLE_TITLES_RU
from ..security import get_current_user

router = APIRouter(prefix="/api/chat", tags=["chat"])


class MessageIn(BaseModel):
    text: str
    priority: str = "normal"  # normal/important/emergency


def post_system_message(db: Session, text: str, priority: str = "normal", pinned: bool = False):
    """Системное сообщение в канал статусов (вызывается из других модулей)."""
    msg = ChatMessage(user_id=None, text=text, priority=priority, pinned=pinned, channel="system")
    db.add(msg)
    db.commit()
    return msg


def _msg_dict(m: ChatMessage, u: User | None):
    return {
        "id": m.id,
        "ts": m.ts.isoformat(),
        "user_id": u.id if u else -1,
        "username": u.username if u else "system",
        "full_name": (u.full_name or u.username) if u else "Система",
        "role": ROLE_TITLES_RU.get(u.role, u.role.value) if u else "AUTO",
        "text": m.text,
        "priority": m.priority,
        "pinned": m.pinned,
        "channel": m.channel,
    }


@router.get("/messages")
def get_messages(
    after_id: int = Query(0),
    limit: int = Query(200, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = (
        select(ChatMessage, User)
        .outerjoin(User, ChatMessage.user_id == User.id)
        .where(ChatMessage.id > after_id)
        .order_by(ChatMessage.id.asc())
        .limit(limit)
    )
    rows = db.execute(q).all()
    return [_msg_dict(m, u) for m, u in rows]


@router.get("/pinned")
def get_pinned(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = (
        select(ChatMessage, User)
        .outerjoin(User, ChatMessage.user_id == User.id)
        .where(ChatMessage.pinned == True)  # noqa: E712
        .order_by(ChatMessage.ts.desc())
    )
    return [_msg_dict(m, u) for m, u in db.execute(q).all()]


@router.post("/messages")
def post_message(
    payload: MessageIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    text = payload.text.strip()
    if not text:
        raise HTTPException(400, "Пустое сообщение")
    priority = payload.priority if payload.priority in ("normal", "important", "emergency") else "normal"
    # экстренные — только admin/director/shift
    if priority == "emergency" and user.role not in (Role.ADMIN, Role.DIRECTOR, Role.SHIFT_LEAD):
        priority = "important"
    msg = ChatMessage(
        user_id=user.id, text=text, priority=priority,
        pinned=(priority == "emergency"), channel="general",
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return {"id": msg.id, "priority": priority, "pinned": msg.pinned}


@router.post("/messages/{mid}/unpin")
def unpin(mid: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role not in (Role.ADMIN, Role.DIRECTOR, Role.SHIFT_LEAD):
        raise HTTPException(403, "Недостаточно прав")
    m = db.get(ChatMessage, mid)
    if m:
        m.pinned = False
        db.commit()
    return {"ok": True}
