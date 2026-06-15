from datetime import datetime
from pydantic import BaseModel, Field


# ---- Auth ----

class LoginIn(BaseModel):
    username: str
    password: str


# ---- WMS ----

class MaterialIn(BaseModel):
    sku: str
    name: str
    unit: str = "шт"
    is_hazmat: bool = False
    msds: str = ""
    reorder_point: float = 0
    shelf_life_days: int = 0


class ReceiptIn(BaseModel):
    material_id: int
    lot_no: str
    qty: float = Field(gt=0)
    cell_id: int
    expires_at: datetime | None = None


class TransferIn(BaseModel):
    material_id: int
    lot_id: int
    qty: float = Field(gt=0)
    from_cell_id: int
    to_cell_id: int
    note: str = ""


class IssueIn(BaseModel):
    material_id: int
    qty: float = Field(gt=0)
    from_cell_id: int | None = None
    work_order_id: int | None = None
    note: str = ""
    # выбор стратегии: fifo по received_at, fefo по expires_at
    strategy: str = "fifo"


# ---- Production ----

class StepIn(BaseModel):
    order_index: int
    name: str
    recipe: str = ""
    target_param: str = ""
    tolerance: str = ""


class WorkOrderIn(BaseModel):
    wo_no: str
    product_name: str
    qty_planned: int = Field(ge=1)
    due_date: datetime | None = None
    notes: str = ""
    steps: list[StepIn]


class OperationIn(BaseModel):
    lot_id: int
    measured_value: str = ""
    result: str = "pass"  # pass/fail
    defect_qty: int = 0
    note: str = ""
