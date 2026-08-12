/* Parent editor shell — talks to iframe bridge + Python write APIs. */
(function () {
  'use strict';

  var STYLE_MAP = {
    color: 'f-color',
    'background-color': 'f-bg',
    'font-size': 'f-fs',
    'font-weight': 'f-fw',
    'text-align': 'f-ta',
    width: 'f-w',
    height: 'f-h',
    padding: 'f-pad',
    gap: 'f-gap',
    'border-radius': 'f-br'
  };

  var state = {
    project: null,
    tab: 'slides',
    fileId: null,
    selection: null,
    token: null,
    undo: [],
    redo: [],
    debounce: null,
    busy: false,
    sel: false,
    grid: false
  };

  var $ = function (id) { return document.getElementById(id); };
  var canvas = $('canvas');

  function toast(msg) {
    var t = $('toast');
    t.textContent = msg;
    t.hidden = false;
    clearTimeout(toast._t);
    toast._t = setTimeout(function () { t.hidden = true; }, 2200);
  }

  function live(ok) {
    $('dot').style.background = ok ? '#4ade80' : '#ef4444';
    $('live-label').textContent = ok ? '자동 새로고침 켜짐' : '연결 끊김 — 미리보기를 다시 켜 주세요';
  }

  function addrOf(sel) {
    if (!sel) return '';
    return sel.part ? (sel.region + '.' + sel.part) : sel.region;
  }

  function currentEntry() {
    if (!state.project || !state.fileId) return null;
    var all = (state.project.slides || []).concat(state.project.templates || []);
    for (var i = 0; i < all.length; i++) if (all[i].id === state.fileId) return all[i];
    return null;
  }

  function setTab(tab) {
    state.tab = tab;
    document.querySelectorAll('.tabs button').forEach(function (b) {
      b.classList.toggle('on', b.getAttribute('data-tab') === tab);
    });
    $('list-slides').hidden = tab !== 'slides';
    $('list-templates').hidden = tab !== 'templates';
    $('palette-pane').hidden = tab !== 'palette';
    $('b-add-slide').hidden = tab !== 'templates' || !state.fileId || !(state.fileId.indexOf('templates/') === 0);
    if (tab === 'palette') renderPalette();
  }

  function renderLists() {
    var p = state.project;
    if (!p) return;
    $('deck-title').textContent = p.title || '덱';
    $('nav-meta').textContent = (p.slides || []).length + '장 · 템플릿 ' + (p.templates || []).length;

    function fill(el, items, kind) {
      el.innerHTML = '';
      if (!items.length) {
        el.innerHTML = '<div class="muted" style="padding:8px 10px">없음</div>';
        return;
      }
      items.forEach(function (it, idx) {
        var b = document.createElement('button');
        b.type = 'button';
        b.className = 'item' + (state.fileId === it.id ? ' on' : '');
        b.innerHTML = '<span>' + (kind === 'slides' ? (idx + 1) + '. ' : '') + escapeHtml(it.title || it.id) +
          '</span><span class="sub">' + escapeHtml(it.id) + '</span>';
        b.onclick = function () { openFile(it.id); };
        el.appendChild(b);
      });
    }
    fill($('list-slides'), p.slides || [], 'slides');
    fill($('list-templates'), p.templates || [], 'templates');
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c];
    });
  }

  function fitCanvasFrame() {
    var wrap = $('canvas-wrap');
    if (!wrap || !canvas) return;
    var aw = wrap.clientWidth - 8;
    var ah = wrap.clientHeight - 8;
    if (aw <= 0 || ah <= 0) return;
    var W = 1280, H = 720;
    if (state.project && state.project.size && state.project.size.length === 2) {
      W = state.project.size[0] || W;
      H = state.project.size[1] || H;
    }
    var k = Math.min(aw / W, ah / H);
    canvas.style.width = Math.floor(W * k) + 'px';
    canvas.style.height = Math.floor(H * k) + 'px';
  }

  function syncModeToCanvas() {
    if (!canvas.contentWindow) return;
    try {
      canvas.contentWindow.postMessage({
        source: 'slidecraft-shell',
        type: 'mode',
        select: state.sel,
        grid: state.grid
      }, location.origin);
    } catch (e) {}
  }

  function paintModeButtons() {
    var sel = $('b-sel');
    var grid = $('b-grid');
    if (sel) sel.setAttribute('aria-pressed', state.sel ? 'true' : 'false');
    if (grid) grid.setAttribute('aria-pressed', state.grid ? 'true' : 'false');
  }

  function openInspector() {
    document.body.classList.add('insp-open');
    var panel = $('inspector');
    if (panel) panel.hidden = false;
    fitCanvasFrame();
    syncModeToCanvas();
  }

  function closeInspector() {
    document.body.classList.remove('insp-open');
    var panel = $('inspector');
    if (panel) panel.hidden = true;
    $('insp-body').hidden = true;
    $('insp-err').hidden = true;
    fitCanvasFrame();
    syncModeToCanvas();
  }

  function openFile(fileId) {
    state.fileId = fileId;
    state.selection = null;
    closeInspector();
    renderLists();
    $('b-add-slide').hidden = state.tab !== 'templates' || fileId.indexOf('templates/') !== 0;
    fitCanvasFrame();
    canvas.onload = function () {
      canvas.onload = null;
      syncModeToCanvas();
    };
    canvas.src = '/__canvas?file=' + encodeURIComponent(fileId) + '&t=' + Date.now();
    $('sel-label').textContent = fileId;
  }

  function clearInspector() {
    $('insp-body').hidden = true;
    $('insp-err').hidden = true;
  }

  function fillInspector(sel) {
    openInspector();
    $('insp-body').hidden = false;
    $('insp-err').hidden = true;
    $('insp-addr').textContent = addrOf(sel);
    $('insp-meta').textContent = [sel.label, sel.tag, sel.file].filter(Boolean).join(' · ');

    var text = $('f-text');
    var hint = $('text-hint');
    if (sel.textEditable) {
      text.disabled = false;
      text.value = sel.text || '';
      hint.hidden = true;
    } else {
      text.disabled = true;
      text.value = '';
      hint.hidden = false;
      hint.textContent = '중첩 마크업이 있어 텍스트는 읽기 전용입니다. 스타일만 수정할 수 있습니다.';
    }

    var cs = sel.computedStyle || {};
    Object.keys(STYLE_MAP).forEach(function (prop) {
      var input = $(STYLE_MAP[prop]);
      if (!input) return;
      input.value = (cs[prop] || '').trim();
      input.dataset.prop = prop;
    });
  }

  function collectChanges(clearStyles) {
    var changes = {};
    var sel = state.selection;
    if (!sel) return null;
    if (sel.textEditable) {
      var t = $('f-text').value;
      if (t !== (sel.text || '')) changes.text = t;
    }
    if (clearStyles) {
      changes.style = {};
      Object.keys(STYLE_MAP).forEach(function (p) { changes.style[p] = null; });
      return changes;
    }
    var style = {};
    var any = false;
    Object.keys(STYLE_MAP).forEach(function (prop) {
      var input = $(STYLE_MAP[prop]);
      var val = (input.value || '').trim();
      var prev = ((sel.computedStyle || {})[prop] || '').trim();
      // Only send when user typed something different; empty means "clear local if was edited" — skip unless was intentionally cleared via button
      if (val && val !== prev) {
        style[prop] = val;
        any = true;
      }
    });
    if (any) changes.style = style;
    return Object.keys(changes).length ? changes : null;
  }

  function pushHistory(entry) {
    state.undo.push(entry);
    if (state.undo.length > 50) state.undo.shift();
    state.redo = [];
  }

  async function api(method, path, body) {
    var opts = { method: method, cache: 'no-store', headers: {} };
    if (body !== undefined) {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(body);
    }
    var res = await fetch(path, opts);
    var data = null;
    try { data = await res.json(); } catch (e) { data = {}; }
    if (!res.ok) {
      var err = new Error((data && data.error) || (res.status + ' ' + path));
      err.status = res.status;
      err.data = data;
      throw err;
    }
    return data;
  }

  async function applyPatch(changes, fromHistory) {
    if (!changes || !state.selection) return;
    var entry = currentEntry();
    if (!entry) return;
    var sel = state.selection;
    var inverse = { text: sel.textEditable ? sel.text : undefined, style: {} };
    // approximate inverse: set previous computed values for changed keys
    if (changes.style) {
      Object.keys(changes.style).forEach(function (k) {
        inverse.style[k] = (sel.computedStyle && sel.computedStyle[k]) || null;
      });
    }

    state.busy = true;
    try {
      var result = await api('PATCH', '/__edit', {
        fileId: entry.id,
        baseRevision: entry.revision,
        target: { region: sel.region, part: sel.part },
        changes: changes
      });
      entry.revision = result.revision;
      if (!fromHistory) {
        pushHistory({
          fileId: entry.id,
          target: { region: sel.region, part: sel.part },
          forward: changes,
          inverse: { text: inverse.text, style: inverse.style }
        });
      }
      // refresh selection snapshot after reload
      await reloadProject(false);
      reopenWithHighlight(sel.region, sel.part);
      toast('저장됨');
    } catch (e) {
      showErr(e);
      if (e.status === 409) {
        await reloadProject(true);
        toast('파일이 밖에서 바뀌었습니다. 다시 선택해 주세요.');
        state.undo = [];
        state.redo = [];
      }
    } finally {
      state.busy = false;
    }
  }

  function showErr(e) {
    var box = $('insp-err');
    box.hidden = false;
    box.textContent = (e && e.message) ? e.message : String(e);
  }

  function reopenWithHighlight(region, part) {
    if (!state.fileId) return;
    var url = '/__canvas?file=' + encodeURIComponent(state.fileId) + '&t=' + Date.now();
    canvas.onload = function () {
      canvas.onload = null;
      syncModeToCanvas();
      setTimeout(function () {
        canvas.contentWindow.postMessage({
          source: 'slidecraft-shell',
          type: 'highlight',
          region: region,
          part: part || null
        }, location.origin);
      }, 60);
    };
    canvas.src = url;
  }

  async function reloadProject(forceOpen) {
    var prev = state.fileId;
    var p = await api('GET', '/__project');
    state.project = p;
    state.token = p.token;
    renderLists();
    fitCanvasFrame();
    if (forceOpen || !prev) {
      var first = (p.slides && p.slides[0]) || (p.templates && p.templates[0]);
      if (first) openFile(first.id);
    } else {
      // refresh revision for current file
      var ent = currentEntry();
      if (!ent) {
        var fallback = (p.slides && p.slides[0]);
        if (fallback) openFile(fallback.id);
      }
    }
    if (state.tab === 'palette') renderPalette();
  }

  function renderPalette() {
    var pane = $('palette-pane');
    var tokens = (state.project && state.project.palette) || {};
    var keys = Object.keys(tokens);
    if (!keys.length) {
      pane.innerHTML = '<div class="muted">theme.css 토큰이 없습니다.</div>';
      return;
    }
    pane.innerHTML = '';
    keys.forEach(function (name) {
      var row = document.createElement('div');
      row.className = 'swatch';
      var chip = document.createElement('div');
      chip.className = 'chip';
      chip.style.background = tokens[name];
      var label = document.createElement('div');
      label.textContent = name;
      var color = document.createElement('input');
      color.type = 'color';
      var text = document.createElement('input');
      text.type = 'text';
      text.value = tokens[name];
      var hex = toHex(tokens[name]);
      if (hex) color.value = hex;
      function commit() {
        var val = text.value.trim();
        if (!val) return;
        patchTheme(name, val);
      }
      color.oninput = function () { text.value = color.value; chip.style.background = color.value; };
      color.onchange = commit;
      text.onchange = commit;
      row.appendChild(chip);
      row.appendChild(label);
      var right = document.createElement('div');
      right.style.display = 'grid';
      right.style.gap = '4px';
      right.appendChild(color);
      right.appendChild(text);
      row.appendChild(right);
      // fix grid: put text under name spanning
      row.innerHTML = '';
      row.style.gridTemplateColumns = '28px 1fr';
      var left = document.createElement('div');
      left.className = 'chip';
      left.style.background = tokens[name];
      var mid = document.createElement('div');
      mid.innerHTML = '<div style="margin-bottom:4px">' + escapeHtml(name) + '</div>';
      var row2 = document.createElement('div');
      row2.style.display = 'grid';
      row2.style.gridTemplateColumns = '40px 1fr';
      row2.style.gap = '6px';
      var c2 = document.createElement('input');
      c2.type = 'color';
      if (hex) c2.value = hex;
      var t2 = document.createElement('input');
      t2.type = 'text';
      t2.value = tokens[name];
      c2.oninput = function () { t2.value = c2.value; left.style.background = c2.value; };
      function save() { patchTheme(name, t2.value.trim()); }
      c2.onchange = save;
      t2.onchange = save;
      row2.appendChild(c2);
      row2.appendChild(t2);
      mid.appendChild(row2);
      row.appendChild(left);
      row.appendChild(mid);
      pane.appendChild(row);
    });
  }

  function toHex(v) {
    if (!v) return null;
    v = v.trim();
    if (/^#[0-9a-fA-F]{6}$/.test(v)) return v;
    if (/^#[0-9a-fA-F]{3}$/.test(v)) {
      return '#' + v[1] + v[1] + v[2] + v[2] + v[3] + v[3];
    }
    var m = /^rgba?\((\d+),\s*(\d+),\s*(\d+)/.exec(v);
    if (!m) return null;
    function h(n) { return ('0' + Number(n).toString(16)).slice(-2); }
    return '#' + h(m[1]) + h(m[2]) + h(m[3]);
  }

  async function patchTheme(name, value) {
    try {
      var rev = state.project.themeRevision;
      var data = await api('PATCH', '/__theme', {
        baseRevision: rev,
        changes: { [name]: value }
      });
      state.project.themeRevision = data.revision;
      state.project.palette = data.palette || state.project.palette;
      if (state.project.palette) state.project.palette[name] = value;
      renderPalette();
      if (state.fileId) reopenWithHighlight(
        state.selection && state.selection.region,
        state.selection && state.selection.part
      );
      toast('팔레트 저장됨');
    } catch (e) {
      toast(e.message || '팔레트 저장 실패');
      if (e.status === 409) {
        await reloadProject(false);
        state.undo = [];
        state.redo = [];
      }
    }
  }

  async function undoRedo(dir) {
    var stack = dir < 0 ? state.undo : state.redo;
    var other = dir < 0 ? state.redo : state.undo;
    var item = stack.pop();
    if (!item) return;
    other.push(item);
    state.fileId = item.fileId;
    var entry = currentEntry();
    if (!entry) return;
    var changes = dir < 0 ? item.inverse : item.forward;
    // clean inverse text if undefined
    var payload = {};
    if (changes.text !== undefined) payload.text = changes.text;
    if (changes.style) payload.style = changes.style;
    try {
      var result = await api('PATCH', '/__edit', {
        fileId: item.fileId,
        baseRevision: entry.revision,
        target: item.target,
        changes: payload
      });
      entry.revision = result.revision;
      reopenWithHighlight(item.target.region, item.target.part);
    } catch (e) {
      toast(e.message || '되돌리기 실패');
    }
  }

  window.addEventListener('message', function (e) {
    if (e.origin !== location.origin) return;
    if (!e.data || e.data.source !== 'slidecraft-bridge') return;
    if (e.source !== canvas.contentWindow) return;
    if (e.data.type === 'ready') {
      syncModeToCanvas();
    } else if (e.data.type === 'modeChanged') {
      state.sel = !!e.data.select;
      state.grid = !!e.data.grid;
      paintModeButtons();
    } else if (e.data.type === 'select') {
      state.selection = e.data;
      fillInspector(e.data);
      $('sel-label').textContent = addrOf(e.data);
    } else if (e.data.type === 'deselect') {
      state.selection = null;
      closeInspector();
      $('sel-label').textContent = state.fileId || '';
    }
  });

  document.querySelectorAll('.tabs button').forEach(function (b) {
    b.onclick = function () { setTab(b.getAttribute('data-tab')); };
  });

  $('b-apply').onclick = function () {
    var changes = collectChanges(false);
    if (!changes) { toast('변경 없음'); return; }
    applyPatch(changes, false);
  };
  $('b-clear-style').onclick = function () {
    applyPatch(collectChanges(true), false);
  };
  $('b-undo').onclick = function () { undoRedo(-1); };
  $('b-redo').onclick = function () { undoRedo(1); };
  $('b-sel').onclick = function () {
    state.sel = !state.sel;
    paintModeButtons();
    syncModeToCanvas();
  };
  $('b-grid').onclick = function () {
    state.grid = !state.grid;
    if (state.grid) state.sel = true;
    paintModeButtons();
    syncModeToCanvas();
  };
  $('b-save').onclick = function () { location.href = '/__download'; };
  $('b-pdf').onclick = function () { canvas.contentWindow.print(); };
  $('b-add-slide').onclick = async function () {
    if (!state.fileId || state.fileId.indexOf('templates/') !== 0) return;
    try {
      var data = await api('POST', '/__slides/from-template', { templateId: state.fileId });
      await reloadProject(false);
      openFile(data.fileId);
      setTab('slides');
      toast('슬라이드 추가됨');
    } catch (e) {
      toast(e.message || '추가 실패');
    }
  };

  $('f-text').addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      $('b-apply').click();
    }
  });

  document.addEventListener('keydown', function (e) {
    var mod = e.metaKey || e.ctrlKey;
    if (mod && e.key.toLowerCase() === 'z') {
      e.preventDefault();
      undoRedo(e.shiftKey ? 1 : -1);
      return;
    }
    if (mod) return;
    var tag = (e.target && e.target.tagName || '').toLowerCase();
    if (tag === 'input' || tag === 'textarea' || tag === 'select') return;
    if (e.key === 's' || e.key === 'S') {
      state.sel = !state.sel;
      paintModeButtons();
      syncModeToCanvas();
    } else if (e.key === 'g' || e.key === 'G') {
      state.grid = !state.grid;
      if (state.grid) state.sel = true;
      paintModeButtons();
      syncModeToCanvas();
    } else if (e.key === 'Escape') {
      state.selection = null;
      closeInspector();
      $('sel-label').textContent = state.fileId || '';
      try {
        canvas.contentWindow.postMessage({ source: 'slidecraft-shell', type: 'clear' }, location.origin);
      } catch (err) {}
    }
  });

  function poll() {
    fetch('/__token', { cache: 'no-store' }).then(function (r) { return r.text(); })
      .then(function (t) {
        live(true);
        t = t.trim();
        if (t && state.token && t !== state.token && !state.busy) {
          var sel = state.selection;
          reloadProject(false).then(function () {
            if (state.fileId) {
              if (sel && sel.region) reopenWithHighlight(sel.region, sel.part);
              else openFile(state.fileId);
            }
          });
        }
      }).catch(function () { live(false); });
  }

  addEventListener('resize', function () {
    fitCanvasFrame();
    syncModeToCanvas();
  });

  paintModeButtons();
  closeInspector();

  reloadProject(true).then(function () {
    fitCanvasFrame();
    setInterval(poll, 600);
  }).catch(function (e) {
    live(false);
    toast(e.message || '프로젝트를 불러오지 못했습니다');
  });
})();
