#!/usr/bin/env python3
"""slidecraft — HTML 슬라이드 스캐폴드 / 영역 주소록 / 스크린샷 / QA / 빌드.

브라우저 작업은 전역 설치된 `agent-browser` CLI 를 쓴다 (별도 의존성 없음).

사용법:
  slidecraft.py new  <deck-dir> [--title T] [--size 1280x720]
  slidecraft.py add  <deck-dir> <slug> [--title T]
  slidecraft.py map  <slide.html|deck-dir> [--json] [--out FILE]
  slidecraft.py shot <slide.html|deck-dir> [--mode preview|select|both] [--focus ID] [--outdir D]
  slidecraft.py qa   <slide.html|deck-dir> [--json]
  slidecraft.py build <deck-dir>
  slidecraft.py pdf   <deck-dir>
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
ASSETS = SKILL_DIR / "assets"
SESSION = os.environ.get("AGENT_BROWSER_SESSION", "slidecraft")
ANSI = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


# ------------------------------------------------------------------ 브라우저

def ab(args, retry=True):
    env = dict(os.environ, AGENT_BROWSER_SESSION=SESSION)
    p = subprocess.run(["agent-browser"] + args, capture_output=True, text=True, env=env)
    blob = (p.stdout or "") + (p.stderr or "")
    if p.returncode != 0 and retry and ("has been closed" in blob or "Target page" in blob):
        subprocess.run(["agent-browser", "close"], capture_output=True, text=True, env=env)
        return ab(args, retry=False)
    if p.returncode != 0:
        sys.exit(f"[slidecraft] agent-browser {' '.join(args[:2])} 실패:\n{blob.strip()}")
    return ANSI.sub("", p.stdout)


def open_slide(path: Path, query="", size=(1280, 720)):
    ab(["set", "viewport", str(size[0]), str(size[1])])
    ab(["open", path.resolve().as_uri() + query])


def evaluate(expr):
    out = ab(["eval", expr, "--max-output", "8000000"])
    line = ""
    for ln in reversed(out.strip().splitlines()):
        if ln.strip():
            line = ln.strip()
            break
    val = json.loads(line)
    if isinstance(val, str):
        val = json.loads(val)
    return val


# -------------------------------------------------------------------- 경로

def deck_root(p: Path) -> Path:
    p = p.resolve()
    if p.is_file():
        p = p.parent
    while p != p.parent:
        if (p / "deck.json").exists():
            return p
        p = p.parent
    return Path.cwd()


def cfg(root: Path) -> dict:
    f = root / "deck.json"
    return json.loads(f.read_text()) if f.exists() else {"title": root.name, "size": [1280, 720]}


def slides_of(target: Path):
    t = target.resolve()
    if t.is_file():
        return [t]
    d = t / "slides" if (t / "slides").is_dir() else t
    return sorted(p for p in d.glob("*.html") if not p.name.startswith("_"))


# ------------------------------------------------------------------ 스캐폴드

TEMPLATE = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>{title}</title>
<link rel="stylesheet" href="../assets/deck.css">
<link rel="stylesheet" href="../assets/theme.css">
<link rel="stylesheet" href="../assets/regions.css">
</head>
<body>

<section class="slide" data-slide="{no}" data-title="{title}">

  <header class="s-head" data-region="header" data-label="상단 헤더">
    <div>
      <p class="t-eyebrow" data-part="eyebrow">SECTION</p>
      <h2 class="t-title" data-part="title" style="font-size:var(--fs-head)">{title}</h2>
    </div>
    <span class="s-num">{no}</span>
  </header>

  <div class="fill" data-region="body" data-label="본문 영역">
    <p class="t-body">여기에 내용을 채운다.</p>
  </div>

  <footer class="s-foot" data-region="footer" data-label="하단 푸터">
    <span>{deck}</span>
    <span data-part="source">출처: —</span>
  </footer>

</section>

<script src="../assets/regions.js"></script>
</body>
</html>
"""

THEME = """/* {deck} — 덱 전용 테마. deck.css 대신 이 파일만 고친다.
   색은 주제에 맞게 반드시 새로 고를 것 (references/design.md). */
:root {{
  --bg: #ffffff;
  --bg-alt: #f3f5f8;
  --ink: #14181d;
  --ink-2: #4a5560;
  --ink-3: #8b95a1;
  --line: #dfe3e8;

  --brand: #1e2761;
  --brand-2: #cadcfc;
  --accent: #f96167;
  --on-brand: #ffffff;
}}
"""


def cmd_new(a):
    root = Path(a.deck).resolve()
    (root / "slides").mkdir(parents=True, exist_ok=True)
    (root / "assets").mkdir(exist_ok=True)
    for f in ("deck.css", "regions.css", "regions.js", "worldmap.css"):
        shutil.copy2(ASSETS / f, root / "assets" / f)
    theme = root / "assets" / "theme.css"
    if not theme.exists():
        theme.write_text(THEME.format(deck=a.title))
    w, h = (int(x) for x in a.size.lower().split("x"))
    (root / "deck.json").write_text(json.dumps({"title": a.title, "size": [w, h]}, ensure_ascii=False, indent=2))
    if not any((root / "slides").glob("*.html")):
        (root / "slides" / "01-title.html").write_text(
            TEMPLATE.format(no="01", title=a.title, deck=a.title))
    print(f"[slidecraft] 덱 생성: {root}")
    print(f"  slides/  ← 슬라이드 1장 = 파일 1개")
    print(f"  assets/theme.css ← 팔레트/폰트는 여기서 수정")


