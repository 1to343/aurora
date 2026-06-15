const pptxgen = require("pptxgenjs");
const path = require("path");

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9";
pres.author = "Aurora ERP Team";
pres.title = "Aurora ERP — Питч";

// Constants
const BG = "0A0E1A";
const CYAN = "00D4FF";
const GREEN = "00FF88";
const WHITE = "FFFFFF";
const LGRAY = "C8CCD8";
const MGRAY = "8B8FA3";
const DGRAY = "5A5E72";
const CARD_BG = "111827";
const CARD_BORDER = "1A2744";

const makeShadow = () => ({ type: "outer", color: "000000", blur: 8, offset: 3, angle: 45, opacity: 0.35 });

// ============================================================
// SLIDE 1 — Title
// ============================================================
{
  const s = pres.addSlide();
  s.background = { color: BG };

  // Decorative glow circle (large, faint)
  s.addShape(pres.shapes.OVAL, {
    x: 2.5, y: -0.5, w: 5, h: 5,
    fill: { color: CYAN, transparency: 93 },
  });

  s.addText("AURORA ERP", {
    x: 0.5, y: 1.1, w: 9, h: 1.2,
    fontSize: 52, fontFace: "Calibri", bold: true,
    color: CYAN, align: "center", charSpacing: 8, margin: 0,
  });

  s.addText("Интеллектуальная платформа управления\nпроизводством микрочипов", {
    x: 1, y: 2.35, w: 8, h: 1.1,
    fontSize: 20, fontFace: "Calibri",
    color: LGRAY, align: "center", lineSpacingMultiple: 1.3,
  });

  // Tech stack chips
  const stack = "Python  ·  FastAPI  ·  SQLAlchemy  ·  Canvas 3D  ·  Bootstrap 5";
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x: 1.6, y: 3.75, w: 6.8, h: 0.55,
    fill: { color: CYAN, transparency: 88 },
    rectRadius: 0.15,
  });
  s.addText(stack, {
    x: 1.6, y: 3.75, w: 6.8, h: 0.55,
    fontSize: 12, fontFace: "Calibri",
    color: CYAN, align: "center", valign: "middle", margin: 0,
  });

  s.addText("ERP-система класса Enterprise Resource Planning", {
    x: 1, y: 4.7, w: 8, h: 0.5,
    fontSize: 11, fontFace: "Calibri",
    color: DGRAY, align: "center",
  });

  s.addNotes("Титульный слайд. Представиться, назвать проект Aurora ERP — отечественная платформа для управления производством микрочипов.");
}

// ============================================================
// SLIDE 2 — Team
// ============================================================
{
  const s = pres.addSlide();
  s.background = { color: BG };

  s.addText("Команда разработки", {
    x: 0.5, y: 0.4, w: 9, h: 0.8,
    fontSize: 36, fontFace: "Calibri", bold: true,
    color: WHITE, align: "center", margin: 0,
  });

  const members = [
    "Вячеслав Торопин",
    "Владимир Герцог",
    "Полина Черниенко",
    "Ярослав Рыбинцов",
    "Мария Демахина",
  ];

  members.forEach((name, i) => {
    const yy = 1.55 + i * 0.72;

    // Avatar circle
    s.addShape(pres.shapes.OVAL, {
      x: 2.9, y: yy + 0.05, w: 0.42, h: 0.42,
      fill: { color: i % 2 === 0 ? CYAN : GREEN, transparency: 70 },
    });
    s.addText(name[0], {
      x: 2.9, y: yy + 0.05, w: 0.42, h: 0.42,
      fontSize: 14, fontFace: "Calibri", bold: true,
      color: WHITE, align: "center", valign: "middle", margin: 0,
    });

    s.addText(name, {
      x: 3.5, y: yy, w: 4, h: 0.52,
      fontSize: 20, fontFace: "Calibri",
      color: LGRAY, align: "left", valign: "middle", margin: 0,
    });
  });

  s.addNotes("Представить каждого члена команды. 5 человек — полный цикл разработки: backend, frontend, 3D-визуализация, база данных, дизайн.");
}

