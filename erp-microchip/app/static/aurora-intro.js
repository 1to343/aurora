/* Aurora Intro Overlay — показывается один раз после входа в систему */
(function () {
  'use strict';

  const STORAGE_KEY = 'aurora_intro_seen';

  /* Интро показывается только для авторизованного пользователя (есть .top-nav)
     и только если флаг ещё не выставлен */
  if (
    !document.querySelector('.top-nav') ||
    localStorage.getItem(STORAGE_KEY) === 'true'
  ) return;

  localStorage.setItem(STORAGE_KEY, 'true');

  /* ── DOM-структура оверлея ─────────────────────────────────────────────── */
  const overlay = document.createElement('div');
  Object.assign(overlay.style, {
    position: 'fixed', inset: '0', zIndex: '99999',
    background: '#06060f', overflow: 'hidden',
  });

  const canvas = document.createElement('canvas');
  Object.assign(canvas.style, {
    position: 'absolute', inset: '0',
    width: '100%', height: '100%',
  });

  const logoWrap = document.createElement('div');
  Object.assign(logoWrap.style, {
    position: 'absolute', left: '50%', top: '50%',
    transform: 'translate(-50%,-50%)',
    borderRadius: '50%', background: '#fff',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    opacity: '0', pointerEvents: 'none',
    transition: 'none',
  });

  const logoText = document.createElement('span');
  logoText.textContent = 'AURORA';
  Object.assign(logoText.style, {
    fontFamily: "'Orbitron', sans-serif",
    fontWeight: '600',
    textTransform: 'uppercase',
    color: '#0a0a18',
  });

  const skipBtn = document.createElement('button');
  skipBtn.textContent = 'Пропустить';
  Object.assign(skipBtn.style, {
    position: 'absolute', bottom: '32px', right: '32px',
    background: 'transparent',
    border: '1px solid rgba(255,255,255,0.18)',
    color: 'rgba(255,255,255,0.35)',
    padding: '8px 20px', borderRadius: '8px',
    fontSize: '13px', cursor: 'pointer',
    fontFamily: 'Inter,sans-serif',
    transition: 'color .2s, border-color .2s',
    zIndex: '100000',
  });
  skipBtn.onmouseenter = () => {
    skipBtn.style.color = 'rgba(255,255,255,0.65)';
    skipBtn.style.borderColor = 'rgba(255,255,255,0.42)';
  };
  skipBtn.onmouseleave = () => {
    skipBtn.style.color = 'rgba(255,255,255,0.35)';
    skipBtn.style.borderColor = 'rgba(255,255,255,0.18)';
  };

  logoWrap.appendChild(logoText);
  overlay.appendChild(canvas);
  overlay.appendChild(logoWrap);
  overlay.appendChild(skipBtn);
  document.body.appendChild(overlay);

  /* Шрифт Orbitron */
  if (!document.querySelector('link[href*="Orbitron"]')) {
    const lnk = document.createElement('link');
    lnk.rel = 'stylesheet';
    lnk.href = 'https://fonts.googleapis.com/css2?family=Orbitron:wght@600&display=swap';
    document.head.appendChild(lnk);
  }

  /* ── Canvas / геометрия ────────────────────────────────────────────────── */
  const ctx = canvas.getContext('2d');
  let W, H, cx, cy, R;

  function resize() {
    W = canvas.width  = window.innerWidth;
    H = canvas.height = window.innerHeight;
    cx = W / 2; cy = H / 2;
    R  = Math.min(W, H) * 0.42;

    const sc = Math.min(W / 860, H / 660, 1);
    logoWrap.style.width  = (420 * sc) + 'px';
    logoWrap.style.height = (125 * sc) + 'px';
    logoText.style.fontSize     = (42 * sc) + 'px';
    logoText.style.letterSpacing = (12 * sc) + 'px';
    logoText.style.paddingLeft   = (12 * sc) + 'px'; /* визуальный центр с учётом letter-spacing */
  }
  resize();
  window.addEventListener('resize', resize);

  /* Сфера Фибоначчи — 320 точек на единичной сфере */
  const N   = 320;
  const PHI = Math.PI * (3 - Math.sqrt(5));
  const pts = [];
  for (let i = 0; i < N; i++) {
    const y  = 1 - (i / (N - 1)) * 2;
    const r  = Math.sqrt(1 - y * y);
    const th = PHI * i;
    pts.push({ x: Math.cos(th) * r, y, z: Math.sin(th) * r });
  }

  /* Предвычисляем рёбра (порог 0.44) */
  const edges = [];
  for (let i = 0; i < N; i++) {
    for (let j = i + 1; j < N; j++) {
      const dx = pts[i].x - pts[j].x;
      const dy = pts[i].y - pts[j].y;
      const dz = pts[i].z - pts[j].z;
      if (dx*dx + dy*dy + dz*dz < 0.44 * 0.44) edges.push([i, j]);
    }
  }

  /* Векторы взрыва частиц */
  const evx = new Float32Array(N);
  const evy = new Float32Array(N);
  const evz = new Float32Array(N);
  for (let i = 0; i < N; i++) {
    const p  = pts[i];
    const L  = Math.sqrt(p.x*p.x + p.y*p.y + p.z*p.z) || 1;
    evx[i] = p.x/L + (Math.random() - 0.5) * 0.45;
    evy[i] = p.y/L + (Math.random() - 0.5) * 0.45;
    evz[i] = p.z/L + (Math.random() - 0.5) * 0.45;
  }

  /* ── Временны́е фазы (сек) ──────────────────────────────────────────────── */
  const T_INTRO   = 0.8;   // 0      → 0.8   fade-in сферы
  const T_SPINUP  = 1.0;   // 0.8    → 1.8   разгон 1.8 → 3.5 рад/с
  const T_SQUASH  = 1.7;   // 1.8    → 3.5   сплющивание + разгон → 40 рад/с
  const T_EXPLODE = 0.9;   // 3.5    → 4.4   взрыв + появление лого
  const T_HOLD    = 2.0;   // 4.4    → 6.4   лого держится
  const T_FADEOUT = 1.8;   // 6.4    → 8.2   плавное затухание

  const P0 = T_INTRO;
  const P1 = P0 + T_SPINUP;
  const P2 = P1 + T_SQUASH;
  const P3 = P2 + T_EXPLODE;
  const P4 = P3 + T_HOLD;
  const P5 = P4 + T_FADEOUT;

  /* Easing */
  const easeOutCubic    = t => 1 - Math.pow(1 - t, 3);
  const easeOutQuad     = t => 1 - (1 - t) * (1 - t);
  const easeInCubic     = t => t * t * t;
  const easeInOutCubic  = t => t < 0.5 ? 4*t*t*t : 1 - Math.pow(-2*t + 2, 3) / 2;

  function clamp(v, a, b) { return v < a ? a : v > b ? b : v; }
  function inv(a, b, v)   { return clamp((v - a) / (b - a), 0, 1); }

  /* ── Состояние анимации ─────────────────────────────────────────────────── */
  let rotAngle = 0;
  let startTime = null;
  let lastTs    = null;
  let rafId     = null;
  let finished  = false;

  /* Массивы проекций (переиспользуем, чтобы не мусорить GC) */
  const projX  = new Float32Array(N);
  const projY  = new Float32Array(N);
  const projSc = new Float32Array(N);
  const projA  = new Float32Array(N);  /* opacity */
  const projPS = new Float32Array(N);  /* pointSize */

  const FOV = 3.2;

  function finish() {
    if (finished) return;
    finished = true;
    cancelAnimationFrame(rafId);
    window.removeEventListener('resize', resize);
    overlay.style.transition = 'opacity 0.38s ease';
    overlay.style.opacity    = '0';
    setTimeout(() => overlay.remove(), 400);
  }

  skipBtn.onclick = finish;

  /* ── Главный цикл ───────────────────────────────────────────────────────── */
  function frame(ts) {
    if (finished) return;
    if (!startTime) { startTime = ts; lastTs = ts; }
    const dt = Math.min((ts - lastTs) / 1000, 0.05);
    lastTs   = ts;
    const t  = (ts - startTime) / 1000;

    if (t > P5 + 0.05) { finish(); return; }
    rafId = requestAnimationFrame(frame);

    /* ── Вычисление параметров фазы ─ */
    let sphereAlpha = 0, rotSpeed = 0;
    let yScale = 1, zScale = 1;
    let explodeT = 0, logoAlpha = 0;
    let overlayAlpha = 1, glowAlpha = 0;

    if (t < P0) {
      /* Fade-in сферы */
      const ph = t / P0;
      sphereAlpha = easeOutCubic(ph);
      rotSpeed    = 1.8;

    } else if (t < P1) {
      /* Разгон вращения */
      const ph = inv(P0, P1, t);
      sphereAlpha = 1;
      rotSpeed    = 1.8 + (3.5 - 1.8) * easeOutQuad(ph);

    } else if (t < P2) {
      /* Раскрутка + сплющивание */
      const ph = inv(P1, P2, t);
      sphereAlpha = 1;
      rotSpeed    = 3.5 + (40 - 3.5) * easeInCubic(ph);
      yScale      = 1 + (0.035 - 1) * easeInOutCubic(ph);
      zScale      = 1 + (0.2   - 1) * easeInOutCubic(ph);
      if (ph > 0.2) glowAlpha = 0.12 * easeInOutCubic((ph - 0.2) / 0.8);

    } else if (t < P3) {
      /* Взрыв + появление лого */
      const ph = inv(P2, P3, t);
      rotSpeed    = 40;
      sphereAlpha = Math.max(0, 1 - ph * 4);          /* исчезают за 25% фазы */
      explodeT    = ph;
      yScale      = 0.035; zScale = 0.2;
      logoAlpha   = easeOutCubic(Math.min(1, ph / 0.4)); /* появляется за 40% */

    } else if (t < P4) {
      /* Удержание лого */
      logoAlpha = 1;

    } else {
      /* Затухание */
      const ph = inv(P4, P5, t);
      logoAlpha    = 1 - ph;
      overlayAlpha = 1 - easeInOutCubic(ph);
    }

    /* Накапливаем угол поворота */
    rotAngle += rotSpeed * dt;

    ctx.clearRect(0, 0, W, H);

    /* Свечение в центре при сплющивании */
    if (glowAlpha > 0.001) {
      const grd = ctx.createRadialGradient(cx, cy, 0, cx, cy, R * 0.55);
      grd.addColorStop(0, `rgba(70,175,255,${glowAlpha.toFixed(3)})`);
      grd.addColorStop(1, 'rgba(70,175,255,0)');
      ctx.fillStyle = grd;
      ctx.fillRect(0, 0, W, H);
    }

    /* ── Рисуем частицы ─ */
    if (sphereAlpha > 0.003 || explodeT > 0) {
      const cosA = Math.cos(rotAngle);
      const sinA = Math.sin(rotAngle);

      /* Линии исчезают быстрее — за первые 16% фазы взрыва */
      const linesFade = explodeT > 0 ? Math.max(0, 1 - explodeT / 0.16) : 1;

      /* Проецируем все точки */
      for (let i = 0; i < N; i++) {
        const p  = pts[i];
        let rx = p.x * cosA - p.z * sinA;
        let ry = p.y * yScale;
        let rz = (p.x * sinA + p.z * cosA) * zScale;

        if (explodeT > 0) {
          rx += evx[i] * explodeT * 7;
          ry += evy[i] * explodeT * 7;
          rz += evz[i] * explodeT * 7;
        }

        const sc = FOV / (FOV + rz + 1.5);
        projX[i]  = cx + rx * R * sc;
        projY[i]  = cy + ry * R * sc;
        projSc[i] = sc;

        const depth = 0.5 + 0.5 * clamp(rz / (zScale || 1), -1, 1);
        projA[i]  = sphereAlpha * (0.5 + depth * 0.5);
        projPS[i] = clamp((1.5 + depth * 1.0) * Math.max(sc, 0.15), 0.5, 4.0);
      }

      /* Рёбра */
      if (linesFade > 0.01 && sphereAlpha > 0.01) {
        ctx.lineWidth = 0.5;
        for (let e = 0; e < edges.length; e++) {
          const [i, j] = edges[e];
          const alpha  = Math.min(projA[i], projA[j]) * 0.28 * linesFade;
          if (alpha < 0.005) continue;
          ctx.strokeStyle = `rgba(70,175,255,${alpha.toFixed(3)})`;
          ctx.beginPath();
          ctx.moveTo(projX[i], projY[i]);
          ctx.lineTo(projX[j], projY[j]);
          ctx.stroke();
        }
      }

      /* Точки */
      for (let i = 0; i < N; i++) {
        const alpha = projA[i];
        if (alpha < 0.005) continue;
        ctx.fillStyle = `rgba(70,175,255,${alpha.toFixed(3)})`;
        ctx.beginPath();
        ctx.arc(projX[i], projY[i], projPS[i], 0, 6.2832);
        ctx.fill();
      }
    }

    /* Лого и оверлей */
    logoWrap.style.opacity = logoAlpha.toFixed(3);
    overlay.style.opacity  = overlayAlpha.toFixed(3);
  }

  rafId = requestAnimationFrame(frame);
})();
