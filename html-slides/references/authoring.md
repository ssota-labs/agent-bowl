# 슬라이드 작성 — 마크업 계약과 레이아웃 레시피

## 파일 뼈대

~~~html
<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>슬라이드 제목</title>
<link rel="stylesheet" href="../assets/deck.css">
<link rel="stylesheet" href="../assets/theme.css">
<link rel="stylesheet" href="../assets/regions.css">
</head>
<body>

<section class="slide" data-slide="02" data-title="슬라이드 제목">
  ...
</section>

<script src="../assets/regions.js"></script>
</body>
</html>
~~~

`.slide` 는 1280×720 고정, `padding: 64px`, `display:flex; flex-direction:column; gap:28px`, `overflow:hidden`.
즉 최상위 자식들은 세로로 쌓이고, 남는 높이는 `.fill` 을 붙인 자식이 먹는다.

시각 편집기는 `data-region` / `data-part` 만 클릭·패치한다. 임의 DOM 전체 IDE는 아니다.
`theme.css` 의 관리 토큰은 `/* slidecraft:tokens:start */` … `end` 블록이다.

## data-* 계약

| 속성 | 어디에 | 왜 |
|------|--------|----|
| `data-slide="02"` | `.slide` | 슬라이드 번호 |
| `data-title="…"` | `.slide` | 주소록 헤더에 표시 |
| `data-region="kpi-revenue"` | 주소를 붙일 블록 | **필수.** 없으면 지목 불가 |
| `data-label="매출 KPI 카드"` | 같은 블록 | **필수.** 사용자가 부를 한글 이름 |
| `data-role="차트"` | 블록 | 역할 자동추정을 덮어쓸 때만 |
| `data-part="value"` | 블록 내부 조각 | 2레벨 주소 `kpi-revenue.value` |
| `data-region-color="blue"` | 블록 | 색을 고정하고 싶을 때 (기본은 문서 순서 자동) |
| `data-overlap-ok` | 배경/장식 요소 | QA 겹침 경고 끄기 |

**어디에 `data-region` 을 붙이나** — "사용자가 통째로 가리켜 말할 만한 단위"에 붙인다.
카드 하나, 차트 하나, 헤더 하나, 푸터 하나. 너무 잘게 쪼개면 12색을 넘고, 너무 크게 잡으면 지목이 안 된다.
**한 슬라이드 4~9개가 적정**이다.

## 타이포 클래스

| 클래스 | 크기 | 용도 |
|--------|------|------|
| `.t-title` | 52px 800 | 표지·섹션 대제목 |
| `.t-head` | 28px 700 | 슬라이드 제목, 카드 제목 |
| `.t-sub` | 22px 500 | 부제 |
| `.t-body` | 19px | 본문 |
| `.t-small` | 15px | 카드 안 설명 |
| `.t-cap` | 14px | 라벨·캡션·출처 |
| `.t-eyebrow` | 14px 800 대문자 | 제목 위 카테고리 |
| `.t-kpi` | 76px 800 | 큰 숫자 |
| `.em` / `.strong` | — | 강조색 / 진하게 |

## 레이아웃 클래스

`.row` `.col` `.fill` `.between` `.center` `.grid-2` `.grid-3` `.grid-4`
`.s-head`(슬라이드 헤더) `.s-num`(쪽번호) `.s-foot`(푸터, `margin-top:auto`)
`.card` (`.outline` `.brand` `.edge`) `.chip`(`.accent`) `.steps`>`.step`>`.n`
`.list`>`li` `.tbl` `.bars`>`.b`>`i`+`span` `.bleed` `.bleed-l` `.bleed-r`
`.ic`(`.ic-inline` `.ic-lg` `.ic-xl` `.ic-accent`) — 아이콘. 2만여 개가 스킬에 구워져 있다:
`python3 $S icons find 상승` → `icons get lucide:trending-up` ([icons.md](icons.md))
**한 덱에 한 세트만.** 섞으면 `qa` 가 오류로 잡는다.
`.slide.dark` — 어두운 슬라이드(표지/결론). 안쪽 색 변수가 자동 반전된다.

## 레시피

### 표지 (어두운)

~~~html
<section class="slide dark" data-slide="01" data-title="2026 성장 전략">
  <div class="bleed-r" data-overlap-ok style="background:linear-gradient(160deg,var(--accent),transparent 70%);opacity:.35"></div>
  <div class="fill col" style="justify-content:center;max-width:760px" data-region="cover" data-label="표지 타이틀 영역">
    <p class="t-eyebrow" data-part="eyebrow">2026 STRATEGY</p>
    <h1 class="t-title" data-part="title">엔터프라이즈로 축을 옮긴다</h1>
    <p class="t-sub" data-part="sub">상반기 실적 리뷰와 하반기 실행 계획</p>
  </div>
  <footer class="s-foot" data-region="footer" data-label="하단 푸터">
    <span>전략기획팀</span><span data-part="date">2026-08-07</span>
  </footer>