// ============================================================
// SLIDE 3 — Global Challenge
// ============================================================
{
  const s = pres.addSlide();
  s.background = { color: BG };

  s.addText("Проблема: зависимость от западных ERP", {
    x: 0.5, y: 0.35, w: 9, h: 0.8,
    fontSize: 32, fontFace: "Calibri", bold: true,
    color: WHITE, align: "left", margin: 0,
  });

  const points = [
    { head: "Уход вендоров", body: "SAP, Oracle, Siemens — ушли из России, отключили лицензии и поддержку" },
    { head: "Стратегическая отрасль", body: "Производство микрочипов нельзя ставить в зависимость от иностранного ПО" },
    { head: "Нет аналогов", body: "Российские ERP не учитывают специфику полупроводникового производства" },
    { head: "Что нужно рынку", body: "Отечественная, автономная система, устойчивая к сбоям инфраструктуры" },
  ];

  points.forEach((p, i) => {
    const yy = 1.45 + i * 1.0;

    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x: 0.5, y: yy, w: 9, h: 0.82,
      fill: { color: CARD_BG, transparency: 30 },
      rectRadius: 0.1,
    });

    s.addText(p.head, {
      x: 0.85, y: yy + 0.08, w: 2.6, h: 0.32,
      fontSize: 15, fontFace: "Calibri", bold: true,
      color: CYAN, align: "left", valign: "middle", margin: 0,
    });

    s.addText(p.body, {
      x: 0.85, y: yy + 0.38, w: 8.3, h: 0.36,
      fontSize: 13, fontFace: "Calibri",
      color: LGRAY, align: "left", valign: "top", margin: 0,
    });
  });

  s.addNotes("Описать проблему: западные ERP ушли, стратегическая зависимость, нет отечественных аналогов для полупроводников. Подчеркнуть критичность.");
}

// ============================================================
// SLIDE 4 — Solution
// ============================================================
{
  const s = pres.addSlide();
  s.background = { color: BG };

  s.addText("Aurora ERP — что решает наш проект", {
    x: 0.5, y: 0.35, w: 9, h: 0.8,
    fontSize: 32, fontFace: "Calibri", bold: true,
    color: WHITE, align: "left", margin: 0,
  });

  const items = [
    { icon: "01", title: "Сквозное управление", desc: "От сырья до готового чипа в одной системе" },
    { icon: "02", title: "Прослеживаемость", desc: "Полная lot traceability на каждом этапе техпроцесса" },
    { icon: "03", title: "9 ролей с RBAC", desc: "От оператора до директора + полный аудит-лог" },
    { icon: "04", title: "Модули", desc: "Склад (WMS) · Производство (MES) · Логистика · Чат · KPI" },
    { icon: "05", title: "3D-визуализация", desc: "Живая симуляция и интерактивное дерево техпроцесса" },
    { icon: "06", title: "FIFO / FEFO", desc: "Умные стратегии управления складскими запасами" },
  ];

  // Two columns of cards
  items.forEach((it, i) => {
    const col = i < 3 ? 0 : 1;
    const row = i % 3;
    const xx = 0.5 + col * 4.7;
    const yy = 1.4 + row * 1.28;

    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x: xx, y: yy, w: 4.4, h: 1.08,
      fill: { color: CARD_BG, transparency: 25 },
      rectRadius: 0.1,
      shadow: makeShadow(),
    });

    // Number badge
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x: xx + 0.18, y: yy + 0.2, w: 0.52, h: 0.52,
      fill: { color: CYAN, transparency: 78 },
      rectRadius: 0.08,
    });
    s.addText(it.icon, {
      x: xx + 0.18, y: yy + 0.2, w: 0.52, h: 0.52,
      fontSize: 14, fontFace: "Calibri", bold: true,
      color: CYAN, align: "center", valign: "middle", margin: 0,
    });

    s.addText(it.title, {
      x: xx + 0.85, y: yy + 0.12, w: 3.3, h: 0.4,
      fontSize: 15, fontFace: "Calibri", bold: true,
      color: WHITE, align: "left", valign: "middle", margin: 0,
    });

    s.addText(it.desc, {
      x: xx + 0.85, y: yy + 0.52, w: 3.3, h: 0.42,
      fontSize: 12, fontFace: "Calibri",
      color: LGRAY, align: "left", valign: "top", margin: 0,
    });
  });

  s.addNotes("Перечислить ключевые возможности: сквозное управление, прослеживаемость, роли, модули. Акцент на 3D-визуализацию — уникальное преимущество.");
}

