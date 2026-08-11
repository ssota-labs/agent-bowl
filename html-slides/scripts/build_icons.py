#!/usr/bin/env python3
"""build_icons — 아이콘 세트를 npm 에서 받아 assets/icons/*.json 으로 굽는다.

**슬라이드를 만들 때 이걸 쓸 일은 없다.** 아이콘 라이브러리 버전을 올릴 때만 쓴다.
평소에는 이미 구워진 assets/icons/*.json 만 읽으면 되고 네트워크가 필요 없다.

굽는 이유
  - 오프라인에서 열려야 하고 build 하면 HTML 한 장으로 합쳐지므로 CDN·npm 을 못 쓴다
  - 원본 패키지는 스프라이트·폰트·타입 정의까지 들고 있어 수십 MB 다.
    실제로 필요한 건 아이콘 본문뿐이라 그것만 뽑는다
  - 굽는 과정에서 활성 콘텐츠(스크립트·외부 참조)가 없는지 검사한다

쓰는 법
  python3 scripts/build_icons.py            # 전부 다시 굽는다
  python3 scripts/build_icons.py lucide     # 하나만
"""

import json
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
OUT = SKILL_DIR / "assets" / "icons"

# 세트 정의 — (npm 패키지, 라이선스, 홈, viewBox, [가져올 하위경로])
SETS = {
    "lucide": {
        "root": {"fill":"none","stroke":"currentColor","stroke-width":"2","stroke-linecap":"round","stroke-linejoin":"round"},
        "pkg": "lucide-static", "license": "ISC",
        "home": "https://lucide.dev",
        "viewbox": "0 0 24 24",
        "dirs": {"": "icons"},
        "note": "선이 얇고 균일하다. 기본값으로 쓰기 좋다.",
    },
    "tabler": {
        "root": {"fill":"none","stroke":"currentColor","stroke-width":"2","stroke-linecap":"round","stroke-linejoin":"round"},
        "pkg": "@tabler/icons", "license": "MIT",
        "home": "https://tabler.io/icons",
        "viewbox": "0 0 24 24",
        "dirs": {"": "icons/outline", "fill": "icons/filled"},
        "note": "Lucide 와 결이 비슷하나 수가 훨씬 많다.",
    },
    "phosphor": {
        "root": {"fill":"currentColor"},
        "pkg": "@phosphor-icons/core", "license": "MIT",
        "home": "https://phosphoricons.com",
        "viewbox": "0 0 256 256",
        "dirs": {"": "assets/regular", "fill": "assets/fill", "bold": "assets/bold"},
        "note": "기하학적이고 두께 변형이 있다.",
    },
    "remix": {
        "root": {"fill":"currentColor"},
        "pkg": "remixicon", "license": "Apache-2.0",
        "home": "https://remixicon.com",
        "viewbox": "0 0 24 24",
        "dirs": {"": "icons"},
        "note": "이름 끝의 -line / -fill 로 선형·채움형이 갈린다.",
    },
    "hugeicons": {
        "root": {"fill":"none"},
        "pkg": "@hugeicons/core-free-icons", "license": "MIT",
        "home": "https://hugeicons.com",
        "viewbox": "0 0 24 24",
        "dirs": {"": "dist/esm"},          # SVG 가 아니라 JS 배열이다
        "note": "무료 세트. 원본이 JS 모듈이라 구울 때 변환한다.",
    },
}

# 속성은 지우지 않는다. 선형(fill="none" stroke="currentColor")과 채움형(fill 없음)이
# 섞여 있어서, 지우면 CSS 하나로 둘 다 맞출 수가 없다. 아이콘이 스스로를 설명하게 둔다.
# 반복되는 문자열이라 zip 안에서는 어차피 거의 공짜다 (실측 차이 4%).
UNIFORM = {}

ALLOWED_ELS = {"path", "circle", "ellipse", "line", "polygon", "polyline", "rect", "g"}
DANGER = re.compile(
    r'<script|javascript:|\son[a-z]+\s*=|<foreignObject|<iframe|<embed|<object'
    r'|xlink:href|<image|<!ENTITY|<!DOCTYPE|<use\b', re.I)

CAMEL = re.compile(r'([a-z0-9])([A-Z])')
SVG_OPEN = re.compile(r'^.*?<svg[^>]*>', re.S)
SVG_CLOSE = re.compile(r'</svg>\s*$')
TUPLE = re.compile(r'\[\s*"([a-zA-Z]+)"\s*,\s*\{(.*?)\}\s*\]', re.S)
ATTR = re.compile(r'(\w+)\s*:\s*"([^"]*)"')


