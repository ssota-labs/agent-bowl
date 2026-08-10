/* html-slides runtime — 영역(region) 주소 체계 + 미리보기/선택 모드
 *
 * 핵심 규약
 *  - [data-region="id"]  : 1레벨 주소 대상 (블록)
 *  - [data-part="id"]    : 2레벨 주소 대상 (블록 내부 조각) → "region.part"
 *  - data-label="한글이름": 사람이 부르는 이름 (권장, 강력히)
 *  - data-role="역할"     : 역할 힌트 오버라이드
 *  - data-region-color="red" : 색상 고정(선택). 미지정 시 문서 순서대로 자동 배정
 *
 * 색상은 "문서 순서"대로 팔레트에서 배정된다. 즉 번호 N == 팔레트 N번 색.
 * 오버레이는 별도 레이어에 절대좌표로 그려지므로 원본 레이아웃에 영향이 없다.
 */
(function () {
  'use strict';

  var PALETTE = [
    { ko: '빨강', en: 'red',    hex: '#E23A2E' },
    { ko: '파랑', en: 'blue',   hex: '#2563EB' },
    { ko: '초록', en: 'green',  hex: '#17A24A' },
    { ko: '주황', en: 'orange', hex: '#F1830B' },
    { ko: '보라', en: 'purple', hex: '#8B3FD1' },
    { ko: '청록', en: 'teal',   hex: '#0DA9A0' },
    { ko: '분홍', en: 'pink',   hex: '#E5399B' },
    { ko: '노랑', en: 'yellow', hex: '#C99700' },
    { ko: '남색', en: 'navy',   hex: '#2B3A8F' },
    { ko: '연두', en: 'lime',   hex: '#7CB518' },
    { ko: '갈색', en: 'brown',  hex: '#8A5A33' },
    { ko: '회색', en: 'gray',   hex: '#6B7280' }
  ];

  var ZONE_ROW = ['상', '중', '하'];
  var ZONE_NAME = [
    ['좌상단', '상단중앙', '우상단'],
    ['좌측중앙', '정중앙', '우측중앙'],
    ['좌하단', '하단중앙', '우하단']
  ];

  function slideEl() {
    // 덱 뷰어(dist/deck.html)에서는 현재 보이는 슬라이드가 대상이 된다.
    return document.querySelector('.slide.is-active') || document.querySelector('.slide') || document.body;
  }

  function txt(el) {
    var t = (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim();
    return t.length > 70 ? t.slice(0, 70) + '…' : t;
  }

  function roleOf(el) {
    if (el.dataset.role) return el.dataset.role;
    var tag = el.tagName.toLowerCase();
    if (el.querySelector('svg, canvas')) return '차트/그래픽';
    if (tag === 'img' || el.querySelector('img')) return '이미지';
    if (tag === 'table' || el.querySelector('table')) return '표';
    if (tag === 'ul' || tag === 'ol' || el.querySelector('ul,ol')) return '목록';
    if (/^h[1-3]$/.test(tag) || el.querySelector('h1,h2')) return '제목';
    if (/^h[4-6]$/.test(tag)) return '소제목';
    if (tag === 'footer' || /footer|footnote|source/.test(el.className)) return '푸터/출처';
    return '박스';
  }

  /* 실제 렌더링 배경색을 한국어 색 이름으로. 사용자가 "빨간 박스"라고 할 때
     선택모드 오버레이 색인지 디자인 색인지 둘 다 조회할 수 있게 한다. */
  function colorName(css) {
    var m = /rgba?\(([^)]+)\)/.exec(css || '');
    if (!m) return '';
    var v = m[1].split(',').map(parseFloat);
    var a = v.length > 3 ? v[3] : 1;
    if (a < 0.06) return '';
    var r = v[0] / 255, g = v[1] / 255, b = v[2] / 255;
    var mx = Math.max(r, g, b), mn = Math.min(r, g, b), d = mx - mn;
    var l = (mx + mn) / 2;
    var s = d === 0 ? 0 : d / (1 - Math.abs(2 * l - 1));
    // 채도가 낮거나 RGB 폭이 좁으면 무채색으로 본다 (#f3f5f8 같은 미세한 푸른 회색 방지)
    if (s < 0.12 || d < 0.09) {
      return l > 0.9 ? '흰색' : l > 0.72 ? '아주 밝은 회색' : l > 0.45 ? '회색' : l > 0.2 ? '진회색' : '검정';
    }
    var h = 0;
    if (mx === r) h = 60 * (((g - b) / d) % 6);
    else if (mx === g) h = 60 * ((b - r) / d + 2);
    else h = 60 * ((r - g) / d + 4);
    if (h < 0) h += 360;
    var name =
      h < 15 || h >= 345 ? '빨강' :
      h < 40 ? '주황' : h < 65 ? '노랑' : h < 95 ? '연두' : h < 150 ? '초록' :
      h < 190 ? '청록' : h < 215 ? '하늘' : h < 250 ? (l < 0.4 ? '남색' : '파랑') :
      h < 285 ? '보라' : h < 320 ? '자주' : '분홍';
    if (name !== '남색') {
      if (l < 0.28) name = '진한 ' + name;
      else if (l > 0.78) name = '연한 ' + name;
    }
    return name;
  }

  function paintedBg(el, root) {
    var n = el;
    while (n && n !== root.parentNode) {
      var c = colorName(getComputedStyle(n).backgroundColor);
      if (c) return { name: c, css: getComputedStyle(n).backgroundColor, self: n === el };
      n = n.parentNode;
      if (!n || n.nodeType !== 1) break;
    }
    return { name: '', css: '', self: false };
  }

  function zoneOf(cx, cy, w, h) {
    var col = cx < 1 / 3 ? 0 : cx < 2 / 3 ? 1 : 2;
    var row = cy < 1 / 3 ? 0 : cy < 2 / 3 ? 1 : 2;
    var name = ZONE_NAME[row][col];
    if (w >= 0.8 && h >= 0.8) name = '전체 배경';
    else if (w >= 0.8) name = ZONE_ROW[row] + '단 가로 전폭';
    else if (h >= 0.8) name = (col === 0 ? '좌' : col === 2 ? '우' : '중앙') + '측 세로 전체';
    return name;
  }

  /* 세로로 겹치는 영역끼리 "행"으로 묶고, 행 안에서 좌→우 순번을 매긴다.
     "위쪽 카드 3개 중 가운데" 같은 표현을 해석하기 위한 데이터. */
  function groupRows(items) {
    var flow = items.filter(function (r) { return !(r.box.w >= 0.8 && r.box.h >= 0.8); });
    var sorted = flow.slice().sort(function (a, b) { return a.box.y - b.box.y; });
    var rows = [];
    sorted.forEach(function (r) {
      var placed = false;
      for (var i = 0; i < rows.length; i++) {
        var row = rows[i];
        var overlap = Math.min(row.bottom, r.box.y + r.box.h) - Math.max(row.top, r.box.y);
        var minH = Math.min(row.bottom - row.top, r.box.h);
        if (minH > 0 && overlap / minH > 0.5) {
          row.items.push(r);
          row.top = Math.min(row.top, r.box.y);
          row.bottom = Math.max(row.bottom, r.box.y + r.box.h);
          placed = true;
          break;
        }
      }
      if (!placed) rows.push({ top: r.box.y, bottom: r.box.y + r.box.h, items: [r] });
    });
    rows.sort(function (a, b) { return a.top - b.top; });
    rows.forEach(function (row, ri) {
      row.items.sort(function (a, b) { return a.box.x - b.box.x; });
      row.items.forEach(function (r, ci) {
        r.row = ri + 1;
        r.col = ci + 1;
        r.rowCount = row.items.length;
      });
    });
    items.forEach(function (r) {
      if (!r.row) { r.row = 0; r.col = 0; r.rowCount = 0; }
    });
    return items;
  }

  function pct(v) { return Math.round(v * 1000) / 10; }

  /** 슬라이드의 모든 영역을 측정해 주소록(map)을 만든다. */
  function regionMap() {
    var slide = slideEl();
    var sb = slide.getBoundingClientRect();
    // 미리보기는 슬라이드를 CSS transform 으로 축소해 보여준다. 이때
    // getBoundingClientRect 는 축소된 화면 좌표를 주는데, 오버레이는 축소되는
    // 요소 '안쪽'에 붙으므로 좌표를 되돌려 놓지 않으면 배지·상자가 어긋난다.
    var sk = slide.offsetWidth ? sb.width / slide.offsetWidth : 1;
    if (!sk || !isFinite(sk)) sk = 1;
    var els = Array.prototype.slice.call(slide.querySelectorAll('[data-region]'));

    var used = {};
    els.forEach(function (el) {
      var pin = el.dataset.regionColor;
      if (pin) {
        for (var i = 0; i < PALETTE.length; i++) {
          if (PALETTE[i].en === pin || PALETTE[i].ko === pin) { used[i] = el; el.__pin = i; }
        }
      }
    });

    var next = 0;
    var items = els.map(function (el, idx) {
      var ci;
      if (el.__pin !== undefined) {
        ci = el.__pin;
      } else {
        while (used[next] !== undefined && next < PALETTE.length) next++;
        ci = next % PALETTE.length;
        used[ci] = el;
        next++;
      }
      var c = PALETTE[ci];
      var b = el.getBoundingClientRect();
      var box = {
        x: (b.left - sb.left) / sb.width,
        y: (b.top - sb.top) / sb.height,
        w: b.width / sb.width,
        h: b.height / sb.height
      };
      var parts = Array.prototype.slice.call(el.querySelectorAll('[data-part]')).map(function (p) {
        var pb = p.getBoundingClientRect();
        return {
          id: el.dataset.region + '.' + p.dataset.part,
          label: p.dataset.label || '',
          text: txt(p),
          box: {
            x: (pb.left - sb.left) / sb.width,
            y: (pb.top - sb.top) / sb.height,
            w: pb.width / sb.width,
            h: pb.height / sb.height
          }
        };
      });
      var bg = paintedBg(el, slide);
      return {
        n: idx + 1,
        id: el.dataset.region,
        label: el.dataset.label || '',
        role: roleOf(el),
        color: c.ko,
        colorEn: c.en,
        hex: c.hex,
        bg: bg.self ? bg.name : '',          // 이 영역이 직접 칠한 배경색 (한국어)
        bgInherited: bg.self ? '' : bg.name, // 상위에서 물려받은 배경색
        box: box,
        px: {
          x: Math.round((b.left - sb.left) / sk), y: Math.round((b.top - sb.top) / sk),
          w: Math.round(b.width / sk), h: Math.round(b.height / sk)
        },
        zone: zoneOf(box.x + box.w / 2, box.y + box.h / 2, box.w, box.h),
        text: txt(el),
        parts: parts
      };
    });

    groupRows(items);
    els.forEach(function (el) { delete el.__pin; });

    return {
      slide: {
        file: (location.pathname.split('/').pop() || ''),
        no: slide.dataset.slide || '',
        title: slide.dataset.title || document.title || '',
        w: Math.round(sb.width),
        h: Math.round(sb.height)
      },
      palette: PALETTE,
      regions: items,
      warnings: items.length > PALETTE.length
        ? ['영역이 ' + items.length + '개로 팔레트(12색)를 초과 — 색상이 중복됩니다. 영역을 묶어 12개 이하로 줄이세요.']
        : []
    };
  }

  /* ---------------------------------------------------------------- 오버레이 */

  function clear() {
    var old = document.getElementById('rg-layer');
    if (old) old.remove();
    var lg = document.getElementById('rg-legend');
    if (lg) lg.remove();
    document.documentElement.classList.remove('rg-on');
  }

  function render(opts) {
    opts = opts || {};
    clear();

    // rg-on 은 페이지 레이아웃(정렬·스크롤)을 바꾼다. 반드시 먼저 붙이고
    // 리플로우를 강제한 뒤에 좌표를 재야 오버레이가 어긋나지 않는다.
    document.documentElement.classList.add('rg-on');
    void document.documentElement.offsetHeight;

    var data = regionMap();
    var slide = slideEl();
    // 레이어는 슬라이드 안쪽(스케일 전 좌표계)에 놓이므로 화면 크기가 아니라
    // 슬라이드 자체 크기를 기준으로 계산한다.
    var sb = { width: slide.offsetWidth, height: slide.offsetHeight };
    var focus = opts.focus || null;

    // 레이어를 슬라이드 안에 넣는다. 페이지 정렬·스크롤바 때문에 슬라이드가 움직여도
    // 레이어가 함께 움직이므로 오버레이가 절대 어긋나지 않는다.
    var layer = document.createElement('div');
    layer.id = 'rg-layer';
    layer.style.cssText = 'position:absolute;pointer-events:none;z-index:99998;' +
      'left:0;top:0;width:100%;height:100%;';

    if (opts.grid) {
      for (var i = 1; i < 3; i++) {
        ['left', 'top'].forEach(function (side) {
          var g = document.createElement('div');
          g.className = 'rg-grid';
          g.style.cssText = side === 'left'
            ? 'position:absolute;left:' + (i * 33.333) + '%;top:0;bottom:0;width:0;border-left:1px dashed rgba(0,0,0,.28)'
            : 'position:absolute;top:' + (i * 33.333) + '%;left:0;right:0;height:0;border-top:1px dashed rgba(0,0,0,.28)';
          layer.appendChild(g);
        });
      }
      ZONE_NAME.forEach(function (r, ri) {
        r.forEach(function (name, ci) {
          var z = document.createElement('div');
          z.className = 'rg-zone';
          z.textContent = name;
          // 존 이름은 칸 한가운데가 아니라 좌상단 구석에 — 콘텐츠 위를 덮지 않게
          z.style.cssText = 'position:absolute;left:' + (ci * 33.333) + '%;top:' + (ri * 33.333) + '%;' +
            'width:33.333%;height:33.333%;padding:4px 0 0 6px;box-sizing:border-box;' +
            'font:700 11px/1 system-ui,sans-serif;color:rgba(0,0,0,.3)';
          layer.appendChild(z);
        });
      });
    }

    if (focus) {
      var hit = data.regions.filter(function (r) { return r.id === focus; })[0];
      if (hit) {
        var scrim = document.createElement('div');
        scrim.style.cssText = 'position:absolute;overflow:hidden;inset:0;';
        var hole = document.createElement('div');
        hole.style.cssText = 'position:absolute;border-radius:8px;' +
          'left:' + hit.px.x + 'px;top:' + hit.px.y + 'px;width:' + hit.px.w + 'px;height:' + hit.px.h + 'px;' +
          'box-shadow:0 0 0 9999px rgba(255,255,255,.78);';
        scrim.appendChild(hole);
        layer.appendChild(scrim);
      }
    }

    data.regions.forEach(function (r) {
      var dim = focus && r.id !== focus;
      var box = document.createElement('div');
      box.className = 'rg-box';
      box.style.cssText = 'position:absolute;box-sizing:border-box;' +
        'left:' + r.px.x + 'px;top:' + r.px.y + 'px;width:' + r.px.w + 'px;height:' + r.px.h + 'px;' +
        'border:' + (focus && !dim ? '3px solid ' : '2px dashed ') + r.hex + ';border-radius:6px;' +
        'background:' + r.hex + (dim || focus ? '00' : '1A') + ';' +
        'opacity:' + (dim ? '.3' : '1') + ';';
      layer.appendChild(box);

      var badge = document.createElement('div');
      badge.className = 'rg-badge';
      badge.textContent = r.n + ' · ' + r.color + ' · ' + (r.label || r.id);
      var above = r.px.y >= 22;
      badge.style.cssText = 'position:absolute;left:' + r.px.x + 'px;' +
        'top:' + (above ? r.px.y - 21 : r.px.y + 2) + 'px;' +
        'background:' + r.hex + ';color:#fff;font:700 12px/1 -apple-system,"Apple SD Gothic Neo",system-ui,sans-serif;' +
        'padding:4px 7px;border-radius:4px;white-space:nowrap;opacity:' + (dim ? '.3' : '1') + ';' +
        'box-shadow:0 1px 3px rgba(0,0,0,.35)';
      layer.appendChild(badge);

      if (opts.level >= 2 && !dim) {
        r.parts.forEach(function (p) {
          var pb = document.createElement('div');
          pb.style.cssText = 'position:absolute;box-sizing:border-box;' +
            'left:' + (p.box.x * sb.width) + 'px;top:' + (p.box.y * sb.height) + 'px;' +
            'width:' + (p.box.w * sb.width) + 'px;height:' + (p.box.h * sb.height) + 'px;' +
            'border:1px dotted ' + r.hex + ';background:transparent;';
          layer.appendChild(pb);
          // 부품 이름표는 상자 '위 오른쪽 바깥'에 둔다. 안에 두면 본문 글자를 덮는다.
          var pl = document.createElement('div');
          pl.textContent = p.id.split('.')[1];
          var pTop = p.box.y * sb.height;
          pl.style.cssText = 'position:absolute;right:' +
            (sb.width - (p.box.x + p.box.w) * sb.width) + 'px;' +
            'top:' + (pTop >= 12 ? pTop - 12 : pTop) + 'px;' +
            'font:700 9px/1 system-ui,sans-serif;color:#fff;background:' + r.hex +
            ';opacity:.85;padding:2px 4px;border-radius:3px;white-space:nowrap';
          layer.appendChild(pl);
        });
      }
    });

    slide.appendChild(layer);

    if (opts.legend !== false) {
      var lg = document.createElement('div');
      lg.id = 'rg-legend';
      var rows = data.regions.map(function (r) {
        var pos = r.zone + (r.rowCount > 1 ? ' · ' + r.row + '행 ' + r.col + '/' + r.rowCount : '');
        return '<tr>' +
          '<td><span class="sw" style="background:' + r.hex + '"></span>' + r.n + '</td>' +
          '<td>' + r.color + '</td>' +
          '<td><b>' + (r.label || '—') + '</b></td>' +
          '<td><code>' + r.id + '</code></td>' +
          '<td>' + pos + '</td>' +
          '<td>' + r.role + '</td>' +
          '<td class="tx">' + (r.text || '').replace(/</g, '&lt;').slice(0, 46) + '</td>' +
          '</tr>';
      }).join('');
      lg.innerHTML =
        '<h4>영역 주소록 — ' + (data.slide.title || data.slide.file) + '</h4>' +
        '<table><thead><tr><th>#</th><th>색</th><th>이름</th><th>id</th><th>위치</th><th>역할</th><th>내용</th></tr></thead>' +
        '<tbody>' + rows + '</tbody></table>' +
        (data.warnings.length ? '<p class="warn">⚠ ' + data.warnings.join(' ') + '</p>' : '');
      document.body.appendChild(lg);
    }
  }

  /* ------------------------------------------------------------------- QA */

  function ownsText(n) {
    for (var i = 0; i < n.childNodes.length; i++) {
      var c = n.childNodes[i];
      if (c.nodeType === 3 && c.nodeValue.trim()) return true;
    }
    return false;
  }

  function qa() {
    var slide = slideEl();
    var sb = slide.getBoundingClientRect();
    var issues = [];
    var map = regionMap();
    var add = function (sev, region, kind, detail) {
      issues.push({ sev: sev, region: region, kind: kind, detail: String(detail) });
    };

    // 슬라이드 자체가 내용을 잘라내고 있는가
    if (slide.scrollHeight > slide.clientHeight + 2 || slide.scrollWidth > slide.clientWidth + 2) {
      add('error', '(slide)', '내용이 슬라이드보다 큼 — 잘려나감',
        slide.clientWidth + '×' + slide.clientHeight + ' → ' + slide.scrollWidth + '×' + slide.scrollHeight);
    }

    map.regions.forEach(function (r) {
      var el = slide.querySelector('[data-region="' + r.id + '"]');
      var rb = el.getBoundingClientRect();

      if (r.px.x < -1 || r.px.y < -1 || r.px.x + r.px.w > sb.width + 1 || r.px.y + r.px.h > sb.height + 1) {
        add('error', r.id, '슬라이드 밖으로 벗어남', JSON.stringify(r.px));
      }
      if (!(r.box.w >= 0.95 || r.box.h >= 0.95)) {
        var edge = Math.min(r.px.x, r.px.y, sb.width - (r.px.x + r.px.w), sb.height - (r.px.y + r.px.h));
        if (edge < 24) add('warn', r.id, '가장자리 여백 부족', Math.round(edge) + 'px');
      }

      var scan = [el].concat(Array.prototype.slice.call(el.querySelectorAll('*')));
      scan.forEach(function (n) {
        var cs = getComputedStyle(n);
        // 실제로 잘리는 경우에만 넘침으로 본다 (overflow:visible 은 아래 영역-이탈 검사로 잡는다)
        if (cs.overflow !== 'visible' && n.clientHeight > 0) {
          if (n.scrollHeight > n.clientHeight + 2) {
            add('error', r.id, '내용 세로 잘림', n.tagName.toLowerCase() + ' ' + n.clientHeight + '→' + n.scrollHeight);
          }
          if (n.scrollWidth > n.clientWidth + 2) {
            add('error', r.id, '내용 가로 잘림', n.tagName.toLowerCase() + ' ' + n.clientWidth + '→' + n.scrollWidth);
          }
        }
        if (!ownsText(n) || !n.innerText || !n.innerText.trim()) return;
        var nb = n.getBoundingClientRect();
        if (nb.width && (nb.left < rb.left - 2 || nb.right > rb.right + 2 || nb.top < rb.top - 2 || nb.bottom > rb.bottom + 2)) {
          add('error', r.id, '텍스트가 영역 밖으로 넘침', n.tagName.toLowerCase() + ' "' + txt(n).slice(0, 24) + '"');
        }
        var fs = parseFloat(cs.fontSize);
        if (fs && fs < 12) add('warn', r.id, '글자 너무 작음(' + fs + 'px)', txt(n).slice(0, 24));
      });
    });

    var boxes = map.regions.filter(function (r) {
      var el = slide.querySelector('[data-region="' + r.id + '"]');
      return !(r.box.w >= 0.9 && r.box.h >= 0.9) && !el.hasAttribute('data-overlap-ok');
    });
    for (var i = 0; i < boxes.length; i++) {
      for (var j = i + 1; j < boxes.length; j++) {
        var A = slide.querySelector('[data-region="' + boxes[i].id + '"]');
        var B = slide.querySelector('[data-region="' + boxes[j].id + '"]');
        if (A.contains(B) || B.contains(A)) continue;
        var a = boxes[i].px, b = boxes[j].px;
        var pair = boxes[i].id + ' ↔ ' + boxes[j].id;
        var ox = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x);
        var oy = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y);
        if (ox > 2 && oy > 2) {
          add('error', pair, '영역 겹침', Math.round(ox) + '×' + Math.round(oy) + 'px');
        } else if (oy > 2 && ox <= 0 && ox > -12) {
          add('warn', pair, '가로 간격 너무 좁음', Math.round(-ox) + 'px');
        } else if (ox > 2 && oy <= 0 && oy > -12) {
          add('warn', pair, '세로 간격 너무 좁음', Math.round(-oy) + 'px');
        }
      }
    }
    return { slide: map.slide, issues: issues };
  }

  /* --------------------------------------------------------------- 모드 제어 */

  var state = { mode: 'preview', level: 1, grid: false, focus: null };

  function apply() {
    if (state.mode === 'select') {
      render({ level: state.level, grid: state.grid, focus: state.focus });
    } else {
      clear();
    }
  }

  function fromQuery() {
    var q = new URLSearchParams(location.search);
    if (q.get('mode')) state.mode = q.get('mode');
    if (q.get('level')) state.level = parseInt(q.get('level'), 10) || 1;
    if (q.get('grid')) state.grid = q.get('grid') !== '0';
    if (q.get('focus')) { state.focus = q.get('focus'); state.mode = 'select'; }
    if (q.get('legend') === '0') state.legend = false;
    // ?scale=2 — 고해상도 캡처용 확대 (PDF/이미지 내보내기)
    var sc = parseFloat(q.get('scale'));
    if (sc && sc > 0) document.documentElement.style.zoom = sc;
  }

  window.slideRegions = regionMap;
  window.slideQA = qa;
  window.slideMode = function (m, o) {
    o = o || {};
    state.mode = m;
    if (o.level !== undefined) state.level = o.level;
    if (o.grid !== undefined) state.grid = o.grid;
    state.focus = o.focus || null;
    apply();
    return state;
  };

  document.addEventListener('keydown', function (e) {
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    var k = e.key.toLowerCase();
    if (k === 's') { state.mode = 'select'; apply(); }
    else if (k === 'p') { state.mode = 'preview'; state.focus = null; apply(); }
    else if (k === 'g') { state.grid = !state.grid; if (state.mode === 'select') apply(); }
    else if (k === '2') { state.level = state.level === 2 ? 1 : 2; if (state.mode === 'select') apply(); }
  });

  window.addEventListener('resize', function () { if (state.mode === 'select') apply(); });

  fromQuery();
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', apply);
  } else {
    apply();
  }
})();
