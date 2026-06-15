// Декоративные эффекты на каждой странице:
//  - левая панель «Цепь данных» (поднимающиеся частицы)
//  - правая панель «Код потока» (Matrix-стиль + вертикальный водяной знак)
//  - фоновая пульсирующая точечная сетка
//  - курсор-трейл
// Чистый Canvas + requestAnimationFrame. pointer-events:none везде.

(function () {
  const PW = 56; // ширина боковой панели

  function accent() { return window.PAGE_ACCENT || '#00d4ff'; }
  function label() { return window.PAGE_LABEL || 'ERP'; }

  function hexToRgb(h) {
    h = (h || '#00d4ff').replace('#', '');
    if (h.length === 3) h = h.split('').map((c) => c + c).join('');
    const n = parseInt(h, 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  }
  function rgba(h, a) { const [r, g, b] = hexToRgb(h); return `rgba(${r},${g},${b},${a})`; }

  function mkCanvas(z) {
    const c = document.createElement('canvas');
    c.style.cssText = `position:fixed;pointer-events:none;z-index:${z};`;
    document.body.appendChild(c);
    return c;
  }

  const bg = mkCanvas(0);
  const left = mkCanvas(90);
  const right = mkCanvas(90);
  const trail = mkCanvas(9998);
  const bgx = bg.getContext('2d');
  const lx = left.getContext('2d');
  const rx = right.getContext('2d');
  const tx = trail.getContext('2d');
  const dpr = Math.min(window.devicePixelRatio || 1, 2);

  let navH = 0, W = 0, H = 0, panelH = 0;

  function layout() {
    const nav = document.querySelector('.top-nav');
    navH = nav ? nav.getBoundingClientRect().height : 0;
    W = window.innerWidth; H = window.innerHeight; panelH = H - navH;

    function size(cv, ctx, x, y, w, h) {
      cv.style.left = x; cv.style.top = y;
      cv.style.width = w + 'px'; cv.style.height = h + 'px';
      cv.width = w * dpr; cv.height = h * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    size(bg, bgx, '0', '0', W, H);
    size(trail, tx, '0', '0', W, H);
    bg.style.right = ''; trail.style.right = '';
    size(left, lx, '0', navH + 'px', PW, panelH);
    // правая панель — позиционируем через right:0
    right.style.right = '0'; right.style.left = '';
    right.style.top = navH + 'px';
    right.style.width = PW + 'px'; right.style.height = panelH + 'px';
    right.width = PW * dpr; right.height = panelH * dpr;
    rx.setTransform(dpr, 0, 0, dpr, 0, 0);

    initLeft(); initRight();
  }
  window.addEventListener('resize', layout);

  // ---- ускорение частиц при активных событиях ----
  let boostUntil = 0;
  function boost() { boostUntil = performance.now() + 2500; }
  function boosting() { return performance.now() < boostUntil; }
  if (window.ErpSim && typeof ErpSim.on === 'function') {
    ['replenish', 'defect', 'complete', 'tick'].forEach((e) => { try { ErpSim.on(e, boost); } catch (_) {} });
  }

  // ---- Левая панель: цепь данных ----
  let particles = [], diamonds = [];
  function initLeft() {
    particles = [];
    const n = 10;
    for (let i = 0; i < n; i++) {
      particles.push({ y: Math.random() * panelH, r: 2 + Math.random() * 3, sp: 0.6 + Math.random() * 1.8, jit: (Math.random() - 0.5) * 6 });
    }
    diamonds = [];
    const step = 70;
    for (let y = step; y < panelH; y += step) diamonds.push({ y, flash: 0 });
  }
  function drawLeft() {
    lx.clearRect(0, 0, PW, panelH);
    const cx = PW / 2;
    const col = accent();
    // вертикальная линия
    lx.strokeStyle = rgba(col, 0.28);
    lx.lineWidth = 1;
    lx.beginPath(); lx.moveTo(cx, 0); lx.lineTo(cx, panelH); lx.stroke();
    // ромбы-узлы
    diamonds.forEach((d) => {
      const a = 0.25 + d.flash * 0.75;
      lx.save(); lx.translate(cx, d.y); lx.rotate(Math.PI / 4);
      lx.fillStyle = rgba(col, a);
      const s = 3 + d.flash * 2;
      lx.fillRect(-s / 2, -s / 2, s, s);
      lx.restore();
      d.flash *= 0.88;
    });
    // частицы
    const mult = boosting() ? 2.4 : 1;
    particles.forEach((p) => {
      p.y -= p.sp * mult;
      if (p.y < -4) { p.y = panelH + Math.random() * 30; p.jit = (Math.random() - 0.5) * 6; }
      const x = cx + p.jit;
      // вспышка ромба при прохождении
      diamonds.forEach((d) => { if (Math.abs(d.y - p.y) < 5) d.flash = Math.min(1, d.flash + 0.6); });
      const fade = p.y < 40 ? p.y / 40 : 1;
      lx.beginPath();
      lx.fillStyle = rgba(col, 0.9 * fade);
      lx.shadowColor = col; lx.shadowBlur = 8;
      lx.arc(x, p.y, p.r, 0, Math.PI * 2); lx.fill();
      lx.shadowBlur = 0;
    });
    // индикатор «система активна»
    const t = performance.now() / 600;
    const pr = 3 + Math.sin(t) * 1.5;
    lx.beginPath(); lx.fillStyle = rgba('#00ff88', 0.8);
    lx.shadowColor = '#00ff88'; lx.shadowBlur = 10;
    lx.arc(cx, 16, pr, 0, Math.PI * 2); lx.fill(); lx.shadowBlur = 0;
  }

  // ---- Правая панель: код потока ----
  const POOL = '0123456789ABCDEF01◆▪●';
  const CELL_W = 11, CELL_H = 13;
  let cols = [];
  let flashes = [];
  let lastFlashAt = 0, nextFlash = 3000;
  function randCh() { return POOL[Math.floor(Math.random() * POOL.length)]; }
  function initRight() {
    const nCols = Math.max(1, Math.floor(PW / CELL_W));
    const nRows = Math.ceil(panelH / CELL_H) + 2;
    cols = [];
    for (let c = 0; c < nCols; c++) {
      const chars = [];
      for (let r = 0; r < nRows; r++) chars.push(randCh());
      cols.push({ chars, off: Math.random() * CELL_H, sp: 0.3 + Math.random() * 0.5, rows: nRows });
    }
    flashes = [];
  }
  function drawRight() {
    rx.clearRect(0, 0, PW, panelH);
    rx.font = `${CELL_H - 2}px 'JetBrains Mono', monospace`;
    rx.textAlign = 'center';
    const baseCol = '#00ff88';
    const now = performance.now();
    if (now - lastFlashAt > nextFlash) {
      lastFlashAt = now; nextFlash = 3000 + Math.random() * 2000;
      const c = Math.floor(Math.random() * cols.length);
      const r = Math.floor(Math.random() * cols[c].rows);
      flashes.push({ c, r, t0: now });
    }
    cols.forEach((col, ci) => {
      col.off += col.sp;
      if (col.off >= CELL_H) { col.off -= CELL_H; col.chars.pop(); col.chars.unshift(randCh()); }
      const x = ci * CELL_W + CELL_W / 2;
      col.chars.forEach((ch, ri) => {
        const y = ri * CELL_H + col.off;
        const bright = Math.random() < 0.04;
        rx.fillStyle = bright ? rgba(baseCol, 0.5) : rgba(baseCol, 0.15);
        rx.fillText(ch, x, y);
      });
    });
    // вспышки акцентом
    flashes = flashes.filter((f) => now - f.t0 < 500);
    flashes.forEach((f) => {
      const x = f.c * CELL_W + CELL_W / 2;
      const y = f.r * CELL_H + cols[f.c].off;
      rx.fillStyle = rgba(accent(), 0.95);
      rx.shadowColor = accent(); rx.shadowBlur = 8;
      rx.fillText(cols[f.c].chars[f.r] || randCh(), x, y);
      rx.shadowBlur = 0;
    });
    // вертикальный водяной знак
    rx.save();
    rx.translate(PW / 2, panelH / 2);
    rx.rotate(-Math.PI / 2);
    rx.font = `600 12px 'JetBrains Mono', monospace`;
    rx.fillStyle = 'rgba(255,255,255,0.08)';
    rx.textAlign = 'center';
    rx.fillText(label().split('').join(' '), 0, 0);
    rx.restore();
  }

  // ---- Фоновая точечная сетка ----
  let pulseDot = null, pulseAt = 0;
  function drawBg() {
    bgx.clearRect(0, 0, W, H);
    const step = 40;
    const col = accent();
    const now = performance.now();
    if (now - pulseAt > 5000) {
      pulseAt = now;
      pulseDot = { gx: Math.floor(Math.random() * (W / step)) * step, gy: Math.floor(Math.random() * (H / step)) * step, t0: now };
    }
    for (let x = step; x < W; x += step) {
      for (let y = step; y < H; y += step) {
        bgx.fillStyle = rgba(col, 0.04);
        bgx.fillRect(x - 1, y - 1, 2, 2);
      }
    }
    if (pulseDot) {
      const dt = (now - pulseDot.t0) / 2000;
      if (dt <= 1) {
        const a = 0.04 + Math.sin(dt * Math.PI) * 0.13;
        bgx.fillStyle = rgba(col, a);
        bgx.shadowColor = col; bgx.shadowBlur = 8;
        bgx.fillRect(pulseDot.gx - 2, pulseDot.gy - 2, 4, 4);
        bgx.shadowBlur = 0;
      }
    }
  }

  // ---- Курсор-трейл ----
  const TRAIL_N = 6;
  let tps = Array.from({ length: TRAIL_N }, () => ({ x: -50, y: -50 }));
  let mouse = { x: -50, y: -50 };
  window.addEventListener('mousemove', (e) => { mouse.x = e.clientX; mouse.y = e.clientY; });
  function drawTrail() {
    tx.clearRect(0, 0, W, H);
    tps[0].x += (mouse.x - tps[0].x) * 0.5;
    tps[0].y += (mouse.y - tps[0].y) * 0.5;
    for (let i = 1; i < TRAIL_N; i++) {
      tps[i].x += (tps[i - 1].x - tps[i].x) * 0.3;
      tps[i].y += (tps[i - 1].y - tps[i].y) * 0.3;
    }
    const col = accent();
    for (let i = 0; i < TRAIL_N; i++) {
      const k = 1 - i / TRAIL_N;
      tx.beginPath();
      tx.fillStyle = rgba(col, 0.1 + k * 0.3);
      tx.shadowColor = col; tx.shadowBlur = 6;
      tx.arc(tps[i].x, tps[i].y, 2 + k * 3, 0, Math.PI * 2);
      tx.fill();
    }
    tx.shadowBlur = 0;
  }

  function loop() {
    drawBg();
    drawLeft();
    drawRight();
    drawTrail();
    requestAnimationFrame(loop);
  }

  function start() { layout(); requestAnimationFrame(loop); }
  if (document.readyState !== 'loading') start();
  else document.addEventListener('DOMContentLoaded', start);
})();
