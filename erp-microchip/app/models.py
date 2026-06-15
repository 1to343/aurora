from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class Role(str, enum.Enum):
    ADMIN = "admin"
    DIRECTOR = "director"
    TECHNOLOGIST = "technologist"
    OPERATOR = "operator"
    SHIFT_LEAD = "shift_lead"
    QC = "qc"
    LOGISTICIAN = "logistician"
    MECHANIC = "mechanic"
    ACCOUNTANT = "accountant"


ROLE_TITLES_RU = {
    Role.ADMIN: "Администратор",
    Role.DIRECTOR: "Директор / Руководитель",
    Role.TECHNOLOGIST: "Технолог",
    Role.OPERATOR: "Оператор",
    Role.SHIFT_LEAD: "Начальник смены",
    Role.QC: "Специалист ОТК",
    Role.LOGISTICIAN: "Логист / Снабженец",
    Role.MECHANIC: "Механик",
    Role.ACCOUNTANT: "Бухгалтер",
}


class LotStatus(str, enum.Enum):
    NEW = "new"
    IN_PROGRESS = "in_progress"
    HOLD = "hold"
    PASS = "pass"
    REJECT = "reject"
    REWORK = "rework"
    DONE = "done"


class WorkOrderStatus(str, enum.Enum):
    DRAFT = "draft"
    RELEASED = "released"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CANCELLED = "cancelled"


class MovementType(str, enum.Enum):
    RECEIPT = "receipt"
    ISSUE = "issue"
    TRANSFER = "transfer"
    RETURN = "return"
    ADJUSTMENT = "adjustment"


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(128), default="")
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    role: Mapped[Role] = mapped_column(Enum(Role), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    username: Mapped[str] = mapped_column(String(64), default="")
    action: Mapped[str] = mapped_column(String(64))
    entity: Mapped[str] = mapped_column(String(64), default="")
    entity_id: Mapped[str] = mapped_column(String(64), default="")
    ip: Mapped[str] = mapped_column(String(64), default="")
    details: Mapped[str] = mapped_column(Text, default="")
    module: Mapped[str] = mapped_column(String(32), default="")
    context: Mapped[str] = mapped_column(Text, default="")  # JSON-строка


# ----- WMS -----

class Warehouse(Base):
    __tablename__ = "warehouses"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(128))
    zones: Mapped[list["Zone"]] = relationship(back_populates="warehouse", cascade="all,delete")


class Zone(Base):
    __tablename__ = "zones"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"))
    code: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(128))
    # типы: general, climate, hazmat, quarantine
    zone_type: Mapped[str] = mapped_column(String(32), default="general")
    warehouse: Mapped[Warehouse] = relationship(back_populates="zones")
    cells: Mapped[list["Cell"]] = relationship(back_populates="zone", cascade="all,delete")
    __table_args__ = (UniqueConstraint("warehouse_id", "code"),)


class Cell(Base):
    __tablename__ = "cells"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    zone_id: Mapped[int] = mapped_column(ForeignKey("zones.id"))
    code: Mapped[str] = mapped_column(String(32))
    zone: Mapped[Zone] = relationship(back_populates="cells")
    __table_args__ = (UniqueConstraint("zone_id", "code"),)


class Material(Base):
    __tablename__ = "materials"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sku: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(256))
    unit: Mapped[str] = mapped_column(String(16), default="шт")
    is_hazmat: Mapped[bool] = mapped_column(Boolean, default=False)
    msds: Mapped[str] = mapped_column(Text, default="")
    reorder_point: Mapped[float] = mapped_column(Float, default=0.0)
    shelf_life_days: Mapped[int] = mapped_column(Integer, default=0)