def cmd_add(a):
    root = deck_root(Path(a.deck))
    c = cfg(root)
    existing = slides_of(root)
    no = f"{len(existing) + 1:02d}"
    f = root / "slides" / f"{no}-{a.slug}.html"
    f.write_text(TEMPLATE.format(no=no, title=a.title or a.slug, deck=c.get("title", root.name)))
    print(f"[slidecraft] 슬라이드 추가: {f}")


# ------------------------------------------------------------------ 주소록

def fmt_map(m, rel):
    s = m["slide"]
    out = [f'### {rel} — 슬라이드 {s["no"] or "?"} · {s["title"]}  ({s["w"]}×{s["h"]})', ""]
    out.append("| # | 선택모드색 | 실제색 | 이름 | id | 위치 | 좌표(%) | 역할 | 내용 |")
    out.append("|---|-----------|-------|------|----|------|---------|------|------|")
    for r in m["regions"]:
        b = r["box"]
        coord = "x {:.0f}–{:.0f} · y {:.0f}–{:.0f}".format(
            b["x"] * 100, (b["x"] + b["w"]) * 100, b["y"] * 100, (b["y"] + b["h"]) * 100)
        pos = r["zone"]
        if r.get("rowCount", 0) > 1:
            pos += f' · {r["row"]}행 좌→우 {r["col"]}/{r["rowCount"]}'
        text = (r["text"] or "").replace("|", "\\|")[:50] or "—"
        bg = r.get("bg") or (f'({r["bgInherited"]})' if r.get("bgInherited") else "투명")
        out.append("| {n} | {color} | {bg} | {label} | `{id}` | {pos} | {coord} | {role} | {text} |".format(
            n=r["n"], color=r["color"], bg=bg, label=r["label"] or "—", id=r["id"],
            pos=pos, coord=coord, role=r["role"], text=text))
    parts = [(r, p) for r in m["regions"] for p in r["parts"]]
    if parts:
        out += ["", "부품(2레벨):", ""]
        for r, p in parts:
            out.append(f'- `{p["id"]}` ({r["color"]} 영역 내부) {p["label"] or ""} — {p["text"][:40] or "—"}')
    for w in m.get("warnings", []):
        out += ["", f"⚠ {w}"]
    return "\n".join(out)


def cmd_map(a):
    target = Path(a.target)
    root = deck_root(target)
    c = cfg(root)
    files = slides_of(target)
    maps, chunks = [], []
    for f in files:
        open_slide(f, size=tuple(c["size"]))
        m = evaluate("JSON.stringify(slideRegions())")
        m["file"] = str(f.relative_to(root)) if root in f.parents else str(f)
        maps.append(m)
        chunks.append(fmt_map(m, m["file"]))
    body = json.dumps(maps, ensure_ascii=False, indent=2) if a.json else "\n\n".join(chunks)

    # 캐시는 덱 전체 기준으로 유지한다 (한 장만 map 해도 나머지가 지워지지 않게 병합)
    cache = root / ".slidecraft"
    cache.mkdir(exist_ok=True)
    store = {}
    old = cache / "regions.json"
    if old.exists():
        try:
            for m in json.loads(old.read_text()):
                store[m.get("file")] = m
        except (ValueError, AttributeError):
            store = {}
    for m in maps:
        store[m["file"]] = m
    merged = [store[k] for k in sorted(store)]
    old.write_text(json.dumps(merged, ensure_ascii=False, indent=2))
    (cache / "regions.md").write_text("\n\n".join(fmt_map(m, m["file"]) for m in merged))
    if a.out:
        Path(a.out).write_text(body)
        print(f"[slidecraft] 저장: {a.out}")
    else:
        print(body)


# ---------------------------------------------------------------- 스크린샷

def cmd_shot(a):
    target = Path(a.target)
    root = deck_root(target)
    c = cfg(root)
    outdir = Path(a.outdir) if a.outdir else root / ".slidecraft" / "shots"
    outdir.mkdir(parents=True, exist_ok=True)
    modes = ["select"] if a.focus else (["preview", "select"] if a.mode == "both" else [a.mode])
    made = []
    for f in slides_of(target):
        for mode in modes:
            q = ""
            name = f"{f.stem}-{mode}.png"
            if a.focus:
                q = f"?mode=select&focus={a.focus}"
                name = f"{f.stem}-focus-{a.focus}.png"
            elif mode == "select":
                q = "?mode=select" + ("&grid=1" if a.grid else "")
            open_slide(f, q, size=tuple(c["size"]))
            out = outdir / name
            args = ["screenshot", str(out)]
            if mode == "select" or a.focus:
                args.append("--full")
            ab(args)
            made.append(out)
    for m in made:
        print(m)


# ---------------------------------------------------------------------- QA

