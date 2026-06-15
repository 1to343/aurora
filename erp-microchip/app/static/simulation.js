// Глобальная клиентская симуляция: производство, склад, часы, toast.
// Состояние делится между вкладками через localStorage.

(function () {
  const STAGES = [
    { id: 1, name: 'Подготовка пластины', short: 'Wafer Prep' },
    { id: 2, name: 'Литография', short: 'Lithography' },
    { id: 3, name: 'Травление', short: 'Etching' },
    { id: 4, name: 'Легирование', short: 'Doping' },
    { id: 5, name: 'Тестирование', short: 'Testing' },
    { id: 6, name: 'Упаковка', short: 'Packaging' },
  ];

  const MATERIALS = [
    { name: 'Кремниевые пластины 300мм', stock: 420, max: 1000 },
    { name: 'Фоторезист AZ-5214', stock: 180, max: 500 },
    { name: 'Маски литографии', stock: 65, max: 200 },
    { name: 'Припой SAC305', stock: 240, max: 800 },
    { name: 'Керамические корпуса', stock: 510, max: 1500 },
    { name: 'Золотая проволока 25мкм', stock: 90, max: 300 },
    { name: 'Эпоксидный компаунд', stock: 320, max: 700 },
    { name: 'Тестовые зонды', stock: 75, max: 250 },
  ];

  const KEY = 'erp_sim_v1';

  function loadState() {
    try {
      const s = JSON.parse(localStorage.getItem(KEY));
      if (s && s.lots && s.materials && s.events) return s;
    } catch (e) {}
    return null;
  }

  function initState() {
    const now = Date.now();
    const lots = [];
    const initialCount = 6;
    for (let i = 1; i <= initialCount; i++) {
      lots.push({
        id: 'LOT-' + String(i).padStart(3, '0'),
        stage: 1 + Math.floor(Math.random() * 5),
        progress: Math.floor(Math.random() * 80),
        status: 'running',
        startedAt: now - Math.floor(Math.random() * 8 * 3600 * 1000),
        lastUpdate: now,
        completedAt: null,
      });
    }
    return {
      lots,
      materials: MATERIALS.map((m) => ({ ...m })),
      events: [],
      nextLotNum: initialCount + 1,
      lastReplenish: now,
      replenishAt: now + (120 + Math.random() * 120) * 1000,
    };
  }

  let state = loadState() || initState();

  function save() {
    try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) {}
  }

  const listeners = { tick: [], replenish: [], defect: [], complete: [], event: [] };
  function on(ev, fn) { (listeners[ev] = listeners[ev] || []).push(fn); }
  function emit(ev, payload) { (listeners[ev] || []).forEach((fn) => { try { fn(payload); } catch (e) { console.error(e); } }); }

  function logEvent(type, text) {
    const e = { ts: Date.now(), type, text };
    state.events.unshift(e);
    if (state.events.length > 200) state.events.length = 200;
    emit('event', e);
    return e;
  }

  // ----- Производство -----

  function tickProduction() {
    const now = Date.now();
    let changed = false;
    state.lots.forEach((lot) => {
      if (lot.status === 'done' || lot.status === 'defect') return;
      // 5% брак
      if (Math.random() < 0.05) {
        lot.status = 'defect';
        lot.lastUpdate = now;
        logEvent('error', `Брак обнаружен на партии ${lot.id} на этапе «${STAGES[lot.stage - 1].name}»`);
        emit('defect', lot);
        changed = true;
        return;
      }
      const inc = 3 + Math.random() * 5;
      lot.progress += inc;
      lot.lastUpdate = now;
      if (lot.progress >= 100) {
        lot.progress = 0;
        lot.stage += 1;
        if (lot.stage > 6) {
          lot.stage = 6;
          lot.progress = 100;
          lot.status = 'done';
          lot.completedAt = now;
          logEvent('success', `Партия ${lot.id} полностью изготовлена`);
          emit('complete', lot);
          // через 30 сек добавим новую
          setTimeout(() => addNewLot(), 30000);
        } else {
          logEvent('info', `Партия ${lot.id} перешла на этап «${STAGES[lot.stage - 1].name}»`);
        }
      }
      changed = true;
    });
    if (changed) { save(); emit('tick', state); }
  }

  function addNewLot() {
    const id = 'LOT-' + String(state.nextLotNum++).padStart(3, '0');
    state.lots.push({
      id,
      stage: 1,
      progress: 0,
      status: 'running',
      startedAt: Date.now(),
      lastUpdate: Date.now(),
      completedAt: null,
    });
    logEvent('info', `Запущена новая партия ${id}`);
    save();
    emit('tick', state);
  }

  function resumeLot(lotId) {
    const l = state.lots.find((x) => x.id === lotId);
    if (l && l.status === 'defect') {
      l.status = 'running';
      l.lastUpdate = Date.now();
      logEvent('warning', `Партия ${lotId} возобновлена после брака`);
      save();
      emit('tick', state);
    }
  }
  function stopLot(lotId) {
    const l = state.lots.find((x) => x.id === lotId);
    if (l && l.status === 'running') {
      l.status = 'paused';
      logEvent('warning', `Партия ${lotId} остановлена оператором`);
      save();
      emit('tick', state);
    }
  }
  function startLotAgain(lotId) {
    const l = state.lots.find((x) => x.id === lotId);
    if (l && l.status === 'paused') {
      l.status = 'running';
      logEvent('info', `Партия ${lotId} возобновлена`);
      save();
      emit('tick', state);
    }
  }

  // ----- Склад -----

  function checkReplenish() {
    const now = Date.now();
    if (now >= state.replenishAt) {
      const idx = Math.floor(Math.random() * state.materials.length);
      const m = state.materials[idx];
      const add = 50 + Math.floor(Math.random() * 151);
      m.stock = Math.min(m.stock + add, m.max);
      const evt = { ts: now, material: m.name, add, total: m.stock, idx };
      logEvent('success', `📦 Склад пополнен: ${m.name} +${add} шт. (остаток ${m.stock})`);
      state.replenishAt = now + (120 + Math.random() * 120) * 1000;
      state.lastReplenish = now;
      save();
      emit('replenish', evt);
    }
  }

  function manualReplenish(idx, add) {
    const m = state.materials[idx];
    if (!m) return;
    m.stock = Math.min(m.stock + add, m.max);
    logEvent('success', `Ручное пополнение: ${m.name} +${add} шт. (остаток ${m.stock})`);
    save();
    emit('replenish', { ts: Date.now(), material: m.name, add, total: m.stock, idx });
  }

  // ----- Toast -----

  function ensureToastContainer() {
    let c = document.getElementById('toast-container');
    if (!c) {
      c = document.createElement('div');
      c.id = 'toast-container';
      c.style.cssText = 'position:fixed;right:20px;bottom:20px;z-index:9999;display:flex;flex-direction:column;gap:.5rem;pointer-events:none;';
      document.body.appendChild(c);
    }
    return c;
  }

  function showToast(html, type = 'info') {
    const c = ensureToastContainer();
    const el = document.createElement('div');
    const colors = {
      info: '#00d4ff',
      success: '#00ff88',
      warning: '#ffb86b',
      error: '#ff5577',
    };
    const color = colors[type] || colors.info;
    el.style.cssText = `pointer-events:auto;min-width:280px;max-width:380px;background:rgba(17,24,39,.9);backdrop-filter:blur(12px);border:1px solid ${color}55;border-left:3px solid ${color};color:#e4e6f0;padding:.7rem .9rem;border-radius:10px;font-size:.85rem;box-shadow:0 8px 24px rgba(0,0,0,.4),0 0 20px ${color}33;opacity:0;transform:translateX(60px);transition:all .35s cubic-bezier(.2,.8,.2,1)`;
    el.innerHTML = html;
    c.appendChild(el);
    requestAnimationFrame(() => { el.style.opacity = '1'; el.style.transform = 'translateX(0)'; });
    setTimeout(() => {
      el.style.opacity = '0';
      el.style.transform = 'translateX(60px)';
      setTimeout(() => el.remove(), 400);
    }, 5000);
  }

  // ----- Часы -----

  function startClock() {
    const timeEl = document.getElementById('clock-time');
    const dateEl = document.getElementById('clock-date');
    if (!timeEl) return;
    const months = ['января','февраля','марта','апреля','мая','июня','июля','августа','сентября','октября','ноября','декабря'];
    const wd = ['воскресенье','понедельник','вторник','среда','четверг','пятница','суббота'];
    function update() {
      const d = new Date();
      const hh = String(d.getHours()).padStart(2,'0');
      const mm = String(d.getMinutes()).padStart(2,'0');
      const ss = String(d.getSeconds()).padStart(2,'0');
      timeEl.textContent = `${hh}:${mm}:${ss}`;
      if (dateEl) dateEl.textContent = `${d.getDate()} ${months[d.getMonth()]} ${d.getFullYear()}, ${wd[d.getDay()]}`;
    }
    update(); setInterval(update, 1000);
  }

  // ----- Подключаем toast к событиям -----
  on('replenish', (e) => {
    showToast(`📦 <b>Склад пополнен</b><br><span style="color:#8b8fa3">${e.material}</span><br><span style="color:#00ff88">+${e.add} шт.</span> | Остаток: <b>${e.total}</b>`, 'success');
  });
  on('defect', (l) => {
    showToast(`⚠️ <b>Брак на партии ${l.id}</b><br>Этап: ${STAGES[l.stage-1].name}`, 'error');
  });
  on('complete', (l) => {
    showToast(`✅ <b>Партия ${l.id} завершена</b><br>Все 6 этапов пройдены`, 'success');
  });

  // ----- Запуск -----
  // Один таб — мастер (по таймстампу инициализации); остальные слушают через storage event
  function isMaster() {
    const masterTs = +localStorage.getItem('erp_sim_master') || 0;
    return Date.now() - masterTs < 5000;
  }
  function claimMaster() { localStorage.setItem('erp_sim_master', Date.now()); }
  // heartbeat
  if (!localStorage.getItem('erp_sim_master') || Date.now() - (+localStorage.getItem('erp_sim_master') || 0) > 15000) {
    claimMaster();
  }
  setInterval(claimMaster, 4000);

  function loop() {
    if (isMaster()) {
      tickProduction();
      checkReplenish();
    } else {
      // не мастер — перечитать состояние
      const s = loadState();
      if (s) state = s;
      emit('tick', state);
    }
  }
  setInterval(loop, 10000);

  // storage event — реагируем на изменения из других вкладок
  window.addEventListener('storage', (e) => {
    if (e.key === KEY) {
      const s = loadState();
      if (s) {
        const oldMats = state.materials.map(m => m.stock);
        const oldEvents = state.events.length;
        state = s;
        emit('tick', state);
        // если события добавились — эмулируем replenish/event
        if (state.events.length > oldEvents) {
          const newEvts = state.events.slice(0, state.events.length - oldEvents);
          newEvts.forEach(ev => emit('event', ev));
        }
        state.materials.forEach((m, i) => {
          if (oldMats[i] !== undefined && m.stock > oldMats[i]) {
            emit('replenish', { ts: Date.now(), material: m.name, add: m.stock - oldMats[i], total: m.stock, idx: i });
          }
        });
      }
    }
  });

  // ----- Публичный API -----
  window.ErpSim = {
    STAGES,
    getState: () => state,
    getLots: () => state.lots,
    getMaterials: () => state.materials,
    getEvents: () => state.events,
    on,
    showToast,
    startClock,
    stopLot,
    startLotAgain,
    resumeLot,
    manualReplenish,
    logEvent,
  };

  if (document.readyState !== 'loading') startClock();
  else document.addEventListener('DOMContentLoaded', startClock);
})();