def fetch(pkg: str, into: Path) -> Path:
    """npm pack 으로 받아서 푼다. install 이 아니라 pack 이다 — 설치 스크립트를 돌리지 않는다."""
    print(f"  · {pkg} 받는 중…", flush=True)
    r = subprocess.run(["npm", "pack", pkg, "--silent"], cwd=into,
                       capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"[build_icons] npm pack {pkg} 실패:\n{r.stderr.strip()}")
    tgz = sorted(into.glob("*.tgz"))[-1]
    with tarfile.open(tgz) as t:
        t.extractall(into / "x")
    return into / "x" / "package"


def clean_attrs(pairs):
    out = {}
    for k, v in pairs:
        k = CAMEL.sub(r'\1-\2', k).lower()
        if k == "key":
            continue
        if UNIFORM.get(k) == v:          # 균일한 값은 CSS 가 준다
            continue
        out[k] = v
    return out


def body_from_svg(text: str) -> str:
    body = SVG_CLOSE.sub("", SVG_OPEN.sub("", text))
    body = re.sub(r'<!--.*?-->', "", body, flags=re.S)
    # 균일 속성 제거
    def strip(m):
        tag, attrs = m.group(1), m.group(2)
        keep = clean_attrs(re.findall(r'([\w:-]+)\s*=\s*"([^"]*)"', attrs))
        a = " ".join(f'{k}="{v}"' for k, v in keep.items())
        return f'<{tag}{" " + a if a else ""}/>'
    body = re.sub(r'<([a-zA-Z]+)([^>]*?)/>', strip, body)
    return re.sub(r'>\s+<', "><", body).strip()


def body_from_js(text: str) -> str:
    parts = []
    for tag, attrs in TUPLE.findall(text):
        keep = clean_attrs(ATTR.findall(attrs))
        a = " ".join(f'{k}="{v}"' for k, v in keep.items())
        parts.append(f'<{tag}{" " + a if a else ""}/>')
    return "".join(parts)


def harvest(root: Path, spec: dict):
    icons, els = {}, set()
    for suffix, rel in spec["dirs"].items():
        src = root / rel
        if not src.is_dir():
            sys.exit(f"[build_icons] 경로가 없다: {src}")
        if rel.endswith("esm"):                       # hugeicons
            files = [f for f in src.glob("*.js")
                     if not f.name.startswith(("index", "types", "loader"))]
            for f in files:
                # Building01Icon → building-01. 문자→대문자뿐 아니라 문자→숫자 경계도
                # 끊어야 다른 라이브러리 이름 관례(arrow-up-01)와 맞는다.
                stem = f.stem.replace("Icon", "")
                stem = CAMEL.sub(r'\1-\2', stem)
                stem = re.sub(r'([A-Za-z])(\d)', r'\1-\2', stem)
                name = stem.lower().strip("-")
                b = body_from_js(f.read_text(errors="replace"))
                if b:
                    icons[name] = b
            continue
        for f in sorted(src.rglob("*.svg")):
            if f.stat().st_size > 20000:              # 스프라이트는 아이콘이 아니다
                continue
            raw = f.read_text(errors="replace")
            if DANGER.search(raw):
                sys.exit(f"[build_icons] 활성 콘텐츠 발견, 중단: {f}")
            els.update(re.findall(r'<\s*([a-zA-Z][\w:-]*)', raw))
            b = body_from_svg(raw)
            if b:
                icons[f.stem + ("-" + suffix if suffix else "")] = b
    bad = els - ALLOWED_ELS - {"svg"}
    if bad:
        sys.exit(f"[build_icons] 예상 못 한 요소: {sorted(bad)}")
    return icons


def build(name: str, tmp: Path):
    spec = SETS[name]
    root = fetch(spec["pkg"], tmp / name)
    icons = harvest(root, spec)
    if not icons:
        sys.exit(f"[build_icons] {name}: 아이콘을 못 뽑았다")
    ver = json.loads((root / "package.json").read_text()).get("version", "?")
    OUT.mkdir(parents=True, exist_ok=True)
    f = OUT / f"{name}.json"
    f.write_text(json.dumps({
        "set": name, "package": spec["pkg"], "version": ver,
        "license": spec["license"], "home": spec["home"],
        "viewBox": spec["viewbox"], "root": spec["root"], "note": spec["note"],
        "icons": dict(sorted(icons.items())),
    }, ensure_ascii=False, separators=(",", ":")))
    print(f"  → {f.name}  {len(icons):5}개  {f.stat().st_size/1024:7.1f} KB  (v{ver}, {spec['license']})")


def main():
    want = sys.argv[1:] or list(SETS)
    for w in want:
        if w not in SETS:
            sys.exit(f"[build_icons] 모르는 세트: {w} — {', '.join(SETS)}")
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        for name in want:
            (tmp / name).mkdir()
            build(name, tmp)
    print("\n라이선스 고지는 assets/icons/LICENSES.md 에 함께 둔다.")


if __name__ == "__main__":
    main()