def cmd_qa(a):
    target = Path(a.target)
    root = deck_root(target)
    c = cfg(root)
    results = []
    for f in slides_of(target):
        open_slide(f, size=tuple(c["size"]))
        r = evaluate("JSON.stringify(slideQA())")
        r["file"] = f.name
        results.append(r)
    if a.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return
    bad = 0
    for r in results:
        issues = r["issues"]
        bad += sum(1 for i in issues if i["sev"] == "error")
        head = f'{r["file"]} — {len(issues)}건'
        print(head)
        for i in issues:
            mark = "✗" if i["sev"] == "error" else "!"
            print(f'  {mark} [{i["region"]}] {i["kind"]} — {i["detail"]}')
        if not issues:
            print("  ✓ 이상 없음")
    print(f"\n오류 {bad}건")
    if bad:
        sys.exit(1)


# -------------------------------------------------------------------- 빌드

SECTION_RE = re.compile(r"<section\b[^>]*class=\"[^\"]*\bslide\b[^\"]*\"[\s\S]*?</section>", re.I)

DECK_SHELL = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
{css}
/* 슬라이드는 항상 같은 자리에 고정한다. 세로 가운데 정렬을 쓰면 선택 모드에서
   주소록이 붙는 순간 슬라이드가 위로 튄다. scrollbar-gutter 는 스크롤바가
   생겼다 사라질 때 가로로 밀리는 것까지 막는다. */
html{{background:#1a1c1f;height:auto;scrollbar-gutter:stable}}
body{{background:#1a1c1f;height:auto;justify-content:flex-start;padding:20px 0 64px}}
#stage{{position:relative}}
.slide{{display:none;box-shadow:0 18px 60px rgba(0,0,0,.45)}}
.slide.is-active{{display:flex}}
#pager{{position:fixed;right:18px;bottom:14px;color:#8b95a1;font:600 13px/1 system-ui,sans-serif;z-index:99999}}
#bar{{position:fixed;left:14px;bottom:12px;z-index:99999;display:flex;gap:6px;align-items:center;
  font:600 12px/1 -apple-system,"Apple SD Gothic Neo",system-ui,sans-serif}}
#bar button{{border:1px solid #3a3f47;background:#24272c;color:#c7ccd3;border-radius:7px;
  padding:7px 11px;cursor:pointer;font:inherit}}
