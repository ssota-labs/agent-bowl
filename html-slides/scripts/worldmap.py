#!/usr/bin/env python3
"""worldmap — 세계지도 SVG 생성기 (slidecraft 의 `worldmap` 서브커맨드가 쓴다).

원본: assets/worldmap.svg — amCharts SVG Map Generator 로 만든 나라별 경로 257개.
이 모듈은 그 경로들을 대륙 그룹으로 묶고, 프레임 밖 경로를 버리고, 슬라이드에 넣을
`<svg>` 조각을 만든다. 색·호버는 assets/worldmap.css 가 담당한다.

단독 실행도 된다:
  python3 worldmap.py --highlight KR,JP,US --focus as > snippet.html
"""

import argparse
import re
import sys
from html import escape
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
SOURCE = SKILL_DIR / "assets" / "worldmap.svg"

# 대륙 코드 → (한글, 영문)
CONTINENTS = {
    "na": ("북아메리카", "North America"),
    "sa": ("남아메리카", "South America"),
    "eu": ("유럽", "Europe"),
    "af": ("아프리카", "Africa"),
    "as": ("아시아", "Asia"),
    "oc": ("오세아니아", "Oceania"),
    "an": ("남극", "Antarctica"),
}
ORDER = ["na", "sa", "eu", "af", "as", "oc", "an"]

# 사람들이 부르는 이름 → 대륙 코드
ALIASES = {
    "북미": "na", "northamerica": "na", "north-america": "na", "namerica": "na",
    "남미": "sa", "southamerica": "sa", "south-america": "sa", "samerica": "sa",
    "유럽": "eu", "europe": "eu",
    "아프리카": "af", "africa": "af",
    "아시아": "as", "asia": "as",
    "오세아니아": "oc", "oceania": "oc", "대양주": "oc", "호주": "oc", "australia": "oc",
    "남극": "an", "antarctica": "an",
    "아태": "apac", "apac": "apac", "asiapacific": "apac",
    "전세계": "world", "세계": "world", "world": "world", "all": "world",
}

# 대륙에 안 들어가는 묶음 (highlight 전용)
GROUPS = {
    "apac": ["as", "oc"],
    "americas": ["na", "sa"],
    "emea": ["eu", "af"],
}

# ISO 3166-1 alpha-2 → 대륙. 원본 SVG 의 257개 id 를 전부 덮는다.
CC2CONT = {}


def _reg(codes, cont):
    for c in codes.split():
        CC2CONT[c] = cont


_reg("""US CA MX GT BZ HN SV NI CR PA CU JM HT DO PR TT BB LC VC GD AG KN DM
        VI VG AI BM KY TC BS GL PM MF BL BQ CW SX AW MS GP MQ""", "na")
_reg("BR AR CO VE PE CL EC BO PY UY GY SR GF FK", "sa")
_reg("""GB FR DE IT ES PT NL BE CH AT PL CZ SK HU RO BG GR SE NO FI DK IE LU
        LT LV EE SI HR RS BA ME MK AL BY UA MD XK MT IS LI MC SM VA AD GI IM
        JE GG FO AX SJ CY RU""", "eu")
_reg("""NG ET EG CD ZA TZ KE UG DZ SD MZ GH CI CM MG AO ML BF NE SN ZM SS SO
        TD TN ZW GN RW BI BJ TG SL ER MR CF NA BW MW GM GW GQ GA CG DJ LS MU
        SZ ST CV KM SC LY MA EH LR RE YT SH GO JU""", "af")
_reg("""CN IN JP KR ID PK BD VN PH TR IR IQ SA SY KZ UZ MY TH MM AF KP TW LK
        NP KH LA AE IL JO LB PS KW QA BH OM YE MN TJ KG TM AZ AM GE HK MO BT
        MV IO BN TL SG""", "as")
_reg("""AU NZ PG FJ SB VU WS TO KI FM PW MH NR TV CK NU TK WF PF NC GU MP AS
        NF PN CX CC UM-DQ UM-FQ UM-HQ UM-JQ UM-MQ UM-WQ""", "oc")
_reg("AQ BV GS HM TF", "an")