// ============================================================
// SLIDE 5 — Resilience
// ============================================================
{
  const s = pres.addSlide();
  s.background = { color: BG };

  s.addText("Работа без интернета, связи и электричества", {
    x: 0.5, y: 0.3, w: 9, h: 0.7,
    fontSize: 28, fontFace: "Calibri", bold: true,
    color: WHITE, align: "left", margin: 0,
  });

  // Three columns
  const cols = [
    {
      title: "ЭЛЕКТРИЧЕСТВО",
      color: GREEN,
      items: [
        "Мониторинг питания:\nсеть / ИБП / генератор",
        "Режим энергосбережения —\nотключает тяжёлые эффекты",
        "Таймер работы от\nрезервного источника",
      ],
    },
    {
      title: "ИНТЕРНЕТ И СВЯЗЬ",
      color: CYAN,
      items: [
        "Service Worker —\nполный офлайн-режим",
        "Очередь операций\nв IndexedDB",
        "Автосинхронизация\nпри восстановлении",
        "Индикатор связи:\nонлайн / нестабильно / офлайн",
      ],
    },
    {
      title: "ДАННЫЕ",
      color: "FFB86B",
      items: [
        "Автосохранение черновиков\nкаждые 5 секунд",
        "Восстановление форм\nпосле перезагрузки",
        "localStorage + IndexedDB\nдля локального хранения",
      ],
    },
  ];

  cols.forEach((col, ci) => {
    const xx = 0.35 + ci * 3.15;
    const colW = 3.0;

    // Column card
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x: xx, y: 1.15, w: colW, h: 4.15,
      fill: { color: CARD_BG, transparency: 20 },
      rectRadius: 0.12,
      shadow: makeShadow(),
    });

    // Column header
    s.addText(col.title, {
      x: xx, y: 1.3, w: colW, h: 0.45,
      fontSize: 13, fontFace: "Calibri", bold: true,
      color: col.color, align: "center", valign: "middle", margin: 0,
      charSpacing: 2,
    });

    // Items
    col.items.forEach((item, ii) => {
      const iy = 1.95 + ii * 0.8;
      s.addText(item, {
        x: xx + 0.2, y: iy, w: colW - 0.4, h: 0.7,
        fontSize: 11, fontFace: "Calibri",
        color: LGRAY, align: "center", valign: "top",
        lineSpacingMultiple: 1.2, margin: 0,
      });
    });
  });

  s.addNotes("Ключевой слайд — отличие от конкурентов. Система работает при полном отключении инфраструктуры. Service Worker, IndexedDB, мониторинг питания.");
}

// ============================================================
// SLIDE 6 — Architecture / Tech Stack
// ============================================================
{
  const s = pres.addSlide();
  s.background = { color: BG };

  s.addText("Технологический стек", {
    x: 0.5, y: 0.35, w: 9, h: 0.8,
    fontSize: 32, fontFace: "Calibri", bold: true,
    color: WHITE, align: "left", margin: 0,
  });

  const layers = [
    { label: "Backend", value: "Python 3.14, FastAPI, SQLAlchemy 2.0", color: CYAN },
    { label: "База данных", value: "SQLite / PostgreSQL (переключается через DATABASE_URL)", color: CYAN },
    { label: "Аутентификация", value: "JWT в httpOnly-cookie, bcrypt (passlib)", color: GREEN },
    { label: "Frontend", value: "Vanilla JavaScript, Bootstrap 5, Chart.js", color: "FFB86B" },
    { label: "3D / визуализация", value: "Canvas API + CSS 3D Transforms (без Three.js)", color: "BF6BFF" },
    { label: "Офлайн", value: "Service Worker + IndexedDB + localStorage", color: GREEN },
  ];

  layers.forEach((l, i) => {
    const yy = 1.35 + i * 0.63;

    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x: 0.5, y: yy, w: 9, h: 0.52,
      fill: { color: CARD_BG, transparency: 35 },
      rectRadius: 0.08,
    });

    s.addText(l.label, {
      x: 0.75, y: yy, w: 2.3, h: 0.52,
      fontSize: 13, fontFace: "Calibri", bold: true,
      color: l.color, align: "left", valign: "middle", margin: 0,
    });

    s.addText(l.value, {
      x: 3.1, y: yy, w: 6.2, h: 0.52,
      fontSize: 13, fontFace: "Calibri",
      color: LGRAY, align: "left", valign: "middle", margin: 0,
    });
  });

  // Bottom tagline
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x: 1.2, y: 4.7, w: 7.6, h: 0.55,
    fill: { color: CYAN, transparency: 90 },
    rectRadius: 0.1,
  });
  s.addText("Минимум зависимостей — максимум автономности. Работает на любом сервере без облака.", {
    x: 1.2, y: 4.7, w: 7.6, h: 0.55,
    fontSize: 12, fontFace: "Calibri", italic: true,
    color: CYAN, align: "center", valign: "middle", margin: 0,
  });

  s.addNotes("Подчеркнуть: минимум зависимостей, нет тяжёлых фреймворков (React, Three.js), легко развернуть на любом сервере. PostgreSQL для масштабирования.");
}

