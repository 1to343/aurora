// Универсальное автосохранение черновиков форм в localStorage.
// Использование: ErpAutosave.attach('#form-id', 'ключ');
(function () {
  const PREFIX = 'erp_draft_';
  const MAX_AGE = 24 * 3600 * 1000; // 24 часа

  function serialize(form) {
    const data = {};
    form.querySelectorAll('input, select, textarea').forEach((el) => {
      if (!el.name && !el.id) return;
      const key = el.name || el.id;
      if (el.type === 'checkbox') data[key] = el.checked;
      else if (el.type === 'password') return;
      else data[key] = el.value;
    });
    return data;
  }

  function restore(form, data) {
    Object.entries(data).forEach(([k, v]) => {
      const el = form.querySelector(`[name="${k}"]`) || form.querySelector(`#${CSS.escape(k)}`);
      if (!el) return;
      if (el.type === 'checkbox') el.checked = !!v;
      else el.value = v;
    });
  }

  function hasContent(data) {
    return Object.values(data).some((v) => v !== '' && v !== false && v != null);
  }

  function toast(html, type) {
    if (window.ErpSim && ErpSim.showToast) ErpSim.showToast(html, type || 'info');
    else console.log('[autosave]', html);
  }

  function attach(selector, key) {
    const form = document.querySelector(selector);
    if (!form) return;
    const storeKey = PREFIX + key;

    // восстановление
    try {
      const raw = localStorage.getItem(storeKey);
      if (raw) {
        const saved = JSON.parse(raw);
        const age = Date.now() - (saved.ts || 0);
        if (age > MAX_AGE) {
          localStorage.removeItem(storeKey);
        } else if (hasContent(saved.data || {})) {
          showRestorePrompt(form, storeKey, saved);
        }
      }
    } catch (e) {}

    // автосохранение каждые 5 сек
    setInterval(() => {
      const data = serialize(form);
      if (hasContent(data)) {
        localStorage.setItem(storeKey, JSON.stringify({ ts: Date.now(), data }));
      }
    }, 5000);

    // очистка после отправки
    form.addEventListener('submit', () => {
      setTimeout(() => localStorage.removeItem(storeKey), 100);
    });
  }

  function showRestorePrompt(form, storeKey, saved) {
    const c = document.getElementById('toast-container') || (() => {
      const d = document.createElement('div');
      d.id = 'toast-container';
      d.style.cssText = 'position:fixed;right:20px;bottom:20px;z-index:9999;display:flex;flex-direction:column;gap:.5rem;';
      document.body.appendChild(d); return d;
    })();
    const el = document.createElement('div');
    const ageMin = Math.round((Date.now() - saved.ts) / 60000);
    el.style.cssText = 'pointer-events:auto;min-width:300px;background:rgba(17,24,39,.95);backdrop-filter:blur(12px);border:1px solid #00d4ff55;border-left:3px solid #00d4ff;color:#e4e6f0;padding:.8rem;border-radius:10px;font-size:.85rem;box-shadow:0 8px 24px rgba(0,0,0,.4)';
    el.innerHTML = `<div>📝 Найден несохранённый черновик (${ageMin} мин назад). Восстановить?</div>
      <div style="margin-top:.5rem;display:flex;gap:.5rem">
        <button class="btn btn-sm btn-primary" data-act="restore">Восстановить</button>
        <button class="btn btn-sm btn-outline-secondary" data-act="dismiss">Отклонить</button>
      </div>`;
    c.appendChild(el);
    el.querySelector('[data-act="restore"]').onclick = () => { restore(form, saved.data); el.remove(); };
    el.querySelector('[data-act="dismiss"]').onclick = () => { localStorage.removeItem(storeKey); el.remove(); };
  }

  window.ErpAutosave = { attach };
})();