# --focus 로 확대할 때 쓰는 viewBox. 대륙 경로의 bbox 를 그대로 쓰면
# 러시아 극동(유럽) · 태평양 섬(오세아니아) 때문에 엉뚱하게 넓어져서 직접 잡았다.
FOCUS_BOX = {
    # 실측 대륙 bbox 를 기준으로 잡은 지리적 프레임.
    # 대륙 bbox 를 그대로 쓰면 안 된다 — 유럽은 러시아 극동(x≈1058)까지,
    # 오세아니아는 태평양 섬(x≈11)까지 뻗어 있어 프레임이 무의미해진다.
    "world":    (8.47, 60.48, 1164.56, 606.52),
    "na":       (85, 58, 495, 285),
    "sa":       (278, 300, 212, 280),
    "eu":       (533, 63, 220, 197),
    "af":       (498, 208, 288, 292),
    "as":       (652, 138, 405, 282),
    "oc":       (922, 368, 255, 180),
    "an":       (200, 533, 805, 140),
    "apac":     (648, 132, 532, 420),
    "americas": (78, 55, 505, 525),
    "emea":     (492, 58, 302, 445),
}

PATH_RE = re.compile(r'<path\s[^>]*?/>')
ATTR_RE = re.compile(r'(\w[\w-]*)="([^"]*)"')


# ------------------------------------------------------------------ 원본 파싱

def load_source(src: Path = SOURCE):
    """원본 SVG → [{cc, name, cont, d}, ...]"""
    if not src.exists():
        sys.exit(f"[worldmap] 지도 원본이 없다: {src}")
    raw = src.read_text()
    out = []
    for tag in PATH_RE.findall(raw):
        a = dict(ATTR_RE.findall(tag))
        cc = a.get("id", "")
        d = a.get("d", "")
        if not cc or not d:
            continue
        out.append({
            "cc": cc,
            "name": a.get("title", cc),
            "cont": CC2CONT.get(cc, ""),
            "d": d,
        })
    unknown = sorted({p["cc"] for p in out if not p["cont"]})
    if unknown:
        sys.exit(f"[worldmap] 대륙 미분류 코드: {', '.join(unknown)} — CC2CONT 에 추가할 것")
    return out


# ------------------------------------------------------------------ 경로 가공

def _subpaths(d):
    """'M x,y L x,y ... Z' (절대좌표 M/L/Z 만) → [([(x,y)...], closed)]"""
    out = []
    for chunk in d.split("M")[1:]:
        chunk = chunk.strip()
        closed = chunk.endswith("Z")
        pts = []
        for pair in chunk.rstrip("Z").split("L"):
            if "," in pair:
                x, y = pair.split(",")
                fx, fy = float(x), float(y)
                if fx != fx or fy != fy or fx in (float("inf"), float("-inf")) \
                        or fy in (float("inf"), float("-inf")):
                    sys.exit(f"[worldmap] 좌표가 숫자가 아니다: {pair!r}")
                pts.append((fx, fy))
        if pts:
            out.append((pts, closed))
    return out


def _rdp(pts, eps):
    """Douglas–Peucker. 재귀 대신 스택 (남극 경로가 깊다)."""
    n = len(pts)
    if n < 3:
        return pts
    keep = [False] * n
    keep[0] = keep[-1] = True
    stack = [(0, n - 1)]
    while stack:
        i0, i1 = stack.pop()
        if i1 <= i0 + 1:
            continue
        x1, y1 = pts[i0]
        x2, y2 = pts[i1]
        dx, dy = x2 - x1, y2 - y1
        norm = (dx * dx + dy * dy) ** .5
        imax, dmax = -1, eps
        for i in range(i0 + 1, i1):
            px, py = pts[i]
            if norm:
                dist = abs(dx * (y1 - py) - dy * (x1 - px)) / norm
            else:
                dist = ((px - x1) ** 2 + (py - y1) ** 2) ** .5
            if dist > dmax:
                imax, dmax = i, dist
        if imax > 0:
            keep[imax] = True
            stack.append((i0, imax))
            stack.append((imax, i1))
    return [p for p, k in zip(pts, keep) if k]


def compact(d, eps=0.3, nd=1):
    """좌표를 줄인다. 경로를 통째로 버리지는 않는다 (하이라이트 대상이 사라지면 안 된다)."""
    def fmt(v):
        s = f"{v:.{nd}f}".rstrip("0").rstrip(".")
        return s if s not in ("", "-0") else "0"

    out = []
    for pts, closed in _subpaths(d):
        q = _rdp(pts, eps) if eps > 0 else pts
        if closed and len(q) < 3:
            q = pts                       # 뭉개졌으면 원본 유지
        if len(q) < 2:
            continue
        out.append("M" + "L".join(f"{fmt(x)},{fmt(y)}" for x, y in q) + ("Z" if closed else ""))
    return "".join(out) or d


