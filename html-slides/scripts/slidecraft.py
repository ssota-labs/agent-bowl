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
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
ASSETS = SKILL_DIR / "assets"
SESSION = "slidecraft"
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
    for f in ("deck.css", "regions.css", "regions.js"):
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


def cmd_build(a):
    root = deck_root(Path(a.deck))
    c = cfg(root)
    files = slides_of(root)
    if not files:
        sys.exit("[slidecraft] 슬라이드가 없다")
    sections = []
    for f in files:
        m = SECTION_RE.search(f.read_text())
        if not m:
            sys.exit(f"[slidecraft] {f.name}: <section class=\"slide\"> 를 찾지 못함")
        sections.append(m.group(0))

    dist = root / "dist"
    dist.mkdir(exist_ok=True)
    sheets = ("deck.css", "theme.css") if a.clean else ("deck.css", "theme.css", "regions.css")
    css = "\n".join((root / "assets" / n).read_text()
                    for n in sheets if (root / "assets" / n).exists())

    if a.clean:
        body = "\n".join(AUTHORING_ATTRS.sub("", s) for s in sections)
        out = dist / "deck-share.html"
        out.write_text(CLEAN_SHELL.format(
            title=c.get("title", root.name), css=css,
            slides=body, w=c["size"][0], h=c["size"][1]))
        print(f"[slidecraft] 공유본 빌드: {out}  ({len(sections)}장, 선택 모드·툴바·작성용 속성 없음)")
    else:
        js = (root / "assets" / "regions.js").read_text()
        out = dist / "deck.html"
        out.write_text(DECK_SHELL.format(
            title=c.get("title", root.name), css=css, js=js,
            slides="\n".join(sections), w=c["size"][0], h=c["size"][1]))
        print(f"[slidecraft] 작업본 빌드: {out}  ({len(sections)}장, 선택 모드 포함)")


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
