# 세계지도

업무 슬라이드에서 지도는 거의 항상 셋 중 하나다.

| 하고 싶은 말 | 쓸 것 |
|---|---|
| "우리는 여기 진출해 있다" | `--highlight` 로 나라/대륙을 칠한다 |
| "이 지역을 보자" | `--focus` 로 그 지역만 확대한다 |
| 화면에서 대륙을 짚어가며 설명 | `--hover continent` (기본값) |

## 명령어

~~~bash
S=<스킬디렉터리>/scripts/slidecraft.py

# 지도 슬라이드를 덱에 한 장 추가
python3 $S worldmap <덱경로> --title "글로벌 진출 현황" --highlight KR,JP,US --legend

# 아시아만 확대 + 아시아 전체 하이라이트 + 바다 칠하기
python3 $S worldmap <덱경로> --slug apac --title "APAC" --focus apac --highlight as --sea

# 슬라이드 말고 지도 블록만 뽑아서 기존 슬라이드에 직접 붙이기
python3 $S worldmap --svg-only /tmp/map.html --highlight DE,FR,GB --focus eu
~~~

`worldmap.py` 를 직접 불러도 된다 (`python3 scripts/worldmap.py --highlight KR > snippet.html`).

## 옵션

| 옵션 | 기본 | 설명 |
|---|---|---|
| `--highlight` | 없음 | `KR,JP,US` (나라) / `as,eu` (대륙) / 섞어도 된다 |
| `--focus` | `world` | `world na sa eu af as oc an apac americas emea` |
| `--hover` | `continent` | `continent` / `country` / `off` |
| `--palette` | `accent` | `accent` = 강조색 하나 / `continent` = 대륙별 7색 |
| `--legend` | 꺼짐 | 범례를 우하단에 붙인다. `--palette continent` 면 대륙 목록, `accent` 면 `--legend-label` 한 줄 |
| `--sea` | 꺼짐 | 바다를 브랜드색으로 칠한다 (밝은 슬라이드에서 지도를 띄울 때) |
| `--slug` `--title` `--eyebrow` | — | 슬라이드 파일명·제목 |
| `--region` `--label` | `world-map` / `세계 지도` | 영역 주소 (주소록에 이 이름으로 뜬다) |
| `--assign` | 없음 | `RU=as` 처럼 대륙 재배정 |
| `--marker` | 없음 | `KR,JP,SG` — 그 나라 안에 핀을 찍는다 |
| `--marker-size` | `1.0` | 핀 크기 배수. 작은 나라를 덮으면 0.7 정도로 |
| `--legend-label` | `진출 국가` | `--palette accent` 일 때 범례 한 줄 문구 |
| `--simplify` `--precision` | `0` / `1` | 좌표 축약. **기본은 끔** — 켜면 확대 뷰에서 해안선이 눈에 띄게 뭉개진다 |
| `--svg-only FILE` | — | 슬라이드 대신 지도 블록만 파일로 |

**`--palette continent` 는 기본값이 아니다.** 강조색을 아껴 쓰라는 디자인 원칙
([design.md](design.md)) 때문이다. 대륙별 7색은 범례가 필요한 발표에서만 켠다.

## 색 바꾸기

`assets/worldmap.css` 는 고치지 않는다. 덱의 `assets/theme.css` 에서 변수만 덮어쓴다.

~~~css
:root {
  --wm-land:   #dfe6ef;   /* 기본 육지 */
  --wm-on:     #1e2761;   /* 하이라이트한 나라 */
  --wm-hover:  #f96167;   /* 마우스 올린 곳 */
  --wm-stroke: #ffffff;   /* 나라 경계선 */
  --wm-sea:    #1e2761;   /* --sea 켰을 때 바다 */
}
~~~

기본값은 `--brand` / `--brand-2` / `--accent` 를 따라가므로, 테마 색만 바꿔도 지도가 같이 따라온다.
`.slide.dark` 와 `--sea` 일 때는 육지가 자동으로 반투명 흰색이 된다.

## 마크업

생성되는 구조는 이렇다. 손으로 고칠 일이 있으면 이 형태를 유지한다.

~~~html
<div class="wm" data-hover="continent" data-palette="accent"
     data-region="world-map" data-label="세계 지도">
  <svg class="wm-svg" viewBox="…">
    <g class="wm-c wm-c-as" data-continent="as" data-label="아시아">
      <path class="wm-land is-on" d="…" data-cc="KR" data-name="South Korea"/>
      …
    </g>
  </svg>
  <ul class="wm-legend">…</ul>
</div>
~~~