class Lot(Base):
    __tablename__ = "lots"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lot_no: Mapped[str] = mapped_column(String(64), unique=True)
    material_id: Mapped[int | None] = mapped_column(ForeignKey("materials.id"), nullable=True)
    # для wafer-партий — кол-во пластин:
    wafer_qty: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[LotStatus] = mapped_column(Enum(LotStatus), default=LotStatus.NEW)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    work_order_id: Mapped[int | None] = mapped_column(ForeignKey("work_orders.id"), nullable=True)
    current_step_index: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str] = mapped_column(Text, default="")
    material: Mapped[Material | None] = relationship()


class Stock(Base):
    """Остатки материала по партии и ячейке (для WMS-материалов)."""
    __tablename__ = "stock"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id"))
    lot_id: Mapped[int] = mapped_column(ForeignKey("lots.id"))
    cell_id: Mapped[int] = mapped_column(ForeignKey("cells.id"))
    qty: Mapped[float] = mapped_column(Float, default=0.0)
    material: Mapped[Material] = relationship()
    lot: Mapped[Lot] = relationship()
    cell: Mapped[Cell] = relationship()
    __table_args__ = (UniqueConstraint("material_id", "lot_id", "cell_id"),)


class Movement(Base):
    __tablename__ = "movements"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    move_type: Mapped[MovementType] = mapped_column(Enum(MovementType))
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id"))
    lot_id: Mapped[int] = mapped_column(ForeignKey("lots.id"))
    qty: Mapped[float] = mapped_column(Float)
    from_cell_id: Mapped[int | None] = mapped_column(ForeignKey("cells.id"), nullable=True)
    to_cell_id: Mapped[int | None] = mapped_column(ForeignKey("cells.id"), nullable=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    work_order_id: Mapped[int | None] = mapped_column(ForeignKey("work_orders.id"), nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")


# ----- Производство -----

class RoutingStep(Base):
    __tablename__ = "routing_steps"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    work_order_id: Mapped[int] = mapped_column(ForeignKey("work_orders.id"))
    order_index: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(128))  # литография, травление, ...
    recipe: Mapped[str] = mapped_column(String(64), default="")
    target_param: Mapped[str] = mapped_column(String(64), default="")
    tolerance: Mapped[str] = mapped_column(String(64), default="")
    work_order: Mapped["WorkOrder"] = relationship(back_populates="steps")


class WorkOrder(Base):
    __tablename__ = "work_orders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    wo_no: Mapped[str] = mapped_column(String(64), unique=True)
    product_name: Mapped[str] = mapped_column(String(256))
    qty_planned: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[WorkOrderStatus] = mapped_column(Enum(WorkOrderStatus), default=WorkOrderStatus.DRAFT)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    due_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    steps: Mapped[list[RoutingStep]] = relationship(
        back_populates="work_order", cascade="all,delete", order_by="RoutingStep.order_index"
    )


class OperationLog(Base):
    """Фактически выполненная операция над партией."""
    __tablename__ = "operation_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    lot_id: Mapped[int] = mapped_column(ForeignKey("lots.id"))
    step_id: Mapped[int] = mapped_column(ForeignKey("routing_steps.id"))
    operator_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    measured_value: Mapped[str] = mapped_column(String(64), default="")
    result: Mapped[str] = mapped_column(String(16), default="pass")  # pass/fail
    defect_qty: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[str] = mapped_column(Text, default="")


# ----- Чат -----

class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(String(16), default="normal")  # normal/important/emergency
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    channel: Mapped[str] = mapped_column(String(16), default="general")  # general/system
    user: Mapped[User] = relationship()


# ----- A1. Энергоустойчивость -----

class PowerEvent(Base):
    __tablename__ = "power_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    start_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    event_type: Mapped[str] = mapped_column(String(16), default="outage")  # outage/ups/restore
    source: Mapped[str] = mapped_column(String(16), default="grid")  # grid/ups/generator/none
    is_planned: Mapped[bool] = mapped_column(Boolean, default=False)
    affected_zones: Mapped[str] = mapped_column(String(256), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str] = mapped_column(String(64), default="")


# ----- A3. Кризисная логистика -----

class Shipment(Base):
    __tablename__ = "shipments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ship_type: Mapped[str] = mapped_column(String(16), default="in")  # in/out
    priority: Mapped[str] = mapped_column(String(16), default="medium")  # critical/high/medium/low
    contents: Mapped[str] = mapped_column(String(256), default="")
    origin: Mapped[str] = mapped_column(String(128), default="")
    destination: Mapped[str] = mapped_column(String(128), default="")
    transport_type: Mapped[str] = mapped_column(String(32), default="truck")  # truck/rail/manual/drone
    status: Mapped[str] = mapped_column(String(24), default="planned")
    planned_eta: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    actual_arrival: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    delay_reason: Mapped[str] = mapped_column(String(64), default="")
    delay_minutes: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class RouteSegment(Base):
    __tablename__ = "route_segments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    from_point: Mapped[str] = mapped_column(String(64), default="")
    to_point: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[str] = mapped_column(String(16), default="free")  # free/hard/blocked
    blocked_reason: Mapped[str] = mapped_column(String(128), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TransportUnit(Base):
    __tablename__ = "transport_units"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    unit_type: Mapped[str] = mapped_column(String(32), default="truck")  # truck/van/forklift/cart
    capacity_kg: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(24), default="available")  # available/in_transit/repair/destroyed
    current_location: Mapped[str] = mapped_column(String(128), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ----- A4. Карантин склада -----

class QuarantineItem(Base):
    __tablename__ = "quarantine_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id"))
    lot_id: Mapped[int | None] = mapped_column(ForeignKey("lots.id"), nullable=True)
    qty: Mapped[float] = mapped_column(Float, default=0)
    reason: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[str] = mapped_column(String(16), default="hold")  # hold/released/scrapped
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolved_by: Mapped[str] = mapped_column(String(64), default="")
    material: Mapped[Material] = relationship()


