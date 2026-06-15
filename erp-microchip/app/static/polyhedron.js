// 3D-полиэдр на чистом canvas. Никаких зависимостей.
(function () {
  const phi = (1 + Math.sqrt(5)) / 2;

  function perms(arr, signs) {
    // Все перестановки + знаки нулевых координат
    const out = [];
    const sigCombos = (n) => {
      const r = [];
      for (let i = 0; i < (1 << n); i++) {
        const s = [];
        for (let b = 0; b < n; b++) s.push(i & (1 << b) ? -1 : 1);
        r.push(s);
      }
      return r;
    };
    const flips = sigCombos(arr.length);
    for (const f of flips) {
      const v = arr.map((x, i) => x * f[i]);
      if (!out.some((p) => p.every((c, i) => Math.abs(c - v[i]) < 1e-6))) out.push(v);
    }
    return out;
  }

  function shapes() {
    const I = [];
    // икосаэдр
    [[0, 1, phi], [0, 1, -phi], [0, -1, phi], [0, -1, -phi]].forEach((v) => I.push(v));
    [[1, phi, 0], [1, -phi, 0], [-1, phi, 0], [-1, -phi, 0]].forEach((v) => I.push(v));
    [[phi, 0, 1], [phi, 0, -1], [-phi, 0, 1], [-phi, 0, -1]].forEach((v) => I.push(v));

    // куб
    const C = [];
    for (let x of [-1, 1]) for (let y of [-1, 1]) for (let z of [-1, 1]) C.push([x, y, z]);

    // октаэдр
    const O = [[1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1]];

    // тетраэдр
    const T = [[1, 1, 1], [1, -1, -1], [-1, 1, -1], [-1, -1, 1]];

    // додекаэдр
    const D = [];
    for (let x of [-1, 1]) for (let y of [-1, 1]) for (let z of [-1, 1]) D.push([x, y, z]);
    [[0, 1 / phi, phi], [0, 1 / phi, -phi], [0, -1 / phi, phi], [0, -1 / phi, -phi]].forEach((v) => D.push(v));
    [[1 / phi, phi, 0], [1 / phi, -phi, 0], [-1 / phi, phi, 0], [-1 / phi, -phi, 0]].forEach((v) => D.push(v));
    [[phi, 0, 1 / phi], [phi, 0, -1 / phi], [-phi, 0, 1 / phi], [-phi, 0, -1 / phi]].forEach((v) => D.push(v));

    // кубооктаэдр
    const CO = [];
    [[1, 1, 0], [1, -1, 0], [-1, 1, 0], [-1, -1, 0]].forEach((v) => CO.push(v));
    [[1, 0, 1], [1, 0, -1], [-1, 0, 1], [-1, 0, -1]].forEach((v) => CO.push(v));
    [[0, 1, 1], [0, 1, -1], [0, -1, 1], [0, -1, -1]].forEach((v) => CO.push(v));

    return {
      icosahedron: { vertices: I, color: '#00d4ff', glow: 'rgba(0,212,255,.35)', face: 'rgba(0,212,255,.06)' },
      cube: { vertices: C, color: '#00ff88', glow: 'rgba(0,255,136,.35)', face: 'rgba(0,255,136,.06)' },
      octahedron: { vertices: O, color: '#bf6bff', glow: 'rgba(191,107,255,.4)', face: 'rgba(191,107,255,.08)', pulse: true },
      tetrahedron: { vertices: T, color: '#ffb86b', glow: 'rgba(255,184,107,.35)', face: 'rgba(255,184,107,.06)' },
      dodecahedron: { vertices: D, color: '#cfd6e6', glow: 'rgba(207,214,230,.3)', face: 'rgba(207,214,230,.05)' },
      cuboctahedron: { vertices: CO, color: '#ffe66b', glow: 'rgba(255,230,107,.35)', face: 'rgba(255,230,107,.06)' },
    };
  }

  function computeEdges(verts) {
    let minDist = Infinity;
    for (let i = 0; i < verts.length; i++)
      for (let j = i + 1; j < verts.length; j++) {
        const d = Math.hypot(verts[i][0] - verts[j][0], verts[i][1] - verts[j][1], verts[i][2] - verts[j][2]);
        if (d > 1e-3 && d < minDist) minDist = d;
      }
    const edges = [];
    for (let i = 0; i < verts.length; i++)
      for (let j = i + 1; j < verts.length; j++) {
        const d = Math.hypot(verts[i][0] - verts[j][0], verts[i][1] - verts[j][1], verts[i][2] - verts[j][2]);
        if (Math.abs(d - minDist) < 1e-3) edges.push([i, j]);
      }
    return edges;
  }

  function rotate(v, ax, ay) {
    let [x, y, z] = v;
    // Rx
    const cx = Math.cos(ax), sx = Math.sin(ax);
    [y, z] = [y * cx - z * sx, y * sx + z * cx];
    // Ry
    const cy = Math.cos(ay), sy = Math.sin(ay);
    [x, z] = [x * cy + z * sy, -x * sy + z * cy];
    return [x, y, z];
  }

  function project(v, w, h, scale) {
    const dist = 4.5;
    const f = (dist) / (dist - v[2]);
    return [w / 2 + v[0] * scale * f, h / 2 + v[1] * scale * f, f];
  }

  const SHAPES = shapes();
  const cache = {};
  function getShape(name) {
    if (!cache[name]) {
      const s = SHAPES[name];
      cache[name] = { ...s, edges: computeEdges(s.vertices) };
    }
    return cache[name];
  }

  window.startPolyhedron = function (canvasId, shapeName, opts) {
    const cv = document.getElementById(canvasId);
    if (!cv) return;
    const ctx = cv.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    function resize() {
      const r = cv.getBoundingClientRect();
      cv.width = r.width * dpr;
      cv.height = r.height * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    resize();
    window.addEventListener('resize', resize);

    const shape = getShape(shapeName);
    const speed = (opts && opts.speed) || 1;
    const scale = (opts && opts.scale) || 36;
    let ax = 0.4, ay = 0.6;
    let t0 = performance.now();

    function tick(t) {
      const dt = (t - t0) / 1000;
      t0 = t;
      ax += dt * 0.25 * speed;
      ay += dt * 0.4 * speed;

      const r = cv.getBoundingClientRect();
      const w = r.width, h = r.height;
      ctx.clearRect(0, 0, w, h);

      // glow эффект пульсации для октаэдра
      let pulseScale = scale;
      if (shape.pulse) pulseScale = scale * (1 + Math.sin(t / 400) * 0.05);

      const verts2D = shape.vertices.map((v) => {
        const r3 = rotate(v, ax, ay);
        return project(r3, w, h, pulseScale);
      });

      // фон-glow
      const grad = ctx.createRadialGradient(w / 2, h / 2, 0, w / 2, h / 2, Math.min(w, h) / 2);
      grad.addColorStop(0, shape.glow);
      grad.addColorStop(1, 'transparent');
      ctx.fillStyle = grad;
      ctx.fillRect(0, 0, w, h);

      // рёбра
      ctx.strokeStyle = shape.color;
      ctx.lineWidth = 1.2;
      ctx.shadowColor = shape.color;
      ctx.shadowBlur = 8;
      ctx.beginPath();
      shape.edges.forEach(([a, b]) => {
        ctx.moveTo(verts2D[a][0], verts2D[a][1]);
        ctx.lineTo(verts2D[b][0], verts2D[b][1]);
      });
      ctx.stroke();
      ctx.shadowBlur = 0;

      // вершины
      ctx.fillStyle = shape.color;
      verts2D.forEach((v) => {
        ctx.beginPath();
        ctx.arc(v[0], v[1], 1.5 + v[2] * 0.3, 0, Math.PI * 2);
        ctx.fill();
      });

      requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  };
})();
