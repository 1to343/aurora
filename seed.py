"""Создаёт пример данных: пользователи всех ролей, склад, материалы, WO с маршрутом."""
from datetime import datetime, timedelta

from app.db import Base, SessionLocal, engine
from app.models import (
    Cell,
    Equipment,
    Facility,
    Lot,
    LotStatus,
    Material,
    PowerEvent,
    Role,
    RouteSegment,
    RoutingStep,
    Shipment,
    Stock,
    TransportUnit,
    User,
    Warehouse,
    WorkOrder,
    WorkOrderStatus,
    Zone,
)
from app.security import hash_password


def run():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(User).count():
            print("Seed уже выполнен — пропускаю")
            return

        users = [
            ("admin", "admin", "Главный администратор", Role.ADMIN),
            ("director", "director", "Иван Директоров", Role.DIRECTOR),
            ("tech", "tech", "Анна Технолог", Role.TECHNOLOGIST),
            ("operator", "operator", "Пётр Оператор", Role.OPERATOR),
            ("shift", "shift", "Мария Начсмены", Role.SHIFT_LEAD),
            ("qc", "qc", "Ольга ОТК", Role.QC),
            ("logist", "logist", "Сергей Логист", Role.LOGISTICIAN),
            ("mech", "mech", "Андрей Механик", Role.MECHANIC),
            ("accountant", "accountant", "Елена Бухгалтер", Role.ACCOUNTANT),
        ]
        for u, p, fn, r in users:
            db.add(User(username=u, password_hash=hash_password(p), full_name=fn, role=r))

        # Склады/зоны/ячейки
        wh = Warehouse(code="WH1", name="Основной склад")
        db.add(wh)
        db.flush()
        zones = [
            Zone(warehouse_id=wh.id, code="GEN", name="Общая зона", zone_type="general"),
            Zone(warehouse_id=wh.id, code="CLIM", name="Климатическая (фоторезисты)", zone_type="climate"),
            Zone(warehouse_id=wh.id, code="HAZ", name="Опасные (кислоты, газы)", zone_type="hazmat"),
            Zone(warehouse_id=wh.id, code="QUAR", name="Карантин (вх. контроль)", zone_type="quarantine"),
        ]
        for z in zones:
            db.add(z)
        db.flush()
        cells = []
        for z in zones:
            for i in range(1, 4):
                c = Cell(zone_id=z.id, code=f"{z.code}-{i:02d}")
                db.add(c)
                cells.append(c)
        db.flush()

        # Материалы
        mats = [
            Material(sku="WAF-200", name="Пластины кремниевые 200 мм", unit="шт",
                     reorder_point=100),
            Material(sku="PR-A1", name="Фоторезист A1 (positive)", unit="л",
                     is_hazmat=True, msds="MSDS PR-A1 rev.3", reorder_point=20,
                     shelf_life_days=180),
            Material(sku="HF-49", name="Плавиковая кислота 49%", unit="л",
                     is_hazmat=True, msds="MSDS HF rev.2", reorder_point=10),
            Material(sku="AL-99", name="Алюминий 99.999% (для металлизации)", unit="кг",
                     reorder_point=5),
            Material(sku="PKG-DIP", name="Корпус DIP-40", unit="шт", reorder_point=500),
        ]
        for m in mats:
            db.add(m)
        db.flush()

        # Приёмка нескольких партий
        gen_cell = next(c for c in cells if c.code == "GEN-01")
        clim_cell = next(c for c in cells if c.code == "CLIM-01")
        haz_cell = next(c for c in cells if c.code == "HAZ-01")

        receipts = [
            (mats[0], "WAF-LOT-001", 500, gen_cell, None),
            (mats[0], "WAF-LOT-002", 300, gen_cell, None),
            (mats[1], "PR-LOT-001", 50, clim_cell, datetime.utcnow() + timedelta(days=120)),
            (mats[1], "PR-LOT-002", 25, clim_cell, datetime.utcnow() + timedelta(days=60)),
            (mats[2], "HF-LOT-001", 30, haz_cell, None),
            (mats[3], "AL-LOT-001", 20, gen_cell, None),
            (mats[4], "PKG-LOT-001", 1000, gen_cell, None),
        ]
        for m, lot_no, qty, cell, exp in receipts:
            lot = Lot(lot_no=lot_no, material_id=m.id, status=LotStatus.PASS,
                     received_at=datetime.utcnow(), expires_at=exp)
            db.add(lot)
            db.flush()
            db.add(Stock(material_id=m.id, lot_id=lot.id, cell_id=cell.id, qty=qty))

        # WO с типовым маршрутом
        wo = WorkOrder(
            wo_no="WO-2026-001",
            product_name="Чип SOC-X1",
            qty_planned=2,
            status=WorkOrderStatus.RELEASED,
            due_date=datetime.utcnow() + timedelta(days=14),
        )
        db.add(wo)
        db.flush()
        steps = [
            ("Литография", "PR-1", "толщина PR", "1.2±0.1 мкм"),
            ("Травление", "ET-2", "глубина", "0.5±0.05 мкм"),
            ("Диффузия", "DF-3", "температура", "1050°C±10"),
            ("Металлизация", "ME-4", "толщина Al", "0.8±0.05 мкм"),
            ("Корпусирование", "PK-5", "герметичность", "PASS"),
        ]
        for i, (n, rcp, tp, tol) in enumerate(steps, 1):
            db.add(RoutingStep(work_order_id=wo.id, order_index=i, name=n,
                              recipe=rcp, target_param=tp, tolerance=tol))

        # Стартуем одну партию пластин по WO
        prod_lot = Lot(
            lot_no="PROD-LOT-001",
            wafer_qty=25,
            status=LotStatus.IN_PROGRESS,
            work_order_id=wo.id,
            current_step_index=0,
        )
        db.add(prod_lot)

        # ---- Энергособытия (история за неделю) ----
        import random
        for d in range(7):
            for _ in range(random.randint(2, 4)):
                start = datetime.utcnow() - timedelta(days=d, hours=random.randint(0, 23))
                dur = random.randint(90, 150)
                db.add(PowerEvent(
                    start_time=start, end_time=start + timedelta(minutes=dur),
                    event_type="outage", source=random.choice(["ups", "generator", "none"]),
                    is_planned=random.random() < 0.3,
                    affected_zones=random.choice(["Цех №1", "Склад", "Лаборатория", "Весь объект"]),
                    created_by="system",
                ))

        # ---- Логистика ----
        segs = [
            ("Москва → Зеленоград", "Москва", "Зеленоград", "free"),
            ("Зеленоград → Цех", "Зеленоград", "Цех", "free"),
            ("Цех → Тест-лаб", "Цех", "Тест-лаб", "hard"),
            ("Тест-лаб → Склад ГП", "Тест-лаб", "Склад ГП", "free"),
            ("Склад ГП → Отгрузка", "Склад ГП", "Отгрузка", "blocked"),
        ]
        for n, a, b, st in segs:
            db.add(RouteSegment(name=n, from_point=a, to_point=b, status=st,
                                blocked_reason="Разрушенная дорога" if st == "blocked" else ""))

        transport = [
            ("truck", 5000, "available", "Склад сырья"),
            ("truck", 8000, "in_transit", "В пути"),
            ("van", 1500, "available", "Цех"),
            ("forklift", 2000, "repair", "Гараж"),
            ("cart", 300, "available", "Склад ГП"),
            ("truck", 5000, "destroyed", "—"),
        ]
        for tt, cap, st, loc in transport:
            db.add(TransportUnit(unit_type=tt, capacity_kg=cap, status=st, current_location=loc))

        ships = [
            ("in", "critical", "Si пластины 300мм", "Тайвань", "Склад сырья", "truck", "delayed", "Разрушенная дорога", 240),
            ("in", "high", "Фоторезист AZ-5214", "Москва", "Склад сырья", "truck", "in_transit", "", 0),
            ("out", "medium", "Готовые чипы SOC-X1", "Склад ГП", "Берлин", "rail", "planned", "", 0),
            ("in", "high", "Золотая проволока", "Цюрих", "Склад сырья", "drone", "loading", "", 0),
            ("out", "low", "Тестовые образцы", "Цех", "Тест-лаб", "manual", "delivered", "", 0),
            ("in", "critical", "Маски литографии", "Япония", "Склад сырья", "truck", "delayed", "Проверка на КПП", 180),
        ]
        for tp, pr, cont, org, dst, tr, st, dr, dm in ships:
            db.add(Shipment(ship_type=tp, priority=pr, contents=cont, origin=org, destination=dst,
                            transport_type=tr, status=st, delay_reason=dr, delay_minutes=dm,
                            planned_eta=datetime.utcnow() + timedelta(hours=random.randint(2, 48)),
                            created_by="logist"))

        # ---- Инфраструктура ----
        equipment = [
            ("Сканер ASML PAS5500", "литография", "Цех №1, уч. 1", "working"),
            ("Plasma Etch LAM", "травление", "Цех №1, уч. 2", "limited"),
            ("Ion Implanter AMAT", "легирование", "Цех №1, уч. 3", "working"),
            ("CVD/Furnace TEL", "осаждение", "Цех №1, уч. 4", "stopped"),
            ("ATE Teradyne J750", "тестирование", "Тест-лаб", "working"),
            ("Disco DAD3350", "нарезка", "Цех №2", "damaged"),
            ("Wire Bonder K&S", "разварка", "Цех №2", "working"),
            ("CMP Ebara", "планаризация", "Цех №1, уч. 5", "destroyed"),
        ]
        for n, t, loc, st in equipment:
            db.add(Equipment(name=n, eq_type=t, location=loc, status=st,
                             last_maintenance=datetime.utcnow() - timedelta(days=random.randint(10, 60)),
                             next_maintenance=datetime.utcnow() + timedelta(days=random.randint(5, 30)),
                             condition_notes="" if st == "working" else "Требует внимания", updated_by="mech"))

        facilities = [
            ("Цех №1 (литография)", "производственный цех", "limited", "generator", "limited", True, 60),
            ("Цех №2 (сборка)", "производственный цех", "working", "yes", "yes", True, 100),
            ("Склад сырья", "склад", "working", "yes", "yes", True, 90),
            ("Склад ГП", "склад", "limited", "no", "limited", False, 70),
            ("Тест-лаборатория", "лаборатория", "working", "generator", "yes", True, 100),
            ("Серверная", "серверная", "limited", "generator", "yes", True, 80),
            ("Офис", "офис", "down", "no", "no", False, 0),
        ]
        for n, t, st, pw, nw, cc, cap in facilities:
            db.add(Facility(name=n, fac_type=t, status=st, has_power=pw, has_network=nw,
                            has_climate_control=cc, capacity_percent=cap,
                            damage_description="" if st == "working" else "Частичные повреждения", updated_by="shift"))

        db.commit()
        print("OK Seed выполнен. Пользователи admin/admin, operator/operator, i t.d.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
