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
EDITOR = SKILL_DIR / "editor"
TEMPLATES = SKILL_DIR / "templates"
SESSION = os.environ.get("AGENT_BROWSER_SESSION", "slidecraft")
ANSI = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")

sys.path.insert(0, str(SKILL_DIR / "scripts"))
import html_patch  # noqa: E402


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
    # 브라우저 세션은 호출 사이에 유지된다. 앞서 지도 위에 머문 커서가 그대로
    # 남으면 엉뚱한 대륙이 호버색으로 찍히고, PDF 에 구워지면 되돌릴 수 없다.
    # CSS 로 pointer-events 를 꺼도 이미 걸린 :hover 는 안 풀린다 —
    # 브라우저는 마우스가 움직여야 호버를 다시 계산한다. 그래서 실제로 치운다.
    ab(["mouse", "move", "2", "2"])
    ab(["eval", "document.documentElement.classList.add('rg-capture')"])


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

DECKS_DIR = ".html-slides"      # 덱 작업 파일은 작업 폴더의 이 숨김 폴더 안에 둔다
SCAN_DEPTH = 5


def scan_roots():
    """덱을 찾아볼 뿌리들.

    보통은 스킬이 놓인 폴더의 부모가 사용자의 작업 폴더다. 다만 하위 프로젝트에서
    작업하는 중이면 위쪽 폴더의 덱도 보여야 하므로, .html-slides/ 를 가진 조상도
    같이 뿌리로 잡는다.
    """
    out = []

    def add(p):
        p = p.resolve()
        if p.is_dir() and p not in out:
            out.append(p)

    here = Path.cwd().resolve()
    add(here)
    for anc in here.parents:
        if (anc / DECKS_DIR).is_dir():
            add(anc)
    add(SKILL_DIR.parent)
    return out


def find_decks(roots=None):
    """deck.json 을 훑어 덱 목록을 만든다. 목록을 파일로 저장하지 않는다 —
    저장하면 사용자가 폴더를 지웠을 때 유령 항목이 남는다."""
    seen, out = set(), []
    skill = SKILL_DIR.resolve()
    for root in (roots or scan_roots()):
        if not root.is_dir():
            continue
        stack = [(root, 0)]
        while stack:
            d, depth = stack.pop()
            if (d / "deck.json").is_file():
                r = d.resolve()
                # 스킬이 들고 있는 예시 덱은 사용자 덱이 아니다
                if r == skill or skill in r.parents:
                    continue
                if r not in seen:
                    seen.add(r)
                    out.append(r)
                continue                      # 덱 안쪽은 더 들어가지 않는다
            if depth >= SCAN_DEPTH:
                continue
            try:
                kids = list(d.iterdir())
            except OSError:
                continue
            for k in kids:
                if k.is_dir() and k.name not in ("dist", ".slidecraft", "node_modules",
                                                 ".git", "__pycache__"):
                    stack.append((k, depth + 1))
    return out


def find_deck(arg: str) -> Path:
    """'<경로>' 든 '월간보고' 든 덱 폴더로 바꾼다.

    사용자는 경로를 모른다. 덱 이름만 말해도 찾아지게 한다.
    """
    p = Path(arg)
    if p.exists():
        return deck_root(p)
    if not p.is_absolute() and os.sep not in arg:
        here = Path.cwd() / DECKS_DIR / arg
        if (here / "deck.json").exists():
            return here.resolve()
        hits = [d for d in find_decks() if d.name == arg]
        if len(hits) == 1:
            return hits[0]
        if len(hits) > 1:
            sys.exit("[slidecraft] 같은 이름의 덱이 여러 개다:\n  " +
                     "\n  ".join(str(h) for h in hits))
    known = find_decks()
    msg = f"[slidecraft] 덱을 찾지 못했다: {arg}"
    if known:
        msg += "\n  있는 덱: " + ", ".join(sorted(d.name for d in known))
    sys.exit(msg)


