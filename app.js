(function () {
  'use strict';

  var CFG = window.UAOA_I18N_REVIEW || {};
  var API = (CFG.apiBase || '').replace(/\/$/, '');
  var LOCALES = CFG.locales || [];
  var MODULE_ORDER = ['common', 'm1', 'm2', 'm3', 'm4', 'm5', 'summary', 'embeds', 'player'];
  var MODULE_LABELS = {
    common: 'Common UI',
    m1: 'Module 1',
    m2: 'Module 2',
    m3: 'Module 3',
    m4: 'Module 4',
    m5: 'Module 5',
    summary: 'Summary',
    embeds: 'Chrome embeds',
    player: 'Player / system labels',
  };

  var state = {
    name: sessionStorage.getItem('uaoa.reviewer') || '',
    sessionId: sessionStorage.getItem('uaoa.sessionId') || '',
    locale: '',
    module: 'common',
    en: null,
    tr: null,
    approvals: {},
    lock: null,
    canEdit: false,
    editingKey: null,
    pendingKey: null,
    pendingAction: null, // 'save' | 'approve' | 'unapprove'
    filter: '',
    rowsCache: [],
  };

  var el = {
    localeSelect: document.getElementById('localeSelect'),
    reviewerPill: document.getElementById('reviewerPill'),
    lockPill: document.getElementById('lockPill'),
    releaseBtn: document.getElementById('releaseBtn'),
    modList: document.getElementById('modList'),
    rows: document.getElementById('rows'),
    stats: document.getElementById('stats'),
    search: document.getElementById('search'),
    banner: document.getElementById('statusBanner'),
    nameModal: document.getElementById('nameModal'),
    nameInput: document.getElementById('nameInput'),
    nameStart: document.getElementById('nameStart'),
    toast: document.getElementById('toast'),
  };

  function uid() {
    return 's-' + Math.random().toString(36).slice(2) + Date.now().toString(36);
  }

  function toast(msg, kind) {
    el.toast.textContent = msg;
    el.toast.className = 'toast show' + (kind === 'error' ? ' error' : kind === 'ok' ? ' ok' : '');
    clearTimeout(toast._t);
    toast._t = setTimeout(function () {
      el.toast.classList.remove('show');
    }, 2400);
  }

  function setPending(key, action) {
    state.pendingKey = key || null;
    state.pendingAction = action || null;
  }

  function clearPending() {
    state.pendingKey = null;
    state.pendingAction = null;
  }

  function btnLabel(text, busy) {
    if (!busy) return text;
    return '<span class="btn-spinner" aria-hidden="true"></span><span>' + text + '</span>';
  }

  function isLocalTunnel(base) {
    return /\.loca\.lt$/i.test(String(base || '').replace(/^https?:\/\//i, '').split('/')[0] || '');
  }

  function api(path, opts) {
    opts = opts || {};
    var headers = Object.assign({
      'Accept': 'application/json',
    }, opts.headers || {});
    // Only for localtunnel — custom header forces CORS preflight; Render must allow it.
    if (isLocalTunnel(API)) headers['Bypass-Tunnel-Reminder'] = 'true';
    if (opts.body && !headers['Content-Type']) headers['Content-Type'] = 'application/json';

    var attempts = typeof opts.retries === 'number' ? opts.retries : 2;
    var timeoutMs = typeof opts.timeoutMs === 'number' ? opts.timeoutMs : 45000;

    function once() {
      var ctrl = typeof AbortController !== 'undefined' ? new AbortController() : null;
      var timer = ctrl ? setTimeout(function () { ctrl.abort(); }, timeoutMs) : null;
      return fetch(API + path, {
        method: opts.method || 'GET',
        headers: headers,
        body: opts.body ? JSON.stringify(opts.body) : undefined,
        cache: 'no-store',
        signal: ctrl ? ctrl.signal : undefined,
      }).then(function (res) {
        return res.json().catch(function () { return {}; }).then(function (data) {
          if (!res.ok) {
            var err = new Error((data && data.error) || ('HTTP ' + res.status));
            err.status = res.status;
            err.data = data;
            throw err;
          }
          return data;
        });
      }).finally(function () {
        if (timer) clearTimeout(timer);
      });
    }

    function run(left) {
      return once().catch(function (e) {
        var retriable = !e.status || e.status >= 500 || e.name === 'AbortError' ||
          /Failed to fetch|NetworkError|timeout/i.test(String(e.message || e));
        if (left <= 0 || !retriable) throw e;
        return new Promise(function (r) { setTimeout(r, 1500); }).then(function () {
          return run(left - 1);
        });
      });
    }

    return run(attempts);
  }

  function leafText(node) {
    if (node == null) return '';
    if (typeof node === 'string') return node;
    if (typeof node === 'object' && typeof node.text === 'string') return node.text;
    return '';
  }

  function leafNote(node) {
    if (node && typeof node === 'object' && node.note) return String(node.note);
    return '';
  }

  function walk(obj, prefix, out) {
    if (!obj || typeof obj !== 'object') return;
    Object.keys(obj).forEach(function (k) {
      if (k.charAt(0) === '_') return;
      var path = prefix ? prefix + '.' + k : k;
      var v = obj[k];
      if (v && typeof v === 'object' && !Array.isArray(v) && ('text' in v)) {
        out.push({ key: path, text: leafText(v), note: leafNote(v) });
      } else if (v && typeof v === 'object' && !Array.isArray(v)) {
        walk(v, path, out);
      } else if (typeof v === 'string') {
        out.push({ key: path, text: v, note: '' });
      }
    });
  }

  function getByPath(root, key) {
    var cur = root;
    var parts = key.split('.');
    for (var i = 0; i < parts.length; i++) {
      if (!cur || typeof cur !== 'object') return null;
      cur = cur[parts[i]];
    }
    return cur;
  }

  function moduleOf(key) {
    return key.split('.')[0] || 'other';
  }

  function widgetOf(key) {
    var parts = key.split('.');
    if (parts.length < 2) return parts[0] || 'root';
    if (parts[0] === 'player') return parts.slice(0, 3).join('.');
    return parts.slice(0, 2).join('.');
  }

  function flattenEn() {
    var out = [];
    walk(state.en, '', out);
    return out;
  }

  function ensureSession() {
    if (!state.sessionId) {
      state.sessionId = uid();
      sessionStorage.setItem('uaoa.sessionId', state.sessionId);
    }
  }

  function localeFromUrl() {
    var q = new URLSearchParams(location.search);
    return (q.get('locale') || LOCALES[0] && LOCALES[0].code || 'es').toLowerCase();
  }

  function setUrlLocale(code) {
    var u = new URL(location.href);
    u.searchParams.set('locale', code);
    history.replaceState(null, '', u.toString());
  }

  function fillLocaleSelect() {
    el.localeSelect.innerHTML = '';
    LOCALES.forEach(function (loc) {
      var opt = document.createElement('option');
      opt.value = loc.code;
      opt.textContent = loc.label + ' (' + loc.code + ')';
      el.localeSelect.appendChild(opt);
    });
  }

  function updateChrome() {
    el.reviewerPill.textContent = state.name ? ('Reviewer: ' + state.name) : 'Reviewer…';
    var lock = state.lock;
    if (!lock) {
      el.lockPill.textContent = 'Locale available';
      el.lockPill.className = 'pill ok';
      el.releaseBtn.hidden = true;
    } else if (lock.sessionId === state.sessionId) {
      el.lockPill.textContent = 'Checked out by you';
      el.lockPill.className = 'pill ok';
      el.releaseBtn.hidden = false;
    } else {
      el.lockPill.textContent = 'In use by ' + (lock.holder || 'someone');
      el.lockPill.className = 'pill busy';
      el.releaseBtn.hidden = true;
    }

    if (!state.canEdit) {
      el.banner.hidden = false;
      if (lock && lock.sessionId !== state.sessionId) {
        el.banner.className = 'banner';
        el.banner.textContent = (lock.holder || 'Another reviewer') +
          ' has this locale checked out until ' +
          (lock.until ? new Date(lock.until).toLocaleString() : 'later') +
          '. You can browse in read-only mode.';
      } else {
        el.banner.className = 'banner';
        el.banner.textContent = 'Read-only — could not check out this locale. Try again or pick another language.';
      }
    } else {
      el.banner.hidden = false;
      el.banner.className = 'banner ok';
      el.banner.textContent = 'You have an exclusive checkout for ' + state.locale.toUpperCase() +
        '. Approve locks a line; Edit lets you change the translation.';
    }
  }

  function moduleStats(allRows) {
    var by = {};
    MODULE_ORDER.forEach(function (m) { by[m] = { total: 0, approved: 0 }; });
    allRows.forEach(function (r) {
      var m = moduleOf(r.key);
      if (!by[m]) by[m] = { total: 0, approved: 0 };
      by[m].total += 1;
      if (state.approvals[r.key] && state.approvals[r.key].approved) by[m].approved += 1;
    });
    return by;
  }

  function renderModules(allRows) {
    var stats = moduleStats(allRows);
    el.modList.innerHTML = '';
    MODULE_ORDER.forEach(function (m) {
      if (!stats[m] || !stats[m].total) return;
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'mod-btn' + (state.module === m ? ' active' : '');
      btn.innerHTML = '<span>' + (MODULE_LABELS[m] || m) + '</span>' +
        '<span class="meta">' + stats[m].approved + ' / ' + stats[m].total + ' approved</span>';
      btn.addEventListener('click', function () {
        state.module = m;
        state.editingKey = null;
        renderModules(allRows);
        renderRows();
      });
      el.modList.appendChild(btn);
    });
  }

  function filteredRows() {
    var q = (state.filter || '').trim().toLowerCase();
    return state.rowsCache.filter(function (r) {
      if (moduleOf(r.key) !== state.module) return false;
      if (!q) return true;
      var tr = leafText(getByPath(state.tr, r.key));
      return (r.key + ' ' + r.text + ' ' + tr + ' ' + r.note).toLowerCase().indexOf(q) !== -1;
    });
  }

  function renderRows() {
    var rows = filteredRows();
    var approved = rows.filter(function (r) {
      return state.approvals[r.key] && state.approvals[r.key].approved;
    }).length;
    el.stats.textContent = (MODULE_LABELS[state.module] || state.module) +
      ' · ' + rows.length + ' strings · ' + approved + ' approved';

    if (!rows.length) {
      el.rows.innerHTML = '<div class="empty">No strings in this module' +
        (state.filter ? ' match your filter' : '') + '.</div>';
      return;
    }

    var groups = {};
    var order = [];
    rows.forEach(function (r) {
      var w = widgetOf(r.key);
      if (!groups[w]) { groups[w] = []; order.push(w); }
      groups[w].push(r);
    });

    el.rows.innerHTML = '';
    order.forEach(function (w) {
      var block = document.createElement('section');
      block.className = 'widget-block';
      var head = document.createElement('header');
      head.textContent = w;
      block.appendChild(head);

      groups[w].forEach(function (r) {
        block.appendChild(renderRow(r));
      });
      el.rows.appendChild(block);
    });
  }

  function renderRow(r) {
    var approved = !!(state.approvals[r.key] && state.approvals[r.key].approved);
    var editing = state.editingKey === r.key;
    var pending = state.pendingKey === r.key;
    var pendingSave = pending && state.pendingAction === 'save';
    var pendingApprove = pending && state.pendingAction === 'approve';
    var pendingUnlock = pending && state.pendingAction === 'unapprove';
    var trText = leafText(getByPath(state.tr, r.key));

    var row = document.createElement('article');
    row.className = 'row' + (pending ? ' is-pending' : '');
    row.dataset.key = r.key;

    var keyEl = document.createElement('div');
    keyEl.className = 'key';
    keyEl.textContent = r.key;
    row.appendChild(keyEl);

    if (r.note) {
      var note = document.createElement('p');
      note.className = 'note';
      note.textContent = r.note;
      row.appendChild(note);
    }

    var left = document.createElement('div');
    left.innerHTML = '<div class="panel-label">English</div>';
    var enBox = document.createElement('div');
    enBox.className = 'en-box';
    enBox.textContent = r.text;
    left.appendChild(enBox);
    row.appendChild(left);

    var right = document.createElement('div');
    right.innerHTML = '<div class="panel-label">Translation (' + state.locale + ')</div>';
    var trBox;
    if (editing) {
      trBox = document.createElement('textarea');
      trBox.className = 'tr-box editable' + (pendingSave ? ' is-busy' : '');
      trBox.value = trText;
      trBox.id = 'edit-' + r.key;
      if (pendingSave) trBox.disabled = true;
    } else {
      trBox = document.createElement('div');
      trBox.className = 'tr-box' + (approved ? ' locked' : '');
      trBox.textContent = trText || '—';
    }
    right.appendChild(trBox);
    row.appendChild(right);

    var actions = document.createElement('div');
    actions.className = 'actions';

    if (!state.canEdit) {
      var ro = document.createElement('span');
      ro.className = 'pill ro';
      ro.textContent = approved ? 'Approved' : 'Read-only';
      actions.appendChild(ro);
    } else if (editing) {
      var save = document.createElement('button');
      save.type = 'button';
      save.className = 'btn btn-save' + (pendingSave ? ' is-busy' : '');
      save.innerHTML = btnLabel(pendingSave ? 'Saving…' : 'Save', pendingSave);
      save.disabled = pendingSave;
      save.setAttribute('aria-busy', pendingSave ? 'true' : 'false');
      save.addEventListener('click', function () {
        if (state.pendingKey) return;
        saveEdit(r.key, trBox.value);
      });
      var cancel = document.createElement('button');
      cancel.type = 'button';
      cancel.className = 'btn btn-cancel';
      cancel.textContent = 'Cancel';
      cancel.disabled = pendingSave;
      cancel.addEventListener('click', function () {
        if (state.pendingKey) return;
        state.editingKey = null;
        renderRows();
      });
      actions.appendChild(save);
      actions.appendChild(cancel);
    } else if (approved) {
      var locked = document.createElement('span');
      locked.className = 'pill ok';
      locked.textContent = 'Locked';
      var unlock = document.createElement('button');
      unlock.type = 'button';
      unlock.className = 'btn btn-unlock' + (pendingUnlock ? ' is-busy' : '');
      unlock.innerHTML = btnLabel(pendingUnlock ? 'Unlocking…' : 'Unlock', pendingUnlock);
      unlock.disabled = pendingUnlock;
      unlock.setAttribute('aria-busy', pendingUnlock ? 'true' : 'false');
      unlock.addEventListener('click', function () {
        if (state.pendingKey) return;
        unapprove(r.key);
      });
      actions.appendChild(locked);
      actions.appendChild(unlock);
    } else {
      var approve = document.createElement('button');
      approve.type = 'button';
      approve.className = 'btn btn-approve' + (pendingApprove ? ' is-busy' : '');
      approve.innerHTML = btnLabel(pendingApprove ? 'Approving…' : 'Approve', pendingApprove);
      approve.disabled = pendingApprove;
      approve.setAttribute('aria-busy', pendingApprove ? 'true' : 'false');
      approve.addEventListener('click', function () {
        if (state.pendingKey) return;
        approveKey(r.key);
      });
      var edit = document.createElement('button');
      edit.type = 'button';
      edit.className = 'btn btn-edit';
      edit.textContent = 'Edit';
      edit.disabled = pendingApprove;
      edit.addEventListener('click', function () {
        if (state.pendingKey) return;
        state.editingKey = r.key;
        renderRows();
        var ta = document.getElementById('edit-' + r.key);
        if (ta) ta.focus();
      });
      actions.appendChild(approve);
      actions.appendChild(edit);
    }

    row.appendChild(actions);
    return row;
  }

  function setByPathLocal(root, key, text) {
    var parts = key.split('.');
    var cur = root;
    for (var i = 0; i < parts.length - 1; i++) {
      var p = parts[i];
      if (!cur[p] || typeof cur[p] !== 'object' || ('text' in cur[p] && Object.keys(cur[p]).every(function (k) {
        return k === 'text' || k === 'note';
      }))) {
        cur[p] = {};
      }
      cur = cur[p];
    }
    var leaf = parts[parts.length - 1];
    var existing = cur[leaf];
    if (existing && typeof existing === 'object' && 'text' in existing) {
      cur[leaf] = Object.assign({}, existing, { text: text });
    } else {
      cur[leaf] = { text: text };
    }
  }

  function approveKey(key) {
    if (state.pendingKey) return;
    setPending(key, 'approve');
    renderRows();
    api('/api/approve', {
      method: 'POST',
      body: {
        locale: state.locale,
        key: key,
        name: state.name,
        sessionId: state.sessionId,
      },
    }).then(function (data) {
      state.approvals = data.approvals || state.approvals;
      state.approvals[key] = data.entry || { approved: true, by: state.name };
      clearPending();
      toast('Approved', 'ok');
      renderModules(state.rowsCache);
      renderRows();
    }).catch(function (e) {
      clearPending();
      toast(e.message || 'Approve failed', 'error');
      renderRows();
    });
  }

  function unapprove(key) {
    if (state.pendingKey) return;
    setPending(key, 'unapprove');
    renderRows();
    api('/api/unapprove', {
      method: 'POST',
      body: {
        locale: state.locale,
        key: key,
        name: state.name,
        sessionId: state.sessionId,
      },
    }).then(function (data) {
      state.approvals = data.approvals || {};
      clearPending();
      toast('Unlocked', 'ok');
      renderModules(state.rowsCache);
      renderRows();
    }).catch(function (e) {
      clearPending();
      toast(e.message || 'Unlock failed', 'error');
      renderRows();
    });
  }

  function saveEdit(key, text) {
    if (state.pendingKey) return;
    // Keep editingKey so the row stays in edit mode until the request finishes.
    setByPathLocal(state.tr, key, text);
    setPending(key, 'save');
    renderRows();
    api('/api/translation', {
      method: 'PUT',
      body: {
        locale: state.locale,
        key: key,
        text: text,
        name: state.name,
        sessionId: state.sessionId,
      },
    }).then(function (data) {
      if (data.catalog) state.tr = data.catalog;
      else setByPathLocal(state.tr, key, text);
      clearPending();
      state.editingKey = null;
      toast('Saved', 'ok');
      renderRows();
    }).catch(function (e) {
      clearPending();
      toast(e.message || 'Save failed', 'error');
      renderRows();
    });
  }

  function claimLocale() {
    return api('/api/lock/claim', {
      method: 'POST',
      body: {
        locale: state.locale,
        name: state.name,
        sessionId: state.sessionId,
        minutes: CFG.leaseMinutes || 15,
      },
    }).then(function (data) {
      state.lock = data.lock || null;
      state.canEdit = !!data.acquired;
      if (data.approvals) state.approvals = data.approvals;
      updateChrome();
      return data;
    });
  }

  function releaseLocale() {
    return api('/api/lock/release', {
      method: 'POST',
      body: {
        locale: state.locale,
        name: state.name,
        sessionId: state.sessionId,
      },
    }).then(function () {
      state.lock = null;
      state.canEdit = false;
      updateChrome();
      toast('Locale released');
    }).catch(function (e) { toast(e.message || 'Release failed'); });
  }

  function heartbeat() {
    if (!state.canEdit || !state.locale) return;
    api('/api/lock/heartbeat', {
      method: 'POST',
      body: {
        locale: state.locale,
        name: state.name,
        sessionId: state.sessionId,
        minutes: CFG.leaseMinutes || 15,
      },
    }).then(function (data) {
      if (data.lock) state.lock = data.lock;
      if (data.acquired === false) {
        state.canEdit = false;
        updateChrome();
        renderRows();
        toast('Checkout lost — locale taken or expired');
      }
    }).catch(function () { /* ignore transient */ });
  }

  function loadLocale(code) {
    state.locale = code;
    state.editingKey = null;
    setUrlLocale(code);
    el.localeSelect.value = code;

    return Promise.all([
      api('/api/catalog/en'),
      api('/api/catalog/' + encodeURIComponent(code)),
      api('/api/approvals/' + encodeURIComponent(code)),
      api('/api/lock/' + encodeURIComponent(code)),
    ]).then(function (parts) {
      state.en = parts[0].catalog;
      state.tr = parts[1].catalog;
      state.approvals = parts[2].approvals || {};
      state.lock = parts[3].lock || null;
      state.rowsCache = flattenEn();
      if (!MODULE_ORDER.includes(state.module) ||
          !state.rowsCache.some(function (r) { return moduleOf(r.key) === state.module; })) {
        state.module = 'common';
      }
      return claimLocale();
    }).then(function () {
      renderModules(state.rowsCache);
      renderRows();
    });
  }

  function boot() {
    fillLocaleSelect();
    ensureSession();

    el.localeSelect.addEventListener('change', function () {
      var next = el.localeSelect.value;
      var prev = state.locale;
      var go = function () {
        loadLocale(next).catch(function (e) { toast(e.message || 'Failed to load locale'); });
      };
      if (state.canEdit && prev && prev !== next) {
        releaseLocale().finally(go);
      } else {
        go();
      }
    });

    el.releaseBtn.addEventListener('click', function () {
      releaseLocale().then(function () { return claimLocale(); }).then(function () {
        renderRows();
      });
    });

    el.search.addEventListener('input', function () {
      state.filter = el.search.value;
      renderRows();
    });

    function startReview() {
      api('/api/health').then(function () {
        return loadLocale(localeFromUrl());
      }).catch(function (e) {
        el.banner.hidden = false;
        el.banner.className = 'banner';
        el.banner.textContent = 'API unavailable (' + (e.message || 'network') +
          '). Run python3 api/server.py locally, or host the API (Render) and set config.js apiBase.';
        toast('API unavailable');
      });
    }

    el.nameStart.addEventListener('click', function () {
      var name = (el.nameInput.value || '').trim();
      if (name.length < 2) {
        el.nameInput.focus();
        return;
      }
      state.name = name;
      sessionStorage.setItem('uaoa.reviewer', name);
      el.nameModal.hidden = true;
      startReview();
    });

    el.nameInput.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') el.nameStart.click();
    });

    window.addEventListener('beforeunload', function () {
      if (!state.canEdit) return;
      try {
        navigator.sendBeacon(
          API + '/api/lock/release',
          new Blob([JSON.stringify({
            locale: state.locale,
            name: state.name,
            sessionId: state.sessionId,
          })], { type: 'application/json' })
        );
      } catch (e) {}
    });

    setInterval(heartbeat, 120000);

    el.localeSelect.value = localeFromUrl();
    if (!state.name) {
      el.nameModal.hidden = false;
      el.nameInput.focus();
    } else {
      el.nameModal.hidden = true;
      startReview();
    }
  }

  boot();
})();