</section>
~~~

### KPI 3장 + 차트 + 인사이트

~~~html
<header class="s-head" data-region="header" data-label="상단 헤더">
  <div>
    <p class="t-eyebrow" data-part="eyebrow">H1 REVIEW</p>
    <h2 class="t-head" data-part="title">2026 상반기 실적 요약</h2>
  </div>
  <span class="s-num">02</span>
</header>

<div class="grid-3">
  <div class="card edge" data-region="kpi-revenue" data-label="매출 KPI 카드">
    <p class="t-cap" data-part="label">누적 매출</p>
    <p class="t-kpi" data-part="value">142<span style="font-size:32px">억</span></p>
    <p class="t-small" data-part="delta">전년 동기 대비 <b class="em">+38%</b></p>
  </div>
  <!-- kpi-users, kpi-churn 동일 구조 -->
</div>

<div class="row fill">
  <div class="card fill" data-region="chart" data-label="분기별 매출 차트">
    <p class="t-cap">분기별 매출 (억원)</p>
    <div class="bars fill">
      <div class="b"><i style="--v:38%"></i><span>24 Q3</span></div>
      <div class="b on"><i style="--v:92%"></i><span>26 Q1</span></div>
    </div>
  </div>
  <div class="col" style="width:400px">
    <div class="card brand fill" data-region="insight" data-label="핵심 인사이트 박스">…</div>
    <div class="card outline" data-region="risk" data-label="리스크 박스">…</div>
  </div>
</div>

<footer class="s-foot" data-region="footer" data-label="하단 푸터">
  <span>2026 성장 전략</span><span data-part="source">출처: 내부 BI</span>
</footer>
~~~

### 좌우 2단 (설명 + 목록)

~~~html
<div class="row fill" style="gap:56px">
  <div class="col fill" style="justify-content:center" data-region="lead" data-label="왼쪽 설명 영역">
    <h3 class="t-head" data-part="title">왜 지금인가</h3>
    <p class="t-body" data-part="body">…</p>
  </div>
  <ul class="list fill" data-region="points" data-label="오른쪽 핵심 목록">
    <li>…</li><li>…</li><li>…</li>
  </ul>
</div>
~~~

### 프로세스 4단계

~~~html
<div class="steps fill" data-region="process" data-label="4단계 프로세스">
  <div class="step"><span class="n">STEP 1</span><b class="t-body">진단</b><p class="t-small">…</p></div>
  <div class="step"><span class="n">STEP 2</span>…</div>
</div>
~~~

### 표

~~~html
<table class="tbl" data-region="table" data-label="세그먼트별 실적 표">
  <thead><tr><th>세그먼트</th><th>매출</th><th>YoY</th></tr></thead>
  <tbody>
    <tr><td>엔터프라이즈</td><td class="num">96억</td><td class="num">+61%</td></tr>
  </tbody>
</table>
~~~

### 막대 차트

높이는 `<i style="--v:72%">` 로 준다 (`height` 아님). `.b.on` 을 붙이면 강조색.
선/파이 등 더 복잡한 차트는 인라인 `<svg>` 로 직접 그리고 `data-region` 을 `<svg>` 를 감싼 컨테이너에 건다.

## 흔한 함정

- **`.fill` 을 안 붙여서** 콘텐츠가 위로 몰리고 아래가 텅 빔 → 세로로 늘어야 하는 자식에 `.fill`
- **flex 자식이 안 줄어듦** → `min-width:0` 이 이미 `.fill`/`.card` 에 들어있다. 커스텀 요소엔 직접 넣기
- **퍼센트 높이가 안 먹음** → 부모 높이가 불확정. `.bars` 처럼 `flex-basis` 로 푼다
- **텍스트가 카드를 뚫고 나감** → `qa` 가 "텍스트가 영역 밖으로 넘침"으로 잡는다. 글자 크기를 줄이지 말고 **내용을 줄이는** 쪽을 먼저 검토
- **`data-region` 을 `.fill` 래퍼가 아니라 안쪽 텍스트에 붙임** → 주소록 좌표가 실제 카드와 안 맞는다. 시각적 경계(카드 테두리)와 같은 요소에 붙인다