def resolve_target(arg: str) -> Path:
    """map/shot/qa 처럼 슬라이드 파일도 덱도 받는 명령용."""
    p = Path(arg)
    return p if p.exists() else find_deck(arg)


def new_deck_path(arg: str) -> Path:
    """`new` 가 만들 위치. 이름만 주면 작업 폴더의 .html-slides/ 아래로 간다."""
    p = Path(arg)
    if p.is_absolute() or os.sep in arg:
        return p.resolve()
    return (Path.cwd() / DECKS_DIR / arg).resolve()


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
/* slidecraft:tokens:start */
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
/* slidecraft:tokens:end */
"""


def copy_skill_templates(root: Path):
    dest = root / "templates"
    dest.mkdir(parents=True, exist_ok=True)
    if not TEMPLATES.is_dir():
        return
    for src in sorted(TEMPLATES.glob("*.html")):
        target = dest / src.name
        if not target.exists():
            shutil.copy2(src, target)


def templates_of(root: Path):
    d = root / "templates"
    if not d.is_dir():
        return []
    return sorted(p for p in d.glob("*.html") if not p.name.startswith("_"))


def slide_title_of(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    m = re.search(r'data-title="([^"]*)"', text)
    if m:
        return m.group(1)
    m = re.search(r"<title>([^<]*)</title>", text, re.I)
    return (m.group(1).strip() if m else path.stem)


def cmd_new(a):
    root = new_deck_path(a.deck)
    (root / "slides").mkdir(parents=True, exist_ok=True)
    (root / "assets").mkdir(exist_ok=True)
    for f in ("deck.css", "regions.css", "regions.js", "worldmap.css", "icons.css"):
        shutil.copy2(ASSETS / f, root / "assets" / f)
    theme = root / "assets" / "theme.css"
    if not theme.exists():
        theme.write_text(THEME.format(deck=a.title))
    copy_skill_templates(root)
    w, h = (int(x) for x in a.size.lower().split("x"))
    (root / "deck.json").write_text(json.dumps({"title": a.title, "size": [w, h]}, ensure_ascii=False, indent=2))
    if not any((root / "slides").glob("*.html")):
        title_tpl = root / "templates" / "title.html"
        if title_tpl.exists():
            html = title_tpl.read_text(encoding="utf-8")
            html = re.sub(r'data-slide="[^"]*"', 'data-slide="01"', html, count=1)
            html = re.sub(r'data-title="[^"]*"', f'data-title="{a.title}"', html, count=1)
            html = re.sub(r"<title>[^<]*</title>", f"<title>{a.title}</title>", html, count=1, flags=re.I)
            (root / "slides" / "01-title.html").write_text(html)
        else:
            (root / "slides" / "01-title.html").write_text(
                TEMPLATE.format(no="01", title=a.title, deck=a.title))
    print(f"[slidecraft] 덱 생성: {root}")
    print(f"  덱 이름: {root.name}   ← 사용자에게 이 이름을 알려줄 것")
    print(f"  다음부터는 경로 대신 이름만 줘도 된다:  preview {root.name}")


def cmd_add(a):
    root = find_deck(a.deck)
    c = cfg(root)
    existing = slides_of(root)
    no = f"{len(existing) + 1:02d}"
    # 번호는 여기서 붙인다. 예시 파일명(02-kpi)을 그대로 슬러그로 넘기는 일이 잦아서,
    # 앞에 이미 번호가 있으면 떼어낸다 (안 그러면 02-02-kpi.html 이 된다).
    slug = re.sub(r'^\d{1,3}[-_]', "", a.slug)
    f = root / "slides" / f"{no}-{slug}.html"
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
    target = resolve_target(a.target)
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
    target = resolve_target(a.target)
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

ICON_TAG = re.compile(r'data-ic-set="([^"]+)"\s+data-ic="([^"]+)"')


def icon_consistency(files):
    """아이콘이 섞였는지 본다. 브라우저 QA 로는 못 잡는 종류의 문제다 —
    렌더는 멀쩡한데 세트가 섞이면 선 두께가 어긋나 조잡해 보인다."""
    use = {}
    for f in files:
        for st, name in ICON_TAG.findall(f.read_text()):
            use.setdefault(st, {}).setdefault(name, []).append(f.name)
    if not use:
        return []

    msgs = []
    if len(use) > 1:
        detail = " · ".join(f"{k}({sum(len(v) for v in n.values())}개)" for k, n in sorted(use.items()))
        msgs.append(("✗", f"아이콘 세트가 섞였다 — {detail}. 한 덱에는 한 세트만 쓴다"))

    # 같은 세트 안에서도 -line/-fill 처럼 결이 갈리는 접미사를 섞으면 티가 난다
    for st, names in sorted(use.items()):
        kinds = {}
        for n in names:
            for suf in ("-line", "-fill", "-bold", "-duotone"):
                if n.endswith(suf):
                    kinds.setdefault(suf, []).append(n)
                    break
            else:
                kinds.setdefault("(기본)", []).append(n)
        if len(kinds) > 1:
            detail = " · ".join(f"{k} {len(v)}개" for k, v in sorted(kinds.items()))
            msgs.append(("!", f"{st}: 아이콘 결이 섞였다 — {detail}. 접미사까지 통일한다"))
    return msgs


def cmd_qa(a):
    target = resolve_target(a.target)
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
    for sev, msg in icon_consistency(slides_of(target)):
        print(f"  {sev} [아이콘] {msg}")
        if sev == "✗":
            bad += 1

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
    r'\s+data-(?:region|label|part|role|region-color|ic-set|ic)="[^"]*"'
    r'|\s+data-overlap-ok(?=[\s/>])')


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
    sheets = ["deck.css", "theme.css", "worldmap.css", "icons.css"]
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
    root = find_deck(a.deck)
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
        root = find_deck(a.target)
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


def cmd_icons(a):
    """아이콘은 덱과 무관하므로 별도 스크립트에 그대로 넘긴다."""
    r = subprocess.run([sys.executable, str(SKILL_DIR / "scripts" / "icons.py")] + a.rest)
    sys.exit(r.returncode)


def cmd_decks(a):
    import datetime
    rows = []
    for d in find_decks():
        c = cfg(d)
        slides = slides_of(d)
        times = [p.stat().st_mtime for p in slides] + [(d / "deck.json").stat().st_mtime]
        rows.append({
            "name": d.name,
            "title": c.get("title", d.name),
            "slides": len(slides),
            "updated": datetime.datetime.fromtimestamp(max(times)).strftime("%m-%d %H:%M"),
            "path": str(d),
        })
    rows.sort(key=lambda r: r["updated"], reverse=True)

    if a.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    if not rows:
        print("[slidecraft] 덱이 없다. `new <이름>` 으로 만든다")
        return
    w = max(len(r["title"]) for r in rows)
    print(f'{"제목".ljust(w)}  장수  마지막 수정   이름')
    for r in rows:
        print(f'{r["title"].ljust(w)}  {r["slides"]:>3}  {r["updated"]}  {r["name"]}')
    print(f"\n{len(rows)}개. 고치려면: preview <이름>")


# ------------------------------------------------------------------ 라이브 프리뷰 / 시각 편집기

WATCH_GLOBS = (
    "slides/*.html",
    "templates/*.html",
    "assets/*.css",
    "assets/*.js",
    "deck.json",
)

EDITOR_FILES = {"shell.html", "shell.css", "shell.js", "bridge.js"}
MAX_BODY = 256_000


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


def resolve_deck_file(root: Path, file_id: str) -> Path:
    """Allow only slides/*.html, templates/*.html under the deck root."""
    if not file_id or "\\" in file_id or file_id.startswith("/") or ".." in file_id.split("/"):
        raise PermissionError("path not allowed")
    parts = file_id.split("/")
    if len(parts) != 2 or parts[0] not in ("slides", "templates"):
        raise PermissionError("path not allowed")
    if not parts[1].endswith(".html") or parts[1].startswith(".") or "/" in parts[1]:
        raise PermissionError("path not allowed")
    path = (root / parts[0] / parts[1]).resolve()
    root_r = root.resolve()
    if path.parent != (root_r / parts[0]):
        raise PermissionError("path escape")
    return path


def project_manifest(root: Path) -> dict:
    c = cfg(root)
    theme = root / "assets" / "theme.css"
    theme_text = theme.read_text(encoding="utf-8") if theme.exists() else ""
    slides = []
    for p in slides_of(root):
        slides.append({
            "id": f"slides/{p.name}",
            "title": slide_title_of(p),
            "revision": html_patch.file_revision(p),
        })
    templates = []
    for p in templates_of(root):
        templates.append({
            "id": f"templates/{p.name}",
            "title": slide_title_of(p),
            "revision": html_patch.file_revision(p),
        })
    return {
        "title": c.get("title", root.name),
        "size": c.get("size", [1280, 720]),
        "token": watch_token(root),
        "slides": slides,
        "templates": templates,
        "palette": html_patch.read_theme_tokens(theme_text) if theme_text else {},
        "themeRevision": html_patch.file_revision(theme) if theme.exists() else "",
    }


def inject_canvas(html: str, file_id: str, bridge_js: str) -> str:
    """Inject base href + bridge. Keep regions.js for select-mode overlays."""
    base_dir = "/slides/" if file_id.startswith("slides/") else "/templates/"
    if re.search(r"<base\b", html, re.I) is None:
        if re.search(r"<head[^>]*>", html, re.I):
            html = re.sub(
                r"(<head[^>]*>)",
                rf'\1\n<base href="{base_dir}">\n',
                html, count=1, flags=re.I)
        else:
            html = f'<base href="{base_dir}">\n' + html
    if re.search(r"<html\b", html, re.I):
        if "data-editor-file=" in html:
            html = re.sub(
                r'data-editor-file="[^"]*"',
                f'data-editor-file="{file_id}"',
                html, count=1)
        else:
            html = re.sub(
                r"<html\b",
                f'<html data-editor-file="{file_id}"',
                html, count=1, flags=re.I)
    # Ensure regions.js is present for select/grid overlays (after other scripts).
    if not re.search(r'regions\.js', html, re.I):
        tag = '<script src="../assets/regions.js"></script>\n'
        if re.search(r"</body\s*>", html, re.I):
            html = re.sub(r"</body\s*>", tag + "</body>", html, count=1, flags=re.I)
        else:
            html += "\n" + tag
    bridge_tag = f"<script>\n{bridge_js}\n</script>\n"
    if re.search(r"</body\s*>", html, re.I):
        html = re.sub(r"</body\s*>", bridge_tag + "</body>", html, count=1, flags=re.I)
    else:
        html = html + "\n" + bridge_tag
    return html


def read_json_body(handler, max_bytes=MAX_BODY) -> dict:
    length = int(handler.headers.get("Content-Length") or "0")
    if length <= 0 or length > max_bytes:
        raise ValueError("invalid body size")
    raw = handler.rfile.read(length)
    return json.loads(raw.decode("utf-8"))


def cmd_preview(a):
    import http.server
    import json as _json
    import socketserver
    import threading
    import webbrowser

    root = find_deck(a.deck)
    c = cfg(root)

    def load_bridge():
        f = EDITOR / "bridge.js"
        return f.read_text(encoding="utf-8") if f.exists() else ""

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kw):
            super().__init__(*args, directory=str(root), **kw)

        def log_message(self, *args):
            pass

        def _check_local(self):
            host = (self.headers.get("Host") or "").split(":")[0]
            if host not in ("127.0.0.1", "localhost", ""):
                self.send_error(403, "localhost only")
                return False
            return True

        def _send(self, body, ctype="text/html; charset=utf-8", extra=None, status=200):
            if isinstance(body, str):
                body = body.encode()
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def _send_json(self, payload, status=200):
            return self._send(
                _json.dumps(payload, ensure_ascii=False),
                "application/json; charset=utf-8",
                status=status,
            )

        def do_GET(self):
            if not self._check_local():
                return
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            qs = urllib.parse.parse_qs(parsed.query)
            try:
                if path == "/":
                    shell = (EDITOR / "shell.html").read_text(encoding="utf-8")
                    return self._send(shell)

                if path.startswith("/__editor/"):
                    name = path[len("/__editor/"):]
                    if name not in EDITOR_FILES:
                        return self.send_error(404)
                    f = EDITOR / name
                    if not f.exists():
                        return self.send_error(404)
                    ctype = {
                        ".css": "text/css; charset=utf-8",
                        ".js": "application/javascript; charset=utf-8",
                        ".html": "text/html; charset=utf-8",
                    }.get(f.suffix, "application/octet-stream")
                    return self._send(f.read_text(encoding="utf-8"), ctype)

                if path == "/__token":
                    return self._send(watch_token(root), "text/plain; charset=utf-8")

                if path == "/__regions.js":
                    f = root / "assets" / "regions.js"
                    return self._send(f.read_text() if f.exists() else "",
                                      "application/javascript; charset=utf-8")

                if path == "/__project":
                    return self._send_json(project_manifest(root))

                if path == "/__canvas":
                    file_id = (qs.get("file") or [""])[0]
                    try:
                        target = resolve_deck_file(root, file_id)
                    except PermissionError:
                        return self._send_json({"error": "path not allowed"}, 403)
                    if not target.exists():
                        return self._send_json({"error": "file not found"}, 404)
                    html = inject_canvas(target.read_text(encoding="utf-8"), file_id, load_bridge())
                    return self._send(html)

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
                    import datetime
                    stamp = datetime.datetime.now().strftime("%m-%d %H%M")
                    title = f'{c.get("title", root.name)} ({stamp})'
                    utf8 = urllib.parse.quote(
                        re.sub(r'[\\/:*?"<>|]+', "_", title).strip() or "deck")
                    ascii_name = re.sub(r'[^A-Za-z0-9._-]+', "_", title).strip("_") or "deck"
                    return self._send(html, "text/html; charset=utf-8",
                                      {"Content-Disposition":
                                       f'attachment; filename="{ascii_name}.html"; '
                                       f"filename*=UTF-8''{utf8}.html"})
            except (Exception, SystemExit) as e:
                return self._send(f"<pre>{e}</pre>", "text/html; charset=utf-8")

            return super().do_GET()

        def do_PATCH(self):
            if not self._check_local():
                return
            path = urllib.parse.urlparse(self.path).path
            try:
                body = read_json_body(self)
            except Exception as e:
                return self._send_json({"error": str(e)}, 400)

            try:
                if path == "/__edit":
                    return self._patch_edit(body)
                if path == "/__theme":
                    return self._patch_theme(body)
                return self._send_json({"error": "not found"}, 404)
            except html_patch.PatchError as e:
                status = {
                    "not_found": 404,
                    "duplicate": 400,
                    "non_leaf": 400,
                    "malformed": 400,
                    "bad_request": 400,
                    "bad_style": 400,
                    "bad_text": 400,
                    "bad_token": 400,
                    "no_text": 400,
                }.get(e.code, 400)
                return self._send_json({"error": str(e), "code": e.code}, status)
            except PermissionError as e:
                return self._send_json({"error": str(e)}, 403)
            except Exception as e:
                return self._send_json({"error": str(e)}, 500)

        def do_POST(self):
            if not self._check_local():
                return
            path = urllib.parse.urlparse(self.path).path
            try:
                body = read_json_body(self)
            except Exception as e:
                return self._send_json({"error": str(e)}, 400)
            if path != "/__slides/from-template":
                return self._send_json({"error": "not found"}, 404)
            try:
                tpl_id = body.get("templateId") or ""
                src = resolve_deck_file(root, tpl_id)
                if not tpl_id.startswith("templates/") or not src.exists():
                    return self._send_json({"error": "template not found"}, 404)
                existing = slides_of(root)
                no = f"{len(existing) + 1:02d}"
                stem = re.sub(r"\.html$", "", src.name)
                dest = root / "slides" / f"{no}-{stem}.html"
                html = src.read_text(encoding="utf-8")
                title = slide_title_of(src)
                html = re.sub(r'data-slide="[^"]*"', f'data-slide="{no}"', html, count=1)
                html = re.sub(
                    r'<span class="s-num">[^<]*</span>',
                    f'<span class="s-num">{no}</span>',
                    html, count=1)
                html_patch.atomic_write(dest, html)
                return self._send_json({
                    "fileId": f"slides/{dest.name}",
                    "title": title,
                    "revision": html_patch.file_revision(dest),
                    "token": watch_token(root),
                })
            except PermissionError as e:
                return self._send_json({"error": str(e)}, 403)
            except Exception as e:
                return self._send_json({"error": str(e)}, 500)

        def _patch_edit(self, body):
            file_id = body.get("fileId") or ""
            base_rev = body.get("baseRevision") or ""
            target = body.get("target") or {}
            changes = body.get("changes") or {}
            path = resolve_deck_file(root, file_id)
            if not path.exists():
                return self._send_json({"error": "file not found"}, 404)
            cur = html_patch.file_revision(path)
            if base_rev != cur:
                return self._send_json({
                    "error": "revision conflict",
                    "revision": cur,
                    "reason": "file changed externally",
                }, 409)
            region = target.get("region")
            part = target.get("part")
            if not region:
                return self._send_json({"error": "region required"}, 400)
            html = path.read_text(encoding="utf-8")
            new_html = html_patch.apply_html_patch(html, region, part, changes)
            html_patch.atomic_write(path, new_html)
            return self._send_json({
                "ok": True,
                "revision": html_patch.file_revision(path),
                "token": watch_token(root),
            })

        def _patch_theme(self, body):
            theme = root / "assets" / "theme.css"
            if not theme.exists():
                return self._send_json({"error": "theme.css missing"}, 404)
            base_rev = body.get("baseRevision") or ""
            cur = html_patch.file_revision(theme)
            if base_rev != cur:
                return self._send_json({
                    "error": "revision conflict",
                    "revision": cur,
                    "reason": "theme changed externally",
                }, 409)
            changes = body.get("changes") or {}
            css = theme.read_text(encoding="utf-8")
            new_css = html_patch.apply_theme_patch(css, changes)
            html_patch.atomic_write(theme, new_css)
            return self._send_json({
                "ok": True,
                "revision": html_patch.file_revision(theme),
                "palette": html_patch.read_theme_tokens(new_css),
                "token": watch_token(root),
            })

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
    print(f"[slidecraft] 시각 편집기: {url}   ({c.get('title', root.name)} · {n}장)", flush=True)
    print("  영역을 클릭해 고치면 원본 HTML/테마 파일이 저장된다. 'HTML 저장'으로 공유본을 받는다.",
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
    root = find_deck(a.deck)
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

    p = sub.add_parser("icons", help="아이콘 찾기/조각 만들기 (icons.py 로 넘긴다)",
                       add_help=False)
    p.add_argument("rest", nargs=argparse.REMAINDER); p.set_defaults(fn=cmd_icons)

    p = sub.add_parser("decks", help="만들어 둔 덱 목록 (저장하지 않고 훑는다)")
    p.add_argument("--json", action="store_true"); p.set_defaults(fn=cmd_decks)

    p = sub.add_parser("preview", help="라이브 시각 편집기 (브라우저 자동 실행 · 자동 새로고침)")
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