// ============================================================
// SLIDE 7 — Value for Russia
// ============================================================
{
  const s = pres.addSlide();
  s.background = { color: BG };

  s.addText("Значение для России", {
    x: 0.5, y: 0.35, w: 9, h: 0.8,
    fontSize: 32, fontFace: "Calibri", bold: true,
    color: WHITE, align: "left", margin: 0,
  });

  const benefits = [
    { title: "Импортозамещение", desc: "Полностью отечественная разработка, не зависит от западных лицензий", color: CYAN },
    { title: "Технологический суверенитет", desc: "Контроль над критической инфраструктурой производства чипов", color: GREEN },
    { title: "Готовность к кризисам", desc: "Работает при отключении интернета и электричества", color: "FFB86B" },
    { title: "Масштабируемость", desc: "От пилотного участка до полноценного завода (PostgreSQL, модули)", color: "BF6BFF" },
    { title: "Прозрачность", desc: "Полный аудит-лог, соответствие требованиям регуляторов", color: CYAN },
    { title: "Кадровый потенциал", desc: "Обучение специалистов на отечественном ПО", color: GREEN },
  ];

  // Two columns
  benefits.forEach((b, i) => {
    const col = i < 3 ? 0 : 1;
    const row = i % 3;
    const xx = 0.5 + col * 4.7;
    const yy = 1.35 + row * 1.3;

    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x: xx, y: yy, w: 4.4, h: 1.1,
      fill: { color: CARD_BG, transparency: 25 },
      rectRadius: 0.1,
      shadow: makeShadow(),
    });

    s.addText(b.title, {
      x: xx + 0.3, y: yy + 0.15, w: 3.8, h: 0.38,
      fontSize: 15, fontFace: "Calibri", bold: true,
      color: b.color, align: "left", valign: "middle", margin: 0,
    });

    s.addText(b.desc, {
      x: xx + 0.3, y: yy + 0.55, w: 3.8, h: 0.4,
      fontSize: 12, fontFace: "Calibri",
      color: LGRAY, align: "left", valign: "top", margin: 0,
    });
  });

  s.addNotes("Ключевые тезисы для комиссии: импортозамещение, суверенитет, кризисоустойчивость. Акцент — это не просто учебный проект, а реальная потребность рынка.");
}

// ============================================================
// SLIDE 8 — Final / Thank You
// ============================================================
{
  const s = pres.addSlide();
  s.background = { color: BG };

  // Decorative glow
  s.addShape(pres.shapes.OVAL, {
    x: 2.5, y: 0.5, w: 5, h: 4,
    fill: { color: CYAN, transparency: 94 },
  });

  s.addText("AURORA ERP", {
    x: 0.5, y: 1.3, w: 9, h: 1.1,
    fontSize: 48, fontFace: "Calibri", bold: true,
    color: CYAN, align: "center", charSpacing: 8, margin: 0,
  });

  s.addText("Российская платформа для производства микрочипов", {
    x: 1, y: 2.5, w: 8, h: 0.7,
    fontSize: 18, fontFace: "Calibri",
    color: LGRAY, align: "center",
  });

  s.addText("Спасибо за внимание", {
    x: 1, y: 3.6, w: 8, h: 0.7,
    fontSize: 24, fontFace: "Calibri", bold: true,
    color: WHITE, align: "center",
  });

  s.addText("aurora-erp@team.ru", {
    x: 1, y: 4.6, w: 8, h: 0.5,
    fontSize: 12, fontFace: "Calibri",
    color: DGRAY, align: "center",
  });

  s.addNotes("Финальный слайд. Поблагодарить за внимание, предложить демонстрацию системы.");
}

// ============================================================
// Save
// ============================================================
const outPath = path.join(__dirname, "Aurora_ERP_Pitch.pptx");
pres.writeFile({ fileName: outPath }).then(() => {
  console.log("Presentation saved to:", outPath);
}).catch((err) => {
  console.error("Error:", err);
  process.exit(1);
});