- 대륙 그룹 = `g.wm-c-<코드>` · 나라 = `path[data-cc]`
- 하이라이트 = `is-on` 클래스 (나라 `path` 에 붙이거나 대륙 `g` 에 붙인다)
- 나중에 손으로 한 나라만 더 칠하고 싶으면 그 `path` 에 `is-on` 만 추가하면 된다

지도 블록 전체가 `data-region` 하나다. 영역 주소록에는 "세계 지도" 한 줄로 잡힌다.

## 마커(핀) 꽂기

~~~bash
python3 $S worldmap <덱경로> --focus apac --highlight KR,JP,SG --marker KR,JP,SG
~~~

`--marker` 는 나라 **안쪽**에 핀을 찍는다. 위치는 자동으로 잡는다:

- 섬이 여러 개면 **가장 넓은 덩어리**를 고른다 (일본에서 홋카이도에 찍히지 않는다)
- 폴리곤 중심이 나라 밖으로 나가는 굽은 나라(칠레·노르웨이)는 안쪽으로 되돌린다
- 반지름은 프레임 폭에 비례한다 — **확대해도 화면상 크기가 그대로**다.
  작은 나라를 핀이 덮으면 `--marker-size 0.7` 로 줄인다

핀 색은 `--wm-pin` (기본 `--accent`). 나라마다 다르게 하려면:

