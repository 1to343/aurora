// Оркестратор отказоустойчивости: индикатор связи, статус-бар, энергосбережение.
(function () {
  // ---------- Режим энергосбережения ----------
  const PS_KEY = 'erp_powersave';
  window.ErpPowerSave = localStorage.getItem(PS_KEY) === '1';

  function applyPowerSave() {
    document.documentElement.classList.toggle('power-save', window.ErpPowerSave);
    const btn = document.getElementById('powersave-toggle');
    if (btn) {
      btn.classList.toggle('active', window.ErpPowerSave);
      btn.title = window.ErpPowerSave ? 'Энергосбережение ВКЛ' : 'Энергосбережение ВЫКЛ';
    }
    document.dispatchEvent(new CustomEvent('powersave-change', { detail: window.ErpPowerSave }));
  }
  window.togglePowerSave = function () {
    window.ErpPowerSave = !window.ErpPowerSave;
    localStorage.setItem(PS_KEY, window.ErpPowerSave ? '1' : '0');
    applyPowerSave();
    if (window.ErpSim) ErpSim.showToast(window.ErpPowerSave ? '🔋 Режим энергосбережения включён' : '⚡ Режим энергосбережения выключен', 'info');
  };

  // ---------- Индикатор связи (фактический ping) ----------
  const pingHistory = []; // true=ok
  let connState = 'online';

  async function ping() {
    let ok = false;
    try {
      const ctrl = new AbortController();
      const to = setTimeout(() => ctrl.abort(), 4000);
      const r = await fetch('/api/health', { signal: ctrl.signal, cache: 'no-store' });
      clearTimeout(to);
      ok = r.ok;
    } catch (e) { ok = false; }
    pingHistory.push(ok);
    if (pingHistory.length > 5) pingHistory.shift();
    const fails = pingHistory.filter((x) => !x).length;
    let newState = 'online';
    if (!navigator.onLine || fails >= 5) newState = 'offline';
    else if (fails >= 3) newState = 'unstable';
    if (newState !== connState) onConnChange(connState, newState);
    connState = newState;
    renderConn();
  }

  function onConnChange(from, to) {
    if (!window.ErpSim) return;
    if (to === 'offline') ErpSim.showToast('🔴 Связь потеряна. Данные сохраняются локально и будут синхронизированы при восстановлении.', 'error');
    else if (from === 'offline' && to !== 'offline') {
      ErpSim.showToast('🟢 Связь восстановлена. Синхронизация...', 'success');
      if (window.ErpQueue) ErpQueue.replay();
    }
  }

  async function renderConn() {
    const el = document.getElementById('conn-indicator');
    if (!el) return;
    const map = { online: ['🟢', 'Онлайн', 'var(--accent-green)'], unstable: ['🟡', 'Нестабильно', 'var(--accent-orange)'], offline: ['🔴', 'Офлайн', 'var(--accent-red)'] };
    const [ic, txt, col] = map[connState];
    let qn = 0;
    if (window.ErpQueue) qn = await ErpQueue.count();
    el.innerHTML = `${ic} <span style="color:${col}">${txt}</span>${qn ? ` <span class="badge" style="background:var(--accent-orange);color:#0a0e1a">${qn}</span>` : ''}`;
  }

  // ---------- Глобальный статус-бар ----------
  let powerSince = null;

  async function refreshStatusBar() {
    // питание
    try {
      const p = await fetch('/api/power/status').then((r) => r.json());
      const sbp = document.getElementById('sb-power');
      if (sbp) {
        const map = { grid: ['⚡', 'Сеть', 'ok'], ups: ['🔋', 'ИБП', 'warn'], generator: ['🔌', 'Генератор', 'warn'], none: ['🚫', 'Нет питания', 'crit'] };
        const [ic, txt, lvl] = map[p.status] || map.grid;
        powerSince = p.since ? new Date(p.since) : null;
        sbp.dataset.level = lvl;
        sbp.innerHTML = `${ic} Электричество: <b>${txt}</b> <span id="sb-power-timer" class="mono"></span>`;
      }
    } catch (e) {}
    // инфраструктура
    try {
      const s = await fetch('/api/infra/summary').then((r) => r.json());
      const sbi = document.getElementById('sb-infra');
      if (sbi) {
        const lvl = s.equipment_total && s.equipment_working / s.equipment_total < 0.5 ? 'crit' : (s.equipment_working < s.equipment_total ? 'warn' : 'ok');
        sbi.dataset.level = lvl;
        sbi.innerHTML = `🏭 Инфраструктура: <b>${s.equipment_working}/${s.equipment_total}</b> оборуд.`;
      }
    } catch (e) {}
    recolorBar();
  }

  function recolorBar() {
    const bar = document.getElementById('statusbar');
    if (!bar) return;
    const levels = ['ok'];
    ['sb-power', 'sb-net', 'sb-infra'].forEach((id) => { const e = document.getElementById(id); if (e && e.dataset.level) levels.push(e.dataset.level); });
    // net level
    const netLvl = connState === 'offline' ? 'crit' : (connState === 'unstable' ? 'warn' : 'ok');
    levels.push(netLvl);
    const worst = levels.includes('crit') ? 'crit' : (levels.includes('warn') ? 'warn' : 'ok');
    bar.dataset.level = worst;
  }

  function tickTimers() {
    const t = document.getElementById('sb-power-timer');
    if (t && powerSince) {
      const sec = Math.floor((Date.now() - powerSince) / 1000);
      const m = String(Math.floor(sec / 60)).padStart(2, '0');
      const s = String(sec % 60).padStart(2, '0');
      t.textContent = `(${m}:${s})`;
    } else if (t) t.textContent = '';
    // net в статус-баре
    const sbn = document.getElementById('sb-net');
    if (sbn) {
      const map = { online: ['🌐', 'Онлайн', 'ok'], unstable: ['🌐', 'Нестабильно', 'warn'], offline: ['🌐', 'Офлайн', 'crit'] };
      const [ic, txt, lvl] = map[connState];
      sbn.dataset.level = lvl;
      ErpQueue && ErpQueue.count().then((qn) => {
        sbn.innerHTML = `${ic} Связь: <b>${txt}</b>${qn ? ` · очередь ${qn}` : ''}`;
        recolorBar();
      });
    }
  }

  // ---------- Панель очереди ----------
  window.toggleQueuePanel = function () {
    const p = document.getElementById('queue-panel');
    if (!p) return;
    p.classList.toggle('open');
    if (p.classList.contains('open') && window.ErpQueue) ErpQueue.renderPanel();
  };

  // ---------- Service Worker ----------
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch((e) => console.warn('SW fail', e));
    });
  }

  // ---------- Запуск ----------
  function start() {
    applyPowerSave();
    ping(); setInterval(ping, 10000);
    refreshStatusBar(); setInterval(refreshStatusBar, 20000);
    setInterval(tickTimers, 1000);
    document.addEventListener('queue-synced', renderConn);
    document.addEventListener('power-changed', refreshStatusBar);
  }
  if (document.readyState !== 'loading') start();
  else document.addEventListener('DOMContentLoaded', start);
})();
