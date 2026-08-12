/* Canvas bridge — injected only into /__canvas responses, never written to source files. */
(function () {
  'use strict';
  var ORIGIN = location.origin;
  var FILE = document.documentElement.getAttribute('data-editor-file') || '';
  var selected = null;
  var mode = { select: false, grid: false };

  var STYLE_PROPS = [
    'color', 'background-color', 'font-size', 'font-weight', 'text-align',
    'width', 'height', 'padding', 'gap', 'border-radius'
  ];

  function post(type, payload) {
    parent.postMessage(Object.assign({ source: 'slidecraft-bridge', type: type }, payload || {}), ORIGIN);
  }

  function closestTarget(node) {
    if (!node || node.nodeType !== 1) return null;
    // overlays are pointer-events:none, but guard anyway
    if (node.closest && node.closest('#rg-layer, #rg-legend, .rg-box, .rg-badge')) return null;
    var part = node.closest('[data-part]');
    if (part) {
      var region = part.closest('[data-region]');
      if (region) {
        return {
          el: part,
          region: region.getAttribute('data-region'),
          part: part.getAttribute('data-part'),
          host: region
        };
      }
    }
    var regionOnly = node.closest('[data-region]');
    if (regionOnly) {
      return {
        el: regionOnly,
        region: regionOnly.getAttribute('data-region'),
        part: null,
        host: regionOnly
      };
    }
    return null;
  }

  function isLeafText(el) {
    if (!el) return false;
    for (var i = 0; i < el.childNodes.length; i++) {
      var n = el.childNodes[i];
      if (n.nodeType === 1) return false;
    }
    return true;
  }

  function computedBag(el) {
    var cs = getComputedStyle(el);
    var out = {};
    STYLE_PROPS.forEach(function (p) { out[p] = cs.getPropertyValue(p); });
    return out;
  }

  function clearOutline() {
    document.querySelectorAll('.sc-selected, .sc-hover').forEach(function (n) {
      n.classList.remove('sc-selected');
      n.classList.remove('sc-hover');
    });
  }

  function paintSelection(el) {
    document.querySelectorAll('.sc-selected').forEach(function (n) {
      n.classList.remove('sc-selected');
    });
    if (el) el.classList.add('sc-selected');
  }

  function emitSelect(t) {
    selected = t;
    paintSelection(t && t.el);
    if (!t) {
      post('deselect', { file: FILE });
      return;
    }
    var textEditable = isLeafText(t.el);
    post('select', {
      file: FILE,
      region: t.region,
      part: t.part,
      label: (t.host && t.host.getAttribute('data-label')) || t.el.getAttribute('data-label') || '',
      tag: t.el.tagName.toLowerCase(),
      text: textEditable ? (t.el.textContent || '') : null,
      textEditable: textEditable,
      computedStyle: computedBag(t.el)
    });
  }

  function applyRegionMode() {
    if (typeof window.slideMode !== 'function') return;
    if (mode.select) {
      window.slideMode('select', { grid: mode.grid, level: 1 });
    } else {
      window.slideMode('preview', { grid: false, level: 1 });
    }
    // address book table is for agent map/shot; hide in visual editor
    var lg = document.getElementById('rg-legend');
    if (lg) lg.style.display = 'none';
  }

  document.addEventListener('mouseover', function (e) {
    var t = closestTarget(e.target);
    document.querySelectorAll('.sc-hover').forEach(function (n) {
      if (!n.classList.contains('sc-selected')) n.classList.remove('sc-hover');
    });
    if (t && t.el && !t.el.classList.contains('sc-selected')) {
      t.el.classList.add('sc-hover');
    }
  }, true);

  document.addEventListener('mouseout', function (e) {
    var t = closestTarget(e.target);
    if (t && t.el && !t.el.contains(e.relatedTarget)) {
      t.el.classList.remove('sc-hover');
    }
  }, true);

  document.addEventListener('click', function (e) {
    var t = closestTarget(e.target);
    if (!t) {
      emitSelect(null);
      return;
    }
    e.preventDefault();
    e.stopPropagation();
    emitSelect(t);
  }, true);

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      emitSelect(null);
      return;
    }
    var k = e.key.toLowerCase();
    if (k === 's' || k === 'g') {
      e.preventDefault();
      e.stopPropagation();
      if (k === 's') mode.select = !mode.select;
      if (k === 'g') {
        mode.grid = !mode.grid;
        if (mode.grid) mode.select = true;
      }
      applyRegionMode();
      post('modeChanged', { select: mode.select, grid: mode.grid });
    }
  }, true);

  window.addEventListener('message', function (e) {
    if (e.origin !== ORIGIN) return;
    var d = e.data || {};
    if (!d || d.source !== 'slidecraft-shell') return;
    if (d.type === 'mode') {
      mode.select = !!d.select;
      mode.grid = !!d.grid;
      applyRegionMode();
      fitSlide();
      applyRegionMode();
    }
    if (d.type === 'clear') {
      emitSelect(null);
    }
    if (d.type === 'highlight' && d.region) {
      var sel = '[data-region="' + CSS.escape(d.region) + '"]';
      if (d.part) sel += ' [data-part="' + CSS.escape(d.part) + '"]';
      var el = document.querySelector(sel);
      if (el) {
        var region = el.closest('[data-region]') || el;
        emitSelect({
          el: el,
          region: region.getAttribute('data-region'),
          part: el.getAttribute('data-part'),
          host: region
        });
      }
    }
    if (d.type === 'ping') post('ready', { file: FILE });
  });

  var style = document.createElement('style');
  style.textContent = [
    '[data-region],[data-part]{cursor:pointer}',
    '.sc-hover{outline:2px dashed #60a5fa!important;outline-offset:2px!important;cursor:pointer!important}',
    '.sc-selected{outline:2px solid #2563EB!important;outline-offset:2px!important;cursor:default!important}',
    '#rg-legend{display:none!important}',
    'html,body{margin:0;width:100%;height:100%;background:#1a1c1f;overflow:hidden}',
    'body{display:flex;align-items:center;justify-content:center;box-sizing:border-box}',
    '.slide{flex:none;box-shadow:0 18px 60px rgba(0,0,0,.45);transform-origin:center center}'
  ].join('');
  document.head.appendChild(style);

  function fitSlide() {
    var slide = document.querySelector('.slide');
    if (!slide) return;
    var W = slide.offsetWidth || 1280;
    var H = slide.offsetHeight || 720;
    var pad = 16;
    var k = Math.min((innerWidth - pad) / W, (innerHeight - pad) / H, 1);
    if (!isFinite(k) || k <= 0) k = 1;
    slide.style.transform = 'scale(' + k + ')';
  }

  function boot() {
    fitSlide();
    applyRegionMode();
    post('ready', { file: FILE });
  }

  addEventListener('resize', function () {
    fitSlide();
    if (mode.select) applyRegionMode();
  });
  if (document.fonts && document.fonts.ready) {
    document.fonts.ready.then(function () { fitSlide(); if (mode.select) applyRegionMode(); }).catch(function () {});
  }
  requestAnimationFrame(function () {
    requestAnimationFrame(boot);
  });
})();