~~~css
.wm-pin[data-cc="KR"] { --wm-pin: #e5342a; }
.wm-pin[data-cc="JP"] { --wm-pin: #36454f; }
~~~

싱가포르·홍콩처럼 지도에서 1px 도 안 되는 나라는 `--highlight` 로는 안 보인다.
**그럴 때 핀이 유일한 방법이다.**

## 카드(콜아웃) 붙이기

카드는 내용·위치가 매번 달라서 자동 생성하지 않는다. 아래를 베껴서 손으로 넣는다.

**반드시 `<svg>` 안에, 나라 `path` 와 같은 좌표계로 넣는다.** `.wm` 컨테이너 위에
HTML 로 얹으면 어긋난다 — 지도는 비율을 지키느라 컨테이너를 꽉 채우지 않고,
남는 여백(레터박스)만큼 밀린다.

먼저 앵커 좌표를 얻는다:

~~~bash
python3 scripts/worldmap.py --anchor KR,JP,SG
#  KR   978.1   220.7
#  JP  1008.7   220.4
#  SG   926.3   353.9
~~~

그리고 `</svg>` 바로 앞에 넣는다:

~~~html
<g class="wm-callout">
  <line class="wm-callout-leader" x1="932" y1="198" x2="974" y2="217"/>
  <rect class="wm-callout-box" x="800" y="172" width="134" height="40" rx="5"/>
  <text class="wm-callout-title" x="810" y="187" font-size="11.1">서울 · 아시아 본부</text>
  <text class="wm-callout-body"  x="810" y="202" font-size="9.2">직원 120명</text>
</g>
~~~

- `line` 의 `x2,y2` 를 앵커 좌표 근처로 두면 카드가 그 나라를 가리킨다
- **글자 크기는 viewBox 단위**다. `프레임 폭 ÷ 48`(제목) · `÷ 58`(본문) 에서 시작한다.
  위 값은 `--focus apac`(폭 532) 기준 — 프레임이 바뀌면 다시 계산한다
- 프레임 폭은 `maps.md` 의 `FOCUS_BOX` 또는 생성된 `viewBox` 3번째 값에서 본다
- 넣고 나면 **반드시 `shot` 으로 찍어 눈으로 본다.** 카드가 나라를 덮거나
  프레임 밖으로 나가는 건 `qa` 가 못 잡는다

### 호버하면 카드가 뜨게

CSS 만으로 된다 (JS 없음). 카드에 `data-for="KR"` 을 달고, 슬라이드 `<section>` 안에
`<style>` 을 넣는다. `<head>` 가 아니라 **`<section>` 안**이어야 빌드에서 살아남는다.

~~~html
<style>
  .wm-callout[data-for] { opacity: 0; transition: opacity .18s ease; pointer-events: none; }
  .wm-svg:has([data-cc="KR"]:hover) .wm-callout[data-for="KR"] { opacity: 1; }
</style>
~~~

나라마다 한 줄씩 필요하다 (`:has()` 로는 값을 일반화할 수 없다).

**대신 발표자료에는 웬만하면 쓰지 말 것.**

- **PDF·인쇄물에는 호버가 없다.** 호버에만 담은 정보는 공유하는 순간 사라진다
- 발표 중에 청중은 마우스를 올릴 수 없다. 화면 앞의 발표자만 볼 수 있다

호버 카드가 값어치를 하는 건 **사용자가 자기 화면에서 혼자 훑어볼 때**다.
남에게 보낼 덱이라면 카드를 그냥 항상 보이게 둔다.

## 대륙 코드

| 코드 | 이름 | 나라 수 |
|---|---|---|
| `na` | 북아메리카 | 41 |
| `sa` | 남아메리카 | 14 |
| `eu` | 유럽 | 53 |
| `af` | 아프리카 | 60 |
| `as` | 아시아 | 51 |
| `oc` | 오세아니아 | 33 |
| `an` | 남극 | 5 |

묶음: `apac`(as+oc) · `americas`(na+sa) · `emea`(eu+af) · `world`(전부)
한글도 통한다 — `아시아`, `유럽`, `북미`, `남미`, `아프리카`, `오세아니아`.

**러시아(RU)는 유럽에 넣었다.** 유럽에 마우스를 올리면 시베리아까지 같이 칠해진다.
아시아 쪽으로 옮기려면 `--assign RU=as`. (`--focus eu` 프레임은 러시아 극동을
일부러 잘라내므로, 확대 뷰에서는 이 문제가 보이지 않는다.)

크리스마스섬(CX)·코코스제도(CC)는 호주령이라 오세아니아에 넣었다.

## 나라 코드

ISO 3166-1 alpha-2 두 글자다. 자주 쓰는 것:

`KR` 한국 · `JP` 일본 · `CN` 중국 · `TW` 대만 · `HK` 홍콩 · `SG` 싱가포르 · `IN` 인도
`VN` 베트남 · `TH` 태국 · `ID` 인도네시아 · `MY` 말레이시아 · `PH` 필리핀 · `AE` UAE · `SA` 사우디
`US` 미국 · `CA` 캐나다 · `MX` 멕시코 · `BR` 브라질 · `AR` 아르헨티나 · `CL` 칠레
`GB` 영국 · `DE` 독일 · `FR` 프랑스 · `IT` 이탈리아 · `ES` 스페인 · `NL` 네덜란드
`SE` 스웨덴 · `PL` 폴란드 · `TR` 튀르키예 · `RU` 러시아
`AU` 호주 · `NZ` 뉴질랜드 · `ZA` 남아공 · `EG` 이집트 · `NG` 나이지리아 · `KE` 케냐

전체 목록은 `python3 scripts/worldmap.py --help` 대신 아래로 확인한다:

~~~bash
python3 -c "import sys;sys.path.insert(0,'scripts');import worldmap as w;\
print(sorted(p['cc']+' '+p['name'] for p in w.load_source()))"
~~~

모르는 코드를 넣으면 그 자리에서 에러가 난다 (조용히 무시하지 않는다).

## 크기

경로를 슬라이드에 인라인으로 박으므로 지도 한 장이 그만큼 무겁다. **프레임 밖 경로는
자동으로 버리기 때문에** 확대할수록 가벼워진다 (보이는 결과는 그대로다).

| `--focus` | 경로 | 크기 |
|---|---|---|
| `world` | 257 | 149KB |
| `apac` | 126 | 82KB |
| `as` | 101 | 74KB |
| `na` | 73 | 50KB |
| `eu` / `af` | 79 / 89 | 44KB |
| `sa` | 32 | 20KB |
| `oc` | 12 | 12KB |

`--simplify` 로 더 줄일 수는 있지만 **기본값 0 을 권한다.** 0.3 만 줘도 `--focus eu`
같은 확대 뷰에서 렌더 픽셀의 35%가 달라진다 (해안선이 각지게 뭉개진다).

## 하지 말 것

- `assets/worldmap.svg` 원본을 직접 편집하기 — 생성기가 매번 다시 읽는다. 색은 CSS 로
- 한 장에 지도 두 개 — `data-region` 이 겹치면 `--region` 으로 다르게 줄 것
- `--palette continent` 를 범례 없이 켜기 — 색이 무슨 뜻인지 아무도 모른다
- 남극을 하이라이트하기 — 기본으로 흐리게 깔려 있고 호버도 안 먹는다 (의도된 것)

## 출처

`assets/worldmap.svg` 는 amCharts 의 SVG Map Generator
(dojo.amcharts.com/svg-map-generator) 로 만든 파일이다. 원본 주석을 파일에 그대로 남겨 뒀다.
다른 지도로 갈아끼우려면 나라마다 `id="<ISO2>"` 와 `title` 이 있는 SVG 여야 하고,
`worldmap.py` 의 `CC2CONT` 와 `FOCUS_BOX` 를 새 좌표계에 맞춰 다시 잡아야 한다.
