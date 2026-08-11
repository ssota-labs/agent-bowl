#!/usr/bin/env python3
"""icons — 구워둔 아이콘 세트에서 찾아 슬라이드에 넣을 조각을 만든다.

네트워크를 쓰지 않는다. assets/icons/*.json 만 읽는다.
(그 파일을 다시 굽는 건 build_icons.py 이고, 버전 올릴 때만 쓴다)

  python3 icons.py sets                     # 어떤 세트가 있나
  python3 icons.py find 화살표               # 이름으로 찾기 (한글도 통한다)
  python3 icons.py find chart --set lucide
  python3 icons.py get lucide:trending-up   # 슬라이드에 붙일 <svg> 조각
"""

import argparse
import json
import sys
from html import escape
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
ICON_DIR = SKILL_DIR / "assets" / "icons"

# 한글로 찾을 수 있게. 업무 슬라이드에서 자주 찾는 것들만 — 없으면 영어로 찾으면 된다.
ALIASES = {
    "화살표": "arrow", "위": "up", "아래": "down", "왼쪽": "left", "오른쪽": "right",
    "상승": "trending-up", "증가": "trending-up", "하락": "trending-down", "감소": "trending-down",
    "차트": "chart", "그래프": "chart", "막대": "bar", "원형": "pie", "지표": "activity",
    "사람": "user", "사용자": "user", "고객": "user", "팀": "users", "조직": "users",
    "회사": "building", "건물": "building", "공장": "factory", "매장": "store",
    "돈": "dollar", "매출": "dollar", "비용": "wallet", "카드": "credit-card",
    "달력": "calendar", "일정": "calendar", "시간": "clock", "시계": "clock",
    "체크": "check", "완료": "check", "확인": "check", "경고": "alert", "주의": "alert",
    "오류": "x-circle", "실패": "x", "금지": "ban", "정보": "info", "물음": "help",
    "설정": "settings", "톱니": "settings", "검색": "search", "돋보기": "search",
    "메일": "mail", "이메일": "mail", "전화": "phone", "메시지": "message",
    "문서": "file-text", "파일": "file", "폴더": "folder", "보고서": "file-text",
    "잠금": "lock", "보안": "shield", "방패": "shield", "열쇠": "key",
    "지구": "globe", "세계": "globe", "지도": "map", "위치": "map-pin", "핀": "map-pin",
    "전구": "lightbulb", "아이디어": "lightbulb", "번개": "zap", "로켓": "rocket",
    "별": "star", "하트": "heart", "북마크": "bookmark", "태그": "tag",
    "목표": "target", "과녁": "target", "깃발": "flag", "트로피": "trophy",
    "톱니바퀴": "settings", "새로고침": "refresh", "다운로드": "download", "업로드": "upload",
    "장바구니": "shopping-cart", "상자": "package", "배송": "truck", "비행기": "plane",
}


def load(name: str) -> dict:
    f = ICON_DIR / f"{name}.json"
    if not f.exists():
        sys.exit(f"[icons] 그런 세트가 없다: {name} — {', '.join(available()) or '구운 세트 없음'}")
    return json.loads(f.read_text())


def available():
    return sorted(p.stem for p in ICON_DIR.glob("*.json")) if ICON_DIR.is_dir() else []


def cmd_sets(a):
    names = available()
    if not names:
        sys.exit("[icons] 구운 세트가 없다. scripts/build_icons.py 를 돌린다")
    print(f"{'세트':10} {'개수':>6}  {'라이선스':12} 설명")
    for n in names:
        d = load(n)
        print(f"{d['set']:10} {len(d['icons']):>6}  {d['license']:12} {d.get('note','')}")
    print("\n한 덱에는 한 세트만 쓴다 (design.md — 모티프 하나를 끝까지 반복).")


def cmd_find(a):
    q = a.query.strip().lower()
    q = ALIASES.get(a.query.strip(), q)
    sets = [a.set] if a.set else available()
    total = 0
    for n in sets:
        d = load(n)
        hits = [k for k in d["icons"] if q in k]
        if not hits:
            continue
        # 이름이 짧을수록 정확한 매치일 확률이 높다
        hits.sort(key=lambda k: (not k.startswith(q), len(k), k))
        shown = hits[:a.limit]
        total += len(hits)
        print(f"\n[{n}] {len(hits)}개 중 {len(shown)}개")
        for i in range(0, len(shown), 4):
            print("  " + "  ".join(f"{k:26}" for k in shown[i:i + 4]).rstrip())
    if not total:
        print(f"'{a.query}' 로는 못 찾았다. 영어 키워드로 다시 찾아본다 "
              f"(예: arrow, chart, user, check)")
    else:
        print(f"\n붙일 조각:  python3 icons.py get <세트>:<이름>")


def snippet(set_name: str, icon: str, cls="ic", size=None, label=None) -> str:
    d = load(set_name)
    if icon not in d["icons"]:
        near = [k for k in d["icons"] if icon in k][:6]
        msg = f"[icons] {set_name} 에 '{icon}' 이 없다"
        if near:
            msg += "\n  비슷한 것: " + ", ".join(near)
        sys.exit(msg)
    style = f' style="--ic-size:{size}"' if size else ""
    if label:
        a11y = f' role="img" aria-label="{escape(label, quote=True)}"'
    else:
        a11y = ' aria-hidden="true"'
    # 루트 속성(fill/stroke 등)은 원본 <svg> 에 있던 것이다. 개별 path 가 이걸
    # 물려받으므로 빠지면 선형 아이콘이 검은 덩어리로 칠해진다.
    root = " ".join(f'{k}="{v}"' for k, v in d.get("root", {}).items())
    return (f'<svg class="{escape(cls, quote=True)}" viewBox="{d["viewBox"]}"'
            f'{" " + root if root else ""}{style}{a11y} '
            f'xmlns="http://www.w3.org/2000/svg">{d["icons"][icon]}</svg>')


def cmd_get(a):
    if ":" not in a.ref:
        sys.exit("[icons] 형식은 <세트>:<이름> 이다 (예: lucide:trending-up)")
    s, name = a.ref.split(":", 1)
    print(snippet(s, name, a.cls, a.size, a.label))


def main():
    ap = argparse.ArgumentParser(prog="icons", description="구워둔 아이콘에서 찾아 조각을 만든다")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("sets", help="세트 목록"); p.set_defaults(fn=cmd_sets)

    p = sub.add_parser("find", help="이름으로 찾기 (한글 키워드도 된다)")
    p.add_argument("query"); p.add_argument("--set"); p.add_argument("--limit", type=int, default=24)
    p.set_defaults(fn=cmd_find)

    p = sub.add_parser("get", help="슬라이드에 붙일 <svg> 조각")
    p.add_argument("ref", help="<세트>:<이름>")
    p.add_argument("--cls", default="ic", help='클래스 (기본 ic, 예: "ic ic-lg")')
    p.add_argument("--size", help="크기 직접 지정 (예: 28px)")
    p.add_argument("--label", help="스크린리더용 설명. 없으면 장식으로 취급한다")
    p.set_defaults(fn=cmd_get)

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