def path_bbox(d):
    """경로의 바운딩 박스. 프레임 밖 경로를 걸러내는 데 쓴다."""
    xs, ys = [], []
    for pts, _ in _subpaths(d):
        for x, y in pts:
            xs.append(x)
            ys.append(y)
    if not xs:
        return None
    return min(xs), min(ys), max(xs), max(ys)


# ------------------------------------------------------------------ 앵커(마커 위치)

def _ring_area(pts):
    n = len(pts)
    return sum(pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1]
               for i in range(n)) / 2


def _ring_centroid(pts):
    n = len(pts)
    a = _ring_area(pts)
    if not a:
        return sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n
    cx = cy = 0.0
    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        cross = x0 * y1 - x1 * y0
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross
    return cx / (6 * a), cy / (6 * a)


def _inside(pts, x, y):
    """레이 캐스팅 — 점이 폴리곤 안인가."""
    n, ins = len(pts), False
    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        if (y0 > y) != (y1 > y):
            xi = x0 + (y - y0) * (x1 - x0) / (y1 - y0)
            if x < xi:
                ins = not ins
    return ins


def _widest_span(pts, y):
    """주어진 y 에서 폴리곤 내부 구간 중 가장 넓은 구간의 중점."""
    n, xs = len(pts), []
    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        if (y0 > y) != (y1 > y):
            xs.append(x0 + (y - y0) * (x1 - x0) / (y1 - y0))
    xs.sort()
    best, bw = None, -1
    for i in range(0, len(xs) - 1, 2):
        w = xs[i + 1] - xs[i]
        if w > bw:
            bw, best = w, (xs[i] + xs[i + 1]) / 2
    return best


def anchor(cc, src=SOURCE):
    """나라 코드 → 마커를 꽂을 (x, y). viewBox 와 같은 좌표계다.

    - 섬이 여러 개면 **가장 넓은** 폴리곤을 쓴다 (일본에서 홋카이도에 찍히는 걸 막는다).
    - 폴리곤 중심이 나라 밖이면(칠레·노르웨이처럼 굽은 나라) 같은 위도에서
      내부 구간이 가장 넓은 지점으로 옮긴다.
    """
    hit = [p for p in load_source(src) if p["cc"] == cc.upper()]
    if not hit:
        sys.exit(f"[worldmap] 모르는 나라 코드: {cc!r}")
    rings = [pts for pts, closed in _subpaths(hit[0]["d"]) if len(pts) >= 3]
    if not rings:
        sys.exit(f"[worldmap] {cc}: 쓸 수 있는 폴리곤이 없다")
    pts = max(rings, key=lambda r: abs(_ring_area(r)))

    x, y = _ring_centroid(pts)
    if not _inside(pts, x, y):
        for yy in (y, sum(p[1] for p in pts) / len(pts)):
            nx = _widest_span(pts, yy)
            if nx is not None and _inside(pts, nx, yy):
                x, y = nx, yy
                break
    return round(x, 1), round(y, 1)


# ------------------------------------------------------------------ 선택 해석

def resolve(token: str):
    """'KR' / 'as' / '아시아' / 'apac' → ('cc', 'KR') | ('cont', ['as']) """
    t = token.strip()
    if not t:
        return None
    key = t.lower().replace(" ", "")
    if key in ALIASES:
        key = ALIASES[key]
    if key == "world":
        return ("cont", list(ORDER))
    if key in GROUPS:
        return ("cont", GROUPS[key])
    if key in CONTINENTS:
        return ("cont", [key])
    up = t.upper()
    if up in CC2CONT:
        return ("cc", up)
    return None


def parse_list(spec: str):
    """'KR,JP,as' → (set(국가코드), set(대륙코드))"""
    ccs, conts = set(), set()
    for tok in (spec or "").replace(";", ",").split(","):
        if not tok.strip():
            continue
        r = resolve(tok)
        if not r:
            sys.exit(f"[worldmap] 모르는 지역: {tok!r} — 대륙(as/eu/…) 또는 ISO 2자리(KR/US/…)")
        if r[0] == "cc":
            ccs.add(r[1])
        else:
            conts.update(r[1])
    return ccs, conts


# ------------------------------------------------------------------ SVG 생성