#bar button:hover{{background:#31353b;color:#fff}}
#bar button[aria-pressed="true"]{{background:#e8eaed;border-color:#e8eaed;color:#16181b}}
#bar .sep{{width:1px;height:20px;background:#3a3f47;margin:0 4px}}
@media print{{
  html,body{{background:#fff;overflow:visible;height:auto;padding:0;scrollbar-gutter:auto}}
  #pager,#bar{{display:none}}
  .slide{{display:flex!important;box-shadow:none;page-break-after:always;break-after:page}}
  @page{{size:{w}px {h}px;margin:0}}
}}
</style>
</head>
<body>
<div id="stage">
{slides}
</div>
<div id="pager"></div>
<div id="bar">
  <button id="b-prev" title="이전 (←)">‹</button>
  <button id="b-next" title="다음 (→)">›</button>
  <span class="sep"></span>
  <button id="b-sel" aria-pressed="false" title="선택 모드 (S) — 영역에 번호·색·이름 배지와 주소록 표시">선택 모드</button>
  <button id="b-grid" aria-pressed="false" title="위치 격자 (G)">격자</button>
  <button id="b-part" aria-pressed="false" title="부품까지 표시 (2)">부품</button>
</div>
<script>
{js}
</script>
<script>
(function(){{
  var s=[].slice.call(document.querySelectorAll('.slide')),i=0;
  var st={{sel:location.search.indexOf('mode=select')>=0,grid:false,part:false}};
  var $=function(id){{return document.getElementById(id)}};

  function paint(){{
    $('b-sel').setAttribute('aria-pressed',st.sel);
    $('b-grid').setAttribute('aria-pressed',st.grid);
    $('b-part').setAttribute('aria-pressed',st.part);
    window.slideMode(st.sel?'select':'preview',{{grid:st.grid,level:st.part?2:1}});
  }}
  function go(n){{i=Math.max(0,Math.min(s.length-1,n));
    s.forEach(function(e,k){{e.classList.toggle('is-active',k===i)}});
    $('pager').textContent=(i+1)+' / '+s.length;
    paint();
  }}
  $('b-prev').onclick=function(){{go(i-1)}};
  $('b-next').onclick=function(){{go(i+1)}};
  $('b-sel').onclick=function(){{st.sel=!st.sel;paint()}};
  $('b-grid').onclick=function(){{st.grid=!st.grid;if(!st.sel)st.sel=true;paint()}};
  $('b-part').onclick=function(){{st.part=!st.part;if(!st.sel)st.sel=true;paint()}};

  document.addEventListener('keydown',function(e){{
    if(e.key==='ArrowRight'||e.key===' '||e.key==='PageDown')go(i+1);
    else if(e.key==='ArrowLeft'||e.key==='PageUp')go(i-1);
    else if(e.key==='Home')go(0);
    else if(e.key==='End')go(s.length-1);
    else if(e.key==='s'||e.key==='S'){{st.sel=true;paint()}}
    else if(e.key==='p'||e.key==='P'){{st.sel=false;paint()}}
    else if(e.key==='g'||e.key==='G'){{st.grid=!st.grid;paint()}}
    else if(e.key==='2'){{st.part=!st.part;paint()}}
  }},true);
  go(0);
}})();
</script>
</body>
</html>
"""


# 작성용 속성 — 공유본에서는 털어낸다
AUTHORING_ATTRS = re.compile(
    r'\s+data-(?:region|label|part|role|region-color)="[^"]*"|\s+data-overlap-ok(?=[\s/>])')


def sections_of(root: Path):
    """각 슬라이드 파일에서 <section class="slide"> 만 뽑아 온다."""
    out = []
    for f in slides_of(root):
        m = SECTION_RE.search(f.read_text())
        if not m:
            sys.exit(f"[slidecraft] {f.name}: <section class=\"slide\"> 를 찾지 못함")
        out.append(m.group(0))
    return out


def deck_css(root: Path, clean=False):
    sheets = ["deck.css", "theme.css", "worldmap.css"]
    if not clean:
        sheets.append("regions.css")
    return "\n".join((root / "assets" / n).read_text()
                     for n in sheets if (root / "assets" / n).exists())


def render_deck(root: Path, clean=False):
    """빌드 결과 HTML 문자열. cmd_build 와 preview 의 다운로드가 함께 쓴다."""
    c = cfg(root)
    sections = sections_of(root)
    if not sections:
        sys.exit("[slidecraft] 슬라이드가 없다")
    css = deck_css(root, clean)
    if clean:
        return CLEAN_SHELL.format(
            title=c.get("title", root.name), css=css,
            slides="\n".join(AUTHORING_ATTRS.sub("", s) for s in sections),
            w=c["size"][0], h=c["size"][1]), len(sections)
    js = (root / "assets" / "regions.js").read_text()
    return DECK_SHELL.format(
        title=c.get("title", root.name), css=css, js=js,
        slides="\n".join(sections), w=c["size"][0], h=c["size"][1]), len(sections)


def cmd_build(a):
    root = deck_root(Path(a.deck))
    html, n = render_deck(root, a.clean)
    dist = root / "dist"
    dist.mkdir(exist_ok=True)
    out = dist / ("deck-share.html" if a.clean else "deck.html")
    out.write_text(html)
    if a.clean:
        print(f"[slidecraft] 공유본 빌드: {out}  ({n}장, 선택 모드·툴바·작성용 속성 없음)")
    else:
        print(f"[slidecraft] 작업본 빌드: {out}  ({n}장, 선택 모드 포함)")


CLEAN_SHELL = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
{css}
html{{background:#1a1c1f;height:auto;scrollbar-gutter:stable}}
body{{background:#1a1c1f;height:auto;justify-content:center;min-height:100vh;padding:20px 0}}
.slide{{display:none;box-shadow:0 18px 60px rgba(0,0,0,.45)}}
.slide.is-active{{display:flex}}
#pager{{position:fixed;right:18px;bottom:14px;color:#8b95a1;
  font:600 13px/1 system-ui,sans-serif;z-index:99999}}
@media print{{
  html,body{{background:#fff;overflow:visible;height:auto;min-height:0;padding:0;scrollbar-gutter:auto}}
  #pager{{display:none}}
  .slide{{display:flex!important;box-shadow:none;page-break-after:always;break-after:page}}
  @page{{size:{w}px {h}px;margin:0}}
}}
</style>
</head>
<body>
{slides}
<div id="pager"></div>
<script>
(function(){{
  var s=[].slice.call(document.querySelectorAll('.slide')),i=0;
  function go(n){{i=Math.max(0,Math.min(s.length-1,n));
    s.forEach(function(e,k){{e.classList.toggle('is-active',k===i)}});
    document.getElementById('pager').textContent=(i+1)+' / '+s.length;
  }}
  document.addEventListener('keydown',function(e){{
    if(e.key==='ArrowRight'||e.key===' '||e.key==='PageDown')go(i+1);
    else if(e.key==='ArrowLeft'||e.key==='PageUp')go(i-1);
    else if(e.key==='Home')go(0);
    else if(e.key==='End')go(s.length-1);
  }});
  document.addEventListener('click',function(e){{go(e.clientX<innerWidth/4?i-1:i+1)}});
  go(0);
}})();
</script>
</body>
</html>
"""


# ------------------------------------------------------------------ 세계지도

MAP_SLIDE = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>{title}</title>
<link rel="stylesheet" href="../assets/deck.css">
<link rel="stylesheet" href="../assets/theme.css">
<link rel="stylesheet" href="../assets/worldmap.css">
<link rel="stylesheet" href="../assets/regions.css">
</head>
<body>

<section class="slide" data-slide="{no}" data-title="{title}">

  <header class="s-head" data-region="header" data-label="상단 헤더">
    <div>
      <p class="t-eyebrow" data-part="eyebrow">{eyebrow}</p>
      <h2 class="t-head" data-part="title">{title}</h2>
    </div>
    <span class="s-num">{no}</span>
  </header>

{block}

  <footer class="s-foot" data-region="footer" data-label="하단 푸터">
    <span>{deck}</span>
    <span data-part="source">출처: —</span>
  </footer>

</section>

<script src="../assets/regions.js"></script>
</body>
</html>
"""


def cmd_worldmap(a):
    sys.path.insert(0, str(SKILL_DIR / "scripts"))
    import worldmap as wm

    assign = {}
    for kv in (a.assign or "").split(","):
        if "=" in kv:
            k, v = kv.split("=", 1)
            assign[k.strip().upper()] = v.strip().lower()

    svg, meta = wm.build_svg(a.highlight, a.hover, a.focus, a.simplify, a.precision, assign,
                             marker=a.marker, marker_size=a.marker_size)
    legend = wm.legend_items(a.palette, meta, a.legend_label) if a.legend else None
    block = wm.wrap(svg, a.hover, a.palette, legend,
                    region=a.region, label=a.label, indent="  ")
    block = "  " + block
    if a.sea:
        block = block.replace('<div class="wm" ', '<div class="wm" data-sea="on" ', 1)

    if a.svg_only:
        out = Path(a.svg_only)
        out.write_text(block + "\n")
        print(f"[slidecraft] 지도 조각: {out}")
    else:
        root = deck_root(Path(a.target))
        if not (root / "deck.json").exists():
            sys.exit("[slidecraft] 덱을 찾지 못했다 — 먼저 `new` 로 만들거나 --svg-only 를 쓸 것")
        css = root / "assets" / "worldmap.css"
        if not css.exists():
            css.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ASSETS / "worldmap.css", css)
            print(f"[slidecraft] assets/worldmap.css 추가")
        c = cfg(root)
        no = f"{len(slides_of(root)) + 1:02d}"
        f = root / "slides" / f"{no}-{a.slug}.html"
        f.write_text(MAP_SLIDE.format(
            no=no, title=a.title, eyebrow=a.eyebrow, deck=c.get("title", root.name), block=block))
        print(f"[slidecraft] 지도 슬라이드 추가: {f}")

    if meta.get("markers"):
        print(f"  마커 {len(meta['markers'])}개: {', '.join(meta['markers'])}")
    hi = ", ".join(meta["highlight_cc"] + meta["highlight_cont"]) or "없음"
    print(f"  경로 {sum(meta['counts'].values())}개 · {meta['bytes'] / 1024:.0f}KB"
          f" · 초점 {meta['focus']} · 호버 {meta['hover']} · 하이라이트 {hi}")


# ------------------------------------------------------------------ 라이브 프리뷰

WATCH_GLOBS = ("slides/*.html", "assets/*.css", "assets/*.js", "deck.json")


def watch_token(root: Path) -> str:
    sig = []
    for g in WATCH_GLOBS:
        for p in sorted(root.glob(g)):
            try:
                st = p.stat()
            except OSError:
                continue
            sig.append(f"{p.name}:{int(st.st_mtime * 1000)}:{st.st_size}")
    import hashlib
    return hashlib.sha1("|".join(sig).encode()).hexdigest()[:16]


PREVIEW_SHELL = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} — 미리보기</title>
<style id="deck-css"></style>
<style>
  /* 툴바·페이저는 작업본 deck.html 과 같은 모양을 쓴다 (떠 있는 작은 버튼들) */
  html,body{{margin:0;height:100%;background:#1a1c1f;overflow:hidden}}
  #wrap{{position:fixed;inset:0 0 52px 0;overflow:hidden;transition:right .18s ease}}
  #scaler{{position:absolute;left:50%;top:50%;transform-origin:center center}}

  /* 선택 모드 주소록은 슬라이드 위에 겹치지 않게 오른쪽 패널로 뺀다 */
  #panel{{position:fixed;right:0;top:0;bottom:52px;width:420px;overflow:auto;z-index:99998;
    background:#202329;border-left:1px solid #2c3138;padding:14px;display:none}}
  body.panel-on #panel{{display:block}}
  body.panel-on #wrap{{right:420px}}
  #panel #rg-legend{{width:auto!important;max-width:none!important;margin:0!important;
    border:0!important;border-radius:0!important;background:transparent!important;
    padding:0!important;color:#c7ccd3!important;overflow:visible!important}}
  #panel #rg-legend h4{{color:#e8eaed!important}}
  #panel #rg-legend table{{font-size:12px!important}}
  #panel #rg-legend th{{color:#8b95a1!important;background:transparent!important;
    border-color:#2c3138!important;position:sticky;top:-14px}}
  #panel #rg-legend td{{color:#c7ccd3!important;border-color:#2c3138!important;
    white-space:normal!important}}
  #panel #rg-legend td.tx{{color:#9aa3ad!important}}
  #panel #rg-legend code{{color:#e8eaed!important}}
  #panel-empty{{color:#8b95a1;font:600 12px/1.6 -apple-system,"Apple SD Gothic Neo",system-ui,sans-serif}}
  #stage .slide{{display:none;box-shadow:0 18px 60px rgba(0,0,0,.45)}}
  #stage .slide.is-active{{display:flex}}

  #bar{{position:fixed;left:14px;bottom:12px;z-index:99999;display:flex;gap:6px;align-items:center;
    font:600 12px/1 -apple-system,"Apple SD Gothic Neo",system-ui,sans-serif}}
  #bar button{{border:1px solid #3a3f47;background:#24272c;color:#c7ccd3;border-radius:7px;
    padding:7px 11px;cursor:pointer;font:inherit}}
  #bar button:hover{{background:#31353b;color:#fff}}
  #bar button[aria-pressed="true"]{{background:#e8eaed;border-color:#e8eaed;color:#16181b}}
  #bar button.primary{{background:#e8eaed;border-color:#e8eaed;color:#16181b}}
  #bar button.primary:hover{{background:#fff;color:#16181b}}
  #bar .sep{{width:1px;height:20px;background:#3a3f47;margin:0 4px}}
  #pg{{color:#8b95a1;font-variant-numeric:tabular-nums;padding:0 2px}}

  #pager{{position:fixed;right:18px;bottom:14px;z-index:99999;display:flex;align-items:center;gap:7px;
    color:#8b95a1;font:600 12px/1 -apple-system,"Apple SD Gothic Neo",system-ui,sans-serif}}
  #dot{{width:7px;height:7px;border-radius:50%;background:#4ade80}}
  #dot.hit{{background:#fbbf24}}
  #err{{position:fixed;left:14px;right:14px;bottom:52px;background:#3b1416;color:#fca5a5;
    border:1px solid #7f1d1d;border-radius:7px;padding:9px 12px;display:none;z-index:99999;
    white-space:pre-wrap;font:600 12px/1.5 -apple-system,"Apple SD Gothic Neo",system-ui,sans-serif}}

  @media print{{
    html,body{{background:#fff;overflow:visible;height:auto}}
    #bar,#pager,#err{{display:none!important}}
    #wrap{{position:static;inset:auto;display:block;overflow:visible}}
    #scaler{{position:static;left:auto;top:auto;transform:none!important}}
    #stage .slide{{display:flex!important;box-shadow:none;page-break-after:always;break-after:page}}
    @page{{size:{w}px {h}px;margin:0}}
  }}
</style>
</head>
<body>

<div id="wrap"><div id="scaler"><div id="stage"></div></div></div>
<div id="panel"><div id="panel-empty">선택 모드를 켜면 영역 주소록이 여기 나옵니다.</div></div>
<div id="err"></div>

<div id="bar">
  <button id="b-prev" title="이전 (←)">‹</button>
  <span id="pg">– / –</span>
  <button id="b-next" title="다음 (→)">›</button>
  <span class="sep"></span>
  <button id="b-sel" aria-pressed="false" title="영역에 번호·색·이름 배지를 붙인다 (S)">선택 모드</button>
  <button id="b-grid" aria-pressed="false" title="위치 격자 (G)">격자</button>
  <span class="sep"></span>
  <button id="b-save" class="primary" title="완성본 HTML 파일을 내려받는다">HTML 저장</button>
  <button id="b-pdf" title="브라우저 인쇄창에서 'PDF로 저장'을 고른다">PDF 저장</button>
</div>
<div id="pager"><span id="dot"></span><span id="live-label">자동 새로고침 켜짐</span></div>

<script>
(function(){{
  var W={w}, H={h};
  var stage=document.getElementById('stage'), scaler=document.getElementById('scaler');
  var st={{i:0, sel:false, grid:false, token:null, loaded:false, fails:0}};
  var $=function(id){{return document.getElementById(id)}};

  function fit(){{
    var pw=document.body.classList.contains('panel-on')?420:0;
    var vw=innerWidth-pw-96, vh=innerHeight-52-72;
    var k=Math.min(vw/W, vh/H, 1);
    scaler.style.transform='translate(-50%,-50%) scale('+k+')';
    scaler.style.width=W+'px'; scaler.style.height=H+'px';
  }}
  addEventListener('resize', fit);

  function err(msg){{
    var e=$('err');
    if(!msg){{ e.style.display='none'; return; }}
    e.textContent=msg; e.style.display='block';
  }}

  function movePanel(){{
    var lg=document.getElementById('rg-legend');
    var panel=document.getElementById('panel');
    if(st.sel){{
      document.body.classList.add('panel-on');
      if(lg && lg.parentNode!==panel){{ panel.innerHTML=''; panel.appendChild(lg); }}
    }} else {{
      document.body.classList.remove('panel-on');
      if(lg) lg.remove();
      panel.innerHTML='<div id="panel-empty">선택 모드를 켜면 영역 주소록이 여기 나옵니다.</div>';
    }}
    fit();
  }}

  function paint(){{
    var s=stage.querySelectorAll('.slide');
    if(!s.length) return;
    st.i=Math.max(0, Math.min(s.length-1, st.i));
    for(var k=0;k<s.length;k++) s[k].classList.toggle('is-active', k===st.i);
    $('pg').textContent=(st.i+1)+' / '+s.length;
    $('b-sel').setAttribute('aria-pressed', st.sel);
    $('b-grid').setAttribute('aria-pressed', st.grid);
    if(window.slideMode) window.slideMode(st.sel?'select':'preview', {{grid:st.grid, level:1}});
    movePanel();
  }}
  function go(n){{ st.i=n; paint(); }}

  function loadRegions(){{
    if(window.slideMode) return Promise.resolve();
    return new Promise(function(res){{
      var sc=document.createElement('script');
      sc.src='/__regions.js'; sc.onload=res; sc.onerror=res;
      document.body.appendChild(sc);
    }});
  }}

  function apply(d){{
    document.getElementById('deck-css').textContent=d.css;
    stage.innerHTML=d.slides;
    document.title=d.title+' — 미리보기';
    st.token=d.token;
    st.loaded=true;
    fit();
    return loadRegions().then(paint);
  }}

  function pull(){{
    return fetch('/__deck', {{cache:'no-store'}}).then(function(r){{return r.json()}})
      .then(function(d){{
        if(d.error){{ err(d.error); return; }}
        err(''); return apply(d);
      }})
      .catch(function(e){{ err('미리보기 서버에 연결하지 못했습니다: '+e.message); }});
  }}

  function poll(){{
    fetch('/__token', {{cache:'no-store'}}).then(function(r){{return r.text()}})
      .then(function(t){{
        t=t.trim();
        live(true);
        if(t && (!st.loaded || t!==st.token)){{
          $('dot').classList.add('hit');
          pull().then(function(){{ setTimeout(function(){{$('dot').classList.remove('hit')}}, 400); }});
        }}
      }}).catch(function(){{ live(false); }});
  }}

  function live(ok){{
    st.fails = ok ? 0 : st.fails+1;
    var dot=$('dot'), lab=$('live-label');
    if(!ok && st.fails>=3){{
      dot.style.background='#ef4444';
      lab.textContent='연결 끊김 — 미리보기를 다시 켜 주세요';
    }} else if(ok){{
      dot.style.background='';
      lab.textContent='자동 새로고침 켜짐';
    }}
  }}

  $('b-prev').onclick=function(){{go(st.i-1)}};
  $('b-next').onclick=function(){{go(st.i+1)}};
  $('b-sel').onclick=function(){{st.sel=!st.sel;paint()}};
  $('b-grid').onclick=function(){{st.grid=!st.grid; if(st.grid) st.sel=true; paint()}};
  $('b-save').onclick=function(){{ location.href='/__download'; }};
  $('b-pdf').onclick=function(){{ print(); }};

  document.addEventListener('keydown', function(e){{
    if(e.metaKey||e.ctrlKey) return;
    if(e.key==='ArrowRight'||e.key===' '||e.key==='PageDown') go(st.i+1);
    else if(e.key==='ArrowLeft'||e.key==='PageUp') go(st.i-1);
    else if(e.key==='Home') go(0);
    else if(e.key==='End') go(stage.querySelectorAll('.slide').length-1);
    else if(e.key==='s'||e.key==='S'){{st.sel=!st.sel;paint()}}
    else if(e.key==='g'||e.key==='G'){{st.grid=!st.grid; if(st.grid) st.sel=true; paint()}}
  }}, true);

  fit();
  pull();
  setInterval(poll, 600);
}})();
</script>
</body>
</html>
"""


def cmd_preview(a):
    import http.server
    import json as _json
    import socketserver
    import threading
    import webbrowser

    root = deck_root(Path(a.deck))
    if not (root / "deck.json").exists():
        sys.exit(f"[slidecraft] 덱을 찾지 못했다: {a.deck} — 먼저 `new` 로 만들 것")
    c = cfg(root)
    w, h = c["size"]

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kw):
            super().__init__(*args, directory=str(root), **kw)

        def log_message(self, *args):
            pass

        def _send(self, body, ctype="text/html; charset=utf-8", extra=None):
            if isinstance(body, str):
                body = body.encode()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = self.path.split("?")[0]
            try:
                if path == "/":
                    return self._send(PREVIEW_SHELL.format(
                        title=c.get("title", root.name), w=w, h=h))

                if path == "/__token":
                    return self._send(watch_token(root), "text/plain; charset=utf-8")

                if path == "/__regions.js":
                    f = root / "assets" / "regions.js"
                    return self._send(f.read_text() if f.exists() else "",
                                      "application/javascript; charset=utf-8")

                if path == "/__deck":
                    try:
                        secs = sections_of(root)
                        if not secs:
                            raise RuntimeError(
                                "슬라이드가 한 장도 없습니다. slides/ 폴더에 .html 파일을 만들어 주세요.")
                        payload = {
                            "title": c.get("title", root.name),
                            "css": deck_css(root),
                            "slides": "\n".join(secs),
                            "token": watch_token(root),
                        }
                    except (SystemExit, RuntimeError) as e:
                        payload = {"error": str(e)}
                    return self._send(_json.dumps(payload), "application/json; charset=utf-8")

                if path == "/__download":
                    html, _ = render_deck(root, clean=True)
                    # HTTP 헤더는 latin-1 이라 한글 제목을 그대로 넣으면 응답이 깨진다.
                    # ASCII 대체 이름 + RFC 5987 로 한글 이름을 함께 보낸다.
                    title = c.get("title", root.name)
                    utf8 = urllib.parse.quote(
                        re.sub(r'[\\/:*?"<>|]+', "_", title).strip() or "deck")
                    ascii_name = re.sub(r'[^A-Za-z0-9._-]+', "_", title).strip("_") or "deck"
                    return self._send(html, "text/html; charset=utf-8",
                                      {"Content-Disposition":
                                       f'attachment; filename="{ascii_name}.html"; '
                                       f"filename*=UTF-8''{utf8}.html"})
            except (Exception, SystemExit) as e:  # 서버가 죽으면 비개발자는 손을 못 쓴다
                return self._send(f"<pre>{e}</pre>", "text/html; charset=utf-8")

            return super().do_GET()

    class Server(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
        daemon_threads = True

    port, srv = a.port, None
    for cand in range(a.port, a.port + 40):
        try:
            srv = Server(("127.0.0.1", cand), Handler)
            port = cand
            break
        except OSError:
            continue
    if srv is None:
        sys.exit(f"[slidecraft] {a.port}~{a.port + 39} 사이에 빈 포트가 없다")

    url = f"http://127.0.0.1:{port}/"
    n = len(slides_of(root))
    print(f"[slidecraft] 미리보기: {url}   ({c.get('title', root.name)} · {n}장)", flush=True)
    print("  파일을 고치면 브라우저가 알아서 새로고침한다. 'HTML 저장' 버튼으로 완성본을 내려받는다.",
          flush=True)
    print("  멈추려면 Ctrl+C.", flush=True)

    if not a.no_open:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n[slidecraft] 미리보기 종료")
    finally:
        srv.server_close()


def cmd_pdf(a):
    """슬라이드를 2배 해상도 PNG 로 찍어 정확한 16:9 페이지의 PDF 로 묶는다.
    (브라우저 인쇄 PDF 는 용지 크기가 Letter 로 고정돼 슬라이드 비율이 깨진다)"""
    root = deck_root(Path(a.deck))
    c = cfg(root)
    w, h = c["size"]
    scale = a.scale
    tmp = root / ".slidecraft" / "pdfpages"
    tmp.mkdir(parents=True, exist_ok=True)
    pages = []
    for f in slides_of(root):
        open_slide(f, f"?scale={scale}", size=(w * scale, h * scale))
        p = tmp / f"{f.stem}.png"
        ab(["screenshot", str(p)])
        pages.append(p)
    if not pages:
        sys.exit("[slidecraft] 슬라이드가 없다")
    pdf = root / "dist" / "deck.pdf"
    pdf.parent.mkdir(exist_ok=True)
    try:
        from PIL import Image
    except ImportError:
        sys.exit("[slidecraft] Pillow 가 필요하다:  pip install Pillow")
    imgs = [Image.open(p).convert("RGB") for p in pages]
    imgs[0].save(pdf, "PDF", resolution=96.0 * scale, save_all=True, append_images=imgs[1:])
    print(f"[slidecraft] PDF: {pdf}  ({len(imgs)}장, {w}×{h} @{scale}x)")


# -------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(prog="slidecraft")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("new"); p.add_argument("deck"); p.add_argument("--title", default="새 덱")
    p.add_argument("--size", default="1280x720"); p.set_defaults(fn=cmd_new)

    p = sub.add_parser("add"); p.add_argument("deck"); p.add_argument("slug")
    p.add_argument("--title"); p.set_defaults(fn=cmd_add)

    p = sub.add_parser("map"); p.add_argument("target"); p.add_argument("--json", action="store_true")
    p.add_argument("--out"); p.set_defaults(fn=cmd_map)

    p = sub.add_parser("shot"); p.add_argument("target")
    p.add_argument("--mode", choices=["preview", "select", "both"], default="both")
    p.add_argument("--focus"); p.add_argument("--grid", action="store_true")
    p.add_argument("--outdir"); p.set_defaults(fn=cmd_shot)

    p = sub.add_parser("qa"); p.add_argument("target"); p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_qa)

    p = sub.add_parser("preview", help="라이브 미리보기 서버 (브라우저 자동 실행 · 자동 새로고침)")
    p.add_argument("deck"); p.add_argument("--port", type=int, default=7373)
    p.add_argument("--no-open", action="store_true", help="브라우저를 열지 않는다")
    p.set_defaults(fn=cmd_preview)

    p = sub.add_parser("worldmap", help="세계지도 슬라이드/조각 생성")
    p.add_argument("target", nargs="?", default=".", help="덱 경로 (--svg-only 면 무시)")
    p.add_argument("--slug", default="world"); p.add_argument("--title", default="글로벌 현황")
    p.add_argument("--eyebrow", default="GLOBAL")
    p.add_argument("--highlight", default="", help="KR,JP,US 또는 as,eu — 섞어도 된다")
    p.add_argument("--hover", choices=["continent", "country", "off"], default="continent")
    p.add_argument("--palette", choices=["accent", "continent"], default="accent")
    p.add_argument("--focus", default="world", help="world|na|sa|eu|af|as|oc|an|apac|americas|emea")
    p.add_argument("--legend", action="store_true", help="범례를 붙인다")
    p.add_argument("--legend-label", default="진출 국가",
                   help="--palette accent 일 때 범례 문구 (기본: 진출 국가)")
    p.add_argument("--sea", action="store_true", help="바다를 브랜드색으로 칠한다")
    p.add_argument("--region", default="world-map"); p.add_argument("--label", default="세계 지도")
    p.add_argument("--assign", default="", help="RU=as 처럼 대륙 재배정")
    p.add_argument("--marker", default="", help="KR,JP,SG — 그 나라 안에 핀을 찍는다")
    p.add_argument("--marker-size", type=float, default=1.0, help="핀 크기 배수 (기본 1.0)")
    p.add_argument("--simplify", type=float, default=0.0,
                   help="추가 단순화 (원본이 이미 최적화돼 있어 보통 0)")
    p.add_argument("--precision", type=int, default=1)
    p.add_argument("--svg-only", help="슬라이드 대신 지도 블록만 이 파일에 쓴다")
    p.set_defaults(fn=cmd_worldmap)

    p = sub.add_parser("build"); p.add_argument("deck")
    p.add_argument("--clean", action="store_true",
                   help="공유용: 선택 모드 런타임·툴바·작성용 data-* 속성 제거 → dist/deck-share.html")
    p.set_defaults(fn=cmd_build)
    p = sub.add_parser("pdf"); p.add_argument("deck")
    p.add_argument("--scale", type=int, default=2); p.set_defaults(fn=cmd_pdf)

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