# ----- A5. Инфраструктура -----

class Equipment(Base):
    __tablename__ = "equipment"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    eq_type: Mapped[str] = mapped_column(String(48), default="")
    location: Mapped[str] = mapped_column(String(128), default="")
    status: Mapped[str] = mapped_column(String(24), default="working")
    # working/limited/stopped/damaged/destroyed
    condition_notes: Mapped[str] = mapped_column(Text, default="")
    last_maintenance: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    next_maintenance: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_by: Mapped[str] = mapped_column(String(64), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Facility(Base):
    __tablename__ = "facilities"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    fac_type: Mapped[str] = mapped_column(String(48), default="")
    status: Mapped[str] = mapped_column(String(24), default="working")
    # working/limited/down/destroyed
    has_power: Mapped[str] = mapped_column(String(16), default="yes")  # yes/no/generator
    has_network: Mapped[str] = mapped_column(String(16), default="yes")  # yes/no/limited
    has_climate_control: Mapped[bool] = mapped_column(Boolean, default=True)
    capacity_percent: Mapped[int] = mapped_column(Integer, default=100)
    damage_description: Mapped[str] = mapped_column(Text, default="")
    updated_by: Mapped[str] = mapped_column(String(64), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Incident(Base):
    __tablename__ = "incidents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    inc_type: Mapped[str] = mapped_column(String(32), default="other")
    # shelling/accident/flood/fire/wear/other
    description: Mapped[str] = mapped_column(Text, default="")
    affected_equipment_ids: Mapped[str] = mapped_column(String(128), default="")
    affected_facility_ids: Mapped[str] = mapped_column(String(128), default="")
    severity: Mapped[str] = mapped_column(String(16), default="medium")  # low/medium/high/critical
    status: Mapped[str] = mapped_column(String(16), default="new")  # new/in_progress/resolved/unrecoverable
    assigned_to: Mapped[str] = mapped_column(String(64), default="")
    resolution_notes: Mapped[str] = mapped_column(Text, default="")
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