def build_svg(highlight="", hover="continent", focus="world", eps=0.0, nd=1,
              assign=None, src=SOURCE, indent="      ", marker="", marker_size=1.0):
    paths = load_source(src)
    if assign:
        for cc, cont in assign.items():
            for p in paths:
                if p["cc"] == cc:
                    p["cont"] = cont

    hi_ccs, hi_conts = parse_list(highlight)
    box = FOCUS_BOX.get(focus)
    if not box:
        sys.exit(f"[worldmap] --focus 값이 이상하다: {focus!r} — {', '.join(FOCUS_BOX)}")
    vb = " ".join(str(round(v, 2)) for v in box)

    # 프레임 밖 경로는 버린다. 보이는 결과는 그대로고 파일만 작아진다
    # (--focus oc 슬라이드가 지구 반대편 경로까지 들고 있을 이유가 없다).
    fx0, fy0 = box[0], box[1]
    fx1, fy1 = box[0] + box[2], box[1] + box[3]
    kept, dropped = [], 0
    for p in paths:
        bb = path_bbox(p["d"])
        if bb and (bb[2] < fx0 or bb[0] > fx1 or bb[3] < fy0 or bb[1] > fy1):
            dropped += 1
            continue
        kept.append(p)

    groups = {c: [] for c in ORDER}
    for p in kept:
        groups[p["cont"]].append(p)

    used = [c for c in ORDER if groups[c]]
    # width/height 를 viewBox 비율 그대로 박아 둔다. 이게 없으면 .wm-svg 가 컨테이너를
    # 꽉 채우고, preserveAspectRatio="meet" 이 남는 폭만큼 프레임 밖을 더 보여준다
    # (--focus eu 인데 시베리아가 화면을 덮던 문제가 여기서 났다).
    # 값은 넉넉히 키워 둔다 — CSS 가 max-width/max-height 로 줄이기만 하므로,
    # 고유 크기가 작으면 슬라이드 한복판에 우표만 하게 박힌다.
    k = 2000.0 / max(box[2], box[3])
    lines = [f'<svg class="wm-svg" viewBox="{vb}" '
             f'width="{box[2] * k:.0f}" height="{box[3] * k:.0f}" '
             f'role="img" aria-label="세계 지도" xmlns="http://www.w3.org/2000/svg">']
    for c in used:
        ko, _ = CONTINENTS[c]
        on = " is-on" if c in hi_conts else ""
        lines.append(f'  <g class="wm-c wm-c-{c}{on}" data-continent="{c}" data-label="{escape(ko, quote=True)}">')
        for p in sorted(groups[c], key=lambda p: p["cc"]):
            cls = "wm-land is-on" if (p["cc"] in hi_ccs) else "wm-land"
            # 원본 SVG 는 사용자가 갈아끼울 수 있다. id/title 을 그대로 흘려보내면
            # 슬라이드 HTML 로 마크업이 새어 들어간다 — 전부 이스케이프한다.
            d = escape(compact(p["d"], eps, nd), quote=True)
            cc = escape(p["cc"], quote=True)
            name = escape(p["name"], quote=True)
            lines.append(f'    <path class="{cls}" d="{d}" data-cc="{cc}" data-name="{name}"/>')
        lines.append("  </g>")

    # 마커. 반지름을 프레임 폭에 비례시켜야 화면상 크기가 일정하다 —
    # viewBox 단위 고정값을 쓰면 확대할수록 커져서 작은 나라를 통째로 덮는다.
    pin_ccs = []
    for tok in (marker or "").replace(";", ",").split(","):
        if tok.strip():
            r = resolve(tok)
            if not r or r[0] != "cc":
                sys.exit(f"[worldmap] --marker 는 나라 코드만 받는다: {tok!r}")
            pin_ccs.append(r[1])
    if pin_ccs:
        k = box[2] / 1164.56 * marker_size
        rd, rh = round(3.0 * k, 2), round(6.4 * k, 2)
        lines.append('  <g class="wm-pins">')
        for cc in pin_ccs:
            x, y = anchor(cc, src)
            e = escape(cc, quote=True)
            lines.append(f'    <g class="wm-pin" data-cc="{e}" transform="translate({x} {y})">')
            lines.append(f'      <circle class="wm-pin-halo" r="{rh}"/>')
            lines.append(f'      <circle class="wm-pin-dot" r="{rd}"/>')
            lines.append("    </g>")
        lines.append("  </g>")

    lines.append("</svg>")
    svg = ("\n" + indent).join(lines)

    meta = {
        "counts": {c: len(groups[c]) for c in used},
        "highlight_cc": sorted(hi_ccs),
        "highlight_cont": sorted(hi_conts),
        "hover": hover,
        "focus": focus,
        "dropped": dropped,
        "markers": pin_ccs,
        "bytes": len(svg),
    }
    return svg, meta


