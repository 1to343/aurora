// Очередь офлайн-операций в IndexedDB + перехват fetch для POST/PUT/DELETE к /api.
(function () {
  const DB_NAME = 'erp_offline_queue';
  const STORE = 'operations';
  let dbp = null;

  function openDB() {
    if (dbp) return dbp;
    dbp = new Promise((resolve, reject) => {
      const r = indexedDB.open(DB_NAME, 1);
      r.onupgradeneeded = () => {
        const db = r.result;
        if (!db.objectStoreNames.contains(STORE)) db.createObjectStore(STORE, { keyPath: 'id' });
      };
      r.onsuccess = () => resolve(r.result);
      r.onerror = () => reject(r.error);
    });
    return dbp;
  }

  async function tx(mode, fn) {
    const db = await openDB();
    return new Promise((resolve, reject) => {
      const t = db.transaction(STORE, mode);
      const store = t.objectStore(STORE);
      const res = fn(store);
      t.oncomplete = () => resolve(res);
      t.onerror = () => reject(t.error);
    });
  }

  async function enqueue(op) {
    op.id = Date.now() + '-' + Math.random().toString(36).slice(2, 7);
    op.timestamp = Date.now();
    op.status = 'pending';
    await tx('readwrite', (s) => s.add(op));
    updateBadge();
    return op;
  }

  async function all() {
    const db = await openDB();
    return new Promise((resolve) => {
      const out = [];
      const t = db.transaction(STORE, 'readonly');
      t.objectStore(STORE).openCursor().onsuccess = (e) => {
        const cur = e.target.result;
        if (cur) { out.push(cur.value); cur.continue(); } else resolve(out.sort((a, b) => a.timestamp - b.timestamp));
      };
    });
  }

  async function remove(id) { await tx('readwrite', (s) => s.delete(id)); updateBadge(); }
  async function update(op) { await tx('readwrite', (s) => s.put(op)); updateBadge(); }
  async function count() { const a = await all(); return a.filter((o) => o.status === 'pending').length; }

  function describe(op) {
    const map = {
      '/api/wms/receipt': 'Приёмка', '/api/wms/quick-receipt': 'Быстрая приёмка',
      '/api/wms/issue': 'Выдача', '/api/wms/quick-issue': 'Быстрая выдача',
      '/api/wms/quarantine': 'Карантин', '/api/prod/work-orders': 'Создание WO',
      '/api/prod/operations': 'Операция', '/api/chat/messages': 'Сообщение',
      '/api/logistics/shipments': 'Поставка', '/api/power/event': 'Энергособытие',
    };
    for (const k in map) if (op.url.startsWith(k)) return map[k];
    return op.method + ' ' + op.url;
  }

  async function replay() {
    const ops = await all();
    let ok = 0;
    for (const op of ops) {
      if (op.status === 'conflict') continue;
      try {
        const res = await realFetch(op.url, { method: op.method, headers: op.headers, body: op.body });
        if (res.status === 409) {
          op.status = 'conflict'; await update(op);
          toast(`⚠️ Конфликт: ${describe(op)}`, 'warning');
        } else if (res.ok) {
          await remove(op.id); ok++;
          toast(`✓ Синхронизировано: ${describe(op)}`, 'success');
        }
      } catch (e) { /* сеть снова пропала — оставляем в очереди */ break; }
    }
    if (ok) document.dispatchEvent(new CustomEvent('queue-synced', { detail: { count: ok } }));
    updateBadge();
    return ok;
  }

  function toast(html, type) { if (window.ErpSim && ErpSim.showToast) ErpSim.showToast(html, type); }

  async function updateBadge() {
    const n = await count();
    const badge = document.getElementById('queue-badge');
    if (badge) { badge.textContent = n; badge.style.display = n ? 'inline-block' : 'none'; }
    const list = document.getElementById('queue-list');
    if (list && list.offsetParent !== null) renderPanel();
  }

  async function renderPanel() {
    const list = document.getElementById('queue-list');
    if (!list) return;
    const ops = await all();
    list.innerHTML = ops.length ? ops.map((o) => `
      <div style="padding:.5rem;border:1px solid var(--border-glass);border-radius:8px;margin-bottom:.4rem;font-size:.82rem">
        <div style="display:flex;justify-content:space-between">
          <b>${describe(o)}</b>
          <span class="badge badge-status-${o.status === 'conflict' ? 'reject' : o.status === 'pending' ? 'hold' : 'pass'}">${o.status}</span>
        </div>
        <div style="color:var(--text-muted);font-size:.72rem;font-family:var(--font-mono)">${new Date(o.timestamp).toLocaleString('ru-RU')}</div>
        <button class="btn btn-sm btn-outline-danger mt-1" onclick="ErpQueue.remove('${o.id}')"><i class="bi bi-trash"></i></button>
      </div>`).join('') : '<div style="color:var(--text-muted);text-align:center;padding:1rem">Очередь пуста</div>';
  }

  // ---- перехват fetch ----
  const realFetch = window.fetch.bind(window);
  window.fetch = async function (url, opts = {}) {
    const u = typeof url === 'string' ? url : url.url;
    const method = (opts.method || 'GET').toUpperCase();
    const isWrite = ['POST', 'PUT', 'DELETE'].includes(method);
    const isApi = u.startsWith('/api/') && !u.startsWith('/api/health');

    if (isWrite && isApi) {
      if (!navigator.onLine) {
        await enqueue({ url: u, method, body: opts.body, headers: opts.headers || { 'Content-Type': 'application/json' } });
        toast(`⏳ Сохранено локально: ${describe({ url: u, method })}`, 'info');
        return new Response(JSON.stringify({ queued: true }), { status: 202, headers: { 'Content-Type': 'application/json' } });
      }
      try {
        return await realFetch(url, opts);
      } catch (e) {
        await enqueue({ url: u, method, body: opts.body, headers: opts.headers || { 'Content-Type': 'application/json' } });
        toast(`⏳ Сеть недоступна, в очереди: ${describe({ url: u, method })}`, 'warning');
        return new Response(JSON.stringify({ queued: true }), { status: 202, headers: { 'Content-Type': 'application/json' } });
      }
    }
    return realFetch(url, opts);
  };

  window.addEventListener('online', () => setTimeout(replay, 800));

  window.ErpQueue = { enqueue, all, remove, replay, count, renderPanel, updateBadge };
  document.addEventListener('DOMContentLoaded', updateBadge);
})();