def legend_html(items, indent="      "):
    """items — [(대륙코드 또는 '', 라벨)]. 대륙코드가 있어야 색점이 대륙색을 따라간다."""
    rows = []
    for key, label in items:
        attr = f' data-continent="{escape(key, quote=True)}"' if key else ""
        rows.append(f'<li class="wm-leg-item"{attr}>'
                    f'<i class="wm-leg-dot"></i>{escape(label)}</li>')
    return ("\n" + indent + "  ").join(
        ['<ul class="wm-legend">'] + rows + ["</ul>"])


def legend_items(palette, meta, label="진출 국가"):
    """범례 항목을 정한다.

    대륙 팔레트면 대륙별 색이 다르니 대륙을 나열한다.
    강조색 하나(accent)면 점이 전부 같은 색이라 대륙을 나열해봐야 뜻이 없다 —
    "이 색이 무슨 뜻인지" 한 줄만 보여준다.
    """
    if palette == "continent":
        return [(c, CONTINENTS[c][0]) for c in ORDER
                if c in meta["counts"] and c != "an"]
    return [("", label)]


def wrap(svg, hover="continent", palette="accent", legend=None,
         region="world-map", label="세계 지도", indent="    "):
    """슬라이드에 그대로 붙일 수 있는 .wm 블록."""
    inner = [f'<div class="wm" data-hover="{escape(hover, quote=True)}"'
             f' data-palette="{escape(palette, quote=True)}"'
             f' data-region="{escape(region, quote=True)}"'
             f' data-label="{escape(label, quote=True)}">',
             f'  {svg}']
    if legend:
        inner.append(f'  {legend_html(legend, indent + "  ")}')
    inner.append("</div>")
    return ("\n" + indent).join(inner)


# -------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(prog="worldmap",
                                 description="세계지도 SVG 조각을 만든다 (stdout)")
    ap.add_argument("--highlight", default="", help="KR,JP,US 또는 as,eu (섞어도 됨)")
    ap.add_argument("--hover", choices=["continent", "country", "off"], default="continent")
    ap.add_argument("--palette", choices=["accent", "continent"], default="accent")
    ap.add_argument("--focus", default="world", help=", ".join(FOCUS_BOX))
    ap.add_argument("--legend", action="store_true")
    ap.add_argument("--legend-label", default="진출 국가",
                    help="--palette accent 일 때 범례에 쓸 한 줄 설명")
    ap.add_argument("--simplify", type=float, default=0.0,
                    help="좌표 단순화. 확대 뷰에서 해안선이 뭉개지므로 기본 0")
    ap.add_argument("--precision", type=int, default=1)
    ap.add_argument("--assign", default="", help="RU=as 처럼 대륙 재배정 (쉼표 구분)")
    ap.add_argument("--marker", default="", help="KR,JP,SG — 그 나라 안에 핀을 찍는다")
    ap.add_argument("--marker-size", type=float, default=1.0, help="핀 크기 배수 (기본 1.0)")
    ap.add_argument("--anchor", default="",
                    help="핀 좌표만 출력하고 끝낸다 (KR,JP,SG). 카드를 손으로 붙일 때 쓴다")
    a = ap.parse_args()

    assign = {}
    for kv in a.assign.split(","):
        if "=" in kv:
            k, v = kv.split("=", 1)
            assign[k.strip().upper()] = v.strip().lower()

    if a.anchor:
        for tok in a.anchor.replace(";", ",").split(","):
            if not tok.strip():
                continue
            cc = tok.strip().upper()
            x, y = anchor(cc)
            print(f"{cc}\t{x}\t{y}")
        return

    svg, meta = build_svg(a.highlight, a.hover, a.focus, a.simplify, a.precision,
                          assign, marker=a.marker, marker_size=a.marker_size)
    legend = legend_items(a.palette, meta, a.legend_label) if a.legend else None
    print(wrap(svg, a.hover, a.palette, legend))
    print(f"<!-- {meta['bytes'] / 1024:.0f}KB · {sum(meta['counts'].values())} paths -->",
          file=sys.stderr)


if __name__ == "__main__":
    main()
